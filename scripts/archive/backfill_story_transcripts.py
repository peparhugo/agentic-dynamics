#!/usr/bin/env python3
"""Recover per-session transcripts for story worktrees from the opencode DB.

Story runs (scripts/run_story.py) execute 5 sessions per worktree. Historically
each session overwrote ``.instrument/session.jsonl``, so only the final session's
transcript survived on disk. The full transcripts live in opencode.db (``part``
records keyed by session id), so this script reconstructs ``session_{n}.jsonl``
for every story session.

Timeout-continuation forks (titles ending in ``(fork #N)``) are concatenated onto
their parent session so each ``session_{n}.jsonl`` holds the complete trajectory.
Interleaved ``@explore subagent`` sessions are skipped.

Usage:
    python scripts/backfill_story_transcripts.py              # recover all
    python scripts/backfill_story_transcripts.py --dry-run    # preview
    python scripts/backfill_story_transcripts.py --worktree <name>  # one worktree
"""

import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "experiments" / "results" / "stories" / "transcripts"
OPENCODE_DB = Path.home() / ".local" / "share" / "opencode" / "opencode.db"

_SESSION_RE = re.compile(r"Session\s+(\d+):")


def _extract_transcript(db: sqlite3.Connection, session_id: str) -> str:
    """Reconstruct the JSONL transcript for a session from its part records."""
    rows = db.execute(
        "SELECT data FROM part WHERE session_id = ? ORDER BY time_created",
        (session_id,),
    ).fetchall()
    lines = []
    for (data_str,) in rows:
        try:
            json.loads(data_str)
            lines.append(data_str)
        except json.JSONDecodeError:
            continue
    return "\n".join(lines)


def discover_story_sessions(db: sqlite3.Connection) -> dict[str, list[tuple[int, list[str]]]]:
    """Map story worktree path -> [(session_number, [session_id, ...]), ...].

    Forked continuation sessions share the parent's session number and are kept
    in time order so they can be concatenated onto the original.
    """
    rows = db.execute(
        "SELECT id, directory, title FROM session "
        "WHERE directory LIKE '/tmp/story_%' ORDER BY time_created"
    ).fetchall()

    by_dir: dict[str, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    for session_id, directory, title in rows:
        if not title:
            continue
        m = _SESSION_RE.search(title)
        if not m:
            continue  # skip subagent/continuation-only sessions without a session number
        by_dir[directory][int(m.group(1))].append(session_id)

    return {d: sorted(s.items()) for d, s in by_dir.items()}


def main() -> None:
    ap = argparse.ArgumentParser(description="Recover story session transcripts from opencode.db")
    ap.add_argument("--dry-run", action="store_true", help="Preview without writing")
    ap.add_argument("--worktree", help="Recover a single worktree by name (e.g. story_abc123)")
    args = ap.parse_args()

    if not OPENCODE_DB.exists():
        print(f"ERROR: opencode DB not found at {OPENCODE_DB}", file=sys.stderr)
        sys.exit(1)

    db = sqlite3.connect(str(OPENCODE_DB))
    by_dir = discover_story_sessions(db)

    if args.worktree:
        wt_name = args.worktree if args.worktree.startswith("story_") else f"story_{args.worktree}"
        wt_path = f"/tmp/{wt_name}"
        if wt_path not in by_dir:
            print(f"ERROR: no sessions found for {wt_name}", file=sys.stderr)
            sys.exit(1)
        by_dir = {wt_path: by_dir[wt_path]}

    total_sessions = sum(len(v) for v in by_dir.values())
    print(f"Found {len(by_dir)} story worktrees, {total_sessions} sessions in opencode DB")

    recovered = 0
    empty = 0
    for directory, sessions in sorted(by_dir.items()):
        wt_name = Path(directory).name
        out_dir = OUTPUT_DIR / wt_name

        for session_n, session_ids in sessions:
            chunks = []
            for session_id in session_ids:
                transcript = _extract_transcript(db, session_id)
                if transcript:
                    chunks.append(transcript)
            if not chunks:
                empty += 1
                continue

            combined = "\n".join(chunks)
            out_path = out_dir / f"session_{session_n}.jsonl"
            if not args.dry_run:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(combined)
            recovered += 1
            n_parts = len(combined.splitlines())
            fork_note = f" ({len(session_ids)} parts)" if len(session_ids) > 1 else ""
            print(f"  ✓ {wt_name} session {session_n}{fork_note} ({n_parts} parts)")

    db.close()

    print(f"\n{'='*70}")
    print(f"Recovered {recovered} transcripts, {empty} empty")
    if args.dry_run:
        print("  (DRY RUN — no changes made)")
    else:
        print(f"  Output: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
