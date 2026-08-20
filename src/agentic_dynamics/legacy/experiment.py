"""Experiment runner — measures solution quality under perturbation.

The dependent variable is correctness-per-unit-cost, not text similarity.
Each run: perturb problem → model builds solution → evaluate correctness →
measure token/energy cost → compare to baseline.

The research question: does perturbation class predict correctness/cost variance?
"""

from __future__ import annotations

import warnings
warnings.warn(
    "instrument.experiment is deprecated. The current pipeline uses "
    "scripts/run.py with instrument.opencode.run_opencode_agentic directly.",
    DeprecationWarning, stacklevel=2
)

import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from agentic_dynamics.measurement.perturb import Perturbation, build_operators, derive_seed, perturb_prompt
from agentic_dynamics.measurement.basin import BasinMetrics, measure_basin_escape
from agentic_dynamics.measurement.solution import SolutionMetrics, evaluate_solution
from agentic_dynamics.measurement.efficiency import EfficiencyMetrics, compute_efficiency
from agentic_dynamics.measurement.strategy import StrategyReport, classify_strategy


@dataclass
class ExperimentConfig:
    """Configuration for a perturbation experiment."""

    name: str = "unnamed"
    task: str = ""
    constraints: list[str] = field(default_factory=list)
    operators: list[str] = field(default_factory=lambda: [
        "inject_alien_vocab", "invert_constraint", "shift_framing",
        "inject_false_premise", "remove_critical_constraint",
        "inject_phantom_success", "reverse_causality",
        "inject_competing_goal", "force_abandonment",
    ])
    strengths: list[float] = field(default_factory=lambda: [0.5, 0.8])
    model: str = ""
    model_id: str = ""
    rng_seed: int = 42
    repetitions: int = 1
    output_dir: Path | None = None


@dataclass
class ExperimentRun:
    """Single perturbed run result — all three measurement dimensions."""

    operator: str
    strength: float
    perturbation: Perturbation
    basin: BasinMetrics
    solution: SolutionMetrics
    efficiency: EfficiencyMetrics
    strategy: StrategyReport
    response_text: str = ""
    error: str = ""


@dataclass
class ExperimentResult:
    """Complete experiment result."""

    config: ExperimentConfig
    baseline: ExperimentRun | None = None
    runs: list[ExperimentRun] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_energy_j: float = 0.0
    total_duration_s: float = 0.0

    def summary(self) -> str:
        lines = ["", "=" * 100, f"Experiment: {self.config.name}", "=" * 100, ""]

        if self.baseline:
            b = self.baseline
            lines.append(
                f"Baseline: correctness={b.solution.correctness_score:.0%} "
                f"constraints={b.solution.constraints_met}/{b.solution.constraints_total} "
                f"tokens={b.efficiency.total_tokens:,} ${b.efficiency.total_cost_usd:.4f} "
                f"energy=~{b.efficiency.total_energy_j:.0f}J "
                f"LOC={b.solution.lines_of_code}"
            )
            lines.append("")

        header = f"{'Operator':<25} {'S':>3} {'Escape':>6} {'Correct':>6} {'Tok':>8} {'Think%':>6} {'$':>8} {'Strategy':>13}"
        lines.append(header)
        lines.append("-" * 100)

        for r in self.runs:
            lines.append(
                f"{r.operator:<25} {r.strength:>3.1f} "
                f"{r.basin.escape_score:>6.3f} "
                f"{r.solution.correctness_score:>6.0%} "
                f"{r.efficiency.total_tokens:>8,} "
                f"{r.efficiency.thinking_ratio:>6.0%} "
                f"{r.efficiency.total_cost_usd:>8.4f} "
                f"{r.strategy.strategy.value:>13}"
            )

        lines.extend([
            "-" * 100,
            f"Total: {self.total_tokens:,} tokens, ${self.total_cost_usd:.4f}, ~{self.total_energy_j:.0f}J, {self.total_duration_s:.0f}s",
        ])

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.config.name, "task": self.config.task[:200],
            "model": self.config.model_id,
            "baseline": self.baseline.basin.to_dict() if self.baseline else None,
            "runs": [
                {
                    "operator": r.operator, "strength": r.strength,
                    "basin": r.basin.to_dict(),
                    "solution": r.solution.to_dict(),
                    "efficiency": r.efficiency.to_dict(),
                    "strategy": r.strategy.to_dict(),
                    "error": r.error,
                }
                for r in self.runs
            ],
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "total_energy_j": self.total_energy_j,
            "total_duration_s": self.total_duration_s,
        }


