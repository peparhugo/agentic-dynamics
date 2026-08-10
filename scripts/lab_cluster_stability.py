#!/usr/bin/env python3
r"""Lab Book: Within-Session Cluster Stability

Computes k-means clusters (k=5) on BGE-M3 step embeddings, then measures
within-session cluster stability: entropy, switch rate, dominant ratio.

Output: experiments/results/lab_stability.json
"""

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from instrument.embeddings import ChromaStore
from _constants import MODEL_LABELS

SUMMARY_PATH = ROOT / "experiments" / "results" / "_results_summary.json"
OUTPUT_PATH = ROOT / "experiments" / "results" / "lab_stability.json"

N_CLUSTERS = 5


def _entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    entropy = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            entropy -= p * math.log(p)
    return entropy


def compute():
    store = ChromaStore()
    results = store.collection.get(include=["embeddings", "metadatas"])
    embeddings = results["embeddings"]
    metadatas = results["metadatas"]

    step_indices = [i for i, m in enumerate(metadatas)
                    if m.get("embedding_source") == "reasoning_step"]

    if len(step_indices) < N_CLUSTERS:
        return {"_meta": {"error": f"Need >= {N_CLUSTERS} steps, got {len(step_indices)}"}}

    emb_matrix = np.array([embeddings[i] for i in step_indices], dtype=np.float32)

    kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(emb_matrix)

    session_cluster_seqs: dict[str, list[int]] = defaultdict(list)
    session_models: dict[str, str] = {}

    for j, idx in enumerate(step_indices):
        sid = metadatas[idx].get("session_id", "")
        if sid:
            session_cluster_seqs[sid].append(int(cluster_labels[j]))
            if sid not in session_models:
                session_models[sid] = metadatas[idx].get("model", "unknown")

    summary_data = json.loads(SUMMARY_PATH.read_text())
    summary_by_worktree = {}
    for e in summary_data.get("entries", []):
        wt = e.get("worktree_name", "")
        if wt:
            summary_by_worktree[wt] = e

    # Per-session metrics
    session_metrics: dict[str, dict] = {}
    model_stability: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list))
    strategy_stability: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list))
    correctness_stability: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list))
    failure_stability: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list))

    for sid, seq in session_cluster_seqs.items():
        if len(seq) < 2:
            continue

        cluster_counts = [0] * N_CLUSTERS
        for c in seq:
            cluster_counts[c] += 1

        ent = _entropy(cluster_counts)
        max_entropy = math.log(N_CLUSTERS)  # Normalize
        norm_entropy = ent / max_entropy if max_entropy > 0 else 0.0

        switches = sum(1 for i in range(1, len(seq)) if seq[i] != seq[i - 1])
        switch_rate = switches / (len(seq) - 1)

        dominant_cluster = max(cluster_counts)
        dominant_ratio = dominant_cluster / len(seq)

        stability_score = dominant_ratio * (1.0 - switch_rate)

        entry = summary_by_worktree.get(sid, {})
        model = session_models.get(sid, entry.get("model", "unknown"))
        strategy = entry.get("strategy", "?")
        correctness = entry.get("correctness", None)
        narration_failure = entry.get("narration_failure", False)

        session_metrics[sid] = {
            "model": model,
            "n_steps": len(seq),
            "cluster_sequence": seq,
            "cluster_counts": cluster_counts,
            "entropy": round(norm_entropy, 4),
            "switch_rate": round(switch_rate, 4),
            "switch_count": switches,
            "dominant_ratio": round(dominant_ratio, 4),
            "dominant_cluster": cluster_counts.index(dominant_cluster),
            "stability_score": round(stability_score, 4),
            "strategy": strategy,
            "correctness": correctness,
            "narration_failure": narration_failure,
        }

        # Aggregate buckets
        model_stability[model]["entropy"].append(norm_entropy)
        model_stability[model]["switch_rate"].append(switch_rate)
        model_stability[model]["dominant_ratio"].append(dominant_ratio)
        model_stability[model]["stability_score"].append(stability_score)

        if strategy and strategy != "?":
            strategy_stability[strategy]["entropy"].append(norm_entropy)
            strategy_stability[strategy]["switch_rate"].append(switch_rate)
            strategy_stability[strategy]["dominant_ratio"].append(dominant_ratio)
            strategy_stability[strategy]["stability_score"].append(stability_score)

        if correctness is not None:
            if correctness >= 0.9:
                bucket = "high (>=0.9)"
            elif correctness >= 0.7:
                bucket = "medium (0.7-0.9)"
            else:
                bucket = "low (<0.7)"
            correctness_stability[bucket]["entropy"].append(norm_entropy)
            correctness_stability[bucket]["switch_rate"].append(switch_rate)
            correctness_stability[bucket]["dominant_ratio"].append(dominant_ratio)
            correctness_stability[bucket]["stability_score"].append(stability_score)

        failure_stability["narration_failure" if narration_failure else "success"]["entropy"].append(norm_entropy)
        failure_stability["narration_failure" if narration_failure else "success"]["switch_rate"].append(switch_rate)
        failure_stability["narration_failure" if narration_failure else "success"]["dominant_ratio"].append(dominant_ratio)
        failure_stability["narration_failure" if narration_failure else "success"]["stability_score"].append(stability_score)

    def _agg(d: dict[str, dict[str, list[float]]]) -> dict:
        out = {}
        for key, metrics in sorted(d.items()):
            entry_out = {}
            for metric_name, values in sorted(metrics.items()):
                if values:
                    entry_out[metric_name] = {
                        "mean": round(float(np.mean(values)), 4),
                        "std": round(float(np.std(values)), 4),
                        "n": len(values),
                    }
            out[key] = entry_out
        return out

    # Cluster sizes
    cluster_sizes = [0] * N_CLUSTERS
    for s in cluster_labels:
        cluster_sizes[s] += 1

    # Summary stats
    all_ents = [m["entropy"] for m in session_metrics.values()]
    all_switches = [m["switch_rate"] for m in session_metrics.values()]
    all_dom = [m["dominant_ratio"] for m in session_metrics.values()]
    all_stab = [m["stability_score"] for m in session_metrics.values()]

    return {
        "_meta": {
            "experiment_id": "lab_cluster_stability",
            "total_step_embeddings": len(step_indices),
            "n_clusters": N_CLUSTERS,
            "n_sessions": len(session_metrics),
            "cluster_sizes": [int(s) for s in cluster_sizes],
            "embedding_source": "BGE-M3 via ChromaDB",
            "method": "k-means on per-step reasoning embeddings, then within-session cluster transition analysis",
        },
        "global_summary": {
            "mean_entropy_norm": round(float(np.mean(all_ents)), 4),
            "mean_switch_rate": round(float(np.mean(all_switches)), 4),
            "mean_dominant_ratio": round(float(np.mean(all_dom)), 4),
            "mean_stability_score": round(float(np.mean(all_stab)), 4),
        },
        "by_model": _agg(model_stability),
        "by_strategy": _agg(strategy_stability),
        "by_correctness_bucket": _agg(correctness_stability),
        "by_narration_outcome": _agg(failure_stability),
    }


if __name__ == "__main__":
    results = compute()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(results, indent=2, default=str))
    print(f"Wrote: {OUTPUT_PATH}")
    print(f"  Sessions: {results.get('_meta', {}).get('n_sessions', '?')}")
    print(f"  Step embeddings: {results.get('_meta', {}).get('total_step_embeddings', '?')}")
    gs = results.get("global_summary", {})
    print(f"  Mean entropy: {gs.get('mean_entropy_norm', '?')}")
    print(f"  Mean switch rate: {gs.get('mean_switch_rate', '?')}")
    print(f"  Mean dominant ratio: {gs.get('mean_dominant_ratio', '?')}")
    print(f"  Mean stability score: {gs.get('mean_stability_score', '?')}")
