"""Tests for embeddings module — EmbeddingClient, ChromaStore, extract_session_text."""

import contextlib
import os
import socket
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentic_dynamics.knowledge.embeddings import (
    ChromaStore,
    ChromaStoreError,
    EmbeddingClient,
    extract_session_text,
    step_doc_id,
)

# Skip entire module if Ollama or ChromaDB is unreachable
try:
    socket.create_connection(("localhost", 11434), timeout=2).close()
    _OLLAMA_OK = True
except Exception:
    _OLLAMA_OK = False
try:
    socket.create_connection(("localhost", 8000), timeout=2).close()
    _CHROMA_OK = True
except Exception:
    _CHROMA_OK = False

NEEDS_OLLAMA = pytest.mark.skipif(not _OLLAMA_OK, reason="Ollama not available on localhost:11434")
NEEDS_CHROMA = pytest.mark.skipif(not _CHROMA_OK, reason="ChromaDB not available on localhost:8000")


pytestmark = [pytest.mark.external, NEEDS_OLLAMA]


TEST_DIR = Path(__file__).resolve().parent


class TestEmbeddingClient:
    def test_embed_returns_1024_dim_vector(self):
        client = EmbeddingClient(model="bge-m3:latest")
        result = client.embed("hello world")
        assert isinstance(result, list)
        assert len(result) == 1024
        assert all(isinstance(x, float) for x in result)

    def test_embed_different_inputs_produce_different_vectors(self):
        client = EmbeddingClient()
        a = client.embed("build a web server in rust")
        b = client.embed("write a poem about flowers")
        assert a != b

    def test_embed_batch_returns_correct_count(self):
        client = EmbeddingClient()
        texts = ["one", "two", "three"]
        results = client.embed_batch(texts, batch_size=2)
        assert len(results) == 3
        assert all(len(r) == 1024 for r in results)

    def test_cosine_distance_identical_is_zero(self):
        client = EmbeddingClient()
        a = client.embed("identical text")
        b = client.embed("identical text")
        dist = client.cosine_distance(a, b)
        assert 0.0 <= dist < 0.05

    def test_cosine_distance_different_is_high(self):
        client = EmbeddingClient()
        a = client.embed("python web framework")
        b = client.embed("quantum physics")
        dist = client.cosine_distance(a, b)
        assert dist > 0.1

    def test_cosine_distance_empty_vectors(self):
        client = EmbeddingClient()
        assert client.cosine_distance([], [1.0, 2.0]) == 1.0
        assert client.cosine_distance([1.0], []) == 1.0
        assert client.cosine_distance([], []) == 1.0

    def test_embedding_distance_paired_texts(self):
        client = EmbeddingClient()
        baseline = ["build an API", "add auth", "write tests"]
        perturbed = ["construct endpoint", "add login", "write specs"]
        dist = client.embedding_distance(baseline, perturbed)
        assert 0.0 <= dist <= 1.0

    def test_embedding_distance_empty_inputs(self):
        client = EmbeddingClient()
        assert client.embedding_distance([], []) == 0.0
        assert client.embedding_distance([], ["something"]) == 0.0

    def test_default_model_is_bge_m3(self):
        client = EmbeddingClient()
        assert client.model == "bge-m3:latest"


def _chroma_reachable(timeout: float = 3.0) -> bool:
    """True only when a REAL Chroma server answers a heartbeat.

    A port with any OTHER service (this machine's 8000 held the opencode web server)
    must count as unavailable — the live tests would otherwise hang on a mismatched
    protocol: chromadb.HttpClient retries with backoff and no connect timeout, which
    stalled the full deterministic suite for ~60 minutes twice during
    cap_stabilization_release p3.
    """
    import json
    import urllib.request

    host = os.environ.get("CHROMA_HOST", "localhost")
    port = int(os.environ.get("CHROMA_PORT", "8000"))
    for path in ("/api/v2/heartbeat", "/api/v1/heartbeat"):
        try:
            with urllib.request.urlopen(f"http://{host}:{port}{path}", timeout=timeout) as resp:
                body = json.loads(resp.read())
            if isinstance(body, dict) and "heartbeat" in body:
                return True
        except Exception:  # noqa: BLE001 — any failure (refused, wrong protocol, timeout) = unavailable
            continue
    return False


