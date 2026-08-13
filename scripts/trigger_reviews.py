"""trigger_reviews.py — Wait for analysis to drain, then enqueue + spawn review workers.

Async handoff between the post-hoc phases, driven by the Redis queue (6380):
  1. Poll ``analysis_jobs`` + ``analysis_status`` until every story is done/failed.
  2. Run ``enqueue_reviews.py`` (populates ``review_jobs``).
  3. Spawn N ``review_worker.py`` processes (detached).

Usage:
    python3 scripts/trigger_reviews.py            # default 4 review workers
    REVIEW_WORKERS=6 python3 scripts/trigger_reviews.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import redis

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))
ANALYSIS_QUEUE = "analysis_jobs"
ANALYSIS_STATUS = "analysis_status"
REVIEW_WORKERS = int(os.environ.get("REVIEW_WORKERS", "4"))
POLL_SECONDS = 20

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "experiments" / "results" / "stories" / "logs"


def _r() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)


def _analysis_done(r: redis.Redis) -> bool:
    if r.llen(ANALYSIS_QUEUE) > 0:
        return False
    active = {v for v in r.hgetall(ANALYSIS_STATUS).values() if v in ("queued", "running")}
    return len(active) == 0


def main() -> None:
    r = _r()
    print("Waiting for analysis queue to drain...", flush=True)

    while True:
        try:
            if _analysis_done(r):
                break
            queued = r.llen(ANALYSIS_QUEUE)
            running = sum(1 for v in r.hgetall(ANALYSIS_STATUS).values() if v == "running")
            print(f"  ... {queued} queued, {running} running", flush=True)
        except Exception:
            r = _r()
        time.sleep(POLL_SECONDS)

    print("Analysis complete. Enqueuing reviews...", flush=True)
    subprocess.run([sys.executable, "scripts/enqueue_reviews.py"], check=True)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Spawning {REVIEW_WORKERS} review workers...", flush=True)
    for i in range(REVIEW_WORKERS):
        log_path = LOG_DIR / f"review_worker_{i}.log"
        subprocess.Popen(
            ["nohup", sys.executable, "-u", "scripts/review_worker.py"],
            stdout=open(log_path, "w"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    print("Done — review workers running against 'review_jobs'.", flush=True)


if __name__ == "__main__":
    main()
