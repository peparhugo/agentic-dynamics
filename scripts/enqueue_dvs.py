"""Enqueue story results for parallel DVS analysis.

Usage:
    python scripts/enqueue_dvs.py
"""

import json
import sys
from pathlib import Path

import redis

REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
QUEUE_KEY = "dvs_jobs"
STATUS_KEY = "dvs_status"
RESULTS_KEY = "dvs_results"


def main() -> None:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    if "--clear" in sys.argv:
        r.delete(QUEUE_KEY)
        r.delete(STATUS_KEY)
        r.delete(RESULTS_KEY)
        print("DVS queue cleared.")
        return

    results_dir = Path("experiments/results/stories")
    result_files = sorted(results_dir.glob("*.json"))
    result_files = [f for f in result_files if "log" not in f.name and "dvs" not in f.name]

    count = 0
    for rf in result_files:
        try:
            d = json.loads(rf.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if "model" not in d:
            continue
        r.lpush(QUEUE_KEY, str(rf))
        r.hset(STATUS_KEY, rf.name, "queued")
        count += 1

    print(f"Enqueued {count} cells for DVS analysis")
    print(f"Start workers: python scripts/worker_dvs.py &")


if __name__ == "__main__":
    main()
