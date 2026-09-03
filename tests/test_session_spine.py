"""Tests for the session-spine record type (session_ingestion) — s1a of the
self_knowledge_layer wave.

Covers the record-type cases ONLY (the s1a scope fence): the ``meta_session`` source-type
reuse, the AIO org-root actor/scope carriage, the seven content fields, the round trip through
record_to_artifact / record_to_event / extract_record, rerun-safe identity (same input -> same
knowledge_id), and the identity-namespace separation from the legacy ``ledger/v1`` meta_session
lines. The close (s1b) and open (s1c) command cases extend this file in their own phases.
"""

import hashlib
import json

import pytest

from agentic_dynamics.knowledge import ledger_ingestion as li
from agentic_dynamics.knowledge import session_ingestion as si
from agentic_dynamics.knowledge.knowledge import (
    SOURCE_TYPES,
    Authority,
)
from agentic_dynamics.knowledge.knowledge_ingestion import (
    REPOSITORY_ID,
    extract_record,
    record_to_artifact,
    record_to_event,
)


def _session(**overrides) -> dict:
    """A synthetic AIO session close payload — the s1a DONE_WHEN fixture."""
    base = {
        "session_date": "2026-09-03",
        "slug": "wt_selfk_s1a_session_record_type",
        "waves_run": ["self_knowledge_layer/s0_pin_spec", "self_knowledge_layer/s1a"],
        "merged": ["2026-08-14_experiment-spec-and-compiler-design"],
        "parked": ["fleet ladder rung 2", "deploy-gate false positive"],
        "open_threads": ["session spine close command (s1b)", "open command (s1c)"],
        "self_notes": "I re-derived the wave verdict by grep instead of reading a record.",
    }
    base.update(overrides)
    return base


def _payload(record) -> dict:
    return json.loads(record.text)


def _ledger_meta_session_attempt(attempt_id: str = "9696322fa9636310_1"):
    """A legacy embryonic meta_session record (the shape Edge 1 inspected at the s0 pin): a
    ledger_ingestion attempt whose title routed to ``meta_session`` by classify_session."""
    story_result = {
        "story_id": "abc123def456",
        "story_name": "task_manager_api",
        "language": "python",
        "worktree": "/tmp/pipeline/story_abc123",
        "sessions": [
            {
                "session_number": 1,
                "agentic": {
                    "total_tokens": 661,
                    "estimated_cost_usd": 0.001252412,
                    "confidence": None,
                },
            }
        ],
    }
    row = {"title": "meta_batch_042", "cost": 0.5, "tokens_input": 400, "tokens_output": 261}
    records = li.derive_ledger_records(story_result, row, {})
    assert {r.source_type for r in records} == {"ledger_job", "meta_session"}
    return next(r for r in records if r.source_type == "meta_session")


# ── Extractor contract constants ────────────────────────────────


def test_extractor_constants():
    assert si.SOURCE_TYPE == "meta_session"
    assert si.EXTRACTOR_VERSION == "session/v1"
    assert si.ACTOR == "aio"
    assert si.REVISION_FALLBACK == "session/unrevisioned"
    assert si.CONTENT_FIELDS == (
        "session_date",
        "slug",
        "waves_run",
        "merged",
        "parked",
        "open_threads",
        "self_notes",
    )
    # meta_session stays the single registered vocabulary row — the spine family is a producer
    # reuse of the existing source_type, never a fork in the vocabulary (the disambiguator is
    # extractor_version, exactly as the schema separates every other reuse).
    assert si.SOURCE_TYPE in SOURCE_TYPES


def test_session_ingestion_is_exported_from_the_knowledge_package():
    from agentic_dynamics.knowledge import session_ingestion

    assert session_ingestion is si


# ── Provenance + the actor/scope carriage ───────────────────────


def test_record_provenance_is_advisory_h_like_meta_session_nominal():
    record = si.derive_session_record(_session())
    assert record.source_type == "meta_session"
    assert record.authority is Authority.ADVISORY
    assert record.evidence_class == "[H]"
    assert SOURCE_TYPES["meta_session"].authority is Authority.ADVISORY


