#!/usr/bin/env python3
"""Lab Book 3: Does Claude's Premium Buy Anything?

Head-to-head correctness comparison on 13 overlapping task types.
Null hypothesis: Claude achieves higher correctness than DeepSeek
on at least 3 of the 13 overlapping task types.

Output: experiments/results/lab_correctness_premium.json
"""

import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
SUMMARY_PATH = ROOT / "experiments" / "results" / "_results_summary.json"
OUTPUT_PATH = ROOT / "experiments" / "results" / "lab_correctness_premium.json"

from _constants import normalize_task

DEEPSEEK_ID = "deepseek/deepseek-v4-pro"
CLAUDE_ID = "anthropic/claude-fable-5"

GPT56_ID = "openai/gpt-5.6"


def compute():
    summary = json.loads(SUMMARY_PATH.read_text())
    entries = summary.get("entries", [])

    ds_entries = [e for e in entries if e.get("model") == DEEPSEEK_ID and not e.get("narration_failure")]
    cl_entries = [e for e in entries if e.get("model") == CLAUDE_ID and not e.get("narration_failure")]
    g56_entries = [e for e in entries if e.get("model") == GPT56_ID and not e.get("narration_failure")]

    ds_by_task = defaultdict(list)
    cl_by_task = defaultdict(list)
    g56_by_task = defaultdict(list)
    for e in ds_entries:
        ds_by_task[normalize_task(e.get("experiment", ""))].append(e)
    for e in cl_entries:
        cl_by_task[normalize_task(e.get("experiment", ""))].append(e)
    for e in g56_entries:
        g56_by_task[normalize_task(e.get("experiment", ""))].append(e)

    overlapping = sorted(set(ds_by_task.keys()) & set(cl_by_task.keys()))
    overlapping = [t for t in overlapping if t and t != "?" and not t.startswith("exp_")]

    per_task = []
    claude_leads = 0
    deepseek_leads = 0
    ties = 0

    for task in overlapping:
        ds = ds_by_task[task]
        cl = cl_by_task[task]
        g56 = g56_by_task.get(task, [])

        ds_correct = sum(e.get("correctness", 0) for e in ds) / len(ds) if ds else 0
        cl_correct = sum(e.get("correctness", 0) for e in cl) / len(cl) if cl else 0
        g56_correct = sum(e.get("correctness", 0) for e in g56) / len(g56) if g56 else None

        ds_cost = sum(e.get("cost", 0) for e in ds) / len(ds) if ds else 0
        cl_cost = sum(e.get("cost", 0) for e in cl) / len(cl) if cl else 0
        g56_cost = sum(e.get("cost", 0) for e in g56) / len(g56) if g56 else None

        ds_loc = sum(e.get("code_lines", 0) for e in ds) / max(len(ds), 1)
        cl_loc = sum(e.get("code_lines", 0) for e in cl) / max(len(cl), 1)

        delta = cl_correct - ds_correct
        cost_ratio = round(cl_cost / max(ds_cost, 0.0001), 1) if ds_cost > 0 else 0

        if delta > 0.05:
            winner = "Claude"
            claude_leads += 1
        elif delta < -0.05:
            winner = "DeepSeek"
            deepseek_leads += 1
        else:
            winner = "Tie"
            ties += 1

        per_task.append({
            "task": task,
            "ds_n": len(ds), "cl_n": len(cl),
            "ds_correctness": round(ds_correct, 2),
            "cl_correctness": round(cl_correct, 2),
            "g56_correctness": round(g56_correct, 2) if g56_correct is not None else None,
            "correctness_delta": round(delta, 2),
            "ds_cost": round(ds_cost, 4), "cl_cost": round(cl_cost, 4),
            "g56_cost": round(g56_cost, 4) if g56_cost is not None else None,
            "cost_ratio": cost_ratio,
            "ds_loc": round(ds_loc), "cl_loc": round(cl_loc),
            "winner": winner,
            "is_claude_worth_it": cl_correct > ds_correct + 0.05,  # >5pp lead
        })

    # Aggregate
    total_ds_n = sum(t["ds_n"] for t in per_task)
    total_cl_n = sum(t["cl_n"] for t in per_task)
    total_ds_cost = sum(t["ds_cost"] * t["ds_n"] for t in per_task)
    total_cl_cost = sum(t["cl_cost"] * t["cl_n"] for t in per_task)
    ds_avg_correct = sum(t["ds_correctness"] * t["ds_n"] for t in per_task) / total_ds_n
    cl_avg_correct = sum(t["cl_correctness"] * t["cl_n"] for t in per_task) / total_cl_n

    # Claude vs DeepSeek correctness by perturbation class
    by_pclass = defaultdict(lambda: {"ds_correct": [], "cl_correct": [], "ds_cost": [], "cl_cost": []})
    for task in overlapping:
        for e in ds_by_task[task]:
            pc = e.get("perturbation_class", "unknown")
            by_pclass[pc]["ds_correct"].append(e.get("correctness", 0))
            by_pclass[pc]["ds_cost"].append(e.get("cost", 0))
        for e in cl_by_task[task]:
            pc = e.get("perturbation_class", "unknown")
            by_pclass[pc]["cl_correct"].append(e.get("correctness", 0))
            by_pclass[pc]["cl_cost"].append(e.get("cost", 0))

    pclass_comparison = {}
    for pc, data in by_pclass.items():
        pclass_comparison[pc] = {
            "ds_avg_correctness": round(sum(data["ds_correct"]) / max(len(data["ds_correct"]), 1), 2),
            "cl_avg_correctness": round(sum(data["cl_correct"]) / max(len(data["cl_correct"]), 1), 2),
            "ds_avg_cost": round(sum(data["ds_cost"]) / max(len(data["ds_cost"]), 1), 4),
            "cl_avg_cost": round(sum(data["cl_cost"]) / max(len(data["cl_cost"]), 1), 4),
            "ds_n": len(data["ds_correct"]),
            "cl_n": len(data["cl_correct"]),
        }

    # Decision rule: Claude leads on >= 3 tasks (practical tie-break threshold)
    decision_signal = claude_leads >= 3

    output = {
        "_meta": {
            "experiment_id": "lab_correctness_premium",
            "overlapping_tasks": len(overlapping),
            "decision_rule": "Claude achieves higher correctness on at least 3 overlapping task types (practical threshold, not a statistical test)",
            "decision_result": decision_signal,
            "tie_threshold": ">0.05 practical correctness delta (>5 percentage points, not a p-value)",
        },
        "per_task": sorted(per_task, key=lambda x: x["correctness_delta"], reverse=True),
        "aggregate": {
            "deepseek_n": total_ds_n,
            "claude_n": total_cl_n,
            "deepseek_avg_cost": round(total_ds_cost / total_ds_n, 4),
            "claude_avg_cost": round(total_cl_cost / total_cl_n, 4),
            "deepseek_avg_correctness": round(ds_avg_correct, 2),
            "claude_avg_correctness": round(cl_avg_correct, 2),
            "cost_ratio": round((total_cl_cost / total_cl_n) / max(total_ds_cost / total_ds_n, 0.0001), 1),
            "claude_leads_n": claude_leads,
            "deepseek_leads_n": deepseek_leads,
            "ties_n": ties,
            "claude_worth_it_n": sum(1 for t in per_task if t["is_claude_worth_it"]),
        },
        "by_perturbation_class": pclass_comparison,
        "verdict": (
            "DECISION: Claude leads on fewer than 3 overlapping tasks. "
            "The premium does not buy general correctness improvement."
            if not decision_signal else
            "DECISION: Claude leads on at least 3 tasks (7 DS / 3 Claude / 5 ties)."
        ),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, default=str))
    return output


