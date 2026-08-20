"""Enqueue post-hoc analysis jobs into Redis for parallel execution.

Scans story result JSONs and enqueues one analysis job per story that has no
``experiments/results/analysis/analysis_{story_id}.json`` output yet.

Usage:
    python scripts/enqueue_analysis.py                # enqueue all un-analyzed stories
    python scripts/enqueue_analysis.py --dry-run      # preview
    python scripts/enqueue_analysis.py --clear        # clear the analysis queue

Runs against the isolated framework Redis (FINOPS_REDIS_PORT default 6380).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import redis

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))

ROOT = Path(__file__).resolve().parent.parent
try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


# Job shapes, queue/status keys, and the canonical enqueue path all come from
# the shared module so this backfill tool can't drift from the worker triggers.
from agentic_dynamics.runtime.posthoc import (  # noqa: E402
    ANALYSIS_QUEUE,
    ANALYSIS_STATUS,
    build_analysis_job,
    enqueue_job,
)

RESULTS_DIR = ROOT / "experiments" / "results" / "stories"
ANALYSIS_DIR = ROOT / "experiments" / "results" / "analysis"


def build_jobs(skip_existing: bool = True) -> list[dict]:
    jobs = []
    for f in sorted(RESULTS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        story_id = data.get("story_id")
        if not story_id:
            continue
        if skip_existing and (ANALYSIS_DIR / f"analysis_{story_id}.json").exists():
            continue
        jobs.append(build_analysis_job(story_id, data.get("worktree", ""), f))
    return jobs


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    clear = "--clear" in sys.argv
    skip_existing = "--skip-existing" in sys.argv or True

    jobs = build_jobs(skip_existing=skip_existing)

    if dry_run:
        print(f"Would enqueue {len(jobs)} analysis jobs:")
        for j in jobs[:15]:
            print(f"  {j['story_id']}  {j['worktree']}")
        if len(jobs) > 15:
            print(f"  ... (+{len(jobs) - 15} more)")
        return

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

    if clear:
        r.delete(ANALYSIS_QUEUE, ANALYSIS_STATUS)
        print("Analysis queue cleared.")
        return

    for job in jobs:
        enqueue_job(r, ANALYSIS_QUEUE, ANALYSIS_STATUS, job, job["story_id"])

    print(f"Enqueued {len(jobs)} analysis jobs into '{ANALYSIS_QUEUE}'")
    print("Start workers with:")
    print("  python scripts/analysis_worker.py &")


if __name__ == "__main__":
    main()
