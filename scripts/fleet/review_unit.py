#!/usr/bin/env python3
"""The review-unit wrapper — the cell-tier review runner (proposal §7 slice 1, D-10).

The supervisor-tier ``trigger-reviews`` polls analysis, enqueues reviews, then LPUSHes a
trigger onto ``fleet:review_trigger`` (db1 / 6380). This unit BRPOPs that trigger and runs
``review_all.py`` (the ThreadPoolExecutor review runner) exactly once. The split is the D-10
sequenced cut-over: the supervisor never runs ``review_all`` itself, so there is exactly ONE
review runner — no double-review window.

The supervisor holds no docker socket (D-3/D-14), so the trigger is Redis-mediated, the same
channel pattern as ``fleet:commands`` (D-14). This script is dependency-light (redis only) and
runs inside the ``fleet/base`` image as the ``review-unit`` service.

Exit codes: 0 = trigger received and ``review_all`` ran (any exit), or a clean timeout with no
trigger; non-zero = the ``review_all`` subprocess failed to launch.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

import redis

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))
REVIEW_TRIGGER_KEY = "fleet:review_trigger"

# How long the unit waits for the supervisor's trigger before giving up. A clean timeout is
# NOT an error (the cut-over may bring this unit up before the trigger fires, or the trigger
# may never fire); the operator re-runs the service for the next review cycle.
BRPOP_TIMEOUT = 3600


def _connect() -> redis.Redis:
    """Connect to the framework Redis (db1 / 6380), retrying with backoff like the workers."""
    delay = 2.0
    while True:
        try:
            client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
                decode_responses=True, socket_connect_timeout=5,
            )
            client.ping()
            return client
        except Exception as exc:  # noqa: BLE001 — the unit must survive a Redis blip
            print(f"[review-unit] redis unavailable ({exc}); retrying in {delay:.0f}s",
                  flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 30.0)


def main() -> int:
    client = _connect()
    print(f"[review-unit] waiting for trigger on {REVIEW_TRIGGER_KEY} "
          f"(timeout {BRPOP_TIMEOUT}s) ...", flush=True)

    while True:
        try:
            result = client.brpop(REVIEW_TRIGGER_KEY, timeout=BRPOP_TIMEOUT)
            break
        except redis.RedisError as exc:
            # A long BRPOP can die on a socket read timeout mid-wait — reconnect
            # and re-arm, never die (the unit is the exactly-one review runner).
            print(f"[review-unit] trigger read error ({exc}); reconnecting ...",
                  flush=True)
            client = _connect()
    if result is None:
        print("[review-unit] no trigger within timeout — exiting (nothing to review).",
              flush=True)
        return 0

    _key, raw = result
    print(f"[review-unit] got trigger {raw} — running review_all.py --only-missing ...",
          flush=True)
    try:
        proc = subprocess.run(
            [sys.executable, "scripts/review_all.py", "--only-missing"],
            check=False,
        )
    except OSError as exc:
        print(f"[review-unit] failed to launch review_all.py: {exc}", flush=True)
        return 2

    print(f"[review-unit] review_all.py exited {proc.returncode}.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
