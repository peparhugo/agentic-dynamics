"""P0-4 promoter tests (control-plane stabilization): the ONLY push-to-main path.

The load-bearing guarantee: promotion is refused when ANY gate evidence is missing,
stale, or bound to a different candidate — a failed phase, a test phase without an
independent success verdict, an awaiting run without a binding approval, or a candidate
rewritten after verification. The promoter never repairs; it refuses and returns 20
(awaiting → 10). The squash-and-push itself is verified via --dry-run (no remote, no
push) + the local-only path.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = str(_REPO_ROOT / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from promote import (  # noqa: E402
    _PromoteAwaitingError,
    _PromoteRefusedError,
    _run_promotion,
)

# ── fixtures: a candidate worktree + a matching ledger ────────────────────────


def _make_candidate(tmp_path: Path) -> Path:
    """A git worktree with one '[workflow] scope — g' commit (the candidate head)."""
    wt = tmp_path / "candidate"
    wt.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=wt, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=wt, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=wt, check=True)
    (wt / "calc.py").write_text("def add(a, b): return a + b\n")
    subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "[workflow] scope — g"], cwd=wt, check=True)
    return wt


def _candidate_sha(wt: Path) -> str:
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True, text=True, check=True
    ).stdout.strip()
    return out


def _ledger(wt: Path, **overrides) -> dict:
    sha = _candidate_sha(wt)
    data = {
        "spec_name": "promote_test",
        "git_sha": sha,
        "ok": True,
        "state": "succeeded",
        "total_cost_usd": 0.001,
        "phases": [
            {
                "phase": "scope",
                "kind": "agent",
                "status": "ok",
                "commit_hash": sha,
                "test_executed_success": None,
            },
            {
                "phase": "verify",
                "kind": "test",
                "status": "ok",
                "commit_hash": sha,
                "test_executed_success": True,
            },
        ],
    }
    data.update(overrides)
    return data


def _write_ledger(tmp_path: Path, data: dict) -> Path:
    spec_dir = tmp_path / "ledgers" / data["spec_name"]
    spec_dir.mkdir(parents=True, exist_ok=True)
    path = spec_dir / "20260901T000000Z.json"
    path.write_text(json.dumps(data))
    return path


def _promote_args(tmp_path, wt, ledger, **overrides):
    from types import SimpleNamespace

    args = {
        "spec": "promote_test",
        "workdir": str(wt),
        "ledger": str(ledger),
        "approval": None,
        "base": "main",
        "dry_run": True,
    }
    args.update(overrides)
    return SimpleNamespace(**args)


def _require_main(wt: Path) -> None:
    """The promoter needs a base branch — create main at the candidate for the tests."""
    subprocess.run(["git", "branch", "main"], cwd=wt, check=True)


# ── happy path: everything binds, dry-run would promote ───────────────────────


def test_dry_run_promotes_a_verified_candidate(tmp_path):
    wt = _make_candidate(tmp_path)
    _require_main(wt)
    ledger = _write_ledger(tmp_path, _ledger(wt))
    # must not raise
    _run_promotion(_promote_args(tmp_path, wt, ledger))


# ── refused: gate evidence ────────────────────────────────────────────────────


def test_refused_when_a_phase_failed(tmp_path):
    wt = _make_candidate(tmp_path)
    _require_main(wt)
    data = _ledger(wt)
    data["phases"][0]["status"] = "failed"
    ledger = _write_ledger(tmp_path, data)
    with pytest.raises(_PromoteRefusedError, match="unverified phase"):
        _run_promotion(_promote_args(tmp_path, wt, ledger))


def test_refused_when_test_phase_never_ran(tmp_path):
    """A test phase whose independent verdict is None (null-not-zero) refuses — the
    declared verification never executed, so promotion is forbidden."""
    wt = _make_candidate(tmp_path)
    _require_main(wt)
    data = _ledger(wt)
    data["phases"][1]["test_executed_success"] = None
    ledger = _write_ledger(tmp_path, data)
    with pytest.raises(_PromoteRefusedError, match="no independent success verdict"):
        _run_promotion(_promote_args(tmp_path, wt, ledger))


def test_refused_when_candidate_rewritten_after_verification(tmp_path):
    """The worktree HEAD no longer matches the ledger's git_sha — the candidate was
    modified after its gates ran. Refuse; never repair."""
    wt = _make_candidate(tmp_path)
    _require_main(wt)
    verified_sha = _candidate_sha(wt)  # the head the gates verified
    # a commit ON TOP of the verified head = the head moved
    (wt / "extra.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "[workflow] scope — g"], cwd=wt, check=True)
    data = _ledger(wt)
    data["git_sha"] = verified_sha  # the ledger binds the OLD head — now stale
    ledger = _write_ledger(tmp_path, data)
    with pytest.raises(_PromoteRefusedError, match="candidate rewritten"):
        _run_promotion(_promote_args(tmp_path, wt, ledger))


# ── awaiting: approval must bind the candidate ────────────────────────────────


def test_awaiting_run_without_approval_refuses_with_exit_10_shape(tmp_path):
    wt = _make_candidate(tmp_path)
    _require_main(wt)
    data = _ledger(wt)
    data["awaiting"] = True
    data["ok"] = False
    ledger = _write_ledger(tmp_path, data)
    with pytest.raises(_PromoteAwaitingError):
        _run_promotion(_promote_args(tmp_path, wt, ledger))


def test_awaiting_run_with_approval_for_a_different_candidate_refuses(tmp_path):
    wt = _make_candidate(tmp_path)
    _require_main(wt)
    data = _ledger(wt)
    data["awaiting"] = True
    data["ok"] = False
    ledger = _write_ledger(tmp_path, data)
    approval = tmp_path / "approval.md"
    approval.write_text(
        "---\nstatus: accepted\n---\n\n# Approval\n\ncandidate: deadbeefdeadbeef\n"
        "operator: Dr. Seuss\ndate: 2026-09-01\n"
    )
    args = _promote_args(tmp_path, wt, ledger, approval=str(approval))
    with pytest.raises(_PromoteRefusedError, match="DIFFERENT candidate"):
        _run_promotion(args)


def test_awaiting_run_with_binding_approval_promotes(tmp_path):
    wt = _make_candidate(tmp_path)
    _require_main(wt)
    sha = _candidate_sha(wt)
    data = _ledger(wt)
    data["awaiting"] = True
    data["ok"] = False
    ledger = _write_ledger(tmp_path, data)
    approval = tmp_path / "approval.md"
    approval.write_text(
        "---\nstatus: accepted\n---\n\n# Approval\n\n"
        f"candidate: {sha}\noperator: Dr. Seuss\ndate: 2026-09-01\n"
    )
    args = _promote_args(tmp_path, wt, ledger, approval=str(approval))
    _run_promotion(args)  # must not raise (dry-run)


# ── base branch missing ───────────────────────────────────────────────────────


def test_refused_when_base_branch_missing(tmp_path):
    wt = _make_candidate(tmp_path)  # no main branch created
    ledger = _write_ledger(tmp_path, _ledger(wt))
    with pytest.raises(_PromoteRefusedError, match="base branch"):
        _run_promotion(_promote_args(tmp_path, wt, ledger))
