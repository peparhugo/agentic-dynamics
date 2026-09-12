"""Hermetic tests for scripts/run_workflow.py's versioned-graph CLI wiring (cap_2a p1).

Two surfaces under test, loaded via ``importlib.util.spec_from_file_location`` (the same
technique ``tests/test_fact_auto_emit.py`` uses — ``scripts/run_workflow.py`` is not a
package):

* ``resolve_graph_uri`` / ``_build_graph_client`` / ``_build_change_analyzer`` — the
  composition-root resolution: CLI > ``FINOPS_NEO4J_URI`` > ``FINOPS_NEO4J_URL``, credentials
  ONLY from ``FINOPS_NEO4J_USER`` / ``FINOPS_NEO4J_PASSWORD``, and the preserved no-op default
  when ``--change-analysis`` is absent (the graph env vars / flag alone change nothing).
* the client lifecycle in ``main()``: the ``Neo4jClient`` is constructed only when graph
  analysis is explicitly requested, and is closed in a ``finally`` even when ``run_workflow``
  raises.

GUARD (no Neo4j, no Redis, no agent runs): ``Neo4jClient`` is monkeypatched with a fake
everywhere; ``run_workflow`` / ``load_spec`` are stubbed; nothing touches the network.
"""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_module(name="run_workflow_under_test_graph_cli"):
    spec = importlib.util.spec_from_file_location(
        name, PROJECT_ROOT / "scripts" / "run_workflow.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeNeo4jClient:
    """Records constructor kwargs + close() calls; construction failure is scriptable."""

    fail_construction = False
    instances: list["_FakeNeo4jClient"] = []

    def __init__(self, **kwargs):
        if self.__class__.fail_construction:
            raise RuntimeError("neo4j unavailable")
        self.kwargs = kwargs
        self.closed = False
        self.__class__.instances.append(self)

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _fresh_fake(monkeypatch):
    _FakeNeo4jClient.fail_construction = False
    _FakeNeo4jClient.instances = []
    # ``_build_graph_client`` imports Neo4jClient lazily from the module at call time, so
    # patching the class on the knowledge.graph module intercepts every construction.
    monkeypatch.setattr("agentic_dynamics.knowledge.graph.Neo4jClient", _FakeNeo4jClient)
    yield
    _FakeNeo4jClient.instances = []


# ── URI resolution: CLI > FINOPS_NEO4J_URI > FINOPS_NEO4J_URL > None ──


def test_resolve_graph_uri_cli_wins(monkeypatch):
    module = _load_module()
    monkeypatch.setenv("FINOPS_NEO4J_URI", "bolt://env-uri:7687")
    monkeypatch.setenv("FINOPS_NEO4J_URL", "bolt://env-url:7687")
    assert module.resolve_graph_uri("bolt://cli:7687") == "bolt://cli:7687"


def test_resolve_graph_uri_env_precedence(monkeypatch):
    module = _load_module()
    monkeypatch.setenv("FINOPS_NEO4J_URI", "bolt://env-uri:7687")
    monkeypatch.setenv("FINOPS_NEO4J_URL", "bolt://env-url:7687")
    assert module.resolve_graph_uri(None) == "bolt://env-uri:7687"
    monkeypatch.delenv("FINOPS_NEO4J_URI")
    assert module.resolve_graph_uri(None) == "bolt://env-url:7687"


def test_resolve_graph_uri_none_when_unset(monkeypatch):
    module = _load_module()
    monkeypatch.delenv("FINOPS_NEO4J_URI", raising=False)
    monkeypatch.delenv("FINOPS_NEO4J_URL", raising=False)
    assert module.resolve_graph_uri(None) is None


# ── Client construction: credentials from env only, failures degrade to None ──


def test_build_graph_client_threads_env_credentials(monkeypatch):
    module = _load_module()
    monkeypatch.setenv("FINOPS_NEO4J_USER", "alice")
    monkeypatch.setenv("FINOPS_NEO4J_PASSWORD", "s3cret")
    client = module._build_graph_client("bolt://x:7687")
    assert client is not None
    assert client.kwargs == {"uri": "bolt://x:7687", "user": "alice", "password": "s3cret"}


def test_build_graph_client_uses_constructor_defaults_without_env(monkeypatch):
    module = _load_module()
    monkeypatch.delenv("FINOPS_NEO4J_USER", raising=False)
    monkeypatch.delenv("FINOPS_NEO4J_PASSWORD", raising=False)
    client = module._build_graph_client("bolt://x:7687")
    assert client is not None
    assert client.kwargs == {"uri": "bolt://x:7687"}  # nothing secret hard-coded here


def test_build_graph_client_construction_failure_is_graph_unavailable():
    module = _load_module()
    _FakeNeo4jClient.fail_construction = True
    assert module._build_graph_client("bolt://x:7687") is None  # degraded, never a crash


def test_construction_failure_is_recorded_as_unavailable(monkeypatch):
    module = _load_module()
    _FakeNeo4jClient.fail_construction = True
    analyzer, client = module._build_change_analyzer(
        _args(change_analysis=True, change_analysis_graph="bolt://x:7687")
    )
    assert analyzer is not None and client is None
    assert analyzer.graph_requested is True


# ── Composition-root wiring: no-op default preserved; client only when requested ──


def _args(**overrides):
    base = dict(change_analysis=False, change_analysis_graph=None)
    base.update(overrides)
    return SimpleNamespace(**base)


def test_change_analyzer_absent_without_flag():
    module = _load_module()
    analyzer, client = module._build_change_analyzer(_args())
    assert analyzer is None and client is None
    assert _FakeNeo4jClient.instances == []


def test_change_analyzer_absent_when_only_graph_requested(monkeypatch):
    """--change-analysis absent → the seam stays inert even when a graph URI is given AND the
    env vars are set: the no-op default is preserved (byte-identical to pre-seam runs)."""
    module = _load_module()
    monkeypatch.setenv("FINOPS_NEO4J_URI", "bolt://env:7687")
    analyzer, client = module._build_change_analyzer(
        _args(change_analysis_graph="bolt://x:7687")
    )
    assert analyzer is None and client is None
    assert _FakeNeo4jClient.instances == []


def test_change_analysis_without_graph_keeps_delta_only_path():
    module = _load_module()
    analyzer, client = module._build_change_analyzer(_args(change_analysis=True))
    assert analyzer is not None  # the seam IS injected
    assert client is None  # …but with graph_client=None: delta-only facts, no graph leg
    assert _FakeNeo4jClient.instances == []


def test_change_analysis_with_graph_flag_builds_client():
    module = _load_module()
    analyzer, client = module._build_change_analyzer(
        _args(change_analysis=True, change_analysis_graph="bolt://x:7687")
    )
    assert analyzer is not None
    assert client is not None and client.closed is False


def test_change_analysis_with_env_uri_builds_client(monkeypatch):
    module = _load_module()
    monkeypatch.setenv("FINOPS_NEO4J_URI", "bolt://env:7687")
    analyzer, client = module._build_change_analyzer(_args(change_analysis=True))
    assert analyzer is not None
    assert client is not None and client.kwargs["uri"] == "bolt://env:7687"


# ── main() lifecycle: the client is closed in a finally, even when the run raises ──


def _stub_spec():
    return SimpleNamespace(
        name="demo",
        spec_id="demo@1.0",
        # w2: the composition root records the canonical spec revision on the control-db run
        workflow_revision_id="sha256:" + "ab" * 32,
        workflow=SimpleNamespace(params={}),
    )


def _stub_result():
    return SimpleNamespace(
        to_dict=lambda: {"ok": True},
        total_cost_usd=0.0,
        ok=True,
        git_sha="abc123",
        phases=[],
    )


def _run_main(module, tmp_path, monkeypatch, *, fake_run):
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "load_spec_any", lambda p: _stub_spec())
    monkeypatch.setattr(module, "run_workflow", fake_run)
    # Keep the post-run best-effort hooks quiet in the hermetic environment.
    monkeypatch.setenv("FINOPS_FACT_AUTO_EMIT", "0")
    monkeypatch.setattr(sys, "argv", [
        "run_workflow.py", "--spec", "x.yaml", "--goal", "g", "--model", "m",
        "--workdir", str(tmp_path), "--change-analysis", "--change-analysis-graph",
        "bolt://x:7687",
    ])
    return module.main()


