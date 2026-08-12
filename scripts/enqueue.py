"""Enqueue experiment cells into Redis for parallel execution.

Usage:
    python scripts/enqueue.py                # Fill queue with all cells (DeepSeek)
    python scripts/enqueue.py --model anthropic/claude-sonnet-4-5   # Claude cells
    python scripts/enqueue.py --dry-run      # Print the plan without enqueueing
    python scripts/enqueue.py --clear        # Clear the queue (reset)

Model is read from FINOPS_MODEL env var or --model flag.
"""

import json
import os
import sys
from typing import Any

import redis

# ── Matrix Definition ──────────────────────────────────────────

STORIES = ["task_manager_api", "static_site_gen", "notification_service"]
TIERS = ["tier1_minimal", "tier2_small"]
MODEL = os.environ.get("FINOPS_MODEL", "deepseek/deepseek-v4-pro")

GOOD_CONDITIONS = ["clean", "bad_seed", "early_degrade"]
BAD_CONDITIONS = ["clean", "early_degrade"]

REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
QUEUE_KEY = "story_jobs"
STATUS_KEY = "story_status"       # Redis hash: cell_id -> status
RESULTS_KEY = "story_results"     # Redis hash: cell_id -> result path


def build_cells(model: str = MODEL) -> list[dict[str, Any]]:
    """Build the full experiment matrix."""
    cells = []
    for story in STORIES:
        for tier in TIERS:
            conditions = GOOD_CONDITIONS if True else BAD_CONDITIONS  # expanded below
            for quality in ["good", "bad"]:
                conds = GOOD_CONDITIONS if quality == "good" else BAD_CONDITIONS
                for condition in conds:
                    cell_id = f"{story}_{tier}_{quality}_{condition}"
                    cells.append({
                        "cell_id": cell_id,
                        "story": story,
                        "tier": tier,
                        "quality": quality,
                        "condition": condition,
                        "model": model,
                    })
    return cells


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    clear = "--clear" in sys.argv
    model = MODEL
    if "--model" in sys.argv:
        idx = sys.argv.index("--model")
        if idx + 1 < len(sys.argv):
            model = sys.argv[idx + 1]

    cells = build_cells(model=model)
    total = len(cells)

    if dry_run:
        print(f"Would enqueue {total} cells (model={model}):")
        for i, cell in enumerate(cells):
            print(f"  [{i+1}/{total}] {cell['cell_id']}")
        return

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    if clear:
        r.delete(QUEUE_KEY)
        r.delete(STATUS_KEY)
        r.delete(RESULTS_KEY)
        print("Queue cleared.")
        return

    # Enqueue cells
    for cell in cells:
        r.lpush(QUEUE_KEY, json.dumps(cell))
        r.hset(STATUS_KEY, cell["cell_id"], "queued")

    print(f"Enqueued {total} cells into '{QUEUE_KEY}'")
    print(f"Status tracker: '{STATUS_KEY}'")
    print()
    print("Start workers with:")
    print("  python scripts/worker.py &")
    print("Monitor progress with:")
    print("  python scripts/monitor.py --watch")


if __name__ == "__main__":
    main()
