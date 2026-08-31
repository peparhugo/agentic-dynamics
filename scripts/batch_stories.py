"""Batch experiment runner — executes all DeepSeek matrix cells sequentially.

Usage:
    python scripts/batch_stories.py
    python scripts/batch_stories.py --dry-run  # Just print the plan

This is the v0.9 DeepSeek-only pipeline validation:
  3 stories × 2 tiers × 2 qualities × 3/2 conditions = 30 cells × 5 sessions = 150 sessions
"""

import subprocess
import sys
import time
from pathlib import Path

from agentic_dynamics.control.model_policy import SUBSCRIPTION_DEFAULT, ensure_model_allowed

# ── Matrix Definition ──────────────────────────────────────────

STORIES = ["task_manager_api", "static_site_gen", "notification_service"]
TIERS = ["tier1_minimal", "tier2_small"]
MODEL = SUBSCRIPTION_DEFAULT

GOOD_CONDITIONS = ["clean", "bad_seed", "early_degrade"]
BAD_CONDITIONS = ["clean", "early_degrade"]

QUALITIES = {
    "good": {"conditions": GOOD_CONDITIONS, "label": "good"},
    "bad": {"conditions": BAD_CONDITIONS, "label": "bad"},
}


def main():
    ensure_model_allowed(MODEL)
    dry_run = "--dry-run" in sys.argv

    cells = []
    for story in STORIES:
        for tier in TIERS:
            for quality_key, quality in QUALITIES.items():
                for condition in quality["conditions"]:
                    cells.append({
                        "story": story,
                        "tier": tier,
                        "quality": quality_key,
                        "condition": condition,
                    })

    total = len(cells)
    print(f"Batch experiment: {total} cells × 5 sessions = {total * 5} sessions")
    print(f"Model: {MODEL}")
    print(f"{'='*60}")

    if dry_run:
        for i, cell in enumerate(cells):
            print(f"  [{i+1}/{total}] {cell['story']} | {cell['tier']} | {cell['quality']} | {cell['condition']}")
        return

    results_dir = Path("experiments/results/stories")
    results_dir.mkdir(parents=True, exist_ok=True)

    started_at = time.strftime("%Y-%m-%d %H:%M:%S")
    successes = 0
    failures = 0

    for i, cell in enumerate(cells):
        cell_num = i + 1
        print(f"\n{'='*60}")
        print(f"[{cell_num}/{total}] {cell['story']} | {cell['tier']} | "
              f"{cell['quality']} | {cell['condition']}")
        print(f"  Started: {time.strftime('%H:%M:%S')}")

        t0 = time.monotonic()

        result = subprocess.run(
            [
                sys.executable, "scripts/run_story.py",
                cell["story"],
                "--model", MODEL,
                "--tier", cell["tier"],
                "--codebase-quality", cell["quality"],
                "--condition", cell["condition"],
                "--timeout", "900",
            ],
            capture_output=True,
            text=True,
            timeout=7200,  # 2 hour per cell max
        )

        elapsed = time.monotonic() - t0

        if result.returncode == 0 and "ERROR" not in result.stdout:
            print(f"  OK ({elapsed:.0f}s)")
            successes += 1
        else:
            print(f"  FAILED ({elapsed:.0f}s)")
            if result.stderr:
                print(f"  Stderr: {result.stderr[:200]}")
            failures += 1

        # Log output to a file
        log_dir = Path("experiments/results/stories/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{cell['story']}_{cell['quality']}_{cell['condition']}_{cell['tier']}.log"
        log_file.write_text(result.stdout)

        # Brief pause between cells
        if cell_num < total:
            time.sleep(5)

    # Summary
    print(f"\n{'='*60}")
    print(f"Batch complete: {successes} succeeded, {failures} failed, {total} total")
    print(f"Started: {started_at}")
    print(f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
