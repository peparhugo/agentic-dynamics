"""review_all.py — Review every story directly with ThreadPoolExecutor (no Redis).

Reviews commits + story for each worktree in parallel, writing
experiments/results/reviews/review_{story_id}.json.

This replaces the Redis queue (which repeatedly lost jobs) with the same
ThreadPoolExecutor pattern that analyze_stories.py uses reliably.

Usage:
  python3 scripts/review_all.py              # review all stories
  python3 scripts/review_all.py --workers 6  # parallel
  python3 scripts/review_all.py --story notification_service  # subset
  python3 scripts/review_all.py --dry-run    # list what would run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


from agentic_dynamics.reporting.review import review_commit, review_story
from agentic_dynamics.runtime.story import load_story_result

RESULTS_DIR = Path(__file__).resolve().parent.parent / "experiments" / "results" / "stories"
REVIEWS_DIR = Path(__file__).resolve().parent.parent / "experiments" / "results" / "reviews"
MODEL = "deepseek/deepseek-v4-flash"


def _get_story_commits(worktree: Path) -> list[tuple[str, str, int]]:
    """Return [(hash, message, session_number)] for session commits."""
    try:
        log = subprocess.run(
            ["git", "-C", str(worktree), "log", "--reverse", "--format=%H|%s"],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []

    import re
    commits = []
    for line in log.strip().splitlines():
        if "|" not in line or "Session" not in line:
            continue
        ch, cm = line.split("|", 1)
        m = re.search(r"Session\s+(\d+)", cm)
        sn = int(m.group(1)) if m else 0
        commits.append((ch, cm, sn))
    return commits


def _review_one_story(result_file: Path) -> tuple[str, str]:
    """Review a single story and write its review file. Returns (name, err)."""
    name = result_file.name
    try:
        story = load_story_result(result_file)
    except Exception as e:
        return name, f"load: {e}"

    worktree = Path(story.worktree) if story.worktree else None
    if not worktree or not worktree.exists():
        return name, "worktree missing"

    commits = _get_story_commits(worktree)
    if not commits:
        return name, "no session commits"

    review_path = REVIEWS_DIR / f"review_{story.story_id}.json"
    data = {"commit_reviews": []}
    if review_path.exists():
        try:
            data = json.loads(review_path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {"commit_reviews": []}

    # Commit reviews
    existing = {cr.get("session_number"): cr for cr in data.get("commit_reviews", [])}
    commit_reviews = []
    for ch, _cm, sn in commits:
        if sn in existing and existing[sn]:
            commit_reviews.append(existing[sn])  # reuse already-done review
            continue
        r = review_commit(
            worktree, ch,
            story_name=story.story_name, session_number=sn,
            model=MODEL, story_id=story.story_id,
        )
        d = r.to_dict()
        d["session_number"] = sn
        commit_reviews.append(d)

    # Story review (reuse if already done)
    story_review = data.get("story_review")
    if not story_review:
        try:
            sr = review_story(worktree, story.story_name, model=MODEL)
            story_review = sr.to_dict()
        except Exception as e:
            story_review = {"error": str(e)}

    data = {
        "story_name": story.story_name,
        "story_id": story.story_id,
        "model": MODEL,
        "commit_reviews": commit_reviews,
        "story_review": story_review,
    }
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    review_path.write_text(json.dumps(data, indent=2))
    return name, ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--story", default="", help="Substring filter on story name")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result_files = sorted(
        f for f in RESULTS_DIR.glob("*.json")
        if "dvs" not in f.name and "log" not in f.name
    )
    if args.story:
        result_files = [f for f in result_files if args.story in f.name]

    print(f"Reviewing {len(result_files)} stories with {args.workers} workers")

    if args.dry_run:
        for f in result_files:
            print(f"  {f.name}")
        return

    done = 0
    errors = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_review_one_story, rf): rf for rf in result_files}
        for fut in as_completed(futures):
            name, err = fut.result()
            done += 1
            if err:
                errors += 1
                print(f"  [{done}/{len(result_files)}] ERROR {name}: {err}", flush=True)
            else:
                print(f"  [{done}/{len(result_files)}] done {name}", flush=True)

    print(f"\nDone: {done} stories, {errors} errors")


if __name__ == "__main__":
    main()
