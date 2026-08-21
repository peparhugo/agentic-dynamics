"""
Lab Book: Verification Value — does writing more tests predict reviewer outcomes?

Joins per-story test counts to the second-model commit reviews and asks: do
high-test stories produce fewer "worse" commits and more "better" commits?

CANONICAL INPUT (semantic-integrity release, phase s2): publication-eligible, so both
sides of the join come from the registry resolver — current ``story`` rows and current
``review`` rows. The resolver stamps ``_story_id`` on each review from its registry row,
which replaces the old "scan every review_*.json and guess from the filename" join. The
output embeds a ``lab_contract`` block that ``build_data.py`` re-validates.

Usage:
    python scripts/lab_verification_value.py

Output:
    experiments/results/lab_verification_value.json
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


from agentic_dynamics.reporting.canonical_corpus import load_canonical_tables
from agentic_dynamics.reporting.lab_contract import attach_contract

#: This script's name, as classified in scripts/lab_manifest.json — the contract key.
LAB = "lab_verification_value.py"
OUTPUT_PATH = Path("experiments/results/lab_verification_value.json")


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


def compute(story_payloads: list[dict], reviews: list[dict]) -> dict:
    """Join test thoroughness to reviewer outcomes over the canonical corpus.

    Split out of :func:`main` so the analysis is testable without touching the registry.
    """
    # story_id -> (model, test_count), from the current story rows only.
    stories = {}
    for d in story_payloads:
        sid = str(d.get("story_id") or "")
        if len(sid) >= 8:
            stories[sid] = (_short_model(d.get("model", "?")), _test_count(d))

    # Buckets of test thoroughness -> worse/better outcomes.
    buckets = defaultdict(lambda: {"better": 0, "worse": 0, "neutral": 0, "n": 0})
    by_model = defaultdict(lambda: {"better": 0, "worse": 0, "neutral": 0, "tests": []})

    for d in reviews:
        # `_story_id` comes from the review's registry row — an exact join, not a
        # filename heuristic.
        sid = str(d.get("_story_id") or d.get("story_id") or "")
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
        rows.append(
            {
                "model": model,
                "tests": tests,
                "reviews": b["n"],
                "better_rate": round(b["better"] / total, 3),
                "worse_rate": round(b["worse"] / total, 3),
            }
        )
    rows.sort(key=lambda x: (x["model"], x["tests"]))

    # Correlation: tests vs worse_rate across all story-cells with >=3 reviews.
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

    return {
        "experiment_id": "lab_verification_value",
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "correlation_tests_vs_worse_rate": corr,
            "cells": len(rows),
            "stories": len(story_payloads),
            "reviews": len(reviews),
        },
        "rows": rows,
    }


def main():
    tables = load_canonical_tables("story", "review")
    output = compute(tables.stories, tables.reviews)
    # Record scope (public-truth review P1): the metric consumes every current story and
    # every current review (both sides of the join) — declared explicitly, not via a
    # permissive default.
    attach_contract(
        output,
        LAB,
        tables,
        n_eligible_records=len(tables.stories) + len(tables.reviews),
        n_used_records=len(tables.stories) + len(tables.reviews),
    )

    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"Saved: {OUTPUT_PATH}")
    print(
        f"  canonical input: {len(tables.stories)} stories + {len(tables.reviews)} reviews "
        f"({tables.identity.registry_version})"
    )
    for r in output["rows"][:40]:
        print(
            f"  {r['model']:20s} tests={r['tests']:4d} reviews={r['reviews']:3d} "
            f"better={r['better_rate']:.0%} worse={r['worse_rate']:.0%}"
        )
    print(
        f"correlation(tests, worse_rate) = {output['summary']['correlation_tests_vs_worse_rate']}"
    )


if __name__ == "__main__":
    main()
