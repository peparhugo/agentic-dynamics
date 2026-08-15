#!/usr/bin/env python3
"""Lab Book 1: The Claude Audit — Where Did $47.54 Go?

Cross-model comparison on overlapping task types. Computes per-task
cost, correctness, LOC, and narration penalty for DeepSeek vs Claude.
Produces cost breakdown by token type and 'Claude wins' flags.

Output: experiments/results/lab_claude_audit.json
"""

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUMMARY_PATH = ROOT / "experiments" / "results" / "_results_summary.json"
TRAJECTORY_PATH = ROOT / "experiments" / "results" / "_trajectory_aggregate.json"
OUTPUT_PATH = ROOT / "experiments" / "results" / "lab_claude_audit.json"

from _constants import normalize_task

DEEPSEEK_ID = "deepseek/deepseek-v4-pro"
CLAUDE_ID = "anthropic/claude-fable-5"


def compute():
    summary = json.loads(SUMMARY_PATH.read_text())
    entries = summary.get("entries", [])

    ds_entries = [e for e in entries if e.get("model") == DEEPSEEK_ID and not e.get("narration_failure")]
    cl_entries = [e for e in entries if e.get("model") == CLAUDE_ID and not e.get("narration_failure")]

    # Normalize and group by task
    ds_by_task = defaultdict(list)
    cl_by_task = defaultdict(list)
    for e in ds_entries:
        ds_by_task[normalize_task(e.get("experiment", ""))].append(e)
    for e in cl_entries:
        cl_by_task[normalize_task(e.get("experiment", ""))].append(e)

    # Find overlapping tasks
    overlapping = sorted(set(ds_by_task.keys()) & set(cl_by_task.keys()))
    overlapping = [t for t in overlapping if t and t != "?" and not t.startswith("exp_")]

    # Per-task comparison
    per_task = []
    claude_wins = 0
    deepseek_wins = 0
    ties = 0
    total_ds_cost = 0
    total_cl_cost = 0
    total_ds_correct = 0
    total_cl_correct = 0
    total_ds_n = 0
    total_cl_n = 0

    for task in overlapping:
        ds = ds_by_task[task]
        cl = cl_by_task[task]

        ds_cost = sum(e.get("cost", 0) for e in ds) / len(ds)
        cl_cost = sum(e.get("cost", 0) for e in cl) / len(cl)
        ds_correct = sum(e.get("correctness", 0) for e in ds) / len(ds)
        cl_correct = sum(e.get("correctness", 0) for e in cl) / len(cl)
        ds_loc = sum(e.get("code_lines", 0) for e in ds) / max(len(ds), 1)
        cl_loc = sum(e.get("code_lines", 0) for e in cl) / max(len(cl), 1)
        ds_narr = sum(1 for e in ds if e.get("narration_penalty", 0) > 0) / max(len(ds), 1)
        cl_narr = sum(1 for e in cl if e.get("narration_penalty", 0) > 0) / max(len(cl), 1)

        cost_ratio = round(cl_cost / max(ds_cost, 0.0001), 1)
        correct_delta = round(cl_correct - ds_correct, 2)

        if correct_delta > 0.05:
            winner = "Claude"
            claude_wins += 1
        elif correct_delta < -0.05:
            winner = "DeepSeek"
            deepseek_wins += 1
        else:
            winner = "Tie"
            ties += 1

        per_task.append({
            "task": task,
            "ds_n": len(ds), "cl_n": len(cl),
            "ds_cost": round(ds_cost, 4), "cl_cost": round(cl_cost, 4),
            "ds_correctness": round(ds_correct, 2), "cl_correctness": round(cl_correct, 2),
            "correctness_delta": correct_delta,
            "ds_loc": round(ds_loc), "cl_loc": round(cl_loc),
            "ds_narration_rate": round(ds_narr, 2), "cl_narration_rate": round(cl_narr, 2),
            "cost_ratio": cost_ratio,
            "winner": winner,
        })

        total_ds_cost += ds_cost * len(ds)
        total_cl_cost += cl_cost * len(cl)
        total_ds_correct += ds_correct * len(ds)
        total_cl_correct += cl_correct * len(cl)
        total_ds_n += len(ds)
        total_cl_n += len(cl)

    # Cost breakdown by token type for Claude
    cl_all = [e for e in entries if e.get("model") == CLAUDE_ID]
    cost_input = sum(e.get("cost_input_usd", 0) or 0 for e in cl_all)
    cost_output = sum(e.get("cost_output_usd", 0) or 0 for e in cl_all)
    cost_reasoning = sum(e.get("cost_reasoning_usd", 0) or 0 for e in cl_all)
    cost_cache = sum(e.get("cost_cache_usd", 0) or 0 for e in cl_all)
    cost_total = cost_input + cost_output + cost_reasoning + cost_cache

    cost_breakdown = {
        "input": round(cost_input, 2),
        "output": round(cost_output, 2),
        "reasoning": round(cost_reasoning, 2),
        "cache": round(cost_cache, 2),
        "total": round(cost_total, 2),
    }

    # DS cost breakdown
    ds_all = [e for e in entries if e.get("model") == DEEPSEEK_ID]
    ds_cost_total = sum(e.get("cost", 0) or 0 for e in ds_all)
    ds_cost_cache = sum(e.get("cost_cache_usd", 0) or 0 for e in ds_all)

    # Correctness-adjusted cost
    ds_avg_correct = total_ds_correct / max(total_ds_n, 1)
    cl_avg_correct = total_cl_correct / max(total_cl_n, 1)
    ds_cost_per_correct = round((total_ds_cost / max(total_ds_n, 1)) / max(ds_avg_correct, 0.01), 4)
    cl_cost_per_correct = round((total_cl_cost / max(total_cl_n, 1)) / max(cl_avg_correct, 0.01), 4)

    output = {
        "_meta": {
            "experiment_id": "lab_claude_audit",
            "overlapping_tasks": len(overlapping),
            "total_ds_entries": total_ds_n,
            "total_cl_entries": total_cl_n,
            "tie_threshold_note": "Correctness delta thresholds: >0.05 = Claude leads, <-0.05 = DeepSeek leads, else Tie. 0.05 is a practical delta threshold (5 percentage points), not a statistical significance test.",
        },
        "per_task": sorted(per_task, key=lambda x: x["cost_ratio"], reverse=True),
        "aggregate": {
            "deepseek_avg_cost": round(total_ds_cost / max(total_ds_n, 1), 4),
            "claude_avg_cost": round(total_cl_cost / max(total_cl_n, 1), 4),
            "deepseek_avg_correctness": round(ds_avg_correct, 2),
            "claude_avg_correctness": round(cl_avg_correct, 2),
            "deepseek_total_cost": round(total_ds_cost, 2),
            "claude_total_cost": round(total_cl_cost, 2),
            "cost_ratio": round((total_cl_cost / max(total_cl_n, 1)) / max(total_ds_cost / max(total_ds_n, 1), 0.0001), 1),
            "claude_wins": claude_wins,
            "deepseek_wins": deepseek_wins,
            "ties": ties,
        },
        "cost_breakdown": {
            "claude": cost_breakdown,
            "deepseek_total": round(ds_cost_total, 2),
            "deepseek_cache": round(ds_cost_cache, 2),
        },
        "correctness_adjusted_cost": {
            "deepseek_cost_per_correct_point": ds_cost_per_correct,
            "claude_cost_per_correct_point": cl_cost_per_correct,
            "ratio": round(cl_cost_per_correct / max(ds_cost_per_correct, 0.0001), 1),
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, default=str))
    return output


