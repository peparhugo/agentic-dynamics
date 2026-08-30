"""Pipeline-stage status — summarize the execute/analyze/review stages.

Shared by ``apps/control_room/server.py`` (the Control Room matrix) and ``scripts/monitor.py``
(the ``--json`` dashboard) so the three-stage pipeline view can never drift.

Stage layout on the framework Redis (127.0.0.1:6380 db 1):

    execute  story_jobs / story_status / story_results
    analyze  analysis_jobs / analysis_status
    review   (FILE-derived — the trigger → review_all path writes
             experiments/results/reviews/, never the legacy queue)

Only the execute stage has a results hash; the analyze stage's ``results_saved`` is
``None`` ("not applicable"). The review stage RETIRED the legacy ``review_jobs`` queue and
``review_status`` hash from the display in 2026-08-31: the review-unit cut-over consumes the
``fleet:review_trigger`` channel and runs ``review_all --only-missing`` directly — the queue
was never consumed by the current path, and the hash went stale because the direct runner
never writes it. The display now derives the review stage from the review files on disk (the
single source of truth the pipeline actually writes).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import redis

STAGE_KEYS: dict[str, tuple[str, str, str | None]] = {
    "execute": ("story_jobs", "story_status", "story_results"),
    "analyze": ("analysis_jobs", "analysis_status", None),
}

REVIEWS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "experiments" / "results" / "reviews"
RESULTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "experiments" / "results" / "stories"


def stage_summary(
    redis_client: redis.Redis,
    queue_key: str,
    status_key: str,
    results_key: str | None = None,
) -> dict[str, Any]:
    """Summarize one pipeline stage from its queue list + status hash.

    ``status_key`` is a hash of ``id -> status``; ``queue_key`` is the list
    backing the workers' BRPOP. Only the execute stage passes a ``results_key``
    (``story_results``); the analyze stage passes ``None`` and gets
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


def review_stage_summary(redis_client: redis.Redis) -> dict[str, Any]:
    """File-derived review stage (the legacy queue is retired — see the module docstring).

    ``total`` = the story corpus; ``done`` = stories with a complete review aggregate;
    ``failed`` = the unreviewable stories recorded by the error markers (the review_unit's
    ``review_all --only-missing`` wrote them); ``queued``/``running`` = 0 by construction
    (the trigger → review_unit model has no queue; batches run in seconds-to-minutes).
    """
    story_ids = set()
    for f in RESULTS_DIR.glob("*.json"):
        if "dvs" in f.name or "log" in f.name:
            continue
        # Strip the ".json" suffix properly — model names like gpt-5.6-luna contain dots,
        # so a dot-split would truncate before the story id.
        story_ids.add(f.name[:-len(".json")].rsplit("_", 1)[-1])
    complete_aggregates: dict[str, Any] = {}
    for f in REVIEWS_DIR.glob("review_*.json"):
        if len(f.stem) != len("review_") + 12 or not f.stem[len("review_"):].isalnum():
            continue
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("story_review") and data.get("commit_reviews"):
            complete_aggregates[f.stem[len("review_"):]] = True
    done = sum(1 for sid in story_ids if sid in complete_aggregates)
    failed = len(list(REVIEWS_DIR.glob("review_*.error")))
    total = len(story_ids)
    return {
        "total": total,
        "remaining_in_queue": 0,
        "queued": 0,
        "running": 0,
        "done": done,
        "failed": failed,
        "timeout": 0,
        "retry": 0,
        "completed": done + failed,
        "results_saved": None,
        "cells": {"reviewed": done, "corpus": total},
    }
