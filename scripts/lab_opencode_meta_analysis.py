#!/usr/bin/env python3
r"""Lab Book 13: opencode-Driven Meta-Analysis — The Model Analyzing Itself

Orchestrates analysis sessions where deepseek-v4-flash (via opencode harness)
reads experiment data and produces qualitative analysis. Each analysis session
is recorded, costed, and traceable — a meta-experiment.

Output: experiments/results/lab_opencode_meta_analysis.json
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from instrument.opencode_analyzer import OpencodeAnalyzer, _load_summary

OUTPUT_PATH = ROOT / "experiments" / "results" / "lab_opencode_meta_analysis.json"

ANALYSIS_TASKS = [
    {
        "id": "session_deepdive",
        "name": "Session Deep-Dive",
        "description": "Analyze a single experiment session in depth",
        "type": "session",
        "target": "exp_0s36_d3n",
    },
    {
        "id": "pairwise_comparison",
        "name": "Pairwise Comparison",
        "description": "Compare baseline vs perturbed session",
        "type": "compare",
        "targets": ["exp_0s36_d3n", "exp_brg802xf"],
    },
    {
        "id": "strategy_analysis",
        "name": "Strategy Analysis",
        "description": "What characterizes wasteful runs?",
        "type": "filter",
        "key": "strategy",
        "value": "wasteful",
    },
    {
        "id": "cost_anomalies",
        "name": "Cost Anomaly Detection",
        "description": "What drives high-cost sessions?",
        "type": "batch",
        "question": "Which sessions have costs over $0.50 and why? What patterns drive high costs?",
    },
    {
        "id": "model_profile",
        "name": "DeepSeek Model Profile",
        "description": "Patterns across all DeepSeek runs",
        "type": "model",
        "target": "deepseek/deepseek-v4-pro",
        "question": "What patterns emerge across DeepSeek's experiment runs? "
                    "Look for trends in correctness, cost, and strategy.",
    },
    {
        "id": "perturbation_compare",
        "name": "Perturbation Class Comparison",
        "description": "Manifold vs semantic perturbation impact",
        "type": "batch",
        "question": "Compare manifold vs semantic perturbation classes. "
                    "From the data provided, which class produces more escape, lower correctness, "
                    "and higher cost? Which is harder for models? Be specific with numbers.",
    },
]


def compute(skip_expensive: bool = True, limit_tasks: int = 0):
    tasks = ANALYSIS_TASKS[:limit_tasks] if limit_tasks else ANALYSIS_TASKS

    analyzer = OpencodeAnalyzer(
        model="deepseek/deepseek-v4-flash",
        timeout=300,
    )

    results = []
    total_cost = 0.0
    total_tokens = 0
    total_duration = 0.0
    entries = _load_summary()

    for i, task in enumerate(tasks):
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(tasks)}] {task['name']}: {task['description']}")
        print(f"{'='*60}")

        t0 = time.monotonic()
        result = None

        try:
            if task["type"] == "session":
                result = analyzer.analyze_session(task["target"])
            elif task["type"] == "compare":
                result = analyzer.compare_sessions(task["targets"][0], task["targets"][1])
            elif task["type"] == "filter":
                result = analyzer.analyze_filtered(
                    task["key"], task["value"], task.get("question", ""), limit=10,
                )
            elif task["type"] == "batch":
                subset = entries[:15]
                if task.get("question"):
                    result = analyzer.batch_analyze(subset, task["question"])
                else:
                    result = analyzer.batch_analyze(subset, task.get("question", "Analyze these runs."))
            elif task["type"] == "model":
                result = analyzer.analyze_model(
                    task["target"], task.get("question", ""),
                )
        except ValueError as e:
            result = None
            print(f"  Skipped: {e}")

        elapsed = time.monotonic() - t0
        if result:
            record = {
                "task_id": task["id"],
                "task_name": task["name"],
                "model": result.model,
                "exit_code": result.exit_code,
                "duration_s": round(result.duration_s, 1),
                "total_tokens": result.total_tokens,
                "estimated_cost_usd": round(result.estimated_cost_usd, 6),
                "error": result.error[:200] if result.error else "",
                "final_response_preview": result.final_response[:300] if result.final_response else "",
                "files_created": result.files_created[:5],
            }
            total_cost += result.estimated_cost_usd
            total_tokens += result.total_tokens
            total_duration += result.duration_s
            results.append(record)
        else:
            results.append({
                "task_id": task["id"],
                "task_name": task["name"],
                "error": "No result produced (data missing or analysis failed)",
            })

        print(f"  Done in {elapsed:.1f}s")

    return {
        "_meta": {
            "experiment_id": "lab_opencode_meta_analysis",
            "total_tasks": len(tasks),
            "completed_tasks": len([r for r in results if "error" not in r or not r.get("error")]),
            "analysis_model": "deepseek/deepseek-v4-flash",
            "infrastructure": "opencode_analyzer.py → run_opencode_agentic()",
            "total_cost_usd": round(total_cost, 6),
            "total_tokens": total_tokens,
            "total_duration_s": round(total_duration, 1),
            "note": "Each analysis session is a measured opencode run. The analysis itself is traceable.",
        },
        "analysis_sessions": results,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="opencode meta-analysis orchestrator")
    parser.add_argument("--skip-expensive", action="store_true", default=True,
                        help="Skip high-cost analyses")
    parser.add_argument("--limit-tasks", type=int, default=0,
                        help="Max analysis tasks to run")
    parser.add_argument("--all", dest="skip_expensive", action="store_false",
                        help="Run all tasks including expensive ones")
    args = parser.parse_args()

    results = compute(skip_expensive=args.skip_expensive, limit_tasks=args.limit_tasks)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nWrote: {OUTPUT_PATH}")
    print(f"Total analysis cost: ${results['_meta']['total_cost_usd']:.6f}")
