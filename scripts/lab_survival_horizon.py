#!/usr/bin/env python3
"""Lab Book 8: Infinite Game Survival Horizon

Computes how many sessions a model can sustain before exhausting
a given budget, factoring in perturbation frequency and recovery costs.
The "infinite game" framing: survival horizon = budget / effective_cost.

Output: experiments/results/legacy_labs/lab_survival_horizon.json
"""

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUMMARY_PATH = ROOT / "experiments" / "results" / "_results_summary.json"
#: Quarantined lab (scripts/lab_manifest.json): its input is the RETIRED
#: _results_summary.json, so its output must never sit beside the contract-bearing
#: results. It writes into experiments/results/legacy_labs/ — see that directory's
#: README. Running this by hand is still supported; publishing it is not.
OUTPUT_PATH = ROOT / "experiments" / "results" / "legacy_labs" / "lab_survival_horizon.json"

from agentic_dynamics.core.constants import MODEL_LABELS

SCENARIOS = [
    {"label": "Low perturbation (5%) | $1,000 budget", "perturbation_rate": 0.05, "budget": 1000},
    {"label": "Moderate perturbation (20%) | $10,000 budget", "perturbation_rate": 0.20, "budget": 10000},
    {"label": "High perturbation (50%) | $10,000 budget", "perturbation_rate": 0.50, "budget": 10000},
    {"label": "Adversarial (80%) | $1,000 budget", "perturbation_rate": 0.80, "budget": 1000},
    {"label": "Enterprise annual | 20% perturbation | $100,000 budget", "perturbation_rate": 0.20, "budget": 100000},
    {"label": "Enterprise annual | 20% perturbation | $1,000,000 budget", "perturbation_rate": 0.20, "budget": 1000000},
]

RETRY_RATE = 0.115
ESCALATION_MULTIPLIER = 28.3


def compute():
    summary = json.loads(SUMMARY_PATH.read_text())
    entries = summary.get("entries", [])

    valid = [e for e in entries if not e.get("narration_failure") and e.get("correctness", 0) >= 0]

    # Per-model baseline and perturbed costs
    model_costs = {}
    for mid, label in MODEL_LABELS.items():
        model_entries = [e for e in valid if e.get("model") == mid]
        if not model_entries:
            continue

        baseline = [e for e in model_entries if e.get("operator") == "baseline"]
        perturbed = [e for e in model_entries if e.get("operator") != "baseline"]
        all_model = [e for e in entries if e.get("model") == mid]
        flail = sum(1 for e in all_model if e.get("narration_failure"))
        total = len(all_model)
        flail_rate = flail / max(total, 1)

        bl_cost = sum(e.get("cost", 0) for e in baseline) / max(len(baseline), 1)
        pt_cost = sum(e.get("cost", 0) for e in perturbed) / max(len(perturbed), 1)
        bl_correct = sum(e.get("correctness", 0) for e in baseline) / max(len(baseline), 1)
        pt_correct = sum(e.get("correctness", 0) for e in perturbed) / max(len(perturbed), 1)

        recovery_mult = round(pt_cost / max(bl_cost, 0.0001), 2) if bl_cost > 0 else 0
        overall_cost = sum(e.get("cost", 0) for e in model_entries) / max(len(model_entries), 1)
        overall_correct = sum(e.get("correctness", 0) for e in model_entries) / max(len(model_entries), 1)

        model_costs[label] = {
            "model_id": mid,
            "baseline_cost": round(bl_cost, 4),
            "perturbed_cost": round(pt_cost, 4),
            "overall_cost": round(overall_cost, 4),
            "baseline_correctness": round(bl_correct, 2),
            "perturbed_correctness": round(pt_correct, 2),
            "overall_correctness": round(overall_correct, 2),
            "recovery_multiplier": recovery_mult,
            "flail_rate": round(flail_rate, 3),
            "total_sessions": total,
            "valid_sessions": len(model_entries),
        }

    # Compute survival horizon per scenario
    scenario_results = []
    for scenario in SCENARIOS:
        rate = scenario["perturbation_rate"]
        budget = scenario["budget"]
        model_horizons = {}

        for label, mc in model_costs.items():
            flail = mc["flail_rate"]
            bl_cost = mc["baseline_cost"]
            pt_cost = mc["perturbed_cost"]
            rec_mult = mc["recovery_multiplier"]

            if bl_cost <= 0:
                model_horizons[label] = {"sessions": None, "days": None, "status": "no_baseline_data"}
                continue

            if flail >= 0.9:
                model_horizons[label] = {"sessions": 0, "days": 0, "status": "bankrupt_immediately",
                                         "reason": f"{flail*100:.0f}% flail rate — model cannot be trusted unsupervised"}
                continue

            # Effective cost accounts for perturbation frequency
            # baseline sessions cost baseline_cost
            # perturbed sessions cost perturbed_cost × recovery_multiplier
            # flail sessions cost their full cost (burn budget, produce nothing)
            effective_cost = (
                bl_cost * (1 - rate) * (1 - flail) +           # non-perturbed, non-flailing
                pt_cost * rate * (1 - flail) * rec_mult +     # perturbed, recovering
                bl_cost * (1 - rate) * flail +                # non-perturbed but flailing
                pt_cost * rate * flail                         # perturbed and flailing
            )

            if effective_cost <= 0:
                model_horizons[label] = {"sessions": None, "days": None, "status": "zero_cost"}
                continue

            sessions = int(budget / effective_cost)
            days_at_100_per_day = round(sessions / 100, 1) if sessions else 0

            model_horizons[label] = {
                "sessions": sessions,
                "days_at_100_per_day": days_at_100_per_day,
                "effective_cost_per_session": round(effective_cost, 4),
                "status": "sustainable" if sessions > 1000 else ("limited" if sessions > 100 else "critical"),
            }

        scenario_results.append({
            "scenario": scenario["label"],
            "perturbation_rate": rate,
            "budget": budget,
            "models": model_horizons,
        })

    # Cross-scenario summary: which models survive longest?
    survival_ranking = defaultdict(float)
    for sr in scenario_results:
        for label, mh in sr["models"].items():
            if mh.get("sessions"):
                survival_ranking[label] += mh["sessions"]

    output = {
        "_meta": {
            "experiment_id": "lab_survival_horizon",
            "concept": "Infinite game framing: survival horizon = budget / effective_cost_per_session. The model that lasts longest under perturbation wins.",
            "retry_rate": RETRY_RATE,
            "escalation_multiplier": ESCALATION_MULTIPLIER,
            "effective_cost_formula": "baseline_cost × (1-rate) × (1-flail) + perturbed_cost × rate × (1-flail) × recovery_mult + baseline_cost × (1-rate) × flail + perturbed_cost × rate × flail",
        },
        "model_costs": model_costs,
        "scenarios": scenario_results,
        "survival_ranking": sorted(
            [{"model": m, "total_sessions": int(s)} for m, s in survival_ranking.items()],
            key=lambda x: x["total_sessions"], reverse=True
        ),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, default=str))
    return output


