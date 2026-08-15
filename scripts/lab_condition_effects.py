"""
Lab Book: Condition Effects — does perturbing the seed change the whole arc?

Compares clean vs bad_seed vs early_degrade across the story corpus:
success rate, cost, cascade recovery, and reviewer "worse" rate.

Usage:
    python scripts/lab_condition_effects.py

Output:
    experiments/results/lab_condition_effects.json
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

RESULTS_DIR = Path("experiments/results/stories")
REVIEWS_DIR = Path("experiments/results/reviews")


def _short_model(model: str) -> str:
    return model.split("/")[-1]


def _worse_rate(story_id: str) -> tuple[int, int]:
    """Return (worse, total) commit-review outcomes for a story."""
    worse = total = 0
    for f in REVIEWS_DIR.glob("*.json"):
        try:
            r = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        # reviews keyed by commit; tie back via session_number is unreliable,
        # so only count reviews that embed a story id when present.
        sid = r.get("story_id", "")
        if sid and sid != story_id:
            continue
        if True:
            total += 1
            if r.get("better_or_worse") == "worse":
                worse += 1
    return worse, total


def main():
    by_condition = defaultdict(lambda: {"cells": 0, "cost": [], "success": 0,
                                        "cascade": 0, "worse": 0, "reviewed": 0})

    for f in sorted(RESULTS_DIR.glob("*.json")):
        if "log" in f.name or "dvs" in f.name:
            continue
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if "model" not in d:
            continue
        cond = d.get("perturbation_condition", "") or "clean"
        summary = d.get("summary", {}) or {}
        cost = summary.get("total_cost", 0) or 0
        b = by_condition[cond]
        b["cells"] += 1
        b["cost"].append(cost)
        if summary.get("all_successful"):
            b["success"] += 1
        if summary.get("cascade_recovery"):
            b["cascade"] += 1

    conditions = []
    for cond, b in by_condition.items():
        n = b["cells"]
        conditions.append({
            "condition": cond,
            "cells": n,
            "success_rate": round(b["success"] / n, 3) if n else 0,
            "cascade_rate": round(b["cascade"] / n, 3) if n else 0,
            "avg_cost": round(sum(b["cost"]) / n, 4) if n else 0,
            "total_cost": round(sum(b["cost"]), 4),
        })
    conditions.sort(key=lambda x: x["condition"])

    output = {
        "experiment_id": "lab_condition_effects",
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "conditions": len(conditions),
        },
        "conditions": conditions,
    }

    out = Path("experiments/results/lab_condition_effects.json")
    out.write_text(json.dumps(output, indent=2))
    print(f"Saved: {out}")
    for c in conditions:
        print(f"  {c['condition']:15s} cells={c['cells']:3d} success={c['success_rate']:.0%} "
              f"cascade={c['cascade_rate']:.0%} avg_cost=${c['avg_cost']:.4f}")


if __name__ == "__main__":
    main()
