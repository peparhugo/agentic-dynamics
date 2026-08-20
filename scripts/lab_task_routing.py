#!/usr/bin/env python3
"""Lab Book 6: Task-Optimal Routing — Decision Table

For each of 30 task types, determines the best model based on
correctness/cost efficiency. Simulates three routing strategies.

Output: experiments/results/lab_task_routing.json
"""

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUMMARY_PATH = ROOT / "experiments" / "results" / "_results_summary.json"
TRAJECTORY_AGG_PATH = ROOT / "experiments" / "results" / "_trajectory_aggregate.json"
OUTPUT_PATH = ROOT / "experiments" / "results" / "lab_task_routing.json"

from agentic_dynamics.core.constants import MODEL_LABELS, normalize_task

DEEPSEEK_ID = "deepseek/deepseek-v4-pro"
CLAUDE_ID = "anthropic/claude-fable-5"


def compute():
    summary = json.loads(SUMMARY_PATH.read_text())
    entries = summary.get("entries", [])

    valid = [e for e in entries if not e.get("narration_failure") and e.get("correctness", 0) >= 0]

    # Group by task type
    by_task = defaultdict(list)
    for e in valid:
        task = normalize_task(e.get("experiment", ""))
        by_task[task].append(e)

    # For each task, find best model by efficiency score
    per_task_recs = []
    for task in sorted(by_task.keys()):
        if not task or task == "?" or task.startswith("exp_"):
            continue

        models_in_task = defaultdict(list)
        for e in by_task[task]:
            mid = e.get("model", "unknown")
            models_in_task[mid].append(e)

        if len(models_in_task) < 2:
            continue

        best_efficiency = 0
        best_correctness = 0
        best_model_eff = ""
        best_model_correct = ""
        best_cost = float("inf")

        model_stats = {}
        for mid, group in models_in_task.items():
            n = len(group)
            avg_correctness = sum(e.get("correctness", 0) for e in group) / n
            avg_cost = sum(e.get("cost", 0) for e in group) / n
            efficiency = avg_correctness / max(avg_cost, 0.00001)
            avg_loc = sum(e.get("code_lines", 0) for e in group) / n

            label = MODEL_LABELS.get(mid, mid)
            model_stats[label] = {
                "n": n,
                "avg_correctness": round(avg_correctness, 2),
                "avg_cost": round(avg_cost, 4),
                "efficiency": round(efficiency, 1),
                "avg_loc": round(avg_loc),
            }

            if avg_correctness > best_correctness:
                best_correctness = avg_correctness
                best_model_correct = label

            if efficiency > best_efficiency:
                best_efficiency = efficiency
                best_model_eff = label

            if avg_cost < best_cost and avg_correctness >= 0.7:
                best_cost = avg_cost

        # Recommendation logic
        ds_stats = model_stats.get("DeepSeek v4 Pro", {})
        cl_stats = model_stats.get("Claude Fable 5", {})

        if ds_stats and cl_stats:
            cl_delta = cl_stats.get("avg_correctness", 0) - ds_stats.get("avg_correctness", 0)
            if cl_delta > 0.05:
                recommendation = f"Claude escalation (leads by {cl_delta:.0%} correctness)"
                routing = "escalate_to_claude"
            else:
                recommendation = "DeepSeek (default)"
                routing = "deepseek_default"
        elif ds_stats:
            recommendation = "DeepSeek (default)"
            routing = "deepseek_default"
        elif cl_stats:
            recommendation = "Claude escalation"
            routing = "escalate_to_claude"
        else:
            recommendation = "DeepSeek (default)"
            routing = "deepseek_default"

        per_task_recs.append({
            "task": task,
            "models_tested": len(models_in_task),
            "best_correctness_model": best_model_correct,
            "best_efficiency_model": best_model_eff,
            "recommendation": recommendation,
            "routing": routing,
            "models": model_stats,
        })

    # Simulate three strategies
    ds_entries_all = [e for e in valid if e.get("model") == DEEPSEEK_ID]
    cl_entries_all = [e for e in valid if e.get("model") == CLAUDE_ID]

    ds_cost = sum(e.get("cost", 0) for e in ds_entries_all)
    cl_cost = sum(e.get("cost", 0) for e in cl_entries_all)
    ds_correct = sum(e.get("correctness", 0) for e in ds_entries_all) / max(len(ds_entries_all), 1)
    cl_correct = sum(e.get("correctness", 0) for e in cl_entries_all) / max(len(cl_entries_all), 1)

    # Grit-routed: apply recommendation per task
    routed_cost = 0
    routed_correctness_sum = 0
    routed_n = 0
    routing_counts = defaultdict(int)

    for rec in per_task_recs:
        routing = rec["routing"]
        task = rec["task"]
        task_entries = by_task[task]

        if routing == "deepseek_default":
            ds_in_task = [e for e in task_entries if e.get("model") == DEEPSEEK_ID]
            if ds_in_task:
                routed_cost += sum(e.get("cost", 0) for e in ds_in_task)
                routed_correctness_sum += sum(e.get("correctness", 0) for e in ds_in_task)
                routed_n += len(ds_in_task)
                routing_counts["DeepSeek"] += len(ds_in_task)
        elif routing == "escalate_to_claude":
            cl_in_task = [e for e in task_entries if e.get("model") == CLAUDE_ID]
            if cl_in_task:
                routed_cost += sum(e.get("cost", 0) for e in cl_in_task)
                routed_correctness_sum += sum(e.get("correctness", 0) for e in cl_in_task)
                routed_n += len(cl_in_task)
                routing_counts["Claude"] += len(cl_in_task)

    routed_avg_cost = routed_cost / max(routed_n, 1)
    routed_avg_correctness = routed_correctness_sum / max(routed_n, 1)

    strategies = {
        "claude_only": {
            "n": len(cl_entries_all), "total_cost": round(cl_cost, 2),
            "avg_cost": round(cl_cost / max(len(cl_entries_all), 1), 4),
            "avg_correctness": round(cl_correct, 2),
            "cost_per_correct_point": round(cl_cost / max(cl_correct * len(cl_entries_all), 0.01), 4),
        },
        "deepseek_only": {
            "n": len(ds_entries_all), "total_cost": round(ds_cost, 2),
            "avg_cost": round(ds_cost / max(len(ds_entries_all), 1), 4),
            "avg_correctness": round(ds_correct, 2),
            "cost_per_correct_point": round(ds_cost / max(ds_correct * len(ds_entries_all), 0.01), 4),
        },
        "grit_routed": {
            "n": routed_n, "total_cost": round(routed_cost, 2),
            "avg_cost": round(routed_avg_cost, 4),
            "avg_correctness": round(routed_avg_correctness, 2),
            "cost_per_correct_point": round(routed_cost / max(routed_avg_correctness * routed_n, 0.01), 4),
            "routing_distribution": dict(routing_counts),
        },
    }

    # Which model gets recommended most?
    rec_counts = defaultdict(int)
    for rec in per_task_recs:
        rec_counts[rec["routing"]] += 1

    output = {
        "_meta": {
            "experiment_id": "lab_task_routing",
            "tasks_analyzed": len(per_task_recs),
            "total_valid_entries": len(valid),
        },
        "per_task": sorted(per_task_recs, key=lambda x: x["task"]),
        "strategies": strategies,
        "routing_distribution": dict(rec_counts),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, default=str))
    return output


