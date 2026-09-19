"""Unit tests for the Neo4j-native vector store (the retired Chroma service's replacement).

Fake driver/session — no live calls. Review-round regressions pinned here: bounded candidate
expansion with an explicit incomplete state (scoped recall), timestamps/identity in the hit
metadata, scope metadata persisted by the write path, and the backfill's failure semantics.
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


class _FakeTx:
    def __init__(self, session, timeout):
        self.session = session
        self.timeout = timeout

    def run(self, cypher, **params):
        self.session.calls.append((cypher, params))
        return _FakeResult(self.session.responder(cypher, params))

    def close(self):
        pass

    def commit(self):
        pass


class _FakeSession:
    def __init__(self, responder=None):
        self.responder = responder or (lambda cypher, params: [])
        self.calls = []

    def begin_transaction(self, timeout=None):
        return _FakeTx(self, timeout)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeEmbedder:
    def embed(self, text):
        return [0.0, 0.0, 0.0, 1.0]

    def embed_batch(self, texts, batch_size=32):
        return [self.embed(t) for t in texts]


def _store(session, *, corpus=-1):
    store = Neo4jVectorStore.__new__(Neo4jVectorStore)
    store._client = type(
        "C",
        (),
        {
            "_driver": type("D", (), {"session": lambda self: session})(),
            "close": lambda self: None,
        },
    )()
    store._embedder = _FakeEmbedder()
    store.dimensions = 4
    store.timeout_s = 5.0
    store.last_search_stats = {}
    store.last_search_incomplete = False
    store._corpus_count = corpus
    return store


def _row(i, **overrides):
    row = {
        "id": f"kid_{i}",
        "document": f"doc {i}",
        "score": 0.75,
        "repository_id": "agentic-dynamics",
        "acl_scope": "public",
        "commit_sha": "",
        "authority": "MEASURED",
        "source_type": "finding",
        "evidence_class": "[M]",
        "logical_locator": f"loc_{i}",
        "observed_at": "2026-09-01T00:00:00+00:00",
        "content_hash": "hash",
        "pattern_payload": "",
    }
    row.update(overrides)
    return row


# ── predicate translation ───────────────────────────────────────────────────────────────────


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


# ── hit contract ────────────────────────────────────────────────────────────────────────────


def test_search_returns_the_chroma_shaped_hit_contract_with_timestamps():
    """Review P2: the returned metadata keeps the timestamps and identities the freshness
    rules and the content joins consume."""
    session = _FakeSession(lambda cypher, params: [_row(1)])
    store = _store(session, corpus=1000)
    hits = store.search("q", top_k=3, where={"repository_id": "agentic-dynamics"})
    assert hits[0]["id"] == "kid_1"
    assert hits[0]["distance"] == pytest.approx(0.25)
    meta = hits[0]["metadata"]
    assert meta["observed_at"] == "2026-09-01T00:00:00+00:00"
    assert meta["content_hash"] == "hash"
    cypher, params = session.calls[0]
    assert "db.index.vector.queryNodes" in cypher
    assert "node.repository_id = $" in cypher
    assert "agentic-dynamics" in params.values()


# ── scoped recall: bounded expansion + explicit incomplete state (review P1) ────────────────


def test_search_expands_until_the_scoped_set_fills():
    """Other scopes dominating the global ranking must not starve the scoped result."""
    def responder(cypher, params):
        k = params["k"]
        if k < 64:
            return []  # every global neighbour belonged to another scope
        return [_row(i) for i in range(3)]

    store = _store(_FakeSession(responder), corpus=10000)
    hits = store.search("q", top_k=3, where={"repository_id": "agentic-dynamics"})
    assert len(hits) == 3
    assert store.last_search_stats["scanned"] == 64
    assert store.last_search_incomplete is False


def test_search_reports_incomplete_at_the_scan_cap():
    """A cap-limited scan with no scoped hits is EXPLICITLY incomplete — never a silent
    'nothing exists'."""
    store = _store(_FakeSession(lambda cypher, params: []), corpus=1000000)
    hits = store.search("q", top_k=3, where={"repository_id": "agentic-dynamics"})
    assert hits == []
    assert store.last_search_incomplete is True
    assert store.last_search_stats["scanned"] == 4096


def test_search_is_complete_when_the_corpus_is_exhausted():
    store = _store(_FakeSession(lambda cypher, params: []), corpus=10)
    assert store.search("q", top_k=3, where={"repository_id": "agentic-dynamics"}) == []
    assert store.last_search_incomplete is False


def test_unfiltered_short_page_is_the_index_exhaustion():
    store = _store(_FakeSession(lambda cypher, params: [_row(1)]), corpus=0)
    hits = store.search("q", top_k=10)
    assert len(hits) == 1
    assert store.last_search_incomplete is False


# ── write path: acknowledged = scoped-retrievable (review P2) ────────────────────────────────


def test_upsert_persists_scope_metadata_and_pattern_payload():
    session = _FakeSession()
    store = _store(session)
    store.upsert(
        ["kid_1"],
        documents=["doc"],
        metadatas=[
            {
                "repository_id": "agentic-dynamics",
                "acl_scope": "public",
                "authority": "DERIVED",
                "source_type": "pattern",
                "evidence_class": "[C]",
                "logical_locator": "workload:x#pattern",
                "commit_sha": "abc",
                "observed_at": "2026-09-01T00:00:00+00:00",
                "content_hash": "hash",
                "pattern_payload": {"claim": "c"},
            }
        ],
        embeddings=[[0.0, 0.0, 0.0, 1.0]],
    )
    cypher, params = session.calls[0]
    row = params["rows"][0]
    assert row["repository_id"] == "agentic-dynamics"
    assert row["acl_scope"] == "public"
    assert row["observed_at"] == "2026-09-01T00:00:00+00:00"
    assert row["pattern_payload"] == '{"claim": "c"}'
    assert "k.repository_id = coalesce(row.repository_id, k.repository_id)" in cypher


def test_upsert_requires_matching_vectors():
    store = _store(_FakeSession())
    with pytest.raises(Neo4jVectorStoreError):
        store.upsert(["a", "b"], embeddings=[[1.0]])


# ── backfill semantics (review P2) ───────────────────────────────────────────────────────────


def test_backfill_main_exit_codes(monkeypatch):
    """A failed or incomplete migration is nonzero; a requested batch completing is zero."""
    import agentic_dynamics.knowledge.neo4j_vectors as nv

    monkeypatch.setattr(
        nv,
        "backfill",
        lambda **k: {"embedded": 0, "skipped": 5, "total": 0, "remaining": 5, "failed": True},
    )
    assert nv.main(["--backfill"]) == 1

    monkeypatch.setattr(
        nv,
        "backfill",
        lambda **k: {"embedded": 10, "skipped": 0, "total": 10, "remaining": 3, "failed": False},
    )
    assert nv.main(["--backfill"]) == 1  # all-mode, still incomplete
    assert nv.main(["--backfill", "--limit", "10"]) == 0  # requested batch completed
