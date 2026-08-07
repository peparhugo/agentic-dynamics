#!/usr/bin/env python3
"""Lab Book 4: What Makes a Model Flail?

Analyzes narration failure patterns across models, perturbation classes,
and task types. Identifies common triggers for flail behavior.

Output: experiments/results/lab_flail_triggers.json
"""

import json
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parent.parent
SUMMARY_PATH = ROOT / "experiments" / "results" / "_results_summary.json"
TRAJECTORY_PATH = ROOT / "experiments" / "results" / "_trajectory_summary.json"
OUTPUT_PATH = ROOT / "experiments" / "results" / "lab_flail_triggers.json"

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


def normalize_task(experiment: str) -> str:
    exp = experiment
    for suffix in ["_s0.5", "_s0.3", "_s0.7", "_r1", "_r2", "_r3", "_r4"]:
        if exp.endswith(suffix):
            exp = exp[: -len(suffix)]
    return exp


def compute():
    summary = json.loads(SUMMARY_PATH.read_text())
    entries = summary.get("entries", [])

    # Load trajectory data for flail entries
    trajectory_data = {}
    if TRAJECTORY_PATH.exists():
        traj = json.loads(TRAJECTORY_PATH.read_text())
        for t in traj:
            name = t.get("report_name", "")
            if name:
                trajectory_data[name] = t

    # Flail entries
    flail = [e for e in entries if e.get("narration_failure")]
    valid = [e for e in entries if not e.get("narration_failure") and e.get("correctness", 0) >= 0]

    # Per-model flail rate
    model_total = Counter()
    model_flail = Counter()
    for e in entries:
        m = e.get("model", "unknown")
        model_total[m] += 1
        if e.get("narration_failure"):
            model_flail[m] += 1

    model_breakdown = {}
    for mid, label in MODEL_LABELS.items():
        total = model_total.get(mid, 0)
        flail_n = model_flail.get(mid, 0)
        flail_entries = [e for e in flail if e.get("model") == mid]
        avg_cost_when_flailing = sum(e.get("cost", 0) for e in flail_entries) / max(len(flail_entries), 1) if flail_entries else 0
        model_breakdown[label] = {
            "total": total,
            "flail_count": flail_n,
            "flail_rate": round(flail_n / total * 100, 1) if total else 0,
            "avg_cost_when_flailing": round(avg_cost_when_flailing, 4),
        }

    # Per-perturbation-class flail rate
    pc_total = Counter()
    pc_flail = Counter()
    for e in entries:
        pc = e.get("perturbation_class", "unknown")
        pc_total[pc] += 1
        if e.get("narration_failure"):
            pc_flail[pc] += 1

    pc_breakdown = {}
    for pc in sorted(pc_total.keys()):
        total = pc_total[pc]
        flail_n = pc_flail[pc]
        pc_breakdown[pc] = {
            "total": total,
            "flail_count": flail_n,
            "flail_rate": round(flail_n / total * 100, 1) if total else 0,
        }

    # Per-task-type flail rate (top tasks only)
    task_total = Counter()
    task_flail = Counter()
    for e in entries:
        task = normalize_task(e.get("experiment", ""))
        task_total[task] += 1
        if e.get("narration_failure"):
            task_flail[task] += 1

    task_breakdown = {}
    for task, total in task_total.most_common(15):
        flail_n = task_flail.get(task, 0)
        task_breakdown[task] = {
            "total": total,
            "flail_count": flail_n,
            "flail_rate": round(flail_n / total * 100, 1) if total else 0,
        }

    # Flail signature: analyze trajectory data for flail sessions
    flail_with_traj = []
    for e in flail:
        wt_name = e.get("worktree_name", "")
        traj = trajectory_data.get(wt_name, {})
        flail_with_traj.append({
            "worktree": wt_name,
            "model": MODEL_LABELS.get(e.get("model", ""), e.get("model", "")),
            "cost": e.get("cost", 0),
            "reasoning_chars": traj.get("reasoning_chars", 0),
            "step_count": traj.get("step_count", 0),
            "output_tokens": traj.get("total_output_tokens", 0),
            "write_calls": traj.get("write_calls", 0),
            "read_calls": traj.get("read_calls", 0),
            "bash_calls": traj.get("bash_calls", 0),
            "code_density": traj.get("code_density", 0),
            "experiment": e.get("experiment", ""),
            "perturbation_class": e.get("perturbation_class", ""),
        })

    # Flail signature stats
    has_reasoning = sum(1 for f in flail_with_traj if f["reasoning_chars"] > 500)
    has_no_writes = sum(1 for f in flail_with_traj if f["write_calls"] == 0)
    short_sessions = sum(1 for f in flail_with_traj if 0 < f["step_count"] < 5)
    read_only = sum(1 for f in flail_with_traj if f["read_calls"] > 0 and f["write_calls"] == 0)

    output = {
        "_meta": {
            "experiment_id": "lab_flail_triggers",
            "total_entries": len(entries),
            "flail_entries": len(flail),
            "valid_entries": len(valid),
            "overall_flail_rate": round(len(flail) / len(entries) * 100, 1),
        },
        "by_model": model_breakdown,
        "by_perturbation_class": pc_breakdown,
        "by_task_type": task_breakdown,
        "flail_signature": {
            "total_flail_entries": len(flail_with_traj),
            "produced_reasoning_but_no_code": has_reasoning,
            "never_wrote_files": has_no_writes,
            "short_sessions_under_5_steps": short_sessions,
            "read_only_no_writes": read_only,
        },
        "flail_details": flail_with_traj,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, default=str))
    return output


def main():
    data = compute()
    m = data["_meta"]

    print(f"=== LAB BOOK 4: WHAT MAKES A MODEL FLAIL? ===\n")
    print(f"Total entries: {m['total_entries']}  |  Flail: {m['flail_entries']}  |  Valid: {m['valid_entries']}")
    print(f"Overall flail rate: {m['overall_flail_rate']}%\n")

    print("FLAIL RATE BY MODEL:")
    print(f"{'Model':<22} {'Total':>6} {'Flail':>6} {'Rate':>7} {'Avg Cost/Flail':>14}")
    print("-" * 59)
    for label, d in sorted(data["by_model"].items(), key=lambda x: x[1]["flail_rate"], reverse=True):
        print(f"{label:<22} {d['total']:>6} {d['flail_count']:>6} {d['flail_rate']:>6.1f}% ${d['avg_cost_when_flailing']:>13.4f}")

    print(f"\nFLAIL RATE BY PERTURBATION CLASS:")
    for pc, d in sorted(data["by_perturbation_class"].items(), key=lambda x: x[1]["flail_rate"], reverse=True):
        print(f"  {pc}: {d['flail_count']}/{d['total']} = {d['flail_rate']:.1f}%")

    print(f"\nTOP TASK TYPES BY FLAIL RATE:")
    for task, d in sorted(data["by_task_type"].items(), key=lambda x: x[1]["flail_rate"], reverse=True)[:8]:
        print(f"  {task:<40} {d['flail_count']}/{d['total']} = {d['flail_rate']:.1f}%")

    sig = data["flail_signature"]
    print(f"\nFLAIL SIGNATURE (of {sig['total_flail_entries']} flail sessions):")
    print(f"  Produced >500 reasoning chars but no code: {sig['produced_reasoning_but_no_code']}")
    print(f"  Never wrote files:                         {sig['never_wrote_files']}")
    print(f"  Short sessions (<5 steps):                  {sig['short_sessions_under_5_steps']}")
    print(f"  Read only (never wrote):                    {sig['read_only_no_writes']}")

    print(f"\nOutput: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