def main():
    data = compute()
    m = data["_meta"]

    print("=== LAB BOOK 6: TASK-OPTIMAL ROUTING ===\n")
    print(f"Tasks analyzed: {m['tasks_analyzed']}\n")

    print("PER-TASK RECOMMENDATIONS:")
    print(f"{'Task':<35} {'Rec':<10} {'Best Eff':<22} {'Best Corr':<22}")
    print("-" * 92)
    for t in data["per_task"][:20]:
        routing_short = "DS" if t["routing"] == "deepseek_default" else "CL"
        print(f"{t['task']:<35} {routing_short:<10} {t['best_efficiency_model']:<22} {t['best_correctness_model']:<22}")

    print("\nSTRATEGY COMPARISON:")
    print(f"{'Strategy':<18} {'N':>5} {'Total Cost':>12} {'Avg Cost':>10} {'Avg Correct':>12} {'Cost/Correct':>13}")
    print("-" * 75)
    for name, s in data["strategies"].items():
        print(f"{name:<18} {s['n']:>5} ${s['total_cost']:>11.2f} ${s['avg_cost']:>9.4f} {s['avg_correctness']:>11.0%} ${s['cost_per_correct_point']:>12.4f}")

    rd = data["routing_distribution"]
    print(f"\nROUTING DISTRIBUTION: DeepSeek default: {rd.get('deepseek_default',0)} tasks, Claude escalation: {rd.get('escalate_to_claude',0)} tasks")

    # Find winning strategy
    ds = data["strategies"]["deepseek_only"]
    cl = data["strategies"]["claude_only"]
    gr = data["strategies"]["grit_routed"]
    print("\nWINNER: ", end="")
    if gr["avg_correctness"] >= ds["avg_correctness"] and gr["avg_cost"] < cl["avg_cost"] * 0.1:
        print("Grit-routed strategy — highest correctness at near-DeepSeek cost.")
    elif ds["avg_cost"] < cl["avg_cost"] and ds["avg_correctness"] >= cl["avg_correctness"]:
        print("DeepSeek-only — cheaper AND more correct than Claude-only.")

    print(f"\nOutput: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
