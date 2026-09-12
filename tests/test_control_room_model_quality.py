"""Tests for the P3 ``model_quality`` projection (step 6, d3 §5 P3).

The d3 §9 invariants are pinned here: the ONE Grit definition (shared with the lab, not
re-implemented), coverage before every ratio, unknown ≠ zero (named reasons), and an
evidence class on every block. Deterministic fixtures; no clock, no sockets.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from agentic_dynamics.control.projections.model_quality import (  # noqa: E402
    SCHEMA,
    build_model_quality,
    load_workflow_attempts,
)
from agentic_dynamics.reporting.grit_metric import (  # noqa: E402
    METRIC_DEFINITION,
    rate_row,
)

_NOW = "2026-09-12T00:00:00+00:00"


def _finding(model, strength, verdict, answer=None, explanation=None):
    row = {
        "model": model,
        "perturbation_strength": strength,
        "operator": "op",
        "perturbation_class": "cls",
        "test_executed_success": verdict,
    }
    if answer is not None:
        row["answer_tokens"] = answer
        row["explanation_tokens"] = explanation
    return row


def _strategy_findings():
    # 6 cells for m/one at s=0.5 with 3 successes; 2 at s=0.0 with 2 successes.
    cells = [True, True, True, False, False, False]
    findings = [_finding("m/one", 0.5, ok) for ok in cells]
    findings += [_finding("m/one", 0.0, True), _finding("m/one", 0.0, True)]
    return findings


def test_grit_reuses_the_shared_metric_definition():
    """Grit matches the shared implementation (the lab's definition) for a fixed fixture."""
    payload = build_model_quality(_strategy_findings(), [], [], now=_NOW)
    block = payload["models"][0]
    assert payload["schema"] == SCHEMA
    assert block["grit"]["definition"] == METRIC_DEFINITION
    assert block["grit"]["evidence_class"] == "[M]"
    # the s=0.5 row is exactly what the shared rate_row/wilson implementation produces.
    assert block["grit"]["by_strength"][1] == rate_row("strength", 0.5, 3, 6)
    assert block["grit"]["overall"] == rate_row("model", "one", 5, 8)


def test_population_coverage_is_reported_before_any_ratio():
    """Excluded cells are tallied with their canonical reason; eligible counts precede ratios."""
    findings = _strategy_findings()
    broken = _finding("m/one", 0.5, True)
    del broken["test_executed_success"]  # missing required field
    payload = build_model_quality(findings, [broken], [], now=_NOW)
    population = payload["population"]
    assert population["resolved_cells"] == 9
    assert population["eligible_cells"] == 8
    assert population["excluded_cells"] == 1
    assert population["exclusions"] == {"missing_required_field": 1}


def test_first_pass_uses_attempt_rows_with_coverage_first():
    attempts = [
        {"model": "m/one", "attempt_number": 1, "accepted": True},
        {"model": "m/one", "attempt_number": 1, "accepted": False},
        {"model": "m/one", "attempt_number": 2, "accepted": True},
        {"model": "m/one", "attempt_number": None, "accepted": True},  # ineligible
        {"model": "m/one", "attempt_number": 1, "accepted": "yes"},  # ineligible (not a bool)
    ]
    payload = build_model_quality([], [], attempts, now=_NOW)
    block = payload["models"][0]["first_pass"]
    assert block["n_total"] == 5
    assert block["n_eligible"] == 3
    assert block["coverage"] == 0.6
    assert block["first_attempts"] == 2
    assert block["first_pass_rate"] == 0.5
    assert block["accepted_rate"] == 0.6667
    # 2 first attempts is below the shared small-sample threshold — flagged, not hidden.
    assert block["insufficient_support"] is True


def test_first_pass_zero_denominator_is_unknown_not_zero():
    attempts = [{"model": "m/one", "attempt_number": 2, "accepted": True}]
    block = build_model_quality([], [], attempts, now=_NOW)["models"][0]["first_pass"]
    assert block["first_pass_rate"] is None
    assert "zero denominator" in block["reason"] or "no eligible first attempts" in block["reason"]


def test_narration_ratio_and_null_stays_unknown():
    findings = [
        _finding("m/one", 0.5, True, answer=100, explanation=100),
        _finding("m/one", 0.5, True, answer=300, explanation=0),
    ]
    block = build_model_quality(findings, [], [], now=_NOW)["models"][0]["narration"]
    assert block["evidence_class"] == "[C]"
    assert block["n_eligible"] == 2
    assert block["explanation_tokens"] == 100
    assert block["answer_tokens"] == 400
    assert block["explanation_ratio"] == 0.2
    assert block["insufficient_support"] is True  # below the shared threshold, visible

    # a cell without the split does not become a zero-token cell.
    bare = build_model_quality([_finding("m/one", 0.5, True)], [], [], now=_NOW)
    narration = bare["models"][0]["narration"]
    assert narration["explanation_ratio"] is None
    assert narration["answer_tokens"] is None
    assert "token split" in narration["reason"]


def test_flail_is_an_explicit_unknown_with_its_gap():
    block = build_model_quality([], [], [], now=_NOW)
    assert block["models"] == []
    # the definition block still exists for consumers; unknown is not rendered as a rate.
    assert block["definitions"]["flail"].startswith("no named field exists")


def test_loader_reads_attempts_from_workflow_ledgers(tmp_path):
    spec_dir = tmp_path / "workflows" / "spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "run.json").write_text(
        json.dumps(
            {
                "spec_name": "spec",
                "attempts": [
                    {
                        "job_id": "spec:p1",
                        "phase": "p1",
                        "model": "m/one",
                        "attempt_number": 1,
                        "accepted": True,
                        "status": "ok",
                    }
                ],
            }
        )
    )
    (spec_dir / "not-a-ledger.json").write_text(json.dumps({"hello": "world"}))
    rows, n_ledgers = load_workflow_attempts(tmp_path / "workflows")
    assert n_ledgers == 1
    assert rows == [
        {
            "spec_name": "spec",
            "job_id": "spec:p1",
            "phase": "p1",
            "model": "m/one",
            "attempt_number": 1,
            "accepted": True,
            "status": "ok",
        }
    ]
    # a missing directory is an honest empty population, not an error.
    assert load_workflow_attempts(tmp_path / "nope") == ([], 0)
