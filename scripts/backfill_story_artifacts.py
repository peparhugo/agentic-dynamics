"""backfill_story_artifacts.py — Copy generated source code from story worktrees.

The story worktrees (/tmp/story_*) contain the actual code the models wrote,
which is otherwise ephemeral (lost on reboot). This copies each story's source
files into experiments/results/artifacts/{story_id}/, excluding dependency
and build directories (node_modules, build, dist, venv, __pycache__, .git).

Usage:
  python3 scripts/backfill_story_artifacts.py            # all stories
  python3 scripts/backfill_story_artifacts.py --dry-run  # preview
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

STORIES_DIR = Path(__file__).resolve().parent.parent / "experiments" / "results" / "stories"
ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "experiments" / "results" / "artifacts"

EXCLUDED_DIRS = {
    "node_modules", "build", "dist", "venv", ".venv",
    "__pycache__", ".pytest_cache", ".scannerwork", ".git",
}
# Keep only source/artifact files — skip logs, transcripts, and binaries.
INCLUDED_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".rb", ".java",
    ".json", ".yaml", ".yml", ".toml", ".md", ".txt", ".html", ".css",
    ".sql", ".sh", ".cfg", ".ini", ".gitignore", ".dockerfile", ".proto",
}


def _iter_source_files(worktree: Path):
    """Yield relative source files, skipping excluded dirs and binary files."""
    for p in sorted(worktree.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(worktree)
        parts = rel.parts
        if any(part in EXCLUDED_DIRS for part in parts[:-1]):
            continue
        if rel.name.startswith("."):
            continue
        if rel.suffix.lower() not in INCLUDED_SUFFIXES and rel.name != "Dockerfile":
            continue
        # Skip .instrument session.jsonl (that's already committed as transcripts)
        if ".instrument" in parts:
            continue
        yield rel


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    copied_total = 0
    for f in sorted(STORIES_DIR.glob("*.json")):
        if "dvs" in f.name or "log" in f.name:
            continue
        d = json.loads(f.read_text())
        wt = Path(d.get("worktree", ""))
        if not wt.exists():
            continue
        story_id = d.get("story_id", f.stem.split("_")[-1])
        dest = ARTIFACTS_DIR / story_id

        files = list(_iter_source_files(wt))
        if not files:
            continue

        if not dry_run:
            if dest.exists():
                shutil.rmtree(dest)
            dest.mkdir(parents=True, exist_ok=True)
            for rel in files:
                src = wt / rel
                out = dest / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, out)
        copied_total += len(files)
        print(f"  {story_id}: {len(files)} source files")

    print(f"\n{'Would copy' if dry_run else 'Copied'} {copied_total} source files "
          f"across {len(list(STORIES_DIR.glob('*.json')))} stories "
          f"to {ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()
