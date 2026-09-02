"""Per-phase evidence tests — the ``control_db_evidence`` e1 write side (BOTH directions).

Two layers, each proven against real storage (no mocks of the database):

* **the control writer** (:func:`control.phase_evidence.record_phase_evidence`) — one
  :class:`PhaseEvidence` becomes one ``step_attempts`` row + one ``gate_results`` row per fired
  gate, reusing the control db's existing writers. Includes the retry contract: a retried step
  records ``attempt_no`` 1 then 2, satisfying the ``uq_step_attempts_run_step_no`` UNIQUE index
  instead of colliding with it.
* **the engine seam** — running a synthetic spec through ``run_workflow`` with the real recorder
  bound to a real control db proves the write side is actually CALLED in the phase loop (not
  merely testable): every executed phase lands a row, a failed phase lands a FAILED attempt
  (never skipped), and a control-db outage during the phase write does not fail the run (the
  warning is named).

Both directions of the e1 mandate are exercised because each layer can lie on its own: the
writer can be correct while nothing calls it (the pre-e1 state — ``record_gate_result`` had zero
production callers), and the engine can call a seam that writes nothing. The engine tests bind
the REAL writer, so both halves have to be true for a row to appear.
"""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from agentic_dynamics.control.control_db import AttemptState, ControlDB, GateVerdict, RunState
from agentic_dynamics.control.phase_evidence import (
    make_phase_evidence_recorder,
    record_phase_evidence,
)
from agentic_dynamics.experiment.experiment_spec import load_spec
from agentic_dynamics.runtime.phase_evidence import (
    PhaseEvidence,
    PhaseGateEvidence,
    iso_now,
)
from agentic_dynamics.runtime.workflow_runner import run_workflow

SPEC = Path(__file__).resolve().parent.parent / "workflows" / "repository" / "control_room_portal.yaml"

#: A phase-boundary candidate sha for the gate rows — must be non-empty (the schema's CHECK and
#: the writer's ControlFieldError both refuse a verdict about nothing).
CANDIDATE = "a" * 40