def main():
    data = compute()
    m = data["_meta"]

    print("=== LAB BOOK 8: INFINITE GAME SURVIVAL HORIZON ===\n")
    print("Effective cost formula: baseline × (1-P) × (1-F) + perturbed × P × (1-F) × R + flail terms")
    print(f"Retry rate: {m['retry_rate']} | Escalation: {m['escalation_multiplier']}×\n")

    print("MODEL COST PROFILES:")
    print(f"{'Model':<22} {'BaseCost':>9} {'PertCost':>9} {'RecMult':>7} {'Correct':>8} {'Flail':>6}")
    print("-" * 70)
    for label, mc in sorted(data["model_costs"].items()):
        print(f"{label:<22} ${mc['baseline_cost']:>8.4f} ${mc['perturbed_cost']:>8.4f} {mc['recovery_multiplier']:>6.2f}x {mc['overall_correctness']:>7.0%} {mc['flail_rate']*100:>5.1f}%")

    print("\nSURVIVAL HORIZON — sessions before bankruptcy:")
    for sr in data["scenarios"]:
        print(f"\n  {sr['scenario']}:")
        models_sorted = sorted(sr["models"].items(), key=lambda x: x[1].get("sessions", 0) or 0, reverse=True)
        for label, mh in models_sorted:
            s = mh.get("sessions")
            if s is None:
                print(f"    {label:<22} N/A — {mh.get('reason', mh.get('status', ''))}")
            elif s >= 999999:
                print(f"    {label:<22} essentially infinite")
            else:
                days = mh.get("days_at_100_per_day", 0)
                print(f"    {label:<22} {s:>10,} sessions ({days:.0f} days at 100/day) [{mh.get('status','')}]")

    print("\nSURVIVAL RANKING (total sessions across all scenarios):")
    for i, r in enumerate(data["survival_ranking"]):
        print(f"  {i+1}. {r['model']}: {r['total_sessions']:,}")

    print(f"\nOutput: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
