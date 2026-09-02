"""Tests for the transactional outbox — the ONE emission path (``control_db_publication`` p2).

Every rule is proved in BOTH directions: that it permits what it should, and that it refuses
what it should. A test that only shows the happy path proves a feature exists, not that a
guarantee holds — and every guarantee here is about a *failure* (a downed stream, a crash
between the ack and the mark, a payload that will never deliver).

The knowledge stream is a fake throughout (``FakeStream`` below), and that is not a shortcut:
the ack-ordering rule can only be observed by controlling exactly when the ack happens, which a
live Redis will not let a test do. The control database, by contrast, is always real — a
SQLite file under ``tmp_path`` — because the atomicity claim is a claim about SQLite
transactions and a mocked database would prove nothing about them.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from agentic_dynamics.control.control_db import (
    ControlDB,
    OutboxStatus,
    RunState,
    TerminalStateError,
)
from agentic_dynamics.control.outbox import (
    KIND_KNOWLEDGE_EVENT,
    PAYLOAD_VERSION,
    BackoffPolicy,
    DrainReport,
    OutboxPublisher,
    knowledge_payload,
    record_terminal_run,
    registry_lines_for,
    summarize,
)
from agentic_dynamics.knowledge.knowledge import Authority, KnowledgeEvent, KnowledgeRecord

# ── Fixtures and doubles ─────────────────────────────────────────────────────────────────────


@pytest.fixture()
def db(tmp_path):
    """A real, writable control database for one test."""
    handle = ControlDB.open(tmp_path / "control" / "control.db")
    yield handle
    handle.close()


@pytest.fixture()
def run_id(db):
    """A run sitting in ``running`` — the state a terminal write transitions out of."""
    return db.create_run(
        spec_name="control_db_publication",
        model="anthropic/claude-opus-5",
        state=RunState.RUNNING,
    ).run_id


class FakeStream:
    """A knowledge stream that records what it was asked to publish.

    Stands in for the Redis client AND the ``publish_event`` seam. ``fail_times`` makes the
    next N publishes raise, which is how the backoff and dead-letter rules become observable
    without waiting on a real transport.
    """

    def __init__(self, *, fail_times: int = 0, error: Exception | None = None):
        self.published: list[tuple[dict, str, bool]] = []
        self.checkpoints: dict[str, dict[str, str]] = {}
        self.fail_times = fail_times
        self.error = error or RuntimeError("stream rejected the event")
        self.connect_calls = 0

    # -- the connection seam ------------------------------------------------------------------

    def connect(self):
        """Hand back self; the publisher treats the client as opaque."""
        self.connect_calls += 1
        return self

    # -- the publish seam ---------------------------------------------------------------------

    def publish(self, client, event, *, source_type="", authorized=False):
        """Publish, or raise if this call is inside the configured failure window."""
        if self.fail_times > 0:
            self.fail_times -= 1
            raise self.error
        self.published.append((event.to_dict(), source_type, authorized))
        return f"1700000000-{len(self.published)}"  # the ack: a stream entry id

    # -- the checkpoint hash ------------------------------------------------------------------

    def hget(self, key, field):
        return self.checkpoints.get(key, {}).get(field)

    def hset(self, key, field, value):
        self.checkpoints.setdefault(key, {})[field] = value


def make_record(knowledge_id: str = "k" * 64, **overrides) -> KnowledgeRecord:
    """A minimal but COMPLETE KnowledgeRecord — every required field, no placeholders elided."""
    fields = dict(
        knowledge_id=knowledge_id,
        entity_id="spec:control_db_publication",
        source_uri="file://experiments/results/kb/x.json",
        source_type="finding",
        logical_locator="workflows/repository/control_db_publication.yaml",
        repository_id="self-wt_control_db",
        branch="main",
        worktree_id="wt_control_db",
        commit_sha="a" * 40,
        content_hash="b" * 64,
        extractor_version="measured-finding/v1",
        embedding_version="none",
        authority=Authority.MEASURED,
        valid_from="2026-09-02T00:00:00Z",
        valid_to=None,
        observed_at="2026-09-02T00:00:00Z",
        indexed_at="2026-09-02T00:00:01Z",
        acl_scope="repo",
        contains_sensitive_data=False,
        text="the outbox delivered this",
        token_count=5,
        language="python",
        symbols=[],
        outcome_id="",
        test_executed_success=True,
        evidence_class="[M]",
    )
    fields.update(overrides)
    return KnowledgeRecord(**fields)


def make_event(record: KnowledgeRecord, **overrides) -> KnowledgeEvent:
    """The pointer event a producer would build for ``record``."""
    fields = dict(
        knowledge_id=record.knowledge_id,
        entity_id=record.entity_id,
        operation="upsert",
        source_uri=record.source_uri,
        source_revision=record.commit_sha,
        content_hash=record.content_hash,
        occurred_at=record.observed_at,
        schema_version="knowledge-event/v1",
        event_id=record.knowledge_id,
        reason="fact-content=deadbeef",
    )
    fields.update(overrides)
    return KnowledgeEvent(**fields)


def publisher(db, stream, tmp_path, **kwargs) -> OutboxPublisher:
    """A publisher wired to the fake stream and to throwaway artifact/registry paths."""
    options = dict(
        connect=stream.connect,
        publish=stream.publish,
        artifact_dir=tmp_path / "kb",
        registry_path=tmp_path / "registry_index.jsonl",
        checkpoint_key="finops:kb:checkpoint",
        authorized=True,
        log=lambda _msg: None,
    )
    options.update(kwargs)
    return OutboxPublisher(db, **options)


def enqueue(db, run_id, *, record=None, **payload_kwargs):
    """Queue one knowledge payload and return the outbox row."""
    rec = record or make_record()
    return db.enqueue_outbox_event(
        run_id, knowledge_payload(rec, make_event(rec), **payload_kwargs)
    )


# ── 1. The payload contract ──────────────────────────────────────────────────────────────────


def test_payload_carries_the_event_verbatim():
    """The stored envelope IS the producer's — nothing is re-derived on the way to the stream."""
    record = make_record()
    event = make_event(record, operation="supersede", reason="spec-lifecycle-content=abc")
    payload = knowledge_payload(record, event)

    assert payload["payload_version"] == PAYLOAD_VERSION
    assert payload["kind"] == KIND_KNOWLEDGE_EVENT
    # Byte-for-byte the producer's dict, not a reconstruction of it.
    assert payload["event"] == event.to_dict()
    assert payload["record"] == record.to_dict()


