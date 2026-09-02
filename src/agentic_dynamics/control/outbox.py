"""Transactional outbox — the ONE emission path (``control_db_publication`` p2).

Why this module exists
----------------------
Before it, a workflow run's knowledge emission was **best-effort fire-and-forget**. Two call
sites in ``scripts/run_workflow.py`` (``_emit_spec_record`` and ``_emit_workflow_facts``) each
did the same thing: derive some records, open Redis, publish, and swallow every exception into
a printed warning. That posture was deliberate and, for its purpose, correct — a finished run
must never fail because the knowledge stream was down. But it bought that safety with a real
loss: when the stream *was* down, the events were **gone**. Nothing recorded that they had been
owed. The registry silently fell behind the ledgers, and the only way to notice was to count
artifacts against registry rows after the fact (the "F2 materialization stall").

This module replaces "try to emit, shrug on failure" with the transactional-outbox pattern:

1. **Enqueue is transactional.** The parent run's terminal write puts the events it owes into
   the ``outbox`` table *in the same SQLite transaction* as the run's state transition. Either
   the run is recorded as terminal **and** its events are durably queued, or neither happened.
   There is no window in which the state moved but the emission was lost, because the two facts
   are one commit.
2. **Delivery is at-least-once.** :class:`OutboxPublisher` drains the table: for each pending
   row it publishes to the knowledge stream and marks the row ``delivered`` **only after the
   stream acknowledges**. A crash between the ack and the mark re-delivers the event (harmless
   — consumers key on ``knowledge_id``); the opposite order would lose it silently, which is
   the exact failure this module exists to remove.
3. **Failure is visible, not silent.** A delivery that fails retries with exponential backoff
   and, after :attr:`BackoffPolicy.max_attempts`, becomes ``dead`` — a row that stays in the
   table forever with its ``last_error``. An undelivered knowledge event is a hole in the
   projection chain, and an operator has to be able to find it. "Dead" is an alert; a swallowed
   exception was not.

What the publisher deliberately does NOT know
---------------------------------------------
The control plane must not learn how to *derive* knowledge records. Every producer (facts,
spec lifecycle, stories, reviews…) has its own rules for the pointer event's ``operation`` and
``reason``, its own registry-line shape, and its own view of whether a checkpoint applies. So
the payload written into the outbox is **fully derived at enqueue time by the producer's own
helpers** (``control.fact_ingestion.fact_event``, ``knowledge.spec_ingestion.spec_event``, …)
and this module is a faithful delivery mechanism over it:

* the event dict is stored **verbatim**, so the envelope that lands on the stream is byte-for-
  byte the one the old direct-publish path would have produced. That is what makes "the
  existing consumer groups still consume the same event shape" a testable claim rather than a
  hope — only the delivery *path* changed;
* the record dict is stored so the publisher can rebuild the durable artifact
  (``record_to_artifact`` is deterministic and content-addressed by construction), preserving
  the universal producer ordering: **artifact first, then the pointer event** — a consumer must
  never see a pointer to bytes that are not on disk yet;
* the registry lines are stored pre-rendered, because their ``operation``/``reason`` derivation
  is producer-specific (``fact_reason`` vs ``spec_reason`` vs ``pattern_projection_reason``).

Layering
--------
``control`` is tier 2 and ``knowledge`` is tier 1, so importing the stream seam here is with
the dependency direction, not against it (``tests/test_dependency_direction.py``). The Redis
handle and the publish function are both **injected** (see :class:`OutboxPublisher`), which is
what lets the tests below prove the ack-ordering and backoff rules without a live Redis.

What this phase does NOT do
---------------------------
The phase scope fence is real. This module owns the publisher and the parent's atomic terminal
write. It does not refresh projection watermarks from consumer groups (p3), does not render the
control packet (p4), and does not touch the instruction surfaces (p5) or publication (p6).
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agentic_dynamics.control.control_db import (
    ControlDB,
    ControlDBError,
    OutboxRecord,
    OutboxStatus,
    RunRecord,
    RunState,
)

# ── The payload contract ─────────────────────────────────────────────────────────────────────

#: Version tag on every payload this module writes. Bumped when the payload SHAPE changes in a
#: way an older publisher could misread. A publisher that meets an unknown version refuses the
#: row (see :meth:`OutboxPublisher._deliver`) rather than guessing at its fields — a half-
#: understood emission is worse than a visible dead row.
PAYLOAD_VERSION = "control-outbox-payload/v1"

#: The only payload kind p2 delivers: one knowledge-stream pointer event plus the durable
#: artifact and bookkeeping that accompany it. Declared as a named constant (rather than
#: assumed) so a future kind — a webhook, a Control Room notification — is an explicit
#: addition with its own branch, never a silent reinterpretation of these rows.
KIND_KNOWLEDGE_EVENT = "knowledge_event"

#: Every kind this publisher understands. Membership is checked before delivery.
KNOWN_KINDS: frozenset[str] = frozenset({KIND_KNOWLEDGE_EVENT})


class OutboxError(ControlDBError):
    """Base class for outbox delivery refusals.

    Subclasses :class:`~agentic_dynamics.control.control_db.ControlDBError` so a caller that
    already handles "the control plane refused something" catches these too.
    """


class MalformedPayloadError(OutboxError):
    """A row's payload cannot be delivered as written — a *permanent* failure.

    Distinguished from a transport failure on purpose: retrying a payload whose version is
    unknown or whose required keys are missing will never succeed, so such a row goes straight
    to ``dead`` instead of burning the retry budget to reach the same conclusion N attempts
    later.
    """


# ── Retry policy ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BackoffPolicy:
    """Exponential backoff with a cap, and a hard attempt ceiling.

    The defaults deliver quickly on a transient blip (2s, 6s, 18s, 54s…) while a long outage
    settles onto :attr:`max_seconds` rather than growing without bound — an event owed to the
    knowledge stream should be re-tried every few minutes for as long as it is worth trying at
    all, not once a day.

    :attr:`max_attempts` is the ceiling the mandate calls for ("escalating to dead after N
    attempts"). It counts *delivery attempts*, not retries: with ``max_attempts=5`` a row is
    published at most five times before it is declared dead.
    """

    #: How many delivery attempts a row gets before it is declared ``dead``.
    max_attempts: int = 5
    #: Delay after the first failure.
    base_seconds: float = 2.0
    #: Multiplier applied per subsequent failure.
    factor: float = 3.0
    #: Ceiling on the computed delay, so a long outage does not push the next try past the
    #: point where anyone is still watching.
    max_seconds: float = 900.0

    def __post_init__(self) -> None:
        """Refuse a policy that cannot express a retry — a silent no-retry cap is a trap."""
        if self.max_attempts < 1:
            raise ValueError("BackoffPolicy.max_attempts must be >= 1")
        if self.base_seconds < 0 or self.max_seconds < 0:
            raise ValueError("BackoffPolicy delays must be non-negative")
        if self.factor < 1:
            raise ValueError("BackoffPolicy.factor must be >= 1 (a shrinking backoff is a bug)")

    def delay_for(self, attempts: int) -> float:
        """Seconds to wait after ``attempts`` failed deliveries (1 = the first failure)."""
        # `attempts - 1` so the FIRST failure waits exactly `base_seconds` rather than
        # base * factor — the common case (one transient blip) should retry fast.
        exponent = max(0, attempts - 1)
        return min(self.base_seconds * (self.factor**exponent), self.max_seconds)

    def next_retry_at(self, attempts: int, *, now: datetime) -> str:
        """ISO-8601 stamp of the earliest legal next attempt (the value stored on the row)."""
        return _iso(now + timedelta(seconds=self.delay_for(attempts)))

    def is_exhausted(self, attempts: int) -> bool:
        """Has a row that has now failed ``attempts`` times run out of budget?"""
        return attempts >= self.max_attempts


# ── Reports ──────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DrainReport:
    """The outcome of one :meth:`OutboxPublisher.drain` pass — every row accounted for.

    The five counters partition the rows the pass examined, which is deliberate: a summary in
    which the parts do not add up to the whole is how "we emitted everything" quietly becomes
    "we emitted what did not error".
    """

    #: Rows published to the stream and marked ``delivered`` on this pass.
    delivered: int = 0
    #: Rows already present in the consumer checkpoint — the event was emitted by an earlier
    #: pass (or the pre-outbox path) and re-publishing would be a duplicate. Marked delivered
    #: without re-publishing.
    skipped: int = 0
    #: Rows whose delivery failed and which are scheduled for another attempt.
    retried: int = 0
    #: Rows that exhausted the attempt budget, or whose payload was permanently malformed.
    dead: int = 0
    #: Set when the pass could not reach the stream at all. **No row is charged an attempt in
    #: this case** — see :meth:`OutboxPublisher.drain` for why an outage must not consume the
    #: retry budget of every queued event at once.
    stream_error: str = ""

    @property
    def examined(self) -> int:
        """Rows this pass reached a decision about."""
        return self.delivered + self.skipped + self.retried + self.dead

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready rendering (what the composition root prints and p4's packet can read)."""
        return {
            "delivered": self.delivered,
            "skipped": self.skipped,
            "retried": self.retried,
            "dead": self.dead,
            "examined": self.examined,
            "stream_error": self.stream_error,
        }


@dataclass(frozen=True)
class TerminalWrite:
    """What the parent's atomic terminal write recorded — the receipt for one commit."""

    run: RunRecord
    events: tuple[OutboxRecord, ...] = ()

    @property
    def event_ids(self) -> tuple[str, ...]:
        """The outbox ids queued by this write, in order."""
        return tuple(e.event_id for e in self.events)


# ── Payload construction (the producer-facing half) ──────────────────────────────────────────


def knowledge_payload(
    record: Any,
    event: Any,
    *,
    checkpoint: bool = False,
    registry_lines: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Build the outbox payload for ONE derived knowledge record + its pointer event.

    Called by the producer side (the composition root), which already holds both objects — the
    control plane never derives them itself (see the module docstring on layering).

    ``event`` is serialized **verbatim**: whatever the producer's own event builder returned is
    exactly what will reach the stream, so routing this emission through the outbox cannot
    change the envelope. ``record`` travels alongside it because the publisher must write the
    durable artifact before the pointer lands, and ``record_to_artifact`` is the only thing that
    knows how.

    ``checkpoint`` mirrors the producer's existing behaviour rather than imposing one: the fact
    producer (``kb_produce_facts.emit_records``) checkpoints each ``knowledge_id`` so a re-run
    skips it, while the spec-lifecycle producer (``spec_ingestion.emit_spec_record``) does not
    checkpoint at all — it decides "unchanged?" from the registry head instead. Defaulting to
    ``False`` means a caller that says nothing gets the *weaker* claim (no dedup marker), which
    is the safe direction: a missing checkpoint costs a duplicate event that consumers already
    de-duplicate on ``knowledge_id``, whereas a spurious one would suppress a real emission.

    ``registry_lines`` are pre-rendered by the producer (see :func:`registry_lines_for`) because
    the ``operation``/``reason`` derivation differs per source family.
    """
    return {
        "payload_version": PAYLOAD_VERSION,
        "kind": KIND_KNOWLEDGE_EVENT,
        # Hoisted out of the nested dicts so an operator can grep the outbox table for an id
        # without parsing JSON, and so the publisher can consult the checkpoint before it
        # reconstructs anything.
        "knowledge_id": record.knowledge_id,
        "source_type": record.source_type,
        "checkpoint": bool(checkpoint),
        "checkpoint_value": record.indexed_at,
        "event": event.to_dict(),
        "record": record.to_dict(),
        "registry_lines": [dict(line) for line in registry_lines],
    }


def registry_lines_for(record: Any, *, operation: str, reason: str) -> list[dict[str, Any]]:
    """Render the append-only registry index line(s) for one record.

    Field-for-field the shape ``scripts/kb_produce_facts._materialize_registry_row`` writes (and
    the ``kb-registry-v1`` consumer writes), lifted here so the publisher can append it after a
    successful delivery. The duplicate line a later consumer pass appends is byte-identical and
    ``generate_manifest.py``'s latest-per-entity compaction folds it away — the same tolerance
    the existing producer path already relies on.

    ``operation``/``reason`` are parameters rather than derived here on purpose: they come from
    the producer's own helpers (``fact_operation``/``fact_reason``, ``spec_operation``/
    ``spec_reason``, ``pattern_projection_reason``), and re-deriving them in the control plane
    would be a second implementation free to drift from the first.
    """
    lifecycle = "current" if operation in ("upsert", "supersede") else "tombstoned"
    lines: list[dict[str, Any]] = [
        {
            "knowledge_id": record.knowledge_id,
            "entity_id": record.entity_id,
            "source_type": record.source_type,
            "logical_locator": record.logical_locator,
            "source_uri": record.source_uri,
            "lifecycle_state": lifecycle,
            "observed_at": record.observed_at,
            "indexed_at": record.indexed_at,
            "supersedes": record.supersedes,
            "causes": record.causes,
            "reason": reason,
        }
    ]
    if operation == "supersede" and record.supersedes:
        # The predecessor line: the superseded version is closed out at the successor's
        # valid_from. Written as its own line because the registry index is append-only —
        # nothing back-writes the earlier row.
        lines.append(
            {
                "knowledge_id": record.supersedes,
                "entity_id": record.entity_id,
                "lifecycle_state": "superseded",
                "valid_to": record.valid_from,
                "indexed_at": record.indexed_at,
            }
        )
    return lines


# ── The atomic parent write ──────────────────────────────────────────────────────────────────


def record_terminal_run(
    db: ControlDB,
    run_id: str,
    *,
    state: RunState | str,
    payloads: Iterable[dict[str, Any]] = (),
    reason: str = "",
    actor: str = "orchestrator",
    cost_usd: float | None = None,
    ledger_path: str | None = None,
    candidate_sha: str | None = None,
    ended_at: str | None = None,
    at: str | None = None,
) -> TerminalWrite:
    """Write a run's termination and everything it owes downstream in ONE transaction.

    This is the parent-run atomic write the mandate calls for. In a single
    :meth:`ControlDB.transaction` (``BEGIN IMMEDIATE`` … ``COMMIT``) it records:

    1. **the run state transition** — ``running`` → the control-vocabulary state the ledger's
       outcome maps to (``promotable``/``awaiting_approval``/``failed``/``cancelled``, via
       :func:`~agentic_dynamics.control.control_db.run_state_from_ledger_state`);
    2. **the run result envelope** — the run row's ``ledger_path`` (the pointer to the envelope
       JSON the runner just wrote), ``cost_usd``, ``candidate_sha`` and ``ended_at``. These are
       passed to :meth:`ControlDB.transition_run` rather than written afterwards because a
       terminal state is immutable: the terminal transition is the *last* moment they can be
       recorded at all;
    3. **the events the run owes the knowledge stream** — one ``pending`` outbox row per
       payload.

    Atomicity is the whole point. If anything raises part-way — a rejected transition, a
    payload that will not serialize, a disk error — the transaction rolls back and the database
    holds **neither** half: no orphan transition claiming the run ended with its events lost,
    and no queued events for a termination that never happened. That is only true because the
    composition is built from methods that *join* the outer transaction rather than opening
    their own (see :meth:`ControlDB.transaction`'s re-entrancy note).

    Ordering inside the transaction is transition-then-events, which matters for one reason:
    :meth:`ControlDB.enqueue_outbox_event` refuses a row for an unknown run, so the run must
    exist first. It does not matter for atomicity — one commit, one outcome.
    """
    rows: list[OutboxRecord] = []
    with db.transaction():
        run = db.transition_run(
            run_id,
            state,
            reason=reason,
            actor=actor,
            at=at,
            cost_usd=cost_usd,
            candidate_sha=candidate_sha,
            ledger_path=ledger_path,
            ended_at=ended_at,
        )
        for payload in payloads:
            rows.append(db.enqueue_outbox_event(run_id, payload, created_at=at))
    # Re-read outside the transaction so the returned record reflects the committed row rather
    # than a mid-transaction view.
    committed = db.get_run(run_id)
    return TerminalWrite(run=committed or run, events=tuple(rows))


# ── The publisher ────────────────────────────────────────────────────────────────────────────


class OutboxPublisher:
    """Drains the outbox to the knowledge stream — the ONE emission path.

    Every dependency that touches the outside world is injected, for two reasons that are both
    load-bearing:

    * the ack-ordering rule ("mark delivered only after the stream acknowledges") and the
      backoff/dead escalation are the behaviours under test, and they must be provable without
      a live Redis;
    * the write guard is not this module's to weaken. ``publish`` defaults to the real
      :func:`agentic_dynamics.knowledge.knowledge_stream.publish_event`, and ``authorized``
      defaults to ``False``, so an unauthorized process draining the outbox raises exactly the
      same ``RuntimeError`` it would have raised on the direct path. The composition root opts
      in the same way it always did (``_authorized_kb_write()``).
    """

    def __init__(
        self,
        db: ControlDB,
        *,
        connect: Callable[[], Any] | None = None,
        publish: Callable[..., Any] | None = None,
        policy: BackoffPolicy | None = None,
        authorized: bool = False,
        artifact_dir: Path | str | None = None,
        registry_path: Path | str | None = None,
        checkpoint_key: str | None = None,
        clock: Callable[[], datetime] | None = None,
        log: Callable[[str], None] | None = None,
    ) -> None:
        """Wire the publisher. Every argument has a real default; none reaches out at import."""
        self.db = db
        self.policy = policy or BackoffPolicy()
        self.authorized = authorized
        # Resolved at CALL time, never frozen into a default argument. Two real consequences:
        # a containerized orchestrator whose checkout is mounted at a different absolute path
        # gets the right directory, and a test can redirect both without the value having been
        # captured at import.
        self.artifact_dir = Path(artifact_dir) if artifact_dir is not None else _kb_artifact_dir()
        self.registry_path = (
            Path(registry_path) if registry_path is not None else _registry_index_path()
        )
        self._connect = connect
        self._publish = publish
        self._checkpoint_key = checkpoint_key
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        # Defaults to stderr so a drain inside the composition root reports like every other
        # post-run step there (the ledger path, the spec index, the fact emit) without this
        # module deciding to own a logging configuration.
        self._log = log or (lambda msg: print(msg, file=sys.stderr))

    # -- lazily-resolved knowledge-stream seam ------------------------------------------------

    def _stream(self) -> Any:
        """Import the stream module lazily.

        Deferred to call time rather than module import so that merely *importing* the control
        plane (which the Control Room, the supervisor, and every test do) never pulls in redis
        or the knowledge package's optional dependencies.
        """
        from agentic_dynamics.knowledge import knowledge_stream as ks

        return ks

    def _do_connect(self) -> Any:
        """Open the stream connection (injected in tests, real ``ks.connect`` in production)."""
        if self._connect is not None:
            return self._connect()
        return self._stream().connect()

    def _do_publish(self, client: Any, event: Any, *, source_type: str) -> Any:
        """Publish one event and return the stream's acknowledgement (its entry id).

        The return value IS the ack: ``publish_event`` returns whatever ``XADD`` returned. A
        raised exception means no ack, and therefore no ``delivered`` mark.
        """
        if self._publish is not None:
            return self._publish(
                client, event, source_type=source_type, authorized=self.authorized
            )
        return self._stream().publish_event(
            client, event, source_type=source_type, authorized=self.authorized
        )

    def _checkpoint_field(self) -> str:
        """The Redis hash key consumers checkpoint ``knowledge_id``s into."""
        if self._checkpoint_key is not None:
            return self._checkpoint_key
        return str(self._stream().CHECKPOINT_KEY)

    # -- the drain loop -----------------------------------------------------------------------

    def drain(self, *, limit: int | None = None, client: Any = None) -> DrainReport:
        """Deliver every eligible pending row; return an accounting of what happened.

        Eligibility is the database's call, not this loop's: :meth:`ControlDB.pending_outbox_events`
        returns ``pending`` rows whose ``next_retry_at`` has come, oldest first, so backoff is
        enforced by the same query that orders delivery.

        **An unreachable stream charges nobody an attempt.** If the connection itself fails, the
        pass returns immediately with :attr:`DrainReport.stream_error` set and every row left
        untouched. This is a deliberate asymmetry against per-row failures: a Redis restart is
        not evidence that any particular payload is undeliverable, and charging all N queued
        rows an attempt for one outage is how a 30-second blip turns a full queue ``dead``. A
        row's retry budget is spent only on failures the row itself provoked.
        """
        if client is None:
            try:
                client = self._do_connect()
            except Exception as exc:  # noqa: BLE001 — any transport failure, reported not raised
                return DrainReport(stream_error=f"{type(exc).__name__}: {exc}")

        now = self._clock()
        rows = self.db.pending_outbox_events(now=_iso(now), limit=limit)

        delivered = skipped = retried = dead = 0
        for row in rows:
            outcome = self._deliver_row(client, row)
            if outcome == "delivered":
                delivered += 1
            elif outcome == "skipped":
                skipped += 1
            elif outcome == "retried":
                retried += 1
            else:
                dead += 1
        return DrainReport(delivered=delivered, skipped=skipped, retried=retried, dead=dead)

    def _deliver_row(self, client: Any, row: OutboxRecord) -> str:
        """Attempt ONE row; record the result in the database; return the outcome label.

        The two failure classes are handled differently on purpose:

        * :class:`MalformedPayloadError` is **permanent** — an unknown payload version or a
          missing required key will read exactly the same on the fifth attempt as on the first,
          so the row goes straight to ``dead`` with a diagnosis rather than spending four more
          attempts to learn nothing;
        * every other exception is treated as **transient** (the stream rejected it, the guard
          refused, the artifact could not be written) and consumes one attempt from the budget.
        """
        try:
            return self._attempt(client, row)
        except MalformedPayloadError as exc:
            self.db.mark_outbox_dead(row.event_id, error=f"malformed payload: {exc}")
            self._log(f"outbox: {row.event_id} DEAD (malformed payload: {exc})")
            return "dead"
        except Exception as exc:  # noqa: BLE001 — a delivery failure is data, not a crash
            return self._record_failure(row, exc)

    def _record_failure(self, row: OutboxRecord, exc: BaseException) -> str:
        """Charge one attempt: schedule a retry, or declare the row dead if the budget is out."""
        error = f"{type(exc).__name__}: {exc}"
        attempts = row.attempts + 1  # the attempt just made; the DB bumps the stored counter
        if self.policy.is_exhausted(attempts):
            self.db.mark_outbox_dead(row.event_id, error=error)
            self._log(
                f"outbox: {row.event_id} DEAD after {attempts} attempts ({error})"
            )
            return "dead"
        next_at = self.policy.next_retry_at(attempts, now=self._clock())
        self.db.mark_outbox_retry(row.event_id, next_retry_at=next_at, error=error)
        self._log(
            f"outbox: {row.event_id} retry {attempts}/{self.policy.max_attempts} "
            f"at {next_at} ({error})"
        )
        return "retried"

    def _attempt(self, client: Any, row: OutboxRecord) -> str:
        """One delivery attempt, in the order the producer contract requires.

        artifact → publish → **ack** → bookkeeping → mark delivered.

        The artifact lands before the pointer event because a consumer reads the artifact the
        event hashes; publishing first would open a window in which the stream points at bytes
        that are not on disk. The ``delivered`` mark comes last because the ack is the only
        evidence the event exists downstream.
        """
        payload = self._parse(row)

        # Idempotence: the consumer checkpoint already holds this knowledge_id, so the event was
        # emitted before (an earlier drain that crashed after the ack, or the pre-outbox direct
        # path). Re-publishing would be a duplicate; leaving the row pending would retry it
        # forever. Mark it delivered and move on — the obligation IS discharged.
        if payload["checkpoint"] and self._already_checkpointed(client, payload["knowledge_id"]):
            self.db.mark_outbox_delivered(row.event_id)
            return "skipped"

        record, event = self._rebuild(payload)
        self._write_artifact(record)

        # THE ack. Anything raised here means the stream did not take the event, so the row is
        # never marked delivered — it retries. This single ordering is the at-least-once
        # guarantee.
        self._do_publish(client, event, source_type=str(payload["source_type"]))

        # Post-ack bookkeeping. Best-effort BY DESIGN: the event is already on the stream, so a
        # failure here must not un-deliver it (re-publishing would duplicate an event whose
        # checkpoint write is exactly what failed). The canonical registry writer is the
        # kb-registry-v1 consumer; these two writes are the emit-time materialization that makes
        # a row visible without waiting for a worker.
        self._bookkeep(client, payload, record)

        self.db.mark_outbox_delivered(row.event_id)
        return "delivered"

    # -- payload handling ---------------------------------------------------------------------

    def _parse(self, row: OutboxRecord) -> dict[str, Any]:
        """Decode and validate a row's payload, raising :class:`MalformedPayloadError`.

        Validation is strict and up front rather than "read keys as we go": a row that fails
        half-way through delivery would have already written an artifact for an event it cannot
        publish.
        """
        try:
            payload = row.payload
        except Exception as exc:  # noqa: BLE001 — unparseable JSON is a permanent defect
            raise MalformedPayloadError(f"payload is not valid JSON ({exc})") from exc
        if not isinstance(payload, dict):
            raise MalformedPayloadError(f"payload is {type(payload).__name__}, expected an object")
        version = payload.get("payload_version")
        if version != PAYLOAD_VERSION:
            raise MalformedPayloadError(
                f"payload_version {version!r} is not {PAYLOAD_VERSION!r} — refusing to guess "
                f"at a shape this publisher does not understand"
            )
        kind = payload.get("kind")
        if kind not in KNOWN_KINDS:
            raise MalformedPayloadError(
                f"kind {kind!r} is not deliverable by this publisher (known: "
                f"{', '.join(sorted(KNOWN_KINDS))})"
            )
        for key in ("knowledge_id", "source_type", "event", "record"):
            if key not in payload:
                raise MalformedPayloadError(f"payload is missing required key {key!r}")
        payload.setdefault("checkpoint", False)
        payload.setdefault("checkpoint_value", "")
        payload.setdefault("registry_lines", [])
        return payload

    def _rebuild(self, payload: dict[str, Any]) -> tuple[Any, Any]:
        """Reconstruct the ``(record, event)`` pair the producer enqueued.

        ``KnowledgeEvent.from_dict`` of the stored dict is the whole envelope-fidelity claim:
        the publisher never re-derives ``operation``/``reason``/``content_hash``, it replays
        exactly what the producer built.
        """
        from agentic_dynamics.knowledge.knowledge import KnowledgeEvent, KnowledgeRecord

        try:
            record = KnowledgeRecord.from_dict(payload["record"])
            event = KnowledgeEvent.from_dict(payload["event"])
        except Exception as exc:  # noqa: BLE001 — a shape this code cannot rebuild is permanent
            raise MalformedPayloadError(f"cannot rebuild record/event ({exc})") from exc
        return record, event

    def _already_checkpointed(self, client: Any, knowledge_id: str) -> bool:
        """Has a consumer already checkpointed this ``knowledge_id``?

        A checkpoint-store failure is *not* treated as "not checkpointed" — it propagates, so
        the row retries. Defaulting to False on an error would re-publish on every transient
        Redis hiccup, converting a read failure into duplicate emissions.
        """
        return client.hget(self._checkpoint_field(), knowledge_id) is not None

    def _write_artifact(self, record: Any) -> None:
        """Write the durable artifact the pointer event will hash.

        Content-addressed and deterministic (``record_to_artifact`` blanks ids and timestamps
        precisely so re-derivation is stable), so re-writing it on a redelivery is a no-op in
        content terms — which is what makes at-least-once delivery safe at this step.
        """
        from agentic_dynamics.knowledge.knowledge_ingestion import record_to_artifact

        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        (self.artifact_dir / f"{record.knowledge_id}.json").write_bytes(record_to_artifact(record))

    def _bookkeep(self, client: Any, payload: dict[str, Any], record: Any) -> None:
        """Post-ack checkpoint + registry materialization. Never raises (see :meth:`_attempt`)."""
        if payload["checkpoint"]:
            try:
                client.hset(
                    self._checkpoint_field(),
                    payload["knowledge_id"],
                    payload["checkpoint_value"] or record.indexed_at,
                )
            except Exception as exc:  # noqa: BLE001 — post-ack, must not un-deliver
                self._log(f"outbox: checkpoint write failed for {record.knowledge_id} ({exc})")
        lines = payload.get("registry_lines") or []
        if not lines:
            return
        try:
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.registry_path, "a") as fh:
                for line in lines:
                    fh.write(json.dumps(line) + "\n")
        except Exception as exc:  # noqa: BLE001 — post-ack, must not un-deliver
            self._log(f"outbox: registry line append failed for {record.knowledge_id} ({exc})")


# ── Introspection helpers (what the operator and p4's packet read) ───────────────────────────


@dataclass(frozen=True)
class OutboxSummary:
    """Counts by status, plus the oldest still-undelivered row — the operator's one glance."""

    pending: int = 0
    delivered: int = 0
    dead: int = 0
    oldest_pending_at: str = ""
    dead_event_ids: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready rendering for the control packet."""
        return {
            "pending": self.pending,
            "delivered": self.delivered,
            "dead": self.dead,
            "oldest_pending_at": self.oldest_pending_at,
            "dead_event_ids": list(self.dead_event_ids),
        }


def summarize(db: ControlDB, *, run_id: str | None = None) -> OutboxSummary:
    """Summarize the outbox (optionally for one run).

    Deliberately reports ``dead`` ids rather than only a count: a dead event is a hole in the
    projection chain, and "3 dead" without the ids is an alert nobody can act on.
    """
    rows = db.outbox_events(run_id=run_id)
    pending = [r for r in rows if r.status is OutboxStatus.PENDING]
    return OutboxSummary(
        pending=len(pending),
        delivered=sum(1 for r in rows if r.status is OutboxStatus.DELIVERED),
        dead=sum(1 for r in rows if r.status is OutboxStatus.DEAD),
        oldest_pending_at=pending[0].created_at if pending else "",
        dead_event_ids=tuple(r.event_id for r in rows if r.status is OutboxStatus.DEAD),
    )


def _kb_artifact_dir() -> Path:
    """The durable KB artifact directory, read from ``core.paths`` at call time."""
    from agentic_dynamics.core import paths

    return Path(paths.KB_ARTIFACT_DIR)


def _registry_index_path() -> Path:
    """The append-only registry index, read from ``core.paths`` at call time."""
    from agentic_dynamics.core import paths

    return Path(paths.REGISTRY_INDEX_PATH)


def _iso(moment: datetime) -> str:
    """UTC ISO-8601 with a ``Z`` suffix — byte-for-byte ``control_db._now()``'s shape.

    This is not cosmetic. The backoff is enforced by a SQL string comparison
    (``next_retry_at <= now`` in :meth:`ControlDB.pending_outbox_events`), and string ordering
    only tracks time ordering if every stamp shares one format. A ``+00:00`` suffix written
    here against ``Z`` suffixes written there would sort ``+`` (0x2B) before ``Z`` (0x5A) and
    make a not-yet-due row look eligible.
    """
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
