#!/usr/bin/env python3
"""Backfill artifact directories for all existing worktrees with game reports.

Copies generated code from /tmp/exp_* worktrees to experiments/results/reports/{name}/
and extracts session transcripts from the opencode SQLite database.

Usage:
  python scripts/backfill_artifacts.py              # backfill all matching worktrees
  python scripts/backfill_artifacts.py --dry-run     # show what would be done
  python scripts/backfill_artifacts.py --sessions-only # only backfill session transcripts
"""

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "experiments" / "results" / "reports"
OPENCODE_DB = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
from _constants import WORKTREE_ROOT

SKIP_DIRS = {
    "__pycache__", ".git", "venv", ".venv", "env", "site-packages",
    "node_modules", ".mypy_cache", ".pytest_cache", "dist", "build",
    "Lib", "lib", "include", ".instrument",
}


def build_session_map() -> dict[str, str]:
    """Build mapping from worktree path -> session_id from the opencode DB."""
    if not OPENCODE_DB.exists():
        return {}
    db = sqlite3.connect(str(OPENCODE_DB))
    rows = db.execute(
        f"SELECT directory, id FROM session WHERE directory LIKE '{WORKTREE_ROOT}/exp_%'"
    ).fetchall()
    db.close()
    return {r[0]: r[1] for r in rows if r[0]}


def extract_session_transcript(session_id: str) -> str:
    """Extract the full session transcript as JSONL from the opencode DB."""
    if not OPENCODE_DB.exists():
        return ""
    db = sqlite3.connect(str(OPENCODE_DB))
    parts = db.execute(
        "SELECT data FROM part WHERE session_id = ? ORDER BY time_created",
        (session_id,),
    ).fetchall()
    db.close()

    lines = []
    for (data_str,) in parts:
        try:
            obj = json.loads(data_str)
            lines.append(json.dumps(obj))
        except json.JSONDecodeError:
            lines.append(data_str)
    return "\n".join(lines) if lines else ""


def backfill_worktree(
    worktree_name: str,
    worktree_path: str,
    session_id: str = "",
    dry_run: bool = False,
    sessions_only: bool = False,
) -> dict:
    """Backfill artifacts for a single worktree. Returns status dict."""
    wt = Path(worktree_path)
    report_path = REPORTS_DIR / f"{worktree_name}.md"

    result = {
        "name": worktree_name,
        "code_files": 0,
        "has_session": False,
        "skipped": False,
    }

    if not wt.exists():
        result["skipped"] = True
        result["reason"] = "worktree missing"
        return result

    artifact_dir = REPORTS_DIR / worktree_name
    code_dir = artifact_dir / "code"

    # ── Code files ──
    code_files = 0
    if not sessions_only and not dry_run:
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
    elif not sessions_only:
        for item in wt.rglob("*"):
            if item.is_file() and not (SKIP_DIRS & set(item.parts)):
                if not item.name.startswith("."):
                    code_files += 1

    result["code_files"] = code_files

    # ── Session transcript from DB ──
    session_component = ""
    if session_id:
        # Check worktree-local copy first (from new-style runs)
        local_jsonl = wt / ".instrument" / "session.jsonl"
        if local_jsonl.exists():
            session_component = local_jsonl.read_text()
        else:
            session_component = extract_session_transcript(session_id)

        if session_component:
            result["has_session"] = True
            if not dry_run:
                artifact_dir.mkdir(parents=True, exist_ok=True)
                (artifact_dir / "session.jsonl").write_text(session_component)

    # ── Patch .md report ──
    has_content = code_files > 0 or result["has_session"]
    if not dry_run and report_path.exists() and has_content:
        try:
            md_content = report_path.read_text()

            session_link = f"- [Opencode session transcript](./{worktree_name}/session.jsonl)"
            code_link = f"- [Generated code](./{worktree_name}/code/)"

            if "## Artifacts" not in md_content:
                artifact_section = [
                    "",
                    "---",
                    "",
                    "## Artifacts",
                    "",
                    "Raw session transcript and generated source code for independent verification.",
                    "",
                ]
                if result["has_session"]:
                    artifact_section.append(session_link)
                if code_files > 0:
                    artifact_section.append(code_link)
                if code_files == 0 and result["has_session"]:
                    artifact_section.append("")
                    artifact_section.append("*No code output — this session was narration-only.*")
                report_path.write_text(md_content + "\n".join(artifact_section))
                result["patched_report"] = True
            else:
                # Artifacts section already exists — rebuild it with all available links
                new_section = [
                    "## Artifacts",
                    "",
                    "Raw session transcript and generated source code for independent verification.",
                    "",
                ]
                if result["has_session"]:
                    new_section.append(session_link)
                if code_files > 0:
                    new_section.append(code_link)
                if code_files == 0 and result["has_session"]:
                    new_section.append("")
                    new_section.append("*No code output — this session was narration-only.*")

                pattern = r"## Artifacts\n.*?(?=\n---\n|\n## |\Z)"
                replacement = "\n".join(new_section)
                new_md = re.sub(pattern, replacement, md_content, count=1, flags=re.DOTALL)
                if new_md != md_content:
                    report_path.write_text(new_md)
                    result["patched_report"] = True
        except Exception as e:
            result["patch_error"] = str(e)[:80]

    return result


def main():
    ap = argparse.ArgumentParser(description="Backfill artifact directories for existing worktrees")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be done without copying")
    ap.add_argument("--sessions-only", action="store_true", help="Only backfill session transcripts (skip code)")
    ap.add_argument("--worktree", help="Backfill a single worktree by name or path")
    args = ap.parse_args()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Build session map
    session_map = build_session_map()
    print(f"Opencode DB: {len(session_map)} sessions mapped to worktree paths")

    if args.worktree:
        wt_path = args.worktree
        if not wt_path.startswith("/"):
            wt_path = f"/tmp/{wt_path}"
        name = Path(wt_path).name
        sid = session_map.get(wt_path, "")
        r = backfill_worktree(name, wt_path, sid, dry_run=args.dry_run, sessions_only=args.sessions_only)
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
        worktree_map[wt_name] = (str(p), session_map.get(str(p), ""))

    # Match against existing reports
    existing_reports = set()
    for md_file in sorted(REPORTS_DIR.glob("exp_*.md")):
        existing_reports.add(md_file.stem)

    if args.dry_run:
        print(f"DRY RUN — {len(worktree_map)} worktrees, {len(existing_reports)} existing reports")
        print()

    results = []
    for name in sorted(worktree_map):
        wt_path, sid = worktree_map[name]
        r = backfill_worktree(name, wt_path, sid, dry_run=args.dry_run, sessions_only=args.sessions_only)
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
    if not args.sessions_only:
        print(f"  Code files copied:     {total_files:,}")
    print(f"  Session transcripts:    {with_session}")
    print(f"  Reports patched:        {patched}")
    if args.dry_run:
        print(f"  (DRY RUN — no changes made)")
    print(f"  Artifacts dir:          {REPORTS_DIR}/")


if __name__ == "__main__":
    main()
