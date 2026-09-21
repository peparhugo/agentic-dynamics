#!/usr/bin/env python3
"""Job-queue dead-letter surface (proposal §7 slice 1, R4).

The framework queue's failure model was "a failed job sits in the status hash as ``failed``
forever" — 70 dead analysis jobs pointed at removed files and there was no way to see or
re-drive them. This module adds a per-queue **dead-letter list**:

    story_jobs:dead_letter      (``story_jobs``  -> dlq)
    analysis_jobs:dead_letter
    review_jobs:dead_letter

Each entry is a JSON object ``{job, reason, ts}``. The fleet manager's watcher reads the
list lengths into the board; the operator (or a bounded triage pass) can ``requeue`` an
entry back onto its live queue — a one-at-a-time re-drive, never an automatic blast.

This mirrors the KB stream's own dead-letter discipline (``kb:v1:dead_letter``,
``knowledge_stream.py:54``) — the job queues get the same surface they lacked.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import redis

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))

# The live job queues (mirrors worker.py / analysis_worker.py / the review queue) plus the
# fleet's own submitted-job "queue" (``fleet_jobs`` — not a real Redis list any submit is
# LPUSHed onto, just the DLQ namespace a failed/refused submit's dead-letter entry is filed
# under; the fleet's job submission proposal reuses this surface rather than inventing a
# fourth tier of failure-tracking machinery, p2_launch_handler).
QUEUE_KEYS = ("story_jobs", "analysis_jobs", "review_jobs", "fleet_jobs")


def dlq_key(queue_key: str) -> str:
    """The dead-letter list key for a live queue (``<queue>:dead_letter``)."""
    return f"{queue_key}:dead_letter"


def record_dead(client: redis.Redis, queue_key: str, job: object, reason: str) -> int:
    """Append a failed job to the queue's dead-letter list (returns the new length).

    Called by a worker when a job fails for a *terminal* reason (e.g. a removed worktree),
    so the fleet has a durable record instead of an orphaned ``failed`` status hash row.
    """
    entry = {"job": job, "reason": reason, "ts": time.time()}
    return client.rpush(dlq_key(queue_key), json.dumps(entry))


def dead_counts(client: redis.Redis) -> dict[str, int]:
    """Length of each queue's dead-letter list (the watcher's DLQ surface)."""
    return {q: client.llen(dlq_key(q)) for q in QUEUE_KEYS}


def requeue_one(client: redis.Redis, queue_key: str) -> bool:
    """Pop one entry off the dead-letter list and push it back onto the live queue.

    Returns True if an entry was re-driven. A bounded, one-at-a-time re-drive — the
    proposal's slice-3 DLQ triage ("re-drive or tombstone") is done entry by entry.
    """
    raw = client.lpop(dlq_key(queue_key))
    if raw is None:
        return False
    entry = json.loads(raw)
    client.rpush(queue_key, json.dumps(entry["job"]))
    return True


def list_dead(client: redis.Redis, queue_key: str) -> list[dict]:
    """The decoded dead-letter entries for one queue (read-only, for the board/triage)."""
    raw = client.lrange(dlq_key(queue_key), 0, -1)
    return [json.loads(e) for e in raw]


def triage(client: redis.Redis, *, out: str | Path, apply: bool = False) -> dict:
    """Characterize every job-queue DLQ into one durable report; optionally clear the lists.

    Never requeues: a dead job re-driven onto the live queue EXECUTES (spend, side effects),
    so re-queueing stays an explicit per-entry operator act (:func:`requeue_one`). The report
    is the durable record of what was cleared; ``apply`` empties the live dead-letter lists.
    """
    report: dict = {"schema": "dlq-triage/v1", "ts": time.time(), "queues": {}, "cleared": False}
    for queue in QUEUE_KEYS:
        entries = list_dead(client, queue)
        counts: dict[str, int] = {}
        for entry in entries:
            reason = str(entry.get("reason") or entry.get("error") or "?")[:120]
            counts[reason] = counts.get(reason, 0) + 1
        top = dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:10])
        report["queues"][queue] = {"count": len(entries), "by_reason": top, "entries": entries}
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    if apply:
        for queue in QUEUE_KEYS:
            client.delete(dlq_key(queue))
        report["cleared"] = True
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Job-queue dead-letter triage.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_triage = sub.add_parser(
        "triage", help="write a durable DLQ report; --apply clears the live dead-letter lists"
    )
    p_triage.add_argument("--out", required=True, help="the report path (JSON)")
    p_triage.add_argument("--apply", action="store_true", help="clear the live dead-letter lists")
    p_triage.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    client = redis.Redis(
        host=os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1"),
        port=int(os.environ.get("FINOPS_REDIS_PORT", "6380")),
        db=int(os.environ.get("FINOPS_REDIS_DB", "1")),
        socket_timeout=10,
    )
    if args.command == "triage":
        report = triage(client, out=args.out, apply=args.apply)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            total = sum(meta["count"] for meta in report["queues"].values())
            print(
                f"dlq triage: {total} dead entr(ies) across {len(report['queues'])} queue(s) "
                f"→ {args.out}" + ("; lists CLEARED" if report["cleared"] else " (report only)")
            )
            for queue, meta in report["queues"].items():
                if meta["count"]:
                    print(f"  {queue}: {meta['count']}")
                    for reason, n in list(meta["by_reason"].items())[:3]:
                        print(f"      {n:4d}  {reason}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
