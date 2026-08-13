"""
Lab Book: Verification Value — does writing more tests predict reviewer outcomes?

Joins per-story test counts to the second-model commit reviews and asks: do
high-test stories produce fewer "worse" commits and more "better" commits?

Usage:
    python scripts/lab_verification_value.py

Output:
    experiments/results/lab_verification_value.json
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

RESULTS_DIR = Path("experiments/results/stories")
REVIEWS_DIR = Path("experiments/results/reviews")


def _short_model(model: str) -> str:
    return model.split("/")[-1]


def _test_count(d: dict) -> int:
    summary = d.get("summary", {}) or {}
    n = summary.get("test_count", 0) or 0
    if n > 0:
        return int(n)
    peak = 0
    for s in d.get("sessions", []):
        a = s.get("agentic", {}) or {}
        peak = max(peak, a.get("tests_total", 0) or 0)
    return peak


def main():
    # story_id -> (model, test_count)
    stories = {}
    for f in sorted(RESULTS_DIR.glob("*.json")):
        if "log" in f.name or "dvs" in f.name:
            continue
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        sid = d.get("story_id", "") or f.stem.split("_")[-1]
        if len(sid) >= 8:
            stories[sid] = (_short_model(d.get("model", "?")), _test_count(d))

    # Buckets of test thoroughness -> worse/better outcomes.
    buckets = defaultdict(lambda: {"better": 0, "worse": 0, "neutral": 0, "n": 0})
    by_model = defaultdict(lambda: {"better": 0, "worse": 0, "neutral": 0, "tests": []})

    for f in sorted(REVIEWS_DIR.glob("review_*.json")):
        if "_S" in f.stem or f.stem.endswith("_story"):
            continue
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        sid = d.get("story_id", "")
        model, tests = stories.get(sid, ("?", 0))
        for cr in d.get("commit_reviews", []):
            outcome = cr.get("better_or_worse", "?")
            b = buckets[(model, tests)]
            b[outcome] = b.get(outcome, 0) + 1
            b["n"] += 1
            by_model[model][outcome] = by_model[model].get(outcome, 0) + 1
        if sid in stories:
            by_model[model]["tests"].append(tests)

    # Summarize worse-rate as a function of test count (per model).
    rows = []
    for (model, tests), b in sorted(buckets.items()):
        total = b["n"] or 1
        rows.append({
            "model": model,
            "tests": tests,
            "reviews": b["n"],
            "better_rate": round(b["better"] / total, 3),
            "worse_rate": round(b["worse"] / total, 3),
        })
    rows.sort(key=lambda x: (x["model"], x["tests"]))

    # Correlation: tests vs worse_rate across all story-cells with >=3 reviews.
    import statistics
    pts = [(r["tests"], r["worse_rate"]) for r in rows if r["reviews"] >= 3]
    corr = None
    if len(pts) >= 3:
        n = len(pts)
        mx = sum(t for t, _ in pts) / n
        my = sum(w for _, w in pts) / n
        num = sum((t - mx) * (w - my) for t, w in pts)
        dx = sum((t - mx) ** 2 for t, _ in pts) ** 0.5
        dy = sum((w - my) ** 2 for _, w in pts) ** 0.5
        corr = round(num / (dx * dy), 3) if dx and dy else None

    output = {
        "experiment_id": "lab_verification_value",
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "correlation_tests_vs_worse_rate": corr,
            "cells": len(rows),
        },
        "rows": rows,
    }

    out = Path("experiments/results/lab_verification_value.json")
    out.write_text(json.dumps(output, indent=2))
    print(f"Saved: {out}")
    for r in rows[:40]:
        print(f"  {r['model']:20s} tests={r['tests']:4d} reviews={r['reviews']:3d} "
              f"better={r['better_rate']:.0%} worse={r['worse_rate']:.0%}")
    print(f"correlation(tests, worse_rate) = {corr}")


if __name__ == "__main__":
    main()