def test_payload_defaults_to_no_checkpoint():
    """The weaker claim is the default: a caller that says nothing gets no dedup marker.

    The safe direction — a missing checkpoint costs a duplicate event that consumers already
    de-duplicate on ``knowledge_id``; a spurious one would SUPPRESS a real emission.
    """
    assert knowledge_payload(make_record(), make_event(make_record()))["checkpoint"] is False


def test_registry_lines_match_the_producers_shape():
    """An upsert renders one line; a supersede also closes out its predecessor."""
    record = make_record()
    upsert = registry_lines_for(record, operation="upsert", reason="fact-content=1")
    assert len(upsert) == 1
    assert upsert[0]["lifecycle_state"] == "current"
    assert upsert[0]["knowledge_id"] == record.knowledge_id

    superseding = make_record(supersedes="p" * 64)
    lines = registry_lines_for(superseding, operation="supersede", reason="fact-content=2")
    assert len(lines) == 2
    assert lines[0]["lifecycle_state"] == "current"
    # The predecessor line is its own append — the registry index is append-only, so nothing
    # back-writes the earlier row.
    assert lines[1]["knowledge_id"] == "p" * 64
    assert lines[1]["lifecycle_state"] == "superseded"
    assert lines[1]["valid_to"] == superseding.valid_from


def test_a_tombstone_renders_as_tombstoned():
    """The negative direction of the lifecycle mapping: delete is not 'current'."""
    lines = registry_lines_for(make_record(), operation="delete", reason="gone")
    assert lines[0]["lifecycle_state"] == "tombstoned"
    assert len(lines) == 1


# ── 2. The ack ordering (the at-least-once guarantee) ────────────────────────────────────────


def test_a_row_flips_to_delivered_only_after_the_stream_acknowledges(db, run_id, tmp_path):
    """The positive direction: an ack, then — and only then — the delivered mark."""
    stream = FakeStream()
    row = enqueue(db, run_id)
    assert db.get_outbox_event(row.event_id).status is OutboxStatus.PENDING

    report = publisher(db, stream, tmp_path).drain()

    assert report.delivered == 1
    assert len(stream.published) == 1
    stored = db.get_outbox_event(row.event_id)
    assert stored.status is OutboxStatus.DELIVERED
    assert stored.delivered_at != ""


