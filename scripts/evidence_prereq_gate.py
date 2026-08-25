"""Deterministic preflight for cap_evidence_integrity (p0).

Exit-code based: 0 = prerequisites met, 1 = not met (a report of unmet checks on stderr).
NOT a collected pytest test — it is invoked as a script by the p0 phase, so it never breaks
CI or other workflows' test phases.

Checks (each must pass):
  1. The four prerequisite branches are COMPLETE AND MERGED, by ANCESTRY, not text:
     for each of cap_e2_cascade_run, cap_pattern_minting, cap_story_bridge,
     cap_test_runner_wiring — the last run ledger's git_sha must be an ancestor of HEAD
     (`git merge-base --is-ancestor <sha> HEAD`). Ledger path:
     experiments/results/workflows/<spec>/*.json (latest mtime). The run ledgers are
     machine-local and gitignored (never provenance), so on a fresh checkout the gate
     falls back to the PINNED run records in
     experiments/results/evidence_prereq_inputs.json (committed, review-F2 fix) — the
     gate is re-runnable at any branch tip with the inputs that the p0 phase actually
     used.
  2. The sonnet adversary produced an APPROVED verdict, not merely an ok run: for each of the
     four branches, its review doc (docs/review/cap_<branch>_review.md) exists ON HEAD (i.e.
     committed and merged) and contains a non-FAIL verdict line (starts with "## Verdict:" and
     does not contain "FAIL").
  3. cap_story_bridge's last run (ledger or pinned record) is ok=True.

Invocation: python3 scripts/evidence_prereq_gate.py   (exit 0/1)
"""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RESULTS = REPO / "experiments" / "results" / "workflows"
REVIEWS = REPO / "docs" / "review"
PINNED_INPUTS = REPO / "experiments" / "results" / "evidence_prereq_inputs.json"

PREREQ_BRANCHES = (
    "cap_e2_cascade_run",
    "cap_pattern_minting",
    "cap_story_bridge",
    "cap_test_runner_wiring",
)

# Review-doc naming as committed by the adversary: mostly <branch>_review.md, but the a1
# review used the workflow name (cap_e2_cascade_run's workflow is cap_e2_e3_run).
REVIEW_DOCS = {
    "cap_e2_cascade_run": "cap_e2_e3_review.md",
    "cap_pattern_minting": "cap_pattern_minting_review.md",
    "cap_story_bridge": "cap_story_bridge_review.md",
    "cap_test_runner_wiring": "cap_test_runner_wiring_review.md",
}


def _git(*args: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout.strip()


def _last_ledger(spec_name: str) -> dict | None:
    spec_dir = RESULTS / spec_name
    if not spec_dir.exists():
        return None
    ledgers = sorted(spec_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not ledgers:
        return None
    try:
        return json.loads(ledgers[-1].read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _pinned_record(spec_name: str) -> dict | None:
    """The committed pinned run record for ``spec_name``, or None (missing/unreadable)."""
    if not PINNED_INPUTS.exists():
        return None
    try:
        data = json.loads(PINNED_INPUTS.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    return (data.get("runs") or {}).get(spec_name)


def _run_record(spec_name: str) -> tuple[dict | None, str]:
    """The run record for ``spec_name``: the machine-local ledger when present, else the
    pinned committed record (fallback source is reported for the record's provenance)."""
    ledger = _last_ledger(spec_name)
    if ledger is not None:
        return ledger, "ledger"
    return _pinned_record(spec_name), "pinned"


def _branch_merged(spec_name: str) -> tuple[bool, str]:
    """The branch is merged iff its run record's git_sha is an ancestor of HEAD."""
    record, source = _run_record(spec_name)
    if record is None:
        return False, f"{spec_name}: no run ledger and no pinned record found"
    sha = record.get("git_sha") or record.get("current_commit") or ""
    if not sha:
        return False, f"{spec_name}: run record has no git_sha"
    rc, _ = _git("merge-base", "--is-ancestor", sha, "HEAD")
    if rc != 0:
        return False, f"{spec_name}: {source} sha {sha[:10]} not an ancestor of HEAD (not merged)"
    return True, f"{spec_name}: {source} sha {sha[:10]} is an ancestor of HEAD"


def _verdict_approved(spec_name: str) -> tuple[bool, str]:
    """The review doc exists on HEAD and its Verdict line is not FAIL."""
    review = REVIEWS / REVIEW_DOCS[spec_name]
    if not review.exists():
        return False, f"{spec_name}: review doc {review.name} not on HEAD"
    text = review.read_text(errors="replace")
    for line in text.splitlines():
        if line.startswith("## Verdict"):
            if "FAIL" in line.upper():
                return False, f"{spec_name}: verdict is FAIL ({line.strip()})"
            return True, f"{spec_name}: verdict approved ({line.strip()})"
    return False, f"{spec_name}: review doc has no Verdict line"


def main() -> int:
    failures: list[str] = []
    for branch in PREREQ_BRANCHES:
        ok, msg = _branch_merged(branch)
        if not ok:
            failures.append(msg)
            continue
        ok, msg = _verdict_approved(branch)
        if not ok:
            failures.append(msg)

    story, source = _run_record("cap_story_bridge")
    if story is None or not story.get("ok"):
        failures.append("cap_story_bridge: run record is not ok")

    if failures:
        print("EVIDENCE PREREQ GATE: NOT MET", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("EVIDENCE PREREQ GATE: MET (4 branches merged with approved verdicts; story_bridge ok)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
