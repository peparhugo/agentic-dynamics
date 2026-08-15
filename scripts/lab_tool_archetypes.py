#!/usr/bin/env python3
"""Lab Book 5: Tool-Choice Archetypes — Write vs Patch vs Bash

Compares code quality and correctness across models grouped by
dominant tool pattern (write-dominant, bash-dominant, balanced).
Cross-references trajectory tool percentages with worktree quality metrics.

Output: experiments/results/lab_tool_archetypes.json
"""

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUMMARY_PATH = ROOT / "experiments" / "results" / "_results_summary.json"
TRAJECTORY_AGG_PATH = ROOT / "experiments" / "results" / "_trajectory_aggregate.json"
OUTPUT_PATH = ROOT / "experiments" / "results" / "lab_tool_archetypes.json"

from _constants import MODEL_LABELS


def classify_archetype(write_pct, bash_pct):
    if write_pct > 40:
        return "write_dominant"
    if bash_pct > 40:
        return "bash_dominant"
    return "balanced"


def compute():
    summary = json.loads(SUMMARY_PATH.read_text())
    entries = summary.get("entries", [])

    # Load trajectory aggregate for tool percentages
    traj_agg = {}
    if TRAJECTORY_AGG_PATH.exists():
        ta = json.loads(TRAJECTORY_AGG_PATH.read_text())
        for key, val in ta.get("by_task_model", {}).items():
            traj_agg[key] = val

    # Per-model tool percentages from by_model section
    model_tools = {}
    if TRAJECTORY_AGG_PATH.exists():
        ta = json.loads(TRAJECTORY_AGG_PATH.read_text())
        for mid, agg in ta.get("by_model", {}).items():
            model_tools[mid] = {
                "write_pct": agg.get("avg_write_pct", 0),
                "read_pct": agg.get("avg_read_pct", 0),
                "bash_pct": agg.get("avg_bash_pct", 0),
                "avg_steps": agg.get("avg_steps", 0),
                "avg_tokens": agg.get("avg_tokens_per_session", 0),
                "avg_cost": agg.get("avg_cost_per_session", 0),
            }

    # Group valid entries by tool archetype
    valid = [e for e in entries if not e.get("narration_failure") and e.get("correctness", 0) >= 0]

    by_archetype = defaultdict(list)
    for e in valid:
        mid = e.get("model", "unknown")
        tools = model_tools.get(mid, {"write_pct": 0, "bash_pct": 0})
        archetype = classify_archetype(tools["write_pct"], tools["bash_pct"])
        by_archetype[archetype].append(e)

    # Aggregate per archetype
    archetype_agg = {}
    for arch, group in by_archetype.items():
        n = len(group)
        archetype_agg[arch] = {
            "n": n,
            "models": list(set(MODEL_LABELS.get(e.get("model", ""), e.get("model", "")) for e in group)),
            "avg_correctness": round(sum(e.get("correctness", 0) for e in group) / n, 2) if n else 0,
            "avg_cost": round(sum(e.get("cost", 0) for e in group) / n, 4) if n else 0,
            "avg_loc": round(sum(e.get("code_lines", 0) for e in group) / n) if n else 0,
            "avg_composite_score": round(sum(e.get("composite_score", 0) for e in group) / n, 2) if n else 0,
            "avg_code_quality": round(sum(e.get("code_quality_score", 0) for e in group) / n, 2) if n else 0,
            "avg_cyclomatic_complexity": round(sum(e.get("cyclomatic_complexity", 0) for e in group) / n, 1) if n else 0,
            "avg_comment_ratio": round(sum(e.get("comment_ratio", 0) for e in group) / n, 3) if n else 0,
            "avg_escape": round(sum(e.get("escape", 0) for e in group) / n, 2) if n else 0,
        }

    # Per-model tool details
    model_detail = {}
    for mid, label in MODEL_LABELS.items():
        tools = model_tools.get(mid, {})
        archetype = classify_archetype(tools.get("write_pct", 0), tools.get("bash_pct", 0))
        model_entries = [e for e in valid if e.get("model") == mid]
        n = len(model_entries)
        model_detail[label] = {
            "write_pct": tools.get("write_pct", 0),
            "read_pct": tools.get("read_pct", 0),
            "bash_pct": tools.get("bash_pct", 0),
            "archetype": archetype,
            "avg_steps": tools.get("avg_steps", 0),
            "avg_tokens": tools.get("avg_tokens", 0),
            "avg_cost": tools.get("avg_cost", 0),
            "n_entries": n,
            "avg_correctness": round(sum(e.get("correctness", 0) for e in model_entries) / n, 2) if n else 0,
            "avg_loc": round(sum(e.get("code_lines", 0) for e in model_entries) / n) if n else 0,
        }

    output = {
        "_meta": {
            "experiment_id": "lab_tool_archetypes",
            "total_valid_entries": len(valid),
            "archetype_labels": {
                "write_dominant": ">40% write calls — confident generation",
                "bash_dominant": ">40% bash calls — conservative modification",
                "balanced": "mix of tools — flexible approach",
            },
        },
        "by_archetype": archetype_agg,
        "by_model": model_detail,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, default=str))
    return output


def main():
    data = compute()
    m = data["_meta"]

    print("=== LAB BOOK 5: TOOL-CHOICE ARCHETYPES ===\n")
    print(f"Valid entries: {m['total_valid_entries']}\n")

    print("BY ARCHETYPE:")
    print(f"{'Archetype':<20} {'N':>5} {'Correct':>8} {'Cost':>9} {'LOC':>6} {'Quality':>8} {'Complex':>8} {'Escape':>7} {'Models':>30}")
    print("-" * 110)
    for arch, d in sorted(data["by_archetype"].items()):
        models_str = ", ".join(d["models"][:3])
        print(f"{arch:<20} {d['n']:>5} {d['avg_correctness']:>7.0%} ${d['avg_cost']:>8.4f} {d['avg_loc']:>6} {d['avg_code_quality']:>8.2f} {d['avg_cyclomatic_complexity']:>8.1f} {d['avg_escape']:>7.2f} {models_str:<30}")

    print("\nBY MODEL — TOOL PROFILES:")
    print(f"{'Model':<22} {'Write%':>7} {'Read%':>6} {'Bash%':>6} {'Archetype':<16} {'Steps':>6} {'Tokens':>9} {'Cost':>9} {'N':>4} {'Correct':>8} {'LOC':>5}")
    print("-" * 100)
    for label, d in sorted(data["by_model"].items()):
        print(f"{label:<22} {d['write_pct']:>6.1f}% {d['read_pct']:>5.1f}% {d['bash_pct']:>5.1f}% {d['archetype']:<16} {d['avg_steps']:>6.1f} {d['avg_tokens']:>9,} ${d['avg_cost']:>8.4f} {d['n_entries']:>4} {d['avg_correctness']:>7.0%} {d['avg_loc']:>5}")

    print(f"\nOutput: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
