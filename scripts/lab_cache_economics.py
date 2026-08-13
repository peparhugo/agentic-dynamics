"""
Lab Book: Cache Economics — is cache policy the hidden cost driver?

Multi-session work re-reads the growing codebase every session. This lab
measures, per model, the cache hit rate, the read/write split, and the
context-token volume that compounds across the arc.

Usage:
    python scripts/lab_cache_economics.py

Output:
    experiments/results/lab_cache_economics.json
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

RESULTS_DIR = Path("experiments/results/stories")


def _short_model(model: str) -> str:
    return model.split("/")[-1]


def _avg(lst):
    return round(sum(lst) / len(lst), 3) if lst else 0.0


def main():
    by_model = defaultdict(lambda: {
        "costs": [], "cache_hit": [], "reads": [], "writes": [],
        "context": [], "tokens": [], "cells": 0,
    })

    for f in sorted(RESULTS_DIR.glob("*.json")):
        if "log" in f.name or "dvs" in f.name:
            continue
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if "model" not in d:
            continue
        m = _short_model(d["model"])
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
        models.append({
            "model": m,
            "cells": v["cells"],
            "avg_cost": _avg(v["costs"]),
            "avg_cache_hit": _avg(v["cache_hit"]),
            "cache_reads": reads,
            "cache_writes": writes,
            "read_write_ratio": round(reads / writes, 1) if writes else None,
            "avg_context_per_cell": round(sum(v["context"]) / len(v["context"]), 0),
            "avg_tokens_per_cell": round(sum(v["tokens"]) / len(v["tokens"]), 0),
        })
    models.sort(key=lambda x: x["avg_cost"])

    output = {
        "experiment_id": "lab_cache_economics",
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "models": len(models),
        },
        "models": models,
    }

    out = Path("experiments/results/lab_cache_economics.json")
    out.write_text(json.dumps(output, indent=2))
    print(f"Saved: {out}")
    for m in models:
        print(f"  {m['model']:20s} cost=${m['avg_cost']:>7.3f} hit={m['avg_cache_hit']:.0%} "
              f"r/w={m['read_write_ratio']} context/cell={m['avg_context_per_cell']:>9.0f}")


if __name__ == "__main__":
    main()
