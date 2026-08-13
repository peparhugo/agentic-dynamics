"""Monitor experiment progress — watch Redis queue and worker status.

Usage:
    python scripts/monitor.py             # One-shot summary
    python scripts/monitor.py --watch     # Live updating (Ctrl+C to exit)
    python scripts/monitor.py --json      # One-shot summary as JSON
    python scripts/monitor.py --clear     # Clear all experiment data from Redis
"""

import json
import os
import sys
import time
from collections import Counter

import redis

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))
QUEUE_KEY = "story_jobs"
STATUS_KEY = "story_status"
RESULTS_KEY = "story_results"

# Cell ids are "<model>_<story>_<tier>_<quality>_<condition>". Underscores also
# appear inside several of those components, so split by known values instead
# of naively splitting on "_".
KNOWN_STORIES = ("task_manager_api", "static_site_gen", "notification_service")
KNOWN_TIERS = ("tier1_minimal", "tier2_small")
KNOWN_CONDITIONS = ("early_degrade", "bad_seed", "clean")


def _parse_cell_id(cell_id: str) -> tuple[str, str, str, str]:
    """Split a cell id into (model, story, tier, condition)."""
    story = next((s for s in KNOWN_STORIES if s in cell_id), "")
    tier = next((t for t in KNOWN_TIERS if t in cell_id), "")
    condition = next((c for c in KNOWN_CONDITIONS if cell_id.endswith(c)), "")
    model = cell_id.split(story, 1)[0].rstrip("_") if story else ""
    return model, story, tier, condition


def get_status(r: redis.Redis) -> dict:
    """Get current experiment status from Redis."""
    remaining = r.llen(QUEUE_KEY)
    all_statuses = r.hgetall(STATUS_KEY)
    results = r.hgetall(RESULTS_KEY)

    counts = Counter(all_statuses.values())
    total = len(all_statuses)

    # Count by model, story, tier, condition
    by_model = Counter()
    by_story = Counter()
    by_condition = Counter()
    by_tier = Counter()

    for cell_id in all_statuses:
        model, story, tier, condition = _parse_cell_id(cell_id)
        by_model[model] += 1
        by_story[story] += 1
        by_tier[tier] += 1
        by_condition[condition] += 1

    return {
        "total": total,
        "remaining_in_queue": remaining,
        "queued": counts.get("queued", 0),
        "running": counts.get("running", 0),
        "done": counts.get("done", 0),
        "failed": counts.get("failed", 0),
        "timeout": counts.get("timeout", 0),
        "completed": counts.get("done", 0) + counts.get("failed", 0) + counts.get("timeout", 0),
        "results_saved": len(results),
        "by_model": dict(by_model),
        "by_story": dict(by_story),
        "by_condition": dict(by_condition),
        "by_tier": dict(by_tier),
    }


def print_status(status: dict, clear_screen: bool = True) -> None:
    """Print a formatted status summary."""
    if clear_screen:
        print("\033[2J\033[H", end="")  # Clear screen

    total = status["total"]
    done = status["done"]
    failed = status["failed"]
    timeout = status["timeout"]
    completed = status["completed"]
    remaining = total - completed

    bar_width = 40
    done_width = int(bar_width * completed / total) if total > 0 else 0
    bar = "█" * done_width + "░" * (bar_width - done_width)

    print(f"  AI FinOps Dynamics — Experiment Monitor")
    print(f"  {'='*50}")
    print(f"  Progress: [{bar}] {completed}/{total} ({100*completed//total if total else 0}%)")
    print(f"  Done: {done}  |  Failed: {failed}  |  Timeout: {timeout}")
    print(f"  Running: {status['running']}  |  Queued: {status['remaining_in_queue']}")
    print(f"  Results saved: {status['results_saved']}")
    print()

    if status.get("by_model"):
        print(f"  By model: {status['by_model']}")
    if status.get("by_story"):
        print(f"  By story: {status['by_story']}")
    if status.get("by_condition"):
        print(f"  By condition: {status['by_condition']}")


def main() -> None:
    watch = "--watch" in sys.argv
    clear = "--clear" in sys.argv
    json_out = "--json" in sys.argv

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

    if clear:
        r.delete(QUEUE_KEY)
        r.delete(STATUS_KEY)
        r.delete(RESULTS_KEY)
        print("Queue cleared.")
        return

    status = get_status(r)
    if json_out:
        print(json.dumps(status))
        return

    if watch:
        try:
            while True:
                print_status(get_status(r))
                time.sleep(5)
        except KeyboardInterrupt:
            print("\nMonitor stopped.")
    else:
        print_status(status, clear_screen=False)


if __name__ == "__main__":
    main()
