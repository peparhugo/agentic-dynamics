"""Step 3b: the child side of the prepared-step transport.

The child consumes the parent's exact step — never a re-derivation from the spec — and refuses
(never repairs) a missing, malformed, or tampered transport: a prompt that does not hash to the
carried ``prompt_sha256`` means the instruction changed in transit, and executing it would let
the recorded parent decision and the actual run disagree.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from agentic_dynamics.runtime.executor import StepRequest, load_prepared_step
from agentic_dynamics.runtime.workflow_runner import run_concrete_step


def _request(**kwargs) -> StepRequest:
    base = dict(
        phase_name="p1",
        phase_kind="agent",
        prompt="parent prompt",
        model="m",
        goal="g",
        spec_name="t",
        workdir="/tmp/wt",
        attempt=2,
    )
    base.update(kwargs)
    return StepRequest(**base)


def test_prepared_dict_carries_the_prompt_hash_and_attempt():
    prepared = _request().to_prepared_dict()
    assert prepared["schema"] == "prepared-step/v1"
    assert prepared["prompt_sha256"] == _request().prompt_sha256
    assert prepared["attempt"] == 2
    assert prepared["phase_name"] == "p1"


def test_child_loads_and_verifies(tmp_path):
    path = tmp_path / "p1.a2.json"
    path.write_text(json.dumps(_request().to_prepared_dict()), encoding="utf-8")

    loaded = load_prepared_step(path)

    assert loaded["prompt"] == "parent prompt"
    assert loaded["phase_name"] == "p1"
    assert loaded["attempt"] == 2


def test_child_refuses_a_changed_prompt(tmp_path):
    payload = _request().to_prepared_dict()
    payload["prompt"] = "tampered"
    path = tmp_path / "p.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="hash mismatch"):
        load_prepared_step(path)


def test_child_refuses_a_missing_file(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        load_prepared_step(tmp_path / "absent.json")


def test_child_refuses_a_foreign_document(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"schema": "something-else"}), encoding="utf-8")
    with pytest.raises(ValueError, match="not a prepared-step/v1"):
        load_prepared_step(path)


# ── step 3c: the concrete request the worker executes (Astra ae212a0 finding 5) ───────────────


def test_from_prepared_dict_round_trips_the_concrete_request():
    """The worker rebuilds the request from the payload — and carries NO spec context."""
    request = _request(attempt=3, timeout=77, thinking_effort="low", backend="opencode")
    rebuilt = StepRequest.from_prepared_dict(request.to_prepared_dict())
    assert rebuilt.model == "m"
    assert rebuilt.prompt == "parent prompt"
    assert rebuilt.attempt == 3
    assert rebuilt.timeout == 77
    assert rebuilt.thinking_effort == "low"
    assert rebuilt.backend == "opencode"
    # The one field that lets an engine override the concrete model/timeout is empty: there is
    # no source-spec context to reach into.
    assert rebuilt.phase_def == {}


def test_from_prepared_dict_refuses_a_changed_prompt():
    payload = _request().to_prepared_dict()
    payload["prompt"] = "tampered"
    with pytest.raises(ValueError, match="hash mismatch"):
        StepRequest.from_prepared_dict(payload)


# ── run-inspection slice: the prepared-step reference is durable on the phase ledger ──────────


def test_phase_result_serializes_the_prepared_step_reference():
    """The clone-relative path + prompt hash survive onto the phase ledger (additive keys)."""
    from agentic_dynamics.runtime.workflow_runner import PhaseResult

    phase = PhaseResult(
        phase="p1",
        kind="agent",
        status="ok",
        prepared_step_path=".fleet/prepared_steps/p1.a2.json",
        prepared_step_prompt_sha256="c" * 64,
    )

    serialized = phase.to_dict()
    assert serialized["prepared_step_path"] == ".fleet/prepared_steps/p1.a2.json"
    assert serialized["prepared_step_prompt_sha256"] == "c" * 64


# ── isolated conversation forks: the checkpoint transport ─────────────────────────────────

def test_prepared_step_carries_the_fork_identity(tmp_path):
    """A prepared step declares its fork: parent session id + checkpoint hash + child path."""
    req = StepRequest(
        phase_name="p1", phase_kind="agent", prompt="do the thing", model="m", goal="g",
        spec_name="t", workdir="/repo",
        fork_session_id="ses_parent123", fork_checkpoint_sha256="a" * 64,
        fork_db_path="/repo/.fleet/fork_checkpoints/p1.a1.db",
    )
    payload = req.to_prepared_dict(workdir="/repo")
    assert payload["fork"] == {
        "session_id": "ses_parent123",
        "checkpoint_sha256": "a" * 64,
        "db_path": "/repo/.fleet/fork_checkpoints/p1.a1.db",
    }
    rebuilt = StepRequest.from_prepared_dict(payload)
    assert rebuilt.fork_session_id == "ses_parent123"
    assert rebuilt.fork_checkpoint_sha256 == "a" * 64
    assert rebuilt.fork_db_path == "/repo/.fleet/fork_checkpoints/p1.a1.db"


def test_fork_stages_its_own_copy_and_forks(tmp_path, monkeypatch):
    """The child verifies the checkpoint, stages it into ITS state dir, and forks."""
    import hashlib

    src = tmp_path / "transport" / "p1.a1.db"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"checkpoint-bytes")
    state = tmp_path / "state" / "data" / "opencode"
    state.mkdir(parents=True)
    monkeypatch.setenv("FINOPS_OPENCODE_STATE_DIR", str(tmp_path / "state" / "data"))
    captured = {}

    def fake_agent(prompt, **kwargs):
        captured.update(kwargs)
        class R:
            ok = True
            tokens = {"in": 1, "out": 1, "total": 2}
            error = ""
            session_id = "ses_child"
        return R()

    request = StepRequest(
        phase_name="p1", phase_kind="agent", prompt="q", model="m", goal="g",
        spec_name="t", workdir=str(tmp_path),
        fork_session_id="ses_parent123",
        fork_checkpoint_sha256=hashlib.sha256(b"checkpoint-bytes").hexdigest(),
        fork_db_path=str(src),
    )
    result = run_concrete_step(request, run_agent=fake_agent)
    assert result.state == "succeeded"
    assert captured.get("session_id") == "ses_parent123"
    assert captured.get("fork") is True
    assert (state / "opencode.db").read_bytes() == b"checkpoint-bytes"


def test_fork_refuses_a_missing_or_tampered_checkpoint(tmp_path, monkeypatch):
    """A declared fork with missing/changed bytes REFUSES — never a silent fresh session."""
    state = tmp_path / "state" / "data" / "opencode"
    state.mkdir(parents=True)
    monkeypatch.setenv("FINOPS_OPENCODE_STATE_DIR", str(tmp_path / "state" / "data"))

    def fake_agent(prompt, **kwargs):  # pragma: no cover — must never run
        raise AssertionError("the agent must not run for a refused fork")

    missing = StepRequest(
        phase_name="p1", phase_kind="agent", prompt="q", model="m", goal="g",
        spec_name="t", workdir=str(tmp_path), fork_session_id="ses_parent",
        fork_checkpoint_sha256="b" * 64, fork_db_path=str(tmp_path / "nope.db"),
    )
    with pytest.raises(ValueError, match="checkpoint missing"):
        run_concrete_step(missing, run_agent=fake_agent)

    tampered = tmp_path / "tampered.db"
    tampered.write_bytes(b"changed")
    bad = StepRequest(
        phase_name="p1", phase_kind="agent", prompt="q", model="m", goal="g",
        spec_name="t", workdir=str(tmp_path), fork_session_id="ses_parent",
        fork_checkpoint_sha256=hashlib.sha256(b"original").hexdigest(),
        fork_db_path=str(tampered),
    )
    with pytest.raises(ValueError, match="hash mismatch"):
        run_concrete_step(bad, run_agent=fake_agent)


def test_incomplete_fork_declaration_refuses_before_any_provider_call(tmp_path, monkeypatch):
    """A partial fork block (db path but no session/hash) raises BEFORE the agent runs."""
    monkeypatch.setenv("FINOPS_OPENCODE_STATE_DIR", str(tmp_path / "state" / "data"))
    called = {"n": 0}

    def fake_agent(prompt, **kwargs):  # pragma: no cover — must never run
        called["n"] += 1
        raise AssertionError("a provider call happened for an incomplete fork")

    db = tmp_path / "x.db"
    db.write_bytes(b"bytes")
    request = StepRequest(
        phase_name="p1", phase_kind="agent", prompt="q", model="m", goal="g",
        spec_name="t", workdir=str(tmp_path),
        fork_session_id="", fork_checkpoint_sha256="", fork_db_path=str(db),
    )
    with pytest.raises(ValueError, match="incomplete fork declaration"):
        run_concrete_step(request, run_agent=fake_agent)
    assert called["n"] == 0


def test_prepared_fork_block_must_be_complete_on_load():
    """load-side validation: a partial fork block never deserializes."""
    import pytest

    payload = {
        "schema": "prepared-step/v1",
        "phase_name": "p1", "phase_kind": "agent", "prompt": "q",
    }
    import hashlib

    payload["prompt_sha256"] = hashlib.sha256(b"q").hexdigest()
    payload["fork"] = {"session_id": "ses_x"}  # incomplete: no hash, no path
    with pytest.raises(ValueError, match="incomplete"):
        StepRequest.from_prepared_dict(payload)


def test_fork_experiment_specs_validate_with_the_real_validator():
    """The checked-in fork specs pass load_spec + validate_spec (Astra review item 1)."""
    import pathlib

    from agentic_dynamics.experiment.compile_experiment import validate_spec
    from agentic_dynamics.experiment.experiment_spec import load_spec

    root = pathlib.Path(__file__).resolve().parent.parent
    for rel in ("workflows/repository/fork_seed.yaml", "workflows/repository/fork_branch.yaml"):
        spec = load_spec(root / rel)
        errors = validate_spec(spec)
        assert not errors, f"{rel}: {errors}"
        assert spec.intent == "measure"


def test_fork_staging_adapts_the_copys_session_directory(tmp_path, monkeypatch):
    """The staged copy presents the CELL's workdir; the source checkpoint stays untouched."""
    import hashlib
    import sqlite3

    # a frozen snapshot whose session lives at a foreign (host) directory
    src = tmp_path / "transport" / "p1.a1.db"
    src.parent.mkdir(parents=True)
    con = sqlite3.connect(src)
    con.execute("create table session (id text primary key, directory text)")
    con.execute("insert into session values ('ses_parent', '/home/someone/foreign')")
    con.commit()
    con.close()
    before = hashlib.sha256(src.read_bytes()).hexdigest()

    state = tmp_path / "state" / "data" / "opencode"
    state.mkdir(parents=True)
    monkeypatch.setenv("FINOPS_OPENCODE_STATE_DIR", str(tmp_path / "state" / "data"))
    captured = {}

    def fake_agent(prompt, **kwargs):
        captured.update(kwargs)
        class R:
            ok = True
            tokens = {"in": 1, "out": 1, "total": 2}
            error = ""
            session_id = "ses_child"
        return R()

    request = StepRequest(
        phase_name="p1", phase_kind="agent", prompt="q", model="m", goal="g",
        spec_name="t", workdir="/state/workdir",
        fork_session_id="ses_parent",
        fork_checkpoint_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
        fork_db_path=str(src),
    )
    run_concrete_step(request, run_agent=fake_agent)
    con = sqlite3.connect(f"file:{state / 'opencode.db'}?mode=ro", uri=True)
    assert con.execute("select directory from session where id='ses_parent'").fetchone()[0] == "/state/workdir"
    con.close()
    assert hashlib.sha256(src.read_bytes()).hexdigest() == before  # checkpoint untouched
