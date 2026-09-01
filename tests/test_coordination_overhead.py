"""Unit tests for the β coordination-tax instrument (the overhead arithmetic).

Design: ``docs/designs/proposed/beta_snowball_measurement_design.md`` §2.
"""

import pytest
pytestmark = pytest.mark.fast

from agentic_dynamics.measurement.coordination_overhead import (
    CELL_PHASE_KEYS,
    CoordinationComponents,
    coordination_overhead,
    split_breakdown,
    wrapper_share,
)


class TestCoordinationOverhead:
    def test_basic_arithmetic(self):
        # (wrapper + merge + chain + review) / cell
        assert coordination_overhead(1.0, 0.5) == 0.5
        assert coordination_overhead(1.0, 0.5, merge_cost=0.25, chain_cost=0.25) == 1.0

    def test_wrapper_only_numerator(self):
        assert coordination_overhead(2.0, 1.0) == 0.5

    def test_zero_cell_is_none(self):
        # Never divide by zero — a cell denominator that cannot be measured is unmeasured.
        assert coordination_overhead(0.0, 0.5) is None

    def test_missing_terms_is_none(self):
        assert coordination_overhead(None, 0.5) is None
        assert coordination_overhead(1.0, None) is None


class TestWrapperShare:
    def test_2b_prior_arithmetic(self):
        # The 2b prior: 63% = $0.17 of $0.27 (wrapper of (wrapper + cell)).
        assert wrapper_share(0.10, 0.17) == 0.6296296296296297

    def test_zero_total_is_none(self):
        assert wrapper_share(0.0, 0.0) is None
        assert wrapper_share(None, 0.17) is None


class TestSplitBreakdown:
    def test_cell_vs_wrapper(self):
        # implement + rework are cell work; test + verify are wrapper.
        breakdown = {"implement": 0.0036, "test": 0.0, "verify": 0.0052, "rework": 0.001}
        cell, wrapper = split_breakdown(breakdown)
        assert cell == 0.0046
        assert wrapper == 0.0052

    def test_none_phase_contributes_zero(self):
        # The phase-ledger contract writes null for unrun phases — never a fabricated cost.
        cell, wrapper = split_breakdown({"implement": 0.01, "verify": None, "rework": None})
        assert cell == 0.01
        assert wrapper == 0.0

    def test_empty_breakdown(self):
        cell, wrapper = split_breakdown({})
        assert cell == 0.0
        assert wrapper == 0.0

    def test_cell_phase_keys_pinned(self):
        # The cell/wrapper assignment is the instrument's declared [P] policy — pin it.
        assert "implement" in CELL_PHASE_KEYS
        assert "rework" in CELL_PHASE_KEYS
        assert "verify" not in CELL_PHASE_KEYS
        assert "test" not in CELL_PHASE_KEYS


class TestCoordinationComponents:
    def test_to_dict_round_trip(self):
        c = CoordinationComponents(
            campaign="cap_2b",
            cell_cost=0.10,
            wrapper_cost=0.17,
            merge_events=1,
            chain_events=3,
            review_rounds=2,
            wrapper_source="experiments/results/cap_2b/p1_phase_ledger.json",
        )
        d = c.to_dict()
        assert d["campaign"] == "cap_2b"
        assert d["wrapper_cost"] == 0.17
        assert d["merge_events"] == 1
        assert "wrapper_source" in d
