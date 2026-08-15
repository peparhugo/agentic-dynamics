#!/usr/bin/env python3
"""Regenerate typescript_ssg experiment worktrees from opencode DB part records.

Extracts all write/todowrite/edit tool calls from the `part` table and
reconstructs worktree directories at their original /tmp/exp_* paths.
Also saves the session transcript as .instrument/session.jsonl.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

DB_PATH = os.path.expanduser("~/.local/share/opencode/opencode.db")
REPORTS_DIR = Path("/home/drseuss/ai-finops-framework/experiments/results/reports")


def main():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    sessions = db.execute("""
        SELECT id, directory, title, model, cost, tokens_input, tokens_output, tokens_reasoning
        FROM session
        WHERE title LIKE '%typescript_ssg%' AND cost > 0 AND directory LIKE '/tmp/%'
        ORDER BY time_created
    """).fetchall()

    print(f"Found {len(sessions)} typescript_ssg sessions with /tmp/ directories\n")

    success_count = 0
    empty_count = 0
    total_files = 0
    session_map = {}  # session_id -> {model, operator, dir}

    for s in sessions:
        sid = s["id"]
        directory = s["directory"]
        title = s["title"]
        model_raw = json.loads(s["model"]) if s["model"] else {}
        model_id = model_raw.get("id", "unknown")

        operator = "unknown"
        import re
        m = re.match(r'\[([^\]]+)\]', title)
        if m:
            op_raw = m.group(1)
            if "baseline" in op_raw and ":" not in op_raw.split(",")[0]:
                operator = "baseline"
            elif "_s" in op_raw:
                operator = op_raw.rsplit("_s", 1)[0]
            else:
                operator = op_raw

        # Extract parts
        parts = db.execute("""
            SELECT data, time_created
            FROM part
            WHERE session_id = ?
            ORDER BY time_created
        """, (sid,)).fetchall()

        files_written = {}
        transcript_lines = []

        for (data_str, _ts) in parts:
            obj = json.loads(data_str)

            # Collect transcript lines (filter to interesting types)
            ptype = obj.get("type", "")
            if ptype in ("text", "tool", "reasoning", "step-start", "step-finish"):
                transcript_lines.append(json.dumps(obj))

            # Extract file writes
            if ptype == "tool" and obj.get("tool") in ("write", "todowrite"):
                fp = obj.get("state", {}).get("input", {}).get("filePath", "")
                content = obj.get("state", {}).get("input", {}).get("content", "")
                if fp and content:
                    files_written[fp] = content

            # Handle edit tool calls
            if ptype == "tool" and obj.get("tool") == "edit":
                fp = obj.get("state", {}).get("input", {}).get("filePath", "")
                if not fp:
                    continue
                new_str = obj.get("state", {}).get("input", {}).get("newString", "")
                old_str = obj.get("state", {}).get("input", {}).get("oldString", "")
                if not new_str or not old_str:
                    continue
                # Apply edit: find existing content and apply replace
                existing = files_written.get(fp, "")
                if old_str in existing:
                    if obj.get("state", {}).get("input", {}).get("replaceAll"):
                        existing = existing.replace(old_str, new_str)
                    else:
                        existing = existing.replace(old_str, new_str, 1)
                    files_written[fp] = existing
                else:
                    # File might not have been written yet; just set content
                    files_written[fp] = new_str

        if not files_written:
            empty_count += 1
            print(f"  EMPTY: {directory} ({model_id} | {operator})")
            continue

        # Write files to the worktree
        worktree = Path(directory)
        worktree.mkdir(parents=True, exist_ok=True)

        for fp, content in files_written.items():
            # filePath is absolute, strip common prefix
            # Handle both /tmp/exp_*/ and the exact worktree path
            rel = fp
            if fp.startswith(str(worktree) + "/"):
                rel = fp[len(str(worktree)) + 1:]
            elif fp.startswith("/tmp/"):
                # Strip up to the worktree name
                parts_fp = fp.split("/")
                if len(parts_fp) >= 4:
                    rel = "/".join(parts_fp[4:])
                else:
                    rel = parts_fp[-1] if parts_fp else fp

            dest = worktree / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                dest.write_text(content)
                total_files += 1
            except Exception as e:
                print(f"  ERROR writing {dest}: {e}")

        # Save transcript
        instr_dir = worktree / ".instrument"
        instr_dir.mkdir(parents=True, exist_ok=True)
        (instr_dir / "session.jsonl").write_text("\n".join(transcript_lines))

        success_count += 1
        session_map[sid] = {"model": model_id, "operator": operator, "dir": directory,
                           "nfiles": len(files_written)}
        print(f"  OK: {directory} ({model_id} | {operator}) -> {len(files_written)} files")

    db.close()

    print(f"\n{'='*60}")
    print("RECONSTRUCTION COMPLETE")
    print(f"  Sessions with code: {success_count}")
    print(f"  Empty sessions:      {empty_count}")
    print(f"  Total files written: {total_files}")
    print(f"{'='*60}")

    # Count existing reports matching these sessions
    existing_reports = {}
    if REPORTS_DIR.exists():
        for f in REPORTS_DIR.iterdir():
            if f.suffix == ".md" and f.stem.startswith("exp_"):
                existing_reports[f.stem] = f

    typescript_md_count = sum(
        1 for d in REPORTS_DIR.iterdir()
        if d.suffix == ".md" and "typescript_ssg" in d.name
    ) if REPORTS_DIR.exists() else 0

    print(f"\n  Existing typescript_ssg named reports: {typescript_md_count}")
    print(f"  Existing per-worktree reports (exp_*): {len(existing_reports)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