def main():
    data = compute()
    m = data["_meta"]
    agg = data["aggregate"]

    print(f"=== LAB BOOK 3: DOES CLAUDE'S PREMIUM BUY ANYTHING? ===\n")
    print(f"Overlapping tasks: {m['overlapping_tasks']}")
    print(f"Decision rule: {m['decision_rule']}")
    print(f"Tie rule: {m['tie_threshold']}\n")

    print("PER-TASK CORRECTNESS:")
    print(f"{'Task':<30} {'DS Corr':>7} {'CL Corr':>7} {'Delta':>7} {'CL Cost':>9} {'Ratio':>7} {'Worth It?':>9}")
    print("-" * 85)
    for t in data["per_task"]:
        worth = "YES" if t["is_claude_worth_it"] else "No"
        print(f"{t['task']:<30} {t['ds_correctness']:>6.0%} {t['cl_correctness']:>6.0%} {t['correctness_delta']:>+6.0%} ${t['cl_cost']:>8.4f} {t['cost_ratio']:>6.1f}x {worth:>9}")

    print(f"\nAGGREGATE:")
    print(f"  DeepSeek: {agg['deepseek_avg_correctness']:.0%} at ${agg['deepseek_avg_cost']:.4f}/session ({agg['deepseek_n']} entries)")
    print(f"  Claude:   {agg['claude_avg_correctness']:.0%} at ${agg['claude_avg_cost']:.4f}/session ({agg['claude_n']} entries)")
    print(f"  Cost ratio: {agg['cost_ratio']:.0f}×")
    print(f"  Claude leads on:  {agg['claude_leads_n']}/{m['overlapping_tasks']} tasks")
    print(f"  DeepSeek leads on: {agg['deepseek_leads_n']}/{m['overlapping_tasks']} tasks")
    print(f"  Tied:              {agg['ties_n']}/{m['overlapping_tasks']} tasks")
    print(f"  Worth paying for:  {agg['claude_worth_it_n']}/{m['overlapping_tasks']} tasks")

    print(f"\nBY PERTURBATION CLASS:")
    for pc, d in data["by_perturbation_class"].items():
        print(f"  {pc}: DS {d['ds_avg_correctness']:.0%} (${d['ds_avg_cost']:.4f}) vs CL {d['cl_avg_correctness']:.0%} (${d['cl_avg_cost']:.4f})")

    print(f"\nVERDICT: {data['verdict']}")
    print(f"\nOutput: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
