"""
Lab Book: Condition Effects — does perturbing the seed change the whole arc?

Compares clean vs bad_seed vs early_degrade vs late_degrade across the canonical story
corpus: success rate, cost, cascade recovery, and the reviewer "worse" rate.

CANONICAL INPUT (semantic-integrity release, phase s2)
------------------------------------------------------
Publication-eligible, so the input is the registry resolver only
(``agentic_dynamics.reporting.canonical_corpus``): ``lifecycle_state == "current"``
story and review rows. Two consequences that matter for *this* lab specifically:

* The 77 tombstoned ``early_degrade`` cells (``docs/data_integrity_findings.md``) are
  excluded, so the condition comparison is no longer contaminated by them.
* Conditions are read from ``_canonical_condition`` — the resolver's no-op relabel. A
  cell labelled ``bad_seed``/``early_degrade`` that carries no instrumented verdict
  received no actual perturbation and counts as ``clean``. Reporting it as a
  perturbation arm is exactly the error this lab would otherwise commit.

The output embeds a ``lab_contract`` block; ``build_data.py`` re-validates its manifest
hash before publishing.

Usage:
    python scripts/lab_condition_effects.py

Output:
    experiments/results/lab_condition_effects.json
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
LAB = "lab_condition_effects.py"
OUTPUT_PATH = Path("experiments/results/lab_condition_effects.json")


def _short_model(model: str) -> str:
    return model.split("/")[-1]


def _review_outcomes_by_story(reviews: list[dict]) -> dict[str, dict[str, int]]:
    """``story_id -> {"worse": n, "total": n}`` from the canonical review rows.

    The resolver stamps ``_story_id`` on every review from its registry row, so the
    story join is exact. The previous implementation scanned every review file for each
    story and counted reviews with no story id at all, which inflated ``total`` for every
    condition — a measurement error the registry join removes.
    """
    outcomes: dict[str, dict[str, int]] = defaultdict(lambda: {"worse": 0, "total": 0})
    for r in reviews:
        sid = str(r.get("_story_id") or r.get("story_id") or "")
        if not sid:
            continue
        outcomes[sid]["total"] += 1
        if r.get("better_or_worse") == "worse":
            outcomes[sid]["worse"] += 1
    return outcomes


def compute(stories: list[dict], reviews: list[dict]) -> dict:
    """Aggregate outcome metrics per perturbation condition.

    Split out of :func:`main` so the analysis is testable without touching the registry.
    """
    review_outcomes = _review_outcomes_by_story(reviews)

    by_condition = defaultdict(
        lambda: {"cells": 0, "cost": [], "success": 0, "cascade": 0, "worse": 0, "reviewed": 0}
    )

    for d in stories:
        cond = d.get("_canonical_condition") or "clean"
        summary = d.get("summary", {}) or {}
        cost = summary.get("total_cost", 0) or 0
        b = by_condition[cond]
        b["cells"] += 1
        b["cost"].append(cost)
        if summary.get("all_successful"):
            b["success"] += 1
        if summary.get("cascade_recovery"):
            b["cascade"] += 1
        outcome = review_outcomes.get(str(d.get("story_id") or ""))
        if outcome:
            b["reviewed"] += outcome["total"]
            b["worse"] += outcome["worse"]

    conditions = []
    for cond, b in by_condition.items():
        n = b["cells"]
        reviewed = b["reviewed"]
        conditions.append(
            {
                "condition": cond,
                "cells": n,
                "success_rate": round(b["success"] / n, 3) if n else 0,
                "cascade_rate": round(b["cascade"] / n, 3) if n else 0,
                "avg_cost": round(sum(b["cost"]) / n, 4) if n else 0,
                "total_cost": round(sum(b["cost"]), 4),
                "reviews": reviewed,
                # None (not 0) when nothing was reviewed — an unmeasured rate is not "0%".
                "worse_rate": round(b["worse"] / reviewed, 3) if reviewed else None,
            }
        )
    conditions.sort(key=lambda x: x["condition"])

    return {
        "experiment_id": "lab_condition_effects",
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "conditions": len(conditions),
            "stories": len(stories),
            "reviews": len(reviews),
        },
        "conditions": conditions,
    }


def main():
    tables = load_canonical_tables("story", "review")
    output = compute(tables.stories, tables.reviews)
    attach_contract(
        output,
        LAB,
        tables,
    )

    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"Saved: {OUTPUT_PATH}")
    print(
        f"  canonical input: {len(tables.stories)} stories + {len(tables.reviews)} reviews "
        f"({tables.identity.registry_version})"
    )
    for c in output["conditions"]:
        worse = "—" if c["worse_rate"] is None else f"{c['worse_rate']:.0%}"
        print(
            f"  {c['condition']:15s} cells={c['cells']:3d} success={c['success_rate']:.0%} "
            f"cascade={c['cascade_rate']:.0%} avg_cost=${c['avg_cost']:.4f} worse={worse}"
        )


if __name__ == "__main__":
    main()
