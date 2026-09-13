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


def _session(code_lines, files_changed, n=1, **extra):
    row = {
        "session_number": n,
        "code_lines": code_lines,
        "files_changed": files_changed,
    }
    row.update(extra)
    return row


def _story(model, sessions):
    return {"story_name": "s", "model": model, "sessions": sessions}


def test_flail_is_measured_from_session_code_output():
    """G-05: flail is DERIVED from the session rows, not rendered as a no-writer unknown."""
    sessions = [
        _session(0, 0, 1),  # flail: no code, no file changes
        _session(0, 0, 2),  # flail
        _session(10, 2, 3),  # wrote code
        _session(5, 1, 4),
        _session(3, 1, 5),
        _session(0, 3, 6),  # changed files (code counter defaulted) -> not flail
    ]
    payload = build_model_quality([], [_story("m/one", sessions)], [], now=_NOW)
    block = payload["models"][0]["flail"]
    assert block["evidence_class"] == "[C]"
    assert block["definition"].startswith("flail(session)")
    assert block["n_total"] == 6
    assert block["n_eligible"] == 6
    assert block["coverage"] == 1.0
    assert block["flail_sessions"] == 2
    assert block["flail_rate"] == round(2 / 6, 4)
    assert block["insufficient_support"] is False  # 6 >= MIN_CELLS_FOR_RATE
    assert payload["population"]["n_session_rows"] == 6


def test_flail_coverage_counts_ineligible_sessions_first():
    """A session missing either signal is in the coverage gap, never counted as non-flail."""
    sessions = [
        _session(0, 0, 1),  # flail
        _session(4, 1, 2),
        _session(3, 1, 3),
        _session(2, 1, 4),
        _session(5, 2, 5),
        {"session_number": 6},  # neither counter measured
        {"session_number": 7, "code_lines": "x", "files_changed": 1},  # not an int
    ]
    block = build_model_quality([], [_story("m/one", sessions)], [], now=_NOW)["models"][0][
        "flail"
    ]
    assert block["n_total"] == 7
    assert block["n_eligible"] == 5
    assert block["coverage"] == round(5 / 7, 4)
    assert block["flail_sessions"] == 1
    assert block["flail_rate"] == 0.2


def test_flail_zero_denominator_is_unknown_not_zero():
    """No eligible sessions yields a named unknown, never a fabricated 0.0 rate."""
    sessions = [{"session_number": 1}, {"session_number": 2}]
    block = build_model_quality([], [_story("m/one", sessions)], [], now=_NOW)["models"][0][
        "flail"
    ]
    assert block["n_eligible"] == 0
    assert block["flail_rate"] is None
    assert block["insufficient_support"] is True
    assert "no session carries both" in block["reason"]


def test_flail_below_small_sample_is_flagged_not_reported():
    """The shared MIN_CELLS_FOR_RATE rule nulls an under-powered rate (coverage visible)."""
    block = build_model_quality(
        [], [_story("m/one", [_session(0, 0, 1), _session(2, 1, 2)])], [], now=_NOW
    )["models"][0]["flail"]
    assert block["n_eligible"] == 2
    assert block["insufficient_support"] is True
    assert block["flail_rate"] is None
    assert "fewer than" in block["reason"]


def test_flail_is_unknown_only_when_no_population():
    """An empty session population is a named unknown; the definition is still carried."""
    payload = build_model_quality([], [], [], now=_NOW)
    assert payload["models"] == []
    assert payload["population"]["n_session_rows"] == 0
    assert payload["definitions"]["flail"].startswith("flail(session)")


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
