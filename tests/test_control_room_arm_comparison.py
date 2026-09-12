"""Tests for the P6 ``arm_comparison`` projection (step 6, d3 §5 P6).

Pins: the room serves the SAME ``compare_arms`` derivation (comparable-coverage rule
included); a single-arm or unknown-spec request is a NAMED state, never an error; the loader
carries an absent cost as absent (so an unmeasured arm cannot look free).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from agentic_dynamics.control.projections.arm_comparison import (  # noqa: E402
    DEFAULT_LOSS,
    SCHEMA,
    build_arm_comparison,
    load_phase_outcomes,
)
from agentic_dynamics.experiment.compile_experiment import compare_arms  # noqa: E402

_NOW = "2026-09-12T00:00:00+00:00"


def _rows():
    return [
        {"spec_name": "s", "model": "m/one", "cost": 0.1, "correctness": 0.8},
        {"spec_name": "s", "model": "m/two", "cost": 0.5, "correctness": 0.9},
        {"spec_name": "other", "model": "m/one", "cost": 0.2, "correctness": 0.7},
    ]


def test_serves_the_same_compare_arms_derivation():
    rows = _rows()
    payload = build_arm_comparison(rows, spec="s", now=_NOW)
    assert payload["schema"] == SCHEMA
    assert payload["state"] == "ranked"
    assert payload["n_outcomes"] == 2
    expected = compare_arms(
        [r for r in rows if r["spec_name"] == "s"], arm_factor="model", loss=DEFAULT_LOSS
    )
    assert payload["comparison"] == expected
    # the coverage rule rides through: every arm carries its eligible sample counts.
    assert payload["comparison"]["arms"]["m/one"]["coverage"]["cost"] == {
        "n": 1,
        "of": 1,
        "rate": 1.0,
    }


def test_single_arm_returns_a_named_state_not_an_error():
    payload = build_arm_comparison([{"spec_name": "s", "model": "m/one", "cost": 0.1, "correctness": 0.8}], spec="s", now=_NOW)
    assert payload["state"] == "single_arm"
    assert "nothing to compare" in payload["state_reason"]
    assert payload["comparison"]["best_arm"] == "m/one"


def test_unknown_spec_returns_a_named_empty_state():
    payload = build_arm_comparison(_rows(), spec="does-not-exist", now=_NOW)
    assert payload["state"] == "empty"
    assert "does-not-exist" in payload["state_reason"]
    assert payload["comparison"]["best_arm"] is None


def test_decision_calibration_summary_is_carried():
    decisions = [
        {"action": "route", "baseline_action": "route", "model": "a", "baseline_model": "a"},
        {"action": "route", "baseline_action": "skip", "model": "a", "baseline_model": "a"},
    ]
    payload = build_arm_comparison(_rows(), spec="s", decisions=decisions, now=_NOW)
    assert payload["decision_calibration"] == {"n_decisions": 2, "decision_regret": 0.5}


def test_loader_keeps_absent_cost_absent(tmp_path):
    spec_dir = tmp_path / "workflows" / "spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "run.json").write_text(
        json.dumps(
            {
                "spec_name": "spec",
                "phases": [
                    {"kind": "agent", "model": "m/one", "status": "ok", "cost_usd": 0.25},
                    {"kind": "agent", "model": "m/two", "status": "failed"},  # no cost_usd key
                    {"kind": "test", "model": "m/one", "status": "ok", "cost_usd": 0.0},
                ],
            }
        )
    )
    rows, n_ledgers = load_phase_outcomes(tmp_path / "workflows")
    assert n_ledgers == 1
    assert rows[0] == {"spec_name": "spec", "model": "m/one", "correctness": 1.0, "cost": 0.25}
    # the absent cost is NOT defaulted to 0.0 — the coverage rule can then see it.
    assert "cost" not in rows[1]
    assert rows[1]["correctness"] == 0.0
    assert load_phase_outcomes(tmp_path / "nope") == ([], 0)
