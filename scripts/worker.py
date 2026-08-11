"""Experiment worker — pop cell from Redis, run 5-session story, save result.

Usage:
    python scripts/worker.py              # Single worker (foreground)
    python scripts/worker.py &            # Background worker

Workers are designed to run in parallel on the same host. Each worker:
    1. BRPOPs a cell from Redis (atomic — no two workers get the same cell)
    2. Runs run_story.py with the cell's parameters
    3. Saves the result path to Redis
    4. Updates cell status to "done" or "failed"
    5. Loops until queue is empty

Multiple workers:
    python scripts/worker.py &
    python scripts/worker.py &
    python scripts/worker.py &
    python scripts/worker.py &
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import redis

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6379"))
QUEUE_KEY = "story_jobs"
STATUS_KEY = "story_status"
RESULTS_KEY = "story_results"

TIMEOUT_PER_CELL = 7200   # 2 hours
BLOCK_TIMEOUT = 5          # seconds to wait for BRPOP
IDLE_AFTER_EMPTY = 60      # seconds to wait before checking for more jobs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def main() -> None:
    worker_id = os.getpid()
    print(f"[worker {worker_id}] Started")

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    completed = 0
    failed = 0
    empty_polls = 0

    while True:
        # BRPOP: block until a job is available or timeout
        result = r.brpop(QUEUE_KEY, timeout=BLOCK_TIMEOUT)

        if result is None:
            empty_polls += 1
            if empty_polls >= int(IDLE_AFTER_EMPTY / BLOCK_TIMEOUT):
                # Check if there are actually no more jobs
                remaining = r.llen(QUEUE_KEY)
                pending = len([k for k, v in r.hgetall(STATUS_KEY).items() if v in ("queued", "running")])
                if remaining == 0 and pending == 0:
                    print(f"[worker {worker_id}] Queue empty, no pending jobs. Exiting.")
                    break
                empty_polls = 0
            continue

        empty_polls = 0
        _, job_json = result

        try:
            cell = json.loads(job_json)
        except json.JSONDecodeError:
            print(f"[worker {worker_id}] Invalid job JSON, skipping")
            continue

        cell_id = cell["cell_id"]
        r.hset(STATUS_KEY, cell_id, "running")
        print(f"[worker {worker_id}] [{cell_id}] Starting...")

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

            # Log output
            log_dir = Path("experiments/results/stories/logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{cell_id}.log"
            log_file.write_text(proc.stdout)

            if proc.returncode == 0 and "ERROR" not in proc.stdout:
                print(f"[worker {worker_id}] [{cell_id}] OK ({elapsed:.0f}s)")
                r.hset(STATUS_KEY, cell_id, "done")
                completed += 1
            else:
                print(f"[worker {worker_id}] [{cell_id}] FAILED ({elapsed:.0f}s)")
                r.hset(STATUS_KEY, cell_id, "failed")
                failed += 1
                # Log error details
                error_log = log_dir / f"{cell_id}.error.log"
                error_log.write_text(proc.stderr or proc.stdout)

        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - t0
            print(f"[worker {worker_id}] [{cell_id}] TIMEOUT ({elapsed:.0f}s)")
            r.hset(STATUS_KEY, cell_id, "timeout")
            failed += 1

    print(f"[worker {worker_id}] Done: {completed} ok, {failed} failed")


if __name__ == "__main__":
    main()
