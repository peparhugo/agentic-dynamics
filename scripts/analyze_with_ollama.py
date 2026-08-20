#!/usr/bin/env python3
"""Qualitative experiment analysis via DeepSeek R1 on Ollama.

Feeds experiment metrics and session data to deepseek-r1:1.5b for
narrative commentary. Useful for generating human-readable analysis
of individual sessions, comparing runs, and finding patterns.

Usage:
  python scripts/analyze_with_ollama.py --session exp_0s36_d3n
  python scripts/analyze_with_ollama.py --model deepseek/deepseek-v4-pro
  python scripts/analyze_with_ollama.py --compare exp_0s36_d3n exp_brg802xf
  python scripts/analyze_with_ollama.py --batch "How do manifold perturbations differ?"
  python scripts/analyze_with_ollama.py --summarize-filter "strategy=wasteful"
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


from agentic_dynamics.reporting.ollama_analyzer import OllamaAnalyzer, load_summary_data


def find_session_dir(session_name: str) -> Path:
    reports_dir = PROJECT_ROOT / "experiments" / "results" / "reports"
    for d in reports_dir.iterdir():
        if d.name == session_name and (d / "session.jsonl").exists():
            return d
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Analyze experiments via DeepSeek R1 on Ollama"
    )
    parser.add_argument("--session", type=str, help="Analyze a specific session")
    parser.add_argument("--model", type=str, help="Analyze all sessions for a model")
    parser.add_argument("--compare", nargs=2, metavar=("BASELINE", "PERTURBED"),
                        help="Compare two sessions (baseline perturbed)")
    parser.add_argument("--batch", type=str, help="Run batch analysis question")
    parser.add_argument("--summarize-filter", type=str, help="Summarize filtered runs, e.g. 'strategy=wasteful'")
    parser.add_argument("--limit", type=int, default=10, help="Limit batch results")
    args = parser.parse_args()

    analyzer = OllamaAnalyzer()

    if args.session:
        session_dir = find_session_dir(args.session)
        if not session_dir:
            print(f"Session {args.session} not found")
            return
        print(f"Analyzing session: {args.session}\n")
        result = analyzer.analyze_session(session_dir / "session.jsonl")
        print(result)

    elif args.model:
        entries = load_summary_data()
        model_entries = [e for e in entries if e.get("model") == args.model]
        if not model_entries:
            print(f"No runs found for model: {args.model}")
            return
        print(f"Found {len(model_entries)} runs for {args.model}")
        question = f"What patterns emerge across {args.model} experiments?"
        result = analyzer.batch_analyze(model_entries, question)
        print(f"\n{result}")

    elif args.compare:
        entries = load_summary_data()
        baseline_name, perturbed_name = args.compare
        baseline = next((e for e in entries if e.get("worktree_name") == baseline_name), None)
        perturbed = next((e for e in entries if e.get("worktree_name") == perturbed_name), None)
        if not baseline:
            print(f"Baseline session {baseline_name} not found in summary data.")
        if not perturbed:
            print(f"Perturbed session {perturbed_name} not found in summary data.")
        if not baseline or not perturbed:
            return
        print(f"Comparing {baseline_name} vs {perturbed_name}\n")
        result = analyzer.compare_sessions(baseline, perturbed)
        print(result)

    elif args.batch:
        entries = load_summary_data()
        if not entries:
            print("No entries found in summary data.")
            return
        result = analyzer.batch_analyze(entries[:args.limit], args.batch)
        print(result)

    elif args.summarize_filter:
        entries = load_summary_data()
        parts = args.summarize_filter.split("=", 1)
        if len(parts) == 2:
            key, value = parts
            filtered = [e for e in entries if str(e.get(key, "")) == value]
            print(f"Found {len(filtered)} runs matching {args.summarize_filter}")
            if filtered:
                result = analyzer.batch_analyze(
                    filtered[:args.limit],
                    f"What characterizes these {key}={value} runs?",
                )
                print(f"\n{result}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
