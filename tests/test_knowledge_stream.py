"""Tests for durable knowledge ingestion over Redis Streams (DB 2 on 6380).

Requires the framework Redis on FINOPS_REDIS_PORT (default 6380). Skipped when absent.
These tests operate on DB 2 (the reserved knowledge-stream DB) and flush it per-test;
DB 1 (the framework queue) is only ever *read* to prove key isolation.
"""

import hashlib
import os
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


@pytest.fixture(autouse=True)
def _authorize_writes(monkeypatch):
    """Satisfy the publish_event write guard for this module's producer-side tests.

    ``publish_event`` raises without ``FINOPS_KB_WRITE=1``; these tests exercise the
    producer-side publish/reconcile paths, so the flag is set for the whole module. The
    guard itself is unit-tested in ``tests/test_knowledge_ingestion.py``.
    """
    monkeypatch.setenv("FINOPS_KB_WRITE", "1")

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
    kwargs = dict(
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
    kwargs.update(overrides)  # e.g. causes=... for the round-2 actuation-gate tests
    event = KnowledgeEvent(**kwargs)
    return event, content_hash


class _FakeStore:
    """An idempotent destination keyed by knowledge_id (mirrors Chroma/Neo4j upsert)."""

    def __init__(self):
        self.docs = {}

    def upsert(self, record):
        self.docs[record.knowledge_id] = record.text  # same key overwrites → idempotent


def _publish_file_event(
    r, content, *, knowledge_id="kid_1", tmp_path=None, source_type="",
    operation="upsert", reason="",
) -> KnowledgeEvent:
    path = tmp_path or "/tmp/opencode"
    os.makedirs(path, exist_ok=True)
    f = f"{path}/kb_source_{knowledge_id}.txt"
    with open(f, "w") as fh:
        fh.write(content)
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    event = KnowledgeEvent(
        knowledge_id=knowledge_id,
        entity_id="entity_1",
        operation=operation,
        source_uri=f,
        source_revision="rev-1",
        content_hash=content_hash,
        occurred_at="2026-08-15T00:00:00Z",
        schema_version="kb/v1",
        event_id="",
        reason=reason,
    )
    # source_type lets a caller seed the observation-family index the actuation gate's
    # `causes` lineage check reads (see knowledge_stream.SOURCE_TYPE_INDEX_KEY).
    ks.publish_event(r, event, source_type=source_type)
    return event


# ── Contract constants ──────────────────────────────────────────

def test_contract_constants():
    assert ks.REDIS_DB == 2
    assert ks.STREAM_KEY == "kb:v1:changes"
    assert ks.DEAD_LETTER_KEY == "kb:v1:dead_letter"
    assert ks.CONSUMER_GROUPS == (
        "kb-chroma-v1", "kb-neo4j-v1", "kb-ledger-v1", "kb-registry-v1",
    )


def test_kb_registry_v1_is_a_valid_consumer_group(redis2):
    # The registry consumer group can be created idempotently like the other three.
    assert ks.create_consumer_group(redis2, "kb-registry-v1") is True
    assert ks.create_consumer_group(redis2, "kb-registry-v1") is False  # BUSYGROUP → False


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


# ── Operation threading (canonical-state finalize, G1) ───────────
#
# process_entry must pass the event's operation/reason into a handler that opts in (by
# declaring an `operation` parameter), while handlers that don't opt in — like
# `_FakeStore.upsert` above, and every pre-existing chroma/ledger handler — keep receiving
# exactly the old `handler(record)` call.


class _OperationCapturingStore:
    """A handler that opts into operation/reason by declaring both as parameters."""

    def __init__(self):
        self.calls: list[tuple[str, str, str]] = []  # (knowledge_id, operation, reason)

    def upsert(self, record, *, operation="upsert", reason=""):
        self.calls.append((record.knowledge_id, operation, reason))


def test_process_entry_passes_operation_to_an_opted_in_handler(redis2):
    ks.create_consumer_group(redis2, "kb-test-op1")
    _publish_file_event(
        redis2, "tombstoned payload", knowledge_id="kid_op_delete",
        operation="delete", reason="contaminated cell",
    )
    store = _OperationCapturingStore()

    entries = ks.read_events(redis2, "kb-test-op1", "c1", count=1)
    outcome = ks.process_entry(
        redis2, "kb-test-op1", entries[0].entry_id, entries[0].event, store.upsert,
    )
    assert outcome == "ok"
    assert store.calls == [("kid_op_delete", "delete", "contaminated cell")]


def test_process_entry_does_not_pass_operation_to_a_plain_handler(redis2):
    # A handler that only accepts `record` (the pre-existing shape) must still work
    # unchanged — process_entry must not force operation/reason onto it.
    ks.create_consumer_group(redis2, "kb-test-op2")
    _publish_file_event(
        redis2, "supersede payload", knowledge_id="kid_op_plain", operation="supersede",
    )
    store = _FakeStore()

    entries = ks.read_events(redis2, "kb-test-op2", "c1", count=1)
    outcome = ks.process_entry(
        redis2, "kb-test-op2", entries[0].entry_id, entries[0].event, store.upsert,
    )
    assert outcome == "ok"
    assert store.docs == {"kid_op_plain": "supersede payload"}


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


# ── Actuation gate (round 2 canonical-state design §5c) ──────────
#
# The gate lives inside publish_event() itself (the single function every producer
# already calls) and fires only when the caller's `source_type` classifies as
# "actuation" (see instrument.knowledge.message_family). Nothing in the running system
# passes source_type="actuation" today — these tests exercise the gate directly, the same
# way its own eventual caller (a future control-rule evaluator, per design §5b) would.


def test_publish_event_rejects_actuation_without_armed_flag(redis2, tmp_path, monkeypatch):
    monkeypatch.delenv("FINOPS_ACTUATION_ARMED", raising=False)
    obs = _publish_file_event(
        redis2, "an observation", knowledge_id="kid_obs_unarmed", tmp_path=str(tmp_path),
        source_type="story",
    )
    event, _ = _event("actuation candidate", knowledge_id="kid_act_unarmed", causes=obs.knowledge_id)
    with pytest.raises(RuntimeError, match="not armed"):
        ks.publish_event(redis2, event, source_type="actuation")


def test_publish_event_accepts_actuation_when_armed_true_and_causes_valid(redis2, tmp_path):
    obs = _publish_file_event(
        redis2, "an observation", knowledge_id="kid_obs_armed", tmp_path=str(tmp_path),
        source_type="observation",
    )
    event, _ = _event("actuation candidate", knowledge_id="kid_act_armed", causes=obs.knowledge_id)
    entry_id = ks.publish_event(redis2, event, source_type="actuation", armed=True)
    assert entry_id  # accepted — armed explicitly, and `causes` resolves to an observation


def test_publish_event_accepts_actuation_when_env_flag_armed(redis2, tmp_path, monkeypatch):
    monkeypatch.setenv("FINOPS_ACTUATION_ARMED", "1")
    obs = _publish_file_event(
        redis2, "an observation", knowledge_id="kid_obs_envarmed", tmp_path=str(tmp_path),
        source_type="flag",
    )
    event, _ = _event("actuation candidate", knowledge_id="kid_act_envarmed", causes=obs.knowledge_id)
    entry_id = ks.publish_event(redis2, event, source_type="actuation")
    assert entry_id


def test_publish_event_rejects_actuation_with_unresolvable_causes(redis2):
    # armed=True but `causes` points at a knowledge_id nothing ever registered.
    event, _ = _event(
        "actuation candidate", knowledge_id="kid_act_badcauses", causes="no_such_knowledge_id",
    )
    with pytest.raises(RuntimeError, match="causes"):
        ks.publish_event(redis2, event, source_type="actuation", armed=True)


def test_publish_event_rejects_actuation_with_empty_causes(redis2):
    event, _ = _event("actuation candidate", knowledge_id="kid_act_emptycauses")
    assert event.causes == ""
    with pytest.raises(RuntimeError, match="causes"):
        ks.publish_event(redis2, event, source_type="actuation", armed=True)


def test_publish_event_rejects_actuation_whose_causes_is_itself_an_actuation(redis2, tmp_path):
    # `causes` must resolve to an OBSERVATION-family record — an actuation cannot cite
    # another actuation as its justification.
    prior_actuation, _ = _event("prior actuation", knowledge_id="kid_prior_actuation")
    # Published unarmed-check-bypassed via a direct index seed is not possible (the
    # actuation branch never writes to the index — see publish_event's docstring), so the
    # index has no entry for kid_prior_actuation at all; resolution must fail regardless.
    event, _ = _event(
        "actuation candidate", knowledge_id="kid_act_citesactuation",
        causes=prior_actuation.knowledge_id,
    )
    with pytest.raises(RuntimeError, match="causes"):
        ks.publish_event(redis2, event, source_type="actuation", armed=True)


def test_finops_actuation_armed_is_unset_by_default():
    # Guards against a future .env/CI config change silently arming actuation without
    # anyone noticing — nothing else in the suite would catch that.
    assert os.environ.get("FINOPS_ACTUATION_ARMED") != "1"


# ── DB 2 key isolation ──────────────────────────────────────────

def test_db2_keys_are_isolated_from_db1(redis2, redis1):
    redis2.set("kb:v1:test_probe", "x")
    assert redis2.exists("kb:v1:test_probe") == 1
    assert redis1.exists("kb:v1:test_probe") == 0  # never visible on the queue DB
