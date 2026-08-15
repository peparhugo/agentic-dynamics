"""Tests for durable knowledge ingestion over Redis Streams (DB 2 on 6380).

Requires the framework Redis on FINOPS_REDIS_PORT (default 6380). Skipped when absent.
These tests operate on DB 2 (the reserved knowledge-stream DB) and flush it per-test;
DB 1 (the framework queue) is only ever *read* to prove key isolation.
"""

import hashlib
import socket

import pytest

from instrument import knowledge_stream as ks
from instrument.knowledge import KnowledgeEvent

try:
    _probe = socket.create_connection(("127.0.0.1", 6380), timeout=2)
    _probe.close()
    _REDIS_OK = True
except Exception:
    _REDIS_OK = False

pytestmark = pytest.mark.skipif(not _REDIS_OK, reason="Redis not available on 6380")

STREAM = ks.STREAM_KEY
DEAD_LETTER = ks.DEAD_LETTER_KEY


@pytest.fixture()
def redis2():
    r = ks.connect()
    r.flushdb()
    yield r
    r.flushdb()


@pytest.fixture()
def redis1():
    import redis

    r = redis.Redis(host=ks.REDIS_HOST, port=ks.REDIS_PORT, db=1, decode_responses=True)
    return r


def _event(content: str, *, knowledge_id: str = "kid_1", **overrides) -> tuple[KnowledgeEvent, str]:
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    event = KnowledgeEvent(
        knowledge_id=knowledge_id,
        entity_id="entity_1",
        operation="upsert",
        source_uri="",  # filled below with a temp path
        source_revision="rev-1",
        content_hash=content_hash,
        occurred_at="2026-08-15T00:00:00Z",
        schema_version="kb/v1",
        event_id="",
    )
    return event, content_hash


class _FakeStore:
    """An idempotent destination keyed by knowledge_id (mirrors Chroma/Neo4j upsert)."""

    def __init__(self):
        self.docs = {}

    def upsert(self, record):
        self.docs[record.knowledge_id] = record.text  # same key overwrites → idempotent


def _publish_file_event(r, content, *, knowledge_id="kid_1", tmp_path=None) -> KnowledgeEvent:
    import os

    path = tmp_path or "/tmp/opencode"
    os.makedirs(path, exist_ok=True)
    f = f"{path}/kb_source_{knowledge_id}.txt"
    with open(f, "w") as fh:
        fh.write(content)
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    event = KnowledgeEvent(
        knowledge_id=knowledge_id,
        entity_id="entity_1",
        operation="upsert",
        source_uri=f,
        source_revision="rev-1",
        content_hash=content_hash,
        occurred_at="2026-08-15T00:00:00Z",
        schema_version="kb/v1",
        event_id="",
    )
    ks.publish_event(r, event)
    return event


# ── Contract constants ──────────────────────────────────────────

def test_contract_constants():
    assert ks.REDIS_DB == 2
    assert ks.STREAM_KEY == "kb:v1:changes"
    assert ks.DEAD_LETTER_KEY == "kb:v1:dead_letter"
    assert ks.CONSUMER_GROUPS == ("kb-chroma-v1", "kb-neo4j-v1", "kb-ledger-v1")


# ── Group creation ──────────────────────────────────────────────

def test_create_consumer_group_is_idempotent(redis2):
    assert ks.create_consumer_group(redis2, "kb-test-g1") is True
    assert ks.create_consumer_group(redis2, "kb-test-g1") is False  # BUSYGROUP → False


def test_read_events_parses_pointers(redis2):
    ks.create_consumer_group(redis2, "kb-test-g2")
    _publish_file_event(redis2, "hello world", knowledge_id="kid_read")
    entries = ks.read_events(redis2, "kb-test-g2", "c1", count=1)
    assert len(entries) == 1
    assert entries[0].event.knowledge_id == "kid_read"
    assert not hasattr(entries[0].event, "text")  # pointer only, no body


# ── Idempotence + XACK ──────────────────────────────────────────

def test_process_entry_acks_and_prevents_redelivery(redis2):
    ks.create_consumer_group(redis2, "kb-test-g3")
    _publish_file_event(redis2, "payload text", knowledge_id="kid_x")
    store = _FakeStore()

    entries = ks.read_events(redis2, "kb-test-g3", "c1", count=1)
    assert ks.process_entry(redis2, "kb-test-g3", entries[0].entry_id, entries[0].event, store.upsert) == "ok"
    assert ks.pending_count(redis2, "kb-test-g3") == 0
    # A re-read finds nothing — the entry was acked, not redelivered.
    assert ks.read_events(redis2, "kb-test-g3", "c1", count=1) == []


