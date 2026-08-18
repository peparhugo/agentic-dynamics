"""Tests for the knowledge-base ingestion worker's consumer-group handlers (kb_worker.py).

New file — no existing test covered ``kb_worker.py``'s handlers before this (confirmed by
search: zero references to ``build_handler``/``kb_worker`` anywhere under ``tests/``
before this canonical-state round 2 change). Covers:

* ``kb-registry-v1`` — the new handler (plan step 8): appends one compacted JSON line per
  record to the flat, append-only registry index.
* ``kb-neo4j-v1`` — the gap (d) regression: the ``SET`` clause's bound-parameter dict must
  now include ``valid_from``/``observed_at``/``indexed_at``/``supersedes``/``causes`` (the
  base inventory proved these were silently dropped), and the ``SUPERSEDES`` edge must
  only be written when ``record.supersedes`` is non-null.

Uses a minimal store double that records the Cypher query + bound params it was called
with, mirroring ``tests/test_retrieval.py``'s store-double pattern — never a live Neo4j
connection.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from instrument.knowledge import Authority, KnowledgeRecord
from scripts import kb_worker


def _record(**overrides) -> KnowledgeRecord:
    """Build a canonical KnowledgeRecord fixture, overridable per field."""
    ts = datetime(2026, 8, 15, tzinfo=timezone.utc).isoformat()
    kwargs = dict(
        knowledge_id="kid_1",
        entity_id="eid_1",
        source_uri="story:abc123",
        source_type="story",
        logical_locator="abc123",
        repository_id="agentic-dynamics",
        branch="",
        worktree_id="",
        commit_sha="commit_1",
        content_hash="hash_1",
        extractor_version="story/v1",
        embedding_version="",
        authority=Authority.MEASURED,
        valid_from=ts,
        valid_to=None,
        observed_at=ts,
        indexed_at=ts,
        acl_scope="public",
        contains_sensitive_data=False,
        text="a story record",
        token_count=3,
        language="python",
        symbols=[],
        outcome_id="",
        test_executed_success=True,
        evidence_class="[M]",
        confidence=None,
        perturbation_strength=0.0,
        causes=None,
    )
    kwargs.update(overrides)
    return KnowledgeRecord(**kwargs)


# ── kb-registry-v1 ────────────────────────────────────────────────


class _FakeRedis:
    """A no-op Redis stand-in — the registry handler never touches Redis directly."""


def test_kb_registry_v1_handler_appends_jsonl_line(tmp_path, monkeypatch):
    monkeypatch.setattr(kb_worker, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    handler = kb_worker.build_handler("kb-registry-v1", _FakeRedis())

    record = _record()
    handler(record)

    lines = kb_worker.REGISTRY_INDEX_PATH.read_text().splitlines()
    assert len(lines) == 1
    line = json.loads(lines[0])
    assert line == {
        "knowledge_id": "kid_1",
        "entity_id": "eid_1",
        "source_type": "story",
        "logical_locator": record.logical_locator,
        "source_uri": record.source_uri,
        "lifecycle_state": "current",
        "observed_at": record.observed_at,
        "indexed_at": record.indexed_at,
        "supersedes": None,
        "causes": None,
    }


def test_kb_registry_v1_handler_appends_one_line_per_call(tmp_path, monkeypatch):
    monkeypatch.setattr(kb_worker, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    handler = kb_worker.build_handler("kb-registry-v1", _FakeRedis())

    handler(_record(knowledge_id="kid_1"))
    handler(_record(knowledge_id="kid_2"))

    lines = kb_worker.REGISTRY_INDEX_PATH.read_text().splitlines()
    assert len(lines) == 2
    assert [json.loads(l)["knowledge_id"] for l in lines] == ["kid_1", "kid_2"]


def test_kb_registry_v1_handler_creates_parent_directory(tmp_path, monkeypatch):
    nested = tmp_path / "nested" / "dir" / "registry_index.jsonl"
    monkeypatch.setattr(kb_worker, "REGISTRY_INDEX_PATH", nested)
    handler = kb_worker.build_handler("kb-registry-v1", _FakeRedis())

    handler(_record())
    assert nested.exists()


def test_kb_registry_v1_handler_carries_causes_for_actuation_records(tmp_path, monkeypatch):
    monkeypatch.setattr(kb_worker, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    handler = kb_worker.build_handler("kb-registry-v1", _FakeRedis())

    handler(_record(source_type="actuation", causes="obs_kid_1"))
    line = json.loads(kb_worker.REGISTRY_INDEX_PATH.read_text().splitlines()[0])
    assert line["causes"] == "obs_kid_1"
    assert line["source_type"] == "actuation"


# ── kb-neo4j-v1 (gap d) ────────────────────────────────────────────


class _FakeNeo4jClient:
    """Records the Cypher query + bound params it was called with — never a live driver."""

    instances: list["_FakeNeo4jClient"] = []

    def __init__(self, *args, **kwargs):
        self.calls: list[tuple[str, dict]] = []
        self.schema_created = False
        self.closed = False
        _FakeNeo4jClient.instances.append(self)

    def create_knowledge_schema(self) -> None:
        self.schema_created = True

    def _run(self, query: str, params: dict | None = None):
        self.calls.append((query, params or {}))

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _reset_fake_neo4j_instances():
    _FakeNeo4jClient.instances = []
    yield
    _FakeNeo4jClient.instances = []


def _patch_neo4j_client(monkeypatch):
    import instrument.graph as graph_module

    monkeypatch.setattr(graph_module, "Neo4jClient", _FakeNeo4jClient)


def test_kb_neo4j_v1_handler_sets_date_spine_fields(monkeypatch):
    _patch_neo4j_client(monkeypatch)
    handler = kb_worker.build_handler("kb-neo4j-v1", _FakeRedis())

    record = _record()
    handler(record)

    client = _FakeNeo4jClient.instances[0]
    assert client.schema_created is True
    assert client.closed is True
    assert len(client.calls) == 1
    _query, params = client.calls[0]

    # Gap (d): these five fields were silently dropped by the pre-round-2 SET clause.
    assert params["valid_from"] == record.valid_from
    assert params["observed_at"] == record.observed_at
    assert params["indexed_at"] == record.indexed_at
    assert params["supersedes"] is None
    assert params["causes"] is None

    # Pre-existing eleven properties remain unchanged.
    assert params["id"] == record.knowledge_id
    assert params["eid"] == record.entity_id
    assert params["stype"] == record.source_type


def test_kb_neo4j_v1_handler_carries_causes_for_actuation_records(monkeypatch):
    _patch_neo4j_client(monkeypatch)
    handler = kb_worker.build_handler("kb-neo4j-v1", _FakeRedis())

    record = _record(source_type="actuation", causes="obs_kid_1")
    handler(record)

    _query, params = _FakeNeo4jClient.instances[0].calls[0]
    assert params["causes"] == "obs_kid_1"


def test_kb_neo4j_v1_handler_writes_supersedes_edge_when_present(monkeypatch):
    _patch_neo4j_client(monkeypatch)
    handler = kb_worker.build_handler("kb-neo4j-v1", _FakeRedis())

    # `supersedes` is not (yet) a real KnowledgeRecord field in this codebase (see
    # kb_worker.py's comment) — the handler reads it via getattr with a None default, so
    # a caller can still exercise the "present" branch by monkeypatching it onto the
    # frozen dataclass instance via object.__setattr__ (bypassing frozen=True, test-only).
    record = _record()
    object.__setattr__(record, "supersedes", "kid_prev")

    handler(record)
    query, params = _FakeNeo4jClient.instances[0].calls[0]

    assert params["supersedes"] == "kid_prev"
    assert "SUPERSEDES" in query
    assert "FOREACH" in query


def test_kb_neo4j_v1_handler_supersedes_edge_foreach_is_present_but_conditional(monkeypatch):
    # When supersedes is None, the FOREACH clause is still part of the query text (Cypher
    # has no separate "conditional query"), but its CASE guard means the edge MERGE never
    # actually fires — this test documents that the query is unconditionally sent with a
    # None param rather than the handler branching in Python to omit the clause.
    _patch_neo4j_client(monkeypatch)
    handler = kb_worker.build_handler("kb-neo4j-v1", _FakeRedis())

    handler(_record())
    query, params = _FakeNeo4jClient.instances[0].calls[0]
    assert "FOREACH" in query
    assert params["supersedes"] is None


# ── kb-registry-v1 is a recognized group ─────────────────────────


def test_kb_registry_v1_is_in_the_dispatch_table():
    # build_handler must not raise "unknown consumer group" for kb-registry-v1.
    handler = kb_worker.build_handler("kb-registry-v1", _FakeRedis())
    assert callable(handler)