def test_record_carries_aio_actor_and_org_root_scope():
    record = si.derive_session_record(_session())
    # Scope is structural on the record: the org id as repository_id, the org-root AIO scope as
    # acl_scope — distinct from the corpus's "public" acl rows and from any self-* cell scope.
    assert record.repository_id == REPOSITORY_ID
    assert record.acl_scope == "org:agentic-dynamics"
    # And self-describing in the body: the actor + scope keys are part of the hashed payload, so
    # a consumer can filter "what did I (the AIO) write" purely from the artifact bytes.
    payload = _payload(record)
    assert payload["actor"] == "aio"
    assert payload["scope"] == record.acl_scope


def test_repository_override_rescopes_the_record():
    record = si.derive_session_record(_session(), repository_id="another-org")
    assert record.repository_id == "another-org"
    assert record.acl_scope == "org:another-org"
    assert _payload(record)["scope"] == "org:another-org"


def test_cell_scoped_retrieval_excludes_the_aio_record():
    # Actor layering, deterministic at the type: the record lives at the org root (repository_id
    # "agentic-dynamics"), so the retrieval hard pre-filter (scope_excluded) excludes it from any
    # cell/workload query — a self-* cell scope never equals the org id, so a cell agent cannot
    # resolve the AIO's session records. Only an explicit org-root read sees them.
    from agentic_dynamics.knowledge.retrieval import scope_excluded

    record = si.derive_session_record(_session())
    assert scope_excluded(record.repository_id, requested_scope="self-wt_03")
    assert scope_excluded(record.repository_id, requested_scope="org:agentic-dynamics/workload:x")
    # And the AIO itself resolves its record by asking for its own org scope (empty candidate scope
    # semantics unchanged: "" is never a wildcard on either side).
    assert not scope_excluded(record.repository_id, requested_scope="")
    assert not scope_excluded("", requested_scope="agentic-dynamics")


# ── The seven content fields round-trip ─────────────────────────


def test_content_fields_round_trip_through_artifact_and_event():
    session = _session()
    record = si.derive_session_record(session)

    artifact = record_to_artifact(record)
    event = record_to_event(record)
    extracted = extract_record(event, artifact)

    # The durable artifact + pointer carry the record; extract_record reconstructs it losslessly
    # for every stable field, and the content fields survive in the body verbatim.
    assert extracted.knowledge_id == record.knowledge_id
    assert extracted.content_hash == record.content_hash
    assert extracted.entity_id == record.entity_id
    assert extracted.acl_scope == record.acl_scope
    assert extracted.text == record.text

    payload = _payload(extracted)
    assert payload["session_date"] == session["session_date"]
    assert payload["slug"] == session["slug"]
    assert payload["waves_run"] == session["waves_run"]
    assert payload["merged"] == session["merged"]
    assert payload["parked"] == session["parked"]
    assert payload["open_threads"] == session["open_threads"]
    assert payload["self_notes"] == session["self_notes"]

    # The standard pointer contract (mirrors every producer's): content_hash is the sha256 of the
    # artifact, the event names the per-record artifact URI, observed_at round-trips the session's
    # own date (not the producer wall-clock).
    assert event.knowledge_id == record.knowledge_id
    assert event.entity_id == record.entity_id
    assert event.operation == "upsert"
    assert event.source_uri == f"file://experiments/results/kb/{record.knowledge_id}.json"
    # The pointer's source_revision is the record's commit_sha ("" for a session record — the
    # record is not bound to a commit; the stable revision marker travels in the artifact body and
    # the knowledge_id, never on the pointer). content_hash + observed_at round-trip the session's
    # own body + date.
    assert event.source_revision == record.commit_sha == ""
    assert event.content_hash == hashlib.sha256(artifact).hexdigest()
    assert event.observed_at == session["session_date"]
    assert extracted.observed_at == session["session_date"]


def test_full_dict_round_trip_is_lossless():
    from agentic_dynamics.knowledge.knowledge import KnowledgeRecord

    record = si.derive_session_record(_session())
    restored = KnowledgeRecord.from_dict(record.to_dict())
    assert restored == record