def test_upsert_is_idempotent_keyed_by_knowledge_id(redis2, tmp_path):
    ks.create_consumer_group(redis2, "kb-test-g4")
    store = _FakeStore()
    # Same knowledge_id published twice (e.g. replay) → one destination doc.
    for _ in range(2):
        _publish_file_event(redis2, "same text", knowledge_id="kid_dup", tmp_path=str(tmp_path))
    entries = ks.read_events(redis2, "kb-test-g4", "c1", count=10)
    for e in entries:
        assert ks.process_entry(redis2, "kb-test-g4", e.entry_id, e.event, store.upsert) == "ok"
    assert list(store.docs.keys()) == ["kid_dup"]


def test_content_hash_mismatch_fails(redis2, tmp_path):
    ks.create_consumer_group(redis2, "kb-test-g5")
    event = _publish_file_event(redis2, "original", knowledge_id="kid_m", tmp_path=str(tmp_path))
    # Tamper with the artifact after publishing → hash no longer matches.
    with open(event.source_uri, "w") as fh:
        fh.write("tampered")
    entries = ks.read_events(redis2, "kb-test-g5", "c1", count=1)
    outcome = ks.process_entry(
        redis2, "kb-test-g5", entries[0].entry_id, entries[0].event, _FakeStore().upsert,
        max_retries=1,
    )
    assert outcome == "dead_letter"  # corrupt source is dead-lettered, not indexed


# ── Claiming ────────────────────────────────────────────────────

def test_claim_pending_reclaims_stale_message(redis2):
    ks.create_consumer_group(redis2, "kb-test-g6")
    _publish_file_event(redis2, "claim me", knowledge_id="kid_claim")
    # c1 reads but never acks (simulates a crash) — the entry is now pending.
    ks.read_events(redis2, "kb-test-g6", "c1", count=1)
    assert ks.pending_count(redis2, "kb-test-g6") == 1
    # c2 claims it after the lease timeout (0 ms here for determinism).
    claimed = ks.claim_pending(redis2, "kb-test-g6", "c2", min_idle_ms=0)
    assert len(claimed) == 1
    assert claimed[0].event.knowledge_id == "kid_claim"
    assert ks.delivery_count(redis2, "kb-test-g6", claimed[0].entry_id) == 2  # delivery incremented


# ── Retries + dead-letter ───────────────────────────────────────

def test_retry_then_dead_letter_after_cap(redis2):
    ks.create_consumer_group(redis2, "kb-test-g7")
    _publish_file_event(redis2, "flaky", knowledge_id="kid_dl")

    def failing_handler(record):
        raise RuntimeError("store down")

    # Delivery 1 → retry (below cap), not acked.
    entries = ks.read_events(redis2, "kb-test-g7", "c1", count=1)
    eid = entries[0].entry_id
    assert ks.process_entry(redis2, "kb-test-g7", eid, entries[0].event, failing_handler, max_retries=2) == "retry"
    assert ks.pending_count(redis2, "kb-test-g7") == 1

    # Claim back (delivery 2) → now at the cap → dead-letter.
    claimed = ks.claim_pending(redis2, "kb-test-g7", "c2", min_idle_ms=0)
    assert ks.process_entry(redis2, "kb-test-g7", claimed[0].entry_id, claimed[0].event, failing_handler, max_retries=2) == "dead_letter"

    # Original acked (pending 0), and the pointer landed in the dead-letter stream.
    assert ks.pending_count(redis2, "kb-test-g7") == 0
    dl = redis2.xrange(DEAD_LETTER)
    assert len(dl) == 1
    fields = dl[0][1]
    assert fields["knowledge_id"] == "kid_dl"
    assert "reason" in fields


# ── Reconciliation ──────────────────────────────────────────────

def test_reconcile_missing_emits_only_absent_ids(redis2):
    event, _ = _event("reconcile me", knowledge_id="kid_rec")
    # known_ids already contains kid_rec → nothing emitted.
    assert ks.reconcile_missing(redis2, [event], {"kid_rec"}) == []
    # known_ids is missing kid_rec → emitted.
    emitted = ks.reconcile_missing(redis2, [event], set())
    assert len(emitted) == 1
    assert len(redis2.xrange(STREAM)) == 1


# ── DB 2 key isolation ──────────────────────────────────────────

def test_db2_keys_are_isolated_from_db1(redis2, redis1):
    redis2.set("kb:v1:test_probe", "x")
    assert redis2.exists("kb:v1:test_probe") == 1
    assert redis1.exists("kb:v1:test_probe") == 0  # never visible on the queue DB
