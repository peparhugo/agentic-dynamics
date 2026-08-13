"""
Lab Book: Quality Frontier — is code cleanliness decoupled from cost?

Joins per-story cost to mechanical quality signals (LSP errors, code-quality
score, cyclomatic complexity) and asks whether paying more buys cleaner code,
the way review quality already showed it does not.

Usage:
    python scripts/lab_quality_frontier.py

Output:
    experiments/results/lab_quality_frontier.json
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ANALYSIS_DIR = Path("experiments/results/analysis")
STORIES_DIR = Path("experiments/results/stories")


def _short_model(model: str) -> str:
    return model.split("/")[-1]


def _avg(lst):
    return round(sum(lst) / len(lst), 3) if lst else 0.0


def main():
    # story_id -> cost + model (from stories)
    cost_by_sid = {}
    for f in sorted(STORIES_DIR.glob("*.json")):
        if "log" in f.name or "dvs" in f.name:
            continue
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        sid = d.get("story_id", "") or f.stem.split("_")[-1]
        if len(sid) >= 8:
            cost_by_sid[sid] = (d.get("model", "?"), d.get("summary", {}).get("total_cost", 0) or 0)

    by_model = defaultdict(lambda: {
        "costs": [], "lsp_errors": [], "quality": [], "cyclomatic": [], "novelty": [],
    })

    for f in sorted(ANALYSIS_DIR.glob("*.json")):
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        sid = d.get("story_id", "")
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
        models.append({
            "model": m,
            "cells": len(v["costs"]),
            "avg_cost": _avg(v["costs"]),
            "lsp_errors_per_cell": _avg(v["lsp_errors"]),
            "code_quality_score": _avg(v["quality"]),
            "cyclomatic_complexity": _avg(v["cyclomatic"]),
            "novelty_score": _avg(v["novelty"]),
        })
    models.sort(key=lambda x: x["avg_cost"])

    output = {
        "experiment_id": "lab_quality_frontier",
        "generated_at": datetime.now().isoformat(),
        "summary": {"models": len(models)},
        "models": models,
    }

    out = Path("experiments/results/lab_quality_frontier.json")
    out.write_text(json.dumps(output, indent=2))
    print(f"Saved: {out}")
    for m in models:
        print(f"  {m['model']:20s} cost=${m['avg_cost']:>7.3f} lsp_err={m['lsp_errors_per_cell']:>5.1f} "
              f"quality={m['code_quality_score']:>6.3f} cyclomatic={m['cyclomatic_complexity']:>7.1f}")


if __name__ == "__main__":
    main()
