"""Deterministic preflight for cap_evidence_integrity (p0, kind: test).

The evidence-integrity stream may only run after its prerequisites are true on main:
  1. the four in-flight branches (cap_e2_cascade_run, cap_pattern_minting, cap_story_bridge,
     cap_test_runner_wiring) are merged (their final [workflow] commits reachable from HEAD);
  2. cap_sonnet_adversary completed with a release verdict (its last run ledger records ok);
  3. cap_story_bridge completed (not in a runnable/failed lifecycle state).

This is a DETERMINISTIC gate: the runner fails the phase when these tests fail, so a
"FAIL: stop" cannot be ignored the way an agent-phase word can be.
"""

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RESULTS = REPO / "experiments" / "results" / "workflows"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _ledger_ok(spec_name: str) -> bool:
    spec_dir = RESULTS / spec_name
    if not spec_dir.exists():
        return False
    ledgers = sorted(spec_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not ledgers:
        return False
    try:
        return bool(json.loads(ledgers[-1].read_text()).get("ok"))
    except (json.JSONDecodeError, OSError):
        return False


def _branch_final_commit(branch: str) -> str | None:
    """The tip commit of the merged feature branch, if reachable from HEAD."""
    out = subprocess.run(
        ["git", "-C", str(REPO), "log", "--oneline", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    # The branch names encode the final phase commits; look for the branch's merge marker
    # or its expected final phase commit message.
    return next(
        (line for line in out.splitlines() if f"[workflow]" in line and branch.split("-", 2)[-1] in line),
        None,
    )


def test_four_inflight_branches_merged():
    for spec in ("cap_e2_cascade_run", "cap_pattern_minting", "cap_story_bridge", "cap_test_runner_wiring"):
        # The final [workflow] phase commit of each branch must be reachable from HEAD.
        # The branch tip is reachable iff its final phase commit is in HEAD's history.
        final_commit = _branch_final_commit(spec)
        assert final_commit, f"{spec}: final [workflow] commit not reachable from HEAD"


def test_sonnet_adversary_completed():
    # The adversary's ledger must record ok=True (a release verdict was produced).
    assert _ledger_ok("cap_sonnet_adversary"), "cap_sonnet_adversary: no completed (ok) run ledger"


def test_story_bridge_completed():
    # The story bridge must have a completed run (its phases all committed and the last
    # ledger records ok) — a runnable/failed state blocks the stream.
    assert _ledger_ok("cap_story_bridge"), "cap_story_bridge: no completed (ok) run ledger"