def test_a_row_stays_pending_when_the_stream_never_acknowledges(db, run_id, tmp_path):
    """The negative direction — the one that matters.

    The publish raises (no ack), so the row must NOT be delivered. This is the whole
    at-least-once claim: an unacknowledged event is still owed.
    """
    stream = FakeStream(fail_times=1)
    row = enqueue(db, run_id)

    report = publisher(db, stream, tmp_path).drain()

    assert report.delivered == 0
    assert report.retried == 1
    stored = db.get_outbox_event(row.event_id)
    assert stored.status is OutboxStatus.PENDING
    assert stored.delivered_at == ""
    assert "stream rejected" in stored.last_error


def test_the_mark_happens_after_the_publish_not_before(db, run_id, tmp_path):
    """Ordering proved directly: at publish time the row is still pending.

    A publisher that marked first and published second would pass every other test in this
    file — the counters would look identical — and would lose an event on any crash in the
    gap. This test is the only thing that can tell the two implementations apart.
    """
    seen_status: list[OutboxStatus] = []
    row_holder: dict[str, str] = {}

    def publish_and_peek(client, event, *, source_type="", authorized=False):
        # Observed from INSIDE the publish call: the database must still say pending.
        seen_status.append(db.get_outbox_event(row_holder["id"]).status)
        return "1700000000-1"

    stream = FakeStream()
    row = enqueue(db, run_id)
    row_holder["id"] = row.event_id

    publisher(db, stream, tmp_path, publish=publish_and_peek).drain()

    assert seen_status == [OutboxStatus.PENDING]
    assert db.get_outbox_event(row.event_id).status is OutboxStatus.DELIVERED


def test_the_artifact_lands_before_the_pointer_event(db, run_id, tmp_path):
    """A consumer must never see a pointer to bytes that are not on disk yet."""
    record = make_record()
    artifact = tmp_path / "kb" / f"{record.knowledge_id}.json"
    saw_artifact: list[bool] = []

    def publish_and_peek(client, event, *, source_type="", authorized=False):
        saw_artifact.append(artifact.exists())
        return "1700000000-1"

    enqueue(db, run_id, record=record)
    publisher(db, FakeStream(), tmp_path, publish=publish_and_peek).drain()

    assert saw_artifact == [True]
    # The artifact BLANKS ids and timestamps by design (``record_to_artifact``'s stable-content
    # contract — that is what keeps ``content_hash`` identical across re-derivations), so the
    # body is what identifies it, not the id field.
    assert json.loads(artifact.read_text())["text"] == record.text


def test_redelivery_after_a_crash_between_ack_and_mark(db, run_id, tmp_path):
    """At-least-once, demonstrated: a crash in the gap re-delivers rather than losing.

    Simulates the crash by publishing successfully and then failing before the mark. The row
    stays pending, and the next drain publishes it again — a duplicate the consumers
    de-duplicate on ``knowledge_id``, which is exactly the trade at-least-once makes.
    """
    stream = FakeStream()
    row = enqueue(db, run_id)

    class CrashingDB:
        """The real db, with the delivered-mark sabotaged exactly once."""

        def __init__(self, inner):
            self._inner = inner
            self.crashed = False

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def mark_outbox_delivered(self, event_id, **kwargs):
            if not self.crashed:
                self.crashed = True
                raise OSError("power loss between the ack and the mark")
            return self._inner.mark_outbox_delivered(event_id, **kwargs)

    crashing = CrashingDB(db)
    first = publisher(crashing, stream, tmp_path, policy=BackoffPolicy(base_seconds=0)).drain()

    assert len(stream.published) == 1  # the event DID reach the stream
    assert first.retried == 1  # ...but the row is still owed
    assert db.get_outbox_event(row.event_id).status is OutboxStatus.PENDING

    second = publisher(db, stream, tmp_path).drain()
    assert second.delivered == 1
    assert len(stream.published) == 2  # re-delivered, never lost


# ── 3. Backoff and the dead-letter cap ───────────────────────────────────────────────────────


def test_backoff_grows_then_holds_at_the_ceiling():
    """Exponential from the base, capped — a long outage must not retry once a day."""
    policy = BackoffPolicy(base_seconds=2.0, factor=3.0, max_seconds=100.0)
    assert policy.delay_for(1) == 2.0  # the first failure waits exactly the base
    assert policy.delay_for(2) == 6.0
    assert policy.delay_for(3) == 18.0
    assert policy.delay_for(10) == 100.0  # held at the ceiling, not unbounded


