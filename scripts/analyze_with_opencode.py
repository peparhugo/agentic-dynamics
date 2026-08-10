#!/usr/bin/env python3
"""Qualitative experiment analysis via opencode sessions with DeepSeek v4-flash.

Each analysis run spawns a real opencode session — producing a measured,
cost-tracked, traceable result. The analysis itself becomes an experiment
that can be analyzed by the same instrument.

Usage:
  python scripts/analyze_with_opencode.py --session exp_0s36_d3n
  python scripts/analyze_with_opencode.py --model deepseek/deepseek-v4-pro
  python scripts/analyze_with_opencode.py --compare exp_0s36_d3n exp_brg802xf
  python scripts/analyze_with_opencode.py --batch "Why do manifold perturbations waste more?"
  python scripts/analyze_with_opencode.py --filter strategy wasteful --limit 5
  python scripts/analyze_with_opencode.py --list-sessions
"""

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from instrument.opencode_analyzer import OpencodeAnalyzer, REPORTS_DIR
from instrument.opencode import AgenticResult


def _persist_result(result: AgenticResult, tag: str) -> Path:
    archive_dir = REPORTS_DIR / tag
    archive_dir.mkdir(parents=True, exist_ok=True)

    workdir = Path(result.workdir)
    session_src = workdir / ".instrument" / "session.jsonl"
    if session_src.exists():
        shutil.copy(session_src, archive_dir / "session.jsonl")

    analysis_md = workdir / "analysis.md"
    if analysis_md.exists():
        shutil.copy(analysis_md, archive_dir / "analysis.md")

    comparison_md = workdir / "comparison.md"
    if comparison_md.exists():
        shutil.copy(comparison_md, archive_dir / "comparison.md")

    with open(archive_dir / "meta.json", "w") as f:
        import json
        json.dump({
            "tag": tag,
            "model": result.model,
            "exit_code": result.exit_code,
            "duration_s": result.duration_s,
            "total_tokens": result.total_tokens,
            "estimated_cost_usd": result.estimated_cost_usd,
            "files_created": result.files_created,
            "error": result.error,
        }, f, indent=2)

    return archive_dir


def _print_result(result: AgenticResult, archive_dir: Path | None = None):
    print(f"\n{'='*60}")
    print(f"Model: {result.model}")
    print(f"Duration: {result.duration_s:.1f}s")
    print(f"Tokens: {result.total_tokens:,}")
    print(f"Cost: ${result.estimated_cost_usd:.6f}")
    print(f"Exit code: {result.exit_code}")
    if result.error:
        print(f"Error: {result.error[:200]}")
    if archive_dir and archive_dir.exists():
        print(f"Archived to: {archive_dir}")
    if result.final_response:
        preview = result.final_response[:500].strip()
        print(f"\nResponse preview:\n{preview}...")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze experiments via opencode + DeepSeek v4-flash"
    )
    parser.add_argument("--session", type=str, help="Analyze a specific session (worktree name)")
    parser.add_argument("--model", type=str, help="Analyze all sessions for a model ID")
    parser.add_argument("--compare", nargs=2, metavar=("BASELINE", "PERTURBED"),
                        help="Compare two sessions")
    parser.add_argument("--batch", type=str, help="Run batch analysis with this question")
    parser.add_argument("--filter", nargs=2, metavar=("KEY", "VALUE"),
                        help="Filter runs, e.g.: strategy wasteful")
    parser.add_argument("--limit", type=int, default=25, help="Limit batch entries")
    parser.add_argument("--no-archive", action="store_true", help="Don't archive results")
    parser.add_argument("--list-sessions", action="store_true", help="List available session names")
    parser.add_argument("--opencode-model", type=str, default="deepseek/deepseek-v4-flash",
                        help="Model to use for analysis (default: deepseek-v4-flash)")
    parser.add_argument("--timeout", type=int, default=300, help="Session timeout in seconds")
    args = parser.parse_args()

    if args.list_sessions:
        sessions = sorted(
            d.name for d in REPORTS_DIR.iterdir()
            if d.is_dir() and (d / "session.jsonl").exists()
        )
        print(f"\n{sessions} sessions available:")
        for s in sessions:
            print(f"  {s}")
        return

    analyzer = OpencodeAnalyzer(model=args.opencode_model, timeout=args.timeout)
    result = None
    tag = ""

    if args.session:
        print(f"Analyzing session: {args.session}")
        result = analyzer.analyze_session(args.session)
        tag = f"meta_analyze_{args.session}"

    elif args.model:
        print(f"Analyzing all sessions for model: {args.model}")
        result = analyzer.analyze_model(args.model)
        safe_model = args.model.replace("/", "_").replace(" ", "_")
        tag = f"meta_model_{safe_model}"

    elif args.compare:
        print(f"Comparing: {args.compare[0]} vs {args.compare[1]}")
        result = analyzer.compare_sessions(args.compare[0], args.compare[1])
        tag = f"meta_compare_{args.compare[0]}_vs_{args.compare[1]}"

    elif args.batch:
        from instrument.opencode_analyzer import _load_summary
        entries = _load_summary()
        if not entries:
            print("No entries found in summary data.")
            return
        print(f"Analyzing {len(entries[:args.limit])} runs with question: {args.batch}")
        result = analyzer.batch_analyze(entries[:args.limit], args.batch)
        import time
        tag = f"meta_batch_{int(time.time())}"

    elif args.filter:
        key, value = args.filter
        print(f"Filtering: {key}={value}, limit={args.limit}")
        question = f"What characterizes these {key}={value} runs?"
        result = analyzer.analyze_filtered(key, value, question, args.limit)
        tag = f"meta_filter_{key}_{value}"

    else:
        parser.print_help()
        return

    if result is None:
        print("No analysis produced.")
        return

    archive_dir = None
    if not args.no_archive:
        archive_dir = _persist_result(result, tag)

    _print_result(result, archive_dir)


if __name__ == "__main__":
    main()
