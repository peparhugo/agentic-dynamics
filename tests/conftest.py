import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _try_connect(host: str, port: int) -> bool:
    import socket

    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def neo4j_available():
    return _try_connect("localhost", 7687)


@pytest.fixture(scope="session")
def ollama_available():
    return _try_connect("localhost", 11434)


@pytest.fixture(scope="session")
def chroma_available():
    return _try_connect("localhost", 8000)


@pytest.fixture(scope="session")
def redis_fleet_available():
    """The framework Redis (heartbeats on db1, the knowledge stream on db2) at 6380."""
    return _try_connect("localhost", 6380)


@pytest.fixture(scope="session")
def opencode_available():
    bin_path = Path.home() / ".opencode" / "bin" / "opencode"
    return bin_path.exists()


def requires_neo4j(request):
    if not _try_connect("localhost", 7687):
        pytest.skip("Neo4j not available on localhost:7687")


def requires_ollama(request):
    if not _try_connect("localhost", 11434):
        pytest.skip("Ollama not available on localhost:11434")


def requires_chroma(request):
    if not _try_connect("localhost", 8000):
        pytest.skip("ChromaDB not available on localhost:8000")


def requires_opencode(request):
    if not (Path.home() / ".opencode" / "bin" / "opencode").exists():
        pytest.skip("opencode binary not available")


def pytest_addoption(parser):
    parser.addoption(
        "--run-docker",
        action="store_true",
        default=False,
        help="run the docker-marked tests (g1_parity_roundtrip's TRUE container round-trip, "
        "the real DockerVerifierExecutor execute -> spawn -> envelope -> classify path). "
        "Requires a working docker + the fleet-net network + a current fleet/base image "
        "whose baked /app copy matches the repo. Skipped by default; docker is optional "
        "in CI.",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "external: tests requiring external services (opencode, Ollama, ChromaDB, Neo4j)",
    )
    config.addinivalue_line(
        "markers",
        "fast: the parallel-safe unit subset (the sub-minute guards + audited pure-unit "
        "families) — no real subprocesses, no Redis/stores/ports, no real worktrees; "
        "selected by `pytest -m fast` (test_suite_speed p3). A test added to this subset "
        "without passing the parallel-safety audit is a violation.",
    )
    config.addinivalue_line(
        "markers",
        "docker: the TRUE container round-trip (g1_parity_roundtrip F2) — drives the real "
        "DockerVerifierExecutor against the real docker boundary. Opt-in via `--run-docker`; "
        "skipped (never silently passed) in every default run.",
    )


def pytest_collection_modifyitems(config, items):
    """Skip the docker-marked round-trip tests unless the operator opted in with --run-docker.

    The true container round-trip is a real docker smoke (image + network + the reference
    containerized path); it must never run in the default/CI suite. Skipping on the option
    (rather than at module import) keeps the docker tests visible as *skipped* in a default
    run — a regression in their collection shows as an error, not a silent absence.
    """
    if config.getoption("--run-docker"):
        return
    skip_docker = pytest.mark.skip(
        reason="docker round-trip opt-in: run with --run-docker (g1_parity_roundtrip F2)"
    )
    for item in items:
        if "docker" in item.keywords:
            item.add_marker(skip_docker)


@pytest.fixture(autouse=True)
def _isolate_control_db(tmp_path_factory, monkeypatch):
    """Point every test's control database at a throwaway file — never the repo's.

    ``control_db_publication`` p2 wired ``scripts/run_workflow.py``'s composition root to open
    the orchestrator's control database at run start. Without this guard, any test that drives
    ``main()`` (``test_run_workflow_graph_cli.py``, for one) creates a REAL
    ``experiments/results/control/control.db`` in the checkout as a side effect. It is
    gitignored, so it would never be committed — which is precisely why it needs a guard rather
    than a reviewer: state that cannot show up in ``git status`` is state nobody notices
    accumulating, and a test suite that mutates the machine's live control plane can also
    corrupt a concurrent orchestrator run's view of it.

    ``FINOPS_CONTROL_DB`` is the documented override (``control_db.resolve_db_path``), and an
    explicit constructor argument still outranks it — so ``tests/test_control_db.py`` and
    ``tests/test_outbox.py``, which pass their own ``tmp_path`` locations, are unaffected.
    """
    monkeypatch.setenv(
        "FINOPS_CONTROL_DB", str(tmp_path_factory.mktemp("control_db") / "control.db")
    )