def test_a_backoff_that_cannot_retry_is_refused():
    """The negative direction on the policy itself: a shrinking or zero-attempt cap is a bug."""
    with pytest.raises(ValueError):
        BackoffPolicy(max_attempts=0)
    with pytest.raises(ValueError):
        BackoffPolicy(factor=0.5)


def test_a_failed_delivery_schedules_a_retry_in_the_future(db, run_id, tmp_path):
    """The failed row records its error, bumps attempts, and is NOT eligible again yet."""
    now = datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)
    stream = FakeStream(fail_times=1)
    row = enqueue(db, run_id)

    publisher(db, stream, tmp_path, clock=lambda: now).drain()

    stored = db.get_outbox_event(row.event_id)
    assert stored.status is OutboxStatus.PENDING
    assert stored.attempts == 1
    assert stored.next_retry_at > _iso(now)  # scheduled forward, not immediately eligible
    # ...and the backoff is enforced by the query, not merely recorded:
    assert db.pending_outbox_events(now=_iso(now)) == []
    assert len(db.pending_outbox_events(now=_iso(now + timedelta(seconds=10)))) == 1


def test_a_row_goes_dead_after_the_attempt_cap_and_no_later(db, run_id, tmp_path):
    """Both directions of the cap: alive at N-1 attempts, dead at exactly N."""
    policy = BackoffPolicy(max_attempts=3, base_seconds=0)
    stream = FakeStream(fail_times=99)
    row = enqueue(db, run_id)
    pub = publisher(db, stream, tmp_path, policy=policy)

    for attempt in (1, 2):
        report = pub.drain()
        assert report.retried == 1, f"attempt {attempt} should still retry"
        assert db.get_outbox_event(row.event_id).status is OutboxStatus.PENDING

    report = pub.drain()  # the third attempt exhausts the budget
    assert report.dead == 1
    stored = db.get_outbox_event(row.event_id)
    assert stored.status is OutboxStatus.DEAD
    assert stored.attempts == 3
    assert "stream rejected" in stored.last_error


def test_a_dead_row_is_never_picked_up_again(db, run_id, tmp_path):
    """Dead is visible, not retried: it stays as an operator-facing hole in the chain."""
    stream = FakeStream(fail_times=99)
    row = enqueue(db, run_id)
    pub = publisher(db, stream, tmp_path, policy=BackoffPolicy(max_attempts=1, base_seconds=0))

    assert pub.drain().dead == 1
    assert pub.drain() == DrainReport()  # nothing examined on the next pass
    assert db.get_outbox_event(row.event_id).status is OutboxStatus.DEAD


def test_an_unreachable_stream_charges_nobody_an_attempt(db, run_id, tmp_path):
    """A connection outage must not spend the whole queue's retry budget at once.

    The deliberate asymmetry against per-row failures: a Redis restart is not evidence that any
    particular payload is undeliverable, and charging all N queued rows for one outage is how a
    30-second blip turns a full queue dead.
    """
    rows = [enqueue(db, run_id, record=make_record(str(i) * 64)) for i in range(3)]

    def refuse():
        raise ConnectionError("Connection refused")

    report = publisher(db, FakeStream(), tmp_path, connect=refuse).drain()

    assert report.stream_error.startswith("ConnectionError")
    assert report.examined == 0
    for row in rows:
        stored = db.get_outbox_event(row.event_id)
        assert stored.status is OutboxStatus.PENDING
        assert stored.attempts == 0  # untouched, not charged


def test_a_malformed_payload_dies_immediately_rather_than_burning_retries(db, run_id, tmp_path):
    """A permanent defect is diagnosed once, not N times.

    An unknown payload version reads the same on the fifth attempt as on the first, so spending
    four more attempts to reach the same conclusion is pure latency in front of an alert.
    """
    row = db.enqueue_outbox_event(run_id, {"payload_version": "from-the-future/v9", "kind": "x"})

    report = publisher(db, FakeStream(), tmp_path, policy=BackoffPolicy(max_attempts=5)).drain()

    assert report.dead == 1
    stored = db.get_outbox_event(row.event_id)
    assert stored.status is OutboxStatus.DEAD
    assert stored.attempts == 1  # ONE attempt, not five
    assert "payload_version" in stored.last_error


