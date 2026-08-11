"""Aggregate DVS computation — compile all story results into a DVS summary.

Usage:
    python scripts/aggregate_dvs.py                        # Process all results
    python scripts/aggregate_dvs.py --results-dir DIR      # Custom results dir

Reads all story result JSONs, runs per-story analysis, and computes
Durable Value Scores grouped by story × condition × tier × quality.
Outputs experiments/results/dvs_summary.json for the evidence page.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from instrument.story import load_story_result, StoryResult
from instrument.commit_analysis import analyze_story_worktree
from instrument.entropy import compute_entropy
from instrument.codebase_graph import build_graph, compute_metrics
from instrument.value_score import compute_story_dvs, DurableValueScore


def main():
    results_dir = Path("experiments/results/stories")
    if "--results-dir" in sys.argv:
        idx = sys.argv.index("--results-dir")
        results_dir = Path(sys.argv[idx + 1])

    if not results_dir.exists():
        print(f"No results directory: {results_dir}")
        sys.exit(1)

    # Collect all story result JSONs
    result_files = sorted(results_dir.glob("*.json"))
    result_files = [f for f in result_files if "dvs_summary" not in f.name and "log" not in f.parent.name]

    if not result_files:
        print("No story results found. Have experiments completed?")
        sys.exit(1)

    print(f"Processing {len(result_files)} story results...")

    # Group by story + model
    cells: dict[str, list[StoryResult]] = defaultdict(list)

    for rf in result_files:
        try:
            story = load_story_result(rf)
            key = f"{story.story_name}_{story.model}"
            cells[key].append(story)
        except Exception as e:
            print(f"  Skipping {rf.name}: {e}")

    # Compute DVS per cell
    dvs_results: list[dict] = []

    for key, stories in sorted(cells.items()):
        for story in stories:
            cell = _compute_cell_dvs(story)
            if cell:
                dvs_results.append(cell)

    # Write summary
    summary = {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "total_cells": len(dvs_results),
        "cells": dvs_results,
        "by_condition": _group_by(dvs_results, "condition"),
        "by_story": _group_by(dvs_results, "story"),
    }

    out_path = results_dir / "dvs_summary.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nSaved: {out_path}")
    print(f"  {len(dvs_results)} cells analyzed")


def _compute_cell_dvs(story: StoryResult) -> dict | None:
    """Compute DVS for a single story result cell."""
    worktree = Path(story.worktree)
    if not worktree.exists():
        print(f"  Worktree missing: {story.worktree}")
        return None

    # Per-commit analysis
    analysis = analyze_story_worktree(worktree)

    # Entropy after the story
    try:
        entropy_after = compute_entropy(worktree)
    except Exception:
        entropy_after = None

    # Graph metrics after the story
    try:
        graph = build_graph(worktree)
        metrics = compute_metrics(graph)
    except Exception:
        metrics = None

    # Collect per-session values for DVS
    costs = [s.cost_usd for s in story.sessions]
    correctness_values = []
    for s in story.sessions:
        if s.agentic and s.agentic.tests_total > 0:
            correctness_values.append(s.agentic.correctness)
        else:
            correctness_values.append(0.5)  # default when no tests

    # Default review values (will be overridden by review agent)
    arch_fit_values = [0.5] * len(story.sessions)
    convention_values = [c.convention_score for c in analysis.commits] if analysis.commits else [0.5] * len(story.sessions)

    dvs = compute_story_dvs(costs, correctness_values, arch_fit_values, convention_values)

    # Parse story ID to extract condition from file naming
    parts = story.story_name.split("_")
    condition = story.perturbation_condition or "clean"

    return {
        "story": story.story_name,
        "story_id": story.story_id,
        "model": story.model,
        "language": story.language,
        "condition": condition,
        "sessions": story.session_count,
        "all_successful": story.all_successful,
        "cascade_recovery": story.cascade_recovery,
        "total_cost": round(story.total_cost, 6),
        "total_tokens": story.total_tokens,
        "total_duration": round(story.total_duration, 1),
        "dvs": dvs.to_dict(),
        "commits": len(analysis.commits),
        "net_lines": analysis.net_lines,
        "avg_convention": round(sum(c.convention_score for c in analysis.commits) / max(len(analysis.commits), 1), 3),
        "graph": metrics.to_dict() if metrics else {},
    }


def _group_by(results: list[dict], field: str) -> dict:
    """Group results by a field, computing averages."""
    groups = defaultdict(list)
    for r in results:
        val = r.get(field, "unknown")
        groups[val].append(r)

    summary = {}
    for key, items in sorted(groups.items()):
        dvs_scores = [i["dvs"]["score"] for i in items]
        avg_dvs = sum(dvs_scores) / len(dvs_scores) if dvs_scores else 0
        summary[key] = {
            "count": len(items),
            "avg_dvs": round(avg_dvs, 4),
            "avg_cost": round(sum(i["total_cost"] for i in items) / len(items), 6),
            "success_rate": round(sum(1 for i in items if i["all_successful"]) / len(items), 2),
        }
    return summary


if __name__ == "__main__":
    main()
