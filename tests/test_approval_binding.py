"""Wave A4 — exact approval binding: the review's #2 reproductions, flipped to refusals.

* the checkpoint consumer accepted an artifact naming the WRONG spec/phase/candidate/tree
  (it validated ``purpose`` only) — the same fixture now FAILS with the named checks, and the
  correct binding still passes;
* the validator binds the RUN and GATE too (the review: "no expected-run or expected-gate
  parameters");
* the promoter no longer falls back to a mutable working copy for an in-worktree artifact;
* an approval commit refuses a dirty index (the staged-edit ride-along reproduction);
* the writer emits every bound field and the artifact round-trips through validation;
* the Astra ae212a0 finding: the writer resolves the durable run/spec/candidate/pending-gate
  context before writing (a foreign one refuses; a run-level approval carries no gate), and
  the checkpoint consumer/environment thread that same identity through resume so a committed
  artifact naming a foreign run/gate refuses.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src", _ROOT / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import approve_workflow as aw  # noqa: E402
import promote as pr  # noqa: E402
import run_workflow as rw  # noqa: E402

from agentic_dynamics.core import decision_contract as dc  # noqa: E402
from agentic_dynamics.runtime.workflow_runner import (  # noqa: E402
    _checkpoint_approval_valid,
)


def _git(wd: Path, *argv: str) -> str:
    out = subprocess.run(["git", *argv], cwd=wd, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    wd = tmp_path / "wd"
    wd.mkdir()
    _git(wd, "init", "-q")
    _git(wd, "config", "user.email", "t@t")
    _git(wd, "config", "user.name", "t")
    (wd / "work.txt").write_text("checkpoint work")
    _git(wd, "add", "-A")
    _git(wd, "commit", "-qm", "checkpoint work")
    return wd


def _approval(wd: Path, *, spec: str, phase: str, candidate: str, tree: str,
              extra: str = "") -> Path:
    path = wd / "approvals" / "right_spec" / "p1_approval.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nstatus: accepted\n---\n\n# Approval\n\n"
        f"purpose: checkpoint\nspec: {spec}\nphase: {phase}\n"
        f"candidate: {candidate}\ntree: {tree}\n"
        "operator: drseuss\ndate: 2026-09-12\n" + extra
    )
    return path


def _awaiting_run(*, spec: str, candidate: str, gate_ids: tuple[str, ...] = ()) -> str:
    """A REAL awaiting run in the (isolated) control db, with optional gate rows."""
    from agentic_dynamics.control.control_db import ControlDB, RunState

    with ControlDB.open() as db:
        run = db.create_run(spec_name=spec, model="test-model", state=RunState.RUNNING,
                            reason="test run")
        db.transition_run(run.run_id, RunState.AWAITING_APPROVAL, candidate_sha=candidate,
                          reason="checkpoint")
        for gate_id in gate_ids:
            db.record_gate_result(run.run_id, step_id="p1", verdict="pass",
                                  candidate_sha=candidate, gate_id=gate_id)
    return run.run_id


def _approve_args(wd: Path, **overrides):
    args = {
        "run_id": "",
        "gate_id": "",
        "candidate_sha": "",
        "spec": "right_spec",
        "phase": "p1",
        "operator": "drseuss",
        "reason": "",
        "workdir": str(wd),
        "dry_run": False,
    }
    args.update(overrides)
    return SimpleNamespace(**args)


def test_a_correctly_bound_approval_is_accepted(tmp_path):
    wd = _repo(tmp_path)
    ck, tree = _git(wd, "rev-parse", "HEAD"), _git(wd, "rev-parse", "HEAD^{tree}")
    _approval(wd, spec="right_spec", phase="p1", candidate=ck, tree=tree)
    _git(wd, "add", "-A")
    _git(wd, "commit", "-qm", "[approval] right_spec/p1")
    valid, evidence = _checkpoint_approval_valid(wd, "right_spec", "p1", ck)
    assert valid is True, evidence


def test_a_wrong_scope_approval_is_refused(tmp_path):
    """The review's reproduction: wrong spec AND phase AND candidate AND tree was ACCEPTED."""
    wd = _repo(tmp_path)
    ck = _git(wd, "rev-parse", "HEAD")
    _approval(
        wd, spec="WRONG_SPEC", phase="WRONG_PHASE",
        candidate="f" * 40, tree="e" * 40,
    )
    _git(wd, "add", "-A")
    _git(wd, "commit", "-qm", "[approval] wrong scope")
    valid, evidence = _checkpoint_approval_valid(wd, "right_spec", "p1", ck)
    assert valid is False
    assert {"spec", "phase", "candidate_sha", "tree"} <= set(evidence["failed_checks"])


def test_the_validator_binds_run_and_gate():
    decision = dc.parse_approval_decision(
        "# x\n\n- operator: drseuss\n- date: 2026-09-12\n- run: run-1\n- gate: gate-1\n"
    )
    assert dc.validate_decision(decision, run_id="run-1", gate_id="gate-1") == []
    failed = dc.validate_decision(decision, run_id="run-2", gate_id="gate-2")
    assert "run_id" in failed and "gate_id" in failed


