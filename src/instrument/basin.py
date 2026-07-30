"""Basin escape measurement — did the model escape or return?

The central question: when a model's reasoning is perturbed into
unfamiliar territory, does it continue exploring or converge back
to familiar patterns?

BasinMetrics quantifies this as a single pass/fail score:
- escape_score > 0.5: model preserved novelty (escaped the attractor)
- escape_score < 0.3: model returned to familiar territory (captured)
- escape_score 0.3-0.5: inconclusive
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .trajectory import ReasoningTrajectory, compute_trajectory_distance


@dataclass
class BasinMetrics:
    """Metrics describing a model's exploration behavior under perturbation.

    H₀: There is no systematic difference in escape behavior between models.
    H₁: RL-trained models show higher escape rates than SFT-dominant models.

    Interpretation:
    - High escape_score + low recovery_ratio: model explored novel territory
    - Low escape_score + high recovery_ratio: model was captured by attractor
    - Inconclusive: perturbation too weak or measurement too noisy
    """

    perturbation_strength: float = 0.0
    perturbation_operator: str = ""
    perturbation_class: str = "semantic"
    initial_distance: float = 0.0
    final_distance: float = 0.0
    escape_score: float = 0.0
    recovery_ratio: float = 0.0
    exploration_tokens: int = 0
    recovery_tokens: int = 0
    converged_back: bool | None = None
    convergence_step: int | None = None
    verdict: str = ""

    model: str = ""
    task: str = ""
    run_id: str = ""
    baseline_run_id: str = ""

    def get_verdict(self) -> str:
        """Class-aware verdict on whether the model escaped its basin.

        Interpretation depends on perturbation type:

        SEMANTIC perturbations (false premises, missing constraints, etc.):
            Low escape = GOOD — model correctly handled the in-manifold perturbation
            High escape = model over-reacted to a known pattern (potentially bad)

        MANIFOLD perturbations (alien vocab, reverse causality, etc.):
            High escape = GOOD — model explored novel territory
            Low escape = model was captured by attractor (returned from unfamiliar space)
        """
        c = self.perturbation_class

        if self.escape_score > 0.7:
            if c == "semantic":
                return "over-escaped — model over-reacted to a known pattern (semantic perturbation, should have stayed in-manifold)"
            return "escaped — model explored novel territory and preserved it (manifold class expected this)"
        elif self.escape_score > 0.5:
            if c == "semantic":
                return "inflated — semantic perturbation produced unnecessary deviation"
            return "partial_escape — model deviated from baseline but partially returned"
        elif self.escape_score > 0.3:
            if c == "semantic":
                return "stable — semantic perturbation handled in-manifold (within expected reasoning range)"
            return "tentative — model entered unfamiliar territory briefly but returned"
        else:
            if c == "semantic":
                return "competent — model rejected perturbation and maintained sound reasoning (semantic class, truth-seeking)"
            return "captured — model returned from unfamiliar space back to attractor basin"

    def to_dict(self) -> dict[str, Any]:
        return {
            "perturbation_strength": self.perturbation_strength,
            "perturbation_operator": self.perturbation_operator,
            "perturbation_class": self.perturbation_class,
            "initial_distance": round(self.initial_distance, 4),
            "final_distance": round(self.final_distance, 4),
            "escape_score": round(self.escape_score, 4),
            "recovery_ratio": round(self.recovery_ratio, 4),
            "exploration_tokens": self.exploration_tokens,
            "recovery_tokens": self.recovery_tokens,
            "converged_back": self.converged_back,
            "convergence_step": self.convergence_step,
            "verdict": self.get_verdict(),
            "model": self.model,
            "task": self.task,
            "run_id": self.run_id,
            "baseline_run_id": self.baseline_run_id,
        }


def measure_basin_escape(
    baseline: ReasoningTrajectory,
    perturbed: ReasoningTrajectory,
    perturbation_strength: float = 0.5,
    perturbation_operator: str = "",
    perturbation_class: str = "semantic",
) -> BasinMetrics:
    """Measure whether the model escaped its attractor basin.

    Args:
        baseline: The model's reasoning trajectory on the unperturbed task.
        perturbed: The model's reasoning trajectory after perturbation.
        perturbation_strength: How hard the perturbation pushed (0.0-1.0).
        perturbation_operator: Which perturbation operator was applied.

    Returns:
        BasinMetrics with escape score and supporting diagnostics.

    The escape score is computed as:
        escape_score = final_distance / max(initial_distance, 0.01)

    Where:
    - initial_distance is an estimate of perturbation magnitude
      (based on the difference between the first step of the perturbed
      trajectory and the baseline trajectory).
    - final_distance is the similarity between the full baseline and
      perturbed trajectories.

    If final_distance ≈ 0 (model converged back to baseline patterns):
        escape_score ≈ 0 → captured by attractor basin.
    If final_distance ≈ initial_distance (model stayed in novel territory):
        escape_score ≈ 1 → escaped the attractor basin.
    """
    # Initial distance: compare first steps as a proxy for perturbation magnitude
    initial = 0.0
    if baseline.steps and perturbed.steps:
        baseline_first = ReasoningTrajectory(
            run_id="baseline_first",
            steps=[baseline.steps[0]],
            total_tokens=baseline.steps[0].tokens_used,
        )
        perturbed_first = ReasoningTrajectory(
            run_id="perturbed_first",
            steps=[perturbed.steps[0]],
            total_tokens=perturbed.steps[0].tokens_used,
        )
        initial = compute_trajectory_distance(baseline_first, perturbed_first)

    # If no steps, fall back to perturbation_strength as initial distance estimate
    if initial < 0.01:
        initial = perturbation_strength * 0.5

    # Final distance: full trajectory comparison
    final = compute_trajectory_distance(baseline, perturbed)

    # Escape score: how much of the initial perturbation was preserved?
    # Clamp to [0, 1]
    escape_score = min(max(final / max(initial, 0.01), 0.0), 1.0)

    # Recovery ratio: what fraction of tokens look like recovery?
    # v1: if trajectory returned close to baseline, most tokens were recovery
    recovery_ratio = 1.0 - escape_score

    # Token classification
    total_tokens = max(perturbed.total_tokens, 1)
    exploration_tokens = int(total_tokens * escape_score)
    recovery_tokens = total_tokens - exploration_tokens

    # Convergence detection
    converged_back = escape_score < 0.3

    # Estimate convergence step
    convergence_step = None
    if converged_back and len(perturbed.steps) > 0:
        convergence_step = _estimate_convergence_step(baseline, perturbed)

    return BasinMetrics(
        perturbation_strength=perturbation_strength,
        perturbation_operator=perturbation_operator,
        perturbation_class=perturbation_class,
        initial_distance=initial,
        final_distance=final,
        escape_score=escape_score,
        recovery_ratio=recovery_ratio,
        exploration_tokens=exploration_tokens,
        recovery_tokens=recovery_tokens,
        converged_back=converged_back,
        convergence_step=convergence_step,
        model=perturbed.model,
        task=perturbed.task,
        run_id=perturbed.run_id,
        baseline_run_id=baseline.run_id,
    )


def _estimate_convergence_step(
    baseline: ReasoningTrajectory,
    perturbed: ReasoningTrajectory,
) -> int | None:
    """Estimate the step at which the perturbed trajectory converged back.

    Compares each step of the perturbed trajectory against the baseline,
    looking for the point where tool call patterns start matching.
    """
    baseline_tools = set(baseline.tool_call_sequence())
    if not baseline_tools:
        return None

    for step in perturbed.steps:
        if step.tool_name in baseline_tools:
            return step.step_index

    return None
