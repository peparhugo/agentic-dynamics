#!/usr/bin/env python3
"""Backfill artifact directories for all existing worktrees with game reports.

Copies generated code from /tmp/exp_* worktrees to experiments/results/reports/{name}/
and patches the corresponding .md report with an Artifacts section.

Usage:
  python scripts/backfill_artifacts.py           # backfill all matching worktrees
  python scripts/backfill_artifacts.py --dry-run  # show what would be done
"""

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "experiments" / "results" / "reports"

SKIP_DIRS = {
    "__pycache__", ".git", "venv", ".venv", "env", "site-packages",
    "node_modules", ".mypy_cache", ".pytest_cache", "dist", "build",
    "Lib", "lib", "include", ".instrument",
}


def backfill_worktree(worktree_name: str, worktree_path: str, dry_run: bool = False) -> dict:
    """Backfill artifacts for a single worktree. Returns status dict."""
    wt = Path(worktree_path)
    report_path = REPORTS_DIR / f"{worktree_name}.md"

    result = {"name": worktree_name, "code_files": 0, "has_session": False, "skipped": False}

    if not wt.exists():
        result["skipped"] = True
        result["reason"] = "worktree missing"
        return result

    artifact_dir = REPORTS_DIR / worktree_name
    code_dir = artifact_dir / "code"

    # Count code files
    code_files = 0
    if not dry_run:
        code_dir.mkdir(parents=True, exist_ok=True)
        for item in sorted(wt.rglob("*")):
            if item.is_file() and not (SKIP_DIRS & set(item.parts)):
                if item.name.startswith("."):
                    continue
                rel = item.relative_to(wt)
                dest = code_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(item, dest)
                    code_files += 1
                except Exception:
                    pass
    else:
        for item in wt.rglob("*"):
            if item.is_file() and not (SKIP_DIRS & set(item.parts)):
                if not item.name.startswith("."):
                    code_files += 1

    result["code_files"] = code_files

    # Session transcript
    session_src = wt / ".instrument" / "session.jsonl"
    if session_src.exists():
        result["has_session"] = True
        if not dry_run:
            try:
                shutil.copy2(session_src, artifact_dir / "session.jsonl")
            except Exception:
                pass

    # Patch the .md report with Artifacts section if code/session exist
    if not dry_run and report_path.exists() and (code_files > 0 or result["has_session"]):
        try:
            md_content = report_path.read_text()
            if "## Artifacts" not in md_content:
                artifact_section = "\n---\n\n## Artifacts\n\n"
                artifact_section += "Raw session transcript and generated source code for independent verification.\n\n"
                if result["has_session"]:
                    artifact_section += f"- [Opencode session transcript](./{worktree_name}/session.jsonl)\n"
                if code_files > 0:
                    artifact_section += f"- [Generated code](./{worktree_name}/code/)\n"
                if code_files == 0 and result["has_session"]:
                    artifact_section += "\n*No code output — this session was narration-only.*\n"
                report_path.write_text(md_content + artifact_section)
                result["patched_report"] = True
        except Exception as e:
            result["patch_error"] = str(e)[:80]

    return result


def main():
    ap = argparse.ArgumentParser(description="Backfill artifact directories for existing worktrees")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be done without copying")
    ap.add_argument("--worktree", help="Backfill a single worktree by name or path")
    args = ap.parse_args()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.worktree:
        wt_path = args.worktree
        if not wt_path.startswith("/"):
            wt_path = f"/tmp/{wt_path}"
        name = Path(wt_path).name
        r = backfill_worktree(name, wt_path, dry_run=args.dry_run)
        icon = "○" if r["skipped"] else "✓"
        session_icon = " [+]session" if r["has_session"] else ""
        print(f"  {icon} {r['name']:<30} {r['code_files']:>4d} files{'' if r.get('skipped') else ' → artifacts/'}{session_icon}")
        if r.get("patched_report"):
            print(f"    Patched report with Artifacts section")
        return

    # Discover worktrees
    worktree_map = {}
    for p in sorted(Path("/tmp").glob("exp_*")):
        wt_name = p.name
        worktree_map[wt_name] = str(p)

    # Match against existing reports
    existing_reports = set()
    for md_file in sorted(REPORTS_DIR.glob("exp_*.md")):
        existing_reports.add(md_file.stem)

    if args.dry_run:
        print(f"DRY RUN — {len(worktree_map)} worktrees, {len(existing_reports)} existing reports")
        print()

    results = []
    for name in sorted(worktree_map):
        r = backfill_worktree(name, worktree_map[name], dry_run=args.dry_run)
        results.append(r)

        icon = "○" if r["skipped"] else "✓"
        has_report = " [report]" if name in existing_reports else ""
        session_icon = " [+]session" if r["has_session"] else ""
        skip_reason = f" ({r.get('reason','')})" if r.get("skipped") else ""
        print(f"  {icon} {r['name']:<30} {r['code_files']:>4d} files{'' if r.get('skipped') else ' → artifacts/'}{session_icon}{has_report}{skip_reason}")
        if r.get("patched_report"):
            print(f"    Patched report with Artifacts section")

    # Summary
    skipped = sum(1 for r in results if r.get("skipped"))
    done = len(results) - skipped
    total_files = sum(r["code_files"] for r in results)
    with_session = sum(1 for r in results if r.get("has_session"))
    patched = sum(1 for r in results if r.get("patched_report"))

    print(f"\n{'='*70}")
    print(f"SUMMARY — {done} worktrees backfilled, {skipped} skipped")
    print(f"  Code files copied:   {total_files:,}")
    print(f"  Session transcripts:  {with_session}")
    print(f"  Reports patched:      {patched}")
    if args.dry_run:
        print(f"  (DRY RUN — no changes made)")
    print(f"  Artifacts dir:        {REPORTS_DIR}/")


if __name__ == "__main__":
    main()