def test_the_checkpoint_refuses_a_foreign_run_and_gate(tmp_path):
    """The Astra finding's consumer probe: a committed approval matching spec/phase/
    candidate/tree but naming a FOREIGN run and gate was ACCEPTED — now refused."""
    wd = _repo(tmp_path)
    ck, tree = _git(wd, "rev-parse", "HEAD"), _git(wd, "rev-parse", "HEAD^{tree}")
    _approval(wd, spec="right_spec", phase="p1", candidate=ck, tree=tree,
              extra="run: foreign-run\ngate: foreign-gate\n")
    _git(wd, "add", "-A")
    _git(wd, "commit", "-qm", "[approval] foreign run and gate")
    valid, evidence = _checkpoint_approval_valid(
        wd, "right_spec", "p1", ck, run_id="run-1", gate_id="gate-1"
    )
    assert valid is False
    assert {"run_id", "gate_id"} <= set(evidence["failed_checks"])


def test_the_checkpoint_passes_a_matching_run_and_gate(tmp_path):
    wd = _repo(tmp_path)
    ck, tree = _git(wd, "rev-parse", "HEAD"), _git(wd, "rev-parse", "HEAD^{tree}")
    _approval(wd, spec="right_spec", phase="p1", candidate=ck, tree=tree,
              extra="run: run-1\ngate: gate-1\n")
    _git(wd, "add", "-A")
    _git(wd, "commit", "-qm", "[approval] matching run and gate")
    valid, evidence = _checkpoint_approval_valid(
        wd, "right_spec", "p1", ck, run_id="run-1", gate_id="gate-1"
    )
    assert valid is True, evidence


def test_the_checkpoint_passes_a_run_level_approval_with_no_gate(tmp_path):
    """An explicit run-level approval carries no gate; the expected identity is ''."""
    wd = _repo(tmp_path)
    ck, tree = _git(wd, "rev-parse", "HEAD"), _git(wd, "rev-parse", "HEAD^{tree}")
    _approval(wd, spec="right_spec", phase="p1", candidate=ck, tree=tree,
              extra="run: run-1\n")
    _git(wd, "add", "-A")
    _git(wd, "commit", "-qm", "[approval] run-level")
    valid, evidence = _checkpoint_approval_valid(
        wd, "right_spec", "p1", ck, run_id="run-1", gate_id=""
    )
    assert valid is True, evidence


def test_promote_refuses_an_uncommitted_in_worktree_approval(tmp_path):
    """No mutable fallback: the artifact exists on disk but was never committed."""
    wd = _repo(tmp_path)
    path = wd / "approvals" / "s" / "p_approval.md"
    path.parent.mkdir(parents=True)
    path.write_text(f"candidate: {_git(wd, 'rev-parse', 'HEAD')}\n")
    args = SimpleNamespace(approval=str(path), workdir=str(wd), spec="s")
    with pytest.raises(pr._PromoteAwaitingError, match="not committed"):
        pr._load_approval(args, {})


def test_approval_commit_refuses_a_dirty_index(tmp_path):
    """The staged-edit ride-along: a staged unrelated change refuses the approval commit."""
    wd = _repo(tmp_path)
    head = _git(wd, "rev-parse", "HEAD")
    (wd / "staged_edit.py").write_text("sneaky = True\n")
    _git(wd, "add", "staged_edit.py")  # staged, uncommitted
    artifact = wd / "approvals" / "s" / "p_approval.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("operator: drseuss\n")
    args = SimpleNamespace(workdir=str(wd), spec="s", phase="p", candidate_sha=head,
                           operator="drseuss")
    with pytest.raises(aw._ApproveRefusedError, match="staged changes"):
        aw._commit_artifact(args, artifact)


def test_the_writer_emits_every_bound_field_and_round_trips(tmp_path):
    wd = _repo(tmp_path)
    head, tree = _git(wd, "rev-parse", "HEAD"), _git(wd, "rev-parse", "HEAD^{tree}")
    args = SimpleNamespace(
        workdir=str(wd), spec="s", phase="p", run_id="run-1", gate_id="gate-1",
        candidate_sha=head, operator="drseuss", reason="", dry_run=False,
    )
    artifact = aw._write_artifact(args)
    decision = dc.parse_approval_decision(artifact.read_text())
    assert (decision.spec, decision.phase) == ("s", "p")
    assert (decision.run_id, decision.gate_id) == ("run-1", "gate-1")
    assert (decision.candidate_sha, decision.tree) == (head, tree)
    assert decision.operator == "drseuss"
    assert (
        dc.validate_decision(
            decision, purpose=dc.PURPOSE_CHECKPOINT, spec="s", phase="p",
            candidate_sha=head, tree=tree, run_id="run-1", gate_id="gate-1",
        )
        == []
    )


