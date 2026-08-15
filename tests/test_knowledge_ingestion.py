"""Tests for the producer-side measured-finding derivation (knowledge_ingestion).

Covers the extractor contract constants, the identity derivation (ids stable across call
sites, content hash recomputable from text, extractor-version bump → new knowledge_id), the
``MEASURED`` authority / ``[M]`` evidence class, that confidence/perturbation_strength/
test_executed_success are carried through, that the event is pointer-only, and the batch
``derive_records`` filtering.
"""

from dataclasses import fields

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
from instrument.knowledge_ingestion import (
    ACL_SCOPE,
    EXTRACTOR_VERSION,
    REPOSITORY_ID,
    RESULT_VERSION,
    SOURCE_TYPE,
    SOURCE_URI,
    build_record,
    derive_records,
    record_to_event,
)

MODEL = "deepseek/deepseek-v4-pro"
OPERATOR = "perturbed"


def _entry(**overrides) -> dict:
    """A minimal valid results entry, overridable per field for focused tests."""
    entry = {
        "worktree_name": "exp_05ngi4l9",
        "run_id": "exp_05ngi4l9",
        "model": MODEL,
        "operator": OPERATOR,
        "perturbation_class": "semantic",
        "strategy": "exploratory",
        "correctness": 0.8,
        "cost": 0.033537746,
        "escape": 0.7486509085783121,
        "flail": 0.62,
        "narration_failure": False,
        "test_executed_success": None,
        "confidence": None,
        "perturbation_strength": None,
        "outcome_id": "",
    }
    entry.update(overrides)
    return entry


# ── Extractor contract constants ────────────────────────────────


def test_extractor_version_is_explicit_and_stable():
    assert EXTRACTOR_VERSION == "measured-finding/v1"
    # The source is a durable locator; the repo id a stable component of entity_id.
    assert SOURCE_URI == "file://experiments/results/_results_summary.json"
    assert SOURCE_TYPE == "finding"


# ── Identity derivation ─────────────────────────────────────────


def test_record_authority_measured_and_evidence_class_m():
    record = build_record(_entry())
    assert record.authority is Authority.MEASURED
    assert record.evidence_class == "[M]"


def test_ids_stable_across_call_sites():
    # Two independent derivations of the same entry converge on one identity pair.
    a = build_record(_entry())
    b = build_record(_entry())
    assert a.entity_id == b.entity_id
    assert a.knowledge_id == b.knowledge_id
    # And they are real sha256 digests.
    assert len(a.entity_id) == 64
    assert len(a.knowledge_id) == 64


def test_entity_id_uses_repository_source_and_locator():
    record = build_record(_entry(worktree_name="exp_abc", run_id="exp_abc"))
    expected = compute_entity_id(REPOSITORY_ID, SOURCE_URI, "exp_abc")
    assert record.entity_id == expected


def test_content_hash_recomputes_from_text():
    record = build_record(_entry())
    assert record.content_hash == compute_content_hash(record.text)


def test_knowledge_id_folds_revision_hash_and_extractor():
    record = build_record(_entry())
    expected = compute_knowledge_id(
        record.entity_id,
        record.commit_sha,  # commit_sha stores the source_revision
        record.content_hash,
        EXTRACTOR_VERSION,
    )
    assert record.knowledge_id == expected


def test_extractor_version_bump_changes_knowledge_id(monkeypatch):
    entry = _entry()
    record_v1 = build_record(entry)
    monkeypatch.setattr("instrument.knowledge_ingestion.EXTRACTOR_VERSION", "measured-finding/v2")
    record_v2 = build_record(entry)
    # A new extractor generation yields a new knowledge_id ...
    assert record_v2.knowledge_id != record_v1.knowledge_id
    # ... while the logical identity stays stable.
    assert record_v2.entity_id == record_v1.entity_id
    assert record_v2.extractor_version == "measured-finding/v2"


def test_source_revision_falls_back_to_result_version_when_no_commit():
    record = build_record(_entry())  # no git_sha/commit/commit_sha
    assert record.commit_sha == RESULT_VERSION


def test_source_revision_uses_commit_when_stamped():
    record = build_record(_entry(git_sha="abc1234"))
    assert record.commit_sha == "abc1234"
    # The knowledge_id must fold the commit, not the fallback version.
    assert compute_knowledge_id(
        record.entity_id, "abc1234", record.content_hash, EXTRACTOR_VERSION
    ) == record.knowledge_id


# ── Ledger signals carried through ──────────────────────────────


