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
    _default_close_row,
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
        "operator": "test-operator",
        "db": None,
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


# ── a1: the control-row close (promote_row_closeout) ──────────────────────────
# The promoted run's control row must not outlive its content's arrival on main: after the
# push lands, promote closes its own row (promotable -> merged through the legitimate
# transition API) and records the promotions row. The close is best-effort and ordered AFTER
# the push — a control-db failure warns and exits 0, never unwinds the landed push. The seam
# (`close_row`) mirrors the emission seams; the default is verified against a REAL tmp
# control database (storage is the thing under test, so there is nothing to fake there).


def _make_candidate_ahead_of_main(tmp_path: Path) -> Path:
    """A repo whose HEAD (the candidate) is ONE commit ahead of ``main``.

    The non-dry-run path needs a non-empty diff vs the base to reach the push, so the base
    (main) is created one commit behind the candidate — a real, promotable topology.
    """
    wt = tmp_path / "candidate"
    wt.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=wt, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=wt, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=wt, check=True)
    (wt / "base.txt").write_text("base\n")
    subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=wt, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "candidate"], cwd=wt, check=True)
    (wt / "calc.py").write_text("def add(a, b): return a + b\n")
    subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "[workflow] scope — g"], cwd=wt, check=True)
    return wt


def _base_head(wt: Path) -> str:
    out = subprocess.run(
        ["git", "rev-parse", "main"], cwd=wt, capture_output=True, text=True, check=True
    ).stdout.strip()
    return out


_PUSHED = "abcd1234abcd1234abcd1234abcd1234abcd1234"


def _noop_emissions() -> dict:
    """Fakes for every post-push seam: a fake push (returns a squash sha), no-op emissions."""
    return {
        "push": lambda workdir, base, subject, candidate: _PUSHED,
        "emit_decision": lambda decision: {"observation_id": "obs-000000000001"},
        "emit_act": lambda decision, causes: None,
        "record_decision": lambda decision: None,
    }


def _make_promotable_run(db_path: Path, candidate_sha: str) -> str:
    """Seed a tmp control db with a run that reached ``promotable`` (the a1 close target)."""
    from agentic_dynamics.control.control_db import ControlDB, RunState

    with ControlDB.open(db_path) as db:
        run = db.create_run(spec_name="promote_test", candidate_sha=candidate_sha)
        db.transition_run(run.run_id, RunState.RUNNING, actor="orchestrator")
        db.transition_run(run.run_id, RunState.PROMOTABLE, actor="orchestrator")
        return run.run_id


def test_a1_close_row_invoked_after_a_landed_push(tmp_path):
    """The injectable close_row fires once, after the push, bound to the ledger run_id +
    the candidate/base/squash shas + the operator — the a1 seam contract."""
    wt = _make_candidate_ahead_of_main(tmp_path)
    sha = _candidate_sha(wt)
    data = _ledger(wt)
    data["run_id"] = "run-a1seam0001"
    ledger = _write_ledger(tmp_path, data)
    calls = []

    def fake_close_row(run_id, **kwargs):
        calls.append((run_id, kwargs))
        return {"closed": True}

    em = _noop_emissions()
    args = _promote_args(tmp_path, wt, ledger, dry_run=False)
    _run_promotion(args, close_row=fake_close_row, **em)
    assert len(calls) == 1
    rid, kw = calls[0]
    assert rid == "run-a1seam0001"
    assert kw["candidate_sha"] == sha
    assert kw["base"] == "main"
    assert kw["base_sha"] == _base_head(wt)
    assert kw["squash_sha"] == _PUSHED
    assert kw["by"] == "test-operator"
    assert kw["db_path"] is None


