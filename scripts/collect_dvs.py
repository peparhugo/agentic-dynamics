"""DVS result collector — compile Redis results into dvs_summary.json.

Usage:
    python scripts/collect_dvs.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import redis

REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
STATUS_KEY = "dvs_status"
RESULTS_KEY = "dvs_results"


def main() -> None:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    all_results = r.hgetall(RESULTS_KEY)
    if not all_results:
        print("No DVS results in Redis. Run workers first.")
        return

    cells = []
    for key, val in all_results.items():
        try:
            cells.append(json.loads(val))
        except json.JSONDecodeError:
            continue

    # Group by condition and story
    by_condition = {}
    by_story = {}
    for c in cells:
        cond = c.get("condition", "clean")
        story = c.get("story", "unknown")

        # By condition
        if cond not in by_condition:
            by_condition[cond] = {"count": 0, "dvs_total": 0, "cost_total": 0, "success": 0}
        by_condition[cond]["count"] += 1
        by_condition[cond]["dvs_total"] += c["dvs"]["score"]
        by_condition[cond]["cost_total"] += c["total_cost"]
        if c["all_successful"]: by_condition[cond]["success"] += 1

        # By story
        if story not in by_story:
            by_story[story] = {"count": 0, "dvs_total": 0, "cost_total": 0, "success": 0}
        by_story[story]["count"] += 1
        by_story[story]["dvs_total"] += c["dvs"]["score"]
        by_story[story]["cost_total"] += c["total_cost"]
        if c["all_successful"]: by_story[story]["success"] += 1

    # Build summary with averages
    cond_summary = {}
    for cond, data in by_condition.items():
        n = data["count"]
        cond_summary[cond] = {
            "count": n,
            "avg_dvs": round(data["dvs_total"] / n, 4) if n else 0,
            "avg_cost": round(data["cost_total"] / n, 6) if n else 0,
            "success_rate": round(data["success"] / n, 2) if n else 0,
        }

    story_summary = {}
    for story, data in by_story.items():
        n = data["count"]
        story_summary[story] = {
            "count": n,
            "avg_dvs": round(data["dvs_total"] / n, 4) if n else 0,
            "avg_cost": round(data["cost_total"] / n, 6) if n else 0,
            "success_rate": round(data["success"] / n, 2) if n else 0,
        }

    summary = {
        "generated_at": datetime.now().isoformat(),
        "total_cells": len(cells),
        "by_condition": cond_summary,
        "by_story": story_summary,
        "cells": cells,
    }

    out = Path("experiments/results/stories/dvs_summary.json")
    out.write_text(json.dumps(summary, indent=2))
    print(f"Saved: {out}")
    print(f"  {len(cells)} cells")

    for cond, data in cond_summary.items():
        print(f"  {cond:15s}: DVS={data['avg_dvs']:.3f}, {data['count']} cells, {data['success_rate']:.0%} success, \${data['avg_cost']:.4f} avg")


if __name__ == "__main__":
    main()
