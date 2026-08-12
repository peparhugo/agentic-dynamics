"""review_worker.py — Pop review jobs from Redis, run review_commit() with SDK bridge.

Each job: worktree path, commit hash, session number, story metadata.
Runs the review agent (review_commit or review_story) via opencode SDK bridge.
Writes results to experiments/results/reviews/.

Designed to run in parallel — multiple workers pop jobs atomically via BRPOP.

Usage:
  python3 scripts/review_worker.py     # single worker
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import redis

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from instrument.review import review_commit, review_story

REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
QUEUE_KEY = "review_jobs"
STATUS_KEY = "review_status"
REVIEWS_DIR = Path(__file__).resolve().parent.parent / "experiments" / "results" / "reviews"

BLOCK_TIMEOUT = 5
IDLE_POLLS_BEFORE_EXIT = 6


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][review] {msg}", flush=True)


def _connect_redis() -> redis.Redis:
    delay = 2.0
    attempts = 0
    while True:
        try:
            r = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT,
                decode_responses=True, socket_connect_timeout=10,
                socket_keepalive=True, health_check_interval=30,
            )
            r.ping()
            attempts += 1
            if attempts > 1:
                log(f"Redis connected (attempt {attempts})")
            return r
        except Exception as e:
            attempts += 1
            log(f"Redis unavailable (attempt {attempts}): {e}")
            time.sleep(delay)
            delay = min(delay * 2, 30.0)


def _load_or_create_review(story_id: str) -> dict:
    path = REVIEWS_DIR / f"review_{story_id}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"commit_reviews": []}


def _save_review(story_id: str, data: dict) -> None:
    path = REVIEWS_DIR / f"review_{story_id}.json"
    path.write_text(json.dumps(data, indent=2))


def main() -> None:
    log(f"Started (pid={sys.argv[0]})")

    r = _connect_redis()
    log("Redis connected")

    completed = 0
    failed = 0
    empty_polls = 0

    while True:
        try:
            result = r.brpop(QUEUE_KEY, timeout=BLOCK_TIMEOUT)
        except Exception as e:
            log(f"Redis brpop error: {e}, reconnecting...")
            time.sleep(10)
            r = _connect_redis()
            continue

        if result is None:
            empty_polls += 1
            if empty_polls >= IDLE_POLLS_BEFORE_EXIT:
                try:
                    remaining = r.llen(QUEUE_KEY)
                except Exception:
                    remaining = 0
                if remaining == 0:
                    log(f"Queue empty. Exiting.")
                    break
                empty_polls = 0
            continue

        empty_polls = 0
        _, job_json = result

        try:
            job = json.loads(job_json)
        except json.JSONDecodeError:
            log("Invalid job JSON, skipping")
            continue

        job_id = job["job_id"]
        story_id = job["story_id"]
        worktree = Path(job["worktree"])
        model = job.get("model", "deepseek/deepseek-v4-flash")

        if not worktree.exists():
            log(f"[{job_id}] Worktree missing: {worktree}")
            r.hset(STATUS_KEY, job_id, "failed")
            failed += 1
            continue

        r.hset(STATUS_KEY, job_id, "running")

        try:
            if job.get("job_type") == "story_review":
                log(f"[{job_id}] Story review: {job['story_name']}")
                review = review_story(worktree, job["story_name"], model=model)
                data = _load_or_create_review(story_id)
                data["story_name"] = job["story_name"]
                data["story_id"] = story_id
                data["story_review"] = review.to_dict()
                _save_review(story_id, data)
            else:
                log(f"[{job_id}] Commit review: S{job['session_number']} {job['story_name']}")
                review = review_commit(
                    worktree, job["commit_hash"],
                    story_name=job["story_name"],
                    session_number=job["session_number"],
                    model=model,
                    story_id=story_id,
                )
                data = _load_or_create_review(story_id)
                data["story_name"] = job["story_name"]
                data["story_id"] = story_id
                data["model"] = data.get("model", "unknown")
                # Merge or replace commit review for this session
                existing = {cr["session_number"]: i for i, cr in enumerate(data.get("commit_reviews", []))}
                review_dict = review.to_dict()
                review_dict["session_number"] = job["session_number"]
                if job["session_number"] in existing:
                    data["commit_reviews"][existing[job["session_number"]]] = review_dict
                else:
                    data["commit_reviews"].append(review_dict)
                _save_review(story_id, data)

            r.hset(STATUS_KEY, job_id, "done")
            completed += 1
            log(f"[{job_id}] OK ({completed+failed}/{completed+failed})")

        except Exception as e:
            log(f"[{job_id}] FAILED: {e}")
            r.hset(STATUS_KEY, job_id, "failed")
            failed += 1

        r = _connect_redis()

    log(f"Done: {completed} ok, {failed} failed, {completed+failed} total")


if __name__ == "__main__":
    main()
