"""Hermetic tests for the CAP fact auto-emit hook (design:
``docs/architecture/current/cap_fact_auto_emit_design.md``).

Two surfaces under test, both loaded via ``importlib.util.spec_from_file_location`` — the SAME
technique ``tests/test_kb_produce_facts_integration.py`` already uses, because neither
``scripts/kb_produce_facts.py`` nor ``scripts/run_workflow.py`` is a package:

* ``scripts/kb_produce_facts.py``'s NEW ``derive_run_facts``/``_policy_evidence_for`` — the
  scoped, per-run derivation the hook calls (§2 of the design). Exercised directly, hermetically,
  against a temp registry — no Redis, no filesystem scan beyond what the test itself writes.
* ``scripts/run_workflow.py``'s NEW ``_emit_workflow_facts``/``_fact_auto_emit_enabled`` — the
  finalize-section hook + the flag-precedence resolver (§1/§4). Exercised with ``kb_produce_facts``
  and ``knowledge_stream.connect`` swapped for hermetic/failing fakes — no Redis, no real KB
  writes, and (for the failure-mode tests) a deliberately raising fake to prove the hook degrades
  to a warning rather than propagating.

GUARD (no Redis/network, per the design's VERIFY clause): nothing here calls a real
``ks.connect()`` against a live Redis. The one test that exercises the emit path
(``test_emit_workflow_facts_...``) monkeypatches ``ks.connect``/``kb_produce_facts.emit_records``.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from agentic_dynamics.control import fact_ingestion as fi
from agentic_dynamics.experiment.experiment_spec import (
    ExperimentSpec,
    StopSpec,
    Workflow,
)
from agentic_dynamics.runtime.workflow_runner import PhaseResult, WorkflowRunResult

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO = "self-test-cell"  # a cell_scope-shaped repository_id, NOT the flat REPOSITORY_ID (design §3)
REVISION = "0123456789abcdef0123456789abcdef01234567"
NOW = "2026-08-24T00:00:00+00:00"


# ── Module loaders (mirrors test_kb_produce_facts_integration.py's `_load_kb_produce_facts`) ──


def _load_module(rel_path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / rel_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def kpf(tmp_path, monkeypatch):
    """A fresh ``kb_produce_facts`` module, hermetically re-rooted at ``tmp_path``."""
    module = _load_module("scripts/kb_produce_facts.py", "kb_produce_facts_under_test_fae")
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    return module


@pytest.fixture
def rw(kpf, monkeypatch):
    """A fresh ``run_workflow`` module, wired to the SAME hermetic ``kpf`` instance.

    ``run_workflow.py`` imports ``kb_produce_facts`` at module load time (§1's "default-ON, not
    lazy" choice); this fixture reaches into the loaded module object and rebinds its
    ``kb_produce_facts`` attribute to the hermetic ``kpf`` fixture above, so
    ``_emit_workflow_facts`` calls ``kpf.derive_run_facts``/``kpf.emit_records`` — never the real,
    repo-rooted module.
    """
    module = _load_module("scripts/run_workflow.py", "run_workflow_under_test_fae")
    monkeypatch.setattr(module, "kb_produce_facts", kpf)
    return module


def _spec(name: str = "demo_spec", *, budget_usd: float = 100.0, max_attempts: int = 3) -> ExperimentSpec:
    """A minimal, in-memory ``ExperimentSpec`` — never loaded from a YAML file, matching how
    ``scripts/run_workflow.py`` already holds one `load_spec`-parsed instance per invocation."""
    return ExperimentSpec(
        name=name,
        question="does the hook work",
        version="1.0",
        workflow=Workflow(kind="agent_task", params={"model_pool": ["deepseek/deepseek-v4-pro"]}),
        factors=[],
        design="factorial",
        stop=StopSpec(budget_usd=budget_usd, max_attempts=max_attempts),
    )


def _result(
    spec_name: str = "demo_spec",
    *,
    ok_phase: bool = True,
    git_sha: str = "abc123",
    cost_usd: float = 1.5,
) -> WorkflowRunResult:
    """A minimal, in-memory ``WorkflowRunResult`` — never round-tripped through JSON, matching
    exactly what ``scripts/run_workflow.py`` holds right after ``run_workflow()`` returns (BEFORE
    the ledger write), which is what ``_emit_workflow_facts`` is actually handed."""
    return WorkflowRunResult(
        spec_name=spec_name,
        model="deepseek/deepseek-v4-pro",
        workdir="/tmp/x",
        goal="build it",
        git_sha=git_sha,
        started_at=NOW,
        ended_at=NOW,
        phases=[
            PhaseResult(
                phase="implement",
                kind="agent",
                status="ok" if ok_phase else "failed",
                model="deepseek/deepseek-v4-pro",
                commit_hash="deadbeef",
                cost_usd=cost_usd,
            ),
        ],
    )


def _registration_line(record) -> dict:
    """The line ``kb_worker.py``'s ``kb-registry-v1`` handler would append for one record —
    mirrored field-for-field, exactly as ``test_kb_produce_facts_integration.py``'s helper of the
    same name does (simulates a completed, Redis-backed producer round without needing Redis)."""
    return {
        "knowledge_id": record.knowledge_id,
        "entity_id": record.entity_id,
        "source_type": record.source_type,
        "logical_locator": record.logical_locator,
        "source_uri": record.source_uri,
        "lifecycle_state": "current",
        "observed_at": record.observed_at,
        "indexed_at": record.indexed_at,
        "supersedes": record.supersedes,
        "causes": record.causes,
        "reason": fi.fact_reason(record),
    }


def _persist(registry_path: Path, *records) -> None:
    lines = "".join(json.dumps(_registration_line(r)) + "\n" for r in records)
    with registry_path.open("a") as f:
        f.write(lines)


def _by_predicate(records) -> dict[str, dict]:
    return {json.loads(r.text)["predicate"]: json.loads(r.text) for r in records}


# ── 1. derive_run_facts: produces facts, scoped correctly, no filesystem scan needed ──


def test_derive_run_facts_produces_attempt_job_policy_and_workflow_facts(kpf, tmp_path):
    spec = _spec(budget_usd=50.0, max_attempts=2)
    result = _result()

    records = kpf.derive_run_facts(
        result, spec, repository_id=REPO, revision=REVISION, now=NOW
    )
    by = _by_predicate(records)

    # All four run-scoped reducer families are represented — the design's explicit widening
    # beyond `_derive_workflow_facts` (which registers ONLY the workflow-level aggregate).
    assert "phase_status" in by  # attempt_facts/v1
    assert "job_status" in by  # job_facts/v1
    assert "max_spend_usd" in by  # policy_facts/v1 (fed from the in-memory spec, no YAML scan)
    assert "workflow_status" in by  # workflow_facts/v1 (the top of the ladder)

    assert by["phase_status"]["value"] == "ok"
    assert by["job_status"]["value"] == "ok"
    assert by["max_spend_usd"]["value"] == "50.0"
    assert by["workflow_status"]["value"] == "completed"

    # Scope correctness (design §3): every record's own scope_path carries the SAME repository_id
    # root this call was given — never the flat, corpus-wide REPOSITORY_ID constant.
    for payload in by.values():
        assert payload["scope_path"].startswith(f"org:{REPO}/")

    # spec_status/v1 (I1, corpus-wide) is deliberately never run by this scoped entry point.
    assert "spec_status" not in by


def test_derive_run_facts_needs_no_filesystem_beyond_the_hermetic_registry(kpf, tmp_path):
    """No run JSONs or spec YAMLs are written to `tmp_path` at all — proving `derive_run_facts`
    truly derives from the in-memory `result`/`spec` only, never `load_run_jsons()`'s corpus scan
    (unlike `_derive_workflow_facts`, which would return nothing here since REPO_ROOT is empty)."""
    assert not (tmp_path / "experiments").exists()
    records = kpf.derive_run_facts(
        _result(), _spec(), repository_id=REPO, revision=REVISION, now=NOW
    )
    assert records  # derived purely from the in-memory objects


# ── 2. Idempotence: re-emitting the same run artifact is a byte-identical no-op ──


def test_reemit_same_run_is_a_byte_identical_noop(kpf, tmp_path):
    spec = _spec()
    result = _result()

    round_1 = kpf.derive_run_facts(result, spec, repository_id=REPO, revision=REVISION, now=NOW)
    assert round_1
    assert all(r.supersedes is None for r in round_1)  # first version of every entity

    # A second, independent derive_run_facts call over the SAME (unpersisted) result must be
    # byte-for-byte stable — run_artifact_id + fact_fingerprint are both pure functions of content.
    round_1b = kpf.derive_run_facts(result, spec, repository_id=REPO, revision=REVISION, now=NOW)
    assert {r.knowledge_id for r in round_1b} == {r.knowledge_id for r in round_1}

    # Persist round 1 (simulating a completed emit), then re-derive against the now-populated
    # registry: the convergence guard must emit NOTHING — the double-emit-from-a-copied-artifact
    # attack named in the design's §9 adversarial checklist.
    _persist(kpf.REGISTRY_INDEX_PATH, *round_1)
    round_2 = kpf.derive_run_facts(result, spec, repository_id=REPO, revision=REVISION, now=NOW)
    assert round_2 == []


def test_a_genuinely_new_run_of_the_same_cell_supersedes_the_old_one(kpf, tmp_path):
    """Contrast case for the no-op test above: idempotence must not become "never updates"."""
    spec = _spec()
    round_1 = kpf.derive_run_facts(
        _result(cost_usd=1.5), spec, repository_id=REPO, revision=REVISION, now=NOW
    )
    _persist(kpf.REGISTRY_INDEX_PATH, *round_1)

    round_2 = kpf.derive_run_facts(
        _result(cost_usd=9.0, git_sha="fedcba"), spec, repository_id=REPO, revision=REVISION, now=NOW
    )
    job_cost_2 = [r for r in round_2 if json.loads(r.text)["predicate"] == "job_accumulated_cost_usd"]
    job_cost_1 = [r for r in round_1 if json.loads(r.text)["predicate"] == "job_accumulated_cost_usd"][0]
    assert len(job_cost_2) == 1
    assert job_cost_2[0].supersedes == job_cost_1.knowledge_id
    assert job_cost_2[0].entity_id == job_cost_1.entity_id  # same logical slot, new version


# ── 3. A failed run still emits its attempt facts ──


def test_failed_run_still_emits_attempt_facts(kpf, tmp_path):
    spec = _spec()
    result = _result(ok_phase=False)
    assert result.ok is False  # sanity: the fixture really is a failed run

    records = kpf.derive_run_facts(result, spec, repository_id=REPO, revision=REVISION, now=NOW)
    by = _by_predicate(records)

    assert by["phase_status"]["value"] == "failed"  # the attempt fact itself
    assert by["job_status"]["value"] == "failed"
    assert by["workflow_status"]["value"] == "failed"  # the aggregate agrees (job_status dominates)


# ── 4. `_control_terminal_write`: the ONE emission path degrades, never propagates ──
#
# control_db_publication p2 moved emission behind the transactional outbox: `_emit_workflow_facts`
# and `_emit_spec_record` are gone, and `_control_terminal_write` records the run's terminal
# transition + its result envelope + the events it owes in ONE control-db transaction, then drains
# the outbox. The guarantees these tests encode are UNCHANGED — a finished run's exit status may
# never depend on the knowledge plane's health — but two of them are now strictly stronger: a
# downed stream leaves the events PENDING (owed, retryable) instead of losing them, and a
# derivation failure no longer costs the run its state record.


class _Args:
    """The argparse namespace `_control_terminal_write` actually reads."""

    workdir = "/tmp/x"
    model = "deepseek/deepseek-v4-pro"
    only_phase = None
    no_fact_emit = False


@pytest.fixture
def control_db(rw, tmp_path, monkeypatch):
    """Redirect EVERY durable path the emission path writes to, then hand back the db location.

    Three redirections, and all three are load-bearing for hermeticity — the publisher writes
    real files, so a test that patches only some of them silently commits fixture data into the
    repo (which is exactly what an earlier draft of this suite did: 34 registry lines and 17 KB
    artifacts for a spec named ``demo_spec``).

    ``core.paths`` is patched rather than ``outbox``'s own names because the publisher resolves
    both paths at CALL time, precisely so they can be redirected.
    """
    monkeypatch.setenv("FINOPS_CONTROL_DB", str(tmp_path / "control" / "control.db"))
    monkeypatch.setattr("agentic_dynamics.core.paths.KB_ARTIFACT_DIR", tmp_path / "kb")
    monkeypatch.setattr(
        "agentic_dynamics.core.paths.REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl"
    )
    # `_spec_payload` reads the REAL experiments/specs index; stub it so these tests stay
    # hermetic and exercise the fact path only.
    monkeypatch.setattr(rw.si, "load_index_entries", lambda **kw: [])
    return tmp_path / "control" / "control.db"


def _open_run(rw, control_db):
    """Create the `running` run row the terminal write transitions out of."""
    return rw._control_open_run(_spec(), _Args())


def test_terminal_write_degrades_to_warning_when_redis_unreachable(
    rw, kpf, control_db, monkeypatch, capsys
):
    """A downed stream must never propagate — and must LEAVE THE EVENTS OWED.

    The pre-outbox path printed a warning and dropped the events on the floor. Now the drain
    reports the stream unreachable and the rows stay `pending`, so the next drain delivers them.
    That is the whole point of the phase: the obligation survives the outage.
    """
    from agentic_dynamics.knowledge import knowledge_stream as real_ks

    def _raise_connect(*a, **kw):
        raise ConnectionError("Redis refused connection")

    monkeypatch.setattr(real_ks, "connect", _raise_connect)
    run_id = _open_run(rw, control_db)
    assert run_id is not None

    rw._control_terminal_write(  # never raises
        _spec(), _Args(), _result(), run_id=run_id, ledger_path=Path("/tmp/ledger.json")
    )

    captured = capsys.readouterr()
    assert "outbox: stream unreachable" in captured.err

    from agentic_dynamics.control.control_db import ControlDB, RunState
    from agentic_dynamics.control.outbox import summarize

    db = ControlDB.open_read_only(control_db)
    try:
        # The run terminated honestly...
        assert db.get_run(run_id).state is RunState.PROMOTABLE
        # ...and its events are OWED, not lost.
        assert summarize(db, run_id=run_id).pending > 0
    finally:
        db.close()


def test_terminal_write_degrades_when_derivation_itself_raises(
    rw, kpf, control_db, monkeypatch, capsys
):
    """A corrupt registry row or a reducer bug costs that producer's events — and nothing else.

    Strengthened from the pre-outbox version: the run's terminal STATE must still be recorded.
    Coupling the state record to a fact reducer would turn a knowledge-plane bug into a phantom
    in-flight run that the control packet and the lease watchdog both have to reason about.
    """

    def _raise_derive(*a, **kw):
        raise RuntimeError("simulated corrupt registry row")

    monkeypatch.setattr(kpf, "derive_run_facts", _raise_derive)

    run_id = _open_run(rw, control_db)
    rw._control_terminal_write(
        _spec(), _Args(), _result(), run_id=run_id, ledger_path=Path("/tmp/ledger.json")
    )

    assert "warning: workflow facts derivation failed" in capsys.readouterr().err

    from agentic_dynamics.control.control_db import ControlDB, RunState
    from agentic_dynamics.control.outbox import summarize

    db = ControlDB.open_read_only(control_db)
    try:
        assert db.get_run(run_id).state is RunState.PROMOTABLE  # the state survived
        assert summarize(db, run_id=run_id).pending == 0  # the failed producer queued nothing
    finally:
        db.close()


def test_terminal_write_happy_path_delivers_and_checkpoints(
    rw, kpf, control_db, tmp_path, monkeypatch, capsys
):
    """The success path end to end: transition, queue, deliver, artifact, checkpoint.

    Still hermetic — a fake Redis handle stands in for `ks.connect()` and `publish_event` is
    stubbed, so nothing here touches a live stream or the real KB_ARTIFACT_DIR.
    """
    from agentic_dynamics.knowledge import knowledge_stream as real_ks

    class _FakeRedis:
        def __init__(self):
            self._checkpoint: dict[str, str] = {}

        def hget(self, key, field):
            return self._checkpoint.get(field)

        def hset(self, key, field, value):
            self._checkpoint[field] = value

    fake_redis = _FakeRedis()
    published: list = []
    monkeypatch.setattr(real_ks, "connect", lambda *a, **kw: fake_redis)
    monkeypatch.setattr(real_ks, "publish_event", lambda r, e, **kw: published.append(e))

    run_id = _open_run(rw, control_db)
    rw._control_terminal_write(
        _spec(), _Args(), _result(), run_id=run_id,
        ledger_path=Path("/tmp/ledger.json"),
    )

    captured = capsys.readouterr()
    assert "outbox:" in captured.err
    assert "stream unreachable" not in captured.err
    assert published, "the events reached the (stubbed) stream"
    # The durable artifacts landed BEFORE the pointer events, as every producer requires.
    assert list((tmp_path / "kb").glob("*.json"))
    # ...and each delivered knowledge_id is checkpointed, so a re-drain will not duplicate it.
    assert fake_redis._checkpoint

    from agentic_dynamics.control.control_db import ControlDB, resolve_db_path
    from agentic_dynamics.control.outbox import summarize

    db = ControlDB.open_read_only(control_db)
    try:
        summary = summarize(db, run_id=run_id)
        assert summary.delivered > 0 and summary.pending == 0 and summary.dead == 0
    finally:
        db.close()

    # Hermeticity, asserted rather than assumed: every durable write landed under tmp_path.
    # The publisher appends real registry lines and writes real artifacts, so a redirection that
    # silently stopped working would otherwise surface only as a dirty working tree.
    assert (tmp_path / "registry_index.jsonl").exists()
    assert tmp_path in resolve_db_path(None).parents


def test_a_child_run_emits_nothing_and_records_no_run(rw, control_db, capsys):
    """P0-2, held at the composition root: **children never emit; the parent aggregates.**

    A `--only-phase` sibling is one phase of the parent's run, not a run of its own. Minting a
    second run row (and a second set of outbox events) for it would double-count the work and
    emit each phase's facts twice — once from the child, once from the parent's aggregate.
    """

    class _ChildArgs(_Args):
        only_phase = "p2_outbox"

    assert rw._control_open_run(_spec(), _ChildArgs()) is None
    rw._control_terminal_write(
        _spec(), _ChildArgs(), _result(), run_id=None, ledger_path=Path("/tmp/ledger.json")
    )

    assert "child mode" in capsys.readouterr().err
    # The child never even created the database — nothing to aggregate, nothing to emit.
    assert not control_db.exists()


# ── 5. Flag precedence: --no-fact-emit > FINOPS_FACT_AUTO_EMIT=0 > default-ON ──


def test_fact_auto_emit_default_on(rw, monkeypatch):
    monkeypatch.delenv(rw.FACT_AUTO_EMIT_ENV, raising=False)

    class _Args:
        no_fact_emit = False

    assert rw._fact_auto_emit_enabled(_Args()) is True


def test_fact_auto_emit_env_zero_disables(rw, monkeypatch):
    monkeypatch.setenv(rw.FACT_AUTO_EMIT_ENV, "0")

    class _Args:
        no_fact_emit = False

    assert rw._fact_auto_emit_enabled(_Args()) is False


def test_fact_auto_emit_env_other_values_stay_on(rw, monkeypatch):
    """Only the literal string "0" disables — this is NOT the opt-in "1"-truthy convention the
    rest of the FINOPS_* family uses (design §4's deliberate posture break)."""
    for value in ("1", "true", "anything"):
        monkeypatch.setenv(rw.FACT_AUTO_EMIT_ENV, value)

        class _Args:
            no_fact_emit = False

        assert rw._fact_auto_emit_enabled(_Args()) is True


def test_no_fact_emit_cli_flag_wins_even_when_env_would_enable(rw, monkeypatch):
    """CLI > env, per the precedence table — even with the env var unset (ON) or set to "1" (ON),
    an explicit --no-fact-emit always disables."""
    monkeypatch.delenv(rw.FACT_AUTO_EMIT_ENV, raising=False)

    class _ArgsUnset:
        no_fact_emit = True

    assert rw._fact_auto_emit_enabled(_ArgsUnset()) is False

    monkeypatch.setenv(rw.FACT_AUTO_EMIT_ENV, "1")

    class _ArgsEnvOn:
        no_fact_emit = True

    assert rw._fact_auto_emit_enabled(_ArgsEnvOn()) is False
