"""Strategy classification — what kind of game did the model play?

Classifies each experimental run into one of four strategy types
based on the interaction of reasoning dynamics, solution quality,
and resource efficiency.

This is the game-theoretic analysis layer: every experiment is a
controlled game. The model's strategy reveals its learned policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from agentic_dynamics.measurement.basin import BasinMetrics
from agentic_dynamics.measurement.efficiency import EfficiencyMetrics
from agentic_dynamics.measurement.solution import SolutionMetrics


class StrategyType(str, Enum):
    """What strategy did the model employ?

    CONSERVATIVE:     Low escape, high correctness, moderate cost.
                      Model re-derived constraints. Stable but boring.
                      Good for production reliability.

    EXPLORATORY:      High escape, moderate-high novelty, varied cost.
                      Model found genuinely new approaches. The goal.
                      Good for research and innovation.

    WASTEFUL:         High escape, low correctness, high cost.
                      Model wandered without converging. Token explosion.
                      Bad for everything — the attractor basin is too weak.

    EFFICIENT:        Low escape, high correctness, low cost.
                      Model solved correctly with minimal resources.
                      The thermodynamic ideal. Best for deployment.
    """

    CONSERVATIVE = "conservative"
    EXPLORATORY = "exploratory"
    WASTEFUL = "wasteful"
    EFFICIENT = "efficient"


@dataclass
class StrategyReport:
    """Complete strategic analysis of one experimental run.

    Combines reasoning dynamics (how it played), solution quality
    (what it built), and resource efficiency (what it cost) into a
    single strategic classification.
    """

    strategy: StrategyType = StrategyType.CONSERVATIVE

    # Dimensions
    reasoning: BasinMetrics | None = None
    solution: SolutionMetrics | None = None
    efficiency: EfficiencyMetrics | None = None

    # Scores
    strategy_score: float = 0.0  # composite strategic quality
    exploration_premium: float = 0.0  # bonus for novel correct solutions
    thermal_efficiency: float = 0.0  # correctness per joule

    # Verdict
    verdict: str = ""
    recommendation: str = ""

    # Metadata
    operator: str = ""
    perturbation_class: str = ""
    model: str = ""
    run_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy.value,
            "strategy_score": round(self.strategy_score, 4),
            "exploration_premium": round(self.exploration_premium, 4),
            "thermal_efficiency": round(self.thermal_efficiency, 4),
            "verdict": self.verdict,
            "recommendation": self.recommendation,
            "operator": self.operator,
            "perturbation_class": self.perturbation_class,
            "model": self.model,
            "run_id": self.run_id,
            "reasoning": self.reasoning.to_dict() if self.reasoning else None,
            "solution": self.solution.to_dict() if self.solution else None,
            "efficiency": self.efficiency.to_dict() if self.efficiency else None,
        }


def classify_strategy(
    reasoning: BasinMetrics,
    solution: SolutionMetrics,
    efficiency: EfficiencyMetrics,
    perturbation_class: str = "",
) -> StrategyReport:
    """Classify the model's strategy from multi-dimensional metrics.

    The classification logic (behavioral only — cost is reported, not classified):

    1. If correctness is low AND reasoning is heavy → WASTEFUL
    2. If correctness is high AND reasoning is lean → EFFICIENT
    3. If correctness is high AND escape is high AND novelty is high → EXPLORATORY
    4. Otherwise → CONSERVATIVE (reliably correct, standard approach)

    EXPLORATORY receives an exploration_premium: the model found a
    genuinely novel approach that works. This is the ideal outcome
    for objective-mutation and process perturbations.

    EFFICIENT receives high thermal_efficiency: maximum correctness
    per joule. This is the ideal outcome for specification corruption.
    """
    r = StrategyReport()
    r.reasoning = reasoning
    r.solution = solution
    r.efficiency = efficiency
    r.operator = reasoning.perturbation_operator
    r.perturbation_class = perturbation_class
    r.model = reasoning.model
    r.run_id = reasoning.run_id

    escape = reasoning.escape_score
    correctness = solution.correctness_score
    novelty = solution.novelty_score
    quality = solution.composite_score
    cost = efficiency.total_cost_usd
    thinking_ratio = efficiency.thinking_ratio
    energy = efficiency.total_energy_j

    # Detection signals — behavioral only. Cost is a provider-price artifact and
    # is reported in the verdict text, but never used to classify strategy, so
    # the archetype is invariant under uniform price rescaling and unbiased
    # across providers. (P0-4: absolute USD thresholds had biased Claude as
    # "expensive" and DeepSeek as "efficient" purely by price, not behavior.)
    is_correct = correctness >= 0.7
    is_novel = novelty >= 0.4
    is_escaped = escape >= 0.5
    is_reasoning_lean = thinking_ratio <= 0.3
    is_wasteful = correctness <= 0.3 and thinking_ratio >= 0.4

    # Classification
    if is_wasteful:
        r.strategy = StrategyType.WASTEFUL
        r.verdict = (
            f"WASTEFUL — model burned {efficiency.total_tokens:,} tokens "
            f"(${cost:.4f}, ~{energy:.0f}J, {thinking_ratio:.0%} thinking) "
            f"achieving only {correctness:.0%} correctness. "
            f"High reasoning overhead without convergence."
        )
        r.recommendation = "Reduce perturbation strength or avoid this operator class."
    elif is_correct and is_escaped and is_novel:
        r.strategy = StrategyType.EXPLORATORY
        r.verdict = (
            f"EXPLORATORY — model escaped attractor (escape={escape:.2f}) "
            f"and found a novel correct solution (novelty={novelty:.2f}, "
            f"correctness={correctness:.0%}). "
            f"Cost: ${cost:.4f}, ~{energy:.0f}J."
        )
        r.recommendation = "Promote this operator. The perturbation succeeded."
        # The exploration premium is cost-denominated: it is only meaningful when a cost
        # was captured (> 0). The old ``/ max(cost, 0.0001)`` floor turned an uncaptured
        # $0 cost into an enormous premium — the same ratio-superspike the finding-economics
        # closure removed elsewhere. An uncaptured cost leaves the premium at its 0.0 default.
        if cost > 0:
            r.exploration_premium = novelty * correctness / cost
    elif is_correct and is_reasoning_lean:
        r.strategy = StrategyType.EFFICIENT
        r.verdict = (
            f"EFFICIENT — model solved correctly ({correctness:.0%}) "
            f"with minimal resources (${cost:.4f}, ~{energy:.0f}J, "
            f"{thinking_ratio:.0%} thinking). Thermodynamically optimal."
        )
        r.recommendation = "This operator+model combination is production-ready."
        # Thermal efficiency is energy-denominated: only meaningful when energy was
        # captured (> 0). The old ``/ max(energy, 0.01)`` floor inflated it for an
        # unmetered 0J run. An uncaptured energy leaves it at its 0.0 default.
        if energy > 0:
            r.thermal_efficiency = correctness / energy
    else:
        r.strategy = StrategyType.CONSERVATIVE
        r.verdict = (
            f"CONSERVATIVE — model maintained sound reasoning "
            f"(correctness={correctness:.0%}, quality={quality:.2f}) "
            f"with moderate resource use (${cost:.4f}, ~{energy:.0f}J). "
            f"Model absorbed the perturbation without divergence."
        )
        r.recommendation = "Reliable but not novel. Good for production, not for exploration."

    # Composite strategic score — behavioral dimensions only. The absolute-USD
    # cost penalty (min(cost*100, 1.0), effectively capping at $0.01) was
    # removed: it biased the score against expensive providers. Cost is reported
    # in the verdict, not scored here.
    r.strategy_score = (
        0.35 * correctness
        + 0.15 * novelty
        + 0.30 * (1.0 - min(thinking_ratio, 1.0))  # penalize excessive thinking
        + 0.20 * (1.0 if is_correct else 0.0)
    )

    return r
