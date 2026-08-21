"""
Lab Book: Verification Frontier — does test thoroughness track cost?

Reads every stories/*.json, recovers test counts (agentic fallback), and
computes the cost x test-thoroughness curve per model. The "frontier" is the
set of models that are not Pareto-dominated: no other model is both cheaper
AND writes more tests.

CANONICAL INPUT (semantic-integrity release, phase s2): publication-eligible, so the
input is the registry resolver only (``lifecycle_state == "current"`` story rows) — no
``stories/*.json`` glob, no retired summary. The output embeds a ``lab_contract`` block
that ``build_data.py`` re-validates against the current manifest before publishing.

Usage:
    python scripts/lab_verification_frontier.py

Output:
    experiments/results/lab_verification_frontier.json
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
LAB = "lab_verification_frontier.py"
OUTPUT_PATH = Path("experiments/results/lab_verification_frontier.json")


def _short_model(model: str) -> str:
    return model.split("/")[-1]


def _test_count(d: dict) -> int:
    """Recover tests-written: summary.test_count, else peak agentic.tests_total."""
    summary = d.get("summary", {}) or {}
    n = summary.get("test_count", 0) or 0
    if n > 0:
        return int(n)
    peak = 0
    for s in d.get("sessions", []):
        a = s.get("agentic", {}) or {}
        peak = max(peak, a.get("tests_total", 0) or 0)
    return peak


def compute(stories: list[dict]) -> dict:
    """Compute the cost x test-thoroughness frontier over the canonical story payloads.

    Split out of :func:`main` so the analysis is testable without touching the registry.
    """
    by_model = defaultdict(lambda: {"costs": [], "tests": [], "cells": 0})

    for d in stories:
        m = _short_model(d.get("model", "unknown"))
        summary = d.get("summary", {}) or {}
        cost = summary.get("total_cost", 0) or 0
        tests = _test_count(d)
        by_model[m]["tests"].append(tests)
        by_model[m]["cells"] += 1
        if cost > 0:
            by_model[m]["costs"].append(cost)

    def avg(lst):
        return round(sum(lst) / len(lst), 3) if lst else 0.0

    models = []
    for m, v in by_model.items():
        models.append(
            {
                "model": m,
                "cells": v["cells"],
                "cost_cells": len(v["costs"]),
                "avg_cost": avg(v["costs"]),
                "avg_tests": avg(v["tests"]),
                "total_cost": round(sum(v["costs"]), 4),
                "total_tests": sum(v["tests"]),
            }
        )
    models.sort(key=lambda x: x["avg_cost"])

    # Pareto frontier: models not dominated (cheaper AND more tests) by another.
    frontier = []
    for m in models:
        dominated = any(
            o["avg_cost"] <= m["avg_cost"]
            and o["avg_tests"] >= m["avg_tests"]
            and (o["avg_cost"] < m["avg_cost"] or o["avg_tests"] > m["avg_tests"])
            for o in models
        )
        if not dominated:
            frontier.append(m["model"])

    return {
        "experiment_id": "lab_verification_frontier",
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "models": len(models),
            "stories": len(stories),
            "cheapest": models[0]["model"] if models else None,
            "most_verified": max(models, key=lambda x: x["avg_tests"])["model"] if models else None,
            "pareto_frontier": frontier,
        },
        "models": models,
    }


def main():
    tables = load_canonical_tables("story")
    output = compute(tables.stories)
    # Record scope (public-truth review P1): every current story is consumed, so
    # eligible == used == resolved — declared explicitly, not via a permissive default.
    attach_contract(
        output,
        LAB,
        tables,
        n_eligible_records=len(tables.stories),
        n_used_records=len(tables.stories),
    )

    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    frontier = output["summary"]["pareto_frontier"]
    print(f"Saved: {OUTPUT_PATH}")
    print(f"  canonical input: {len(tables.stories)} stories ({tables.identity.registry_version})")
    for m in output["models"]:
        print(
            f"  {m['model']:20s} cells={m['cells']:3d} cost=${m['avg_cost']:>7.3f} "
            f"tests={m['avg_tests']:>7.1f} {'[FRONTIER]' if m['model'] in frontier else ''}"
        )


if __name__ == "__main__":
    main()
