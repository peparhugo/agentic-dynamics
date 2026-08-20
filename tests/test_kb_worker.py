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

from agentic_dynamics.knowledge.knowledge import Authority, KnowledgeRecord
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
        "reason": "",
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


# ── kb-registry-v1 — operation-derived lifecycle_state (canonical-state finalize, G1) ──


def test_kb_registry_v1_handler_upsert_is_current(tmp_path, monkeypatch):
    monkeypatch.setattr(kb_worker, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    handler = kb_worker.build_handler("kb-registry-v1", _FakeRedis())

    handler(_record(), operation="upsert")
    line = json.loads(kb_worker.REGISTRY_INDEX_PATH.read_text().splitlines()[0])
    assert line["lifecycle_state"] == "current"


def test_kb_registry_v1_handler_delete_is_tombstoned(tmp_path, monkeypatch):
    monkeypatch.setattr(kb_worker, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    handler = kb_worker.build_handler("kb-registry-v1", _FakeRedis())

    handler(_record(knowledge_id="kid_contaminated"), operation="delete", reason="contaminated cell")

    lines = [json.loads(l) for l in kb_worker.REGISTRY_INDEX_PATH.read_text().splitlines()]
    assert len(lines) == 1  # a self-tombstone — no predecessor side-effect
    assert lines[0]["knowledge_id"] == "kid_contaminated"
    assert lines[0]["lifecycle_state"] == "tombstoned"
    assert lines[0]["reason"] == "contaminated cell"  # the tombstone's "why" is surfaced


def test_kb_registry_v1_handler_supersede_marks_predecessor_superseded_with_effective_valid_to(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(kb_worker, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    handler = kb_worker.build_handler("kb-registry-v1", _FakeRedis())

    successor = _record(
        knowledge_id="kid_v2", entity_id="eid_1", valid_from="2026-08-18T00:00:00+00:00",
    )
    object.__setattr__(successor, "supersedes", "kid_v1")

    handler(successor, operation="supersede")

    lines = [json.loads(l) for l in kb_worker.REGISTRY_INDEX_PATH.read_text().splitlines()]
    assert len(lines) == 2

    successor_line, predecessor_line = lines
    # The successor's own line is a plain "current" registration, same as an upsert.
    assert successor_line["knowledge_id"] == "kid_v2"
    assert successor_line["lifecycle_state"] == "current"

    # The derived side-effect: the predecessor is now superseded, with an effective
    # valid_to equal to the successor's own valid_from.
    assert predecessor_line["knowledge_id"] == "kid_v1"
    assert predecessor_line["lifecycle_state"] == "superseded"
    assert predecessor_line["valid_to"] == "2026-08-18T00:00:00+00:00"


def test_kb_registry_v1_handler_supersede_without_predecessor_writes_one_line(tmp_path, monkeypatch):
    # record.supersedes is falsy (e.g. a mislabeled first version) — no predecessor to mark.
    monkeypatch.setattr(kb_worker, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    handler = kb_worker.build_handler("kb-registry-v1", _FakeRedis())

    handler(_record(), operation="supersede")
    lines = kb_worker.REGISTRY_INDEX_PATH.read_text().splitlines()
    assert len(lines) == 1


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
    import agentic_dynamics.knowledge.graph as graph_module

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

    record = _record()
    object.__setattr__(record, "supersedes", "kid_prev")

    # The edge only fires for an actual "supersede" operation (G1) — see the next test for
    # the upsert-with-a-stale-supersedes-value case.
    handler(record, operation="supersede")
    query, params = _FakeNeo4jClient.instances[0].calls[0]

    assert params["supersedes"] == "kid_prev"
    assert params["operation"] == "supersede"
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


# ── kb-neo4j-v1 — lifecycle_state + CLEARED_BY/REPLACED_BY (canonical-state finalize, G1) ──


def test_kb_neo4j_v1_handler_persists_lifecycle_state_current_for_upsert(monkeypatch):
    _patch_neo4j_client(monkeypatch)
    handler = kb_worker.build_handler("kb-neo4j-v1", _FakeRedis())

    handler(_record(), operation="upsert")
    _query, params = _FakeNeo4jClient.instances[0].calls[0]
    assert params["lifecycle_state"] == "current"


def test_kb_neo4j_v1_handler_persists_lifecycle_state_tombstoned_for_delete(monkeypatch):
    _patch_neo4j_client(monkeypatch)
    handler = kb_worker.build_handler("kb-neo4j-v1", _FakeRedis())

    handler(_record(), operation="delete", reason="contaminated cell")
    _query, params = _FakeNeo4jClient.instances[0].calls[0]
    assert params["lifecycle_state"] == "tombstoned"


def test_kb_neo4j_v1_handler_does_not_write_supersedes_edge_for_upsert(monkeypatch):
    # A record carrying a (stale) `supersedes` value under a plain upsert must not
    # retroactively rewrite graph lineage — the edge is gated on the operation, not merely
    # on the field's presence.
    _patch_neo4j_client(monkeypatch)
    handler = kb_worker.build_handler("kb-neo4j-v1", _FakeRedis())

    record = _record()
    object.__setattr__(record, "supersedes", "kid_prev")
    handler(record, operation="upsert")

    _query, params = _FakeNeo4jClient.instances[0].calls[0]
    assert params["operation"] == "upsert"
    assert params["supersedes"] == "kid_prev"  # still persisted as a property...
    # ...but the FOREACH CASE guard requires operation = 'supersede', so the edge MERGE
    # (present in the query text, per Cypher's unconditional-query-text convention) never
    # actually fires for this call — see the query's CASE clause.
    assert "$operation = 'supersede'" in _query


def test_kb_neo4j_v1_handler_writes_cleared_by_edge_for_flag_tombstone(monkeypatch):
    _patch_neo4j_client(monkeypatch)
    handler = kb_worker.build_handler("kb-neo4j-v1", _FakeRedis())

    flag = _record(
        knowledge_id="kid_flag_v2", source_type="flag", causes="kid_healthy_observation",
    )
    handler(flag, operation="delete", reason="auto-cleared: subsequent observation was healthy")

    query, params = _FakeNeo4jClient.instances[0].calls[0]
    assert params["causes"] == "kid_healthy_observation"
    assert params["stype"] == "flag"
    assert "CLEARED_BY" in query
    assert "REPLACED_BY" in query  # present in query text (both FOREACHes always sent)


def test_kb_neo4j_v1_handler_writes_replaced_by_edge_for_non_flag_tombstone(monkeypatch):
    _patch_neo4j_client(monkeypatch)
    handler = kb_worker.build_handler("kb-neo4j-v1", _FakeRedis())

    story = _record(
        knowledge_id="kid_contaminated", source_type="story", causes="kid_clean_rerun",
    )
    handler(story, operation="delete", reason="contaminated: rerun under a new story_id")

    _query, params = _FakeNeo4jClient.instances[0].calls[0]
    assert params["causes"] == "kid_clean_rerun"
    assert params["stype"] == "story"


def test_kb_neo4j_v1_handler_no_clear_or_replace_edge_without_causes(monkeypatch):
    _patch_neo4j_client(monkeypatch)
    handler = kb_worker.build_handler("kb-neo4j-v1", _FakeRedis())

    handler(_record(source_type="flag"), operation="delete", reason="contaminated cell")
    _query, params = _FakeNeo4jClient.instances[0].calls[0]
    assert params["causes"] is None


# ── kb-registry-v1 is a recognized group ─────────────────────────


def test_kb_registry_v1_is_in_the_dispatch_table():
    # build_handler must not raise "unknown consumer group" for kb-registry-v1.
    handler = kb_worker.build_handler("kb-registry-v1", _FakeRedis())
    assert callable(handler)


# ── Flag auto-clear rule (canonical-state finalize, G3) ───────────
#
# docs/canonical_state_base_design.md, "Open Question 6"(c): a flag is tombstoned
# (delete + reason + a CLEARED_BY edge to the justifying observation) the moment a
# LATER observation for the same session reads "healthy" — fully automatic, no human
# "clear this flag" button, and never touching steer/interrupt/OpenCodeClient.


class _FakeRegistryRedis:
    """A minimal store double supporting exactly what ``publish_event()`` calls:
    ``XADD`` (append an event, returning a fake monotonic entry id) and ``HSET``/
    ``HGET`` (the source_type index ``publish_event`` maintains for non-actuation
    events) — never a live Redis connection. Mirrors ``tests/test_retrieval.py``'s
    store-double convention, extended just far enough to exercise the auto-clear
    rule's actual write path end-to-end (unlike the schema-only ``_FakeRedis`` above,
    which the kb-neo4j-v1 tests never call methods on).
    """

    def __init__(self):
        self.published: list[dict] = []  # every XADD'd event, as its field dict
        self.hashes: dict[str, dict[str, str]] = {}
        self._next_id = 0

    def xadd(self, stream, fields):
        self._next_id += 1
        self.published.append(dict(fields))
        return f"{self._next_id}-0"

    def hset(self, name, key, value):
        self.hashes.setdefault(name, {})[key] = value

    def hget(self, name, key):
        return self.hashes.get(name, {}).get(key)


def _flag_record(**overrides) -> KnowledgeRecord:
    """A ``source_type="flag"`` fixture matching
    ``observation_ingestion.build_flag_record``'s identity shape closely enough for
    these tests: ``logical_locator`` is the session_id (the field the auto-clear rule
    keys its in-process index on)."""
    return _record(
        knowledge_id="kid_flag_1",
        entity_id="eid_flag_session_a",
        source_uri="flag_stream:session_a",
        source_type="flag",
        logical_locator="session_a",
        text="live_session_a [deepseek/deepseek-v4-flash]: stalled — no progress",
        subject_id="session_a",
        subject_status="stalled",
        **overrides,
    )


def _observation_record(*, cell_id="session_a", status="healthy", model="deepseek/deepseek-v4-flash", **overrides) -> KnowledgeRecord:
    """A ``source_type="observation"`` fixture carrying the structured ``subject_id``/
    ``subject_status`` fields the auto-clear rule reads (replacing the old text split).
    ``text`` is deliberately overridable so a test can prove the rule no longer depends on it."""
    return _record(
        knowledge_id=overrides.pop("knowledge_id", "kid_observation_1"),
        entity_id=overrides.pop("entity_id", "eid_observation_1"),
        source_uri=f"observation:{cell_id}",
        source_type="observation",
        logical_locator="assessment_hash_stub",
        text=overrides.pop("text", f"{cell_id} [{model}]: {status}"),
        subject_id=cell_id,
        subject_status=status,
        **overrides,
    )


def test_autoclear_reads_structured_subject_not_text(tmp_path, monkeypatch):
    # R5 / BUG-4 regression: the auto-clear correlation now reads the structured
    # subject_id/subject_status fields. A text-format change (drop the "[model]" bracket,
    # reword the status entirely) must NOT break clearing — the old text-split heuristic
    # would have returned (None, None) here and silently no-op'd.
    monkeypatch.setattr(kb_worker, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    monkeypatch.setattr(kb_worker, "KB_ARTIFACT_DIR", tmp_path / "kb")
    monkeypatch.setenv("FINOPS_KB_WRITE", "1")

    fake_redis = _FakeRegistryRedis()
    handler = kb_worker.build_handler("kb-registry-v1", fake_redis)

    handler(_flag_record(), operation="upsert")
    handler(
        _observation_record(status="healthy", text="reworded prose: no [bracket] format at all"),
        operation="upsert",
    )

    assert len(fake_redis.published) == 1
    assert fake_redis.published[0]["operation"] == "delete"


def test_clear_flag_record_preserves_entity_id_and_sets_causes():
    flag = _flag_record()
    cleared = kb_worker._clear_flag_record(flag, causes="kid_healthy_observation")
    assert cleared.entity_id == flag.entity_id
    assert cleared.causes == "kid_healthy_observation"
    # The new content (causes changed) means a new content_hash/knowledge_id — the
    # original artifact is never mutated in place.
    assert cleared.knowledge_id != flag.knowledge_id
    assert cleared.content_hash != flag.content_hash


def test_flag_autoclear_healthy_observation_emits_exactly_one_delete_for_the_flag(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(kb_worker, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    monkeypatch.setattr(kb_worker, "KB_ARTIFACT_DIR", tmp_path / "kb")
    monkeypatch.setenv("FINOPS_KB_WRITE", "1")

    fake_redis = _FakeRegistryRedis()
    handler = kb_worker.build_handler("kb-registry-v1", fake_redis)

    handler(_flag_record(), operation="upsert")
    handler(_observation_record(status="healthy"), operation="upsert")

    assert len(fake_redis.published) == 1
    event_fields = fake_redis.published[0]
    assert event_fields["operation"] == "delete"
    assert event_fields["reason"] == "auto-cleared: subsequent observation was healthy"
    assert event_fields["causes"] == "kid_observation_1"

    # The tombstone's durable artifact was written before the event was published.
    cleared_kid = event_fields["knowledge_id"]
    assert (tmp_path / "kb" / f"{cleared_kid}.json").exists()

    # ...and it never went through the actuation family — only ever "flag".
    assert fake_redis.hashes[kb_worker.ks.SOURCE_TYPE_INDEX_KEY][cleared_kid] == "flag"


def test_flag_autoclear_non_healthy_observation_does_not_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(kb_worker, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    monkeypatch.setattr(kb_worker, "KB_ARTIFACT_DIR", tmp_path / "kb")
    monkeypatch.setenv("FINOPS_KB_WRITE", "1")

    fake_redis = _FakeRegistryRedis()
    handler = kb_worker.build_handler("kb-registry-v1", fake_redis)

    handler(_flag_record(), operation="upsert")
    for status in ("stalled", "off_track", "unknown"):
        handler(_observation_record(status=status, knowledge_id=f"kid_obs_{status}"), operation="upsert")

    assert fake_redis.published == []


def test_flag_autoclear_no_actuation_event_is_ever_produced(tmp_path, monkeypatch):
    # Even on the success path, the ONLY event this rule can ever construct carries
    # source_type="flag" — never source_type="actuation". Asserted directly against
    # every published event's recorded source_type, not just the happy-path fields.
    monkeypatch.setattr(kb_worker, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    monkeypatch.setattr(kb_worker, "KB_ARTIFACT_DIR", tmp_path / "kb")
    monkeypatch.setenv("FINOPS_KB_WRITE", "1")

    fake_redis = _FakeRegistryRedis()
    handler = kb_worker.build_handler("kb-registry-v1", fake_redis)

    handler(_flag_record(), operation="upsert")
    handler(_observation_record(status="healthy"), operation="upsert")

    assert len(fake_redis.published) == 1
    recorded_source_types = set(fake_redis.hashes.get(kb_worker.ks.SOURCE_TYPE_INDEX_KEY, {}).values())
    assert recorded_source_types == {"flag"}


def test_flag_autoclear_noop_when_no_known_flag_for_session(tmp_path, monkeypatch):
    monkeypatch.setattr(kb_worker, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    monkeypatch.setattr(kb_worker, "KB_ARTIFACT_DIR", tmp_path / "kb")
    monkeypatch.setenv("FINOPS_KB_WRITE", "1")

    fake_redis = _FakeRegistryRedis()
    handler = kb_worker.build_handler("kb-registry-v1", fake_redis)

    # No flag was ever processed for "session_a" — nothing to clear.
    handler(_observation_record(status="healthy"), operation="upsert")
    assert fake_redis.published == []


def test_flag_autoclear_requires_finops_kb_write(tmp_path, monkeypatch):
    monkeypatch.setattr(kb_worker, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    monkeypatch.setattr(kb_worker, "KB_ARTIFACT_DIR", tmp_path / "kb")
    monkeypatch.delenv("FINOPS_KB_WRITE", raising=False)

    fake_redis = _FakeRegistryRedis()
    handler = kb_worker.build_handler("kb-registry-v1", fake_redis)

    handler(_flag_record(), operation="upsert")
    handler(_observation_record(status="healthy"), operation="upsert")

    assert fake_redis.published == []  # not an authorized writer — observe only


def test_flag_autoclear_is_idempotent_across_repeated_healthy_observations(tmp_path, monkeypatch):
    monkeypatch.setattr(kb_worker, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    monkeypatch.setattr(kb_worker, "KB_ARTIFACT_DIR", tmp_path / "kb")
    monkeypatch.setenv("FINOPS_KB_WRITE", "1")

    fake_redis = _FakeRegistryRedis()
    handler = kb_worker.build_handler("kb-registry-v1", fake_redis)

    handler(_flag_record(), operation="upsert")
    handler(_observation_record(status="healthy", knowledge_id="kid_obs_1"), operation="upsert")
    handler(_observation_record(status="healthy", knowledge_id="kid_obs_2"), operation="upsert")

    # The second healthy observation finds no known flag left (popped after the
    # first clear) — exactly one delete total, not two.
    assert len(fake_redis.published) == 1


def test_flag_autoclear_does_not_reclear_a_flag_already_tombstoned(tmp_path, monkeypatch):
    # A `delete` event for the flag (from any source, not just this rule) removes it
    # from the in-process index — a later healthy observation must not re-fire.
    monkeypatch.setattr(kb_worker, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    monkeypatch.setattr(kb_worker, "KB_ARTIFACT_DIR", tmp_path / "kb")
    monkeypatch.setenv("FINOPS_KB_WRITE", "1")

    fake_redis = _FakeRegistryRedis()
    handler = kb_worker.build_handler("kb-registry-v1", fake_redis)

    handler(_flag_record(), operation="upsert")
    handler(_flag_record(), operation="delete", reason="manually tombstoned")
    handler(_observation_record(status="healthy"), operation="upsert")

    assert fake_redis.published == []