def test_derive_and_build_delegate_to_the_same_record():
    session = _session()
    # Two derivation calls land microseconds apart, so the volatile consumer clocks (valid_from /
    # indexed_at) differ — but the stable identity and body are byte-identical (what rerun-safety
    # and the s1b no-op-on-reclose both depend on).
    a = si.derive_session_record(session)
    b = si.build_session_record(session)
    for attr in (
        "knowledge_id",
        "entity_id",
        "content_hash",
        "source_uri",
        "text",
        "logical_locator",
        "acl_scope",
        "repository_id",
    ):
        assert getattr(a, attr) == getattr(b, attr)


# ── Rerun-safe identity ─────────────────────────────────────────


def test_knowledge_id_is_rerun_safe_same_input_same_id():
    first = si.derive_session_record(_session())
    # Re-derivation at a DIFFERENT producer wall-clock must still yield the same id — the volatile
    # timestamps are blanked from the artifact, so the content hash (and the id folding it) is a
    # pure function of the session body + the stable identity. This is what makes a repeated close
    # a no-op rather than a fresh record every session boundary.
    second = si.derive_session_record(_session())
    assert second.knowledge_id == first.knowledge_id
    assert second.entity_id == first.entity_id
    assert second.content_hash == first.content_hash


def test_changed_content_rekeys_knowledge_id_but_not_entity_id():
    first = si.derive_session_record(_session())
    second = si.derive_session_record(_session(waves_run=["self_knowledge_layer/s0_pin_spec"]))
    # A changed wave list is a NEW body -> a new immutable knowledge_id (a new version of the
    # session slot), while the entity_id — the slug's logical identity — holds.
    assert second.entity_id == first.entity_id
    assert second.knowledge_id != first.knowledge_id
    assert second.content_hash != first.content_hash


def test_identity_is_namespace_distinct_from_legacy_ledger_meta_session():
    # Edge 1's legacy shape is a ledger/v1 attempt whose title routed to meta_session. Give the
    # spine producer the SAME logical string as that attempt's slug: the two must never collide on
    # identity — the spine family is session:<slug> + session/v1, the legacy is
    # meta_session:<attempt> + ledger/v1.
    legacy = _ledger_meta_session_attempt()
    assert legacy.extractor_version == "ledger/v1"
    assert legacy.source_uri.startswith("meta_session:")

    spine = si.derive_session_record(_session(slug=legacy.logical_locator))
    assert spine.source_uri.startswith("session:")
    assert spine.extractor_version == "session/v1"
    assert spine.entity_id != legacy.entity_id
    assert spine.knowledge_id != legacy.knowledge_id


# ── Validation + normalization ──────────────────────────────────


def test_missing_slug_raises_value_error():
    with pytest.raises(ValueError, match="slug"):
        si.derive_session_record(_session(slug=""))


def test_missing_session_date_raises_value_error():
    with pytest.raises(ValueError, match="session_date"):
        si.derive_session_record(_session(session_date=None))


def test_empty_list_fields_normalize_to_empty_lists():
    record = si.derive_session_record(
        _session(waves_run=[], merged=None, parked=[], open_threads=None)
    )
    payload = _payload(record)
    assert payload["waves_run"] == []
    assert payload["merged"] == []
    assert payload["parked"] == []
    assert payload["open_threads"] == []
    assert (
        payload["self_notes"]
        == "I re-derived the wave verdict by grep instead of reading a record."
    )


def test_list_fields_coerce_elements_and_keep_caller_order():
    # waves_run is chronological — the list must survive in caller order (never re-sorted) and be
    # JSON-serializable even for non-str elements.
    record = si.derive_session_record(_session(merged=("doc-a", "doc-b"), parked=[42]))
    payload = _payload(record)
    assert payload["merged"] == ["doc-a", "doc-b"]
    assert payload["parked"] == ["42"]


def test_revision_is_not_bound_to_a_commit_so_close_is_rerun_safe():
    record = si.derive_session_record(_session())
    assert record.commit_sha == ""
    # The revision folded into knowledge_id is the stable fallback marker, never the checkout HEAD.
    from agentic_dynamics.knowledge.knowledge import compute_knowledge_id

    recomputed = compute_knowledge_id(
        record.entity_id, si.REVISION_FALLBACK, record.content_hash, si.EXTRACTOR_VERSION
    )
    assert record.knowledge_id == recomputed