def test_a1_dry_run_never_closes_and_never_writes(tmp_path):
    """A dry run reports but performs no close: the close_row seam must never fire."""
    wt = _make_candidate(tmp_path)
    _require_main(wt)
    data = _ledger(wt)
    data["run_id"] = "run-a1dry0001"
    ledger = _write_ledger(tmp_path, data)

    def boom(*a, **k):
        raise AssertionError("dry-run must not call close_row")

    args = _promote_args(tmp_path, wt, ledger)  # dry_run=True (default)
    _run_promotion(args, close_row=boom)  # must not raise


def test_a1_ledger_without_run_id_closes_nothing(tmp_path):
    """A legacy/pre-control-db ledger has no row to close — no close_row call, no raise."""
    wt = _make_candidate_ahead_of_main(tmp_path)
    data = _ledger(wt)  # no run_id
    ledger = _write_ledger(tmp_path, data)

    def boom(*a, **k):
        raise AssertionError("no run_id on the ledger — close_row must not be called")

    em = _noop_emissions()
    args = _promote_args(tmp_path, wt, ledger, dry_run=False)
    _run_promotion(args, close_row=boom, **em)  # must not raise


def test_a1_default_close_row_closes_a_promotable_run(tmp_path):
    """The default close: promotable -> (promoting) -> merged + a promotions row, through the
    legitimate transition API against a REAL control database (a1 DONE_WHEN a)."""
    from agentic_dynamics.control.control_db import ControlDB, RunState

    db_path = tmp_path / "control.db"
    sha = "ab" * 20
    run_id = _make_promotable_run(db_path, sha)
    report = _default_close_row(
        run_id,
        candidate_sha=sha,
        base="main",
        base_sha="bb" * 20,
        squash_sha=_PUSHED,
        by="test-operator",
        db_path=str(db_path),
    )
    assert report["closed"] is True
    with ControlDB.open_read_only(db_path) as db:
        run = db.get_run(run_id)
        assert run is not None
        assert run.state == RunState.MERGED
        transitions = db.transitions(run_id)
        # The lifecycle routes through promoting: both hops recorded, in order, with the
        # actor `promote` and a reason naming the squash sha.
        hops = [
            (t.from_state.value if t.from_state else None, t.to_state.value) for t in transitions
        ]
        assert ("promotable", "promoting") in hops
        merged_hops = [t for t in transitions if t.to_state == RunState.MERGED]
        assert len(merged_hops) == 1
        assert merged_hops[0].actor == "promote"
        assert merged_hops[0].reason is not None and _PUSHED[:12] in merged_hops[0].reason
        promotions = db.promotions(run_id)
        assert len(promotions) == 1
        assert promotions[0].squash_sha == _PUSHED
        assert promotions[0].candidate_sha == sha
        assert promotions[0].by == "test-operator"
        assert promotions[0].base_sha == "bb" * 20
        # a1 DONE_WHEN b: the run is no longer promotable — the packet's promotable_runs
        # (derived from runs(state=promotable)) drops it.
        assert [r.run_id for r in db.runs(state=RunState.PROMOTABLE)] == []


def test_a1_default_close_row_is_idempotent_when_already_merged(tmp_path):
    """Re-running the close on an already-merged run performs NO second transition (a re-run
    of promote after a successful close must not double-close)."""
    from agentic_dynamics.control.control_db import ControlDB

    db_path = tmp_path / "control.db"
    sha = "ab" * 20
    run_id = _make_promotable_run(db_path, sha)
    _default_close_row(
        run_id,
        candidate_sha=sha,
        base="main",
        base_sha="bb",
        squash_sha=_PUSHED,
        by="op",
        db_path=str(db_path),
    )
    with ControlDB.open_read_only(db_path) as db:
        before = (len(db.transitions(run_id)), len(db.promotions(run_id)))
    report = _default_close_row(
        run_id,
        candidate_sha=sha,
        base="main",
        base_sha="bb",
        squash_sha="ee" * 20,
        by="op",
        db_path=str(db_path),
    )
    assert report["closed"] is False
    assert report["reason"] == "state_merged"
    with ControlDB.open_read_only(db_path) as db:
        assert (len(db.transitions(run_id)), len(db.promotions(run_id))) == before


