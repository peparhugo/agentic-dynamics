"""
Lab Book: Cache Economics — is cache policy the hidden cost driver?

Multi-session work re-reads the growing codebase every session. This lab
measures, per model, the cache hit rate, the read/write split, and the
context-token volume that compounds across the arc.

CANONICAL INPUT (semantic-integrity release, phase s2): publication-eligible, so the
input is the registry resolver only — ``lifecycle_state == "current"`` story rows, no
``stories/*.json`` glob, no retired summary. The output embeds a ``lab_contract`` block
that ``build_data.py`` re-validates against the current manifest before publishing.

Usage:
    python scripts/lab_cache_economics.py

Output:
    experiments/results/lab_cache_economics.json
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
from agentic_dynamics.reporting.measurement_coverage import (
    MeasurementCoverage,
    cost_captured,
    cost_coverage,
)

#: This script's name, as classified in scripts/lab_manifest.json — the contract key.
LAB = "lab_cache_economics.py"
OUTPUT_PATH = Path("experiments/results/lab_cache_economics.json")


def _short_model(model: str) -> str:
    return model.split("/")[-1]


def compute(stories: list[dict]) -> tuple[dict, ContributionReport]:
    """Aggregate per-model cache economics over the canonical story payloads.

    Returns ``(result, contribution)`` (m3) — the computation reports exactly which
    records it consumed, and the contract is derived from that report in :func:`main`.

    Split out of :func:`main` so the analysis is testable without touching the registry
    or the filesystem.
    """
    by_model = defaultdict(
        lambda: {
            "costs": [],
            "cache_hit": [],
            "reads": [],
            "writes": [],
            "context": [],
            "tokens": [],
            "cells": 0,
        }
    )
    used_ids: list[str] = []

    for d in stories:
        m = _short_model(d.get("model", "unknown"))
        s = d.get("summary", {}) or {}
        b = by_model[m]
        b["cells"] += 1
        used_ids.append(record_id(d))
        # m2 null-not-zero: only a *captured* cost enters the average; a missing/zero cost
        # is counted (cost_coverage) but never averaged in as $0 (review P1).
        cost = s.get("total_cost")
        if cost_captured(cost):
            b["costs"].append(cost)
        # Same rule for the optional per-cell measurements: a RATE (cache_hit_rate) and the
        # token volumes are captured-only — a session that did not record them is
        # "unavailable", never "zero". (reads/writes below stay count sums: a count's zero
        # is a real value, and they are published as totals, not averages.)
        if s.get("cache_hit_rate") is not None:
            b["cache_hit"].append(s["cache_hit_rate"])
        if s.get("total_context_tokens") is not None:
            b["context"].append(s["total_context_tokens"])
        if s.get("total_tokens") is not None:
            b["tokens"].append(s["total_tokens"])
        b["reads"].append(s.get("total_cache_reads", 0) or 0)
        b["writes"].append(s.get("total_cache_writes", 0) or 0)

    models = []
    for m, v in by_model.items():
        reads = sum(v["reads"])
        writes = sum(v["writes"])
        cost_stats = cost_coverage(v["costs"], n_total=v["cells"])
        cache_hit = MeasurementCoverage.over(v["cache_hit"], n_total=v["cells"], round_value=3)
        context = MeasurementCoverage.over(v["context"], n_total=v["cells"], round_value=0)
        tokens = MeasurementCoverage.over(v["tokens"], n_total=v["cells"], round_value=0)
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
                "avg_cache_hit": cache_hit.value,
                "cache_hit_coverage": cache_hit.to_dict(),
                "cache_reads": reads,
                "cache_writes": writes,
                "read_write_ratio": round(reads / writes, 1) if writes else None,
                "avg_context_per_cell": context.value,
                "context_coverage": context.to_dict(),
                "avg_tokens_per_cell": tokens.value,
                "tokens_coverage": tokens.to_dict(),
            }
        )
    # None-safe ordering: un-priced models sort last (matching the captured-only average).
    models.sort(key=lambda x: (x["avg_cost"] is None, x["avg_cost"] or 0))

    result = {
        "experiment_id": "lab_cache_economics",
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "models": len(models),
            "stories": len(stories),
        },
        "models": models,
    }
    # m3: every current story is consumed — no exclusion, no unused-eligible gap.
    contribution = ContributionReport.of(used_record_ids=used_ids)
    return result, contribution


def main():
    tables = load_canonical_tables("story")
    output, contribution = compute(tables.stories)
    attach_contribution(output, LAB, tables, contribution)

    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"Saved: {OUTPUT_PATH}")
    print(f"  canonical input: {len(tables.stories)} stories ({tables.identity.registry_version})")
    for m in output["models"]:
        cost = "—" if m["avg_cost"] is None else f"${m['avg_cost']:>7.3f}"
        print(
            f"  {m['model']:20s} cost={cost} hit={m['avg_cache_hit']:.0%} "
            f"r/w={m['read_write_ratio']} context/cell={m['avg_context_per_cell']:>9.0f}"
        )


if __name__ == "__main__":
    main()
