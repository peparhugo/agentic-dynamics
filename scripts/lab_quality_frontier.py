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
from agentic_dynamics.reporting.measurement_coverage import (
    MeasurementCoverage,
    cost_captured,
    cost_coverage,
)

#: This script's name, as classified in scripts/lab_manifest.json — the contract key.
LAB = "lab_quality_frontier.py"
OUTPUT_PATH = Path("experiments/results/lab_quality_frontier.json")


def _short_model(model: str) -> str:
    return model.split("/")[-1]


def _avg(lst):
    return round(sum(lst) / len(lst), 3) if lst else 0.0


def _captured_avg(lst):
    """Mean over *available* values only; ``None`` when none available (m2 null-not-zero)."""
    return round(sum(lst) / len(lst), 3) if lst else None


def _coverage(lst, *, n_total):
    """The ``{value, n_available, n_total, coverage}`` shape for an optional metric (m2)."""
    return MeasurementCoverage.over(lst, n_total=n_total, round_value=3).to_dict()


def compute(stories: list[dict], analyses: list[dict]) -> dict:
    """Join per-story cost to mechanical quality signals over the canonical corpus.

    Split out of :func:`main` so the analysis is testable without touching the registry.
    """
    # story_id -> (model, cost), from the current story rows only. A story must carry a
    # real model to be a usable join target; one without is dropped from the map so the
    # join below (``sid not in cost_by_sid``) excludes it rather than emitting a
    # placeholder ``model: "?"`` row (measurement-contribution closure, m1).
    cost_by_sid = {}
    for d in stories:
        sid = str(d.get("story_id") or "")
        model = d.get("model")
        if len(sid) >= 8 and model:
            summary = d.get("summary", {}) or {}
            # Raw cost (None when absent) — captured-ness is decided by cost_captured,
            # not re-derived here with `or 0` (m2).
            cost_by_sid[sid] = (model, summary.get("total_cost"))

    by_model = defaultdict(
        lambda: {
            "cells": 0,
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
        b["cells"] += 1
        if cost_captured(cost):
            b["costs"].append(cost)
        # LSP: count a cell ONLY when the language server actually ran. Every analysis
        # payload carries `errors: 0` by default, so averaging the raw field publishes a
        # fabricated zero — "no diagnostics" when the truth is "no diagnostics tool".
        # (`docs/data_integrity_findings.md`: an unmeasured value is null, never 0.)
        if lsp.get("available"):
            b["lsp_errors"].append(lsp.get("errors", 0) or 0)
        # m2 null-not-zero: an absent solution score is "not measured" and must not enter
        # the average as zero; a present field — even 0.0 — is a real value.
        for field, target in (
            ("code_quality_score", "quality"),
            ("cyclomatic_complexity", "cyclomatic"),
            ("novelty_score", "novelty"),
        ):
            score = sol.get(field)
            if score is not None:
                b[target].append(score)

    models = []
    for m, v in by_model.items():
        lsp_cells = len(v["lsp_errors"])
        cost_stats = cost_coverage(v["costs"], n_total=v["cells"])
        models.append(
            {
                "model": m,
                "cells": v["cells"],
                "avg_cost": cost_stats["avg_captured_cost"],
                "avg_captured_cost": cost_stats["avg_captured_cost"],
                "total_captured_cost": cost_stats["total_captured_cost"],
                "cost_captured_records": cost_stats["cost_captured_records"],
                "total_records": cost_stats["total_records"],
                "cost_coverage": cost_stats["cost_coverage"],
                # None (renders as an em-dash) when the LSP never ran for this model.
                "lsp_errors_per_cell": _avg(v["lsp_errors"]) if lsp_cells else None,
                "lsp_cells": lsp_cells,
                "code_quality_score": _captured_avg(v["quality"]),
                "code_quality_score_coverage": _coverage(v["quality"], n_total=v["cells"]),
                "cyclomatic_complexity": _captured_avg(v["cyclomatic"]),
                "cyclomatic_complexity_coverage": _coverage(v["cyclomatic"], n_total=v["cells"]),
                "novelty_score": _captured_avg(v["novelty"]),
                "novelty_score_coverage": _coverage(v["novelty"], n_total=v["cells"]),
            }
        )
    models.sort(key=lambda x: (x["avg_cost"] is None, x["avg_cost"] or 0))

    return {
        "experiment_id": "lab_quality_frontier",
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "models": len(models),
            "stories": len(stories),
            "analyses": len(analyses),
            # How many analysed cells actually had a language server run. Zero here means
            # every lsp_errors_per_cell is null — the signal is absent, not clean.
            "lsp_available_cells": sum(m["lsp_cells"] for m in models),
        },
        "models": models,
    }


def main():
    tables = load_canonical_tables("story", "analysis")
    output = compute(tables.stories, tables.analysis)
    # Record scope (public-truth review P1): the metric consumes every current story and
    # every analysis the registry resolved for them — declared explicitly, not via a
    # permissive default.
    attach_contract(
        output,
        LAB,
        tables,
        n_eligible_records=len(tables.stories) + len(tables.analysis),
        n_used_records=len(tables.stories) + len(tables.analysis),
    )

    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"Saved: {OUTPUT_PATH}")
    print(
        f"  canonical input: {len(tables.stories)} stories + {len(tables.analysis)} analyses "
        f"({tables.identity.registry_version})"
    )
    for m in output["models"]:
        lsp = "—" if m["lsp_errors_per_cell"] is None else f"{m['lsp_errors_per_cell']:.1f}"
        cost = "—" if m["avg_cost"] is None else f"${m['avg_cost']:>7.3f}"
        quality = "—" if m["code_quality_score"] is None else f"{m['code_quality_score']:>6.3f}"
        cyclomatic = (
            "—" if m["cyclomatic_complexity"] is None else f"{m['cyclomatic_complexity']:>7.1f}"
        )
        print(
            f"  {m['model']:20s} cost={cost} lsp_err={lsp:>5s} "
            f"quality={quality} cyclomatic={cyclomatic}"
        )


if __name__ == "__main__":
    main()
