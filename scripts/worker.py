"""Experiment worker — pop cell from Redis, run 5-session story, save result.

Designed to run in parallel on the same host. Each worker uses Redis BRPOP
for atomic job distribution. Logs to stdout (redirect to file with nohup).

Reliability: retries Redis connections with exponential backoff, recreates
client after long subprocess runs to avoid stale connections.
"""

import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import redis

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6379"))
QUEUE_KEY = "story_jobs"
STATUS_KEY = "story_status"
WORKER_PREFIX = "worker"

TIMEOUT_PER_CELL = 9000
BLOCK_TIMEOUT = 10
IDLE_POLLS_BEFORE_EXIT = 12  # 12 × 10s = 2 minutes idle → exit
REDIS_MAX_RETRIES = 10
REDIS_BASE_DELAY = 2.0  # seconds, doubled each retry

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from instrument.live import LivePublisher  # noqa: E402


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][{WORKER_PREFIX}] {msg}", flush=True)


def _connect_redis() -> redis.Redis:
    """Connect to Redis with exponential backoff. Never exits — retries forever."""
    delay = REDIS_BASE_DELAY
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
            if attempts < REDIS_MAX_RETRIES:
                log(f"  retrying in {delay:.0f}s")
            time.sleep(delay)
            delay = min(delay * 2, 60.0)


def _safe_hset(r: redis.Redis, key: str, field: str, value: str) -> bool:
    """Set a Redis hash field with retry. Returns True on success."""
    for attempt in range(3):
        try:
            r.hset(key, field, value)
            return True
        except Exception as e:
            log(f"Redis hset error (attempt {attempt+1}/3): {e}")
            time.sleep(2 ** attempt)
    return False


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
                    log(f"Queue empty after {empty_polls} polls. Exiting.")
                    break
                empty_polls = 0
            continue

        empty_polls = 0
        _, job_json = result

        try:
            cell = json.loads(job_json)
        except json.JSONDecodeError:
            log("Invalid job JSON, skipping")
            continue

        cell_id = cell["cell_id"]
        _safe_hset(r, STATUS_KEY, cell_id, "running")
        publisher = LivePublisher(cell_id)
        publisher.publish_status("running")
        log(f"[{cell_id}] Starting ({completed+failed+1}/30)")

        t0 = time.monotonic()

        try:
            proc = subprocess.run(
                [
                    sys.executable, "scripts/run_story.py",
                    cell["story"],
                    "--model", cell["model"],
                    "--tier", cell["tier"],
                    "--codebase-quality", cell["quality"],
                    "--condition", cell["condition"],
                    "--timeout", "900",
                ],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_PER_CELL,
                env={**os.environ, "FINOPS_CELL_ID": cell_id},
            )

            elapsed = time.monotonic() - t0

            # Reconnect after a potentially long subprocess — the old
            # connection is almost certainly dead after 15+ minutes.
            r = _connect_redis()

            # Save log
            log_dir = Path("experiments/results/stories/logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{cell_id}.log"
            log_file.write_text(proc.stdout)

            ok = proc.returncode == 0 and "ERROR" not in proc.stdout
            if ok:
                log(f"[{cell_id}] OK ({elapsed:.0f}s)")
                _safe_hset(r, STATUS_KEY, cell_id, "done")
                publisher.publish_status("done")
                completed += 1
            else:
                log(f"[{cell_id}] FAILED ret={proc.returncode} ({elapsed:.0f}s)")
                _safe_hset(r, STATUS_KEY, cell_id, "failed")
                publisher.publish_status("failed")
                error_log = log_dir / f"{cell_id}.error.log"
                error_log.write_text(proc.stderr or proc.stdout)
                failed += 1

        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - t0
            log(f"[{cell_id}] TIMEOUT ({elapsed:.0f}s)")
            r = _connect_redis()
            _safe_hset(r, STATUS_KEY, cell_id, "timeout")
            publisher.publish_status("timeout")
            failed += 1

        except Exception as e:
            log(f"[{cell_id}] EXCEPTION: {e}")
            _safe_hset(r, STATUS_KEY, cell_id, "failed")
            publisher.publish_status("failed")
            failed += 1
            # Reconnect — the exception may have been a Redis error mid-run
            r = _connect_redis()

    log(f"Done: {completed} ok, {failed} failed, {completed+failed} total")


if __name__ == "__main__":
    main()
