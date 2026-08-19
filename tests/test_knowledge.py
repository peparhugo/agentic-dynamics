"""Tests for the canonical knowledge identity + authority contract.

Covers the two sha256 identities, the ordered ``Authority`` enum, the frozen
``KnowledgeRecord`` / ``KnowledgeEvent`` dataclasses (pointer-only events), and
dict serialization round-trips.
"""

from dataclasses import FrozenInstanceError, fields

import pytest

from instrument.knowledge import (
    ACTUATION_TYPES,
    OBSERVATION_TYPES,
    SCHEMA_VERSION,
    SOURCE_TYPES,
    Authority,
    KnowledgeEvent,
    KnowledgeRecord,
    SourceTypeSpec,
    compute_content_hash,
    compute_entity_id,
    compute_knowledge_id,
    message_family,
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
        assert authority < Authority.POLICY
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
    # Identity + pointer/hash/version fields, plus a tracing id, (round 2) `causes`,
    # (round 1) `reason`, and (record-fidelity) `observed_at`.
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
        "causes",
        "reason",
        "observed_at",
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


# ── `causes` (round 2 addition) ─────────────────────────────────


def test_record_causes_defaults_to_none():
    assert _record().causes is None


def test_event_causes_defaults_to_empty_string():
    assert _event().causes == ""


def test_record_causes_round_trips_through_to_dict():
    record = _record(causes="some-observation-knowledge-id")
    restored = KnowledgeRecord.from_dict(record.to_dict())
    assert restored == record
    assert restored.causes == "some-observation-knowledge-id"


def test_event_causes_round_trips_through_to_dict():
    event = _event(causes="some-observation-knowledge-id")
    restored = KnowledgeEvent.from_dict(event.to_dict())
    assert restored == event
    assert restored.causes == "some-observation-knowledge-id"


def test_record_from_dict_accepts_fixture_with_no_causes_key():
    # A pre-existing artifact (any of the 1,913 already on disk) has no `causes` key at
    # all. from_dict() must resolve the missing key to None, never raise a TypeError.
    d = _record().to_dict()
    del d["causes"]
    restored = KnowledgeRecord.from_dict(d)
    assert restored.causes is None


def test_event_from_dict_accepts_fixture_with_no_causes_key():
    d = _event().to_dict()
    del d["causes"]
    restored = KnowledgeEvent.from_dict(d)
    assert restored.causes == ""


# ── message_family (round 2 addition) ───────────────────────────


def test_message_family_classifies_actuation_vs_observation():
    assert message_family("actuation") == "actuation"
    for source_type in OBSERVATION_TYPES:
        assert message_family(source_type) == "observation"


def test_message_family_defaults_unknown_source_type_to_observation():
    # A closed allowlist, not a denylist: a made-up source_type must classify as
    # "observation" (the safe default), not error and not silently become "actuation".
    assert message_family("some_future_source_type_nobody_registered") == "observation"
    assert "some_future_source_type_nobody_registered" not in ACTUATION_TYPES


def test_actuation_types_is_a_single_member_allowlist():
    # Guards the design's "closed by default" invariant directly: ACTUATION_TYPES must
    # never silently grow beyond the one family this round introduces.
    assert frozenset({"actuation"}) == ACTUATION_TYPES


# ── SOURCE_TYPES registry (R2 — the single vocabulary owner) ───


def test_source_types_is_the_single_vocabulary_owner():
    # All thirteen source types — the four round-1 producer types, the round-2 registry
    # types, and the spec-lifecycle type — are registered here. This is what closes the
    # pre-R2 split where OBSERVATION_TYPES silently omitted finding/code/report/policy.
    assert set(SOURCE_TYPES) == {
        "finding", "code", "report", "policy",
        "story", "review", "ledger_job", "ledger_attempt",
        "observation", "flag", "meta_session", "actuation",
        "spec",
    }


def test_spec_source_type_is_a_policy_authority_observation():
    # A spec record states what a spec IS and where its lifecycle stands — pinned,
    # authored repository policy, and never an instruction to act. Both halves matter:
    # POLICY/[P] mirrors the `policy` type's trust tier, and the observation family keeps
    # it structurally outside the actuation gate.
    assert SOURCE_TYPES["spec"] == SourceTypeSpec("observation", Authority.POLICY, "[P]")
    assert message_family("spec") == "observation"
    assert "spec" in OBSERVATION_TYPES
    assert "spec" not in ACTUATION_TYPES


def test_observation_and_actuation_types_are_derived_from_source_types():
    # The two frozensets are pure projections of SOURCE_TYPES' message_family column.
    assert frozenset(
        n for n, s in SOURCE_TYPES.items() if s.message_family == "observation"
    ) == OBSERVATION_TYPES
    assert frozenset(
        n for n, s in SOURCE_TYPES.items() if s.message_family == "actuation"
    ) == ACTUATION_TYPES


def test_source_type_spec_carries_nominal_provenance():
    assert SOURCE_TYPES["actuation"] == SourceTypeSpec("actuation", Authority.POLICY, "[P]")
    assert SOURCE_TYPES["code"] == SourceTypeSpec("observation", Authority.SOURCE, "[C]")
    assert SOURCE_TYPES["policy"] == SourceTypeSpec("observation", Authority.POLICY, "[P]")
    assert SOURCE_TYPES["story"].authority is Authority.MEASURED
    assert SOURCE_TYPES["review"].evidence_class == "[H]"


def test_message_family_keys_off_source_types_for_registered_types():
    # Registered round-1 types now classify via the table, not by the "observation" default.
    for name, spec in SOURCE_TYPES.items():
        assert message_family(name) == spec.message_family


def test_source_type_spec_is_frozen():
    spec = SOURCE_TYPES["code"]
    with pytest.raises(FrozenInstanceError):
        spec.message_family = "actuation"  # type: ignore[misc]

# ── `subject_id` / `subject_status` (record-fidelity addition) ──


def test_record_subject_fields_default_to_empty():
    record = _record()
    assert record.subject_id == ""
    assert record.subject_status == ""


def test_record_subject_fields_round_trip_through_to_dict():
    record = _record(subject_id="session_a", subject_status="healthy")
    restored = KnowledgeRecord.from_dict(record.to_dict())
    assert restored == record
    assert restored.subject_id == "session_a"
    assert restored.subject_status == "healthy"


def test_record_from_dict_accepts_fixture_with_no_subject_keys():
    # A pre-existing artifact has no `subject_id`/`subject_status` keys. from_dict() must
    # resolve the missing keys to "" (the trailing-default pattern), never a TypeError.
    d = _record().to_dict()
    del d["subject_id"]
    del d["subject_status"]
    restored = KnowledgeRecord.from_dict(d)
    assert restored.subject_id == ""
    assert restored.subject_status == ""


# ── `observed_at` on the event (record-fidelity addition) ───────


def test_event_observed_at_defaults_to_empty():
    assert _event().observed_at == ""


def test_event_observed_at_round_trips_through_to_dict():
    event = _event(observed_at="2026-08-14T09:30:00+00:00")
    restored = KnowledgeEvent.from_dict(event.to_dict())
    assert restored == event
    assert restored.observed_at == "2026-08-14T09:30:00+00:00"


def test_event_from_dict_accepts_fixture_with_no_observed_at_key():
    d = _event().to_dict()
    del d["observed_at"]
    restored = KnowledgeEvent.from_dict(d)
    assert restored.observed_at == ""
