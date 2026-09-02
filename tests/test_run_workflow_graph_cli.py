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
    monkeypatch.setattr(module, "load_spec", lambda p: _stub_spec())
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
    monkeypatch.setattr(module, "load_spec", lambda p: _stub_spec())
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
    monkeypatch.setattr(module, "load_spec", spec_stub)
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
