#!/usr/bin/env python3
"""Lab Book: Sonar Quality — does perturbation degrade static code quality?

Reads _results_summary.json and answers:
  1. Does perturbation introduce more bugs/smells/vulnerabilities?
  2. Which perturbation operators cause the most quality degradation?
  3. Which models write the most maintainable code under stress?
  4. Does higher thinking_ratio correlate with better sonar quality?

Usage:
    python scripts/lab_sonar_quality.py
    python scripts/lab_sonar_quality.py --summary /path/to/_results_summary.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SUMMARY = PROJECT_ROOT / "experiments" / "results" / "_results_summary.json"


def load_results(path: Path) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    return data.get("entries", [])


def lab_sonar_quality(results: list[dict]) -> dict:
    """Analyze sonar quality patterns across all experiment sessions."""
    valid = [r for r in results if r.get("sonar_analyzed")]

    if not valid:
        return {"error": "no results with sonar_analyzed=True", "n_total": len(results)}

    by_model = defaultdict(list)
    by_operator = defaultdict(list)
    by_class = defaultdict(list)

    for r in valid:
        m = r.get("model", "unknown")
        o = r.get("operator", "unknown")
        pc = r.get("perturbation_class", "unknown")
        by_model[m].append(r)
        by_operator[o].append(r)
        by_class[pc].append(r)

    def _avg(vals): return round(sum(vals) / len(vals), 2) if vals else 0

    def _model_summary(label, group):
        bugs = [r["sonar_bugs"] for r in group]
        smells = [r["sonar_code_smells"] for r in group]
        vulns = [r["sonar_vulnerabilities"] for r in group]
        complexity = [r["sonar_cognitive_complexity"] for r in group]
        dup = [r["sonar_duplicated_lines_density"] for r in group]
        quality = [r["sonar_quality_score"] for r in group]
        return {
            "n": len(group),
            "avg_bugs": _avg(bugs),
            "avg_smells": _avg(smells),
            "avg_vulnerabilities": _avg(vulns),
            "avg_cognitive_complexity": _avg(complexity),
            "avg_duplication_pct": _avg(dup),
            "avg_quality_score": _avg(quality),
        }

    diff_valid = [r for r in valid if r.get("sonar_bugs_delta", 0) > 0
                   or r.get("sonar_code_smells_delta", 0) > 0
                   or r.get("sonar_maintainability_delta", 0) > 0]

    by_model_diff = defaultdict(list)
    by_operator_diff = defaultdict(list)
    for r in diff_valid:
        by_model_diff[r.get("model", "?")].append(r)
        by_operator_diff[r.get("operator", "?")].append(r)

    def _diff_summary(label, group):
        bugs_d = [r["sonar_bugs_delta"] for r in group]
        smells_d = [r["sonar_code_smells_delta"] for r in group]
        maint_d = [r["sonar_maintainability_delta"] for r in group]
        dup_d = [r["sonar_duplication_delta"] for r in group]
        return {
            "n": len(group),
            "avg_new_bugs": _avg(bugs_d),
            "avg_new_smells": _avg(smells_d),
            "avg_maintainability_degradation": _avg(maint_d),
            "avg_duplication_increase_pct": _avg(dup_d),
        }

    thinking_corr = None
    thinking_vals = [(r.get("thinking_ratio", 0), r.get("sonar_quality_score", 0.5)) for r in valid]
    if len(thinking_vals) >= 3:
        from math import sqrt
        n = len(thinking_vals)
        sx = sum(t for t, _ in thinking_vals)
        sy = sum(q for _, q in thinking_vals)
        sxx = sum(t * t for t, _ in thinking_vals)
        syy = sum(q * q for _, q in thinking_vals)
        sxy = sum(t * q for t, q in thinking_vals)
        denom = sqrt(max(n * sxx - sx * sx, 0.01) * max(n * syy - sy * sy, 0.01))
        thinking_corr = round((n * sxy - sx * sy) / denom, 4) if denom else None

    output = {
        "total_entries": len(results),
        "sonar_analyzed": len(valid),
        "sonar_diffs_available": len(diff_valid),
        "thinking_ratio_vs_sonar_correlation": thinking_corr,
        "by_model": {m: _model_summary(m, g) for m, g in sorted(by_model.items())},
        "by_operator": {o: _model_summary(o, g) for o, g in sorted(by_operator.items())},
        "by_perturbation_class": {c: _model_summary(c, g) for c, g in sorted(by_class.items())},
        "quality_degradation": {
            "by_model": {m: _diff_summary(m, g) for m, g in sorted(by_model_diff.items())},
            "by_operator": {o: _diff_summary(o, g) for o, g in sorted(by_operator_diff.items())},
        },
    }
    return output


def format_output(data: dict) -> str:
    """Render lab book results as a readable text summary."""
    if "error" in data:
        return f"Error: {data['error']} (out of {data.get('n_total', 0)} entries)"

    lines = [
        "=" * 80,
        "LAB BOOK: Sonar Quality",
        "=" * 80,
        "",
        f"Total entries: {data['total_entries']}",
        f"With Sonar analysis: {data['sonar_analyzed']}",
        f"With differential quality (baseline vs perturbed): {data['sonar_diffs_available']}",
    ]

    if data.get("thinking_ratio_vs_sonar_correlation") is not None:
        lines.append(f"Thinking ratio vs Sonar quality correlation: {data['thinking_ratio_vs_sonar_correlation']}")
        if data["thinking_ratio_vs_sonar_correlation"] > 0.3:
            lines.append("  → More thinking correlates with better code quality")
        elif data["thinking_ratio_vs_sonar_correlation"] < -0.3:
            lines.append("  → More thinking correlates with worse code quality (narration?)")
        else:
            lines.append("  → No strong linear correlation")

    lines += [
        "",
        "---",
        "",
        "Per-Model Sonar Quality",
        "",
        "| Model | N | Avg Bugs | Avg Smells | Avg Vulns | Avg Complexity | Duplication% | Quality Score |",
        "|-------|---|----------|------------|-----------|----------------|-------------|---------------|",
    ]
    for m, s in sorted(data["by_model"].items()):
        model_short = m.split("/")[-1] if "/" in m else m
        lines.append(
            f"| {model_short[:25]} | {s['n']} | {s['avg_bugs']:.1f} | {s['avg_smells']:.1f} | "
            f"{s['avg_vulnerabilities']:.1f} | {s['avg_cognitive_complexity']:.1f} | "
            f"{s['avg_duplication_pct']:.1f}% | {s['avg_quality_score']:.3f} |"
        )

    if data["sonar_diffs_available"] > 0:
        lines += [
            "",
            "---",
            "",
            "Quality Degradation (Perturbed vs Baseline)",
            "",
            "Per-Model Diff:",
            "",
            "| Model | N | New Bugs | New Smells | Maint. Degradation | Duplication Increase |",
            "|-------|---|----------|------------|-------------------|----------------------|",
        ]
        for m, s in sorted(data["quality_degradation"]["by_model"].items()):
            if s["n"] == 0:
                continue
            model_short = m.split("/")[-1] if "/" in m else m
            lines.append(
                f"| {model_short[:25]} | {s['n']} | +{s['avg_new_bugs']:.1f} | "
                f"+{s['avg_new_smells']:.1f} | +{s['avg_maintainability_degradation']:.1f} levels | "
                f"+{s['avg_duplication_increase_pct']:.1f}% |"
            )

        lines += [
            "",
            "Per-Operator Diff:",
            "",
            "| Operator | N | New Bugs | New Smells | Maint. Degradation | Duplication Increase |",
            "|----------|---|----------|------------|-------------------|----------------------|",
        ]
        for o, s in sorted(data["quality_degradation"]["by_operator"].items()):
            if s["n"] == 0:
                continue
            lines.append(
                f"| {o[:25]} | {s['n']} | +{s['avg_new_bugs']:.1f} | "
                f"+{s['avg_new_smells']:.1f} | +{s['avg_maintainability_degradation']:.1f} levels | "
                f"+{s['avg_duplication_increase_pct']:.1f}% |"
            )

    lines += [
        "",
        "---",
        "",
        "Per-Operator Quality:",
        "",
        "| Operator | N | Quality Score |",
        "|----------|---|---------------|",
    ]
    for o, s in sorted(data["by_operator"].items()):
        lines.append(f"| {o[:30]} | {s['n']} | {s['avg_quality_score']:.3f} |")

    lines += [
        "",
        "Per-Class Quality:",
        "",
        "| Class | N | Quality Score |",
        "|-------|---|---------------|",
    ]
    for c, s in sorted(data["by_perturbation_class"].items()):
        lines.append(f"| {c[:30]} | {s['n']} | {s['avg_quality_score']:.3f} |")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Lab Book: Sonar Quality degradation analysis")
    ap.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY,
                     help="Path to _results_summary.json")
    ap.add_argument("--json", action="store_true", help="Output raw JSON instead of formatted text")
    args = ap.parse_args()

    if not args.summary.exists():
        print(f"Error: summary file not found: {args.summary}")
        print("Run analyze_worktrees.py with sonar enabled first.")
        sys.exit(1)

    results = load_results(args.summary)
    data = lab_sonar_quality(results)

    if args.json:
        print(json.dumps(data, indent=2, default=str))
    else:
        print(format_output(data))


if __name__ == "__main__":
    main()