def test_main_closes_graph_client_on_success(tmp_path, monkeypatch):
    module = _load_module()
    seen = {}

    def fake_run(spec, **kwargs):
        seen["analyzer"] = kwargs["change_analyzer"]
        return _stub_result()

    _run_main(module, tmp_path, monkeypatch, fake_run=fake_run)

    assert seen["analyzer"] is not None  # the evidence seam was injected
    assert len(_FakeNeo4jClient.instances) == 1
    assert _FakeNeo4jClient.instances[0].closed is True  # closed in the finally


def test_main_closes_graph_client_when_run_raises(tmp_path, monkeypatch):
    module = _load_module()

    def fake_run(spec, **kwargs):
        raise RuntimeError("agent boom")

    with pytest.raises(RuntimeError):
        _run_main(module, tmp_path, monkeypatch, fake_run=fake_run)

    # The driver handle is still closed even though the run never completed.
    assert len(_FakeNeo4jClient.instances) == 1
    assert _FakeNeo4jClient.instances[0].closed is True


def test_main_no_analyzer_no_client_without_flag(tmp_path, monkeypatch):
    """No --change-analysis → no analyzer, no client, and the graph env vars change nothing."""
    module = _load_module()
    monkeypatch.setenv("FINOPS_NEO4J_URI", "bolt://env:7687")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "load_spec_any", lambda p: _stub_spec())
    seen = {}

    def fake_run(spec, **kwargs):
        seen["analyzer"] = kwargs["change_analyzer"]
        return _stub_result()

    monkeypatch.setattr(module, "run_workflow", fake_run)
    monkeypatch.setenv("FINOPS_FACT_AUTO_EMIT", "0")
    monkeypatch.setattr(sys, "argv", [
        "run_workflow.py", "--spec", "x.yaml", "--goal", "g", "--model", "m",
        "--workdir", str(tmp_path),
    ])
    module.main()

    assert seen["analyzer"] is None
    assert _FakeNeo4jClient.instances == []  # never constructed


