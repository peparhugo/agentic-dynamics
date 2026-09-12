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

from enqueue import (  # noqa: E402
    BATCH_QUEUE_KEY,
    QUEUE_KEY,
    build_cells,
    push_cells,
    queued_cell_ids,
    select_new_cells,
)


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


# ── Wave B4: the shared fill contract the pipeline's matrix phases call ──────


def test_select_new_cells_drops_queued_ids():
    """The factored queued-aware skip: the pipeline's fills run the SAME drop the CLI's do."""
    fake = _FakeQueue({QUEUE_KEY: [json.dumps({"cell_id": "a"})], BATCH_QUEUE_KEY: []})
    kept = select_new_cells(fake, [{"cell_id": "a"}, {"cell_id": "b"}])
    assert [c["cell_id"] for c in kept] == ["b"]


def test_push_cells_writes_payloads_and_seeds_statuses():
    """The ONE fill write: every pushed cell is marked `queued` in story_status."""
    class _FakePushQueue:
        def __init__(self):
            self.lists: dict[str, list[str]] = {}
            self.statuses: dict[str, str] = {}

        def lpush(self, key, value):
            self.lists.setdefault(key, []).insert(0, value)
            return len(self.lists[key])

        def hset(self, key, mapping=None, **kwargs):
            self.statuses.update({k: str(v) for k, v in (mapping or {}).items()})

    fake = _FakePushQueue()
    n = push_cells(
        fake,
        [{"cell_id": "a", "model": "m"}, {"cell_id": "b", "model": "m"}],
        lane=BATCH_QUEUE_KEY,
    )
    assert n == 2
    assert len(fake.lists[BATCH_QUEUE_KEY]) == 2
    assert fake.statuses == {"a": "queued", "b": "queued"}


def test_build_cells_accepts_plan_matrix_params():
    """The ONE builder accepts a plan's stories/tiers/conditions — the pipeline's matrix
    params route here instead of through the deleted hand-rolled copy."""
    cells = build_cells(
        model="openai/gpt-5.6-luna",
        missing_only=False,
        stories=["task_manager_api"],
        tiers=["tier1_minimal"],
        conditions={"good": ["clean"], "bad": ["bad_seed"]},
    )
    assert [c["cell_id"] for c in cells] == [
        "gpt_5_6_luna_task_manager_api_tier1_minimal_good_clean",
        "gpt_5_6_luna_task_manager_api_tier1_minimal_bad_bad_seed",
    ]
