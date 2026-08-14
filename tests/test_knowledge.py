"""Tests for the canonical knowledge identity + authority contract.

Covers the two sha256 identities, the ordered ``Authority`` enum, the frozen
``KnowledgeRecord`` / ``KnowledgeEvent`` dataclasses (pointer-only events), and
dict serialization round-trips.
"""

from dataclasses import FrozenInstanceError, fields

import pytest

from instrument.knowledge import (
    SCHEMA_VERSION,
    Authority,
    KnowledgeEvent,
    KnowledgeRecord,
    compute_content_hash,
    compute_entity_id,
    compute_knowledge_id,
)


def _record(**overrides) -> KnowledgeRecord:
    """Build a canonical KnowledgeRecord, overridable per field for focused tests."""
    entity_id = compute_entity_id("repo-1", "src/instrument/knowledge.py", "compute_entity_id")
    content_hash = compute_content_hash("def compute_entity_id(...): ...")
    kwargs = dict(
        knowledge_id=compute_knowledge_id(entity_id, "abc1234", content_hash, "extractor/v1"),
        entity_id=entity_id,
        source_uri="src/instrument/knowledge.py",
        source_type="code",
        logical_locator="compute_entity_id",
        repository_id="repo-1",
        branch="main",
        worktree_id="wt-1",
        commit_sha="abc1234",
        content_hash=content_hash,
        extractor_version="extractor/v1",
        embedding_version="bge-m3/v1",
        authority=Authority.SOURCE,
        valid_from="2026-08-15T00:00:00Z",
        valid_to=None,
        observed_at="2026-08-15T00:00:00Z",
        indexed_at="2026-08-15T00:00:01Z",
        acl_scope="public",
        contains_sensitive_data=False,
        text="def compute_entity_id(...): ...",
        token_count=7,
        language="python",
        symbols=["compute_entity_id"],
        outcome_id="",
        test_executed_success=None,
        evidence_class="[M]",
    )
    kwargs.update(overrides)
    return KnowledgeRecord(**kwargs)


def _event(**overrides) -> KnowledgeEvent:
    entity_id = compute_entity_id("repo-1", "src/instrument/knowledge.py", "compute_entity_id")
    content_hash = compute_content_hash("def compute_entity_id(...): ...")
    kwargs = dict(
        knowledge_id=compute_knowledge_id(entity_id, "abc1234", content_hash, "extractor/v1"),
        entity_id=entity_id,
        operation="upsert",
        source_uri="src/instrument/knowledge.py",
        source_revision="abc1234",
        content_hash=content_hash,
        occurred_at="2026-08-15T00:00:00Z",
        schema_version=SCHEMA_VERSION,
        event_id="",
    )
    kwargs.update(overrides)
    return KnowledgeEvent(**kwargs)


# ── Stable IDs ──────────────────────────────────────────────────


def test_entity_id_is_deterministic_across_call_sites():
    # The same three inputs yield the same identity no matter who computes it —
    # two independent "call sites" converge on one id.
    site_a = compute_entity_id("repo-1", "src/instrument/knowledge.py", "compute_entity_id")
    site_b = compute_entity_id("repo-1", "src/instrument/knowledge.py", "compute_entity_id")
    assert site_a == site_b
    assert len(site_a) == 64  # sha256 hex digest
    assert int(site_a, 16) > 0


def test_entity_id_is_sha256_of_its_components():
    import hashlib

    expected = hashlib.sha256(
        b"repo-1|src/instrument/knowledge.py|compute_entity_id"
    ).hexdigest()
    assert compute_entity_id("repo-1", "src/instrument/knowledge.py", "compute_entity_id") == expected


def test_knowledge_id_is_deterministic():
    entity_id = compute_entity_id("repo-1", "src/a.py", "f")
    k1 = compute_knowledge_id(entity_id, "rev-1", "hash-1", "extractor/v1")
    k2 = compute_knowledge_id(entity_id, "rev-1", "hash-1", "extractor/v1")
    assert k1 == k2
    assert len(k1) == 64


def test_knowledge_id_derives_from_entity_id():
    entity_id = compute_entity_id("repo-1", "src/a.py", "f")
    knowledge_id = compute_knowledge_id(entity_id, "rev-1", "hash-1", "extractor/v1")
    assert knowledge_id != entity_id
    # Same entity + different revision still yields a 64-char sha256 id.
    assert len(knowledge_id) == 64


def test_entity_id_stable_when_only_content_changes():
    # A modified symbol keeps the same entity_id (logical identity) but gets a new
    # knowledge_id (immutable version) because the content hash changes.
    entity_id = compute_entity_id("repo-1", "src/a.py", "f")
    knowledge_v1 = compute_knowledge_id(entity_id, "rev-1", compute_content_hash("v1"), "extractor/v1")
    knowledge_v2 = compute_knowledge_id(entity_id, "rev-2", compute_content_hash("v2"), "extractor/v1")
    assert knowledge_v1 != knowledge_v2
    # And the entity_id did not change because its three components did not.
    assert compute_entity_id("repo-1", "src/a.py", "f") == entity_id


