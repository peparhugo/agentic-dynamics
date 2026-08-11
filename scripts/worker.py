"""Experiment worker — pop cell from Redis, run 5-session story, save result.

Designed to run in parallel on the same host. Each worker uses Redis BRPOP
for atomic job distribution. Logs to stdout (redirect to file with nohup).
"""

import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import redis

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6379"))
QUEUE_KEY = "story_jobs"
STATUS_KEY = "story_status"
WORKER_PREFIX = "worker"

TIMEOUT_PER_CELL = 7200
BLOCK_TIMEOUT = 10
IDLE_POLLS_BEFORE_EXIT = 12  # 12 × 10s = 2 minutes idle → exit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][{WORKER_PREFIX}] {msg}", flush=True)


def main() -> None:
    log(f"Started (pid={os.getpid()})")

    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()
    except Exception as e:
        log(f"FATAL: Cannot connect to Redis at {REDIS_HOST}:{REDIS_PORT}: {e}")
        sys.exit(1)

    log("Redis connected")

    completed = 0
    failed = 0
    empty_polls = 0

    while True:
        try:
            result = r.brpop(QUEUE_KEY, timeout=BLOCK_TIMEOUT)
        except Exception as e:
            log(f"Redis error: {e}, retrying in 10s")
            time.sleep(10)
            continue

        if result is None:
            empty_polls += 1
            if empty_polls >= IDLE_POLLS_BEFORE_EXIT:
                remaining = r.llen(QUEUE_KEY)
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
            log(f"Invalid job JSON, skipping")
            continue

        cell_id = cell["cell_id"]
        r.hset(STATUS_KEY, cell_id, "running")
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
            )

            elapsed = time.monotonic() - t0

            # Save log
            log_dir = Path("experiments/results/stories/logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{cell_id}.log"
            log_file.write_text(proc.stdout)

            ok = proc.returncode == 0 and "ERROR" not in proc.stdout
            if ok:
                log(f"[{cell_id}] OK ({elapsed:.0f}s)")
                r.hset(STATUS_KEY, cell_id, "done")
                completed += 1
            else:
                log(f"[{cell_id}] FAILED ret={proc.returncode} ({elapsed:.0f}s)")
                r.hset(STATUS_KEY, cell_id, "failed")
                error_log = log_dir / f"{cell_id}.error.log"
                error_log.write_text(proc.stderr or proc.stdout)
                failed += 1

        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - t0
            log(f"[{cell_id}] TIMEOUT ({elapsed:.0f}s)")
            r.hset(STATUS_KEY, cell_id, "timeout")
            failed += 1

        except Exception as e:
            log(f"[{cell_id}] EXCEPTION: {e}")
            r.hset(STATUS_KEY, cell_id, "failed")
            failed += 1

    log(f"Done: {completed} ok, {failed} failed, {completed+failed} total")


if __name__ == "__main__":
    main()
