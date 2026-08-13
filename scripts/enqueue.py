"""Enqueue experiment cells into Redis for parallel execution.

Usage:
    python scripts/enqueue.py                      # Fill queue with all cells (DeepSeek)
    python scripts/enqueue.py --model anthropic/claude-sonnet-4-5   # Claude cells
    python scripts/enqueue.py --missing-only       # Skip cells that already have a result
    python scripts/enqueue.py --dry-run            # Print the plan without enqueueing
    python scripts/enqueue.py --clear              # Clear the queue (reset)

Model is read from FINOPS_MODEL env var or --model flag.

Cell ids are namespaced by model slug (``<slug>_<story>_<tier>_<quality>_<condition>``)
so multiple models can share a queue without colliding on ``story_status`` fields
or worker log filenames. ``--missing-only`` skips cells whose result JSON already
exists under ``experiments/results/stories/`` for the target model.
"""

import json
import os
import sys
from pathlib import Path
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
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))
QUEUE_KEY = "story_jobs"
STATUS_KEY = "story_status"       # Redis hash: cell_id -> status
RESULTS_KEY = "story_results"     # Redis hash: cell_id -> result path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "experiments" / "results" / "stories"


def model_slug(model: str) -> str:
    """Derive a short, queue-safe slug from a ``provider/model`` id."""
    base = model.split("/", 1)[-1]
    slug = base.replace("-", "_").replace(".", "_").replace(" ", "_")
    return slug or "model"


def completed_cells(model: str) -> set[str]:
    """Return ``story|tier|quality|condition`` keys already saved for ``model``."""
    completed: set[str] = set()
    if not RESULTS_DIR.is_dir():
        return completed
    for f in RESULTS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("model") != model:
            continue
        story = data.get("story_name")
        if not story:
            continue
        condition = data.get("perturbation_condition") or ""
        if not condition:
            for cond in ("bad_seed", "early_degrade", "clean"):
                if cond in f.name:
                    condition = cond
                    break
        parts = (data.get("codebase_path") or "").split("/")
        tier = parts[-2] if len(parts) >= 2 else "?"
        quality = parts[-1] if len(parts) >= 1 else "?"
        completed.add(f"{story}|{tier}|{quality}|{condition}")
    return completed


def build_cells(model: str = MODEL, missing_only: bool = False) -> list[dict[str, Any]]:
    """Build the full experiment matrix, optionally skipping completed cells."""
    done = completed_cells(model) if missing_only else set()
    slug = model_slug(model)

    cells = []
    for story in STORIES:
        for tier in TIERS:
            for quality in ["good", "bad"]:
                conds = GOOD_CONDITIONS if quality == "good" else BAD_CONDITIONS
                for condition in conds:
                    if f"{story}|{tier}|{quality}|{condition}" in done:
                        continue
                    cells.append({
                        "cell_id": f"{slug}_{story}_{tier}_{quality}_{condition}",
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
    missing_only = "--missing-only" in sys.argv
    model = MODEL
    if "--model" in sys.argv:
        idx = sys.argv.index("--model")
        if idx + 1 < len(sys.argv):
            model = sys.argv[idx + 1]

    cells = build_cells(model=model, missing_only=missing_only)
    total = len(cells)

    if dry_run:
        mode = " (missing-only)" if missing_only else ""
        print(f"Would enqueue {total} cells (model={model}){mode}:")
        for i, cell in enumerate(cells):
            print(f"  [{i+1}/{total}] {cell['cell_id']}")
        return

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

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

    print(f"Enqueued {total} cells into '{QUEUE_KEY}' (model={model})")
    print(f"Status tracker: '{STATUS_KEY}'")
    print()
    print("Start workers with:")
    print("  python scripts/worker.py &")
    print("Monitor progress with:")
    print("  python scripts/monitor.py --watch")


if __name__ == "__main__":
    main()
