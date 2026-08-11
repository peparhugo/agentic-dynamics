"""Post-hoc story analysis — analyze story worktrees after experiments complete.

Usage:
    python scripts/analyze_stories.py /tmp/story_abc123  # Single story
    python scripts/analyze_stories.py --all                # All stories from results
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from instrument.commit_analysis import analyze_story_worktree, StoryAnalysis, CommitAnalysis
from instrument.story import load_story_result, StoryResult


def main():
    parser = argparse.ArgumentParser(
        description="Post-hoc analysis of experiment story worktrees."
    )
    parser.add_argument(
        "worktree",
        nargs="?",
        help="Path to a story worktree with git history",
    )
    parser.add_argument(
        "--results-dir",
        default="experiments/results/stories",
        help="Directory for story result JSON files",
    )
    parser.add_argument(
        "--output-dir",
        default="experiments/results/analysis",
        help="Directory for analysis output",
    )
    parser.add_argument(
        "--no-sonar", action="store_true", help="Skip SonarQube analysis"
    )

    args = parser.parse_args()

    if not args.worktree:
        # Analyze all stories from results directory
        results_dir = Path(args.results_dir)
        if not results_dir.exists():
            print(f"No results directory: {results_dir}")
            return

        for result_file in sorted(results_dir.glob("*.json")):
            print(f"\nAnalyzing: {result_file.name}")
            try:
                story_result = load_story_result(result_file)
                _analyze_from_result(story_result, Path(args.output_dir), args.no_sonar)
            except Exception as e:
                print(f"  ERROR: {e}")
        return

    # Analyze single worktree
    worktree_path = Path(args.worktree)
    if not worktree_path.exists():
        print(f"Worktree not found: {worktree_path}")
        sys.exit(1)

    analysis = analyze_story_worktree(worktree_path)
    _print_analysis(analysis)


def _analyze_from_result(
    story_result: StoryResult,
    output_dir: Path,
    no_sonar: bool,
) -> StoryAnalysis:
    """Analyze a story worktree from a StoryResult and save the analysis."""
    worktree_path = Path(story_result.worktree)
    if not worktree_path.exists():
        print(f"  Worktree no longer exists: {worktree_path}")
        return StoryAnalysis(story_name=story_result.story_name)

    print(f"  Story: {story_result.story_name}")
    print(f"  Model: {story_result.model}")
    print(f"  Sessions: {story_result.session_count}")

    analysis = analyze_story_worktree(worktree_path)
    analysis.story_name = story_result.story_name
    analysis.story_id = story_result.story_id

    _print_analysis(analysis)

    # Save analysis
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"analysis_{story_result.story_id}.json"
    out_path.write_text(json.dumps(analysis.to_dict(), indent=2))
    print(f"  Saved: {out_path}")

    return analysis


def _print_analysis(analysis: StoryAnalysis) -> None:
    """Print a summary of a story analysis."""
    print(f"  Commits analyzed: {len(analysis.commits)}")
    print(f"  Lines: +{analysis.total_lines_added} -{analysis.total_lines_removed} (net {analysis.net_lines})")
    print(f"  Avg convention score: {analysis.average_convention_score:.2f}")

    for c in analysis.commits:
        print(f"    [{c.session_number}] {c.commit_hash[:8]}: "
              f"+{c.lines_added}/-{c.lines_removed} lines, "
              f"funcs +{c.functions_added}/-{c.functions_removed}, "
              f"conv={c.convention_score:.2f}")


if __name__ == "__main__":
    main()
