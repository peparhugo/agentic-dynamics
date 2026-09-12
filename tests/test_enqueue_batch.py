"""Tests for the deferred batch lane's enqueue contract (rule 6, step 12).

Pins the queued-aware skip helper: a cell already waiting in EITHER lane must be dropped from
a re-fill (the mechanism behind the ~65x duplication the controller had cleared), and junk
rows must not crash a fill.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src", _ROOT / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from enqueue import BATCH_QUEUE_KEY, QUEUE_KEY, queued_cell_ids  # noqa: E402


class _FakeQueue:
    """A minimal lrange-only Redis stand-in keyed by list name."""

    def __init__(self, rows: dict[str, list[str]]) -> None:
        self.rows = rows
        self.asked: list[str] = []

    def lrange(self, key, start, end):
        self.asked.append(key)
        return self.rows.get(key, [])


def test_reads_cell_ids_from_both_lanes():
    fake = _FakeQueue(
        {
            QUEUE_KEY: [json.dumps({"cell_id": "on-1"})],
            BATCH_QUEUE_KEY: [json.dumps({"cell_id": "batch-1"}), json.dumps({"cell_id": "batch-2"})],
        }
    )
    ids = queued_cell_ids(fake)
    assert ids == {"on-1", "batch-1", "batch-2"}
    assert fake.asked == [QUEUE_KEY, BATCH_QUEUE_KEY]


def test_junk_rows_are_skipped_not_fatal():
    fake = _FakeQueue(
        {
            QUEUE_KEY: ["not json", json.dumps({"no_cell": True}), json.dumps({"cell_id": "ok"})],
            BATCH_QUEUE_KEY: [],
        }
    )
    assert queued_cell_ids(fake) == {"ok"}


def test_a_lane_read_failure_does_not_crash_the_fill():
    class _Boom:
        def lrange(self, key, start, end):
            raise RuntimeError("redis down")

    assert queued_cell_ids(_Boom()) == set()