def test_a_payload_missing_a_required_key_is_also_permanent(db, run_id, tmp_path):
    """The other malformed shape: right version, missing body."""
    row = db.enqueue_outbox_event(
        run_id, {"payload_version": PAYLOAD_VERSION, "kind": KIND_KNOWLEDGE_EVENT}
    )
    assert publisher(db, FakeStream(), tmp_path).drain().dead == 1
    assert "missing required key" in db.get_outbox_event(row.event_id).last_error


# ── 4. Idempotence (the checkpoint) ──────────────────────────────────────────────────────────


def test_an_already_checkpointed_event_is_not_republished(db, run_id, tmp_path):
    """The obligation is discharged, so the row is closed WITHOUT a duplicate emission."""
    record = make_record()
    stream = FakeStream()
    stream.checkpoints["finops:kb:checkpoint"] = {record.knowledge_id: "2026-09-01T00:00:00Z"}
    row = enqueue(db, run_id, record=record, checkpoint=True)

    report = publisher(db, stream, tmp_path).drain()

    assert report.skipped == 1
    assert stream.published == []  # nothing re-emitted
    assert db.get_outbox_event(row.event_id).status is OutboxStatus.DELIVERED


def test_a_checkpointing_payload_writes_the_checkpoint_after_delivery(db, run_id, tmp_path):
    """The positive direction: the marker the NEXT drain reads is written on success."""
    record = make_record()
    stream = FakeStream()
    enqueue(db, run_id, record=record, checkpoint=True)

    publisher(db, stream, tmp_path).drain()

    assert stream.checkpoints["finops:kb:checkpoint"][record.knowledge_id] == record.indexed_at


def test_a_non_checkpointing_payload_writes_no_checkpoint(db, run_id, tmp_path):
    """The negative direction: the spec producer never checkpointed, and still does not."""
    stream = FakeStream()
    enqueue(db, run_id, checkpoint=False)

    publisher(db, stream, tmp_path).drain()

    assert stream.published  # it WAS delivered...
    assert stream.checkpoints == {}  # ...without acquiring a marker it never had