def test_the_writer_refuses_a_foreign_run_context(tmp_path):
    """The Astra finding's writer probe: a foreign spec/candidate/gate used to be recorded
    because the writer only checked "the run exists and is awaiting" — now each mismatch
    refuses before anything is written."""
    wd = _repo(tmp_path)
    head = _git(wd, "rev-parse", "HEAD")
    run_id = _awaiting_run(spec="right_spec", candidate=head, gate_ids=("gate-1",))

    with pytest.raises(aw._ApproveRefusedError, match="spec"):
        aw._run_approval(_approve_args(wd, run_id=run_id, spec="other_spec",
                                       candidate_sha=head, gate_id="gate-1"))
    with pytest.raises(aw._ApproveRefusedError, match="candidate"):
        aw._run_approval(_approve_args(wd, run_id=run_id, spec="right_spec",
                                       candidate_sha="f" * 40, gate_id="gate-1"))
    with pytest.raises(aw._ApproveRefusedError, match="gate"):
        aw._run_approval(_approve_args(wd, run_id=run_id, spec="right_spec",
                                       candidate_sha=head, gate_id="gate-ghost"))
    # a run-level (empty) approval never clears a named gate
    with pytest.raises(aw._ApproveRefusedError, match="gate"):
        aw._run_approval(_approve_args(wd, run_id=run_id, spec="right_spec",
                                       candidate_sha=head, gate_id=""))
    # and nothing was written or committed by any refusal
    assert not (wd / "approvals").exists()


def test_the_writer_refuses_an_unrelated_gate_on_a_gateless_run(tmp_path):
    """A run stopped without a gate row: the durable identity is run-level (''), so a
    nonempty gate that exists nowhere must still refuse."""
    wd = _repo(tmp_path)
    head = _git(wd, "rev-parse", "HEAD")
    run_id = _awaiting_run(spec="right_spec", candidate=head)
    with pytest.raises(aw._ApproveRefusedError, match="gate"):
        aw._run_approval(_approve_args(wd, run_id=run_id, spec="right_spec",
                                       candidate_sha=head, gate_id="gate-ghost"))
    assert not (wd / "approvals").exists()


def test_the_writer_accepts_a_matching_run_and_gate(tmp_path, monkeypatch):
    wd = _repo(tmp_path)
    head = _git(wd, "rev-parse", "HEAD")
    run_id = _awaiting_run(spec="right_spec", candidate=head, gate_ids=("gate-1",))
    monkeypatch.setattr(aw, "_emit_approval_decision", lambda *a, **k: {})

    aw._run_approval(_approve_args(wd, run_id=run_id, spec="right_spec",
                                   candidate_sha=head, gate_id="gate-1"))

    decision = dc.parse_approval_decision(
        (wd / "approvals" / "right_spec" / "p1_approval.md").read_text()
    )
    assert (decision.run_id, decision.gate_id) == (run_id, "gate-1")
    from agentic_dynamics.control.control_db import ControlDB

    with ControlDB.open_read_only() as db:
        rows = db.approvals(run_id)
    assert [(a.gate_id, a.candidate_sha) for a in rows] == [("gate-1", head)]


def test_the_writer_accepts_a_run_level_approval_with_no_gate(tmp_path, monkeypatch):
    wd = _repo(tmp_path)
    head = _git(wd, "rev-parse", "HEAD")
    run_id = _awaiting_run(spec="right_spec", candidate=head)
    monkeypatch.setattr(aw, "_emit_approval_decision", lambda *a, **k: {})

    aw._run_approval(_approve_args(wd, run_id=run_id, spec="right_spec",
                                   candidate_sha=head, gate_id=""))

    decision = dc.parse_approval_decision(
        (wd / "approvals" / "right_spec" / "p1_approval.md").read_text()
    )
    assert (decision.run_id, decision.gate_id) == (run_id, "")


def test_the_resume_resolution_binds_the_durable_run_and_gate(tmp_path):
    """The composition-root resolution: the continuation's parent run is the expected run;
    its gate context is the expected gate ('' for a gate-less run, None when ambiguous)."""
    from agentic_dynamics.control.control_db import ControlDB, RunState

    head = "a" * 40
    with ControlDB.open() as db:
        parent = db.create_run(spec_name="right_spec", model="m", state=RunState.RUNNING,
                               candidate_sha=head)
        db.transition_run(parent.run_id, RunState.AWAITING_APPROVAL, reason="checkpoint")
        gated = db.create_run(spec_name="right_spec", model="m", state=RunState.RUNNING,
                              candidate_sha=head)
        db.transition_run(gated.run_id, RunState.AWAITING_APPROVAL, reason="checkpoint")
        db.record_gate_result(gated.run_id, step_id="p1", verdict="pass",
                              candidate_sha=head, gate_id="gate-1")
        db.record_gate_result(gated.run_id, step_id="p1", verdict="pass",
                              candidate_sha=head, gate_id="gate-2")

    with ControlDB.open_read_only() as db:
        assert rw._resolve_approval_identity(
            db, {"parent_run_id": parent.run_id}
        ) == (parent.run_id, "")
        assert rw._resolve_approval_identity(
            db, {"parent_run_id": gated.run_id}
        ) == (gated.run_id, None)
        assert rw._resolve_approval_identity(db, {}) == (None, None)
        assert rw._resolve_approval_identity(None, {"parent_run_id": parent.run_id}) == (None, None)


