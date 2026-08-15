"""Post-session test validation — runs pytest on generated code.

Replaces heuristic correctness with actual test pass/fail.
Usage:
    python scripts/validate_session.py --workdir /tmp/exp_xyz
    python scripts/validate_session.py --session-id ses_xxx
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from _constants import WORKTREE_GLOB, WORKTREE_ROOT


def find_test_files(workdir: str) -> list[str]:
    """Find all pytest-compatible test files in a worktree."""
    test_files = []
    for root, dirs, files in os.walk(workdir):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        for f in files:
            if (f.startswith('test') or f.endswith('_test.py')) and f.endswith('.py'):
                test_files.append(os.path.join(root, f))
    return test_files


def run_pytest(workdir: str) -> dict:
    """Run pytest in the worktree and return structured results."""
    test_files = find_test_files(workdir)
    if not test_files:
        return {"passed": 0, "failed": 0, "error": 0, "output": "No test files found"}

    result = subprocess.run(
        ['python3', '-m', 'pytest', '-q', '--tb=short'] + test_files,
        cwd=workdir, capture_output=True, text=True, timeout=120
    )
    output = result.stdout.strip() + "\n" + result.stderr.strip()

    m = re.search(r'(\d+)\s+passed', output)
    passed = int(m.group(1)) if m else 0
    m = re.search(r'(\d+)\s+failed', output)
    failed = int(m.group(1)) if m else 0
    m = re.search(r'(\d+)\s+error', output)
    errors = int(m.group(1)) if m else 0

    return {
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "total": passed + failed + errors,
        "pass_rate": passed / max(passed + failed + errors, 1),
        "output": output[-1000:],
    }


def validate_session(workdir: str, session_id: str = "", append_to_db: bool = False) -> dict:
    """Run pytest validation on an experiment session's worktree."""
    if not os.path.isdir(workdir):
        return {"error": f"Workdir not found: {workdir}"}

    results = run_pytest(workdir)
    results["workdir"] = workdir
    results["session_id"] = session_id

    if append_to_db and session_id:
        try:
            import sqlite3
            conn = sqlite3.connect(str(Path.home() / ".local/share/opencode/opencode.db"))
            conn.execute(
                "UPDATE session SET metadata = json_set(COALESCE(metadata,'{}'), '$.test_results', ?) WHERE id = ?",
                (json.dumps(results), session_id)
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", help="Path to session worktree")
    parser.add_argument("--session-id", help="OpenCode session ID")
    parser.add_argument("--model", default="all", help="Filter by model")
    args = parser.parse_args()

    if args.workdir:
        results = validate_session(args.workdir, args.session_id or "")
        print(json.dumps(results, indent=2))
    else:
        # Scan for recent experiment worktrees
        import glob
        workdirs = sorted(glob.glob(f"{WORKTREE_ROOT}/probe_*") + glob.glob(str(WORKTREE_GLOB)),
                         key=os.path.getmtime, reverse=True)[:10]
        for wd in workdirs:
            results = validate_session(wd)
            if results.get("total", 0) > 0:
                print(f"\n{wd}: {results['passed']}/{results['total']} passed")
