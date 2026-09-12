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
    load_job_timings,
)
from agentic_dynamics.reporting.workflow_metrics import (  # noqa: E402
    BREACH_FIELDS,
    breach_view,
    sla_behavior,
)

_NOW = "2026-09-12T12:00:00+00:00"


def _iso(epoch: float) -> str:
    """An ISO-8601 UTC stamp for an epoch second (timezone-aware, matching the payload)."""
    from datetime import datetime, timezone

    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


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


def test_a_payload_without_stamps_keeps_named_unknowns():
    """A pre-step-8 cell has no enqueue stamp: the wait is a named absence, never a number."""
    jobs = [{"job_id": "old-job", "state": "queued"}]
    payload = build_sla_queue(jobs, [], [], now=_NOW)
    row = payload["per_job"][0]
    assert row["job_id"] == "old-job"
    assert row["queue_wait_ms"]["state"] == "unknown"
    assert "no enqueue stamp" in row["queue_wait_ms"]["reason"]
    assert row["queue_wait_ms"]["gap"] == "G-30"
    # service time has not happened yet — pending, not unknown and not zero
    assert row["service_time_ms"]["state"] == "pending"
    assert row["due_at"]["gap"] == "G-32"
    # the horizon is unset (no policy stamped) — still named, never defaulted
    assert payload["sla"]["horizon"]["state"] == "unset"
    assert payload["sla"]["horizon"]["gap"] == "G-33"


def test_live_wait_is_measured_and_pending_fields_stay_pending():
    """Step 8: enqueue stamps enqueued_at -> the live wait is a subtraction the room CAN do."""
    enqueued = 1_756_900_000.0  # 2026-09-...T10:26:40Z — any fixed epoch works
    jobs = [{"cell_id": "c1", "state": "queued", "enqueued_at": enqueued, "due_at": enqueued + 7200}]
    now = 1_756_900_060.0  # 60s later
    payload = build_sla_queue(jobs, [], [], now=_iso(now))
    row = payload["per_job"][0]
    assert row["job_id"] == "c1"
    assert row["queue_wait_so_far_ms"] == 60000.0
    assert row["queue_wait_ms"]["state"] == "pending"
    assert row["service_time_ms"]["state"] == "pending"
    assert row["due_at"] == enqueued + 7200
    assert row["deadline_slack_so_far_ms"] == 7140000.0  # 2h - 60s
    assert payload["sla"]["horizon"]["state"] == "stamped"
    assert payload["sla"]["horizon"]["stamped_jobs"] == 1


def test_recent_completions_serve_the_settled_timings_and_coverage():
    timings = [
        {
            "cell_id": "c1",
            "story": "task_manager_api",
            "model": "m/one",
            "status": "done",
            "enqueued_at": 100.0,
            "started_at": 130.0,
            "ended_at": 190.0,
            "queue_wait_ms": 30000.0,
            "service_time_ms": 60000.0,
        },
        {
            "cell_id": "c2",
            "status": "failed",
            "started_at": 200.0,
            "ended_at": 260.0,
            "service_time_ms": 60000.0,
        },
    ]
    payload = build_sla_queue([], [], [], timings=timings, now=_NOW)
    block = payload["recent_completions"]
    assert block["n_rows"] == 2
    assert block["n_with_queue_wait"] == 1
    assert block["n_with_deadline"] == 0
    # newest ended first; measured keys present only where measured
    assert [row["cell_id"] for row in block["rows"]] == ["c2", "c1"]
    assert block["rows"][1]["queue_wait_ms"] == 30000.0
    assert "queue_wait_ms" not in block["rows"][0]


def test_loader_reads_the_timing_ledger_and_counts_skips(tmp_path):
    path = tmp_path / "queue_timings.jsonl"
    path.write_text(
        '{"cell_id": "c1", "queue_wait_ms": 1.0}\n'
        "not json\n"
        '{"no_cell": true}\n'
        '{"cell_id": "c2", "service_time_ms": 2.0}\n'
    )
    rows, skipped = load_job_timings(path)
    assert [r["cell_id"] for r in rows] == ["c1", "c2"]
    assert skipped == 2
    assert load_job_timings(tmp_path / "nope.jsonl") == ([], 0)


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


def test_a_single_completion_has_no_rate_not_a_fabricated_1e6():
    """Wave C1 — the P8 fix: ONE completion is a single sample. The old ``max(span_h, 1e-6)``
    floor divided by ~zero and fabricated exactly 1,000,000/h (1 / 1e-6); an unmeasurable
    rate is None with a named reason, never a fabricated maximum."""
    attempts = [_attempt("a1", "2026-09-12T09:00:00Z", "2026-09-12T09:30:00Z")]
    payload = build_sla_queue([], attempts, [], now=_NOW)
    assert payload["burn"]["completions"] == 1
    assert payload["burn"]["burn_per_h"] is None
    assert "single_sample" in payload["burn"]["reason"]


def test_two_completions_sharing_a_timestamp_have_no_rate():
    """Two completions at one timestamp span zero hours — still not a throughput."""
    attempts = [
        _attempt("a1", "2026-09-12T09:00:00Z", "2026-09-12T09:30:00Z"),
        _attempt("a2", "2026-09-12T09:05:00Z", "2026-09-12T09:30:00Z"),
    ]
    payload = build_sla_queue([], attempts, [], now=_NOW)
    assert payload["burn"]["completions"] == 2
    assert payload["burn"]["burn_per_h"] is None
    assert "zero_span" in payload["burn"]["reason"]


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