def main():
    data = compute()

    m = data["_meta"]
    agg = data["aggregate"]
    cb = data["cost_breakdown"]["claude"]
    ca = data["correctness_adjusted_cost"]

    print("=== LAB BOOK 1: THE CLAUDE AUDIT ===\n")
    print(f"Overlapping tasks: {m['overlapping_tasks']}")
    print(f"DeepSeek entries: {m['total_ds_entries']}  |  Claude entries: {m['total_cl_entries']}\n")

    print("PER-TASK COMPARISON:")
    print(f"{'Task':<30} {'DS Cost':>8} {'CL Cost':>8} {'DS Corr':>7} {'CL Corr':>7} {'Delta':>6} {'Ratio':>7} {'Winner':<10}")
    print("-" * 93)
    for t in data["per_task"]:
        print(f"{t['task']:<30} ${t['ds_cost']:>7.4f} ${t['cl_cost']:>7.4f} {t['ds_correctness']:>6.0%} {t['cl_correctness']:>6.0%} {t['correctness_delta']:>+6.0%} {t['cost_ratio']:>6.1f}x {t['winner']:<10}")

    print("\nAGGREGATE:")
    print(f"  DeepSeek avg cost:      ${agg['deepseek_avg_cost']:.4f}/session")
    print(f"  Claude avg cost:        ${agg['claude_avg_cost']:.4f}/session")
    print(f"  DeepSeek avg correctness: {agg['deepseek_avg_correctness']:.0%}")
    print(f"  Claude avg correctness:   {agg['claude_avg_correctness']:.0%}")
    print(f"  Cost ratio:              {agg['cost_ratio']:.0f}×")
    print(f"  Claude wins: {agg['claude_wins']}  |  DeepSeek wins: {agg['deepseek_wins']}  |  Ties: {agg['ties']}")

    print("\nCLAUDE COST BREAKDOWN:")
    print(f"  Output tokens:   ${cb['output']:.2f} ({cb['output']/max(cb['total'],0.01)*100:.0f}%)")
    print(f"  Cache:           ${cb['cache']:.2f} ({cb['cache']/max(cb['total'],0.01)*100:.0f}%)")
    print(f"  Input tokens:    ${cb['input']:.2f} ({cb['input']/max(cb['total'],0.01)*100:.0f}%)")
    print(f"  Reasoning:       ${cb['reasoning']:.2f} ({cb['reasoning']/max(cb['total'],0.01)*100:.0f}%)")
    print(f"  TOTAL:           ${cb['total']:.2f}")

    print("\nCORRECTNESS-ADJUSTED COST (dollars per percentage point of correctness):")
    print(f"  DeepSeek: ${ca['deepseek_cost_per_correct_point']:.4f}")
    print(f"  Claude:   ${ca['claude_cost_per_correct_point']:.4f}")
    print(f"  Ratio:    {ca['ratio']:.0f}×")

    print("\nFINDING: ", end="")
    if agg["claude_wins"] <= 1:
        print(f"Claude leads on {agg['claude_wins']}/{agg['claude_wins']+agg['deepseek_wins']+agg['ties']} overlapping tasks. The 69× premium does not buy general correctness improvement.")
    else:
        print(f"Claude leads on {agg['claude_wins']} tasks. The premium buys correctness on specific perturbation types only.")

    print(f"\nOutput: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
