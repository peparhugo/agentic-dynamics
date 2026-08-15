#!/usr/bin/env python3
"""Lab Book: Semantic Drift Trajectories

Computes within-session cumulative embedding drift from step 0 to each
successive step. Classifies each trajectory as convergent, divergent,
bounce, or flat.

Output: experiments/results/lab_drift.json
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from _constants import MODEL_LABELS

from instrument.embeddings import ChromaStore

OUTPUT_PATH = ROOT / "experiments" / "results" / "lab_drift.json"


def cosine_distance(a, b):
    dot = float(np.dot(a, b))
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return float(1.0 - dot / (norm_a * norm_b))


def classify_trajectory(drifts):
    """Classify a drift trajectory based on trend + oscillation.

    Uses first-half vs second-half mean shift as primary signal,
    backed by linear regression slope for edge cases.
    """
    n = len(drifts)
    if n < 3:
        return "flat"

    # Flat: all drifts < 0.1 (never leaves origin)
    if max(drifts) < 0.1:
        return "flat"

    mid = n // 2
    first_half = drifts[1:mid] if mid > 1 else drifts[1:2]
    second_half = drifts[mid:] if n - mid > 1 else drifts[-1:]

    first_mean = float(np.mean(first_half)) if first_half else 0
    second_mean = float(np.mean(second_half)) if second_half else 0
    mean_shift = second_mean - first_mean

    steps = np.arange(n)
    slope = float(np.polyfit(steps[1:], drifts[1:], 1)[0]) if n > 2 else 0.0

    # Strong divergent: meaningful growth in second half
    if mean_shift > 0.06 and slope > 0.003:
        return "divergent"

    # Convergent: drift is shrinking back
    if mean_shift < -0.04 or (slope < -0.003 and drifts[-1] < drifts[1] * 0.7):
        return "convergent"

    # Bounce: high oscillation amplitude with no clear trend
    std_val = float(np.std(drifts[1:]))
    if std_val > 0.07:
        return "bounce"

    # Mild growth
    if mean_shift > 0.03 and slope > 0.002:
        return "divergent"

    return "convergent"


def compute():
    store = ChromaStore()
    results = store.collection.get(include=["embeddings", "metadatas"])

    by_session = defaultdict(list)
    for i, id_ in enumerate(results["ids"]):
        parts = id_.rsplit("_step_", 1)
        if len(parts) != 2:
            continue
        session_id = parts[0]
        step_idx = int(parts[1])
        by_session[session_id].append({
            "step_idx": step_idx,
            "embedding": results["embeddings"][i],
            "metadata": results["metadatas"][i],
        })

    for sid in by_session:
        by_session[sid].sort(key=lambda x: x["step_idx"])

    # Load summary
    summary = json.loads((ROOT / "experiments" / "results" / "_results_summary.json").read_text())
    wt_to_entry = {}
    for e in summary["entries"]:
        wt = e.get("worktree_name", "")
        if wt:
            wt_to_entry[wt] = e

    # Per-model accumulators
    shapes_by_model = defaultdict(lambda: {"convergent": 0, "divergent": 0, "bounce": 0, "flat": 0})
    terminal_drifts_by_model = defaultdict(list)
    shapes_by_class = defaultdict(lambda: {"convergent": 0, "divergent": 0, "bounce": 0, "flat": 0})
    correctness_by_shape = defaultdict(list)

    all_trajectories = []

    for session_id, steps in sorted(by_session.items()):
        if len(steps) < 5:
            continue
        if session_id not in wt_to_entry:
            continue

        entry = wt_to_entry[session_id]
        model = entry.get("model", "?")
        pert_class = entry.get("perturbation_class", "?")
        correctness = entry.get("correctness", 0)

        step0_emb = steps[0]["embedding"]
        drifts = [0.0]
        for step in steps[1:]:
            emb = step["embedding"]
            d = cosine_distance(step0_emb, emb)
            drifts.append(round(d, 6))

        shape = classify_trajectory(drifts)
        terminal_drift = drifts[-1]

        shapes_by_model[model][shape] += 1
        terminal_drifts_by_model[model].append(terminal_drift)
        shapes_by_class[pert_class][shape] += 1
        correctness_by_shape[shape].append(correctness)

        all_trajectories.append({
            "session_id": session_id,
            "model": model,
            "perturbation_class": pert_class,
            "shape": shape,
            "n_steps": len(steps),
            "drifts": drifts,
            "terminal_drift": terminal_drift,
            "correctness": correctness,
        })

    # Build per-model summary
    by_model = {}
    for model_id, label in MODEL_LABELS.items():
        shapes = shapes_by_model.get(model_id)
        if shapes is None or sum(shapes.values()) == 0:
            continue
        drifts_list = terminal_drifts_by_model[model_id]
        by_model[label] = {
            **shapes,
            "mean_terminal_drift": round(float(np.mean(drifts_list)), 4) if drifts_list else 0.0,
            "n_sessions": sum(shapes.values()),
        }

    # Per perturbation class summary
    by_class = {}
    for pc in ["semantic", "manifold"]:
        shapes = shapes_by_class.get(pc)
        if shapes is None or sum(shapes.values()) == 0:
            by_class[pc] = {"convergent": 0, "divergent": 0, "bounce": 0, "flat": 0}
            continue
        by_class[pc] = dict(shapes)

    # Drift vs correctness
    drift_correctness = {}
    for shape in ["convergent", "divergent", "bounce", "flat"]:
        vals = correctness_by_shape.get(shape, [])
        drift_correctness[f"{shape}_sessions_mean_correctness"] = (
            round(float(np.mean(vals)), 4) if vals else 0.0
        )

    # Additional per-model drift + correctness correlation
    model_drift_correctness = {}
    for model_id, label in MODEL_LABELS.items():
        model_trajs = [t for t in all_trajectories if t["model"] == model_id]
        if not model_trajs:
            continue
        corr = 0.0
        if len(model_trajs) >= 3:
            dr = np.array([t["terminal_drift"] for t in model_trajs])
            co = np.array([t["correctness"] for t in model_trajs])
            corr_mat = np.corrcoef(dr, co)
            if corr_mat.shape == (2, 2):
                corr = round(float(corr_mat[0, 1]), 4)
        avg_drift = round(float(np.mean([t["terminal_drift"] for t in model_trajs])), 4)
        avg_correct = round(float(np.mean([t["correctness"] for t in model_trajs])), 4)
        model_drift_correctness[label] = {
            "mean_drift": avg_drift,
            "mean_correctness": avg_correct,
            "drift_correctness_pearson": corr,
            "n": len(model_trajs),
        }

    output = {
        "metric": "semantic_drift_trajectory",
        "_meta": {
            "total_sessions_analyzed": sum(shapes_by_model[m]["convergent"] + shapes_by_model[m]["divergent"] +
                                            shapes_by_model[m]["bounce"] + shapes_by_model[m]["flat"]
                                            for m in shapes_by_model),
            "min_steps_threshold": 5,
            "distance_metric": "cosine_distance",
            "embedding_model": "bge-m3",
        },
        "by_model": by_model,
        "by_perturbation_class": by_class,
        "drift_vs_correctness": drift_correctness,
        "model_drift_correctness": model_drift_correctness,
        "trajectories": all_trajectories,
    }

    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    return output


if __name__ == "__main__":
    result = compute()
    print(f"Analyzed {result['_meta']['total_sessions_analyzed']} sessions")
    print()
    print("Per-model shape distribution:")
    for model, data in sorted(result["by_model"].items()):
        shapes = {k: data[k] for k in ["convergent", "divergent", "bounce", "flat"]}
        drift = data["mean_terminal_drift"]
        print(f"  {model}: {shapes} | mean_drift={drift}")
    print()
    print("Drift vs Correctness:")
    for k, v in result["drift_vs_correctness"].items():
        print(f"  {k}: {v}")
