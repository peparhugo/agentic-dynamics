import sys
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
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
