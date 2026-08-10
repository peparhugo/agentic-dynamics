#!/usr/bin/env python3
r"""Lab Book 9: Reasoning Divergence — Per-Step Reasoning Comparison

Queries ChromaDB for step-level reasoning embeddings and computes pairwise
cosine distances at matching step positions within each model. Groups by
operator pair and perturbation class.

Output: experiments/results/lab_reasoning_divergence.json
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from instrument.embeddings import ChromaStore

OUTPUT_PATH = ROOT / "experiments" / "results" / "lab_reasoning_divergence.json"

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
        return {"_meta": {"experiment_id": "lab_reasoning_divergence",
                          "error": f"Need >=2 reasoning_step docs, got {len(step_indices)}"}}

    # Group steps by (session_id, step_index)
    by_session_step: dict[str, dict[int, tuple]] = defaultdict(dict)
    for idx in step_indices:
        sid = metadatas[idx].get("session_id", "?")
        step_idx = metadatas[idx].get("step_index", 0)
        by_session_step[sid][step_idx] = (idx, metadatas[idx].get("model", "unknown"))

    # Find overlapping step positions between sessions within same model
    sessions_per_model: dict[str, list[str]] = defaultdict(list)
    session_meta: dict[str, dict] = {}
    for idx in step_indices:
        sid = metadatas[idx].get("session_id", "?")
        model = metadatas[idx].get("model", "unknown")
        if sid not in session_meta:
            session_meta[sid] = metadatas[idx]
            sessions_per_model[model].append(sid)

    per_operator: dict[str, list[float]] = defaultdict(list)
    per_class: dict[str, list[float]] = defaultdict(list)
    per_model: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    pair_details: list[dict] = []
    pair_count = 0

    for model_id, sids in sorted(sessions_per_model.items()):
        for i in range(len(sids)):
            for j in range(i + 1, len(sids)):
                a_steps = by_session_step[sids[i]]
                b_steps = by_session_step[sids[j]]
                common_positions = set(a_steps.keys()) & set(b_steps.keys())
                if len(common_positions) < 2:
                    continue

                dists_at_pos: list[float] = []
                for pos in sorted(common_positions):
                    a_idx, _ = a_steps[pos]
                    b_idx, _ = b_steps[pos]
                    d = _cosine_distance(embeddings[a_idx], embeddings[b_idx])
                    dists_at_pos.append(d)

                mean_dist = sum(dists_at_pos) / len(dists_at_pos)

                ma = session_meta[sids[i]]
                mb = session_meta[sids[j]]
                op_a = ma.get("operator", "?")
                op_b = mb.get("operator", "?")
                cls_a = ma.get("perturbation_class", "?")
                cls_b = mb.get("perturbation_class", "?")

                ops_sorted = tuple(sorted([op_a, op_b]))
                op_key = f"{ops_sorted[0]} × {ops_sorted[1]}"

                per_operator[op_key].append(mean_dist)
                per_model[model_id][op_key].append(mean_dist)
                if cls_a == cls_b:
                    per_class[cls_a].append(mean_dist)
                else:
                    per_class["mixed"].append(mean_dist)

                pair_details.append({
                    "session_a": sids[i],
                    "session_b": sids[j],
                    "model": model_id,
                    "operator_pair": op_key,
                    "class_a": cls_a,
                    "class_b": cls_b,
                    "overlapping_steps": len(common_positions),
                    "mean_distance": round(mean_dist, 4),
                })
                pair_count += 1

    per_operator_out = {}
    for op_key, dists in sorted(per_operator.items(), key=lambda x: -len(x[1])):
        mean_d = sum(dists) / len(dists)
        per_operator_out[op_key] = {
            "operator_pair": op_key,
            "mean_distance": round(mean_d, 4),
            "std_dev": round((sum((d - mean_d) ** 2 for d in dists) / len(dists)) ** 0.5, 4),
            "count": len(dists),
        }

    per_class_out = {}
    for cls, dists in sorted(per_class.items()):
        mean_d = sum(dists) / len(dists)
        per_class_out[cls] = {"class": cls, "mean_distance": round(mean_d, 4),
                              "count": len(dists)}

    per_model_out = {}
    for model_id in sorted(per_model):
        profile = {"model_id": model_id, "label": MODEL_LABELS.get(model_id, model_id),
                   "sessions_with_steps": len(sessions_per_model[model_id])}
        for op_key, dists in sorted(per_model[model_id].items()):
            if dists:
                mean_d = sum(dists) / len(dists)
                profile[op_key] = {"mean_distance": round(mean_d, 4), "count": len(dists)}
        per_model_out[model_id] = profile

    return {
        "_meta": {
            "experiment_id": "lab_reasoning_divergence",
            "total_pairs": pair_count,
            "total_step_embeddings": len(step_indices),
            "models_analyzed": len(sessions_per_model),
            "data_source": "ChromaDB — per-step reasoning embeddings via bge-m3",
            "method": "Compares matching step positions (step N vs step N) across session pairs",
            "metric": "cosine distance between matching reasoning step embeddings",
        },
        "per_operator_pair": per_operator_out,
        "per_class": per_class_out,
        "per_model": per_model_out,
        "pairs": pair_details[:200],
    }


if __name__ == "__main__":
    results = compute()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nWrote: {OUTPUT_PATH}")