# ── Per-phase evidence recorder wiring (control_db_evidence e1) ──────────────────────────────


def test_main_injects_a_phase_evidence_recorder_when_a_run_is_recorded(tmp_path, monkeypatch):
    """The composition root binds the per-phase writer to the recorded run and hands it to the
    engine — the e1 write side is actually wired, not merely implemented."""
    module = _load_module()
    seen = {}

    def fake_run(spec, **kwargs):
        seen["recorder"] = kwargs.get("phase_evidence_recorder")
        return _stub_result()

    _run_main(module, tmp_path, monkeypatch, fake_run=fake_run)

    assert seen["recorder"] is not None
    assert callable(seen["recorder"])


def test_child_mode_records_no_run_and_injects_no_recorder(tmp_path, monkeypatch, capsys):
    """(e) child mode (--only-phase) records NOTHING: no run row is minted, so no recorder is
    injected and the engine's per-phase write seam stays inert — the parent aggregates."""
    module = _load_module()
    seen = {}

    def fake_run(spec, **kwargs):
        seen["recorder"] = kwargs.get("phase_evidence_recorder")
        return _stub_result()

    def spec_stub(p):
        return SimpleNamespace(
            name="demo", spec_id="demo@1.0",
            workflow=SimpleNamespace(params={"phases": [{"name": "scope"}]}),
        )

    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "load_spec_any", spec_stub)
    monkeypatch.setattr(module, "run_workflow", fake_run)
    monkeypatch.setenv("FINOPS_FACT_AUTO_EMIT", "0")
    monkeypatch.setattr(sys, "argv", [
        "run_workflow.py", "--spec", "x.yaml", "--goal", "g", "--model", "m",
        "--workdir", str(tmp_path), "--only-phase", "scope",
    ])
    with pytest.raises(SystemExit):
        module.main()

    assert seen["recorder"] is None
    assert "child mode" in capsys.readouterr().err


