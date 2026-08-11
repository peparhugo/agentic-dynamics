"""Durable Value Score — the north star metric.

Answers the Golden Circle question: did this agent make the system
better, or just bigger?

DVS = (correctness × architectural_fit × convention_adherence)
      ──────────────────────────────────────────────────────
      (session_cost + technical_debt_introduced + future_cost_impact)

DVS > 1 → net positive outcome (value created exceeds cost)
DVS < 1 → net negative outcome (cost exceeds value created)

Integrates measurements from all analysis layers:
  - correctness: from test pass rate
  - architectural_fit: from commit review agent
  - convention_adherence: from convention scoring
  - session_cost: from billing data
  - technical_debt_introduced: from SonarQube delta (normalized to $)
  - future_cost_impact: from entropy delta (normalized to $)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .commit_analysis import CommitAnalysis
from .review import CommitReview


# ── Normalization Constants ────────────────────────────────────

# Cost equivalents for quality deltas. These are calibrated heuristics
# and should be tuned against real-world maintenance cost data.
# Each unit of technical debt or entropy is estimated to cost $X
# in future maintenance burden.

DEBT_COST_PER_BUG = 0.50         # $ per bug introduced
DEBT_COST_PER_SMELL = 0.10       # $ per code smell introduced
DEBT_COST_PER_COMPLEXITY = 0.05  # $ per complexity point added
ENTROPY_COST_PER_001 = 0.25      # $ per 0.01 composite entropy increase


@dataclass
class DurableValueScore:
    """The north star metric for AI FinOps Dynamics."""

    correctness: float = 0.0           # [0-1] test pass rate
    architectural_fit: float = 0.0     # [0-1] review agent score
    convention_adherence: float = 0.0  # [0-1] convention checker score

    session_cost: float = 0.0          # [$] billed cost
    technical_debt_introduced: float = 0.0   # [$] normalized SonarQube delta
    future_cost_impact: float = 0.0    # [$] normalized entropy delta

    score: float = 0.0                 # composite: numerator / denominator
    verdict: str = "unavailable"       # "net_positive" | "net_negative" | "neutral"

    # Provenance
    has_independent_tests: bool = False
    has_review: bool = False
    has_sonar: bool = False
    has_entropy: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "correctness": round(self.correctness, 4),
            "architectural_fit": round(self.architectural_fit, 4),
            "convention_adherence": round(self.convention_adherence, 4),
            "session_cost": round(self.session_cost, 4),
            "technical_debt_introduced": round(self.technical_debt_introduced, 4),
            "future_cost_impact": round(self.future_cost_impact, 4),
            "score": round(self.score, 4),
            "verdict": self.verdict,
            "provenance": {
                "has_independent_tests": self.has_independent_tests,
                "has_review": self.has_review,
                "has_sonar": self.has_sonar,
                "has_entropy": self.has_entropy,
            },
        }


# ── DVS Calculation ────────────────────────────────────────────

def compute_dvs(
    correctness: float,
    architectural_fit: float,
    convention_adherence: float,
    session_cost: float,
    *,
    commit_analysis: CommitAnalysis | None = None,
    commit_review: CommitReview | None = None,
    entropy_delta_value: float = 0.0,
) -> DurableValueScore:
    """Compute Durable Value Score from all available layers.

    Args:
        correctness: Test pass rate [0-1].
        architectural_fit: Review agent score [0-1].
        convention_adherence: Convention checker score [0-1].
        session_cost: Billed cost in USD.
        commit_analysis: Per-commit analysis with SonarQube deltas.
        commit_review: Agent review with structured scores.
        entropy_delta_value: Composite entropy delta (ΔH).

    Returns:
        DurableValueScore with verdict.
    """
    dvs = DurableValueScore(
        correctness=correctness,
        architectural_fit=architectural_fit,
        convention_adherence=convention_adherence,
        session_cost=session_cost,
    )

    # Architectural fit from review agent if available
    if commit_review:
        dvs.architectural_fit = commit_review.architectural_fit
        dvs.convention_adherence = commit_review.convention_adherence
        dvs.has_review = True

    # Technical debt from SonarQube delta
    if commit_analysis and commit_analysis.sonar_available:
        dvs.technical_debt_introduced = _sonar_delta_to_cost(commit_analysis)
        dvs.has_sonar = True

    # Future cost impact from entropy delta
    if entropy_delta_value > 0:
        dvs.future_cost_impact = entropy_delta_value * ENTROPY_COST_PER_001 * 100
        dvs.has_entropy = True

    # Compute score
    numerator = (
        max(dvs.correctness, 0.01)
        * max(dvs.architectural_fit, 0.01)
        * max(dvs.convention_adherence, 0.01)
    )
    denominator = max(
        dvs.session_cost + dvs.technical_debt_introduced + dvs.future_cost_impact,
        0.000001,
    )
    dvs.score = numerator / denominator

    # Verdict
    if dvs.score > 1.0:
        dvs.verdict = "net_positive"
    elif dvs.score >= 0.9:
        dvs.verdict = "neutral"
    else:
        dvs.verdict = "net_negative"

    return dvs


def compute_story_dvs(
    session_costs: list[float],
    correctness_values: list[float],
    arch_fit_values: list[float],
    convention_values: list[float],
    *,
    total_sonar_cost: float = 0.0,
    total_entropy_cost: float = 0.0,
) -> DurableValueScore:
    """Compute DVS for an entire multi-session story.

    Averages quality metrics across sessions and sums costs.
    """
    n = len(session_costs)
    if n == 0:
        return DurableValueScore()

    avg_correctness = sum(correctness_values) / n
    avg_arch_fit = sum(arch_fit_values) / n
    avg_convention = sum(convention_values) / n
    total_cost = sum(session_costs)

    return compute_dvs(
        correctness=avg_correctness,
        architectural_fit=avg_arch_fit,
        convention_adherence=avg_convention,
        session_cost=total_cost,
        entropy_delta_value=total_entropy_cost / (ENTROPY_COST_PER_001 * 100) if ENTROPY_COST_PER_001 > 0 else 0,
    )


# ── Helpers ─────────────────────────────────────────────────────

def _sonar_delta_to_cost(analysis: CommitAnalysis) -> float:
    """Normalize SonarQube deltas to dollar cost estimates."""
    cost = 0.0
    if analysis.sonar_bugs_delta > 0:
        cost += analysis.sonar_bugs_delta * DEBT_COST_PER_BUG
    if analysis.sonar_smells_delta > 0:
        cost += analysis.sonar_smells_delta * DEBT_COST_PER_SMELL
    if analysis.sonar_complexity_delta > 0:
        cost += analysis.sonar_complexity_delta * DEBT_COST_PER_COMPLEXITY
    return cost


def dvs_verdict_to_emoji(verdict: str) -> str:
    """Human-readable verdict display."""
    return {
        "net_positive": "\u2191 better",
        "net_negative": "\u2193 worse",
        "neutral": "\u2194 neutral",
        "unavailable": "? unknown",
    }.get(verdict, verdict)
