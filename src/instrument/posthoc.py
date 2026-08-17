"""Shared post-hoc job construction + enqueue primitives.

The ``execute -> analyze -> review`` chain is driven by three Redis queues on the
isolated framework instance (``finops-queue``, DB 1, port 6380):

    story_jobs     -> worker.py            (execute)
    analysis_jobs  -> analysis_worker.py   (analyze)
    review_jobs    -> review_worker.py     (review)

This module is the single source of truth for the job dict shapes and the
queue/status key names, so the batch backfill scripts (``enqueue_analysis.py``,
``enqueue_reviews.py``) and the auto-trigger paths in the workers (``worker.py``,
``analysis_worker.py``) cannot drift. See ``docs/auto_posthoc_survey.md``.

Job shape contracts
--------------------
Analysis job (payload of ``analysis_jobs``)::

    {"story_id": str, "worktree": str, "result_path": str}

Review jobs (payload of ``review_jobs``) — one per session commit plus one
story-level job::

    {"job_id": str, "story_name": str, "story_id": str, "worktree": str,
     "commit_hash": str, "commit_message": str, "session_number": int,
     "model": str, "job_type": "story_review" | absent}
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

# Queue / status key names — canonical, shared by producers and consumers so the
# ``lpush`` target and the ``hset`` ledger can never drift apart.
ANALYSIS_QUEUE = "analysis_jobs"
ANALYSIS_STATUS = "analysis_status"
REVIEW_QUEUE = "review_jobs"
REVIEW_STATUS = "review_status"

# Reviews are always run by a cheap model, independent of the execute model.
DEFAULT_REVIEW_MODEL = "deepseek/deepseek-v4-flash"


def build_analysis_job(story_id: str, worktree: str, result_path: str | Path) -> dict[str, str]:
    """Build one analysis job dict — the ``analysis_jobs`` payload.

    Mirrors the shape consumed by ``analysis_worker.py`` (``story_id``,
    ``worktree``, ``result_path``). Keeping construction here means the worker
    auto-trigger and the ``enqueue_analysis.py`` backfill emit identical jobs.
    """
    return {
        "story_id": story_id,
        "worktree": worktree,
        "result_path": str(result_path),
    }


def analysis_job_from_result(result_path: str | Path) -> dict[str, str] | None:
    """Read a saved story result JSON and build its analysis job.

    Returns ``None`` when the file is unreadable or lacks a ``story_id``, so a
    malformed result never produces a broken job. This is what ``worker.py``
    calls after ``run_story.py`` saves a cell, without re-scanning the corpus.
    """
    path = Path(result_path)
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    story_id = data.get("story_id")
    if not story_id:
        return None
    return build_analysis_job(story_id, data.get("worktree", ""), path)


def worktree_commits(worktree: Path) -> list[tuple[str, str, int]]:
    """Return ``[(hash, msg, session_num), ...]`` for a story worktree.

    Parses ``git log --reverse`` for commits whose subject mentions ``Session N``.
    Returns an empty list when the worktree is missing or has no story commits —
    callers treat "no commits" as "nothing to review".
    """
    try:
        log = subprocess.run(
            ["git", "-C", str(worktree), "log", "--reverse", "--format=%H|%s"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []

    commits: list[tuple[str, str, int]] = []
    for line in log.strip().splitlines():
        if "|" not in line:
            continue
        commit_hash, commit_msg = line.split("|", 1)
        if "Session" not in commit_msg:
            continue
        m = re.search(r"Session\s+(\d+)", commit_msg)
        session_num = int(m.group(1)) if m else 0
        commits.append((commit_hash, commit_msg, session_num))
    return commits


def build_commit_review_job(
    story_id: str,
    story_name: str,
    worktree: str | Path,
    commit_hash: str,
    commit_message: str,
    session_number: int,
    model: str = DEFAULT_REVIEW_MODEL,
) -> dict[str, Any]:
    """Build one per-commit review job — a ``review_jobs`` payload."""
    return {
        "job_id": f"{story_id}_{session_number}",
        "story_name": story_name,
        "story_id": story_id,
        "worktree": str(worktree),
        "commit_hash": commit_hash,
        "commit_message": commit_message,
        "session_number": session_number,
        "model": model,
    }


def build_story_review_job(
    story_id: str,
    story_name: str,
    worktree: str | Path,
    model: str = DEFAULT_REVIEW_MODEL,
) -> dict[str, Any]:
    """Build the story-level review job (``job_type`` = ``story_review``)."""
    return {
        "job_id": f"{story_id}_story",
        "story_name": story_name,
        "story_id": story_id,
        "worktree": str(worktree),
        "commit_hash": "",
        "commit_message": "",
        "session_number": 0,
        "model": model,
        "job_type": "story_review",
    }


def build_review_jobs(
    story_id: str,
    story_name: str,
    worktree: str | Path,
    commits: list[tuple[str, str, int]],
    model: str = DEFAULT_REVIEW_MODEL,
) -> list[dict[str, Any]]:
    """Build every review job for one story: per-commit jobs + story-level job."""
    jobs: list[dict[str, Any]] = [
        build_commit_review_job(story_id, story_name, worktree, ch, cm, sn, model)
        for ch, cm, sn in commits
    ]
    jobs.append(build_story_review_job(story_id, story_name, worktree, model))
    return jobs


def enqueue_job(r: Any, queue_key: str, status_key: str, job: dict, status_field: str) -> None:
    """Push one job onto ``queue_key`` and seed its status — the canonical write path.

    Every producer (backfill scripts and worker auto-triggers) funnels through
    here so the ``lpush`` + ``hset`` pair, the key names, and the ``"queued"``
    seed are defined exactly once.
    """
    r.lpush(queue_key, json.dumps(job))
    r.hset(status_key, status_field, "queued")


def trigger_analysis(r: Any, result_path: str | Path) -> bool:
    """Build + enqueue one analysis job for a saved story result.

    The ``worker.py`` auto-trigger: called after ``run_story.py`` saves a cell.
    Returns ``True`` if a job was enqueued, ``False`` if there was nothing to
    enqueue (missing/malformed result). Never raises for bad input — a trigger
    failure must not fail the cell (``enqueue_analysis.py`` is the safety net).
    """
    job = analysis_job_from_result(result_path)
    if job is None:
        return False
    enqueue_job(r, ANALYSIS_QUEUE, ANALYSIS_STATUS, job, job["story_id"])
    return True


def trigger_reviews(
    r: Any,
    story_id: str,
    story_name: str,
    worktree: str | Path,
    model: str = DEFAULT_REVIEW_MODEL,
) -> int:
    """Build + enqueue review jobs for one story. Returns the number enqueued.

    The ``analysis_worker.py`` auto-trigger: called after an analysis job
    completes. Mirrors ``enqueue_reviews.py``'s "skip when no commits" rule (a
    story with no session commits gets no review jobs at all).
    """
    commits = worktree_commits(Path(worktree))
    if not commits:
        return 0
    jobs = build_review_jobs(story_id, story_name, worktree, commits, model)
    for job in jobs:
        enqueue_job(r, REVIEW_QUEUE, REVIEW_STATUS, job, job["job_id"])
    return len(jobs)
