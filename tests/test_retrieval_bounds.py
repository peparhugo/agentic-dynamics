"""Deterministic bounded-retrieval tests (delivery-simplification Units 4-5).

The five required failure cases, each a deterministic stub (no live services):

1. dense backend stalls -> healthy lexical results return within the declared budget,
   with dense unavailability preserved in ``leg_errors`` / ``fallback_mode``;
2. embedding service stalls -> the pass returns within budget with the cause recorded;
3. both retrieval legs unavailable -> ``no_rag``, never a successful empty search;
4. healthy retrieval finds no applicable evidence -> genuinely empty (``full``);
5. an access refusal remains a refusal: fallback never relaxes the ACL/repository filters.

Plus the transport-level bounds the repair adds: ChromaStore's bounded construction
pre-flight against a silent server, and the chromadb session timeout application.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from agentic_dynamics.knowledge import embeddings as emb
from agentic_dynamics.knowledge.embeddings import ChromaStore, ChromaStoreError
from agentic_dynamics.knowledge.retrieval import (
    FallbackMode,
    _pairwise_similarities,
    retrieve,
)

_ROOT = Path(__file__).resolve().parent.parent

REPO = "agentic-dynamics"
ACL = "public"
OBSERVED = "2026-09-01T00:00:00+00:00"


def _dense_hit(cid: str, text: str = "some text", **meta) -> dict:
    metadata = {
        "source_type": "finding",
        "authority": "MEASURED",
        "repository_id": REPO,
        "acl_scope": ACL,
        "commit_sha": "",
        "observed_at": OBSERVED,
    }
    metadata.update(meta)
    return {"id": cid, "document": text, "metadata": metadata, "distance": 0.1}


def _lex_hit(cid: str, text: str = "some text", *, score: float = 1.0, **props) -> dict:
    properties = {
        "source_type": "finding",
        "authority": "MEASURED",
        "repository_id": REPO,
        "acl_scope": ACL,
        "commit_sha": "",
        "observed_at": OBSERVED,
        "text": text,
    }
    properties.update(props)
    return {"id": cid, "labels": ["Knowledge"], "properties": properties, "score": score}


class _GraphStub:
    def __init__(self, hits: list[dict] | None = None, expand: list[dict] | None = None):
        self._hits = list(hits or [])
        self._expand = list(expand or [])

    def search_knowledge_fulltext(self, query, *, limit=10, commit=None):
        return list(self._hits)

    def expand_candidates(self, seeds, **kwargs):
        return list(self._expand)


class _DenseStub:
    def __init__(self, hits: list[dict] | None = None, *, block: threading.Event | None = None, exc=None):
        self._hits = list(hits or [])
        self._block = block
        self._exc = exc

    def search(self, query, *, top_k=10, where=None):
        if self._exc is not None:
            raise self._exc
        if self._block is not None:
            self._block.wait(10)
        return list(self._hits)


class _BlockingEmbedder:
    """An embedder that blocks until the test releases it — the stalled-provider case."""

    def __init__(self):
        self.gate = threading.Event()

    def embed(self, text):
        self.gate.wait(10)
        return [0.1, 0.2]

    def embed_batch(self, texts, batch_size=32):
        return [self.embed(t) for t in texts]

    def cosine_distance(self, a, b):
        return 0.5


# ── 1. dense stall, healthy lexical ─────────────────────────────


def test_dense_stall_lexical_returns_within_budget():
    gate = threading.Event()
    dense = _DenseStub(block=gate)
    graph = _GraphStub([_lex_hit("k1", "approved finding text")])
    started = time.monotonic()
    try:
        attempt = retrieve(
            "how do retries work",
            dense_store=dense,
            graph_client=graph,
            repository_id=REPO,
            acl_scope=ACL,
            deadline_s=0.5,
        )
        elapsed = time.monotonic() - started
    finally:
        gate.set()  # release the stuck legs so the pool winds down

    assert elapsed < 3.0, f"retrieve() took {elapsed:.2f}s despite a 0.5s budget"
    assert attempt.fallback_mode == FallbackMode.LEXICAL_GRAPH_ONLY.value
    assert "dense" in attempt.leg_errors
    assert "budget" in attempt.leg_errors["dense"]
    assert any(c.id == "k1" for c in attempt.candidates)


# ── 2. embedding stall ──────────────────────────────────────────


def test_embedding_stall_records_cause_within_budget(monkeypatch):
    stub = _BlockingEmbedder()
    monkeypatch.setattr(emb, "EmbeddingClient", lambda *a, **k: stub)
    dense = _DenseStub([_dense_hit("d1", "alpha text"), _dense_hit("d2", "beta text")])
    graph = _GraphStub([])
    started = time.monotonic()
    try:
        attempt = retrieve(
            "alpha", dense_store=dense, graph_client=graph, deadline_s=0.5
        )
        elapsed = time.monotonic() - started
    finally:
        stub.gate.set()

    assert elapsed < 3.0, f"retrieve() took {elapsed:.2f}s despite a 0.5s budget"
    assert "embedding" in attempt.leg_errors
    assert "deadline" in attempt.leg_errors["embedding"]
    assert attempt.dedup_path == "none"


def test_pairwise_similarities_timeout_cause_is_named():
    embedder = _BlockingEmbedder()
    candidates = [
        SimpleNamespace(id="a", text="x"),
        SimpleNamespace(id="b", text="y"),
    ]
    started = time.monotonic()
    try:
        sims, path, error = _pairwise_similarities(candidates, embedder, timeout_s=0.3)
        elapsed = time.monotonic() - started
    finally:
        embedder.gate.set()
    assert sims == {} and path == "none"
    assert "deadline" in error
    assert elapsed < 2.0


# ── 3. both legs unavailable ────────────────────────────────────


def test_both_legs_unavailable_is_unavailable_not_empty():
    attempt = retrieve("anything", dense_store=None, graph_client=None)
    assert attempt.fallback_mode == FallbackMode.NO_RAG.value
    assert attempt.selected_evidence == []


# ── 4. healthy search, no evidence ──────────────────────────────


def test_healthy_search_with_no_evidence_is_genuinely_empty():
    attempt = retrieve(
        "anything",
        dense_store=_DenseStub([]),
        graph_client=_GraphStub([]),
        repository_id=REPO,
        acl_scope=ACL,
    )
    assert attempt.fallback_mode == FallbackMode.FULL.value
    assert attempt.leg_errors == {}
    assert attempt.candidates == []
    assert attempt.selected_evidence == []


# ── 5. refusal survives fallback ────────────────────────────────


def test_refusal_survives_leg_fallback():
    # The dense leg is down; the lexical leg returns a private coordinator record, a
    # wrong-repository record, and one approved public record. Only the public record may
    # surface — the fallback must not relax ACL or scope filters.
    dense = _DenseStub(exc=RuntimeError("dense backend down"))
    graph = _GraphStub(
        [
            _lex_hit("private1", "coordinator private note", acl_scope="org:agentic-dynamics"),
            _lex_hit("wrongrepo1", "other cell note", repository_id="self-other-cell"),
            _lex_hit("public1", "approved public finding"),
        ]
    )
    attempt = retrieve(
        "question",
        dense_store=dense,
        graph_client=graph,
        repository_id=REPO,
        acl_scope=ACL,
        deadline_s=1.0,
    )
    ids = {c.id for c in attempt.candidates}
    assert "public1" in ids
    assert "private1" not in ids
    assert "wrongrepo1" not in ids
    assert attempt.fallback_mode == FallbackMode.LEXICAL_GRAPH_ONLY.value
    assert "dense" in attempt.leg_errors


# ── transport-level bounds ──────────────────────────────────────


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
            # Accepted and deliberately unanswered: hold it, never read or write.
            conn.settimeout(0.2)
            try:
                while not stop.is_set():
                    time.sleep(0.05)
            finally:
                conn.close()

    threading.Thread(target=loop, daemon=True).start()
    return server, stop, server.getsockname()[1]


def test_chroma_construction_preflight_is_bounded_on_silent_server():
    server, stop, port = _silent_server()
    try:
        started = time.monotonic()
        with pytest.raises(ChromaStoreError):
            ChromaStore(host="127.0.0.1", port=port, timeout_s=0.3)
        elapsed = time.monotonic() - started
    finally:
        stop.set()
        server.close()
    assert elapsed < 3.0, f"ChromaStore construction took {elapsed:.2f}s against a silent server"


def test_bound_chroma_session_applies_declared_timeout():
    fake = SimpleNamespace(_server=SimpleNamespace(_session=SimpleNamespace()))
    assert emb._bound_chroma_session(fake, 2.5) is True
    assert float(fake._server._session.timeout.read) == 2.5


def test_embedding_client_declares_a_timeout():
    default = emb.EmbeddingClient()
    assert default.timeout_s > 0
    explicit = emb.EmbeddingClient(timeout_s=1.25)
    assert explicit.timeout_s == 1.25


# ── review fix P1: expansion is part of the budget ──────────────


class _SlowExpandGraph(_GraphStub):
    """A graph whose expansion blocks, ignoring its own ``timeout_ms`` (review repro)."""

    def expand_candidates(self, seeds, **kwargs):
        time.sleep(2.0)
        return []


def test_expansion_cannot_outlive_the_budget():
    dense = _DenseStub([_dense_hit("d1", "alpha text")])
    graph = _SlowExpandGraph([])
    started = time.monotonic()
    attempt = retrieve("q", dense_store=dense, graph_client=graph, deadline_s=0.4)
    elapsed = time.monotonic() - started
    assert elapsed < 1.5, f"retrieve() took {elapsed:.2f}s with a blocked expansion"
    assert "expansion" in attempt.leg_errors
    assert "budget" in attempt.leg_errors["expansion"]


# ── review fix P2: bounded in-flight work + daemon workers ──────


def test_stalled_dense_never_starves_healthy_lexical():
    """Review finding P1: per-dependency capacity — a stalled dense backend must not consume
    the capacity the healthy lexical fallback needs."""
    from agentic_dynamics.knowledge.retrieval import RETRIEVAL_LEG_CAPACITY

    gates = [threading.Event() for _ in range(6)]
    base_threads = threading.active_count()
    attempts = []
    started = time.monotonic()
    try:
        for i in range(5):
            dense = _DenseStub(block=gates[i])
            graph = _GraphStub([_lex_hit("k1", "approved lexical finding")])
            attempts.append(
                retrieve("q", dense_store=dense, graph_client=graph, deadline_s=0.15)
            )
        elapsed = time.monotonic() - started
        growth = threading.active_count() - base_threads
    finally:
        for gate in gates:
            gate.set()

    assert elapsed < 3.0, f"five outage calls took {elapsed:.2f}s"
    for attempt in attempts:
        # EVERY call still receives the healthy lexical evidence — never no_rag.
        assert any(c.id == "k1" for c in attempt.candidates), attempt.leg_errors
        assert attempt.fallback_mode == FallbackMode.LEXICAL_GRAPH_ONLY.value
    assert any(
        "capacity" in error for attempt in attempts for error in attempt.leg_errors.values()
    ), [a.leg_errors for a in attempts]
    assert growth <= RETRIEVAL_LEG_CAPACITY["dense"] + 2, (
        f"{growth} worker threads accumulated for {len(attempts)} calls"
    )


def test_embedding_timeouts_do_not_accumulate_threads(monkeypatch):
    from agentic_dynamics.knowledge.retrieval import RETRIEVAL_LEG_CAPACITY

    stub = _BlockingEmbedder()
    monkeypatch.setattr(emb, "EmbeddingClient", lambda *a, **k: stub)
    base_threads = threading.active_count()
    attempts = []
    started = time.monotonic()
    try:
        for _ in range(4):
            dense = _DenseStub([_dense_hit("d1", "alpha text"), _dense_hit("d2", "beta text")])
            graph = _GraphStub([])
            attempts.append(
                retrieve("alpha", dense_store=dense, graph_client=graph, deadline_s=0.15)
            )
        elapsed = time.monotonic() - started
        growth = threading.active_count() - base_threads
    finally:
        stub.gate.set()

    # L32: the bound scales under CI shard load; the deadline MECHANISM is what this pins.
    from conftest import wall_clock_tolerance

    assert elapsed < 3.0 * wall_clock_tolerance(), (
        f"four embedding-outage calls took {elapsed:.2f}s"
    )
    # Under pool saturation the DENSE leg may be the first refused, so the outage shows up as
    # "dense leg not started ... in flight" instead of the embedding deadline. Both are the
    # same fact — the call FAILED fast and accumulated nothing — so require a failure on
    # every attempt and the embedding outage named at least once.
    assert all(a.leg_errors for a in attempts), [a.leg_errors for a in attempts]
    assert any("embedding" in str(a.leg_errors) for a in attempts), [a.leg_errors for a in attempts]
    assert growth <= RETRIEVAL_LEG_CAPACITY["embedding"] + 2, (
        f"{growth} embedding worker threads accumulated"
    )


def test_process_exits_with_a_stuck_embedder():
    src = str(_ROOT / "src")
    script = """
