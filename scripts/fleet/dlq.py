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

import json
import os
import time

import redis

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))

# The three live job queues (mirrors worker.py / analysis_worker.py / the review queue).
QUEUE_KEYS = ("story_jobs", "analysis_jobs", "review_jobs")


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
