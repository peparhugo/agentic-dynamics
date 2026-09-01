"""Null-not-zero guard for the measurement-plane ratio sweep (cap_stabilization_release p1).

The finding-economics closure removed ``/ max(cost, tiny)`` ratio floors from the published
corpus and the strategy report (``strategy.py``'s ``exploration_premium``/``thermal_efficiency``
are ``float | None = None`` — "None = denominator uncaptured"). This module locks in the sweep
for the REMAINING ``= 0.0``-when-denominator-missing sites in the measurement plane: a ratio
whose denominator is uncaptured (zero tokens, zero cost, zero energy, zero baseline
correctness, zero constraint count) must be ``None`` — never a fabricated ``0.0`` nor a
``max(denom, tiny)`` superspike — and ``to_dict`` must round-trip that as JSON ``null``.
"""

from agentic_dynamics.measurement import basin, constraint_detection, efficiency, recovery_cost
from agentic_dynamics.measurement.solution import SolutionMetrics


import pytest
pytestmark = pytest.mark.fast

def _solution(correctness=0.9, composite=0.8, loc=120):
    return SolutionMetrics(
        correctness_score=correctness, composite_score=composite, lines_of_code=loc
    )


# ── efficiency ─────────────────────────────────────────────────────────────


def test_efficiency_ratios_null_when_denominator_uncaptured():
    """A zero-token/zero-cost/zero-energy run leaves the solution ratios None, not 0.0."""
    m = efficiency.compute_efficiency(
        prompt_tokens=0, completion_tokens=0, reasoning_tokens=0, total_tokens=0,
        provider="deepseek", model="deepseek-v4-flash", solution=_solution(),
    )
    assert m.solution_density is None
    assert m.correctness_per_dollar is None
    assert m.quality_per_joule is None
    assert m.efficiency_score is None
    d = m.to_dict()
    assert d["solution_density"] is None
    assert d["correctness_per_dollar"] is None
    assert d["quality_per_joule"] is None
    assert d["efficiency_score"] is None


def test_efficiency_ratios_computed_when_denominator_captured():
    m = efficiency.compute_efficiency(
        prompt_tokens=1000, completion_tokens=500, reasoning_tokens=200, total_tokens=1700,
        provider="deepseek", model="deepseek-v4-flash", solution=_solution(),
    )
    assert m.total_cost_usd > 0 and m.total_energy_j > 0 and m.total_tokens > 0
    assert m.solution_density is not None
    assert m.correctness_per_dollar is not None
    assert m.quality_per_joule is not None
    assert m.efficiency_score is not None


# ── basin ──────────────────────────────────────────────────────────────────


def test_basin_quality_ratios_null_when_denominator_uncaptured():
    """Zero baseline correctness (or $0 cost / 0J energy) leaves the ratios None."""
    zero_baseline = basin.measure_basin_escape(
        "a", "b", 0.0, 0.9, 0, 1, 10, 20, cost_usd=0.02
    )
    assert zero_baseline.quality_per_dollar is None
    assert zero_baseline.quality_per_joule is None
    assert zero_baseline.to_dict()["quality_per_dollar"] is None

    zero_cost = basin.measure_basin_escape(
        "a", "b", 0.5, 0.9, 0, 1, 10, 20, cost_usd=0.0,
        prompt_tokens=0, completion_tokens=0, reasoning_tokens=0,
    )
    assert zero_cost.quality_per_dollar is None
    assert zero_cost.quality_per_joule is None


def test_basin_quality_ratios_computed_when_denominator_captured():
    b = basin.measure_basin_escape(
        "a", "b", 0.5, 0.9, 0, 1, 10, 20, cost_usd=0.02
    )
    assert b.quality_per_dollar is not None


# ── recovery_cost ──────────────────────────────────────────────────────────


def test_recovery_ratios_null_when_denominator_uncaptured():
    """A zero-token/$0 perturbed run leaves the recovery ratios None, not 0.0."""
    rc = recovery_cost.compute_recovery_cost(
        baseline_tokens=10, baseline_cost_usd=0.01, perturbed_tokens=0, perturbed_cost_usd=0.0
    )
    assert rc.recovery_token_ratio is None
    assert rc.recovery_cost_ratio is None
    d = rc.to_dict()
    assert d["recovery_token_ratio"] is None
    assert d["recovery_cost_ratio"] is None


def test_recovery_ratios_computed_when_denominator_captured():
    rc = recovery_cost.compute_recovery_cost(
        baseline_tokens=10, baseline_cost_usd=0.01, perturbed_tokens=20, perturbed_cost_usd=0.03
    )
    assert rc.recovery_token_ratio == 0.5
    assert abs(rc.recovery_cost_ratio - 0.02 / 0.03) < 1e-9


# ── constraint_detection ───────────────────────────────────────────────────


def test_detection_rate_null_when_no_constraints():
    """With zero constraints there is nothing to detect — the rate is None, not 0.0."""
    report = constraint_detection.detect_constraints("hello world", [])
    assert report.constraints_total == 0
    assert report.detection_rate is None
    assert report.to_dict()["detection_rate"] is None


def test_detection_rate_computed_when_constraints_present():
    report = constraint_detection.detect_constraints("I used a rate limiter", ["rate limiting"])
    assert report.constraints_total == 1
    assert report.detection_rate == 1.0
