"""
Lab Book: Verification Value — does writing more tests predict reviewer outcomes?

Joins per-story test counts to the second-model commit reviews and asks: do
high-test stories produce fewer "worse" commits and more "better" commits?

CANONICAL INPUT (semantic-integrity release, phase s2): publication-eligible, so both
sides of the join come from the registry resolver — current ``story`` rows and current
``review`` rows. The resolver stamps ``_story_id`` on each review from its registry row,
which replaces the old "scan every review_*.json and guess from the filename" join. The
output embeds a ``lab_contract`` block that ``build_data.py`` re-validates.

MEASUREMENT-CONTRIBUTION CLOSURE (m1, metric v2): the join fails *explicitly* — a review
whose ``_story_id`` names no current, resolved story is excluded and counted as
``review_without_current_story`` (never ``stories.get(sid, ("?", 0))``), and a current
story no review joined is counted as ``story_without_review``. No published row carries a
placeholder ``model: "?"`` identity; the contract's record counts are the joined
populations, not "everything resolved".

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

    The join is **explicit** (measurement-contribution closure, m1): a review whose
    ``_story_id`` names no current, resolved story is excluded and counted as
    ``review_without_current_story`` — never assigned a placeholder ``("?", 0)`` identity.
    A current story that no review joined is counted as ``story_without_review``; it never
    contributes a row (and therefore never a fabricated ``model: "?"`` row).

    Split out of :func:`main` so the analysis is testable without touching the registry.
    """
    # story_id -> (model, test_count), from the current story rows only. A story must
    # carry a real model to be a usable join target — one without is not a measurement
    # record and is dropped from the map (its reviews become `review_without_current_story`).
    stories = {}
    for d in story_payloads:
        sid = str(d.get("story_id") or "")
        model = d.get("model")
        if len(sid) >= 8 and model:
            stories[sid] = (_short_model(model), _test_count(d))

    # Buckets of test thoroughness -> worse/better outcomes. Only joined reviews reach a
    # bucket, so no bucket can ever carry a placeholder model.
    buckets = defaultdict(lambda: {"better": 0, "worse": 0, "neutral": 0, "n": 0})
    review_without_current_story = 0
    joined_story_ids: set[str] = set()

    for d in reviews:
        # `_story_id` comes from the review's registry row — an exact join, not a
        # filename heuristic.
        sid = str(d.get("_story_id") or d.get("story_id") or "")
        entry = stories.get(sid)
        if entry is None:
            # The join failed: this review names a story that is not a current, resolved
            # story (tombstoned or payload-less). Exclude it and count it — never assign
            # it a placeholder identity.
            review_without_current_story += 1
            continue
        model, tests = entry
        joined_story_ids.add(sid)
        for cr in d.get("commit_reviews", []):
            outcome = cr.get("better_or_worse", "?")
            b = buckets[(model, tests)]
            b[outcome] = b.get(outcome, 0) + 1
            b["n"] += 1

    # A current story that no review joined is eligible for the metric but produced no
    # joined observation — counted, not silently folded into a placeholder row.
    story_without_review = len(stories) - len(joined_story_ids)

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
            "review_without_current_story": review_without_current_story,
            "story_without_review": story_without_review,
        },
        "rows": rows,
    }


def main():
    tables = load_canonical_tables("story", "review")
    output = compute(tables.stories, tables.reviews)
    summary = output["summary"]

    # Record scope (measurement-contribution closure, m1): the contract counts are the
    # JOINED populations, not "everything resolved". resolved = stories + reviews;
    # excluded = reviews whose story is not current + stories no review joined; the rest
    # is eligible and all of it is used. Hand-set here because the typed
    # ContributionReport primitive lands in m3.
    n_resolved = len(tables.stories) + len(tables.reviews)
    n_excluded = summary["review_without_current_story"] + summary["story_without_review"]
    n_eligible = n_resolved - n_excluded
    attach_contract(
        output,
        LAB,
        tables,
        n_resolved_records=n_resolved,
        n_eligible_records=n_eligible,
        n_used_records=n_eligible,
        n_excluded_records=n_excluded,
        n_unused_eligible_records=0,
        review_without_current_story=summary["review_without_current_story"],
        story_without_review=summary["story_without_review"],
    )

    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"Saved: {OUTPUT_PATH}")
    print(
        f"  canonical input: {len(tables.stories)} stories + {len(tables.reviews)} reviews "
        f"({tables.identity.registry_version})"
    )
    print(
        f"  joined: {summary['review_without_current_story']} reviews without a current story, "
        f"{summary['story_without_review']} stories without a review"
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
