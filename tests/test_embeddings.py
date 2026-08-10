"""Tests for embeddings module — EmbeddingClient, ChromaStore, extract_session_text."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from instrument.embeddings import EmbeddingClient, ChromaStore, extract_session_text


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


class TestChromaStore:
    TEST_COLLECTION = "test_session_embeddings"

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.store = ChromaStore()
        self.store._collection = self.store._client.get_or_create_collection(
            self.TEST_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        yield
        try:
            self.store._client.delete_collection(self.TEST_COLLECTION)
        except Exception:
            pass

    def test_connectivity(self):
        store = ChromaStore()
        assert store.count() >= 0

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