def _fake_agent(**overrides):
    base = dict(
        prompt_tokens=10,
        completion_tokens=20,
        reasoning_tokens=5,
        total_tokens=35,
        estimated_cost_usd=0.001,
        files_created=["docs/scope.md"],
        files_modified=[],
        final_response="done",
        ok=True,
        exit_code=0,
        error="",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _evidence(**overrides) -> PhaseEvidence:
    base = PhaseEvidence(
        step_id="scope",
        status="ok",
        started_at="2026-09-02T00:00:00Z",
        ended_at="2026-09-02T00:01:00Z",
        candidate_sha=CANDIDATE,
        model="openai/gpt-5.6-sol",
        tokens=35,
        cost_usd=0.001,
        exit_code=0,
    )
    return replace(base, **overrides)


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "control" / "control.db"


@pytest.fixture()
def db(db_path):
    handle = ControlDB.open(db_path)
    yield handle
    handle.close()


def _make_run(db: ControlDB) -> str:
    return db.create_run(spec_name="e1_phase_evidence", model="openai/gpt-5.6-sol",
                         state=RunState.RUNNING).run_id


# ── 1. The control writer (record_phase_evidence) ────────────────────────────────────────────


def test_record_phase_evidence_writes_one_attempt_row_with_all_fields(db):
    """One executed phase -> one step_attempts row with state/tokens/cost/model populated."""
    run_id = _make_run(db)
    evidence = _evidence(gates=(
        PhaseGateEvidence(gate="commit_gate", verdict="fail", reason="COMMIT_PREFIX",
                          evidence={"reason": "COMMIT_PREFIX", "subjects": ["plain"]}),
    ))

    attempt, gates = record_phase_evidence(db, run_id, evidence)

    assert attempt.attempt_no == 1
    assert attempt.step_id == "scope"
    assert attempt.model == "openai/gpt-5.6-sol"
    assert attempt.state is AttemptState.OK
    assert attempt.tokens == 35
    assert attempt.cost_usd == 0.001
    assert attempt.exit_code == 0
    assert attempt.started_at and attempt.ended_at
    # Persisted, not just returned.
    stored = db.attempts(run_id)
    assert len(stored) == 1
    assert stored[0].state is AttemptState.OK
    assert stored[0].tokens == 35 and stored[0].cost_usd == 0.001


def test_record_phase_evidence_writes_one_gate_row_per_fired_gate(db):
    """A gate that fired leaves one gate_results row bound to the candidate; clean gates leave none."""
    run_id = _make_run(db)
    fired = PhaseEvidence(
        step_id="p1", status="failed", started_at=iso_now(), ended_at=iso_now(),
        candidate_sha=CANDIDATE, gates=(
            PhaseGateEvidence(gate="deploy_gate", verdict="fail", reason="DEPLOY_GATE",
                              evidence={"reason": "DEPLOY_GATE", "violations": []}),
            PhaseGateEvidence(gate="commit_gate", verdict="fail", reason="COMMIT_PREFIX",
                              evidence={"reason": "COMMIT_PREFIX"}),
        ),
    )
    clean = PhaseEvidence(step_id="p2", status="ok", started_at=iso_now(), ended_at=iso_now(),
                          candidate_sha=CANDIDATE, gates=())

    record_phase_evidence(db, run_id, fired)
    record_phase_evidence(db, run_id, clean)

    rows = db.gate_results(run_id)
    assert len(rows) == 2  # only the fired gates of p1
    assert {r.step_id for r in rows} == {"p1"}
    assert all(r.verdict is GateVerdict.FAIL for r in rows)
    assert all(r.candidate_sha == CANDIDATE for r in rows)
    assert {r.gate_id is not None for r in rows}


def test_an_approved_relabel_gate_is_recorded_as_a_pass(db):
    """The one fired-gate reason that is not a violation (operator-approved tree reuse) -> PASS."""
    run_id = _make_run(db)
    evidence = _evidence(gates=(
        PhaseGateEvidence(gate="relabel_gate", verdict="pass", reason="APPROVED",
                          evidence={"reason": "APPROVED", "operator": "controller"}),
    ))

    _, gates = record_phase_evidence(db, run_id, evidence)
    assert len(gates) == 1
    assert gates[0].verdict is GateVerdict.PASS


def test_a_failed_phase_records_a_failed_attempt_never_skipped(db):
    """A FAILED phase records state=failed (the AttemptState vocabulary has no 'collapsed')."""
    run_id = _make_run(db)
    attempt, _ = record_phase_evidence(
        db, run_id, _evidence(status="failed", error="boom", exit_code=1, tokens=12, cost_usd=0.01)
    )
    assert attempt.state is AttemptState.FAILED
    assert attempt.error == "boom"
    assert attempt.exit_code == 1
    assert attempt.tokens == 12 and attempt.cost_usd == 0.01


def test_a_checkpoint_awaiting_phase_records_an_awaiting_attempt(db):
    """A designed checkpoint stop is awaiting at the attempt level, never a failure."""
    run_id = _make_run(db)
    attempt, _ = record_phase_evidence(db, run_id, _evidence(status="awaiting", step_id="gate"))
    assert attempt.state is AttemptState.AWAITING


def test_a_retried_phase_records_attempt_no_1_then_2(db):
    """The UNIQUE index contract: a retry is a NEW row with the next attempt_no, never a rewrite."""
    run_id = _make_run(db)
    first = record_phase_evidence(
        db, run_id, _evidence(status="failed", error="transient", ended_at="2026-09-02T00:01:00Z")
    )[0]
    second = record_phase_evidence(
        db, run_id, _evidence(status="ok", ended_at="2026-09-02T00:03:00Z")
    )[0]

    assert first.attempt_no == 1
    assert second.attempt_no == 2
    rows = db.attempts(run_id, step_id="scope")
    assert [a.attempt_no for a in rows] == [1, 2]
    assert [a.state for a in rows] == [AttemptState.FAILED, AttemptState.OK]


def test_a_gate_result_without_a_candidate_sha_is_refused_not_written_halfway(db):
    """record_gate_result enforces the candidate; the phase record rolls back as one unit."""
    run_id = _make_run(db)
    evidence = _evidence(gates=(
        PhaseGateEvidence(gate="commit_gate", verdict="fail", reason="COMMIT_PREFIX",
                          evidence={"reason": "COMMIT_PREFIX"}),
    ))
    from agentic_dynamics.control.control_db import ControlFieldError

    with pytest.raises(ControlFieldError):
        record_phase_evidence(db, run_id, replace(evidence, candidate_sha=""))
    assert db.attempts(run_id) == []  # no half-recorded phase


def test_make_phase_evidence_recorder_is_inert_without_a_run_row(db):
    """Child mode (--only-phase) and a missing db both bind no recorder — the engine seam is off."""
    assert make_phase_evidence_recorder(db, None) is None
    assert make_phase_evidence_recorder(None, "run-x") is None
    bound = make_phase_evidence_recorder(db, _make_run(db))
    assert bound is not None and callable(bound)


# ── 2. The engine seam (run_workflow calls the recorder in the phase loop) ───────────────────


def _spec_with_phases(n: int):
    spec = load_spec(SPEC)
    spec.workflow.params["phases"] = spec.workflow.params["phases"][:n]
    return spec


def _git_init(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)


def test_engine_records_two_attempt_rows_and_the_gate_results_phases_produced(
    tmp_path, monkeypatch
):
    """(a) after a 2-phase run with a fake agent, the db holds the real rows — one per executed
    phase (state/tokens/cost populated) + one gate_results row per gate verdict the phases
    produced. Phase 1 fires the commit gate (strict, no hook); phase 2 passes cleanly."""
    spec = _spec_with_phases(2)
    monkeypatch.setenv("FINOPS_COMMIT_GATE", "strict")  # no commit-msg hook; the gate fires
    repo = tmp_path / "work"
    repo.mkdir()
    _git_init(repo)

    db = ControlDB.open(tmp_path / "control" / "control.db")
    run_id = _make_run(db)
    recorder = make_phase_evidence_recorder(db, run_id)
    assert recorder is not None

    committed = {"phase1": False}

    def agent(prompt, *, model, backend, workdir, **kwargs):
        wd = Path(workdir)
        (wd / "docs").mkdir(exist_ok=True)
        (wd / "docs" / "scope.md").write_text("scope content")
        if not committed["phase1"]:
            # The agent makes a MANUAL commit with a plain (non-conforming) subject in phase 1.
            committed["phase1"] = True
            subprocess.run(["git", "add", "-A"], cwd=wd, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "plain manual commit"], cwd=wd, check=True)
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=repo, run_agentic_fn=agent,
                          stop_on_error=False, phase_evidence_recorder=recorder)

    assert [p.status for p in result.phases] == ["failed", "ok"]  # scope fails the gate
    attempts = db.attempts(run_id)
    assert [a.step_id for a in attempts] == ["scope", "ux_design"]
    assert [a.state for a in attempts] == [AttemptState.FAILED, AttemptState.OK]
    # state/tokens/cost populated — the fields verify(a) names.
    assert attempts[1].tokens == 35
    assert attempts[1].cost_usd == 0.001
    assert attempts[1].model == "m"
    assert "COMMIT_PREFIX" in attempts[0].error

    gates = db.gate_results(run_id)
    assert len(gates) == 1  # scope's commit_gate verdict; ux_design produced none
    assert gates[0].step_id == "scope"
    assert gates[0].verdict is GateVerdict.FAIL
    assert gates[0].candidate_sha  # bound to the phase's tree, never empty
    db.close()


