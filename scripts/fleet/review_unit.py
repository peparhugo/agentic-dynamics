#!/usr/bin/env python3
"""The review-unit daemon — the cell-tier review runner (proposal §7 slice 1, D-10).

The review flow is AUTOMATIC since 2026-08-31: a completed analysis LPUSHes a trigger
onto ``fleet:review_trigger`` (db1 / 6380) — this daemon BRPOPs that trigger and runs
``review_all.py --only-missing`` (the ThreadPoolExecutor review runner, measured
manifests — no LLM) for each trigger, forever. The split is the D-10 sequenced cut-over:
the supervisor never runs ``review_all`` itself, so there is exactly ONE review runner —
no double-review window. ``restart: always`` in the compose keeps the daemon up.

The supervisor holds no docker socket (D-3/D-14), so the trigger is Redis-mediated, the
same channel pattern as ``fleet:commands`` (D-14). This script is dependency-light (redis
only) and runs inside the ``fleet/base`` image as the ``review-unit`` service.

Exit codes: 0 = the daemon was asked to stop cleanly; non-zero = fatal launch error.
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
REVIEW_TRIGGER_KEY = "fleet:review_trigger"

# How long the daemon waits for the next trigger. A socket read timeout mid-wait
# reconnects and re-arms (never dies — the unit is the exactly-one review runner).
BRPOP_TIMEOUT = 600


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


def _run_reviews(raw: str) -> int:
    print(f"[review-unit] got trigger {raw} — running review_all.py --only-missing ...",
          flush=True)
    # P0-3 (control-plane stabilization): a FRESH CLI-state namespace per review run —
    # <state_root>/jobs/review-<ts>/, XDG_* pointed into it. The review daemon must never
    # share a writable opencode/claude state directory across runs (session IDs, SQLite/WAL).
    state_root = Path(os.environ.get("FINOPS_OPENCODE_STATE_ROOT", "/state"))
    job_state = state_root / "jobs" / f"review-{int(time.time())}"
    job_state.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(
        {
            "XDG_DATA_HOME": str(job_state / "data"),
            "XDG_CONFIG_HOME": str(job_state / "config"),
            "XDG_CACHE_HOME": str(job_state / "cache"),
            "FINOPS_OPENCODE_STATE_DIR": str(job_state / "data"),
        }
    )
    try:
        proc = subprocess.run(
            [sys.executable, "scripts/review_all.py", "--only-missing"],
            check=False,
            env=env,
        )
    except OSError as exc:
        print(f"[review-unit] failed to launch review_all.py: {exc}", flush=True)
        return 2
    print(f"[review-unit] review_all.py exited {proc.returncode}.", flush=True)
    return 0


def main() -> int:
    client = _connect()
    print(f"[review-unit] daemon up — watching {REVIEW_TRIGGER_KEY} ...", flush=True)

    while True:
        try:
            result = client.brpop(REVIEW_TRIGGER_KEY, timeout=BRPOP_TIMEOUT)
        except redis.RedisError as exc:
            # A long BRPOP can die on a socket read timeout mid-wait — reconnect
            # and re-arm, never die (the unit is the exactly-one review runner).
            print(f"[review-unit] trigger read error ({exc}); reconnecting ...",
                  flush=True)
            client = _connect()
            continue
        if result is None:
            continue  # timeout with no trigger — the daemon stays up for the next one
        _key, raw = result
        _run_reviews(raw)


if __name__ == "__main__":
    raise SystemExit(main())
