"""Session timeout recovery — continue timed-out opencode sessions.

Uses opencode's native --session flag to continue from where the agent left off.
The full session history (tool calls, file writes, thinking, test runs) is loaded
from opencode's internal database — no custom context reconstruction needed.

Usage:
    python scripts/recover_stories.py                    # Recover all timed-out cells
    python scripts/recover_stories.py --dry-run          # Show what would be recovered
    python scripts/recover_stories.py --cell <cell_id>   # Recover a single cell
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from instrument.story import load_story_result, save_story_result, StoryResult, SessionResult

OPENCODE_BIN = Path.home() / ".opencode/bin/opencode"

RESULTS_DIR = Path("experiments/results/stories")
DRY_RUN = "--dry-run" in sys.argv


def find_timed_out_cells() -> list[dict[str, Any]]:
    """Find all timed-out experiment cells."""
    cells = []
    for f in sorted(RESULTS_DIR.glob("*.json")):
        if "log" in str(f) or "dvs" in str(f):
            continue
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if "model" not in d:
            continue

        if d["summary"]["all_successful"]:
            continue

        # Find the failed session
        for s in d.get("sessions", []):
            err = str(s.get("error", "")).lower() if s.get("error") else ""
            exit_code = s.get("exit_code", 0)
            if exit_code != 0 or "timeout" in err:
                cells.append({
                    "result_file": f,
                    "result_data": d,
                    "worktree": d.get("worktree", ""),
                    "failed_session": s["session_number"],
                    "task_type": s.get("task_type", ""),
                    "model": d.get("model", "deepseek/deepseek-v4-pro"),
                    "session_id": _extract_session_id(d.get("worktree", "")),
                })
                break

    return cells


def _extract_session_id(worktree: str) -> str:
    """Extract opencode session ID from session.jsonl."""
    if not worktree:
        return ""
    jsonl_path = Path(worktree) / ".instrument" / "session.jsonl"
    if not jsonl_path.exists():
        return ""

    try:
        with open(jsonl_path) as f:
            for line in f:
                if not line.strip():
                    continue
                event = json.loads(line)
                sid = event.get("sessionID", "")
                if sid:
                    return sid
    except (json.JSONDecodeError, OSError):
        pass

    return ""


def recover_cell(cell: dict[str, Any]) -> bool:
    """Recover a single timed-out cell by continuing the session."""
    session_id = cell["session_id"]
    worktree = cell["worktree"]
    model = cell["model"]
    failed_session = cell["failed_session"]

    if not session_id:
        print(f"  WARNING: No session ID found in {worktree}/.instrument/session.jsonl")
        return False

    if not Path(worktree).exists():
        print(f"  WARNING: Worktree no longer exists: {worktree}")
        return False

    print(f"  Continuing session {session_id[:12]}...")
    print(f"    Model: {model}")
    print(f"    Worktree: {worktree}")

    continuation_prompt = (
        "Continue what you were doing. Complete the task from where you left off. "
        "The codebase is in its current state. Finish the implementation and run "
        "the tests. Do NOT restart from scratch — continue from the current state."
    )

    t0 = time.monotonic()

    result = subprocess.run(
        [
            str(OPENCODE_BIN), "run",
            "--session", session_id,
            "--fork",
            "--dir", worktree,
            "--model", model,
            "--auto",
            continuation_prompt,
        ],
        capture_output=True,
        text=True,
        timeout=2400,
    )

    elapsed = time.monotonic() - t0

    if result.returncode == 0 and result.stdout.strip():
        print(f"    OK ({elapsed:.0f}s)")

        # Git commit if there are changes
        wt_path = Path(worktree)
        subprocess.run(["git", "-C", str(wt_path), "add", "-A"],
                       capture_output=True)
        status = subprocess.run(
            ["git", "-C", str(wt_path), "status", "--porcelain"],
            capture_output=True, text=True
        ).stdout.strip()

        if status:
            subprocess.run(
                ["git", "-C", str(wt_path), "commit", "-m",
                 f"[story] Session {failed_session}: {cell['task_type']} (continued)"],
                capture_output=True,
            )
            print(f"    Committed changes")

        # Save continuation log
        log_dir = RESULTS_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        name = cell.get("result_data", {}).get("story_name", "unknown")
        log_file = log_dir / f"recover_{name}_{failed_session}.log"
        log_file.write_text(result.stdout)

        # Update result JSON
        _update_result_json(cell, failed_session, ok=True)
        return True
    else:
        print(f"    FAILED ({elapsed:.0f}s)")
        if result.stderr:
            print(f"    Stderr: {result.stderr[:200]}")
        # Save error log
        log_dir = RESULTS_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"recover_{name}_{failed_session}.error.log"
        log_file.write_text(result.stderr or result.stdout)
        return False


def _update_result_json(cell: dict[str, Any], session_num: int, ok: bool) -> None:
    """Update the result JSON to mark the recovered session as OK."""
    story = load_story_result(cell["result_file"])
    if story is None:
        return

    for s in story.sessions:
        if s.session_number == session_num:
            if ok:
                s.exit_code = 0
                s.error = ""
            break

    save_story_result(story, cell["result_file"])


def main() -> None:
    cells = find_timed_out_cells()

    if not cells:
        print("No timed-out cells found. All cells succeeded!")
        return

    print(f"Found {len(cells)} timed-out cells:")

    if DRY_RUN:
        for c in cells:
            sid = c["session_id"][:12] if c["session_id"] else "unknown"
            name = c.get("result_data", {}).get("story_name", "?")
            print(f"  [{name}] S{c['failed_session']} — session={sid}")
        return

    recovered = 0
    for i, cell in enumerate(cells):
        name = cell.get("result_data", {}).get("story_name", "unknown")
        print(f"\n[{i+1}/{len(cells)}] {name} S{cell['failed_session']}")
        if recover_cell(cell):
            recovered += 1

    print(f"\nRecovered: {recovered}/{len(cells)} cells")


if __name__ == "__main__":
    main()
