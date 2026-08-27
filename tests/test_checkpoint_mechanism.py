"""Mechanical human checkpoint tests (cap_runner_hardening2 §Gap 3).

The checkpoint is the mechanical fix for the revamp3 violation: p2 (the design + human
checkpoint) committed the delta preview AND the unsigned approval template, then the runner
moved straight into p3-p6 and recorded ``ok: True`` while the approval sat unsigned — "STOP
for the operator" was a sentence in the prompt, and prompt rules without mechanics get
ignored (measured three times).

The mechanism: a phase declaring ``checkpoint: true`` that completes successfully records the
campaign state ``awaiting_operator_approval`` (phase status ``awaiting`` — a designed stop, not
an error) and EXITS CLEANLY. On ``--resume`` the runner verifies every completed checkpoint
phase's approval contract BEFORE proceeding: ``approvals/<spec>/<phase>_approval.md`` committed
at HEAD, authored AFTER the checkpoint commit (a descendant), with a REAL operator signature
(non-placeholder) + a date. Unsatisfied → the resume refuses to proceed and stops awaiting.

The revamp3 p2 state is REPLAYED as the regression proof on the REAL artifact: the commit
``ee12c9c5b`` carried ``approvals/cap_site_revamp3_design_approval.md`` — an intentionally
unsigned template with ``SIGNED-BY-OPERATOR: <required: ...>`` and ``DATE: <required: ...>``
placeholder fields. Materializing that tree hermetically and running the contract check proves
the unsigned template does not authorize a resume.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from agentic_dynamics.experiment.experiment_spec import load_spec, validate_spec
from agentic_dynamics.runtime.workflow_runner import (
    _checkpoint_approval_valid,
    _parse_checkpoint_approval,
    _phase_commit_sha,
    run_workflow,
)

REPO = Path(__file__).resolve().parent.parent
SPEC = REPO / "workflows" / "repository" / "control_room_portal.yaml"

#: The revamp3 p2 checkpoint commit — the measured violator: delta preview + unsigned approval
#: template committed together, then the runner moved into p3-p6 regardless.
REVAMP3_P2_COMMIT = "ee12c9c5bad26fa11d204c4bd6e261dc5281724f"
REVAMP3_GOAL = "Revamp the site by KEEPING the instrument and ADDING the field layer"

MINIMAL_SPEC_YAML = """\
name: checkpoint_test
question: checkpoint fixture
version: "0.1"
artifact_kind: workflow
intent: mutate
side_effects:
  repository: true
  external_services: false
workflow:
  kind: agent_task
  params:
    language: python
    phases:
      - name: design
        kind: agent
        checkpoint: true
        timeout: 120
        prompt: |
          {goal}
      - name: implement
        kind: agent
        timeout: 120
        prompt: |
          {goal}
factors:
  - {name: model, levels: [deepseek/deepseek-v4-flash]}