CHROMA_REACHABLE = _chroma_reachable()


class TestChromaStore:
    TEST_COLLECTION = "test_session_embeddings"

    pytestmark = pytest.mark.skipif(
        not CHROMA_REACHABLE,
        reason="Chroma server unavailable (heartbeat failed) — live-server tests skip, never hang",
    )

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.store = ChromaStore()
        self.store._collection = self.store._client.get_or_create_collection(
            self.TEST_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        yield
        with contextlib.suppress(Exception):
            self.store._client.delete_collection(self.TEST_COLLECTION)

    def test_connectivity(self):
        """Live-server probe with an availability GUARD (cap_stabilization_release p3
        stall post-mortem): chromadb.HttpClient retries with backoff and no connect
        timeout, so a missing or mismatched server on CHROMA_HOST:CHROMA_PORT (which can
        collide with another service — port 8000 held the opencode web server here) hung
        the full deterministic suite for ~60 minutes on two occasions. A live probe in
        the deterministic suite must SKIP when its server is unavailable — 'unavailable
        is a measured status' — and must never hang."""
        import socket

        host = os.environ.get("CHROMA_HOST", "localhost")
        port = int(os.environ.get("CHROMA_PORT", "8000"))
        try:
            with socket.create_connection((host, port), timeout=3):
                pass
        except OSError as exc:
            pytest.skip(f"Chroma unavailable at {host}:{port} ({exc})")
        try:
            store = ChromaStore()
            assert store.count() >= 0
        except Exception as exc:  # noqa: BLE001 — a mismatched server is skip, not hang
            pytest.skip(f"Chroma unavailable at count(): {exc}")
    def test_index_and_search_session(self):
        self.store.COLLECTION_NAME = self.TEST_COLLECTION
        self.store._collection = None
        steps = [
            {"text": "The model explored WebSocket-based live reload protocols",
             "step_index": 0, "tool_after": "write", "tool_input_summary": "websocket code"},
            {"text": "Testing the connection with chokidar file watching",
             "step_index": 1, "tool_after": "bash", "tool_input_summary": "pytest -v"},
        ]
        self.store.index_session_steps(
            session_id="test_session_1",
            steps=steps,
            metadata={
                "model": "deepseek/deepseek-v4-pro",
                "experiment": "typescript_ssg",
                "strategy": "conservative",
                "correctness": 0.9,
                "cost_usd": 0.01,
            },
        )
        doc_count = self.store.count()
        assert doc_count >= 1

        results = self.store.search(
            query="live reload websocket connection",
            top_k=3,
        )
        assert len(results) >= 1
        hit = results[0]
        assert "test_session_1" in hit["id"]
        assert "deepseek" in hit["metadata"].get("model", "")

    def test_search_with_model_filter(self):
        self.store.COLLECTION_NAME = self.TEST_COLLECTION
        self.store._collection = None
        steps = [
            {"text": "the reasoning step one about the project setup",
             "step_index": 0, "tool_after": "", "tool_input_summary": ""},
            {"text": "the reasoning step two about implementation",
             "step_index": 1, "tool_after": "", "tool_input_summary": ""},
        ]
        self.store.index_session_steps(
            session_id="gpt_test",
            steps=steps,
            metadata={"model": "openai/gpt-5"},
        )
        results = self.store.search(
            query="reasoning step",
            top_k=3,
            filter_model="openai/gpt-5",
        )
        assert len(results) >= 1
        for hit in results:
            assert hit["metadata"].get("model") == "openai/gpt-5"

    def test_index_session_empty_texts_does_not_crash(self):
        self.store.COLLECTION_NAME = self.TEST_COLLECTION
        self.store._collection = None
        steps = [
            {"text": "", "step_index": 0, "tool_after": "", "tool_input_summary": ""},
            {"text": "x" * 15, "step_index": 1, "tool_after": "", "tool_input_summary": ""},
        ]
        self.store.index_session_steps(
            session_id="empty_session",
            steps=steps,
            metadata={},
        )
        assert True


class TestExtractSessionText:
    def test_extracts_reasoning_and_metadata(self):
        session_file = (
            Path(__file__).resolve().parent.parent
            / "experiments" / "results" / "reports"
            / "exp_0s36_d3n" / "session.jsonl"
        )
        if not session_file.exists():
            pytest.skip("No session.jsonl available for testing")

        reasoning, outputs, meta = extract_session_text(session_file)
        assert isinstance(reasoning, str)
        assert isinstance(outputs, str)
        assert isinstance(meta, dict)
        assert "session_id" in meta
        assert "cost_usd" in meta

    def test_missing_file_raises(self):
        fake_path = Path("/nonexistent/session.jsonl")
        with pytest.raises(FileNotFoundError):
            extract_session_text(fake_path)


class TestCanonicalChromaStore:
    """Generic canonical upsert/delete/inventory, collection isolation, env endpoint."""

    def test_step_doc_id_canonical_format(self):
        # The canonical step-document id scheme shared with the graph index.
        assert step_doc_id("sess", 0) == "sess_step_0000"
        assert step_doc_id("sess", 12) == "sess_step_0012"
        assert step_doc_id("sess", 9999) == "sess_step_9999"

    def test_default_collection_name_unchanged(self):
        store = ChromaStore()
        assert store.COLLECTION_NAME == "session_embeddings"

    def test_collection_isolation(self):
        a = ChromaStore(collection_name="test_iso_a")
        b = ChromaStore(collection_name="test_iso_b")
        try:
            a.upsert(["k1"], ["alpha doc"], metadatas=[{"authority": "source"}],
                     embeddings=[[0.1, 0.2, 0.3]])
            b.upsert(["k2"], ["beta doc"], metadatas=[{"authority": "advisory"}],
                     embeddings=[[0.3, 0.2, 0.1]])
            assert a.count() == 1
            assert b.count() == 1
            assert a.inventory()["ids"] == ["k1"]
            assert b.inventory()["ids"] == ["k2"]
        finally:
            a._client.delete_collection("test_iso_a")
            b._client.delete_collection("test_iso_b")

    def test_upsert_delete_inventory_round_trip(self):
        store = ChromaStore(collection_name="test_roundtrip")
        try:
            ids = [step_doc_id("sess_1", i) for i in range(3)]
            n = store.upsert(
                ids,
                [f"document {i}" for i in range(3)],
                metadatas=[{"authority": "source", "i": i} for i in range(3)],
                embeddings=[[0.1, 0.2, 0.3] for _ in range(3)],
            )
            assert n == 3
            inv = store.inventory()
            assert inv["count"] == 3
            assert set(inv["ids"]) == set(ids)
            checkpoint_before = inv["checkpoint"]

            store.delete([ids[0]])
            assert store.count() == 2
            assert store.inventory()["ids"] == sorted(ids[1:])
            # Removing a doc changes the reconciliation checkpoint.
            assert store.inventory()["checkpoint"] != checkpoint_before
        finally:
            store._client.delete_collection("test_roundtrip")

    def test_search_with_where_filter(self):
        store = ChromaStore(collection_name="test_where")
        try:
            store.upsert(
                ["w1", "w2"],
                [
                    "live reload websocket protocol for a static site generator",
                    "quantum physics entanglement of distant particles",
                ],
                metadatas=[{"authority": "source"}, {"authority": "advisory"}],
            )
            hits = store.search("websocket live reload", top_k=5, where={"authority": "source"})
            assert hits
            assert all(h["metadata"].get("authority") == "source" for h in hits)
        finally:
            store._client.delete_collection("test_where")

    def test_upsert_propagates_store_failure(self):
        store = ChromaStore(collection_name="test_err")
        try:
            with pytest.raises(ChromaStoreError):
                store.upsert(["a"], [], embeddings=[[0.1, 0.2, 0.3]])
        finally:
            store._client.delete_collection("test_err")

    def test_env_endpoint(self, monkeypatch):
        monkeypatch.setenv("CHROMA_HOST", "chroma.test")
        monkeypatch.setenv("CHROMA_PORT", "9999")
        captured: dict = {}

        import chromadb

        class FakeHttpClient:
            def __init__(self, host, port):
                captured["host"] = host
                captured["port"] = port

        monkeypatch.setattr(chromadb, "HttpClient", FakeHttpClient)
        ChromaStore()
        assert captured["host"] == "chroma.test"
        assert captured["port"] == 9999
