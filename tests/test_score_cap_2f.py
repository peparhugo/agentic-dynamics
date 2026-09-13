"""Tests for scripts/score_cap_2f.py — the evidence-validity rules (earlier-open items).

Two defects the GPT-Astra review rechecked:

* an INVALID repetition join still counted as an accepted outcome (the cell's
  (class, arm, repetition, variant) did not match the pre-registered table);
* a MISSING cost was coerced to ``0.0``, so a partially-priced arm produced a flag-cost
  number against a fabricated zero.

The corrected semantics mirror ``core.cost_provenance`` (absent = UNKNOWN, never 0.0) and the
P5 ``run_value`` coverage rule (a total/difference over any unknown contributing cost is
``None`` with coverage rendered).
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

score = importlib.import_module("scripts.score_cap_2f")


def _cell(
    cell_id,
    *,
    cls="trivial_clean",
    arm="status_quo",
    rep=1,
    accepted=True,
    cost=1.0,
    variant="clean",
    defect=False,
):
    return {
        "cell_id": cell_id,
        "class": cls,
        "arm": arm,
        "repetition": rep,
        "variant": variant,
        "facts": {},
        "flags": [],
        "proposal": {"action": "continue", "confidence": 0.9},
        "application": {"applied_or_null": None},
        "abstention_decision": {},
        "outcome": {
            "accepted": accepted,
            "test_executed_success": True,
            "tests_passed": 1,
            "tests_total": 1,
            "defect_present_on_final_commit": defect,
            "defect_note": None,
        },
        "cost": {"total_usd": cost} if cost is not None else {},
    }


def _table_row(cell_id, *, cls="trivial_clean", arm="status_quo", rep=1, variant=None):
    return {
        "cell_id": cell_id,
        "class": cls,
        "arm": arm,
        "repetition": rep,
        "variant": variant,
        "slot": 0,
    }


def _rows(cells: dict, table: dict) -> list[dict]:
    joins = score.validate_joins(cells, table)
    return score.per_cell_rows(cells, table, joins)


# ── invalid joins are not accepted evidence ─────────────────────────────────


def test_invalid_repetition_join_never_counts_as_accepted():
    cells = {"c1": _cell("c1", rep=2)}  # the record says repetition 2
    table = {"c1": _table_row("c1", rep=1)}  # the pre-registered cell is repetition 1
    joins = score.validate_joins(cells, table)
    assert joins[0]["valid"] is False

    rows = score.per_cell_rows(cells, table, joins)
    assert rows[0]["join_valid"] is False
    assert rows[0]["accepted"] is False, "an invalid join must not count as accepted"
    assert score.arm_aggregate(rows, "status_quo")["accepted_outcomes"] == 0


def test_valid_join_still_counts_as_accepted():
    cells = {"c1": _cell("c1")}
    table = {"c1": _table_row("c1")}
    rows = _rows(cells, table)
    assert rows[0]["join_valid"] is True
    assert rows[0]["accepted"] is True
    assert score.arm_aggregate(rows, "status_quo")["accepted_outcomes"] == 1


# ── missing cost is unknown, never zero ─────────────────────────────────────


def test_missing_cost_is_unknown_not_zero():
    cells = {
        "c1": _cell("c1", cost=None),
        "c2": _cell("c2", rep=2, accepted=False, cost=2.0),
    }
    table = {"c1": _table_row("c1"), "c2": _table_row("c2", rep=2)}
    rows = _rows(cells, table)
    by_id = {r["cell_id"]: r for r in rows}
    assert by_id["c1"]["cost_usd"] is None
    assert by_id["c1"]["cost_source"] == "unknown"

    agg = score.arm_aggregate(rows, "status_quo")
    assert agg["total_cost_usd"] is None, "a partial arm total must not be 2.0 + 0.0"
    assert agg["total_cost_usd"] != 2.0
    assert agg["cost_captured_records"] == 1
    assert agg["cost_coverage"] == 0.5


def test_recorded_zero_cost_stays_a_real_zero():
    """A recorded 0.0 is a provider reading (mirrors cost_provenance), not an absence."""
    rows = _rows({"c1": _cell("c1", cost=0.0)}, {"c1": _table_row("c1")})
    assert rows[0]["cost_usd"] == 0.0
    assert rows[0]["cost_source"] == "metered"


# ── flag-cost ceiling refuses an unknown ────────────────────────────────────


def test_flag_cost_refuses_a_partially_priced_arm():
    cells = {
        "ab1": _cell("ab1", arm="abstention", cost=1.0),
        "sq1": _cell("sq1", arm="status_quo", cost=None, accepted=False),
    }
    table = {
        "ab1": _table_row("ab1", arm="abstention"),
        "sq1": _table_row("sq1", arm="status_quo"),
    }
    rows = _rows(cells, table)
    flag = score.flag_cost_table(rows)
    assert flag["abstention_total_cost_usd"] == 1.0
    assert flag["status_quo_total_cost_usd"] is None
    assert flag["flag_cost_usd"] is None, "never computed against a fabricated zero"
    assert flag["flag_cost_reason"] == "unmeasured_cost"
    assert flag["cost_unknown_cells"] == ["sq1"]
    assert flag["ceiling_holds"] is False

    rule = score.decision_rule(rows, score.capture_table(rows), flag)
    condition_b = rule["condition_b_flag_cost_ceiling"]
    assert condition_b["holds"] is False
    assert condition_b["flag_cost_usd"] is None
    assert condition_b["flag_cost_reason"] == "unmeasured_cost"
    assert rule["arms"]["status_quo"]["cost_usd"] is None


def test_complete_costs_compute_the_flag_cost():
    cells = {
        "ab1": _cell("ab1", arm="abstention", cost=1.5),
        "sq1": _cell("sq1", arm="status_quo", cost=0.5),
    }
    table = {
        "ab1": _table_row("ab1", arm="abstention"),
        "sq1": _table_row("sq1", arm="status_quo"),
    }
    rows = _rows(cells, table)
    flag = score.flag_cost_table(rows)
    assert flag["abstention_total_cost_usd"] == 1.5
    assert flag["status_quo_total_cost_usd"] == 0.5
    assert flag["flag_cost_usd"] == 1.0
    assert flag["flag_cost_reason"] is None
    assert flag["abstention_cost_coverage"] == 1.0
    # pre-registered: no captured escape -> vacuous -> the ceiling cannot hold
    assert flag["vacuous"] is True
    assert flag["ceiling_holds"] is False


def test_complete_cost_of_empty_population_is_zero_not_unknown():
    assert score.complete_cost([]) == (0.0, 0, 0)
