#!/usr/bin/env python3
"""Lab Book 2: The Grit Matrix — Correctness × Escape × Cost

Builds a 2D bubble chart dataset showing where models cluster in the
correctness-escape space. Each point = one experiment entry. Bubble size = cost.

Output: experiments/results/lab_grit_matrix.json
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUMMARY_PATH = ROOT / "experiments" / "results" / "_results_summary.json"
OUTPUT_PATH = ROOT / "experiments" / "results" / "lab_grit_matrix.json"

from agentic_dynamics.core.constants import MODEL_LABELS

MODEL_COLORS = {
    "deepseek/deepseek-v4-pro": "rgba(52,211,153,0.75)",
    "openai/gpt-5-nano": "rgba(239,68,68,0.75)",
    "openai/gpt-5-mini": "rgba(239,68,68,0.60)",
    "openai/gpt-5": "rgba(251,191,36,0.75)",
    "openai/gpt-5.5": "rgba(251,191,36,0.60)",
    "openai/gpt-5.6": "rgba(59,130,246,0.75)",
    "openai/gpt-5.6-fast": "rgba(59,130,246,0.60)",
    "anthropic/claude-fable-5": "rgba(6,182,212,0.75)",
}


def compute():
    summary = json.loads(SUMMARY_PATH.read_text())
    entries = summary.get("entries", [])

    # Filter to valid entries
    valid = [e for e in entries if not e.get("narration_failure") and e.get("correctness", 0) >= 0 and e.get("escape") is not None]

    # Build data points
    points = []
    for e in valid:
        mid = e.get("model", "unknown")
        points.append({
            "model": mid,
            "label": MODEL_LABELS.get(mid, mid),
            "color": MODEL_COLORS.get(mid, "rgba(161,161,170,0.75)"),
            "escape": round(e.get("escape", 0), 2),
            "correctness": round(e.get("correctness", 0), 2),
            "cost": round(e.get("cost", 0), 4),
            "perturbation_class": e.get("perturbation_class", "unknown"),
            "task": e.get("experiment", "unknown")[:40],
            "loc": e.get("code_lines", 0),
            "thinking_ratio": round(e.get("thinking_ratio", 0), 2),
            "strategy": e.get("strategy", "unknown"),
        })

    # Compute quadrant boundaries (median of all valid entries)
    escapes = [p["escape"] for p in points]
    correctnesses = [p["correctness"] for p in points]
    mid_escape = sorted(escapes)[len(escapes) // 2] if escapes else 0.5
    mid_correctness = sorted(correctnesses)[len(correctnesses) // 2] if correctnesses else 0.5

    # Assign quadrants
    quadrants = {"high_grit": [], "explorative": [], "conservative_fail": [], "wasteful": []}
    for p in points:
        if p["correctness"] >= mid_correctness and p["escape"] <= mid_escape:
            p["quadrant"] = "high_grit"
            quadrants["high_grit"].append(p)
        elif p["correctness"] >= mid_correctness and p["escape"] > mid_escape:
            p["quadrant"] = "explorative"
            quadrants["explorative"].append(p)
        elif p["correctness"] < mid_correctness and p["escape"] <= mid_escape:
            p["quadrant"] = "conservative_fail"
            quadrants["conservative_fail"].append(p)
        else:
            p["quadrant"] = "wasteful"
            quadrants["wasteful"].append(p)

    # Per-model quadrant distribution
    model_quadrants = defaultdict(lambda: {"high_grit": 0, "explorative": 0, "conservative_fail": 0, "wasteful": 0, "total": 0})
    for p in points:
        q = p["quadrant"]
        model_quadrants[p["label"]][q] += 1
        model_quadrants[p["label"]]["total"] += 1

    # Per-model quadrant percentages
    model_quadrant_pct = {}
    for label, counts in model_quadrants.items():
        t = counts["total"]
        model_quadrant_pct[label] = {
            "high_grit_pct": round(counts["high_grit"] / t * 100, 1) if t else 0,
            "explorative_pct": round(counts["explorative"] / t * 100, 1) if t else 0,
            "conservative_fail_pct": round(counts["conservative_fail"] / t * 100, 1) if t else 0,
            "wasteful_pct": round(counts["wasteful"] / t * 100, 1) if t else 0,
            "total": t,
        }

    # Per-perturbation-class quadrant counts
    pc_quadrants = defaultdict(lambda: Counter())
    for p in points:
        pc_quadrants[p["perturbation_class"]][p["quadrant"]] += 1

    output = {
        "_meta": {
            "experiment_id": "lab_grit_matrix",
            "total_points": len(points),
            "models": len(model_quadrants),
            "quadrant_boundaries": {
                "escape_median": round(mid_escape, 2),
                "correctness_median": round(mid_correctness, 2),
            },
            "quadrant_labels": {
                "high_grit": "High correctness, low escape (ideal)",
                "explorative": "High correctness, high escape (explores but succeeds)",
                "conservative_fail": "Low correctness, low escape (didn't try)",
                "wasteful": "Low correctness, high escape (tried and failed)",
            },
        },
        "points": points,
        "quadrants": {k: len(v) for k, v in quadrants.items()},
        "model_quadrants": {
            label: dict(counts) for label, counts in model_quadrants.items()
        },
        "model_quadrant_percentages": model_quadrant_pct,
        "perturbation_class_quadrants": {
            pc: dict(counts) for pc, counts in pc_quadrants.items()
        },
        "chart_data": {
            "datasets": _build_chart_datasets(points),
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, default=str))
    return output


def _build_chart_datasets(points):
    """Build Chart.js bubble chart datasets grouped by model."""
    by_model = defaultdict(list)
    for p in points:
        by_model[p["label"]].append(p)

    datasets = []
    for label, pts in sorted(by_model.items()):
        mid = next((m for m, lbl in MODEL_LABELS.items() if lbl == label), None)
        color = MODEL_COLORS.get(mid, "rgba(161,161,170,0.75)")
        datasets.append({
            "label": label,
            "backgroundColor": color,
            "borderColor": color.replace("0.75", "1"),
            "borderWidth": 1,
            "data": [{
                "x": p["escape"],
                "y": p["correctness"],
                "r": max(3, p["cost"] * 15),
                "cost": p["cost"],
                "task": p["task"],
                "perturbation_class": p["perturbation_class"],
                "strategy": p["strategy"],
                "loc": p["loc"],
                "quadrant": p["quadrant"],
            } for p in pts],
        })
    return datasets


def main():
    data = compute()
    m = data["_meta"]

    print("=== LAB BOOK 2: THE GRIT MATRIX ===\n")
    print(f"Total points: {m['total_points']} across {m['models']} models")
    print(f"Quadrant boundaries: escape={m['quadrant_boundaries']['escape_median']}, correctness={m['quadrant_boundaries']['correctness_median']}\n")

    print("QUADRANT DISTRIBUTION:")
    for q, count in data["quadrants"].items():
        label = m["quadrant_labels"][q]
        print(f"  {q}: {count} entries — {label}")

    print("\nPER-MODEL QUADRANT PERCENTAGES:")
    print(f"{'Model':<22} {'High Grit':>10} {'Explorative':>12} {'Consv Fail':>12} {'Wasteful':>10}")
    print("-" * 70)
    for label, pct in sorted(data["model_quadrant_percentages"].items()):
        print(f"{label:<22} {pct['high_grit_pct']:>9.1f}% {pct['explorative_pct']:>11.1f}% {pct['conservative_fail_pct']:>11.1f}% {pct['wasteful_pct']:>9.1f}%")

    print("\nPERTURBATION CLASS QUADRANTS:")
    for pc, counts in data["perturbation_class_quadrants"].items():
        total = sum(counts.values())
        print(f"  {pc}: {total} entries — ", end="")
        parts = [f"{q}: {c}" for q, c in counts.items()]
        print(", ".join(parts))

    print(f"\nCHART DATA: {len(data['chart_data']['datasets'])} datasets ready for Chart.js bubble chart")
    print("  X-axis: escape rate (0-1)")
    print("  Y-axis: correctness (0-1)")
    print("  Bubble radius: cost ($0.001–$2.49 scaled ×15)")
    print("  Colors: DeepSeek=green, Claude=cyan, GPT-5.6=blue, nano=red, GPT-5=amber")

    print(f"\nOutput: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
