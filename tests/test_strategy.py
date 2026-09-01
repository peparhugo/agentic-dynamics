"""Tests for strategy classification — P0-4 price-rescaling invariance.

The strategy archetype must reflect *behavior*, not provider price. These tests
lock in that classification is invariant under a uniform price rescale and that
no model is "expensive" or "efficient" purely by its price tier.
"""

from agentic_dynamics.measurement.basin import BasinMetrics
from agentic_dynamics.measurement.efficiency import EfficiencyMetrics
from agentic_dynamics.measurement.solution import SolutionMetrics
from agentic_dynamics.measurement.strategy import StrategyType, classify_strategy


import pytest
pytestmark = pytest.mark.fast

def _classify(correctness, novelty, escape, thinking_ratio, cost) -> StrategyType:
    basin = BasinMetrics(
        escape_score=escape,
        novelty_score=novelty,
        model="test/model",
        perturbation_operator="inject_false_premise",
        run_id="r1",
    )
    solution = SolutionMetrics(
        correctness_score=correctness,
        novelty_score=novelty,
        composite_score=correctness,
    )
    efficiency = EfficiencyMetrics(
        total_cost_usd=cost,
        thinking_ratio=thinking_ratio,
        total_energy_j=1000.0,
        total_tokens=1000,
    )
    return classify_strategy(basin, solution, efficiency, "specification_corruption").strategy


# (correctness, novelty, escape, thinking_ratio) → expected archetype
CASES = [
    (0.9, 0.6, 0.7, 0.2, StrategyType.EXPLORATORY),  # correct + novel + escaped
    (0.9, 0.2, 0.2, 0.1, StrategyType.EFFICIENT),  # correct + reasoning-lean
    (0.2, 0.1, 0.1, 0.5, StrategyType.WASTEFUL),  # wrong + reasoning-heavy
    (0.9, 0.2, 0.2, 0.5, StrategyType.CONSERVATIVE),  # correct, moderate reasoning
]


def test_classification_matches_expected_archetype():
    for correctness, novelty, escape, thinking, expected in CASES:
        assert _classify(correctness, novelty, escape, thinking, cost=0.005) == expected


def test_classification_invariant_under_price_rescale():
    for correctness, novelty, escape, thinking, _ in CASES:
        cheap = _classify(correctness, novelty, escape, thinking, cost=0.0001)
        pricey = _classify(correctness, novelty, escape, thinking, cost=10.0)
        assert cheap == pricey, (
            f"classification changed under price rescale ({cheap} vs {pricey}) "
            f"for correctness={correctness} thinking={thinking}"
        )


def test_cheap_model_can_be_wasteful_and_expensive_model_can_be_efficient():
    # A cheap run with heavy, failed reasoning must still classify WASTEFUL.
    assert _classify(0.2, 0.1, 0.1, 0.8, cost=0.0001) == StrategyType.WASTEFUL
    # An expensive run with lean, correct reasoning must still classify EFFICIENT.
    assert _classify(0.9, 0.2, 0.2, 0.1, cost=100.0) == StrategyType.EFFICIENT


def _report(correctness, novelty, escape, thinking_ratio, cost, energy=1000.0):
    """Build a full StrategyReport (not just the archetype) so the ratios can be asserted."""
    basin = BasinMetrics(
        escape_score=escape,
        novelty_score=novelty,
        model="test/model",
        perturbation_operator="inject_false_premise",
        run_id="r1",
    )
    solution = SolutionMetrics(
        correctness_score=correctness,
        novelty_score=novelty,
        composite_score=correctness,
    )
    efficiency = EfficiencyMetrics(
        total_cost_usd=cost,
        thinking_ratio=thinking_ratio,
        total_energy_j=energy,
        total_tokens=1000,
    )
    return classify_strategy(basin, solution, efficiency, "specification_corruption")


def test_economic_ratios_null_when_denominator_uncaptured():
    """Cost/energy-denominated ratios are null (unavailable), not zero, when the denominator is uncaptured.

    The finding-economics closure removed the ``/ max(cost, 0.0001)`` ratio floor from the
    published corpus; the strategy report's exploration_premium (cost-denominated) and
    thermal_efficiency (energy-denominated) carried the same floor. An uncaptured cost/energy
    must leave them None — a ratio unavailable is not a ratio measured as zero.
    """
    # Exploration premium is cost-denominated.
    uncaptured_cost = _report(0.9, 0.6, 0.7, 0.2, cost=0.0)
    captured_cost = _report(0.9, 0.6, 0.7, 0.2, cost=0.005)
    assert uncaptured_cost.exploration_premium is None
    assert captured_cost.exploration_premium > 0.0

    # Thermal efficiency is energy-denominated.
    uncaptured_energy = _report(0.9, 0.2, 0.2, 0.1, cost=0.005, energy=0.0)
    captured_energy = _report(0.9, 0.2, 0.2, 0.1, cost=0.005, energy=1000.0)
    assert uncaptured_energy.thermal_efficiency is None
    assert captured_energy.thermal_efficiency > 0.0