def test_control_open_run_child_mode_never_opens_the_control_db(monkeypatch):
    """The run-row gate is enforced BEFORE any db open: a --only-phase sibling does not even
    construct the database, so it structurally cannot record per-phase evidence."""
    module = _load_module()
    spec = SimpleNamespace(name="demo")
    args = SimpleNamespace(only_phase="scope", model="m")

    def boom():
        raise AssertionError("child mode must never open the control db")

    monkeypatch.setattr(module, "_control_db", boom)
    run_id, db = module._control_open_run(spec, args)
    assert (run_id, db) == (None, None)


def test_main_starts_and_stops_a_run_heartbeat_for_a_recorded_run(tmp_path, monkeypatch):
    """The composition root wires the run heartbeat (control_db_evidence e2): when a run row is
    recorded, a RunHeartbeatThread is started around the engine and stopped in the finally —
    child mode (no run row) starts nothing."""
    module = _load_module()
    events = {"started": 0, "stopped": 0}

    class FakeHeartbeat:
        def __init__(self, *args, **kwargs):
            self.stopped = False

        def start(self):
            events["started"] += 1

        def stop(self):
            events["stopped"] += 1

    monkeypatch.setattr(module, "RunHeartbeatThread", FakeHeartbeat)
    _run_main(module, tmp_path, monkeypatch, fake_run=lambda spec, **kw: _stub_result())

    assert events == {"started": 1, "stopped": 1}  # started before the engine, stopped after


def test_child_mode_starts_no_run_heartbeat(tmp_path, monkeypatch):
    """--only-phase (no run row to beat for) must not start a heartbeat thread — the parent is
    the only process that owns a run row and therefore the only one that beats."""
    module = _load_module()
    events = {"started": 0, "stopped": 0}

    class FakeHeartbeat:
        def start(self):
            events["started"] += 1

        def stop(self):
            events["stopped"] += 1

    monkeypatch.setattr(module, "RunHeartbeatThread", FakeHeartbeat)
    monkeypatch.setattr(module, "ROOT", tmp_path)

    def spec_stub(p):
        return SimpleNamespace(
            name="demo", spec_id="demo@1.0",
            workflow=SimpleNamespace(params={"phases": [{"name": "scope"}]}),
        )

    monkeypatch.setattr(module, "load_spec_any", spec_stub)
    monkeypatch.setattr(module, "run_workflow", lambda spec, **kw: _stub_result())
    monkeypatch.setenv("FINOPS_FACT_AUTO_EMIT", "0")
    monkeypatch.setattr(sys, "argv", [
        "run_workflow.py", "--spec", "x.yaml", "--goal", "g", "--model", "m",
        "--workdir", str(tmp_path), "--only-phase", "scope",
    ])
    with pytest.raises(SystemExit):
        module.main()

    assert events == {"started": 0, "stopped": 0}


# ── Wave B1: explicit resume identity + collision-proof ledger storage ───────


class _PriorRun:
    def __init__(self, run_id, state, *, spec_name="demo"):
        self.run_id = run_id
        self.state = state
        self.spec_name = spec_name
        self.family_id = run_id


class _ResumeDB:
    """The three reads/writes ``_control_open_run`` makes: runs / get_run / create_run."""

    def __init__(self, runs, known):
        self._runs = list(runs)
        self._known = dict(known)
        self.created: list[dict] = []

    def runs(self, *, spec_name):
        return [r for r in self._runs if r.spec_name == spec_name]

    def get_run(self, run_id):
        return self._known.get(run_id)

    def create_run(self, **kwargs):
        self.created.append(kwargs)
        parent = kwargs.get("parent_run_id") or ""
        return SimpleNamespace(
            run_id="run-new",
            state=SimpleNamespace(value="running"),
            parent_run_id=parent,
            family_id=parent or "run-new",
        )

    def close(self):
        pass


def _resume_args(**over):
    base = dict(only_phase=None, model="m", resume=False, parent_run_id="")
    base.update(over)
    return SimpleNamespace(**base)