# ── Version change → new knowledge_id ───────────────────────────


def test_extractor_version_change_produces_new_knowledge_id():
    entity_id = compute_entity_id("repo-1", "src/a.py", "f")
    content_hash = compute_content_hash("x")
    k_v1 = compute_knowledge_id(entity_id, "rev-1", content_hash, "extractor/v1")
    k_v2 = compute_knowledge_id(entity_id, "rev-1", content_hash, "extractor/v2")
    assert k_v1 != k_v2


def test_source_revision_change_produces_new_knowledge_id():
    entity_id = compute_entity_id("repo-1", "src/a.py", "f")
    content_hash = compute_content_hash("x")
    k_v1 = compute_knowledge_id(entity_id, "rev-1", content_hash, "extractor/v1")
    k_v2 = compute_knowledge_id(entity_id, "rev-2", content_hash, "extractor/v1")
    assert k_v1 != k_v2


def test_content_hash_change_produces_new_knowledge_id():
    entity_id = compute_entity_id("repo-1", "src/a.py", "f")
    k_v1 = compute_knowledge_id(entity_id, "rev-1", compute_content_hash("a"), "extractor/v1")
    k_v2 = compute_knowledge_id(entity_id, "rev-1", compute_content_hash("b"), "extractor/v1")
    assert k_v1 != k_v2


# ── Authority ordering ──────────────────────────────────────────


def test_authority_ordering():
    assert Authority.POLICY > Authority.SOURCE > Authority.MEASURED > Authority.DERIVED > Authority.ADVISORY


def test_authority_sorted_ascending():
    assert sorted(Authority, key=lambda a: a) == [
        Authority.ADVISORY,
        Authority.DERIVED,
        Authority.MEASURED,
        Authority.SOURCE,
        Authority.POLICY,
    ]


def test_policy_is_highest_authority():
    # Pinned policy outranks every other class, including current source.
    for authority in (Authority.SOURCE, Authority.MEASURED, Authority.DERIVED, Authority.ADVISORY):
        assert Authority.POLICY > authority
    assert Authority.ADVISORY < Authority.SOURCE


def test_advisory_cannot_override_source():
    # An advisory item can never override current source.
    assert Authority.ADVISORY < Authority.SOURCE


# ── Event has no body ───────────────────────────────────────────


def test_event_has_no_body_field():
    field_names = {f.name for f in fields(KnowledgeEvent)}
    assert "text" not in field_names
    assert "body" not in field_names
    assert "content" not in field_names


def test_event_carries_only_pointers_and_identity():
    field_names = {f.name for f in fields(KnowledgeEvent)}
    # Identity + pointer/hash/version fields, plus a tracing id.
    assert field_names == {
        "knowledge_id",
        "entity_id",
        "operation",
        "source_uri",
        "source_revision",
        "content_hash",
        "occurred_at",
        "schema_version",
        "event_id",
    }


# ── Serialization round-trip ────────────────────────────────────


def test_record_round_trip():
    record = _record()
    restored = KnowledgeRecord.from_dict(record.to_dict())
    assert restored == record
    assert restored.authority is Authority.SOURCE


def test_record_round_trip_preserves_optionals_and_enums():
    record = _record(
        authority=Authority.MEASURED,
        valid_to="2026-09-01T00:00:00Z",
        test_executed_success=True,
        symbols=["a", "b"],
        contains_sensitive_data=True,
        evidence_class="[C]",
    )
    restored = KnowledgeRecord.from_dict(record.to_dict())
    assert restored == record
    assert restored.authority is Authority.MEASURED
    assert restored.valid_to == "2026-09-01T00:00:00Z"
    assert restored.test_executed_success is True
    assert restored.symbols == ["a", "b"]


def test_record_from_dict_accepts_lowercase_authority():
    d = _record().to_dict()
    d["authority"] = "source"
    assert KnowledgeRecord.from_dict(d).authority is Authority.SOURCE


def test_event_round_trip():
    event = _event(event_id="evt-1", operation="supersede")
    restored = KnowledgeEvent.from_dict(event.to_dict())
    assert restored == event
    assert restored.operation == "supersede"
    assert restored.event_id == "evt-1"


def test_record_serialization_encodes_authority_as_name():
    d = _record(authority=Authority.POLICY).to_dict()
    assert d["authority"] == "POLICY"


# ── Frozen contract ─────────────────────────────────────────────


def test_record_is_frozen():
    record = _record()
    with pytest.raises(FrozenInstanceError):
        record.text = "mutated"  # type: ignore[misc]


def test_event_is_frozen():
    event = _event()
    with pytest.raises(FrozenInstanceError):
        event.source_uri = "other.py"  # type: ignore[misc]


def test_record_and_event_share_knowledge_id():
    record = _record()
    event = _event()
    assert record.knowledge_id == event.knowledge_id
    assert record.entity_id == event.entity_id
