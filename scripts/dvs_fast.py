"""Fast sequential DVS computation — runs directly, no Redis queue.

Usage:
    python scripts/dvs_fast.py
"""

import json
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from instrument.story import load_story_result
from instrument.commit_analysis import analyze_story_worktree
from instrument.entropy import compute_entropy, entropy_delta
from instrument.codebase_graph import build_graph, compute_metrics
from instrument.value_score import compute_story_dvs


def main():
    results_dir = Path("experiments/results/stories")
    result_files = sorted(results_dir.glob("*.json"))
    result_files = [f for f in result_files if "log" not in f.name and "dvs" not in f.name]

    cells = []
    skipped = 0
    failed = 0

    for rf in result_files:
        try:
            d = json.loads(rf.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if "model" not in d:
            continue

        t0 = time.monotonic()
        story = load_story_result(rf)
        worktree = Path(story.worktree)

        if not worktree.exists():
            skipped += 1
            continue

        try:
            analysis = analyze_story_worktree(worktree)
            graph = build_graph(worktree)
            graph_m = compute_metrics(graph)

            # Real correctness from session.jsonl test results
            costs = [s.cost_usd for s in story.sessions]
            correctness_values = []
            for s in story.sessions:
                if s.agentic and s.agentic.tests_total > 0:
                    correctness_values.append(s.agentic.correctness)
                else:
                    correctness_values.append(0.0)

            # Architectural fit: placeholder 0.5 (review agents run async via worker_dvs)
            arch_fit_values = [0.5] * len(story.sessions)

            # Convention values from commit analysis
            if analysis.commits:
                conv_vals = [c.convention_score for c in analysis.commits]
                while len(conv_vals) < len(story.sessions):
                    conv_vals.append(conv_vals[-1] if conv_vals else 0.5)
                conv_vals = conv_vals[:len(story.sessions)]
            else:
                conv_vals = [0.5] * len(story.sessions)

            # Entropy delta: seed codebase vs final worktree
            entropy_d = 0.0
            codebase_seed = Path(story.codebase_path)
            if codebase_seed.exists():
                seed_ep = compute_entropy(codebase_seed)
                worktree_ep = compute_entropy(worktree)
                entropy_d = entropy_delta(seed_ep, worktree_ep)

            dvs = compute_story_dvs(
                costs, correctness_values, arch_fit_values, conv_vals,
                entropy_delta=entropy_d,
            )
            elapsed = time.monotonic() - t0

            cells.append({
                "story": story.story_name,
                "story_id": story.story_id,
                "condition": story.perturbation_condition or "clean",
                "model": story.model,
                "sessions": story.session_count,
                "all_successful": story.all_successful,
                "cascade_recovery": story.cascade_recovery,
                "total_cost": round(story.total_cost, 6),
                "total_tokens": story.total_tokens,
                "dvs": dvs.to_dict(),
                "commits": len(analysis.commits),
                "net_lines": analysis.net_lines,
                "avg_convention": round(analysis.average_convention_score, 3),
                "graph": graph_m.to_dict(),
            })

            print(f"  [{story.story_name[:20]:20s}] {story.perturbation_condition or 'clean':15s} DVS={dvs.score:.3f} ({elapsed:.1f}s)")

        except Exception as e:
            failed += 1
            print(f"  [{rf.name[:40]}] FAILED: {e}")

    # Group summaries
    by_condition = {}
    by_story = {}
    for c in cells:
        cond = c["condition"]
        story = c["story"]
        for key, val in [(cond, by_condition), (story, by_story)]:
            if key not in val:
                val[key] = {"count": 0, "dvs_total": 0, "cost_total": 0, "success": 0}
            val[key]["count"] += 1
            val[key]["dvs_total"] += c["dvs"]["score"]
            val[key]["cost_total"] += c["total_cost"]
            if c["all_successful"]:
                val[key]["success"] += 1

    cond_summary = {}
    for k, d in by_condition.items():
        n = d["count"]
        cond_summary[k] = {
            "count": n, "avg_dvs": round(d["dvs_total"]/n, 4) if n else 0,
            "avg_cost": round(d["cost_total"]/n, 6) if n else 0,
            "success_rate": round(d["success"]/n, 2) if n else 0,
        }

    story_summary = {}
    for k, d in by_story.items():
        n = d["count"]
        story_summary[k] = {
            "count": n, "avg_dvs": round(d["dvs_total"]/n, 4) if n else 0,
            "avg_cost": round(d["cost_total"]/n, 6) if n else 0,
            "success_rate": round(d["success"]/n, 2) if n else 0,
        }

    summary = {
        "generated_at": datetime.now().isoformat(),
        "total_cells": len(cells),
        "skipped": skipped,
        "failed": failed,
        "by_condition": cond_summary,
        "by_story": story_summary,
        "cells": cells,
    }

    out = results_dir / "dvs_summary.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"\nSaved: {out}")
    print(f"  {len(cells)} cells ({skipped} skipped, {failed} failed)")
    for cond, d in sorted(cond_summary.items()):
        print(f"  {cond:15s}: DVS={d['avg_dvs']:.2f}, {d['count']} cells, {d['success_rate']:.0%} ok, \${d['avg_cost']:.5f} avg")


if __name__ == "__main__":
    main()
