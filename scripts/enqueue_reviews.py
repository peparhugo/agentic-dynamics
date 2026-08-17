"""enqueue_reviews.py — Push review jobs to Redis queue for parallel processing.

Scans all story result JSONs, finds worktree commits, enqueues review jobs.
Workers (review_worker.py) pop jobs and run review_commit() with DeepSeek Flash.

Usage:
  python3 scripts/enqueue_reviews.py          # enqueue all pending reviews
  python3 scripts/enqueue_reviews.py --dry-run # show what would be enqueued
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import redis

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from instrument.posthoc import (  # noqa: E402
    REVIEW_QUEUE,
    REVIEW_STATUS,
    DEFAULT_REVIEW_MODEL,
    build_commit_review_job,
    build_story_review_job,
    enqueue_job,
    worktree_commits,
)
from instrument.story import load_story_result

REDIS_HOST = "127.0.0.1"
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))
RESULTS_DIR = Path(__file__).resolve().parent.parent / "experiments" / "results" / "stories"
REVIEWS_DIR = Path(__file__).resolve().parent.parent / "experiments" / "results" / "reviews"


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    r.ping()

    if not dry_run:
        REVIEWS_DIR.mkdir(parents=True, exist_ok=True)

    result_files = sorted(
        f for f in RESULTS_DIR.glob("*.json")
        if "dvs" not in f.name and "log" not in f.name
    )

    total_jobs = 0
    stories_with_worktrees = 0

    for rf in result_files:
        try:
            story = load_story_result(rf)
        except Exception:
            continue

        worktree = Path(story.worktree)
        if not worktree.exists():
            continue

        stories_with_worktrees += 1
        commits = worktree_commits(worktree)
        if not commits:
            continue

        # Check if story review was already done
        review_path = REVIEWS_DIR / f"review_{story.story_id}.json"
        if review_path.exists():
            try:
                existing = json.loads(review_path.read_text())
                reviewed_commits = len(existing.get("commit_reviews", []))
                if reviewed_commits >= len(commits) and existing.get("story_review"):
                    continue  # Already complete
            except (json.JSONDecodeError, OSError):
                pass

        for ch, cm, sn in commits:
            job = build_commit_review_job(
                story.story_id, story.story_name, worktree, ch, cm, sn,
                DEFAULT_REVIEW_MODEL,
            )
            if not dry_run:
                enqueue_job(r, REVIEW_QUEUE, REVIEW_STATUS, job, job["job_id"])
            total_jobs += 1

        # Also enqueue story-level review job
        story_job = build_story_review_job(
            story.story_id, story.story_name, worktree, DEFAULT_REVIEW_MODEL,
        )
        if not dry_run:
            enqueue_job(r, REVIEW_QUEUE, REVIEW_STATUS, story_job, story_job["job_id"])
        total_jobs += 1

    if dry_run:
        print(f"Would enqueue {total_jobs} review jobs ({stories_with_worktrees} stories)")
    else:
        print(f"Enqueued {total_jobs} review jobs ({stories_with_worktrees} stories)")
        print(f"Queue: {r.llen(REVIEW_QUEUE)} pending")
        print("Start workers: nohup python3 scripts/review_worker.py &")


if __name__ == "__main__":
    main()
