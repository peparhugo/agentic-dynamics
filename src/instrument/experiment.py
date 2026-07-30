"""Experiment runner — executes perturbation experiments and produces reports.

Wires the instrument modules together with an LLM adapter to run
controlled experiments: baseline → perturbed → measure → report.

Designed to be model-agnostic and self-contained. Every experiment
produces a structured result that can be persisted to a lab book.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .perturb import Perturbation, build_operators, perturb_prompt
from .trajectory import ReasoningTrajectory, TrajectoryStep, compute_trajectory_distance
from .basin import BasinMetrics, measure_basin_escape
from .recovery import classify_trajectory_segments, recovery_token_ratio


@dataclass
class ExperimentConfig:
    """Configuration for a perturbation experiment.

    Args:
        name: Experiment name for reporting.
        task: The task prompt to perturb and measure.
        operators: Which perturbation operators to test.
        strengths: Perturbation strengths to test per operator.
        model: Model identifier passed to the LLM adapter.
        rng_seed: Seed for reproducible perturbations.
        output_dir: Where to write result files (None = no persistence).
    """

    name: str = "unnamed"
    task: str = ""
    operators: list[str] = field(default_factory=lambda: [
        "inject_alien_vocab", "invert_constraint", "shift_framing",
        "inject_false_premise", "remove_critical_constraint",
        "inject_phantom_success", "reverse_causality",
        "inject_competing_goal", "force_abandonment",
    ])
    strengths: list[float] = field(default_factory=lambda: [0.5, 0.8])
    model: str = ""
    rng_seed: int = 42
    output_dir: Path | None = None


@dataclass
class ExperimentRun:
    """Result of a single perturbation run."""

    operator: str
    strength: float
    perturbation: Perturbation
    trajectory: ReasoningTrajectory
    basin: BasinMetrics
    recovery_ratio: float
    exploration_tokens: int
    recovery_tokens: int
    response_text: str = ""
    response_tokens: int = 0
    cost_usd: float = 0.0
    duration_s: float = 0.0
    error: str = ""


@dataclass
class ExperimentResult:
    """Complete result of a perturbation experiment."""

    config: ExperimentConfig
    baseline: ExperimentRun | None = None
    runs: list[ExperimentRun] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_duration_s: float = 0.0

    def summary(self) -> str:
        """Generate a human-readable summary table."""
        lines = ["", "=" * 80, f"Experiment: {self.config.name}", "=" * 80, ""]
        if self.baseline:
            lines.append(f"Baseline: {self.baseline.response_tokens} tokens, "
                         f"${self.baseline.cost_usd:.4f}")
            lines.append("")

        header = f"{'Operator':<28} {'Str':>4} {'Escape':>7} {'Recov':>6} {'Tokens':>7} {'$':>7} {'Verdict'}"
        lines.append(header)
        lines.append("-" * 85)

        for r in self.runs:
            lines.append(
                f"{r.operator:<28} {r.strength:>4.1f} "
                f"{r.basin.escape_score:>7.3f} {r.recovery_ratio:>6.3f} "
                f"{r.response_tokens:>7} {r.cost_usd:>7.4f}  "
                f"{r.basin.get_verdict()[:40]}"
            )

        lines.append("-" * 85)
        lines.append(f"Total: {self.total_tokens} tokens, ${self.total_cost_usd:.4f}, "
                     f"{self.total_duration_s:.1f}s")
        lines.append("")

        # Per-operator averages
        lines.append("Per-operator averages:")
        lines.append(f"{'Operator':<28} {'Avg Escape':>11} {'Avg Recovery':>13}")
        lines.append("-" * 55)
        by_op: dict[str, list[ExperimentRun]] = {}
        for r in self.runs:
            by_op.setdefault(r.operator, []).append(r)
        for op, runs in sorted(by_op.items()):
            avg_esc = sum(r.basin.escape_score for r in runs) / len(runs)
            avg_rec = sum(r.recovery_ratio for r in runs) / len(runs)
            lines.append(f"{op:<28} {avg_esc:>11.3f} {avg_rec:>13.3f}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.config.name,
            "task": self.config.task[:200],
            "model": self.config.model,
            "baseline_tokens": self.baseline.response_tokens if self.baseline else 0,
            "runs": [
                {
                    "operator": r.operator,
                    "strength": r.strength,
                    "escape_score": round(r.basin.escape_score, 4),
                    "recovery_ratio": round(r.recovery_ratio, 4),
                    "exploration_tokens": r.exploration_tokens,
                    "recovery_tokens": r.recovery_tokens,
                    "response_tokens": r.response_tokens,
                    "cost_usd": r.cost_usd,
                    "duration_s": r.duration_s,
                    "verdict": r.basin.get_verdict(),
                    "error": r.error,
                }
                for r in self.runs
            ],
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "total_duration_s": self.total_duration_s,
        }


def run_experiment(
    config: ExperimentConfig,
    llm_invoke: Callable[[str], tuple[str, int, float]],
    *,
    on_progress: Callable[[str], None] | None = None,
) -> ExperimentResult:
    """Run a complete perturbation experiment.

    Args:
        config: Experiment configuration.
        llm_invoke: Function that takes a prompt string and returns
                    (response_text, tokens_used, cost_usd).
        on_progress: Optional callback for progress updates.

    Returns:
        ExperimentResult with baseline + all perturbation runs.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    result = ExperimentResult(config=config, started_at=now)
    operators = build_operators()

    def log(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    # ── Baseline ──
    log("Running baseline...")
    t0 = time.monotonic()
    baseline_text, baseline_tokens, baseline_cost = llm_invoke(config.task)
    baseline_duration = time.monotonic() - t0

    baseline_traj = ReasoningTrajectory(
        run_id="baseline",
        model=config.model,
        task=config.task,
    )
    baseline_traj.add_step(TrajectoryStep(
        step_index=0,
        thought="generating response to unperturbed prompt",
        action=baseline_text,
        tool_name="llm_invoke",
        tokens_used=baseline_tokens,
    ))
    baseline_traj.total_tokens = baseline_tokens
    baseline_traj.total_output_tokens = baseline_tokens

    result.baseline = ExperimentRun(
        operator="baseline",
        strength=0.0,
        perturbation=Perturbation(operator="baseline", description="unperturbed baseline"),
        trajectory=baseline_traj,
        basin=BasinMetrics(escape_score=1.0, recovery_ratio=0.0),
        recovery_ratio=0.0,
        exploration_tokens=baseline_tokens,
        recovery_tokens=0,
        response_text=baseline_text,
        response_tokens=baseline_tokens,
        cost_usd=baseline_cost,
        duration_s=baseline_duration,
    )
    result.total_tokens += baseline_tokens
    result.total_cost_usd += baseline_cost
    result.total_duration_s += baseline_duration
    log(f"Baseline: {baseline_tokens} tokens, ${baseline_cost:.4f}")

    # ── Perturbation runs ──
    total_runs = len(config.operators) * len(config.strengths)
    run_idx = 0

    for op_name in config.operators:
        for strength in config.strengths:
            run_idx += 1
            log(f"[{run_idx}/{total_runs}] {op_name} (strength={strength})...")

            perturbed_prompt, record = perturb_prompt(
                config.task, op_name,
                strength=strength,
                rng_seed=config.rng_seed + run_idx,
            )

            t0 = time.monotonic()
            try:
                response_text, tokens, cost = llm_invoke(perturbed_prompt)
                duration = time.monotonic() - t0
                error = ""
            except Exception as e:
                response_text = ""
                tokens = 0
                cost = 0.0
                duration = time.monotonic() - t0
                error = str(e)

            # Build trajectory
            traj = ReasoningTrajectory(
                run_id=f"{op_name}_{strength}",
                model=config.model,
                task=config.task,
                perturbation_applied=op_name,
                perturbation_strength=strength,
            )
            if response_text:
                traj.add_step(TrajectoryStep(
                    step_index=0,
                    thought="responding to perturbed prompt",
                    action=response_text,
                    tool_name="llm_invoke",
                    tokens_used=tokens,
                ))
            traj.total_tokens = tokens
            traj.total_output_tokens = tokens

            # Basin escape
            basin = measure_basin_escape(
                baseline_traj, traj,
                perturbation_strength=strength,
                perturbation_operator=op_name,
            )

            # Recovery classification
            classifications = classify_trajectory_segments(baseline_traj, traj)
            expl_tokens, rec_tokens, rec_ratio = recovery_token_ratio(classifications)

            run = ExperimentRun(
                operator=op_name,
                strength=strength,
                perturbation=record,
                trajectory=traj,
                basin=basin,
                recovery_ratio=rec_ratio,
                exploration_tokens=expl_tokens,
                recovery_tokens=rec_tokens,
                response_text=response_text,
                response_tokens=tokens,
                cost_usd=cost,
                duration_s=duration,
                error=error,
            )
            result.runs.append(run)
            result.total_tokens += tokens
            result.total_cost_usd += cost
            result.total_duration_s += duration

            log(f"  escape={basin.escape_score:.3f} recovery={rec_ratio:.3f} "
                f"tokens={tokens} cost=${cost:.4f} {basin.get_verdict()}")

    result.completed_at = datetime.now(timezone.utc).isoformat()

    # Persist if output dir specified
    if config.output_dir:
        config.output_dir.mkdir(parents=True, exist_ok=True)
        result_path = config.output_dir / "experiment_result.json"
        result_path.write_text(json.dumps(result.to_dict(), indent=2, default=str))

    return result