def test_a1_default_close_row_refuses_a_candidate_mismatch(tmp_path):
    """A run row bound to a DIFFERENT tree than the one pushed is never closed — closing it
    would record a merge for content that never reached main."""
    from agentic_dynamics.control.control_db import ControlDB, RunState

    db_path = tmp_path / "control.db"
    run_id = _make_promotable_run(db_path, candidate_sha="ab" * 20)
    report = _default_close_row(
        run_id,
        candidate_sha="cd" * 20,
        base="main",
        base_sha="bb",
        squash_sha=_PUSHED,
        by="op",
        db_path=str(db_path),
    )
    assert report["closed"] is False
    assert report["reason"] == "candidate_mismatch"
    with ControlDB.open_read_only(db_path) as db:
        run = db.get_run(run_id)
        assert run is not None and run.state == RunState.PROMOTABLE
        assert db.promotions(run_id) == []


def test_a1_default_close_row_db_unavailable_warns_and_never_raises(tmp_path, capsys):
    """A control-db failure AFTER a landed push is a printed warning naming the run_id + the
    sweep as backstop — never a raise (a1 DONE_WHEN d, hard rule 2)."""
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("i am a file, not a directory")
    db_path = blocker / "control.db"  # ControlDB.open will fail to mkdir the parent
    report = _default_close_row(
        "run-a1down0001",
        candidate_sha="ab" * 20,
        base="main",
        base_sha="bb",
        squash_sha=_PUSHED,
        by="op",
        db_path=str(db_path),
    )
    assert report["closed"] is False
    assert report["reason"] == "error"
    err = capsys.readouterr().err
    assert "run-a1down0001" in err
    assert "close-out sweep" in err


def test_a1_close_row_seam_failure_warns_and_the_promotion_stands(tmp_path, capsys):
    """Even an injected close_row that RAISES cannot fail the promotion: the structural
    best-effort wrapper warns and the push stands (exit path normal, no exception)."""
    wt = _make_candidate_ahead_of_main(tmp_path)
    data = _ledger(wt)
    data["run_id"] = "run-a1down0001"
    ledger = _write_ledger(tmp_path, data)

    def down(*a, **k):
        raise RuntimeError("control db down")

    em = _noop_emissions()
    args = _promote_args(tmp_path, wt, ledger, dry_run=False)
    _run_promotion(args, close_row=down, **em)  # must not raise
    err = capsys.readouterr().err
    assert "control-row close failed" in err
    assert "run-a1down0001" in err


# ── a2: the stale-candidate guard (promote_row_closeout) ──────────────────────
# A candidate whose TREE is already the base head's tree is a post-promote leftover (the
# graph-leg class: content merged as a squash, the branch tip left promotable). promote must
# REFUSE — exit 20, nothing written, nothing pushed — in dry-run AND in a real shot, with a
# reason naming the likely merged sha + the recommendation to cancel the row. A genuinely-new
# candidate (different tree) still promotes.


def _make_stale_candidate(tmp_path: Path) -> Path:
    """The graph-leg topology: a candidate whose tree EQUALS the base head's tree but whose
    history is distinct (a post-squash branch tip — NOT an ancestor of main).

    ``main`` advances v1 → v2; the candidate forks from v1 and re-commits the v2 tree, so
    ``git diff --quiet <candidate> <main-head>`` exits 0 while ``merge-base`` is the v1 commit.
    """
    wt = tmp_path / "stale"
    wt.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=wt, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=wt, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=wt, check=True)
    (wt / "a.txt").write_text("v1\n")
    subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base v1"], cwd=wt, check=True)
    (wt / "a.txt").write_text("v2\n")
    subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "main head v2"], cwd=wt, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "candidate", "HEAD~1"], cwd=wt, check=True)
    (wt / "a.txt").write_text("v2\n")
    subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "[workflow] scope — g"], cwd=wt, check=True)
    return wt


