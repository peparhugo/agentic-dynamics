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
import subprocess
import sys
from pathlib import Path

import redis

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from instrument.story import load_story_result

REDIS_HOST = "127.0.0.1"
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))
QUEUE_KEY = "review_jobs"
STATUS_KEY = "review_status"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "experiments" / "results" / "stories"
REVIEWS_DIR = Path(__file__).resolve().parent.parent / "experiments" / "results" / "reviews"

MODEL = "deepseek/deepseek-v4-flash"


def _get_worktree_commits(worktree: Path) -> list[tuple[str, str, int]]:
    """Get story session commits from a worktree. Returns [(hash, msg, session_num), ...]."""
    try:
        log = subprocess.run(
            ["git", "-C", str(worktree), "log", "--reverse", "--format=%H|%s"],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []

    commits = []
    for line in log.strip().splitlines():
        if "|" not in line:
            continue
        ch, cm = line.split("|", 1)
        if "Session" not in cm:
            continue
        import re
        m = re.search(r"Session\s+(\d+)", cm)
        sn = int(m.group(1)) if m else 0
        commits.append((ch, cm, sn))
    return commits


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
        commits = _get_worktree_commits(worktree)
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
            job = {
                "job_id": f"{story.story_id}_{sn}",
                "story_name": story.story_name,
                "story_id": story.story_id,
                "worktree": str(worktree),
                "commit_hash": ch,
                "commit_message": cm,
                "session_number": sn,
                "model": MODEL,
            }
            if not dry_run:
                r.lpush(QUEUE_KEY, json.dumps(job))
                r.hset(STATUS_KEY, job["job_id"], "queued")
            total_jobs += 1

        # Also enqueue story-level review job
        story_job = {
            "job_id": f"{story.story_id}_story",
            "story_name": story.story_name,
            "story_id": story.story_id,
            "worktree": str(worktree),
            "commit_hash": "",
            "commit_message": "",
            "session_number": 0,
            "model": MODEL,
            "job_type": "story_review",
        }
        if not dry_run:
            r.lpush(QUEUE_KEY, json.dumps(story_job))
            r.hset(STATUS_KEY, story_job["job_id"], "queued")
        total_jobs += 1

    if dry_run:
        print(f"Would enqueue {total_jobs} review jobs ({stories_with_worktrees} stories)")
    else:
        print(f"Enqueued {total_jobs} review jobs ({stories_with_worktrees} stories)")
        print(f"Queue: {r.llen(QUEUE_KEY)} pending")
        print(f"Start workers: nohup python3 scripts/review_worker.py &")


if __name__ == "__main__":
    main()
