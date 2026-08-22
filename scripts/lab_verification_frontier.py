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
from agentic_dynamics.reporting.lab_contract import (
    ContributionReport,
    attach_contribution,
    record_id,
)
from agentic_dynamics.reporting.measurement_coverage import cost_captured, cost_coverage

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


def compute(stories: list[dict]) -> tuple[dict, ContributionReport]:
    """Compute the cost x test-thoroughness frontier over the canonical story payloads.

    Returns ``(result, contribution)`` (m3): every current story is consumed.

    Split out of :func:`main` so the analysis is testable without touching the registry.
    """
    by_model = defaultdict(lambda: {"costs": [], "tests": [], "cells": 0})
    used_ids: list[str] = []

    for d in stories:
        m = _short_model(d.get("model", "unknown"))
        used_ids.append(record_id(d))
        summary = d.get("summary", {}) or {}
        # m2 null-not-zero: only a *captured* cost enters the average; a missing/zero cost
        # is counted but never averaged in as $0 (review P1).
        cost = summary.get("total_cost")
        tests = _test_count(d)
        by_model[m]["tests"].append(tests)
        by_model[m]["cells"] += 1
        if cost_captured(cost):
            by_model[m]["costs"].append(cost)

    def avg(lst):
        return round(sum(lst) / len(lst), 3) if lst else 0.0

    models = []
    for m, v in by_model.items():
        cost_stats = cost_coverage(v["costs"], n_total=v["cells"])
        models.append(
            {
                "model": m,
                "cells": v["cells"],
                "cost_cells": cost_stats["cost_captured_records"],
                "avg_cost": cost_stats["avg_captured_cost"],
                "avg_captured_cost": cost_stats["avg_captured_cost"],
                "total_captured_cost": cost_stats["total_captured_cost"],
                "cost_captured_records": cost_stats["cost_captured_records"],
                "total_records": cost_stats["total_records"],
                "cost_coverage": cost_stats["cost_coverage"],
                "avg_tests": avg(v["tests"]),
                "total_cost": cost_stats["total_captured_cost"],
                "total_tests": sum(v["tests"]),
            }
        )
    # None-safe ordering: un-priced models (avg_cost None) sort last.
    models.sort(key=lambda x: (x["avg_cost"] is None, x["avg_cost"] or 0))

    # Pareto frontier: models not dominated (cheaper AND more tests) by another. An
    # un-priced model (avg_cost None) is treated as infinitely expensive, so it can only
    # survive the frontier if nothing cheaper writes as many tests.
    def _cost(m):
        return m["avg_cost"] if m["avg_cost"] is not None else float("inf")

    frontier = []
    for m in models:
        dominated = any(
            _cost(o) <= _cost(m)
            and o["avg_tests"] >= m["avg_tests"]
            and (_cost(o) < _cost(m) or o["avg_tests"] > m["avg_tests"])
            for o in models
        )
        if not dominated:
            frontier.append(m["model"])

    result = {
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
    contribution = ContributionReport.of(used_record_ids=used_ids)
    return result, contribution


def main():
    tables = load_canonical_tables("story")
    output, contribution = compute(tables.stories)
    attach_contribution(output, LAB, tables, contribution)

    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    frontier = output["summary"]["pareto_frontier"]
    print(f"Saved: {OUTPUT_PATH}")
    print(f"  canonical input: {len(tables.stories)} stories ({tables.identity.registry_version})")
    for m in output["models"]:
        cost = "—" if m["avg_cost"] is None else f"${m['avg_cost']:>7.3f}"
        print(
            f"  {m['model']:20s} cells={m['cells']:3d} cost={cost} "
            f"tests={m['avg_tests']:>7.1f} {'[FRONTIER]' if m['model'] in frontier else ''}"
        )


if __name__ == "__main__":
    main()
