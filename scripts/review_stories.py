"""Batch review script — run commit review + story review on all story results.

Usage:
    python scripts/review_stories.py                         # All stories
    python scripts/review_stories.py --story-dir DIR         # Single story dir
    python scripts/review_stories.py --dry-run                # Just list what would run
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from instrument.story import load_story_result
from instrument.review import review_commit, review_story


def main():
    dry_run = "--dry-run" in sys.argv

    results_dir = Path("experiments/results/stories")
    result_files = sorted(results_dir.glob("*.json"))
    result_files = [f for f in result_files if "dvs_summary" not in f.name and "log" not in f.parent.name]

    if not result_files:
        print("No story results found.")
        return

    print(f"Reviewing {len(result_files)} story results...")

    reviews_dir = Path("experiments/results/reviews")
    reviews_dir.mkdir(parents=True, exist_ok=True)

    for rf in result_files:
        try:
            story = load_story_result(rf)
        except Exception as e:
            print(f"  Skipping {rf.name}: {e}")
            continue

        worktree = Path(story.worktree)
        if not worktree.exists():
            print(f"  Worktree missing: {story.worktree}")
            continue

        print(f"  [{story.story_name}] {story.model} ({story.session_count} sessions)")

        if dry_run:
            continue

        # Commit reviews per session
        commit_reviews = []
        import subprocess
        log = subprocess.run(
            ["git", "-C", str(worktree), "log", "--reverse", "--format=%H %s"],
            capture_output=True, text=True
        ).stdout
        commits = [l.split(" ", 1) for l in log.strip().splitlines() if "Session" in l]

        for i, (ch, cm) in enumerate(commits):
            print(f"    Reviewing commit {i+1}/{len(commits)}: {ch[:8]}")
            review = review_commit(
                worktree, ch,
                story_name=story.story_name,
                session_number=i + 1,
            )
            commit_reviews.append(review.to_dict())

        # Story review
        print(f"    Reviewing full story...")
        story_review = review_story(worktree, story.story_name)

        # Save
        out = {
            "story_name": story.story_name,
            "story_id": story.story_id,
            "model": story.model,
            "condition": story.perturbation_condition,
            "commit_reviews": commit_reviews,
            "story_review": story_review.to_dict(),
        }
        out_path = reviews_dir / f"review_{story.story_id}.json"
        out_path.write_text(json.dumps(out, indent=2))
        print(f"    Saved: {out_path}")

    print(f"\nReviews saved to: {reviews_dir}")


if __name__ == "__main__":
    main()
