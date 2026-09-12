"""Tests for the P5 ``run_value`` projection (step 6, d3 §5 P5).

Pins the preregistered formula orientation — ``cost_per_accepted = total_cost /
accepted_outcomes``, NOT the inverted ``accepted / cost`` — plus the observed-only discipline:
a zero denominator and an unmeasured cost are named unknowns, and BVI stays a declared
modeled scenario with null inputs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from agentic_dynamics.control.projections.run_value import (  # noqa: E402
    FORMULA,
    SCHEMA,
    build_run_value,
    load_attempt_value_rows,
)

_NOW = "2026-09-12T00:00:00+00:00"


def test_cost_per_accepted_is_cost_over_accepted_not_inverted():
    rows = [
        {"run": "r1", "arm": "a", "accepted": True, "cost_usd": 10.0},
        {"run": "r1", "arm": "a", "accepted": True, "cost_usd": 20.0},
        {"run": "r1", "arm": "a", "accepted": False, "cost_usd": 30.0},
    ]
    payload = build_run_value(rows, now=_NOW)
    assert payload["schema"] == SCHEMA
    assert payload["formula"] == FORMULA
    assert payload["observed_only"] is True
    block = payload["rows"][0]
    assert block["total_cost_usd"] == 60.0
    assert block["accepted_outcomes"] == 2
    # 60 / 2 = 30; the inverted reading (2 / 60 ≈ 0.0333) must not appear anywhere.
    assert block["cost_per_accepted"] == 30.0
    assert block["cost_per_accepted"] != round(2 / 60, 6)


def test_zero_accepted_outcomes_is_unknown_with_named_reason():
    rows = [{"run": "r1", "arm": "a", "accepted": False, "cost_usd": 5.0}]
    block = build_run_value(rows, now=_NOW)["rows"][0]
    assert block["cost_per_accepted"] is None
    assert block["cost_per_accepted_reason"] == "no_accepted_outcomes"
    assert block["total_cost_usd"] == 5.0  # the observed cost is still reported


def test_unmeasured_cost_and_zero_cost_are_unknown_not_free():
    rows = [
        {"run": "r1", "arm": "a", "accepted": True, "cost_usd": None},
        {"run": "r2", "arm": "a", "accepted": True, "cost_usd": 0.0},  # 0.0 is not captured
    ]
    by_run = {block["run"]: block for block in build_run_value(rows, now=_NOW)["rows"]}
    for run in ("r1", "r2"):
        assert by_run[run]["cost_per_accepted"] is None
        assert by_run[run]["cost_per_accepted_reason"] == "unmeasured_cost"
        assert by_run[run]["total_cost_usd"] is None
        assert by_run[run]["cost_captured_records"] == 0


def test_bvi_is_declared_modeled_never_computed():
    payload = build_run_value([], now=_NOW)
    bvi = payload["bvi"]
    assert bvi["state"] == "modeled"
    assert bvi["class"] == "[P]"
    assert bvi["value"] is None
    assert bvi["inputs"] == {"H": None, "W": None}
    assert "no owners" in bvi["reason"]


def test_loader_maps_attempt_ledger_statuses_without_inventing_outcomes(tmp_path):
    payload = {
        "spec_id": "grit@1",
        "cells": [
            {"policy_arm": "retry", "status": "accepted", "realized_cost": 2.0, "attempts": [{}]},
            {"status": "failed", "realized_cost": 1.0, "attempts": [{}]},
            {"status": "running", "realized_cost": None, "attempts": [{}]},
        ],
    }
    path = tmp_path / "grid_ledger.json"
    path.write_text(json.dumps(payload))
    (tmp_path / "other.json").write_text(json.dumps({"not": "a ledger"}))

    rows, paths = load_attempt_value_rows(tmp_path)
    assert len(paths) == 1
    assert [(r["accepted"], r["cost_usd"]) for r in rows] == [
        (True, 2.0),
        (False, 1.0),
        (None, None),  # an unsettled status is unknown, never False
    ]
    assert {r["run"] for r in rows} == {"grit@1"}
    assert load_attempt_value_rows(tmp_path / "nope") == ([], [])


def test_two_runs_of_one_spec_are_not_pooled(tmp_path):
    """Wave C1 — the P5 group identity prefers the ledger's OWN run id (stamped since the
    run-identity work): a parent run and its resumed child (same spec_id) no longer pool
    into one population and report a single mixed cost/accepted (the review's P5 repro
    class). A legacy payload without a run id keeps the old spec_id grouping (pinned above)."""
    base = {"spec_id": "grit@1"}
    (tmp_path / "a.json").write_text(json.dumps({
        **base, "run_id": "run-parent",
        "cells": [
            {"policy_arm": "retry", "status": "accepted", "realized_cost": 2.0, "attempts": [{}]},
        ],
    }))
    (tmp_path / "b.json").write_text(json.dumps({
        **base, "run_id": "run-child",
        "cells": [
            {"policy_arm": "retry", "status": "failed", "realized_cost": 4.0, "attempts": [{}]},
        ],
    }))

    rows, _ = load_attempt_value_rows(tmp_path)
    assert {r["run"] for r in rows} == {"run-parent", "run-child"}

    payload = build_run_value(rows)
    assert [
        (block["run"], block["accepted_outcomes"], block["total_cost_usd"])
        for block in payload["rows"]
    ] == [("run-parent", 1, 2.0), ("run-child", 0, 4.0)]