design: factorial
rules: []
metrics: []
comparison: null
"""


def _minimal_spec(tmp_path: Path):
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(MINIMAL_SPEC_YAML)
    return load_spec(spec_path)


def _fake_agent(**overrides):
    from types import SimpleNamespace

    base = dict(
        prompt_tokens=10, completion_tokens=20, reasoning_tokens=5, total_tokens=35,
        estimated_cost_usd=0.001, files_created=[], files_modified=[], final_response="done",
        ok=True, exit_code=0, error="",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def _git_init(workdir: Path) -> None:
    _git("init", "-q", cwd=workdir)
    _git("config", "user.email", "t@t", cwd=workdir)
    _git("config", "user.name", "t", cwd=workdir)


def _materialize_commit_tree(commit: str, target: Path) -> str:
    """Materialize ``commit``'s full tree into ``target`` (fresh repo) and commit it.

    git trees are content-addressed, so the hermetic copy is byte-identical to the real
    revamp3 p2 commit's tree (including its unsigned approval template). Returns the tree hash.
    """
    archive = subprocess.run(["git", "archive", commit], cwd=REPO, capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", str(target)], input=archive.stdout, check=True)
    _git_init(target)
    _git("add", "-Af", cwd=target)
    _git("commit", "-qm", "attempt A", cwd=target)
    return _git("rev-parse", "HEAD^{tree}", cwd=target).stdout.strip()


def _approval_text(*, operator: str = "jane@example.com", date: str = "2026-08-27") -> str:
    return (
        f"# Operator approval\n\n"
        f"- operator: {operator}\n"
        f"- date: {date}\n"
    )


# ── the revamp3 REPLAY (the regression proof) ────────────────────────────────


def test_revamp3_unsigned_template_is_refused():
    """The revamp3 p2 state replayed on the REAL artifact: the checkpoint committed its work
    AND the unsigned approval template together — the contract refuses (the template was
    authored AT the checkpoint commit, not after it), so the "runner proceeds to p3-p6 anyway"
    shape is impossible."""
    import shutil
    import tempfile

    wd = Path(tempfile.mkdtemp(prefix="revamp3_replay_", dir="/tmp")) / "wd"
    wd.mkdir()
    try:
        # reconstruct the revamp3 p2 state hermetically: the real commit's tree (design doc +
        # phase log + the actual unsigned template content, now at the canonical contract path
        # approvals/<spec>/<phase>_approval.md), committed together as the checkpoint.
        _materialize_commit_tree(REVAMP3_P2_COMMIT, wd)
        real_template = subprocess.run(
            ["git", "show", f"{REVAMP3_P2_COMMIT}:approvals/cap_site_revamp3_design_approval.md"],
            cwd=REPO, capture_output=True, text=True, check=True,
        ).stdout
        ap = wd / "approvals" / "cap_site_revamp3"
        ap.mkdir(parents=True)
        (ap / "p2_design_with_human_checkpoint_approval.md").write_text(real_template)
        _git("add", "-Af", cwd=wd)
        _git("commit", "-qm", "p2 checkpoint: delta preview + unsigned approval template", cwd=wd)
        head = _git("rev-parse", "HEAD", cwd=wd).stdout.strip()

        valid, evidence = _checkpoint_approval_valid(
            wd, "cap_site_revamp3", "p2_design_with_human_checkpoint", head
        )
        assert valid is False
        # the template was committed WITH the work → not a descendant-authored approval
        assert "authored_after_checkpoint" in evidence["failed_checks"]
    finally:
        shutil.rmtree(wd.parent, ignore_errors=True)


def test_revamp3_template_signature_fields_are_placeholders():
    """The real revamp3 template's signature block parses and fails the placeholder check: an
    operator who "signed" the template by filling SIGNED-BY-OPERATOR with a placeholder word (or
    leaving the angle-bracket template) does not authorize anything."""
    raw = subprocess.run(
        ["git", "show", f"{REVAMP3_P2_COMMIT}:approvals/cap_site_revamp3_design_approval.md"],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout
    parsed = _parse_checkpoint_approval(raw)
    # the template's signature block fields are recognized
    assert "operator" in parsed and "date" in parsed
    # and both are placeholders (<required: ...> — angle-bracketed templates never sign)
    from agentic_dynamics.runtime.workflow_runner import _date_is_valid, _operator_is_placeholder

    assert _operator_is_placeholder(parsed["operator"]) is True
    assert _date_is_valid(parsed["date"]) is False


def test_placeholder_signature_after_checkpoint_is_refused(tmp_path):
    """A signed-looking approval committed AFTER the checkpoint but with placeholder values
    (the revamp3 "the operator filled it in without signing" shape) is refused."""
    spec = _minimal_spec(tmp_path)
    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / "work.txt").write_text("checkpoint work")
    _git_init(wd)
    _git("add", "-Af", cwd=wd)
    _git("commit", "-qm", "[workflow] design — g", cwd=wd)  # the checkpoint commit
    ap = wd / "approvals" / spec.name
    ap.mkdir(parents=True)
    (ap / "design_approval.md").write_text(_approval_text(operator="<required: operator name>"))
    _git("add", "-Af", cwd=wd)
    _git("commit", "-qm", "signed", cwd=wd)  # a descendant of the checkpoint commit

    valid, evidence = _checkpoint_approval_valid(
        wd, spec.name, "design", _phase_commit_sha(wd, "design", "g")
    )
    assert valid is False
    assert evidence["committed_at_head"] is True
    assert evidence["absent_at_checkpoint_commit"] is True
    assert evidence["checkpoint_is_ancestor"] is True
    assert "operator" in evidence["failed_checks"]  # placeholder signature


# ── the checkpoint stop (both directions) ────────────────────────────────────


def test_checkpoint_phase_stops_run_awaiting(tmp_path):
    """(a) A checkpoint phase that completes successfully stops the run with
    awaiting_operator_approval — phase status ``awaiting``, result awaiting, and NO later
    phase runs (the p3-p6 shape is impossible in a single run)."""
    spec = _minimal_spec(tmp_path)
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)
    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        calls.append(1)
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "design.md").write_text("delta preview")
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=wd, run_agentic_fn=agent)
    assert len(result.phases) == 1  # implement did NOT run
    assert len(calls) == 1
    p = result.phases[0]
    assert p.phase == "design"
    assert p.status == "awaiting"
    assert p.commit_hash  # the checkpoint's work was committed
    assert result.awaiting is True
    assert result.awaiting_phase == "design"
    assert result.awaiting_reason == "checkpoint"
    assert result.ok is False  # a designed stop, not a completed run
    assert result.to_dict()["awaiting"] is True
    # the awaiting status rides the ledger (distinct from failed)
    assert result.to_dict()["phases"][0]["status"] == "awaiting"


def test_checkpoint_phase_that_fails_is_not_awaiting(tmp_path):
    """A checkpoint phase that FAILS stays failed (a designed stop is only for successful
    completion) and the run stops with the failure, never awaiting."""
    spec = _minimal_spec(tmp_path)
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        return _fake_agent(ok=False, error="boom")

    result = run_workflow(spec, goal="g", model="m", workdir=wd, run_agentic_fn=agent)
    assert result.phases[0].status == "failed"
    assert "boom" in result.phases[0].error
    assert result.awaiting is False
    assert result.ok is False


# ── resume gating (the refusal + the legit proceed) ──────────────────────────


def _completed_checkpoint_wd(tmp_path, *, name="wd"):
    """A worktree whose checkpoint phase (``design``) is already committed — the state a resume
    sees after the first run stopped awaiting."""
    wd = tmp_path / name
    wd.mkdir()
    (wd / "work.txt").write_text("checkpoint work")
    _git_init(wd)
    _git("add", "-Af", cwd=wd)
    _git("commit", "-qm", "[workflow] design — g", cwd=wd)
    return wd


def test_resume_refuses_without_approval(tmp_path):
    """(a) resume without the signed artifact: the run refuses to proceed past the completed
    checkpoint and stops again with awaiting_operator_approval — NO further phase runs."""
    spec = _minimal_spec(tmp_path)
    wd = _completed_checkpoint_wd(tmp_path)
    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        calls.append(1)
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=wd, run_agentic_fn=agent, resume=True)
    assert calls == []  # nothing ran
    assert result.phases == []
    assert result.awaiting is True
    assert result.awaiting_phase == "design"
    assert result.awaiting_reason == "approval_refused"


def test_resume_proceeds_with_signed_artifact_committed_after(tmp_path):
    """(b) the operator signs + commits the approval AFTER the checkpoint commit: the resume
    proceeds past the checkpoint and runs the later phases."""
    spec = _minimal_spec(tmp_path)
    wd = _completed_checkpoint_wd(tmp_path)
    ap = wd / "approvals" / spec.name
    ap.mkdir(parents=True)
    (ap / "design_approval.md").write_text(_approval_text())
    _git("add", "-Af", cwd=wd)
    _git("commit", "-qm", "operator approval (descendant of the checkpoint)", cwd=wd)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "impl.md").write_text("implemented")
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=wd, run_agentic_fn=agent, resume=True)
    assert result.awaiting is False
    assert [p.phase for p in result.phases] == ["implement"]
    assert result.phases[0].status == "ok"
    assert result.ok is True


def test_resume_refuses_approval_committed_at_checkpoint(tmp_path):
    """(c) an approval committed WITH the checkpoint's work (present at the checkpoint commit —
    the revamp3 exact shape) is refused: the approval must be authored AFTER the checkpoint."""
    spec = _minimal_spec(tmp_path)
    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / "work.txt").write_text("checkpoint work")
    ap = wd / "approvals" / spec.name
    ap.mkdir(parents=True)
    (ap / "design_approval.md").write_text(_approval_text())
    _git_init(wd)
    _git("add", "-Af", cwd=wd)
    _git("commit", "-qm", "[workflow] design — g", cwd=wd)  # approval rides ALONG with the work

    def agent(prompt, *, model, backend, workdir, **kwargs):
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=wd, run_agentic_fn=agent, resume=True)
    assert result.awaiting is True
    assert result.awaiting_reason == "approval_refused"
    # the direct check names the refusal reason
    valid, evidence = _checkpoint_approval_valid(
        wd, spec.name, "design", _phase_commit_sha(wd, "design", "g")
    )
    assert valid is False
    assert "authored_after_checkpoint" in evidence["failed_checks"]


def test_resume_refuses_missing_artifact(tmp_path):
    """The direct contract: no artifact at all → refused with no_artifact."""
    wd = _completed_checkpoint_wd(tmp_path)
    valid, evidence = _checkpoint_approval_valid(
        wd, "checkpoint_test", "design", _phase_commit_sha(wd, "design", "g")
    )
    assert valid is False
    assert "no_artifact" in evidence["failed_checks"]


def test_resume_refuses_wrong_commit_order_pre_checkpoint(tmp_path):
    """(c) an approval committed BEFORE the checkpoint's work — present at the checkpoint commit
    because it predates it — is refused (a signed-before-the-work artifact does not authorize)."""
    spec = _minimal_spec(tmp_path)
    wd = tmp_path / "wd"
    wd.mkdir()
    ap = wd / "approvals" / spec.name
    ap.mkdir(parents=True)
    (ap / "design_approval.md").write_text(_approval_text())
    _git_init(wd)
    _git("add", "-Af", cwd=wd)
    _git("commit", "-qm", "signed first", cwd=wd)  # approval BEFORE any checkpoint work
    (wd / "work.txt").write_text("checkpoint work")
    _git("add", "-Af", cwd=wd)
    _git("commit", "-qm", "[workflow] design — g", cwd=wd)  # the checkpoint commit

    valid, evidence = _checkpoint_approval_valid(
        wd, spec.name, "design", _phase_commit_sha(wd, "design", "g")
    )
    assert valid is False
    assert "authored_after_checkpoint" in evidence["failed_checks"]


# ── parser + validator + non-checkpoint campaign surfaces ───────────────────


def test_parse_checkpoint_approval_handles_revamp3_template_fields():
    text = (
        "SIGNED-BY-OPERATOR: jane@example.com\n"
        "DATE: 2026-08-27\n"
        "APPROVED DESIGN REVISION: abc123\n"
        "NOTES OR SPECIFIC WAIVERS: none\n"
    )
    parsed = _parse_checkpoint_approval(text)
    assert parsed["operator"] == "jane@example.com"
    assert parsed["date"] == "2026-08-27"


def test_spec_validator_rejects_non_boolean_checkpoint(tmp_path):
    spec_path = tmp_path / "bad.yaml"
    spec_path.write_text(MINIMAL_SPEC_YAML.replace("checkpoint: true", "checkpoint: \"yes\""))
    spec = load_spec(spec_path)
    errors = validate_spec(spec)
    assert any("checkpoint must be a boolean" in e for e in errors)


def test_cap_site_revamp3_spec_carries_the_mechanical_marker():
    """The measured violator now declares the checkpoint mechanically: p2 of cap_site_revamp3
    is ``checkpoint: true`` and the spec still validates."""
    spec = load_spec(REPO / "workflows" / "repository" / "cap_site_revamp3.yaml")
    assert validate_spec(spec) == []
    p2 = next(p for p in spec.workflow.params["phases"] if p["name"] == "p2_design_with_human_checkpoint")
    assert p2.get("checkpoint") is True


def test_non_checkpoint_campaigns_are_unaffected(tmp_path):
    """A campaign with no checkpoint marker runs exactly as before: no awaiting state, all
    phases run, the existing phase kinds unchanged."""
    spec = load_spec(SPEC)
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)
    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        calls.append(1)
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / f"f{len(calls)}.md").write_text(str(len(calls)))
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=wd, run_agentic_fn=agent)
    assert result.awaiting is False
    assert result.awaiting_reason == ""
    assert all(p.status == "ok" for p in result.phases)
    assert result.ok is True
    # the four phases of control_room_portal ran in order (3 agents + the verify test phase)
    assert [p.phase for p in result.phases] == ["scope", "ux_design", "implement", "verify"]
