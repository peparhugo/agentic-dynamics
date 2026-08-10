#!/usr/bin/env python3
r"""Lab Book 11: Cross-Model Reasoning Similarity — Do Models Think Alike?

Uses ChromaDB step-level embeddings to compare reasoning patterns across
models. Computes model-level centroids from all steps, then per-step-position
distances where both models have data.

Output: experiments/results/lab_cross_model_reasoning.json
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from instrument.embeddings import ChromaStore

OUTPUT_PATH = ROOT / "experiments" / "results" / "lab_cross_model_reasoning.json"

MODEL_LABELS = {
    "deepseek/deepseek-v4-pro": "DeepSeek v4 Pro",
    "openai/gpt-5-nano": "GPT-5-nano",
    "openai/gpt-5-mini": "GPT-5-mini",
    "openai/gpt-5": "GPT-5",
    "openai/gpt-5.5": "GPT-5.5",
    "openai/gpt-5.6": "GPT-5.6",
    "openai/gpt-5.6-fast": "GPT-5.6-fast",
    "anthropic/claude-fable-5": "Claude Fable 5",
}


def _cosine_distance(a, b) -> float:
    import numpy as np
    dot = float(np.dot(a, b))
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return (1.0 - dot / (norm_a * norm_b)) / 2.0


def compute():
    store = ChromaStore()
    results = store.collection.get(include=["embeddings", "metadatas"])
    embeddings = results["embeddings"]
    metadatas = results["metadatas"]

    step_indices = [i for i, m in enumerate(metadatas)
                    if m.get("embedding_source") == "reasoning_step"]

    if len(step_indices) < 2:
        return {"_meta": {"experiment_id": "lab_cross_model_reasoning",
                          "error": f"Need >=2 steps, got {len(step_indices)}"}}

    # Group embeddings by model, and by (model, step_index)
    model_steps: dict[str, list] = defaultdict(list)
    model_step_pos: dict[str, dict[int, list]] = defaultdict(lambda: defaultdict(list))

    for idx in step_indices:
        meta = metadatas[idx]
        model = meta.get("model", "unknown")
        if model == "unknown":
            continue
        si = meta.get("step_index", 0)
        emb = embeddings[idx]
        model_steps[model].append(emb)
        model_step_pos[model][si].append(emb)

    # Model-level centroids
    model_centroids: dict[str, list] = {}
    import numpy as np
    for model, embs in model_steps.items():
        if embs:
            model_centroids[model] = np.mean(embs, axis=0).tolist()

    models = sorted(model_centroids.keys())
    print(f"Models with step embeddings: {len(models)}")
    for m in models:
        print(f"  {MODEL_LABELS.get(m, m)}: {len(model_steps[m])} steps")

    # Centroid-level comparison (global model similarity)
    centroid_pairs: list[dict] = []
    global_pairs: dict[str, list[float]] = defaultdict(list)
    for i in range(len(models)):
        for j in range(i + 1, len(models)):
            m_a, m_b = models[i], models[j]
            d = _cosine_distance(model_centroids[m_a], model_centroids[m_b])
            key = f"{m_a} ↔ {m_b}"
            global_pairs[key].append(d)
            centroid_pairs.append({
                "model_a": m_a, "model_b": m_b,
                "centroid_distance": round(d, 4),
                "steps_a": len(model_steps[m_a]),
                "steps_b": len(model_steps[m_b]),
            })

    # Per-step-position comparison (positional reasoning similarity)
    position_pairs: dict[str, dict[int, dict]] = defaultdict(dict)
    for i in range(len(models)):
        for j in range(i + 1, len(models)):
            m_a, m_b = models[i], models[j]
            key = f"{m_a} ↔ {m_b}"
            pos_a = model_step_pos[m_a]
            pos_b = model_step_pos[m_b]
            common = set(pos_a.keys()) & set(pos_b.keys())
            for pos in sorted(common):
                # Take mean embedding per position per model
                ca = np.mean(pos_a[pos], axis=0).tolist()
                cb = np.mean(pos_b[pos], axis=0).tolist()
                d = _cosine_distance(ca, cb)
                position_pairs[key][pos] = {
                    "distance": round(d, 4),
                    "n_a": len(pos_a[pos]),
                    "n_b": len(pos_b[pos]),
                }

    # Per-position aggregate (average distance across all model pairs)
    all_pos_dists: dict[int, list[float]] = defaultdict(list)
    for key, positions in position_pairs.items():
        for pos, info in positions.items():
            all_pos_dists[pos].append(info["distance"])

    position_stats = {}
    for pos in sorted(all_pos_dists):
        dists = all_pos_dists[pos]
        mean_d = sum(dists) / len(dists)
        position_stats[str(pos)] = {
            "mean_distance": round(mean_d, 4),
            "std_dev": round(
                (sum((d - mean_d) ** 2 for d in dists) / len(dists)) ** 0.5, 4
            ) if len(dists) > 1 else 0,
            "model_pairs": len(dists),
        }

    # Aggregate global pairs
    cross_model = {}
    for key, dists in sorted(global_pairs.items()):
        cross_model[key] = {
            "label": key,
            "centroid_distance": round(dists[0], 4),
            "position_count": len(position_pairs.get(key, {})),
            "total_steps_a": len(model_steps.get(key.split(" ↔ ")[0], [])),
            "total_steps_b": len(model_steps.get(key.split(" ↔ ")[1], [])),
        }

    return {
        "_meta": {
            "experiment_id": "lab_cross_model_reasoning",
            "total_step_embeddings": len(step_indices),
            "models_compared": len(models),
            "model_pairs": len(models) * (len(models) - 1) // 2,
            "data_source": "ChromaDB — per-step reasoning embeddings via bge-m3",
            "method": "Model-level centroid comparison + per-step-position distances",
        },
        "model_summary": {
            m: {"steps": len(model_steps[m]), "sessions": len(set(
                metadatas[idx].get("session_id", "") for idx in step_indices
                if metadatas[idx].get("model") == m
            ))}
            for m in models
        },
        "centroid_comparison": centroid_pairs,
        "cross_model": cross_model,
        "per_step_position": position_stats,
        "position_details": {k: {str(pos): v for pos, v in sorted(positions.items())}
                             for k, positions in position_pairs.items()},
    }


if __name__ == "__main__":
    results = compute()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nWrote: {OUTPUT_PATH}")