def _start_broker_seam(tmp_path, monkeypatch, *, docker: str, compose: str,
                       compose_file: str | None = None):
    """Start a live launch-broker seam server (launch_broker.serve) on a tmp unix socket.

    Returns a namespace carrying ``socket_path`` (and the stop handle) and points
    ``FINOPS_LAUNCH_BROKER_SOCKET`` at it, so ``spawn_wrapper``'s seam client (which resolves
    the socket from the env at call time) round-trips through the server. The server runs in a
    daemon thread of the test process — the host-side broker stand-in for tests; production
    runs the same ``serve`` code under the ``agentic-dynamics-launch-broker.service`` systemd
    user unit. ``docker`` / ``compose`` are the broker's runtime binaries (tests pass stub
    paths when a REAL subprocess execution must be observed; lifecycle tests leave the names
    and patch ``subprocess.run`` themselves).
    """
    import threading
    import types

    from scripts.fleet import launch_broker

    socket_path = str(tmp_path / "launch-broker.sock")
    stop_event = threading.Event()
    ready = threading.Event()
    thread = threading.Thread(
        target=launch_broker.serve,
        kwargs={
            "socket_path": socket_path,
            "docker": docker,
            "compose": compose,
            "compose_file": compose_file,
            "stop_event": stop_event,
            "ready_event": ready,
        },
        daemon=True,
    )
    thread.start()
    assert ready.wait(10), "the launch-broker seam server did not start"
    monkeypatch.setenv("FINOPS_LAUNCH_BROKER_SOCKET", socket_path)
    seam = types.SimpleNamespace(socket_path=socket_path, stop_event=stop_event, thread=thread)
    return seam


@pytest.fixture
def broker_seam(tmp_path, monkeypatch):
    """A live launch-broker seam (fb2_broker_hostside): ``launch_broker.serve`` on a tmp socket.

    The broker runs with the default docker/compose binary NAMES (no execution — tests that
    need to observe a real subprocess patch ``subprocess.run`` per test, exactly as the
    consume-lifecycle tests have always done). The env var is set so ``spawn_wrapper``'s seam
    client reaches the server.
    """
    seam = _start_broker_seam(tmp_path, monkeypatch, docker="docker", compose="docker-compose")
    yield seam.socket_path
    seam.stop_event.set()
    seam.thread.join(timeout=10)


@pytest.fixture
def broker_seam_stub(tmp_path, monkeypatch):
    """A live launch-broker seam whose docker/compose are REAL STUB binaries (fb2 VERIFY d/e).

    The stub binaries record every argv they receive to ``BROKER_STUB_LOG`` and exit with
    ``BROKER_STUB_EXIT`` (default 0), so a test can assert the host broker executed the stub
    (the round-trip) and can force a nonzero docker outcome. Returns a namespace with
    ``socket_path``, ``docker_bin``, ``compose_bin`` and ``log`` (the argv record path).
    """

    log = tmp_path / "stub-calls.log"
    for name in ("docker", "docker-compose"):
        stub = tmp_path / name
        stub.write_text(
            "#!/bin/sh\n"
            f'echo "$@" >> "{log}"\n'
            'exit "${BROKER_STUB_EXIT:-0}"\n'
        )
        stub.chmod(0o755)
    monkeypatch.setenv("BROKER_STUB_LOG", str(log))
    monkeypatch.setenv("BROKER_STUB_EXIT", "0")
    seam = _start_broker_seam(
        tmp_path, monkeypatch,
        docker=str(tmp_path / "docker"),
        compose=str(tmp_path / "docker-compose"),
    )
    seam.docker_bin = str(tmp_path / "docker")
    seam.compose_bin = str(tmp_path / "docker-compose")
    seam.log = str(log)
    yield seam
    seam.stop_event.set()
    seam.thread.join(timeout=10)

def _disarm_finding_emit(monkeypatch):
    """Keep workflow-run finding emission out of the unit suite (kb_finding_layer k1).

    emit_self now DEFAULTS ON: every successful committed phase of a workflow run emits a
    scoped finding (a durable artifact under ``experiments/results/kb/`` plus a pointer onto
    the live DB-2 knowledge stream). The unit suite drives synthetic git worktrees with
    throwaway goals — real emissions would litter the canonical KB with a fake finding per
    committed phase on every run. Disarm via the documented env override
    (``FINOPS_EMIT_SELF=0``, the same disable-flag pattern as ``FINOPS_FACT_AUTO_EMIT``) for
    every test; the finding-emission tests themselves opt back in explicitly
    (``monkeypatch.delenv``) and stub the write seam, so the default-on behavior stays proven
    without touching the live KB.
    """
    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