def run_experiment(
    config: ExperimentConfig,
    llm_invoke: Callable[[str], Any],
    *,
    on_progress: Callable[[str], None] | None = None,
) -> ExperimentResult:
    """Run a perturbation experiment measuring solution quality.

    llm_invoke must accept a prompt string and return an object with:
    - .text: the response text
    - .completion_tokens (or .total_tokens)
    - .prompt_tokens (optional)
    - .reasoning_tokens (optional)
    - .estimated_cost_usd (optional)
    """
    from datetime import datetime, timezone

    def _get(obj: Any, attr: str, default: Any = 0) -> Any:
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    now = datetime.now(timezone.utc).isoformat()
    result = ExperimentResult(config=config, started_at=now)
    ops = build_operators()

    def log(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    # ── Baseline ──
    log("Running baseline...")
    t0 = time.monotonic()
    baseline_obj = llm_invoke(config.task)
    baseline_text = _get(baseline_obj, "text", "")
    baseline_duration = time.monotonic() - t0

    baseline_sol = evaluate_solution(baseline_text, config.constraints)
    baseline_eff = compute_efficiency(
        prompt_tokens=_get(baseline_obj, "prompt_tokens"),
        completion_tokens=_get(baseline_obj, "completion_tokens"),
        reasoning_tokens=_get(baseline_obj, "reasoning_tokens"),
        total_tokens=_get(baseline_obj, "total_tokens"),
        solution=baseline_sol,
    )

    # Baseline basin: perfect match with itself, max correctness
    baseline_basin = BasinMetrics(
        escape_score=0.0, correctness=baseline_sol.correctness_score,
        constraints_met=baseline_sol.constraints_met,
        constraints_total=baseline_sol.constraints_total,
        total_tokens=baseline_eff.total_tokens,
        reasoning_tokens=baseline_eff.reasoning_tokens,
        thinking_ratio=baseline_eff.thinking_ratio,
        cost_usd=baseline_eff.total_cost_usd,
        estimated_energy_j=baseline_eff.total_energy_j,
        lines_of_code=baseline_sol.lines_of_code,
        model=config.model_id, task=config.task, run_id="baseline",
    )

    baseline_strat = classify_strategy(baseline_basin, baseline_sol, baseline_eff, "baseline")

    result.baseline = ExperimentRun(
        operator="baseline", strength=0.0,
        perturbation=Perturbation(operator="baseline"),
        basin=baseline_basin, solution=baseline_sol,
        efficiency=baseline_eff, strategy=baseline_strat,
        response_text=baseline_text,
    )
    result.total_tokens += baseline_eff.total_tokens
    result.total_cost_usd += baseline_eff.total_cost_usd
    result.total_energy_j += baseline_eff.total_energy_j
    result.total_duration_s += baseline_duration
    log(f"  correctness={baseline_sol.correctness_score:.0%} tokens={baseline_eff.total_tokens:,} ${baseline_eff.total_cost_usd:.4f}")

    # ── Perturbation runs ──
    total_runs = len(config.operators) * len(config.strengths) * config.repetitions
    run_idx = 0

    for op_name in config.operators:
        for strength in config.strengths:
            for rep in range(config.repetitions):
                run_idx += 1
                rep_str = f" (rep {rep+1}/{config.repetitions})" if config.repetitions > 1 else ""
                log(f"[{run_idx}/{total_runs}] {op_name} s={strength}{rep_str}...")

                op_def = ops.get(op_name)
                pert_class = op_def.perturbation_class if op_def else "semantic"

                perturbed_prompt, record = perturb_prompt(
                    config.task, op_name, strength=strength,
                    # seed_variant=0: repetition re-measures the SAME starting point
                    # (consistent with scripts/run.py); variant would deviate it.
                    rng_seed=derive_seed(config.task, op_name, strength, 0),
                )

                t0 = time.monotonic()
                try:
                    obj = llm_invoke(perturbed_prompt)
                    response_text = _get(obj, "text", "")
                    error = ""
                except Exception as e:
                    response_text = ""
                    obj = {}
                    error = str(e)
                duration = time.monotonic() - t0

                # Solution quality
                sol = evaluate_solution(response_text, config.constraints,
                                        baseline_code=baseline_text)

                # Efficiency
                eff = compute_efficiency(
                    prompt_tokens=_get(obj, "prompt_tokens"),
                    completion_tokens=_get(obj, "completion_tokens"),
                    reasoning_tokens=_get(obj, "reasoning_tokens"),
                    total_tokens=_get(obj, "total_tokens"),
                    solution=sol,
                )

                # Basin escape (output-based)
                basin = measure_basin_escape(
                    baseline_text, response_text,
                    baseline_correctness=baseline_sol.correctness_score,
                    perturbed_correctness=sol.correctness_score,
                    baseline_constraints_met=baseline_sol.constraints_met,
                    perturbed_constraints_met=sol.constraints_met,
                    baseline_loc=baseline_sol.lines_of_code,
                    perturbed_loc=sol.lines_of_code,
                    prompt_tokens=_get(obj, "prompt_tokens"),
                    completion_tokens=_get(obj, "completion_tokens"),
                    reasoning_tokens=_get(obj, "reasoning_tokens"),
                    perturbation_strength=strength,
                    perturbation_operator=op_name,
                    perturbation_class=pert_class,
                    model=config.model_id,
                    task=config.task,
                    run_id=f"{op_name}_{strength}",
                    cost_usd=eff.total_cost_usd,
                )

                # Strategy
                strat = classify_strategy(basin, sol, eff, pert_class)

                run = ExperimentRun(
                    operator=op_name, strength=strength,
                    perturbation=record, basin=basin,
                    solution=sol, efficiency=eff,
                    strategy=strat, response_text=response_text,
                    error=error,
                )
                result.runs.append(run)
                result.total_tokens += eff.total_tokens
                result.total_cost_usd += eff.total_cost_usd
                result.total_energy_j += eff.total_energy_j
                result.total_duration_s += duration

                log(f"  escape={basin.escape_score:.3f} correct={sol.correctness_score:.0%} "
                    f"tok={eff.total_tokens:,} think={eff.thinking_ratio:.0%} "
                    f"${eff.total_cost_usd:.4f} strat={strat.strategy.value}")

    result.completed_at = datetime.now(timezone.utc).isoformat()

    if config.output_dir:
        config.output_dir.mkdir(parents=True, exist_ok=True)
        (config.output_dir / f"{config.name}_{config.model_id}.json").write_text(
            json.dumps(result.to_dict(), indent=2, default=str)
        )

    return result
