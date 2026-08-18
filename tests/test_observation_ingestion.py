"""Tests for observation/flag ingestion (observation_ingestion).

Covers the extractor contract constants, the ADVISORY/[H] provenance, identity
derivation for both record kinds, and — the literal audit-gap closure round 1's OQ6a
described — that EVERY verdict status (not only non-``healthy`` ones) produces an
``observation`` record. Status values mirror ``scripts/supervise.py``'s verdict contract
(``supervise.py``'s ``parse_verdict``/``supervise_once``: ``healthy``, ``stalled``,
``off_track``, ``unknown``).
"""

import hashlib

import pytest

from instrument import observation_ingestion as oi
from instrument.knowledge import Authority, compute_entity_id
from instrument.knowledge_ingestion import record_to_artifact


def _verdict(**overrides) -> dict:
    base = {
        "cell_id": "wf_task_manager_api_1",
        "status": "healthy",
        "why": "on track, tests passing",
        "model": "deepseek/deepseek-v4-flash",
        "at": "2026-08-15T00:00:00+00:00",
    }
    base.update(overrides)
    return base


def _flag(**overrides) -> dict:
    base = {
        "at": "2026-08-15T00:00:00+00:00",
        "session_id": "sess_abc123",
        "title": "wf_task_manager_api_1",
        "model": "deepseek/deepseek-v4-flash",
        "status": "off_track",
        "why": "diverged from spec",
    }
    base.update(overrides)
    return base


# ── Extractor contract constants ────────────────────────────────


def test_extractor_constants():
    assert oi.EXTRACTOR_VERSION == "observation/v1"
    assert oi.SOURCE_TYPE_OBSERVATION == "observation"
    assert oi.SOURCE_TYPE_FLAG == "flag"
    assert oi.ACL_SCOPE == "public"


# ── OQ6a closure: every verdict registers, not only flagged ones ─


@pytest.mark.parametrize("status", ["healthy", "stalled", "off_track", "unknown"])
def test_every_verdict_status_produces_an_observation_record(status):
    record = oi.derive_observation_record(_verdict(status=status))
    assert record.source_type == "observation"
    assert status in record.text


def test_healthy_verdict_registers_even_though_it_never_flags():
    # The literal audit-gap closure: a `healthy` verdict produces NO flags.jsonl line
    # (scripts/supervise.py:343's gate is unchanged), but it must still produce a durable
    # observation record — that's what this producer exists to guarantee.
    record = oi.derive_observation_record(_verdict(status="healthy"))
    assert record.source_type == "observation"
    assert record.authority is Authority.ADVISORY


# ── Identity ─────────────────────────────────────────────────────


def test_observation_identity_folds_in_cell_id_and_timestamp():
    a = oi.derive_observation_record(_verdict(at="2026-08-15T00:00:00+00:00"))
    b = oi.derive_observation_record(_verdict(at="2026-08-15T00:10:00+00:00"))
    # Two verdicts against the same cell at different times are independent facts.
    assert a.knowledge_id != b.knowledge_id
    assert a.entity_id != b.entity_id


def test_flag_entity_id_is_keyed_by_session_id():
    record = oi.derive_flag_record(_flag())
    assert record.source_uri == "flag_stream:sess_abc123"
    expected = compute_entity_id("agentic-dynamics", "flag_stream:sess_abc123", "sess_abc123")
    assert record.entity_id == expected


# ── Provenance ───────────────────────────────────────────────────


def test_observation_authority_is_advisory_and_h():
    record = oi.derive_observation_record(_verdict())
    assert record.authority is Authority.ADVISORY
    assert record.evidence_class == "[H]"


def test_flag_authority_is_advisory_and_h():
    record = oi.derive_flag_record(_flag())
    assert record.authority is Authority.ADVISORY
    assert record.evidence_class == "[H]"


# ── Reused artifact/event contract ──────────────────────────────


def test_observation_content_hash_equals_sha256_of_record_to_artifact():
    record = oi.derive_observation_record(_verdict())
    assert record.content_hash == hashlib.sha256(record_to_artifact(record)).hexdigest()


def test_flag_content_hash_equals_sha256_of_record_to_artifact():
    record = oi.derive_flag_record(_flag())
    assert record.content_hash == hashlib.sha256(record_to_artifact(record)).hexdigest()


# ── Errors ─────────────────────────────────────────────────────


def test_derive_observation_record_raises_without_cell_id():
    with pytest.raises(ValueError):
        oi.derive_observation_record(_verdict(cell_id=""))


def test_derive_flag_record_raises_without_session_id():
    with pytest.raises(ValueError):
        oi.derive_flag_record(_flag(session_id=""))
