#!/usr/bin/env python3
"""Lab Book 7: Attractor Basin Topology Profile

Classifies each model's attractor basin shape from existing escape,
correctness, and cost data. Infers behavioral topology from output
surface divergence patterns — not latent space geometry.

Ref: Munshi et al., "Manifold of Failure: Behavioral Attraction
Basins in Language Models," arXiv:2602.22291, 2026.

Output: experiments/results/lab_basin_topology.json
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUMMARY_PATH = ROOT / "experiments" / "results" / "_results_summary.json"
OUTPUT_PATH = ROOT / "experiments" / "results" / "lab_basin_topology.json"

from agentic_dynamics.core.constants import MODEL_LABELS


def compute_recovery_multiplier(entries, model_id, pert_class):
    """Compute cost ratio: perturbed / baseline per model per perturbation class."""
    baseline = [e for e in entries if e.get("model") == model_id
                and e.get("perturbation_class") in ("semantic", "manifold")
                and e.get("operator") == "baseline"
                and not e.get("narration_failure")]
    perturbed = [e for e in entries if e.get("model") == model_id
                 and e.get("perturbation_class") == pert_class
                 and e.get("operator") != "baseline"
                 and not e.get("narration_failure")]
    if not baseline or not perturbed:
        return None
    bl_cost = sum(e.get("cost", 0) for e in baseline) / len(baseline)
    pt_cost = sum(e.get("cost", 0) for e in perturbed) / len(perturbed)
    if bl_cost <= 0:
        return None
    return round(pt_cost / bl_cost, 3)


def classify_basin(escape, correctness, recovery_mult, flail_rate):
    """Classify attractor basin shape from behavioral metrics."""
    if flail_rate >= 50:
        return "collapsed", "Basin collapsed — model cannot recover from perturbation. >50% flail rate."
    if recovery_mult is None or recovery_mult <= 0:
        recovery_mult = 1.0
    if escape < 0.25 and correctness >= 0.85 and recovery_mult < 1.5:
        return "wide_shallow", "Wide, shallow basin — explores efficiently at low cost. GRPO/MoE signature."
    if escape < 0.25 and correctness >= 0.85 and recovery_mult >= 1.5:
        return "narrow_deep", "Narrow, deep basin — stays close to familiar patterns. Recovery is expensive. SFT/single-provider cluster."
    if escape >= 0.25 and correctness >= 0.80 and recovery_mult < 1.5:
        return "wide_moderate", "Wide, moderate basin — explores but maintains correctness. Reasonable recovery cost."
    if escape >= 0.25 and correctness >= 0.80 and recovery_mult >= 1.5:
        return "deep_expensive", "Deep basin, expensive exit — explores but at high cost to return."
    if correctness < 0.80:
        return "unstable", "Unstable basin — model cannot maintain correctness under perturbation."
    return "unclassified", "No clear basin pattern."


def compute():
    summary = json.loads(SUMMARY_PATH.read_text())
    entries = summary.get("entries", [])

    valid = [e for e in entries if not e.get("narration_failure") and e.get("correctness", 0) >= 0]
    all_entries = entries  # include narration failures for flail rate

    # Per-model, per-perturbation-class analysis
    model_profiles = {}
    for mid, label in MODEL_LABELS.items():
        model_entries = [e for e in all_entries if e.get("model") == mid]
        if not model_entries:
            continue

        total = len(model_entries)
        flail = sum(1 for e in model_entries if e.get("narration_failure"))
        flail_rate = round(flail / total * 100, 1) if total else 0

        basin_profiles = {}
        for pc in ["semantic", "manifold"]:
            pc_entries = [e for e in valid if e.get("model") == mid and e.get("perturbation_class") == pc]
            if len(pc_entries) < 3:
                continue

            n = len(pc_entries)
            escape = round(sum(e.get("escape", 0) for e in pc_entries) / n, 2)
            correctness = round(sum(e.get("correctness", 0) for e in pc_entries) / n, 2)
            cost = round(sum(e.get("cost", 0) for e in pc_entries) / n, 4)
            arch_div = round(sum(e.get("architecture_divergence", 0) for e in pc_entries) / n, 3)
            struct_div = round(sum(e.get("structure_divergence", 0) for e in pc_entries) / n, 3)
            novelty = round(sum(e.get("basin_novelty", 0) for e in pc_entries) / n, 3)
            tok = round(sum(e.get("tokens", 0) for e in pc_entries) / n)
            loc = round(sum(e.get("code_lines", 0) for e in pc_entries) / n)
            thinking = round(sum(e.get("thinking_ratio", 0) for e in pc_entries) / n, 3)

            recovery_mult = compute_recovery_multiplier(all_entries, mid, pc)
            if recovery_mult is None:
                recovery_mult = 1.0

            basin_volume = round((1 - escape) * correctness / max(recovery_mult, 0.001), 3)
            basin_type, basin_desc = classify_basin(escape, correctness, recovery_mult, flail_rate)

            basin_profiles[pc] = {
                "n": n,
                "escape": escape,
                "correctness": correctness,
                "cost": cost,
                "architecture_divergence": arch_div,
                "structure_divergence": struct_div,
                "novelty": novelty,
                "tokens": tok,
                "loc": loc,
                "thinking_ratio": thinking,
                "recovery_multiplier": recovery_mult,
                "basin_volume": basin_volume,
                "basin_type": basin_type,
                "basin_description": basin_desc,
            }

        # Overall profile combining both classes
        all_valid = [e for e in valid if e.get("model") == mid]
        if all_valid:
            overall_escape = round(sum(e.get("escape", 0) for e in all_valid) / len(all_valid), 2)
            overall_correctness = round(sum(e.get("correctness", 0) for e in all_valid) / len(all_valid), 2)
            overall_cost = round(sum(e.get("cost", 0) for e in all_valid) / len(all_valid), 4)
            overall_recovery = round(overall_cost / max(all([compute_recovery_multiplier(all_entries, mid, pc) for pc in ["semantic", "manifold"] if compute_recovery_multiplier(all_entries, mid, pc)] or [1.0]), 0.001), 3)
            round((1 - overall_escape) * overall_correctness / max(overall_recovery, 0.001), 3)

        model_profiles[label] = {
            "model_id": mid,
            "total_sessions": total,
            "valid_sessions": len(all_valid),
            "flail_count": flail,
            "flail_rate": flail_rate,
            "overall_escape": overall_escape,
            "overall_correctness": overall_correctness,
            "overall_cost": overall_cost,
            "basin_profiles": basin_profiles,
        }

    # Cross-model comparison
    model_ranking = sorted(
        [(label, p.get("basin_profiles", {}).get("semantic", {}).get("basin_volume", 0))
         for label, p in model_profiles.items()],
        key=lambda x: x[1], reverse=True
    )

    output = {
        "_meta": {
            "experiment_id": "lab_basin_topology",
            "method": "Behavioral topology inferred from output surface divergence patterns. Not latent space geometry.",
            "reference": "Munshi et al., 'Manifold of Failure: Behavioral Attraction Basins in Language Models,' arXiv:2602.22291, 2026",
            "basin_types": {
                "wide_shallow": "Low escape, high correctness, low recovery cost — explores efficiently (GRPO/MoE signature)",
                "narrow_deep": "Low escape, high correctness, high recovery cost — stays close to patterns (SFT/single-provider cluster)",
                "wide_moderate": "Moderate escape, good correctness, reasonable recovery cost",
                "deep_expensive": "Moderate escape, high recovery cost — exploration is expensive",
                "unstable": "Cannot maintain correctness under perturbation",
                "collapsed": "Cannot recover from perturbation (>50% flail rate)",
            },
            "basin_volume_formula": "(1 - escape) × correctness / recovery_multiplier",
        },
        "model_profiles": model_profiles,
        "basin_volume_ranking": [{"model": m, "basin_volume": v} for m, v in model_ranking],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, default=str))
    return output


def main():
    data = compute()
    m = data["_meta"]

    print("=== LAB BOOK 7: ATTRACTOR BASIN TOPOLOGY PROFILE ===\n")
    print(f"Reference: {m['reference']}")
    print(f"Method: {m['method']}")
    print(f"Volume formula: {m['basin_volume_formula']}\n")

    print("BASIN TOPOLOGY BY MODEL:")
    print(f"{'Model':<22} {'Class':<10} {'Type':<16} {'Escape':>7} {'Correct':>8} {'RecMult':>8} {'Volume':>7} {'Flail':>6}")
    print("-" * 95)
    for label, p in sorted(data["model_profiles"].items()):
        flail = p["flail_rate"]
        for pc, bp in sorted(p.get("basin_profiles", {}).items()):
            print(f"{label:<22} {pc:<10} {bp['basin_type']:<16} {bp['escape']:>7.2f} {bp['correctness']:>7.0%} {bp['recovery_multiplier']:>7.2f}x {bp['basin_volume']:>7.3f} {flail:>5.1f}%")

    print("\nBASIN VOLUME RANKING (semantic):")
    for i, r in enumerate(data["basin_volume_ranking"]):
        print(f"  {i+1}. {r['model']}: {r['basin_volume']:.3f}")

    print("\nBASIN TYPE DISTRIBUTION:")
    type_counts = {}
    for p in data["model_profiles"].values():
        for bp in p.get("basin_profiles", {}).values():
            t = bp["basin_type"]
            type_counts[t] = type_counts.get(t, 0) + 1
    for t, c in sorted(type_counts.items()):
        desc = m["basin_types"].get(t, "")
        print(f"  {t}: {c} profiles — {desc[:80]}")

    print(f"\nOutput: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
