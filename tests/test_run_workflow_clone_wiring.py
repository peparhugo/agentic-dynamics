"""ws1 (fleet_launch_smoke ws1_clone_wired) — the per-run clone is born and bound.

The wave's hard rule 3: **PRIVATE CLONE PER RUN** — a run's cells execute in their own
ephemeral clone at ``PathConfig.runs_root/<run-id>/repo``, never in a shared host worktree.
The lifecycle module (``runtime.run_clone``) and the executor-side request contract are
covered in ``tests/test_run_clone.py`` and ``tests/test_workflow_executor_parity.py``. This
suite proves the piece neither of those reaches: the **composition root**
(``scripts/run_workflow.py``) actually invokes ``create_run_clone`` with the run id and binds
the clone into the Docker executors it builds.

VERIFY (both directions), each proved hermetically (no docker, no Redis):

* (a) under ``--orchestrator`` a run creates its clone before the executors are built — the
  composition mints the control-run id, calls ``create_run_clone(run_id)``, and only THEN
  constructs ``DockerAgentExecutor``/``DockerVerifierExecutor``;
* (b) the executors receive ``run_clone`` EXPLICITLY (the constructor argument, not the
  ``FINOPS_RUN_CLONE`` env fallback — the env read is the fallback, never the primary);
* (c) the clone path is under ``PathConfig.runs_root/<run-id>/repo``;
* (d) a non-orchestrator run creates NO clone and builds no Docker executors (no docker
  needed).

The suite loads ``scripts/run_workflow.py`` as a module under test (the same
``importlib.util.spec_from_file_location`` technique ``tests/test_fact_auto_emit.py`` and
``tests/test_run_workflow_graph_cli.py`` use), monkeypatches ``module.main``'s argv, the
``run_workflow`` engine, and the clone lifecycle seam, and points the control db at a
throwaway file (conftest's autouse ``_isolate_control_db``).
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agentic_dynamics.runtime.run_clone import RUN_CLONE_ENV  # noqa: E402


def _load_module(name="run_workflow_under_test_clone_wiring"):
    spec = importlib.util.spec_from_file_location(
        name, PROJECT_ROOT / "scripts" / "run_workflow.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(*args: str, cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"
    return (proc.stdout or "").strip()


def _make_source_repo(tmp_path: Path) -> Path:
    """A real, offline source repo the clone can be created from (one commit on main)."""
    repo = tmp_path / "src"
    repo.mkdir()
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("config", "user.email", "test@example.com", cwd=repo)
    _git("config", "user.name", "test", cwd=repo)
    (repo / "a.txt").write_text("one")
    _git("add", ".", cwd=repo)
    _git("commit", "-q", "-m", "base", cwd=repo)
    return repo


def _stub_spec(name: str = "demo"):
    return SimpleNamespace(
        name=name,
        spec_id=f"{name}@1.0",
        workflow_revision_id="sha256:" + "ab" * 32,
        workflow=SimpleNamespace(params={}),
    )


def _stub_result():
    return SimpleNamespace(
        to_dict=lambda: {"ok": True, "state": "succeeded", "phases": []},
        state="succeeded",
        total_cost_usd=0.0,
        ok=True,
        git_sha="abc123",
        phases=[],
        ended_at=None,
        awaiting=False,
        awaiting_phase=None,
        awaiting_reason=None,
    )


def _run_main(module, tmp_path, monkeypatch, *, fake_run, argv_extra):
    """Drive ``module.main()`` hermetically: tmp ROOT, stub spec/engine, quiet post-run hooks.

    ``argv_extra`` is appended to the required argv, so an orchestrator test passes
    ``["--orchestrator"]`` and a non-orchestrator test passes ``[]``.
    """
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "load_spec", lambda p: _stub_spec())
    monkeypatch.setattr(module, "run_workflow", fake_run)
    # Keep the post-run best-effort hooks quiet in the hermetic environment: the outbox drain
    # would touch Redis, and the spec-index refresh would read the real index.
    monkeypatch.setattr(module, "_control_terminal_write", lambda *a, **k: None)
    monkeypatch.setattr(module, "_refresh_index", lambda *a, **k: None)
    monkeypatch.setenv("FINOPS_FACT_AUTO_EMIT", "0")
    monkeypatch.setattr(sys, "argv", [
        "run_workflow.py", "--spec", "x.yaml", "--goal", "g", "--model", "m",
        "--workdir", str(tmp_path),
        *argv_extra,
    ])
    # The orchestrator composition EXPORTS FINOPS_RUN_CLONE to os.environ by design (the
    # child-environment export). In an in-process test that export would otherwise leak into
    # later tests; snapshot and restore the key around main().
    prior_env = os.environ.get(RUN_CLONE_ENV)
    try:
        return module.main()
    finally:
        if prior_env is None:
            os.environ.pop(RUN_CLONE_ENV, None)
        else:
            os.environ[RUN_CLONE_ENV] = prior_env


# ── (a)+(b)+(c): the --orchestrator composition creates the clone, then builds the executors ──

def test_orchestrator_run_creates_clone_with_run_id_before_building_executors(
    tmp_path, monkeypatch
):
    """(a)+(c): under --orchestrator the composition mints the control-run id, calls
    create_run_clone(run_id) so the clone lands at runs_root/<run-id>/repo, and only then
    constructs the Docker executors — which receive that clone path as run_clone."""
    src = _make_source_repo(tmp_path)
    runs_root = tmp_path / "runs"
    monkeypatch.setenv("FINOPS_REPO_DIR", str(src))
    monkeypatch.setenv("FINOPS_RUNS_ROOT", str(runs_root))
    # The composition exports FINOPS_RUN_CLONE to os.environ (the child-environment export is
    # its job); track the key via monkeypatch so it cannot leak into later tests in the same
    # process (a later "legacy executor" test would otherwise inherit a live clone env).
    monkeypatch.delenv(RUN_CLONE_ENV, raising=False)
    # The default workdir is NOT a git repo (tmp_path), so create_run_clone falls back to the
    # source's default-branch head — deterministic and offline.
    order: list[str] = []
    calls: dict = {"run_id": None}

    real_create = None
    module = _load_module()

    def fake_create(run_id, base_sha=None, **kwargs):
        order.append("create_run_clone")
        calls["run_id"] = run_id
        return real_create(run_id, base_sha, **kwargs)

    real_create = module.create_run_clone
    monkeypatch.setattr(module, "create_run_clone", fake_create)

    seen = {}

    def fake_run(spec, **kwargs):
        # The engine is only invoked AFTER the composition built the executors — so by the
        # time we observe the executors here, the clone must already have been created.
        order.append("run_workflow")
        seen["step_executor"] = kwargs.get("step_executor")
        seen["verifier_executor"] = kwargs.get("verifier_executor")
        return _stub_result()

    _run_main(module, tmp_path, monkeypatch, fake_run=fake_run, argv_extra=["--orchestrator"])

    # (a) the clone was created keyed by the CONTROL-run id (minted by _control_open_run),
    # and create_run_clone ran BEFORE the engine was handed its executors.
    assert calls["run_id"], "create_run_clone was never called under --orchestrator"
    assert calls["run_id"].startswith("run-")
    assert order.index("create_run_clone") < order.index("run_workflow")
    run_id = calls["run_id"]

    # (c) the clone lives under runs_root/<run-id>/repo and is a real git clone.
    clone_dir = runs_root / run_id / "repo"
    assert clone_dir.is_dir()
    assert (clone_dir / ".git").is_dir()
    assert (clone_dir / "a.txt").read_text() == "one"

    # (a) the executors WERE built (the engine received them) and are bound to the clone path.
    assert seen["step_executor"] is not None
    assert seen["verifier_executor"] is not None
    agent, verifier = seen["step_executor"], seen["verifier_executor"]
    assert agent._run_clone == str(clone_dir)
    assert verifier._run_clone == str(clone_dir)


def test_orchestrator_executors_carry_run_clone_explicitly_not_env_fallback(tmp_path, monkeypatch):
    """(b) the executors' run_clone is the CONSTRUCTOR argument, not the FINOPS_RUN_CLONE env:
    a decoy env value that differs from the created clone path is ignored. The composition
    exports the REAL clone path (its own env write), so the env can never be the source of the
    value the executors hold — the explicit argument is what reaches them."""
    src = _make_source_repo(tmp_path)
    runs_root = tmp_path / "runs"
    monkeypatch.setenv("FINOPS_REPO_DIR", str(src))
    monkeypatch.setenv("FINOPS_RUNS_ROOT", str(runs_root))
    # Track the exported key (see the ordering test) so it cannot leak across tests.
    monkeypatch.delenv(RUN_CLONE_ENV, raising=False)
    # Decoy env: if the executor ever read the env INSTEAD of the constructor argument, it
    # would resolve to this path (the composition overwrites it only AFTER the executors are
    # constructed, and the executor's read happens in __init__).
    monkeypatch.setenv(RUN_CLONE_ENV, str(tmp_path / "decoy-clone"))

    module = _load_module()

    seen = {}

    def fake_run_with_capture(spec, **kwargs):
        # By the time the engine runs, the composition has already exported the REAL clone path
        # (export happens after the executors are constructed, before run_workflow is invoked).
        seen["env_at_engine"] = os.environ.get(RUN_CLONE_ENV)
        seen["agent"] = kwargs.get("step_executor")
        seen["verifier"] = kwargs.get("verifier_executor")
        return _stub_result()

    _run_main(module, tmp_path, monkeypatch, fake_run=fake_run_with_capture,
              argv_extra=["--orchestrator"])

    agent, verifier = seen["agent"], seen["verifier"]
    clone_dir = runs_root / agent._run_clone.split("/")[-2] / "repo"
    # The executor holds the real clone path under runs_root/<run-id>/repo — NOT the decoy.
    assert agent._run_clone == str(clone_dir)
    assert verifier._run_clone == str(clone_dir)
    assert agent._run_clone != str(tmp_path / "decoy-clone")
    assert str(clone_dir).startswith(str(runs_root))
    # The composition exported the REAL path to the child environment.
    assert seen["env_at_engine"] == str(clone_dir)


def test_orchestrator_refuses_without_a_control_run_id(tmp_path, monkeypatch):
    """Fail-closed: if no control-run id was minted (control db unavailable), the orchestrator
    composition refuses loudly instead of silently running the pre-clone shared-worktree shape."""
    module = _load_module()

    def no_db(*a, **k):
        return None, None

    monkeypatch.setattr(module, "_control_open_run", no_db)
    monkeypatch.setattr(module, "run_workflow", lambda spec, **kw: _stub_result())
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "load_spec", lambda p: _stub_spec())
    monkeypatch.setattr(module, "_refresh_index", lambda *a, **k: None)
    monkeypatch.setenv("FINOPS_FACT_AUTO_EMIT", "0")
    monkeypatch.setattr(sys, "argv", [
        "run_workflow.py", "--spec", "x.yaml", "--goal", "g", "--model", "m",
        "--workdir", str(tmp_path), "--orchestrator",
    ])
    with pytest.raises(SystemExit, match="no control-run id"):
        module.main()


# ── (d): a non-orchestrator run creates no clone and builds no Docker executors ──

def test_non_orchestrator_run_creates_no_clone_and_no_docker_executors(tmp_path, monkeypatch):
    """(d) without --orchestrator the composition is inert: create_run_clone is never called,
    FINOPS_RUN_CLONE is never exported, and the engine runs with NO Docker executors (no docker
    needed on the in-process path)."""
    src = _make_source_repo(tmp_path)
    runs_root = tmp_path / "runs"
    monkeypatch.setenv("FINOPS_REPO_DIR", str(src))
    monkeypatch.setenv("FINOPS_RUNS_ROOT", str(runs_root))
    monkeypatch.delenv(RUN_CLONE_ENV, raising=False)

    module = _load_module()
    calls = {"n": 0}
    real_create = module.create_run_clone

    def fake_create(run_id, base_sha=None, **kwargs):
        calls["n"] += 1
        return real_create(run_id, base_sha, **kwargs)

    monkeypatch.setattr(module, "create_run_clone", fake_create)

    seen = {}

    def fake_run(spec, **kwargs):
        seen["step_executor"] = kwargs.get("step_executor")
        seen["verifier_executor"] = kwargs.get("verifier_executor")
        return _stub_result()

    _run_main(module, tmp_path, monkeypatch, fake_run=fake_run, argv_extra=[])

    assert calls["n"] == 0, "a non-orchestrator run must never create a clone"
    assert os.environ.get(RUN_CLONE_ENV) is None, "FINOPS_RUN_CLONE must not be exported"
    # the engine ran in-process: NO Docker executors were built (no docker needed)
    assert seen["step_executor"] is None
    assert seen["verifier_executor"] is None
    # nothing was ever cloned into runs_root
    assert not runs_root.exists() or not any((runs_root / d).is_dir() for d in os.listdir(runs_root))


def test_clone_path_shape_is_runs_root_run_id_repo(tmp_path):
    """(c, shape) the clone dir the composition binds is exactly runs_root/<run-id>/repo — the
    two-segment shape the broker's clone-mount contract and validate_spawn accept."""
    src = _make_source_repo(tmp_path)
    runs_root = tmp_path / "runs"
    module = _load_module()
    run_id = "run-shape-test"
    clone = module.create_run_clone(
        run_id, path_config=SimpleNamespace(
            repo_root=src,
            git_dir=src / ".git",
            runs_root=runs_root,
        ),
    )
    rel = clone.path.relative_to(runs_root)
    assert clone.path == runs_root / run_id / "repo"
    assert list(rel.parts) == [run_id, "repo"]
    assert (clone.path / ".git").is_dir()
