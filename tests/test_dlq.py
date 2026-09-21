"""Tests for the job-queue dead-letter triage (``scripts/fleet/dlq.py``).

The triage pass answers "what is in the piles, and is it safe to clear?": it writes one
durable report (counts by reason + full entries) and only empties the live lists when
``--apply`` is explicit. It NEVER requeues — a dead job re-driven onto the live queue
EXECUTES — so re-queueing stays an explicit per-entry operator act.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _dlq():
    fleet_dir = str(ROOT / "scripts" / "fleet")
    if fleet_dir not in sys.path:
        sys.path.insert(0, fleet_dir)
    return importlib.import_module("dlq")


class _FakeRedis:
    """The redis surface dlq.py's triage touches: list reads and deletes."""

    def __init__(self) -> None:
        self._lists: dict[str, list[str]] = {}

    def lrange(self, key: str, start: int, end: int) -> list[str]:
        return list(self._lists.get(key, []))

    def delete(self, key: str) -> int:
        existed = key in self._lists
        self._lists.pop(key, None)
        return 1 if existed else 0


def test_triage_writes_a_report_and_apply_clears_the_lists(tmp_path):
    dlq = _dlq()
    r = _FakeRedis()
    r._lists[dlq.dlq_key("story_jobs")] = [
        json.dumps({"job": "j1", "reason": "boom"}),
        json.dumps({"job": "j2", "reason": "boom"}),
    ]
    r._lists[dlq.dlq_key("fleet_jobs")] = [json.dumps({"job": "j3", "reason": "other"})]
    out = tmp_path / "dlq_report.json"

    report = dlq.triage(r, out=out, apply=False)
    assert report["queues"]["story_jobs"]["count"] == 2
    assert report["queues"]["story_jobs"]["by_reason"] == {"boom": 2}
    assert report["queues"]["fleet_jobs"]["by_reason"] == {"other": 1}
    assert report["cleared"] is False
    assert out.is_file()
    assert json.loads(out.read_text(encoding="utf-8"))["schema"] == "dlq-triage/v1"
    # Without --apply the live lists are untouched.
    assert r._lists[dlq.dlq_key("story_jobs")]

    report2 = dlq.triage(r, out=out, apply=True)
    assert report2["cleared"] is True
    assert r._lists.get(dlq.dlq_key("story_jobs")) in (None, [])
    assert r._lists.get(dlq.dlq_key("fleet_jobs")) in (None, [])
    # The report survives the clear — it is the durable record.
    assert json.loads(out.read_text(encoding="utf-8"))["queues"]["story_jobs"]["count"] == 2
