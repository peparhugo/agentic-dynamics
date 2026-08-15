"""Story runner CLI — run multi-session experiment stories.

Usage:
    python scripts/run_story.py task_manager_api
    python scripts/run_story.py task_manager_api --condition bad_seed
    python scripts/run_story.py static_site_gen --codebase-quality bad
    python scripts/run_story.py notification_service --tier tier2_small
    python scripts/run_story.py --list
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from _constants import SESSION_TIMEOUT, model_slug

from instrument.story import (
    BUILTIN_STORIES,
    PerturbationCondition,
    StoryConfig,
    run_story,
    save_story_result,
)

# Default codebase mappings for --codebase-quality shortcut
_CODEBASE_MAP = {
    ("python", "tier1_minimal", "good"): "experiments/codebases/python/tier1_minimal/good",
    ("python", "tier1_minimal", "bad"): "experiments/codebases/python/tier1_minimal/bad",
    ("python", "tier2_small", "good"): "experiments/codebases/python/tier2_small/good",
    ("python", "tier2_small", "bad"): "experiments/codebases/python/tier2_small/bad",
    ("typescript", "tier1_minimal", "good"): "experiments/codebases/typescript/tier1_minimal/good",
    ("typescript", "tier1_minimal", "bad"): "experiments/codebases/typescript/tier1_minimal/bad",
    ("typescript", "tier2_small", "good"): "experiments/codebases/typescript/tier2_small/good",
    ("typescript", "tier2_small", "bad"): "experiments/codebases/typescript/tier2_small/bad",
}


def main():
    parser = argparse.ArgumentParser(
        description="Run a multi-session AI FinOps Dynamics experiment story."
    )
    parser.add_argument(
        "story",
        nargs="?",
        help="Story name (task_manager_api, static_site_gen, notification_service) or path to YAML",
    )
    parser.add_argument(
        "--list", action="store_true", help="List available built-in stories"
    )
    parser.add_argument(
        "--model", default="deepseek/deepseek-v4-pro", help="Model ID"
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "opencode", "claude_cli"],
        default="auto",
        help="Backend to execute sessions (auto routes anthropic/* to claude_cli)",
    )
    parser.add_argument(
        "--codebase",
        default=None,
        help="Path to seed codebase (overrides --codebase-quality and --tier)",
    )
    parser.add_argument(
        "--codebase-quality",
        choices=["good", "bad"],
        default="good",
        help="Codebase quality: good (clean) or bad (Flash V4 degraded)",
    )
    parser.add_argument(
        "--tier",
        default="tier1_minimal",
        help="Codebase tier: tier1_minimal or tier2_small",
    )
    parser.add_argument(
        "--condition",
        choices=["clean", "bad_seed", "early_degrade", "late_degrade"],
        default="clean",
        help="Perturbation condition",
    )
    parser.add_argument(
        "--timeout", type=int, default=SESSION_TIMEOUT, help="Per-session timeout in seconds"
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

    # Resolve codebase path
    if args.codebase:
        codebase_path = args.codebase
    else:
        key = (story.language, args.tier, args.codebase_quality)
        codebase_path = _CODEBASE_MAP.get(key)
        if codebase_path is None:
            print(f"No codebase mapping for {key}")
            print("Use --codebase to specify path manually")
            sys.exit(1)
        if not Path(codebase_path).exists():
            print(f"Codebase not found: {codebase_path}")
            print("Use --codebase to specify path or generate the missing codebase")
            sys.exit(1)

    condition = PerturbationCondition(args.condition)

    print(f"\nStory: {story.name} ({len(story.sessions)} sessions, {story.language})")
    print(f"Model: {args.model}")
    print(f"Codebase: {codebase_path} ({args.codebase_quality}, {args.tier})")
    print(f"Condition: {condition.value}")
    print(f"{'='*60}")

    result = run_story(
        story,
        codebase_path=codebase_path,
        model=args.model,
        condition=condition,
        worktree_root=args.worktree_root,
        timeout=args.timeout,
        thinking_budget_tokens=args.thinking_budget,
        output_token_limit=args.output_limit,
        standardize=args.standardize,
        backend=None if args.backend == "auto" else args.backend,
    )

    # Save results
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    slug = model_slug(args.model)
    out_path = results_dir / f"{story.name}_{slug}_{condition.value}_{result.story_id}.json"
    save_story_result(result, out_path)

    print(f"\n{'='*60}")
    print(f"Story complete: {story.name}")
    print(f"  Condition: {condition.value}")
    print(f"  Sessions: {result.session_count}  |  All successful: {result.all_successful}")
    print(f"  Total cost: ${result.total_cost:.4f}")
    print(f"  Total tokens: {result.total_tokens:,}")
    print(f"  Duration: {result.total_duration:.1f}s")
    if result.cascade_recovery is not None:
        print(f"  Cascade recovery: {'yes' if result.cascade_recovery else 'no'}")
    print(f"  Results: {out_path}")
    if result.error:
        print(f"  ERROR: {result.error}")


if __name__ == "__main__":
    main()
