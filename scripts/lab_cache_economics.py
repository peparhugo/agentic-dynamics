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
from agentic_dynamics.reporting.lab_contract import attach_contract

#: This script's name, as classified in scripts/lab_manifest.json — the contract key.
LAB = "lab_cache_economics.py"
OUTPUT_PATH = Path("experiments/results/lab_cache_economics.json")


def _short_model(model: str) -> str:
    return model.split("/")[-1]


def _avg(lst):
    return round(sum(lst) / len(lst), 3) if lst else 0.0


def compute(stories: list[dict]) -> dict:
    """Aggregate per-model cache economics over the canonical story payloads.

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

    for d in stories:
        m = _short_model(d.get("model", "unknown"))
        s = d.get("summary", {}) or {}
        b = by_model[m]
        b["cells"] += 1
        cost = s.get("total_cost", 0) or 0
        if cost > 0:
            b["costs"].append(cost)
        b["cache_hit"].append(s.get("cache_hit_rate", 0) or 0)
        b["reads"].append(s.get("total_cache_reads", 0) or 0)
        b["writes"].append(s.get("total_cache_writes", 0) or 0)
        b["context"].append(s.get("total_context_tokens", 0) or 0)
        b["tokens"].append(s.get("total_tokens", 0) or 0)

    models = []
    for m, v in by_model.items():
        reads = sum(v["reads"])
        writes = sum(v["writes"])
        models.append(
            {
                "model": m,
                "cells": v["cells"],
                "avg_cost": _avg(v["costs"]),
                "avg_cache_hit": _avg(v["cache_hit"]),
                "cache_reads": reads,
                "cache_writes": writes,
                "read_write_ratio": round(reads / writes, 1) if writes else None,
                "avg_context_per_cell": round(sum(v["context"]) / len(v["context"]), 0),
                "avg_tokens_per_cell": round(sum(v["tokens"]) / len(v["tokens"]), 0),
            }
        )
    models.sort(key=lambda x: x["avg_cost"])

    return {
        "experiment_id": "lab_cache_economics",
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "models": len(models),
            "stories": len(stories),
        },
        "models": models,
    }


def main():
    tables = load_canonical_tables("story")
    output = compute(tables.stories)
    # The contract records WHICH corpus produced these numbers; build_data re-checks it.
    attach_contract(output, LAB, tables)

    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"Saved: {OUTPUT_PATH}")
    print(f"  canonical input: {len(tables.stories)} stories ({tables.identity.registry_version})")
    for m in output["models"]:
        print(
            f"  {m['model']:20s} cost=${m['avg_cost']:>7.3f} hit={m['avg_cache_hit']:.0%} "
            f"r/w={m['read_write_ratio']} context/cell={m['avg_context_per_cell']:>9.0f}"
        )


if __name__ == "__main__":
    main()
