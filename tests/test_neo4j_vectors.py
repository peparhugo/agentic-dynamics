"""Unit tests for the Neo4j-native vector store (the retired Chroma service's replacement).

Fake driver/session — no live calls. The live proof lives in the operator's recovery
session (backfill + search + a full retrieval pass); these tests pin the translation and the
hit contract the fusion pipeline consumes.
"""

from __future__ import annotations

import pytest

from agentic_dynamics.knowledge.neo4j_vectors import (
    Neo4jVectorStore,
    Neo4jVectorStoreError,
    _predicate,
)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)

    def single(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def run(self, cypher, **params):
        self.calls.append((cypher, params))
        return _FakeResult(self.rows)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeDriver:
    def __init__(self, rows):
        self.session_obj = _FakeSession(rows)

    def session(self):
        return self.session_obj


class _FakeEmbedder:
    def embed(self, text):
        return [0.0, 0.0, 0.0, 1.0]


def _store(rows):
    store = Neo4jVectorStore.__new__(Neo4jVectorStore)
    store._client = type("C", (), {"_driver": _FakeDriver(rows), "close": lambda self: None})()
    store._embedder = _FakeEmbedder()
    store.dimensions = 4
    store._index_ready = True
    return store


def test_predicate_translates_the_pipeline_vocabulary():
    params: dict = {}
    pred = _predicate(
        {
            "$and": [
                {"repository_id": "agentic-dynamics"},
                {"acl_scope": "public"},
                {"$or": [{"commit_sha": ""}, {"authority": "MEASURED"}]},
            ]
        },
        params,
    )
    assert pred.count("node.") == 4
    assert " AND " in pred and " OR " in pred
    assert params == {
        "p0": "agentic-dynamics",
        "p1": "public",
        "p2": "",
        "p3": "MEASURED",
    }


def test_predicate_refuses_an_unknown_operator():
    with pytest.raises(Neo4jVectorStoreError):
        _predicate({"repository_id": {"$ne": "x"}}, {})


def test_search_returns_the_chroma_shaped_hit_contract():
    rows = [
        {
            "id": "kid_1",
            "document": "text one",
            "score": 0.75,
            "repository_id": "agentic-dynamics",
            "acl_scope": "public",
            "commit_sha": "",
            "authority": "MEASURED",
            "source_type": "finding",
            "evidence_class": "[M]",
            "logical_locator": "loc",
        }
    ]
    store = _store(rows)
    hits = store.search("q", top_k=3, where={"repository_id": "agentic-dynamics"})
    assert hits == [
        {
            "id": "kid_1",
            "document": "text one",
            "metadata": {
                "repository_id": "agentic-dynamics",
                "acl_scope": "public",
                "commit_sha": "",
                "authority": "MEASURED",
                "source_type": "finding",
                "evidence_class": "[M]",
                "logical_locator": "loc",
            },
            "distance": pytest.approx(0.25),
        }
    ]
    cypher, params = store._client._driver.session_obj.calls[0]
    assert "db.index.vector.queryNodes" in cypher
    assert "node.repository_id = $" in cypher
    assert "agentic-dynamics" in params.values()
    assert params["k"] == 12  # filtered queries over-fetch (top_k * 4)


def test_upsert_requires_matching_vectors():
    store = _store([])
    with pytest.raises(Neo4jVectorStoreError):
        store.upsert(["a", "b"], embeddings=[[1.0]])
