"""
Lab Book: Quality Frontier — is code cleanliness decoupled from cost?

Joins per-story cost to mechanical quality signals (LSP errors, code-quality
score, cyclomatic complexity) and asks whether paying more buys cleaner code,
the way review quality already showed it does not.

CANONICAL INPUT (semantic-integrity release, phase s2): publication-eligible, so both
inputs come from the registry resolver. Analysis artifacts are not registered as their
own source type, but the resolver reads only ``analysis_<story_id>.json`` files whose
story row is CURRENT — the registry chooses the files, which is what separates a
registry-filtered join from the ``ANALYSIS_DIR.glob("*.json")`` this replaces. The output
embeds a ``lab_contract`` block that ``build_data.py`` re-validates.

Usage:
    python scripts/lab_quality_frontier.py

Output:
    experiments/results/lab_quality_frontier.json
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
LAB = "lab_quality_frontier.py"
OUTPUT_PATH = Path("experiments/results/lab_quality_frontier.json")


def _short_model(model: str) -> str:
    return model.split("/")[-1]


def _avg(lst):
    return round(sum(lst) / len(lst), 3) if lst else 0.0


def compute(stories: list[dict], analyses: list[dict]) -> dict:
    """Join per-story cost to mechanical quality signals over the canonical corpus.

    Split out of :func:`main` so the analysis is testable without touching the registry.
    """
    # story_id -> (model, cost), from the current story rows only.
    cost_by_sid = {}
    for d in stories:
        sid = str(d.get("story_id") or "")
        if len(sid) >= 8:
            summary = d.get("summary", {}) or {}
            cost_by_sid[sid] = (d.get("model", "?"), summary.get("total_cost", 0) or 0)

    by_model = defaultdict(
        lambda: {
            "costs": [],
            "lsp_errors": [],
            "quality": [],
            "cyclomatic": [],
            "novelty": [],
        }
    )

    for d in analyses:
        sid = str(d.get("_story_id") or d.get("story_id") or "")
        if sid not in cost_by_sid:
            continue
        model, cost = cost_by_sid[sid]
        deep = d.get("deep", {}) or {}
        lsp = deep.get("lsp", {}) or {}
        sol = deep.get("solution", {}) or {}
        b = by_model[_short_model(model)]
        if cost > 0:
            b["costs"].append(cost)
        b["lsp_errors"].append(lsp.get("errors", 0) or 0)
        b["quality"].append(sol.get("code_quality_score", 0) or 0)
        b["cyclomatic"].append(sol.get("cyclomatic_complexity", 0) or 0)
        b["novelty"].append(sol.get("novelty_score", 0) or 0)

    models = []
    for m, v in by_model.items():
        models.append(
            {
                "model": m,
                "cells": len(v["costs"]),
                "avg_cost": _avg(v["costs"]),
                "lsp_errors_per_cell": _avg(v["lsp_errors"]),
                "code_quality_score": _avg(v["quality"]),
                "cyclomatic_complexity": _avg(v["cyclomatic"]),
                "novelty_score": _avg(v["novelty"]),
            }
        )
    models.sort(key=lambda x: x["avg_cost"])

    return {
        "experiment_id": "lab_quality_frontier",
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "models": len(models),
            "stories": len(stories),
            "analyses": len(analyses),
        },
        "models": models,
    }


def main():
    tables = load_canonical_tables("story", "analysis")
    output = compute(tables.stories, tables.analysis)
    attach_contract(
        output,
        LAB,
        tables,
        n_input_records=len(tables.stories) + len(tables.analysis),
    )

    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"Saved: {OUTPUT_PATH}")
    print(
        f"  canonical input: {len(tables.stories)} stories + {len(tables.analysis)} analyses "
        f"({tables.identity.registry_version})"
    )
    for m in output["models"]:
        print(
            f"  {m['model']:20s} cost=${m['avg_cost']:>7.3f} lsp_err={m['lsp_errors_per_cell']:>5.1f} "
            f"quality={m['code_quality_score']:>6.3f} cyclomatic={m['cyclomatic_complexity']:>7.1f}"
        )


if __name__ == "__main__":
    main()
