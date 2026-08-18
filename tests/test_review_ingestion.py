"""Tests for review ingestion (review_ingestion).

Covers the extractor contract constants, identity derivation (entity_id keyed by the
logical ``review:{story_id}`` marker), the ADVISORY/[H] provenance (a review is a
judgment, never an independently measured fact), the reused artifact/event contract,
determinism, and the batch-derivation pre-filter. The fixture mirrors
``scripts/finalize_reviews.py:_finalize_story``'s actual merged output shape
(``finalize_reviews.py:56-63``): ``{"story_name", "story_id", "model", "commit_reviews",
"story_review"}``.
"""

import hashlib

import pytest

from instrument import review_ingestion as ri
from instrument.knowledge import Authority, compute_entity_id
from instrument.knowledge_ingestion import record_to_artifact


def _review(**overrides) -> dict:
    base = {
        "story_name": "task_manager_api",
        "story_id": "abc123def456",
        "model": "deepseek/deepseek-v4-flash",
        "commit_reviews": [
            {
                "commit_hash": "commit_s1",
                "reviewer_model": "deepseek/deepseek-v4-flash",
                "architectural_fit": 0.9,
                "convention_adherence": 0.85,
                "introduces_technical_debt": False,
                "respects_existing_patterns": True,
                "better_or_worse": "better",
                "problems": [],
                "strengths": ["clean separation of concerns"],
                "summary": "solid incremental commit",
                "session_number": 1,
            },
            {
                "commit_hash": "commit_s2",
                "reviewer_model": "deepseek/deepseek-v4-flash",
                "architectural_fit": 0.4,
                "convention_adherence": 0.5,
                "introduces_technical_debt": True,
                "respects_existing_patterns": False,
                "better_or_worse": "worse",
                "problems": [{"category": "architecture", "severity": "major", "description": "coupling"}],
                "strengths": [],
                "summary": "introduced tight coupling",
                "session_number": 2,
            },
        ],
        "story_review": {
            "story_name": "task_manager_api",
            "reviewer_model": "deepseek/deepseek-v4-flash",
            "overall_coherence": 0.7,
            "compounding_issues": ["coupling introduced in session 2"],
            "key_decisions": [],
            "trajectory_description": "",
            "summary": "mostly coherent with a late regression",
        },
    }
    base.update(overrides)
    return base


# ── Extractor contract constants ────────────────────────────────


def test_extractor_constants():
    assert ri.EXTRACTOR_VERSION == "review/v1"
    assert ri.SOURCE_TYPE == "review"
    assert ri.ACL_SCOPE == "public"


# ── Identity ─────────────────────────────────────────────────────


def test_entity_id_is_a_logical_marker_keyed_by_story_id():
    record = ri.build_review_record(_review())
    assert record.source_uri == "review:abc123def456"
    expected = compute_entity_id("agentic-dynamics", "review:abc123def456", "abc123def456")
    assert record.entity_id == expected


def test_logical_locator_is_story_id():
    record = ri.build_review_record(_review())
    assert record.logical_locator == "abc123def456"


# ── Provenance ───────────────────────────────────────────────────


def test_authority_is_advisory_and_evidence_class_is_h():
    record = ri.build_review_record(_review())
    assert record.authority is Authority.ADVISORY
    assert record.evidence_class == "[H]"


def test_review_carries_no_test_executed_success():
    # A review is a judgment, not an independent test run.
    record = ri.build_review_record(_review())
    assert record.test_executed_success is None


# ── Text rendering ───────────────────────────────────────────────


def test_text_mentions_model_and_commit_review_tally():
    record = ri.build_review_record(_review())
    assert "deepseek/deepseek-v4-flash" in record.text
    assert "1 better" in record.text
    assert "1 worse" in record.text


# ── Reused artifact/event contract ──────────────────────────────


def test_content_hash_equals_sha256_of_record_to_artifact():
    record = ri.build_review_record(_review())
    assert record.content_hash == hashlib.sha256(record_to_artifact(record)).hexdigest()


# ── Determinism ──────────────────────────────────────────────────


def test_repeated_derivation_is_idempotent():
    a = ri.build_review_record(_review())
    b = ri.build_review_record(_review())
    assert a.knowledge_id == b.knowledge_id
    assert a.entity_id == b.entity_id


def test_changed_body_yields_a_different_knowledge_id():
    a = ri.build_review_record(_review())
    b = ri.build_review_record(_review(story_review={**_review()["story_review"], "overall_coherence": 0.1}))
    assert a.knowledge_id != b.knowledge_id
    assert a.entity_id == b.entity_id


# ── Errors / batch pre-filter ────────────────────────────────────


def test_build_review_record_raises_without_story_id():
    with pytest.raises(ValueError):
        ri.build_review_record(_review(story_id=""))


def test_derive_review_records_skips_missing_story_id_instead_of_raising():
    assert ri.derive_review_records(_review(story_id="")) == []


def test_derive_review_records_returns_one_record():
    records = ri.derive_review_records(_review())
    assert len(records) == 1
    assert records[0].source_type == "review"