def test_registry_lines_are_appended_after_a_successful_delivery(db, run_id, tmp_path):
    """The F2 emit-time materialization survives the move behind the outbox."""
    record = make_record()
    payload = knowledge_payload(
        record,
        make_event(record),
        registry_lines=registry_lines_for(record, operation="upsert", reason="fact-content=1"),
    )
    db.enqueue_outbox_event(run_id, payload)

    publisher(db, FakeStream(), tmp_path).drain()

    lines = (tmp_path / "registry_index.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["knowledge_id"] == record.knowledge_id


def test_a_failed_delivery_appends_no_registry_line(db, run_id, tmp_path):
    """The negative direction: no ack, no registry row claiming the event exists."""
    record = make_record()
    db.enqueue_outbox_event(
        run_id,
        knowledge_payload(
            record,
            make_event(record),
            registry_lines=registry_lines_for(record, operation="upsert", reason="r"),
        ),
    )
    publisher(db, FakeStream(fail_times=1), tmp_path).drain()
    assert not (tmp_path / "registry_index.jsonl").exists()


def test_post_ack_bookkeeping_failure_does_not_undeliver(db, run_id, tmp_path):
    """The event is on the stream; a checkpoint-write failure must not re-publish it.

    Re-publishing would duplicate an event whose de-duplication marker is exactly what failed
    to write — the worst of both outcomes.
    """
    class BrokenCheckpoint(FakeStream):
        def hset(self, key, field, value):
            raise ConnectionError("checkpoint hash unavailable")

    stream = BrokenCheckpoint()
    row = enqueue(db, run_id, checkpoint=True)

    report = publisher(db, stream, tmp_path).drain()

    assert report.delivered == 1
    assert len(stream.published) == 1
    assert db.get_outbox_event(row.event_id).status is OutboxStatus.DELIVERED


def test_a_checkpoint_read_failure_retries_rather_than_duplicating(db, run_id, tmp_path):
    """Defaulting an unreadable checkpoint to 'not checkpointed' would duplicate on every blip."""
    class BrokenRead(FakeStream):
        def hget(self, key, field):
            raise ConnectionError("checkpoint hash unavailable")

    stream = BrokenRead()
    row = enqueue(db, run_id, checkpoint=True)

    report = publisher(db, stream, tmp_path).drain()

    assert report.retried == 1
    assert stream.published == []
    assert db.get_outbox_event(row.event_id).status is OutboxStatus.PENDING


# ── 5. Envelope fidelity (the consumer-facing claim) ─────────────────────────────────────────


def test_the_delivered_envelope_is_identical_to_the_direct_publish_path(db, run_id, tmp_path):
    """Only the delivery PATH differs — the pointer envelope is unchanged.

    This is the claim the existing ``kb-chroma-v1`` / ``kb-neo4j-v1`` / ``kb-ledger-v1`` /
    ``kb-registry-v1`` consumer groups depend on: they parse ``KnowledgeEvent.to_dict()``, and
    a routing change that altered one field would break every one of them.
    """
    record = make_record()
    direct = make_event(record, operation="supersede", reason="fact-content=cafe")
    stream = FakeStream()
    db.enqueue_outbox_event(run_id, knowledge_payload(record, direct))

    publisher(db, stream, tmp_path).drain()

    delivered_event, source_type, authorized = stream.published[0]
    assert delivered_event == direct.to_dict()  # field for field, including operation/reason
    assert source_type == record.source_type  # the family gate still sees the real source_type
    assert authorized is True


def test_the_delivered_event_round_trips_through_knowledge_event(db, run_id, tmp_path):
    """A consumer reconstructing the event from the stream gets the producer's object back."""
    record = make_record()
    original = make_event(record)
    stream = FakeStream()
    db.enqueue_outbox_event(run_id, knowledge_payload(record, original))

    publisher(db, stream, tmp_path).drain()

    assert KnowledgeEvent.from_dict(stream.published[0][0]) == original


def test_the_write_guard_still_applies(db, run_id, tmp_path):
    """The publisher does not self-authorize: ``authorized`` is forwarded, never assumed.

    The guard moved behind the one emission path; it was not weakened. An unauthorized drain
    raises exactly what the direct path raised — and the row stays owed.
    """
    def guarded_publish(client, event, *, source_type="", authorized=False):
        if not authorized:
            raise RuntimeError("knowledge write not authorized: set FINOPS_KB_WRITE=1")
        return "1700000000-1"

    row = enqueue(db, run_id)
    report = publisher(
        db, FakeStream(), tmp_path, publish=guarded_publish, authorized=False
    ).drain()

    assert report.delivered == 0
    assert "not authorized" in db.get_outbox_event(row.event_id).last_error
    assert db.get_outbox_event(row.event_id).status is OutboxStatus.PENDING


# ── 6. The parent's atomic terminal write ────────────────────────────────────────────────────


def test_the_terminal_write_records_transition_envelope_and_events(db, run_id):
    """All three mandated facts land in one commit."""
    payloads = [knowledge_payload(make_record(str(i) * 64), make_event(make_record())) for i in range(3)]

    write = record_terminal_run(
        db,
        run_id,
        state=RunState.PROMOTABLE,
        payloads=payloads,
        cost_usd=1.25,
        ledger_path="experiments/results/workflows/x/20260902T000000Z.json",
        candidate_sha="c" * 40,
    )

    assert write.run.state is RunState.PROMOTABLE  # 1. the transition
    assert write.run.cost_usd == 1.25  # 2. the result envelope
    assert write.run.ledger_path.endswith("20260902T000000Z.json")
    assert write.run.candidate_sha == "c" * 40
    assert len(write.events) == 3  # 3. the events it owes
    assert all(e.status is OutboxStatus.PENDING for e in db.outbox_events(run_id=run_id))


def test_the_terminal_write_is_atomic_a_crash_mid_write_leaves_nothing(db, run_id):
    """The core atomicity claim, proved by crashing between the two halves.

    A failure while queueing the events must roll the TRANSITION back too. The alternative — a
    run recorded as terminal whose events were never queued — is precisely the silent hole the
    outbox exists to close, and it would be invisible: the run would look finished.
    """
    good = knowledge_payload(make_record("1" * 64), make_event(make_record()))

    class Unserializable:
        """Fails at json.dumps time — i.e. INSIDE the transaction, after the transition."""

        def __repr__(self):
            raise ValueError("boom mid-write")

    # ValueError specifically: `json.dumps(..., default=str)` falls back to `str()`, which
    # reaches the raising `__repr__`. Naming the type keeps this a test of the ROLLBACK, not a
    # test that "something went wrong somewhere".
    with pytest.raises(ValueError):
        record_terminal_run(
            db,
            run_id,
            state=RunState.PROMOTABLE,
            payloads=[good, {"payload_version": PAYLOAD_VERSION, "bad": Unserializable()}],
            cost_usd=9.99,
        )

    # NEITHER half survived: not the transition, not the first (already-queued) event.
    run = db.get_run(run_id)
    assert run.state is RunState.RUNNING
    assert run.cost_usd == 0.0
    assert db.outbox_events(run_id=run_id) == []
    assert [t.to_state for t in db.transitions(run_id)] == [RunState.RUNNING]


def test_the_terminal_write_commits_both_halves_or_neither_positive_direction(db, run_id):
    """The other direction of the same rule: a clean write leaves BOTH halves."""
    record_terminal_run(
        db, run_id, state=RunState.FAILED,
        payloads=[knowledge_payload(make_record(), make_event(make_record()))],
    )
    assert db.get_run(run_id).state is RunState.FAILED
    assert len(db.outbox_events(run_id=run_id)) == 1


def test_the_terminal_write_refuses_an_illegal_transition_and_queues_nothing(db, run_id):
    """A rejected transition must not leave orphan events for a termination that never happened."""
    db.transition_run(run_id, RunState.FAILED)  # already terminal

    with pytest.raises(TerminalStateError):
        record_terminal_run(
            db, run_id, state=RunState.PROMOTABLE,
            payloads=[knowledge_payload(make_record(), make_event(make_record()))],
        )

    assert db.outbox_events(run_id=run_id) == []


def test_the_terminal_write_records_ended_at_on_a_terminal_state(db, run_id):
    """The terminal transition is the LAST moment the envelope can be recorded — so it is."""
    write = record_terminal_run(db, run_id, state=RunState.FAILED, cost_usd=0.5)
    assert write.run.ended_at != ""
    # And immutability then holds: nothing may edit the row afterwards.
    with pytest.raises(TerminalStateError):
        db.transition_run(run_id, RunState.PROMOTABLE)


# ── 7. The operator's view ───────────────────────────────────────────────────────────────────


def test_summarize_partitions_the_rows_and_names_the_dead(db, run_id, tmp_path):
    """A dead-event count without ids is an alert nobody can act on."""
    delivered_row = enqueue(db, run_id, record=make_record("a" * 64))
    dead_row = enqueue(db, run_id, record=make_record("b" * 64))
    enqueue(db, run_id, record=make_record("c" * 64))  # stays pending

    db.mark_outbox_delivered(delivered_row.event_id)
    db.mark_outbox_dead(dead_row.event_id, error="gave up")

    summary = summarize(db, run_id=run_id)
    assert (summary.pending, summary.delivered, summary.dead) == (1, 1, 1)
    assert summary.dead_event_ids == (dead_row.event_id,)
    assert summary.oldest_pending_at != ""


def test_drain_report_counters_partition_the_examined_rows(db, run_id, tmp_path):
    """delivered + skipped + retried + dead == examined — the parts add up to the whole."""
    ok = make_record("1" * 64)
    already = make_record("2" * 64)
    enqueue(db, run_id, record=ok)
    enqueue(db, run_id, record=already, checkpoint=True)
    db.enqueue_outbox_event(run_id, {"payload_version": "nope/v1"})

    stream = FakeStream()
    stream.checkpoints["finops:kb:checkpoint"] = {already.knowledge_id: "2026-09-01T00:00:00Z"}
    report = publisher(db, stream, tmp_path).drain()

    assert (report.delivered, report.skipped, report.dead) == (1, 1, 1)
    assert report.examined == 3
    assert report.to_dict()["examined"] == 3


def test_drain_respects_the_limit(db, run_id, tmp_path):
    """A bounded drain leaves the rest queued rather than silently truncating the obligation."""
    for i in range(3):
        enqueue(db, run_id, record=make_record(str(i) * 64))

    report = publisher(db, FakeStream(), tmp_path).drain(limit=2)

    assert report.delivered == 2
    assert summarize(db, run_id=run_id).pending == 1


def _iso(moment: datetime) -> str:
    """The control-db timestamp shape (``Z`` suffix), used for the eligibility assertions."""
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