def test_engine_records_a_failed_phase_as_a_failed_attempt(tmp_path):
    """(b) a FAILED phase records a failed step_attempt — never skipped, never absent."""
    spec = _spec_with_phases(1)
    repo = tmp_path / "work"
    repo.mkdir()
    _git_init(repo)
    db = ControlDB.open(tmp_path / "control" / "control.db")
    run_id = _make_run(db)
    recorder = make_phase_evidence_recorder(db, run_id)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        return _fake_agent(ok=False, error="boom", exit_code=1)

    result = run_workflow(spec, goal="g", model="m", workdir=repo, run_agentic_fn=agent,
                          phase_evidence_recorder=recorder)
    assert result.phases[0].status == "failed"
    assert result.ok is False

    attempts = db.attempts(run_id)
    assert len(attempts) == 1
    assert attempts[0].state is AttemptState.FAILED
    assert attempts[0].error == "boom"
    assert attempts[0].exit_code == 1
    db.close()


def test_control_db_outage_during_the_phase_write_does_not_fail_the_run(tmp_path, capsys):
    """(d) a control-db outage mid-run (the recorder's handle dies) never fails the phase — the
    run completes, both phases ok, and the loss is a NAMED warning, never silence."""
    spec = _spec_with_phases(2)
    db = ControlDB.open(tmp_path / "control" / "control.db")
    run_id = _make_run(db)
    recorder = make_phase_evidence_recorder(db, run_id)
    db.close()  # the outage: the writer's handle is gone before any phase completes

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path,
                          commit=False, run_agentic_fn=lambda *a, **k: _fake_agent(),
                          phase_evidence_recorder=recorder)

    assert result.ok is True
    assert [p.status for p in result.phases] == ["ok", "ok"]
    err = capsys.readouterr().err
    assert "control-db per-phase evidence write failed" in err


def test_engine_is_byte_identical_without_a_recorder(tmp_path):
    """No recorder injected -> the seam is inert and every phase still runs (pre-e1 behaviour)."""
    spec = _spec_with_phases(2)
    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path,
                          commit=False, run_agentic_fn=lambda *a, **k: _fake_agent())
    assert result.ok is True
    assert [p.status for p in result.phases] == ["ok", "ok"]
