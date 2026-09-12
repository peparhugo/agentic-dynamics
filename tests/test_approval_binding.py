"""Wave A4 — exact approval binding: the review's #2 reproductions, flipped to refusals.

* the checkpoint consumer accepted an artifact naming the WRONG spec/phase/candidate/tree
  (it validated ``purpose`` only) — the same fixture now FAILS with the named checks, and the
  correct binding still passes;
* the validator binds the RUN and GATE too (the review: "no expected-run or expected-gate
  parameters");
* the promoter no longer falls back to a mutable working copy for an in-worktree artifact;
* an approval commit refuses a dirty index (the staged-edit ride-along reproduction);
* the writer emits every bound field and the artifact round-trips through validation.
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
    path = _approval(
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
