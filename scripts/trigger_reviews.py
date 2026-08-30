"""trigger_reviews.py — Wait for analysis to drain, then enqueue + spawn review workers.

Async handoff between the post-hoc phases, driven by the Redis queue (6380):
  1. Poll ``analysis_jobs`` + ``analysis_status`` until every story is done/failed.
  2. Run ``enqueue_reviews.py`` (populates ``review_jobs``).
  3. Run ``review_all.py`` (synchronous — replaces the retired Redis review worker).

Two modes (the slice-1 review cut-over, D-10):

    * default (host legacy) — enqueue + run ``review_all.py`` synchronously in-process, the
      exact shape the ad-hoc host process used (preserved for the rollback path).
    * ``--trigger-only`` (container supervisor) — enqueue, then LPUSH a trigger onto
      ``fleet:review_trigger`` and exit. The cell-tier ``review-unit`` container BRPOPs that
      trigger and runs ``review_all.py``. This keeps the supervisor from running ``review_all``
      itself, so there is exactly ONE review runner — no double-review window.

Usage:
    python3 scripts/trigger_reviews.py            # default (host): enqueue + review_all
    python3 scripts/trigger_reviews.py --trigger-only   # supervisor: enqueue + signal review-unit
    REVIEW_WORKERS=6 python3 scripts/trigger_reviews.py
"""

from __future__ import annotations

import json
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

# The supervisor -> review-unit trigger channel (db1 / 6380). Mirrors the fleet:commands
# pattern (D-14): the supervisor only ever LPUSHes a bounded command; the cell-tier unit
# BRPOPs it. The review-unit is the ONLY consumer.
REVIEW_TRIGGER_KEY = "fleet:review_trigger"

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
    trigger_only = "--trigger-only" in sys.argv
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

    if trigger_only:
        # Supervisor mode (D-10): signal the cell-tier review-unit and exit — never run
        # review_all here. The review-unit is the single review runner.
        cmd = {"action": "review", "ts": time.time()}
        r.lpush(REVIEW_TRIGGER_KEY, json.dumps(cmd))
        print(f"Signalled review-unit via {REVIEW_TRIGGER_KEY} "
              f"(len={r.llen(REVIEW_TRIGGER_KEY)}).", flush=True)
        return

    # review_all.py is the synchronous review runner (ThreadPoolExecutor, no Redis) — it
    # replaces the retired Redis review worker (WS-09). Run it to completion.
    print("Running review_all.py (synchronous)...", flush=True)
    subprocess.run([sys.executable, "scripts/review_all.py"], check=False)
    print("Done — reviews written by review_all.py.", flush=True)


if __name__ == "__main__":
    main()
