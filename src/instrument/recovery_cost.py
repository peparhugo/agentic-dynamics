"""Recovery cost metric — connects basin escape to economic cost.

Measures how many extra tokens and dollars a model burns to recover
from a perturbation. This is the bridge between Phase 1 (conceptual:
how does constraint recovery work?) and Phase 2 (empirical: what does
resilience cost?).

Recovery cost answers: "Removing constraint X costs $Y extra to
re-derive and re-implement." Combined with basin escape score,
it tells you whether resilience is worth the cost.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RecoveryCost:
    """The cost of recovering from a perturbation.

    For each constraint removed or perturbed, measures the
    incremental tokens, dollars, and energy the model spent
    to recover the missing constraint compared to baseline.
    """

    # What was perturbed
    operator: str = ""
    perturbation_class: str = ""
    strength: float = 0.0

    # Baseline (unperturbed) costs
    baseline_tokens: int = 0
    baseline_cost_usd: float = 0.0
    baseline_energy_j: float = 0.0

    # Perturbed costs
    perturbed_tokens: int = 0
    perturbed_cost_usd: float = 0.0
    perturbed_energy_j: float = 0.0

    # Recovery: how much extra was spent
    recovery_tokens: int = 0
    recovery_cost_usd: float = 0.0
    recovery_energy_j: float = 0.0

    # Recovery ratio: what fraction of perturbed cost was "extra"
    recovery_token_ratio: float = 0.0
    recovery_cost_ratio: float = 0.0

    # Correctness
    baseline_correctness: float = 0.0
    perturbed_correctness: float = 0.0
    correctness_delta: float = 0.0

    # Verdict
    verdict: str = ""

    def compute_verdict(self) -> str:
        """Classify the recovery profile.

        Four regimes:
        - Efficient recovery: low extra cost, high correctness
          → perturbation was cheap to handle, model stayed competent
        - Expensive recovery: high extra cost, high correctness
          → model fought hard and succeeded — resilience premium
        - Failed recovery: any extra cost, low correctness
          → perturbation broke the model
        - No recovery needed: zero extra cost (perturbation ignored)
          → model didn't notice the perturbation
        """
        if self.correctness_delta < -0.2:
            return "failed — perturbation degraded correctness"
        if self.recovery_cost_usd < 0.001:
            return "ignored — model did not respond to perturbation"
        if self.recovery_cost_usd < 0.01:
            return "efficient — cheap to recover, correctness maintained"
        if self.perturbed_correctness >= self.baseline_correctness:
            return "expensive — costly recovery, but correctness held"
        return "degraded — spent extra but correctness suffered"

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator": self.operator,
            "perturbation_class": self.perturbation_class,
            "strength": self.strength,
            "baseline_tokens": self.baseline_tokens,
            "baseline_cost_usd": round(self.baseline_cost_usd, 6),
            "perturbed_tokens": self.perturbed_tokens,
            "perturbed_cost_usd": round(self.perturbed_cost_usd, 6),
            "recovery_tokens": self.recovery_tokens,
            "recovery_cost_usd": round(self.recovery_cost_usd, 6),
            "recovery_energy_j": round(self.recovery_energy_j, 2),
            "recovery_token_ratio": round(self.recovery_token_ratio, 4),
            "recovery_cost_ratio": round(self.recovery_cost_ratio, 4),
            "baseline_correctness": round(self.baseline_correctness, 4),
            "perturbed_correctness": round(self.perturbed_correctness, 4),
            "correctness_delta": round(self.correctness_delta, 4),
            "verdict": self.verdict or self.compute_verdict(),
        }


def compute_recovery_cost(
    baseline_tokens: int = 0,
    baseline_cost_usd: float = 0.0,
    baseline_correctness: float = 0.0,
    perturbed_tokens: int = 0,
    perturbed_cost_usd: float = 0.0,
    perturbed_correctness: float = 0.0,
    operator: str = "",
    perturbation_class: str = "",
    strength: float = 0.0,
    energy_per_token: float = 0.1,  # conservative J/tok from TokenPowerBench
) -> RecoveryCost:
    """Compute the recovery cost of a perturbation.

    Measures how many extra tokens, dollars, and joules the model
    spent to handle the perturbation compared to baseline.

    Args:
        baseline_tokens/cost/correctness: Unperturbed reference.
        perturbed_tokens/cost/correctness: Perturbed result.
        operator, perturbation_class, strength: Metadata.
        energy_per_token: Conservative J/tok estimate.

    Returns:
        RecoveryCost with the full recovery profile.
    """
    rc = RecoveryCost()
    rc.operator = operator
    rc.perturbation_class = perturbation_class
    rc.strength = strength

    rc.baseline_tokens = baseline_tokens
    rc.baseline_cost_usd = baseline_cost_usd
    rc.baseline_correctness = baseline_correctness

    rc.perturbed_tokens = perturbed_tokens
    rc.perturbed_cost_usd = perturbed_cost_usd
    rc.perturbed_correctness = perturbed_correctness

    # Recovery = extra spent
    rc.recovery_tokens = max(0, perturbed_tokens - baseline_tokens)
    rc.recovery_cost_usd = max(0, perturbed_cost_usd - baseline_cost_usd)
    rc.recovery_energy_j = rc.recovery_tokens * energy_per_token

    # Recovery ratios
    rc.recovery_token_ratio = rc.recovery_tokens / max(perturbed_tokens, 1)
    rc.recovery_cost_ratio = rc.recovery_cost_usd / max(perturbed_cost_usd, 0.000001)

    rc.correctness_delta = perturbed_correctness - baseline_correctness
    rc.verdict = rc.compute_verdict()

    return rc


def recovery_summary_table(recoveries: list[RecoveryCost]) -> str:
    """Generate a markdown summary table of recovery costs."""
    lines = [
        "| Operator | Class | Recovery Tokens | Recovery $ | Recovery % | Correctness Δ | Verdict |",
        "|----------|-------|----------------|------------|------------|---------------|---------|",
    ]
    for rc in recoveries:
        lines.append(
            f"| {rc.operator} | {rc.perturbation_class} | "
            f"{rc.recovery_tokens:,} | ${rc.recovery_cost_usd:.4f} | "
            f"{rc.recovery_token_ratio:.0%} | {rc.correctness_delta:+.0%} | "
            f"{rc.verdict} |"
        )
    return "\n".join(lines)