def test_a2_dry_run_refuses_a_tree_identical_candidate(tmp_path):
    """A candidate whose tree equals the base head's tree is refused in DRY-RUN too (the
    guard sits before the dry-run return): exit-20 shape, reason names the merged sha + the
    cancel recommendation."""
    wt = _make_stale_candidate(tmp_path)
    base_head = _base_head(wt)
    ledger = _write_ledger(tmp_path, _ledger(wt))
    with pytest.raises(_PromoteRefusedError, match="stale candidate") as exc:
        _run_promotion(_promote_args(tmp_path, wt, ledger))  # dry_run=True (default)
    message = str(exc.value)
    assert base_head[:12] in message  # the likely merged sha is the main-side equal-tree commit
    assert "Cancel the run's control row, do not re-promote" in message


def test_a2_real_shot_refuses_with_nothing_written_or_pushed(tmp_path):
    """A real shot against a synthetic tree-identical branch refuses BEFORE the push: no push,
    no close, and a seeded control row is untouched (run_transitions-free, zero promotions)."""
    from agentic_dynamics.control.control_db import ControlDB, RunState

    wt = _make_stale_candidate(tmp_path)
    data = _ledger(wt)
    data["run_id"] = "run-a2stale0001"
    ledger = _write_ledger(tmp_path, data)

    # Seed a promotable control row for the run — the refusal must leave it untouched.
    db_path = tmp_path / "control.db"
    with ControlDB.open(db_path) as db:
        run = db.create_run(spec_name="promote_test", candidate_sha=_candidate_sha(wt))
        db.transition_run(run.run_id, RunState.RUNNING, actor="orchestrator")
        db.transition_run(run.run_id, RunState.PROMOTABLE, actor="orchestrator")
    with ControlDB.open_read_only(db_path) as db:
        before_transitions = len(db.transitions(run.run_id))

    pushed = []
    closed = []

    def boom_push(*a, **k):
        pushed.append(True)
        raise AssertionError("a stale candidate must never be pushed")

    def boom_close(*a, **k):
        closed.append(True)
        raise AssertionError("a stale candidate must never reach the row close")

    em = _noop_emissions()
    em["push"] = boom_push
    args = _promote_args(tmp_path, wt, ledger, dry_run=False, db=str(db_path))
    with pytest.raises(_PromoteRefusedError, match="stale candidate"):
        _run_promotion(args, close_row=boom_close, **em)
    assert pushed == []  # nothing was pushed
    assert closed == []  # the close seam never fired
    with ControlDB.open_read_only(db_path) as db:
        run_now = db.get_run(run.run_id)
        assert run_now is not None and run_now.state == RunState.PROMOTABLE
        assert len(db.transitions(run.run_id)) == before_transitions  # no new transitions
        assert db.promotions(run.run_id) == []  # no promotion row


def test_a2_genuinely_new_candidate_still_promotes(tmp_path):
    """A genuinely-new candidate (a different tree, ahead of main) is NOT stale: the dry-run
    happy path still verifies and the real-shot path still reaches the push + close."""
    wt = _make_candidate_ahead_of_main(tmp_path)
    data = _ledger(wt)
    data["run_id"] = "run-a2fresh0001"
    ledger = _write_ledger(tmp_path, data)
    # dry-run: verifies without raising
    _run_promotion(_promote_args(tmp_path, wt, ledger))  # must not raise
    # real-shot: reaches the push and the close seam (the a1 happy path, unchanged)
    calls = []

    def fake_close_row(run_id, **kwargs):
        calls.append((run_id, kwargs))
        return {"closed": True}

    em = _noop_emissions()
    args = _promote_args(tmp_path, wt, ledger, dry_run=False)
    _run_promotion(args, close_row=fake_close_row, **em)  # must not raise
    assert len(calls) == 1
    assert calls[0][0] == "run-a2fresh0001"
