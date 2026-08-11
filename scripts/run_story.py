"""Story runner CLI — run multi-session experiment stories.

Usage:
    python scripts/run_story.py task_manager_api --model deepseek/deepseek-v4-pro
    python scripts/run_story.py static_site_gen --model anthropic/claude-fable-5 --mutation inject_bug --strength 0.5
    python scripts/run_story.py --list  # List available stories
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from instrument.story import (
    BUILTIN_STORIES,
    StoryConfig,
    run_story,
    save_story_result,
)
from instrument.mutation import compile_mutation


def main():
    parser = argparse.ArgumentParser(
        description="Run a multi-session AI FinOps Dynamics experiment story."
    )
    parser.add_argument(
        "story",
        nargs="?",
        help="Story name (task_manager_api, static_site_gen) or path to YAML",
    )
    parser.add_argument(
        "--list", action="store_true", help="List available built-in stories"
    )
    parser.add_argument(
        "--model", default="deepseek/deepseek-v4-pro", help="Model ID"
    )
    parser.add_argument(
        "--codebase",
        default="experiments/codebases/python/tier1_minimal/good",
        help="Path to seed codebase",
    )
    parser.add_argument(
        "--mutation",
        default=None,
        help="Perturbation operator to apply (e.g. inject_bug, remove_constraint)",
    )
    parser.add_argument(
        "--strength", type=float, default=0.5, help="Mutation strength (0.0-1.0)"
    )
    parser.add_argument(
        "--timeout", type=int, default=600, help="Per-session timeout in seconds"
    )
    parser.add_argument(
        "--worktree-root", default="/tmp", help="Parent directory for worktrees"
    )
    parser.add_argument(
        "--results-dir",
        default="experiments/results/stories",
        help="Directory for result JSON files",
    )
    parser.add_argument(
        "--thinking-budget", type=int, default=0, help="Thinking token budget"
    )
    parser.add_argument(
        "--output-limit", type=int, default=0, help="Output token limit"
    )
    parser.add_argument(
        "--standardize", action="store_true", default=True, help="Apply standardized constraints"
    )
    parser.add_argument(
        "--no-standardize", dest="standardize", action="store_false", help="Skip standardized constraints"
    )

    args = parser.parse_args()

    if args.list:
        print("Available stories:")
        for name, story in sorted(BUILTIN_STORIES.items()):
            print(f"  {name:30s} — {story.description} ({len(story.sessions)} sessions, {story.language})")
        return

    if not args.story:
        parser.error("story name or --list is required")

    # Load story config
    story_path = Path(args.story)
    if story_path.suffix in (".yaml", ".yml") and story_path.exists():
        story = StoryConfig.from_yaml(story_path)
    elif args.story in BUILTIN_STORIES:
        story = BUILTIN_STORIES[args.story]
    else:
        print(f"Unknown story: {args.story!r}")
        print(f"Available: {list(BUILTIN_STORIES)}")
        sys.exit(1)

    # Compile mutation if requested
    mutation = None
    if args.mutation:
        print(f"Compiling mutation: {args.mutation} (strength={args.strength})...")
        mutation = compile_mutation(
            specification=story.sessions[0].prompt if story.sessions else "",
            operator=args.mutation,
            strength=args.strength,
            codebase_path=Path(args.codebase) if Path(args.codebase).exists() else None,
        )
        print(f"  Mutation ID: {mutation.mutation_id}")

    print(f"\nStory: {story.name} ({len(story.sessions)} sessions)")
    print(f"Model: {args.model}")
    print(f"Codebase: {args.codebase}")
    print(f"Mutation: {args.mutation or 'none'}")
    print(f"{'='*60}")

    result = run_story(
        story,
        codebase_path=args.codebase,
        model=args.model,
        mutation=mutation,
        worktree_root=args.worktree_root,
        timeout=args.timeout,
        thinking_budget_tokens=args.thinking_budget,
        output_token_limit=args.output_limit,
        standardize=args.standardize,
    )

    # Save results
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    model_slug = args.model.replace("/", "_").replace(" ", "_")
    out_path = results_dir / f"{story.name}_{model_slug}_{result.story_id}.json"
    save_story_result(result, out_path)

    print(f"\n{'='*60}")
    print(f"Story complete: {story.name}")
    print(f"  Sessions: {result.session_count}")
    print(f"  Total cost: ${result.total_cost:.4f}")
    print(f"  Total tokens: {result.total_tokens:,}")
    print(f"  Duration: {result.total_duration:.1f}s")
    print(f"  All successful: {result.all_successful}")
    print(f"  Results: {out_path}")
    if result.error:
        print(f"  ERROR: {result.error}")


if __name__ == "__main__":
    main()