import sys, threading, time
sys.path.insert(0, "SRC_PATH")
import agentic_dynamics.knowledge.embeddings as emb

class BlockingEmbedder:
    def embed(self, text):
        threading.Event().wait()  # blocks forever
        return [0.0]
    def embed_batch(self, texts, batch_size=32):
        return [self.embed(t) for t in texts]
    def cosine_distance(self, a, b):
        return 0.5

emb.EmbeddingClient = BlockingEmbedder

from agentic_dynamics.knowledge.retrieval import retrieve

_META = {"source_type": "finding", "authority": "MEASURED", "repository_id": "agentic-dynamics",
         "acl_scope": "public", "commit_sha": "", "observed_at": "2026-09-01T00:00:00+00:00"}

class Dense:
    def search(self, query, *, top_k=10, where=None):
        return [{"id": "d1", "document": "alpha", "metadata": dict(_META), "distance": 0.1},
                {"id": "d2", "document": "beta", "metadata": dict(_META), "distance": 0.1}]

class Graph:
    def search_knowledge_fulltext(self, query, *, limit=10, commit=None):
        return []

started = time.monotonic()
attempt = retrieve("alpha", dense_store=Dense(), graph_client=Graph(), deadline_s=0.2)
print("returned", round(time.monotonic() - started, 2), "legs", attempt.leg_errors, flush=True)
""".replace("SRC_PATH", src)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "returned" in completed.stdout


def test_process_exits_with_a_stuck_leg():
    src = str(_ROOT / "src")
    script = f'''
import sys, threading, time
sys.path.insert(0, {src!r})
from agentic_dynamics.knowledge.retrieval import retrieve

class Blocking:
    def search(self, query, *, top_k=10, where=None):
        threading.Event().wait()  # blocks forever
        return []

class Graph:
    def search_knowledge_fulltext(self, query, *, limit=10, commit=None):
        return []

started = time.monotonic()
attempt = retrieve("q", dense_store=Blocking(), graph_client=Graph(), deadline_s=0.2)
print("returned", round(time.monotonic() - started, 2), flush=True)
'''
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "returned" in completed.stdout


# ── review fix P2: named causes survive serialization ───────────


def test_leg_errors_survive_to_dict():
    dense = _DenseStub(exc=RuntimeError("dense connection refused"))
    graph = _GraphStub([])
    attempt = retrieve("q", dense_store=dense, graph_client=graph)
    payload = attempt.to_dict()
    assert "leg_errors" in payload
    assert "dense" in payload["leg_errors"]
    assert "connection refused" in payload["leg_errors"]["dense"]
