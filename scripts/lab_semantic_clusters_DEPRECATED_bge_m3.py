#!/usr/bin/env python3
r"""Lab Book 10: Semantic Step Clusters — Reasoning Pattern Typology

Uses ChromaDB step-level embeddings to discover latent clusters of reasoning
steps across all sessions. Clusters individual reasoning steps (not whole
sessions) by semantic similarity, revealing cross-session thinking patterns.

Output: experiments/results/lab_semantic_clusters.json
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from instrument.embeddings import ChromaStore

OUTPUT_PATH = ROOT / "experiments" / "results" / "lab_semantic_clusters.json"


def _cosine_distance(a, b) -> float:
    import numpy as np
    dot = float(np.dot(a, b))
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return (1.0 - dot / (norm_a * norm_b)) / 2.0


def compute(max_steps: int = 5000):
    store = ChromaStore()
    results = store.collection.get(include=["embeddings", "metadatas"])
    embeddings = results["embeddings"]
    metadatas = results["metadatas"]

    step_indices = [i for i, m in enumerate(metadatas)
                    if m.get("embedding_source") == "reasoning_step"]

    if len(step_indices) < 2:
        return {"_meta": {"experiment_id": "lab_semantic_clusters",
                          "error": f"Need >=2 reasoning_step docs, got {len(step_indices)}"}}

    use_indices = step_indices[:max_steps]

    print(f"Total step embeddings: {len(step_indices)}")
    print(f"Comparing {len(use_indices)} steps...")

    pairs: list[dict] = []
    n = len(use_indices)

    for i in range(n):
        for j in range(i + 1, n):
            ma = metadatas[use_indices[i]]
            mb = metadatas[use_indices[j]]
            if ma.get("session_id") == mb.get("session_id"):
                continue
            if ma.get("step_index") != mb.get("step_index"):
                continue

            dist = _cosine_distance(
                embeddings[use_indices[i]], embeddings[use_indices[j]],
            )
            pairs.append({
                "step_a": f"{ma.get('session_id','?')}@{ma.get('step_index',0)}",
                "step_b": f"{mb.get('session_id','?')}@{mb.get('step_index',0)}",
                "session_a": ma.get("session_id", ""),
                "session_b": mb.get("session_id", ""),
                "step_index": ma.get("step_index", 0),
                "tool_a": ma.get("tool_after", ""),
                "tool_b": mb.get("tool_after", ""),
                "model_a": ma.get("model", ""),
                "model_b": mb.get("model", ""),
                "distance": round(dist, 4),
            })
        if (i + 1) % 25 == 0:
            print(f"  Compared {i+1}/{n} steps, {len(pairs)} pairs...", flush=True)

    pairs.sort(key=lambda p: p["distance"])

    # Per-step-index statistics
    by_step_index: dict[int, list[float]] = defaultdict(list)
    for p in pairs:
        si = p.get("step_index", 0)
        by_step_index[si].append(p["distance"])

    step_stats = {}
    for si, dists in sorted(by_step_index.items()):
        mean_d = sum(dists) / len(dists)
        step_stats[str(si)] = {
            "mean_distance": round(mean_d, 4),
            "std_dev": round((sum((d - mean_d) ** 2 for d in dists) / len(dists)) ** 0.5, 4),
            "count": len(dists),
        }

    # Model pair distances
    model_pairs: dict[str, list[float]] = defaultdict(list)
    for p in pairs:
        ma, mb = p["model_a"], p["model_b"]
        if ma and mb and ma != mb:
            key = f"{ma} ↔ {mb}" if ma < mb else f"{mb} ↔ {ma}"
            model_pairs[key].append(p["distance"])

    cross_model = {}
    for key, dists in sorted(model_pairs.items()):
        if dists:
            m = sum(dists) / len(dists)
            cross_model[key] = {"mean_distance": round(m, 4), "count": len(dists)}

    # Tool-based distances
    tool_pairs: dict[str, list[float]] = defaultdict(list)
    for p in pairs:
        ta, tb = p["tool_a"], p["tool_b"]
        if ta and tb:
            tools = tuple(sorted([ta, tb]))
            tool_key = f"{tools[0]} × {tools[1]}"
            tool_pairs[tool_key].append(p["distance"])

    tool_stats = {}
    for key, dists in sorted(tool_pairs.items(), key=lambda x: -len(x[1])):
        m = sum(dists) / len(dists)
        tool_stats[key] = {"mean_distance": round(m, 4), "count": len(dists)}

    avg_d = sum(p["distance"] for p in pairs) / max(len(pairs), 1)
    std_d = 0
    if len(pairs) > 1:
        std_d = (sum((p["distance"] - avg_d) ** 2 for p in pairs) / len(pairs)) ** 0.5

    outliers = [p for p in pairs if p["distance"] > avg_d + 2 * std_d]

    return {
        "_meta": {
            "experiment_id": "lab_semantic_clusters",
            "total_step_embeddings": len(step_indices),
            "pairwise_comparisons": len(pairs),
            "mean_distance": round(avg_d, 4),
            "std_dev_distance": round(std_d, 4),
            "method": "Step-level comparison: matching positions only (step N vs step N, different sessions)",
        },
        "closest_pairs": pairs[:20],
        "farthest_pairs": pairs[-10:][::-1],
        "outliers": outliers[:10],
        "per_step_index": step_stats,
        "cross_model": cross_model,
        "by_tool_pair": tool_stats,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-steps", type=int, default=5000)
    args = parser.parse_args()
    results = compute(max_steps=args.max_steps)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nWrote: {OUTPUT_PATH}")