def test_confidence_perturbation_strength_carried_through_text():
    record = build_record(_entry(confidence=0.82, perturbation_strength=0.5))
    # confidence [H] and perturbation_strength [M] are carried through the rendered finding.
    assert "confidence 0.82" in record.text
    assert "perturb_strength 0.50" in record.text


def test_confidence_absent_renders_em_dash_not_zero():
    record = build_record(_entry(confidence=None))
    assert "confidence —" in record.text
    assert "confidence 0.00" not in record.text


def test_test_executed_success_carried_through():
    record_true = build_record(_entry(test_executed_success=True))
    assert record_true.test_executed_success is True
    assert "tests pass" in record_true.text

    record_false = build_record(_entry(test_executed_success=False))
    assert record_false.test_executed_success is False
    assert "tests FAIL (unverified)" in record_false.text

    record_none = build_record(_entry(test_executed_success=None))
    assert record_none.test_executed_success is None


def test_outcome_id_carried_through():
    record = build_record(_entry(outcome_id="outcome-42"))
    assert record.outcome_id == "outcome-42"


# ── Record metadata consistency ─────────────────────────────────


def test_record_text_is_evidence_card_oneliner():
    record = build_record(_entry())
    assert record.text.startswith(f"{MODEL} under {OPERATOR} (class semantic) -> correctness")
    assert record.token_count == max(1, len(record.text.split()))
    assert record.acl_scope == ACL_SCOPE
    assert record.source_uri == SOURCE_URI
    assert record.repository_id == REPOSITORY_ID
    assert record.logical_locator == "exp_05ngi4l9"
    assert record.valid_to is None
    assert record.valid_from and record.observed_at and record.indexed_at


def test_record_round_trip_preserves_measured_fields():
    record = build_record(_entry(test_executed_success=True, outcome_id="o1"))
    restored = KnowledgeRecord.from_dict(record.to_dict())
    assert restored == record
    assert restored.authority is Authority.MEASURED
    assert restored.test_executed_success is True


# ── Event is pointer-only ───────────────────────────────────────


def test_event_has_no_body():
    record = build_record(_entry())
    event = record_to_event(record)
    assert not hasattr(event, "text")
    assert not hasattr(event, "body")
    assert "text" not in fields(KnowledgeEvent)
    assert "body" not in fields(KnowledgeEvent)


def test_event_carries_identity_and_pointers():
    record = build_record(_entry())
    event = record_to_event(record)
    assert event.knowledge_id == record.knowledge_id
    assert event.entity_id == record.entity_id
    assert event.operation == "upsert"
    assert event.source_uri == record.source_uri
    assert event.source_revision == record.commit_sha
    assert event.content_hash == record.content_hash
    assert event.schema_version == SCHEMA_VERSION
    assert event.occurred_at  # producer timestamp is set
    assert event.event_id == ""


def test_event_occurred_at_respects_injected_now():
    from datetime import datetime, timezone

    pinned = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    record = build_record(_entry(), now=pinned)
    event = record_to_event(record, now=pinned)
    assert event.occurred_at == pinned.isoformat()


# ── Batch derivation filters like build_evidence_cards ──────────


def test_derive_records_skips_narration_failure_and_bad_correctness():
    entries = [
        _entry(worktree_name="exp_good", run_id="exp_good"),
        _entry(worktree_name="exp_narr", run_id="exp_narr", narration_failure=True),
        _entry(worktree_name="exp_neg", run_id="exp_neg", correctness=-1.0),
        _entry(worktree_name="exp_none", run_id="exp_none", correctness=None),
        _entry(worktree_name="exp_nan", run_id="exp_nan", correctness=float("nan")),
    ]
    records = derive_records(entries)
    assert [r.logical_locator for r in records] == ["exp_good"]


def test_derive_records_preserves_input_order():
    entries = [
        _entry(worktree_name="exp_a", run_id="exp_a"),
        _entry(worktree_name="exp_b", run_id="exp_b"),
    ]
    records = derive_records(entries)
    assert [r.logical_locator for r in records] == ["exp_a", "exp_b"]


def test_derive_records_empty_and_all_invalid():
    assert derive_records([]) == []
    assert derive_records([_entry(narration_failure=True)]) == []


# ── build_record rejects invalid entries loudly ─────────────────


def test_build_record_raises_on_skipped_entry():
    with pytest.raises(ValueError):
        build_record(_entry(narration_failure=True))
    with pytest.raises(ValueError):
        build_record(_entry(correctness=None))
    with pytest.raises(ValueError):
        build_record(_entry(correctness=-0.5))
