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
