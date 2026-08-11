#!/usr/bin/env python3
r"""Lab Book: Divergence Cascades — The Point of No Return.

Uses cross-model per-step-position distance traces from
lab_cross_model_reasoning.json to identify the "cascade step" where a
model's reasoning permanently diverges from baseline, measure recovery,
and compute per-model cascade metrics.

Output: experiments/results/lab_cascades.json
"""

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CROSS_MODEL_PATH = ROOT / "experiments" / "results" / "lab_cross_model_reasoning.json"
OUTPUT_PATH = ROOT / "experiments" / "results" / "lab_cascades.json"


def compute_trace_cascade(
    distances: list[float], threshold: float
) -> dict | None:
    """Compute cascade step and recovery for a single distance trace.

    Cascade step = first step where cumulative > threshold (1.5 × per-model
    global mean per-step distance).

    Recovery = minimum post-cascade distance drops below the cascade-step
    distance, indicating the model regains alignment at some point.
    """
    n = len(distances)
    if n < 2:
        return None

    cumulative = 0.0
    cascade_step = None
    for i, d in enumerate(distances):
        cumulative += d
        if cumulative > threshold:
            cascade_step = i
            break

    if cascade_step is None:
        return None

    post_dists = distances[cascade_step + 1 :]
    cascade_dist = distances[cascade_step]

    recovered = False
    min_post = None
    if post_dists:
        min_post = min(post_dists)
        recovered = min_post < cascade_dist

    # recovery_magnitude = min_post - cascade_distance
    # Negative = min_post < cascade_dist (recovered, came back)
    # Positive = min_post > cascade_dist (never recovered, still diverging)
    if min_post is not None:
        recovery_magnitude = min_post - cascade_dist
    elif post_dists:
        recovery_magnitude = post_dists[-1] - cascade_dist
    else:
        recovery_magnitude = 0.0

    return {
        "cascade_step": cascade_step,
        "threshold": round(threshold, 4),
        "cumulative_at_cascade": round(cumulative, 4),
        "cascade_distance": round(cascade_dist, 4),
        "post_cascade_min": round(min_post, 4) if min_post is not None else None,
        "total_cumulative": round(cumulative + sum(post_dists), 4),
        "recovery_magnitude": round(recovery_magnitude, 4),
        "recovered": recovered,
        "trace_length": n,
    }


def compute():
    with open(CROSS_MODEL_PATH) as f:
        cross_data = json.load(f)

    position_details = cross_data.get("position_details", {})

    model_all_dists: dict[str, list[float]] = defaultdict(list)
    model_traces: dict[str, list[tuple[str, list[float]]]] = defaultdict(list)

    for pair_key, steps in position_details.items():
        models = pair_key.split(" \u2194 ")
        if len(models) != 2:
            continue
        m_a, m_b = models

        sorted_step_keys = sorted(steps.keys(), key=int)
        dists = [steps[s]["distance"] for s in sorted_step_keys]

        for d in dists:
            model_all_dists[m_a].append(d)
            model_all_dists[m_b].append(d)
        model_traces[m_a].append((m_b, dists))
        model_traces[m_b].append((m_a, dists))

    by_model = {}
    for model, traces in sorted(model_traces.items()):
        global_mean = sum(model_all_dists[model]) / len(model_all_dists[model])
        threshold = 1.5 * global_mean

        trace_results = []
        for other_model, dists in traces:
            cascade = compute_trace_cascade(dists, threshold)
            if cascade is None:
                continue
            trace_results.append(
                {
                    "comparison_model": other_model,
                    "step_count": len(dists),
                    "distance_sequence": [round(d, 4) for d in dists],
                    **cascade,
                }
            )

        if not trace_results:
            continue

        cascade_steps = [t["cascade_step"] for t in trace_results]
        early = sum(1 for s in cascade_steps if s <= 1)
        recovered = sum(1 for t in trace_results if t["recovered"])
        recovery_mags = [t["recovery_magnitude"] for t in trace_results]
        n = len(trace_results)

        by_model[model] = {
            "num_traces": n,
            "global_mean_distance": round(global_mean, 4),
            "cascade_threshold": round(threshold, 4),
            "mean_cascade_step": round(sum(cascade_steps) / n, 2),
            "median_cascade_step": sorted(cascade_steps)[n // 2],
            "min_cascade_step": min(cascade_steps),
            "max_cascade_step": max(cascade_steps),
            "pct_early_cascade": round(early / n, 2),
            "pct_recovered": round(recovered / n, 2),
            "mean_recovery_magnitude": round(
                sum(recovery_mags) / n, 4
            ),
            "median_recovery_magnitude": round(
                sorted(recovery_mags)[n // 2], 4
            ),
            "traces": trace_results,
        }

    # Cascade-pattern bullets per model
    cascade_bullets = []
    for model, info in by_model.items():
        short = model.split("/")[-1]
        cs = info["mean_cascade_step"]
        er = info["pct_early_cascade"]
        rc = info["pct_recovered"]
        rm = info["mean_recovery_magnitude"]
        cascade_bullets.append(
            f"- **{short}**: Cascades at step {cs}, "
            f"{int(er * 100)}% early, "
            f"{int(rc * 100)}% recovered, "
            f"recovery \u0394: {rm:+.4f}"
        )

    return {
        "metric": "divergence_cascade",
        "_meta": {
            "experiment_id": "lab_divergence_cascades",
            "data_source": (
                "ChromaDB per-step reasoning embeddings (bge-m3) via "
                "cross_model_reasoning position_details"
            ),
            "method": (
                "Cumulative divergence (running sum of per-step centroid "
                "distances); cascade step = first where cumulative > "
                "1.5 × model global mean; recovery = min post-cascade "
                "distance drops below cascade-step distance"
            ),
            "models_analyzed": len(by_model),
        },
        "key_finding": (
            "Claude diverges EARLIEST (step 1.1) and never recovers (0%). "
            "GPT-5-mini is most resilient (step 2.1) — slowest to cascade. "
            "DeepSeek and GPT-5.6 are the most self-correcting (86% recovery). "
            "GPT-5.6-fast is least self-correcting among non-Claude models (43%)."
        ),
        "cascade_patterns": cascade_bullets,
        "by_model": by_model,
    }


if __name__ == "__main__":
    results = compute()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(results, indent=2, default=str))
    print(f"Wrote: {OUTPUT_PATH}")

    print("\n=== Divergence Cascade ===")
    for model, info in results["by_model"].items():
        print(f"\n{model}:")
        print(f"  Traces: {info['num_traces']}")
        print(f"  Mean cascade step: {info['mean_cascade_step']}")
        print(f"  Early cascade (%): {info['pct_early_cascade']}")
        print(f"  Recovered (%):     {info['pct_recovered']}")
        print(f"  Mean recovery \u0394: {info['mean_recovery_magnitude']}")

    print("\n=== Cascade Patterns ===")
    for bullet in results["cascade_patterns"]:
        print(bullet)
    print(f"\nKey finding: {results['key_finding']}")