def _demo_spec():
    return SimpleNamespace(name="demo", workflow_revision_id="rev1")


def test_resume_links_only_the_explicit_parent_run(monkeypatch):
    module = _load_module()
    prior = _PriorRun("run-old", module.RunState.FAILED)
    db = _ResumeDB([prior], {"run-old": prior})
    monkeypatch.setattr(module, "_control_db", lambda: db)
    run_id, _ = module._control_open_run(
        _demo_spec(), _resume_args(resume=True, parent_run_id="run-old")
    )
    assert run_id == "run-new"
    assert db.created[0]["parent_run_id"] == "run-old"


def test_resume_refuses_a_bad_explicit_parent_before_any_run_is_created(monkeypatch, capsys):
    """An explicit identity that does not validate (unknown id / another spec's run /
    a run that is not continuable) refuses the whole run — never a silently ignored link."""
    module = _load_module()
    known = {
        "run-a": _PriorRun("run-a", module.RunState.FAILED),
        "run-other": _PriorRun("run-other", module.RunState.FAILED, spec_name="other"),
        "run-done": _PriorRun("run-done", module.RunState.PROMOTABLE),
    }
    db = _ResumeDB(list(known.values()), known)
    monkeypatch.setattr(module, "_control_db", lambda: db)
    for bad in ("run-ghost", "run-other", "run-done"):
        with pytest.raises(SystemExit) as exc:
            module._control_open_run(_demo_spec(), _resume_args(resume=True, parent_run_id=bad))
        assert exc.value.code == 2
    assert "REFUSED" in capsys.readouterr().err
    assert db.created == []  # refused BEFORE any run row was created


def test_resume_never_picks_by_recency_when_ambiguous(monkeypatch, capsys):
    """Two continuable runs: no ordering guess, no family link — the candidates are named
    so the operator can pass --parent-run-id, and the run proceeds as its own family root."""
    module = _load_module()
    runs = [
        _PriorRun("run-a", module.RunState.FAILED),
        _PriorRun("run-b", module.RunState.CANCELLED),
    ]
    db = _ResumeDB(runs, {})
    monkeypatch.setattr(module, "_control_db", lambda: db)
    module._control_open_run(_demo_spec(), _resume_args(resume=True))
    assert db.created[0]["parent_run_id"] == ""
    err = capsys.readouterr().err
    assert "AMBIGUOUS" in err and "run-a" in err and "run-b" in err


def test_resume_links_the_single_continuable_candidate(monkeypatch):
    """One continuable candidate beside a non-continuable newer run: deterministic link."""
    module = _load_module()
    done = _PriorRun("run-done", module.RunState.PROMOTABLE)
    continuable = _PriorRun("run-failed", module.RunState.FAILED)
    db = _ResumeDB([done, continuable], {})
    monkeypatch.setattr(module, "_control_db", lambda: db)
    module._control_open_run(_demo_spec(), _resume_args(resume=True))
    assert db.created[0]["parent_run_id"] == "run-failed"


def test_ledger_path_is_collision_proof_and_identity_carrying(tmp_path, monkeypatch):
    """Wave B1 storage: microsecond precision + the run id in the name; a same-second
    sibling never overwrites, and spec_status's fallback parser reads the name back."""
    module = _load_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    now = module.datetime(2026, 9, 12, 16, 41, 42, 123456, tzinfo=module.timezone.utc)
    first = module._ledger_out_path("demo", run_id="run-abc", now=now)
    first.write_text("{}")
    second = module._ledger_out_path("demo", run_id="run-abc", now=now)
    third = module._ledger_out_path("demo", run_id="run-other", now=now)
    assert first.name == "20260912T164142123456Z_run-abc.json"
    assert second.name == "20260912T164142123456Z_run-abc.1.json"  # never overwrites
    assert third.name == "20260912T164142123456Z_run-other.json"  # same second, distinct runs
    from agentic_dynamics.experiment.spec_status import parse_timestamp

    assert parse_timestamp(first.stem) == now
    assert parse_timestamp(second.stem) == now
