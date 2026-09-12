"""Tests for the queue-timing writer (step 8, G-30/G-32): stamp -> settle -> append.

Pins the arithmetic (ms conversions, clamped waits, slack sign), the absence semantics (no
enqueue stamp -> no wait key, never a fabricated number), the append-only roundtrip, and the
contract with the P8 projection's reader.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from agentic_dynamics.control.projections.sla_queue import load_job_timings  # noqa: E402
from agentic_dynamics.runtime.queue_timings import (  # noqa: E402
    append_timing,
    stamp_enqueue,
    timing_row,
)


def test_stamp_enqueue_sets_transport_times_and_policy():
    cells = [{"cell_id": "c1"}, {"cell_id": "c2", "enqueued_at": 5.0}]
    stamp_enqueue(cells, due_hours=2, now=100.0)
    assert cells[0]["enqueued_at"] == 100.0
    assert cells[0]["due_at"] == 100.0 + 7200.0
    # an existing stamp (an interleaved queue row) is kept — its wait is real elapsed time
    assert cells[1]["enqueued_at"] == 5.0
    assert cells[1]["due_at"] == 5.0 + 7200.0
    # idempotent: a second stamp does not move the times
    stamp_enqueue(cells, now=999.0)
    assert cells[0]["enqueued_at"] == 100.0


def test_timing_row_measures_wait_and_service():
    cell = {"cell_id": "c1", "story": "s", "model": "m", "enqueued_at": 100.0, "due_at": 220.0}
    row = timing_row(cell, status="done", started_at=130.0, ended_at=190.0)
    assert row["queue_wait_ms"] == 30000.0
    assert row["service_time_ms"] == 60000.0
    assert row["due_at"] == 220.0
    assert row["deadline_slack_ms"] == 30000.0  # due - ended, positive = early
    assert row["enqueued_at"] == 100.0


def test_timing_row_without_a_stamp_omits_the_wait_never_fabricates():
    row = timing_row({"cell_id": "c1"}, status="failed", started_at=10.0, ended_at=12.0)
    assert "queue_wait_ms" not in row
    assert "enqueued_at" not in row
    assert row["service_time_ms"] == 2000.0
    assert "due_at" not in row  # no policy stamped -> absent, not zero


def test_timing_row_clamps_clock_skew_and_rejects_junk():
    row = timing_row(
        {"cell_id": "c1", "enqueued_at": "soon", "due_at": True},
        status="done",
        started_at=10.0,
        ended_at=9.5,  # backwards clock -> service time negative is still the measured truth
        enqueued_at=20.0,  # started BEFORE enqueue -> clamp to 0, never negative
    )
    assert row["queue_wait_ms"] == 0.0
    assert row["service_time_ms"] == -500.0
    assert "due_at" not in row  # a bool is not a timestamp


def test_settled_slack_can_be_negative_and_stays_recorded():
    row = timing_row(
        {"cell_id": "c1", "enqueued_at": 0.0, "due_at": 100.0},
        status="done",
        started_at=10.0,
        ended_at=130.0,  # 30s past the deadline
    )
    assert row["deadline_slack_ms"] == -30000.0


def test_append_roundtrips_through_the_projection_reader(tmp_path):
    path = tmp_path / "queue_timings.jsonl"
    warning = append_timing(
        timing_row(
            {"cell_id": "c1", "story": "s", "model": "m", "enqueued_at": 1.0},
            status="done",
            started_at=2.0,
            ended_at=3.0,
        ),
        path=path,
    )
    assert warning is None
    rows, skipped = load_job_timings(path)
    assert skipped == 0
    assert rows[0]["cell_id"] == "c1"
    assert rows[0]["queue_wait_ms"] == 1000.0
    assert rows[0]["service_time_ms"] == 1000.0


def test_append_failure_is_a_warning_never_a_raise(tmp_path):
    # a path whose parent is a FILE cannot be created — the append must warn, not raise
    blocker = tmp_path / "blocker"
    blocker.write_text("occupied")
    warning = append_timing({"cell_id": "c1"}, path=blocker / "sub" / "timings.jsonl")
    assert warning is not None
    assert "could not append" in warning


def test_rows_are_valid_json_lines(tmp_path):
    path = tmp_path / "queue_timings.jsonl"
    for cell_id in ("a", "b"):
        append_timing({"cell_id": cell_id, "service_time_ms": 1.0}, path=path)
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln]
    assert len(lines) == 2
    assert [json.loads(ln)["cell_id"] for ln in lines] == ["a", "b"]


def test_batch_mode_is_recorded_only_for_batch_cells():
    """The deferred lane's accounting: present on batch rows, ABSENT on on-demand rows."""
    batch = timing_row(
        {"cell_id": "c1", "batch_mode": True}, status="done", started_at=1.0, ended_at=2.0
    )
    on_demand = timing_row({"cell_id": "c2"}, status="done", started_at=1.0, ended_at=2.0)
    assert batch["batch_mode"] is True
    assert "batch_mode" not in on_demand  # absence IS the on-demand classification
