"""review_worker.py — Pop review jobs from Redis, run review_commit() with SDK bridge.

Each job: worktree path, commit hash, session number, story metadata.
Runs the review agent (review_commit or review_story) via opencode SDK bridge.

Reliability guarantees:
  - Failed jobs are re-enqueued with a retry counter (no silent job loss).
  - Each commit review is written to its own file (review_{story_id}_S{n}.json),
    eliminating the read-modify-write race when sessions of one story land
    on different workers. A separate finalize_reviews.py merges them.

Usage:
  python3 scripts/review_worker.py     # single worker
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import redis

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


from agentic_dynamics.reporting.review import review_commit, review_story

REDIS_HOST = "127.0.0.1"
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))
QUEUE_KEY = "review_jobs"
STATUS_KEY = "review_status"
REVIEWS_DIR = Path(__file__).resolve().parent.parent / "experiments" / "results" / "reviews"

BLOCK_TIMEOUT = 5
IDLE_POLLS_BEFORE_EXIT = 6
MAX_RETRIES = 3


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][review] {msg}", flush=True)


def _connect_redis() -> redis.Redis:
    delay = 2.0
    attempts = 0
    while True:
        try:
            r = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
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


def _atomic_write(path: Path, data: dict) -> None:
    """Write JSON atomically (temp + rename) to avoid partial files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)


def _write_commit_review(story_id: str, session: int, review_dict: dict) -> None:
    review_dict = dict(review_dict)
    review_dict["session_number"] = session
    path = REVIEWS_DIR / f"review_{story_id}_S{session}.json"
    _atomic_write(path, review_dict)


def _write_story_review(story_id: str, review_dict: dict) -> None:
    path = REVIEWS_DIR / f"review_{story_id}_story.json"
    _atomic_write(path, review_dict)


def _requeue(r: redis.Redis, job: dict, job_id: str, err: str) -> bool:
    """Re-enqueue a failed job. Returns True if re-queued (retry), False if dead."""
    retries = job.get("_retries", 0)
    if retries >= MAX_RETRIES:
        return False
    job["_retries"] = retries + 1
    r.lpush(QUEUE_KEY, json.dumps(job))
    r.hset(STATUS_KEY, job_id, f"retry_{retries + 1}")
    log(f"[{job_id}] FAILED (retry {retries + 1}/{MAX_RETRIES}): {err}")
    return True


def main() -> None:
    log(f"Started (pid={os.getpid()})")

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
                    log("Queue empty. Exiting.")
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
            if _requeue(r, job, job_id, "worktree missing"):
                continue
            r.hset(STATUS_KEY, job_id, "failed")
            failed += 1
            continue

        r.hset(STATUS_KEY, job_id, "running")

        try:
            if job.get("job_type") == "story_review":
                log(f"[{job_id}] Story review: {job['story_name']}")
                review = review_story(worktree, job["story_name"], model=model)
                _write_story_review(story_id, review.to_dict())
            else:
                log(f"[{job_id}] Commit review: S{job['session_number']} {job['story_name']}")
                review = review_commit(
                    worktree, job["commit_hash"],
                    story_name=job["story_name"],
                    session_number=job["session_number"],
                    model=model,
                    story_id=story_id,
                )
                _write_commit_review(story_id, job["session_number"], review.to_dict())

            r.hset(STATUS_KEY, job_id, "done")
            completed += 1
            log(f"[{job_id}] OK")

        except Exception as e:
            if _requeue(r, job, job_id, str(e)):
                continue
            r.hset(STATUS_KEY, job_id, "failed")
            failed += 1
            log(f"[{job_id}] FAILED (permanent): {e}")

        r = _connect_redis()

    log(f"Done: {completed} ok, {failed} failed, {completed+failed} total")


if __name__ == "__main__":
    main()
