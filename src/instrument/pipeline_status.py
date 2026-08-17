"""Pipeline-stage status — summarize the execute/analyze/review Redis queues.

Shared by ``admin/server.py`` (the Control Room matrix) and ``scripts/monitor.py``
(the ``--json`` dashboard) so the three-stage pipeline view can never drift.

Stage layout on the framework Redis (127.0.0.1:6380 db 1):

    execute  story_jobs / story_status / story_results
    analyze  analysis_jobs / analysis_status
    review   review_jobs / review_status

Only the execute stage has a results hash; the post-hoc stages do not, so their
``results_saved`` is ``None`` ("not applicable") rather than a fabricated zero.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import redis

STAGE_KEYS: dict[str, tuple[str, str, str | None]] = {
    "execute": ("story_jobs", "story_status", "story_results"),
    "analyze": ("analysis_jobs", "analysis_status", None),
    "review": ("review_jobs", "review_status", None),
}


def stage_summary(
    redis_client: redis.Redis,
    queue_key: str,
    status_key: str,
    results_key: str | None = None,
) -> dict[str, Any]:
    """Summarize one pipeline stage from its queue list + status hash.

    ``status_key`` is a hash of ``id -> status``; ``queue_key`` is the list
    backing the workers' BRPOP. Only the execute stage passes a ``results_key``
    (``story_results``); post-hoc stages pass ``None`` and get
    ``results_saved=None``.

    A ``retry_`` status prefix (the review worker re-enqueues a failed job as
    ``retry_N``) is reported separately in ``retry`` and also folded into
    ``running`` — a job awaiting retry is still in flight, not terminal.
    """
    statuses = redis_client.hgetall(status_key)
    counts = Counter(statuses.values())
    retry = sum(value for key, value in counts.items() if key.startswith("retry_"))
    running = counts.get("running", 0) + retry
    return {
        "total": len(statuses),
        "remaining_in_queue": redis_client.llen(queue_key),
        "queued": counts.get("queued", 0),
        "running": running,
        "done": counts.get("done", 0),
        "failed": counts.get("failed", 0),
        "timeout": counts.get("timeout", 0),
        "retry": retry,
        "completed": counts.get("done", 0) + counts.get("failed", 0) + counts.get("timeout", 0),
        "results_saved": len(redis_client.hgetall(results_key)) if results_key else None,
        "cells": statuses,
    }
