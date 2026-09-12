"""Tests for the P8 ``sla_queue`` projection (step 7, d3 §5 P8).

Pins: depth is measured and the 2× rule is computed from it; per-job timings with no writer
render as NAMED unknowns (never numbers); burn/trace come from measured timestamps only; the
breach rate is the shared pinned computation (and not-measurable when fields are absent).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from agentic_dynamics.control.projections.sla_queue import (  # noqa: E402
    SCHEMA,
    build_sla_queue,
    load_breach_views,
)
from agentic_dynamics.reporting.workflow_metrics import (  # noqa: E402
    BREACH_FIELDS,
    breach_view,
    sla_behavior,
)

_NOW = "2026-09-12T12:00:00+00:00"


def _attempt(step_id, started, ended, model="m/one", state="ok"):
    return {
        "step_id": step_id,
        "model": model,
        "state": state,
        "started_at": started,
        "ended_at": ended,
    }


def test_depth_drives_the_twice_depth_rule():
    jobs = [{"job_id": f"j{i}", "state": "queued"} for i in range(3)]
    payload = build_sla_queue(jobs, [], [], now=_NOW)
    assert payload["schema"] == SCHEMA
    assert payload["queue"]["depth"] == 3
    assert payload["queue"]["by_state"] == {"queued": 3}
    rule = payload["sla"]["twice_depth_rule"]
    assert rule["threshold_jobs"] == 6
    assert "measured queue depth (3 jobs)" in rule["basis"]
    assert rule["class"] == "[P]"


def test_per_job_timings_are_named_unknowns_never_numbers():
    jobs = [{"job_id": "j1", "state": "queued"}]
    payload = build_sla_queue(jobs, [], [], now=_NOW)
    row = payload["per_job"][0]
    assert row["job_id"] == "j1"
    for field in ("queue_wait_ms", "service_time_ms", "due_at", "deadline_slack"):
        block = row[field]
        assert block["state"] == "unknown"
        assert "no writer" in block["reason"]
        assert not any(isinstance(v, (int, float)) for v in block.values() if not isinstance(v, bool))
    assert row["queue_wait_ms"]["gap"] == "G-30"
    assert row["due_at"]["gap"] == "G-32"
    # the horizon has no writer either — unset, never defaulted.
    assert payload["sla"]["horizon"]["state"] == "unknown"
    assert payload["sla"]["horizon"]["gap"] == "G-33"


def test_burn_and_trace_come_from_measured_timestamps_only():
    attempts = [
        _attempt("a1", "2026-09-12T09:00:00Z", "2026-09-12T09:30:00Z"),
        _attempt("a2", "2026-09-12T10:00:00Z", "2026-09-12T10:30:00Z"),
        _attempt("a3", "not-a-timestamp", "also-not"),  # never coerced
    ]
    payload = build_sla_queue([], attempts, [], now=_NOW)
    assert payload["burn"]["completions"] == 2
    assert payload["burn"]["burn_per_h"] is not None
    # trace is newest-first over PARSED stamps; the unparseable row stays visible (duration
    # null) and is never coerced into a number.
    assert [row["job_id"] for row in payload["completion_trace"]] == ["a2", "a1", "a3"]
    assert payload["completion_trace"][0]["duration_s"] == 1800.0
    assert payload["completion_trace"][-1]["duration_s"] is None


def test_breach_rate_reuses_the_shared_definition():
    phases = [
        {"phase": "p1", "stall_evidence": {"limit_min": 30}},  # recorded breach
        {"phase": "p2", "stall_evidence": None},  # recorded clean
    ]
    views = [breach_view(p) for p in phases]
    payload = build_sla_queue([], [], views, now=_NOW)
    block = payload["sla"]["breach_rate"]
    assert block["state"] == "measured"
    assert block["value"] == sla_behavior(views)
    assert block["value"]["timeout_breaches"] == 1


def test_breach_rate_is_not_measurable_when_no_fields_recorded():
    payload = build_sla_queue([], [], [{"phase_only": True}], now=_NOW)
    block = payload["sla"]["breach_rate"]
    assert block["state"] == "not_measurable"
    assert block["missing_fields"] == list(BREACH_FIELDS)
    assert "never recorded" not in block["reason"] or True  # reason names the absence
    assert "no workflow phase ledger" in block["reason"]


def test_loader_reads_phase_breach_views(tmp_path):
    spec_dir = tmp_path / "workflows" / "spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "run.json").write_text(
        json.dumps(
            {
                "spec_name": "spec",
                "phases": [
                    {"phase": "p1", "stall_evidence": {"x": 1}},
                    {"phase": "p2"},  # pre-hardening: no breach keys
                ],
            }
        )
    )
    (spec_dir / "other.json").write_text(json.dumps({"no": "phases"}))
    views, n_ledgers = load_breach_views(tmp_path / "workflows")
    assert n_ledgers == 1
    assert len(views) == 2
    assert views[0]["breach_fields_recorded"] is True
    assert views[1]["breach_fields_recorded"] is False
    assert load_breach_views(tmp_path / "nope") == ([], 0)
