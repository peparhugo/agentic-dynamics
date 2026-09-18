"""Review-fix tests (PR #80): explicit chroma endpoints + bounded construction.

Finding 1 — the port default must not be implied across environments:
  * the HOST default is localhost:8100 (the published loopback port);
  * the container pair is chromadb:8000 (declared together in x-ladder-env);
  * a NAMED host with no declared port is refused, never paired with the host port.

Finding 2 — construction must be bounded BEFORE it performs I/O:
  * a server that answers the heartbeat but stalls the identity endpoint fails within the
    declared deadline (the reviewer's repro);
  * with the preflight disabled, the construction wait itself is bounded, and a repeated
    attempt against the same endpoint is refused by the cooldown (bounded outstanding work).
"""

from __future__ import annotations

import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src", _ROOT / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from agentic_dynamics.knowledge import embeddings as emb  # noqa: E402
from agentic_dynamics.knowledge.embeddings import ChromaStore, ChromaStoreError  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("CHROMA_HOST", raising=False)
    monkeypatch.delenv("CHROMA_PORT", raising=False)


# ── finding 1: endpoint resolution ──────────────────────────────


def test_host_default_is_the_published_loopback_port():
    assert emb.resolve_chroma_endpoint() == ("localhost", 8100)


def test_container_pair_resolves_explicitly(monkeypatch):
    monkeypatch.setenv("CHROMA_HOST", "chromadb")
    monkeypatch.setenv("CHROMA_PORT", "8000")
    assert emb.resolve_chroma_endpoint() == ("chromadb", 8000)


def test_named_host_without_port_is_refused(monkeypatch):
    monkeypatch.setenv("CHROMA_HOST", "chromadb")
    with pytest.raises(ChromaStoreError) as excinfo:
        emb.resolve_chroma_endpoint()
    message = str(excinfo.value)
    assert "CHROMA_PORT" in message and "8000" in message and "8100" in message


def test_explicit_arguments_win(monkeypatch):
    monkeypatch.setenv("CHROMA_HOST", "chromadb")
    monkeypatch.setenv("CHROMA_PORT", "8000")
    assert emb.resolve_chroma_endpoint("127.0.0.1", 8100) == ("127.0.0.1", 8100)


# ── finding 2: bounded construction ─────────────────────────────


class _HeartbeatStallHandler(BaseHTTPRequestHandler):
    """Answers the heartbeat; every other path stalls (the reviewer's repro server)."""

    def do_GET(self):  # noqa: N802 — the BaseHTTPRequestHandler contract
        if "heartbeat" in self.path:
            body = b'{"nanosecond heartbeat": 1}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        time.sleep(3)

    def log_message(self, *args):  # keep test output quiet
        return


def _stalling_server() -> tuple[ThreadingHTTPServer, int]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _HeartbeatStallHandler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_port


def _silent_server() -> tuple[socket.socket, threading.Event, int]:
    """A TCP listener that accepts connections and never answers (a hung backend)."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(8)
    stop = threading.Event()

    def loop() -> None:
        while not stop.is_set():
            try:
                server.settimeout(0.2)
                conn, _ = server.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            conn.settimeout(0.2)
            try:
                while not stop.is_set():
                    time.sleep(0.05)
            finally:
                conn.close()

    threading.Thread(target=loop, daemon=True).start()
    return server, stop, server.getsockname()[1]


def test_construction_fails_within_deadline_when_identity_stalls():
    server, port = _stalling_server()
    try:
        started = time.monotonic()
        with pytest.raises(ChromaStoreError) as excinfo:
            ChromaStore(host="127.0.0.1", port=port, timeout_s=0.3)
        elapsed = time.monotonic() - started
    finally:
        server.shutdown()
        server.server_close()
    assert elapsed < 2.0, f"construction took {elapsed:.2f}s against an identity-stalling server"
    message = str(excinfo.value)
    assert "identity" in message or "construction" in message


def test_bounded_construction_backstop_and_cooldown(monkeypatch):
    # The preflight would catch this server first; disable it so the CONSTRUCTION wait itself
    # is what is measured (review finding 2's backstop).
    monkeypatch.setattr(emb, "_probe_chroma", lambda *a, **k: None)
    server, stop, port = _silent_server()
    try:
        started = time.monotonic()
        with pytest.raises(ChromaStoreError):
            ChromaStore(host="127.0.0.1", port=port, timeout_s=0.3)
        first = time.monotonic() - started

        second_started = time.monotonic()
        with pytest.raises(ChromaStoreError) as excinfo:
            ChromaStore(host="127.0.0.1", port=port, timeout_s=0.3)
        second = time.monotonic() - second_started
    finally:
        stop.set()
        server.close()

    assert first < 2.0, f"bounded construction took {first:.2f}s"
    assert second < 0.2, f"a recent construction failure must refuse fast (took {second:.2f}s)"
    assert "suppressed" in str(excinfo.value)
