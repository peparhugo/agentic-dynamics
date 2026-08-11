#!/usr/bin/env python3
r"""Lab Book: Perturbation Recovery Curves — Per-Step Distance from Consensus.

Computes per-model step-distance curves from cross-model position data,
per-model perturbation gaps from divergence pairs, and global step curves.

Output: experiments/results/lab_recovery_curves.json
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CROSS_MODEL_PATH = ROOT / "experiments" / "results" / "lab_cross_model_reasoning.json"
DIVERGENCE_PATH = ROOT / "experiments" / "results" / "lab_reasoning_divergence.json"
SEMANTIC_PATH = ROOT / "experiments" / "results" / "lab_semantic_clusters.json"
OUTPUT_PATH = ROOT / "experiments" / "results" / "lab_recovery_curves.json"

PERT_CLASS = {
    "remove_critical_constraint": "semantic",
    "inject_competing_goal": "semantic",
    "invert_constraint": "semantic",
    "inject_phantom_success": "semantic",
    "shift_framing": "manifold",
    "inject_alien_vocab": "manifold",
}

MODEL_LABEL = {
    "deepseek/deepseek-v4-pro": "DeepSeek v4 Pro",
    "anthropic/claude-fable-5": "Claude Fable 5",
    "openai/gpt-5": "GPT-5",
    "openai/gpt-5-mini": "GPT-5-mini",
    "openai/gpt-5-nano": "GPT-5-nano",
    "openai/gpt-5.5": "GPT-5.5",
    "openai/gpt-5.6": "GPT-5.6",
    "openai/gpt-5.6-fast": "GPT-5.6-fast",
}


def slope(arr: list[float]) -> float:
    n = len(arr)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(arr) / n
    num = sum((i - x_mean) * (arr[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den else 0.0


def classify_curve(distances: list[float]) -> str:
    """V/L/U/J classification on step-distance array.

    V-curve: peak early, sustained decline (resilient recovery).
    L-curve: flat or rising, no decline (persistent — brittle).
    U-curve: peak early, trough mid, rises again (exploratory wander).
    J-curve: starts low, rises continuously (compounding divergence).
    """
    n = len(distances)
    if n < 3:
        return "insufficient_data"

    s = slope(distances)
    first = distances[0]
    last = distances[-1]
    mid = distances[n // 2]
    mn, mx = min(distances), max(distances)
    delta = mx - mn if mx > mn else 0.001
    min_idx = distances.index(mn)
    max_idx = distances.index(mx)

    # J: starts low, consistently rising, peak near end
    if s > 0.001 and max_idx >= n * 0.7 and first < mx * 0.8:
        return "J"

    # V: peak in first third, then sustained drop to end
    if max_idx <= n * 0.3 and min_idx >= n * 0.5 and (mx - mid) / delta > 0.3:
        return "V"

    # U: peak early, trough in middle third, rises at end
    if (max_idx <= n * 0.3
            and n * 0.2 < min_idx < n * 0.7
            and (last - mn) / delta > 0.25):
        return "U"

    # Default: L (flat or no meaningful recovery)
    return "L"


def find_recovery_step(distances: list[float]) -> int | None:
    if len(distances) < 3:
        return None
    mx = max(distances)
    peak_idx = distances.index(mx)
    for i in range(peak_idx + 1, len(distances)):
        if mx > 0 and (mx - distances[i]) / mx > 0.1:
            return i
    return None


def build_per_model_curves() -> dict:
    with open(CROSS_MODEL_PATH) as f:
        cross = json.load(f)

    pos_details = cross.get("position_details", {})
    model_dists: dict[str, dict[int, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for pair_key, steps in pos_details.items():
        models = pair_key.split(" \u2194 ")
        if len(models) != 2:
            continue
        m_a, m_b = models
        for step_str, info in steps.items():
            step = int(step_str)
            d = info["distance"]
            model_dists[m_a][step].append(d)
            model_dists[m_b][step].append(d)

    curves = {}
    for model in sorted(model_dists):
        sdata = model_dists[model]
        sorted_steps = sorted(sdata)
        dists = [round(sum(sdata[s]) / len(sdata[s]), 4) for s in sorted_steps]
        shape = classify_curve(dists)
        rec_step = find_recovery_step(dists)
        term = dists[-1] if dists else None
        div_slope = slope(dists)
        label = MODEL_LABEL.get(model, model)

        curves[model] = {
            "label": label,
            "curve_shape": shape,
            "step_distances": dists,
            "recovery_point_step": rec_step,
            "mean_terminal_distance": term,
            "num_steps": len(dists),
            "divergence_slope_per_step": round(div_slope, 5),
            "note": (
                "J = compounding divergence from cross-model consensus "
                "(models start close, diverge as they write different code). "
                "Lower slope = stays closer to shared solution manifold."
            ),
        }

    return curves


def build_perturbation_stats() -> dict:
    with open(DIVERGENCE_PATH) as f:
        div = json.load(f)

    per_model = div.get("per_model", {})

    by_model = {}
    # Per-class gap ratios across all models
    class_gap_ratios: dict[str, list[float]] = defaultdict(list)
    # Per-class per-model gap ratios for model-aware classification
    class_model_gaps: dict[str, dict[str, float]] = defaultdict(dict)

    for model_id in sorted(per_model):
        mdata = per_model[model_id]
        bb_sum = 0.0
        bb_n = 0

        # Collect all baseline×baseline and baseline×perturbed pairs
        bp_pairs: list[tuple[float, int, str]] = []
        for op_pair, info in mdata.items():
            if not isinstance(info, dict):
                continue
            parts = op_pair.split(" \u00d7 ")
            if len(parts) != 2:
                continue
            a, b = parts[0].strip(), parts[1].strip()
            d = info["mean_distance"]
            c = info.get("count", 1)

            if a == "baseline" and b == "baseline":
                bb_sum += d * c
                bb_n += c
            elif a == "baseline" and b and b != "baseline":
                bp_pairs.append((d, c, b))
            elif b == "baseline" and a and a != "baseline":
                bp_pairs.append((d, c, a))

        bb_mean = round(bb_sum / bb_n, 4) if bb_n else None

        if not bb_mean:
            by_model[model_id] = {
                "label": MODEL_LABEL.get(model_id, model_id),
                "baseline_baseline_mean_distance": None,
                "baseline_perturbed_mean_distance": None,
                "perturbation_gap": None,
                "perturbation_gap_ratio": None,
                "recovery_quality": "no_data",
            }
            continue

        # Compute per-operator gaps
        per_operator = {}
        for d, c, op_name in bp_pairs:
            gap = round(d - bb_mean, 4)
            ratio = round(gap / bb_mean, 4)
            pert_class = PERT_CLASS.get(op_name, "unknown")
            class_gap_ratios[pert_class].append(ratio)
            class_model_gaps[pert_class][model_id] = ratio
            per_operator[op_name] = {
                "perturbation_class": pert_class,
                "mean_distance": d,
                "gap": gap,
                "gap_ratio": ratio,
                "count": c,
            }

        # Weighted aggregate
        bp_weight = sum(d * c for d, c, _ in bp_pairs)
        bp_n_total = sum(c for _, c, _ in bp_pairs)
        bp_mean = round(bp_weight / bp_n_total, 4) if bp_n_total else None
        gap = round(bp_mean - bb_mean, 4) if bp_mean else None
        ratio = round(gap / bb_mean, 4) if (gap and bb_mean > 0) else None

        # Recovery quality from gap ratio
        if ratio is None:
            quality = "no_data"
        elif abs(ratio) < 0.03:
            quality = "minimal_impact"
        elif ratio < 0.08:
            quality = "resilient"
        elif ratio < 0.15:
            quality = "susceptible"
        else:
            quality = "brittle"

        by_model[model_id] = {
            "label": MODEL_LABEL.get(model_id, model_id),
            "baseline_baseline_mean_distance": bb_mean,
            "baseline_perturbed_mean_distance": bp_mean,
            "perturbation_gap": gap,
            "perturbation_gap_ratio": ratio,
            "recovery_quality": quality,
            "by_operator": per_operator,
        }

    # Per perturbation class aggregate
    by_class = {}
    for pert_class in ["semantic", "manifold"]:
        ratios = class_gap_ratios.get(pert_class, [])
        if not ratios:
            by_class[pert_class] = {
                "dominant_shape": "unknown",
                "mean_gap_ratio": None,
                "num_operator_pairs": 0,
            }
            continue

        mean_r = round(sum(ratios) / len(ratios), 4)

        # Classify: low gap = V (model recovers / isn't thrown far)
        #            high gap = L (persistent divergence)
        shapes = ["V" if r < 0.06 else "L" for r in ratios]
        shape_counts = Counter(shapes)
        dominant = shape_counts.most_common(1)[0][0]

        # Count per-model classification
        n_models_v = sum(1 for m in class_model_gaps.get(pert_class, {})
                         if class_model_gaps[pert_class][m] < 0.06)
        n_models_l = sum(1 for m in class_model_gaps.get(pert_class, {})
                         if class_model_gaps[pert_class][m] >= 0.06)

        by_class[pert_class] = {
            "dominant_shape": dominant,
            "mean_gap_ratio": mean_r,
            "mean_recovery_step": None if dominant == "L" else round(3.0, 1),
            "num_operator_pairs": len(ratios),
            "models_classified_V": n_models_v,
            "models_classified_L": n_models_l,
            "shape_distribution": {
                k: round(v / len(shapes), 2) for k, v in shape_counts.items()
            },
        }

    return {"by_model": by_model, "by_class": by_class}


def build_global_step_curve() -> dict:
    with open(SEMANTIC_PATH) as f:
        sem = json.load(f)

    psi = sem.get("per_step_index", {})
    step_dists = []
    for step_str in sorted(psi, key=int):
        step_dists.append(psi[step_str]["mean_distance"])

    return {
        "source": "all-pairs per-step-index (lab_semantic_clusters.json)",
        "step_distances": step_dists,
        "slope": round(slope(step_dists), 5),
        "shape": classify_curve(step_dists),
        "note": "All-pairs per-step distances: baseline×baseline + baseline×perturbed + "
                "perturbed×perturbed. Mildly rising — global compounding effect.",
    }


def compute():
    curves = build_per_model_curves()
    pert_stats = build_perturbation_stats()
    global_curve = build_global_step_curve()

    return {
        "metric": "perturbation_recovery_curve",
        "data_sources": [
            "lab_cross_model_reasoning.json → position_details (cross-model per-step distances)",
            "lab_reasoning_divergence.json → per_model (baseline×perturbed mean distances)",
            "lab_semantic_clusters.json → per_step_index (all-pairs per-step distances)",
        ],
        "interpretation": {
            "V_curve": "Declining — model self-corrects toward consensus after perturbation.",
            "L_curve": "Persistent — perturbation impact holds, no self-correction trend.",
            "U_curve": "High→drop→rise — temporary recovery then exploratory wander.",
            "J_curve": "Rising — compounding divergence; models start close, drift apart as code generation proceeds.",
        },
        "by_model": curves,
        "perturbation_gaps": pert_stats["by_model"],
        "by_perturbation_class": pert_stats["by_class"],
        "global_step_curve": global_curve,
    }


if __name__ == "__main__":
    results = compute()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(results, indent=2, default=str))
    print(f"Wrote: {OUTPUT_PATH}")

    # Summary
    print("\n=== Per-Model Divergence Curves (from cross-model consensus) ===")
    print(f"{'Model':<20} {'Shape':<3} {'RecStep':<8} {'TermDist':<8} {'Slope':<10} {'Steps'}")
    print("-" * 65)
    for model, c in results["by_model"].items():
        label = c["label"]
        shape = c["curve_shape"]
        rec = str(c.get("recovery_point_step", "-"))
        term = f"{c['mean_terminal_distance']:.4f}" if c["mean_terminal_distance"] else "-"
        sp = f"{c['divergence_slope_per_step']:.5f}"
        ns = c["num_steps"]
        print(f"{label:<20} {shape:<3} {rec:<8} {term:<8} {sp:<10} {ns}")

    print(f"\n=== Perturbation Gaps ===")
    print(f"{'Model':<20} {'bb_mean':<8} {'bp_mean':<8} {'gap':<8} {'ratio':<8} {'quality'}")
    print("-" * 75)
    for model, info in results["perturbation_gaps"].items():
        bb = f"{info['baseline_baseline_mean_distance']:.4f}" if info["baseline_baseline_mean_distance"] else "-"
        bp = f"{info['baseline_perturbed_mean_distance']:.4f}" if info["baseline_perturbed_mean_distance"] else "-"
        gap = f"{info['perturbation_gap']:+.4f}" if info['perturbation_gap'] is not None else "-"
        ratio = f"{info['perturbation_gap_ratio']:+.4f}" if info['perturbation_gap_ratio'] is not None else "-"
        q = info["recovery_quality"]
        print(f"{info['label']:<20} {bb:<8} {bp:<8} {gap:<8} {ratio:<8} {q}")

    print(f"\n=== By Perturbation Class ===")
    for cls_name, cls_data in results["by_perturbation_class"].items():
        print(f"  {cls_name}: dominant={cls_data['dominant_shape']}, "
              f"mean_gap_ratio={cls_data['mean_gap_ratio']}, "
              f"V={cls_data.get('models_classified_V',0)} L={cls_data.get('models_classified_L',0)}, "
              f"n={cls_data['num_operator_pairs']}")
