"""Projection watermarks — making knowledge projection explicit (``control_db_publication`` p3).

Why this module exists
----------------------
The knowledge chain has four independent projectors. A producer writes a durable artifact and
publishes a pointer event onto ONE Redis stream (``kb:v1:changes``); four consumer groups then
project that event into four different destinations — the registry log, the Chroma collection,
the Neo4j graph, and the ledger checkpoint hash. Each group acks independently, at its own
pace, and can be down independently.

Before this module, none of that was observable. A projector that had not run for six hours
looked *exactly* like a projector that was fully caught up: both were silent. The only way to
find out that Chroma was 400 events behind the registry was to count rows in one against lines
in the other, after the fact — which is how the "materialization stall" class of failure hid
for as long as it did. Worse, the absence of a signal reads as *good news*: nothing is
complaining, so everything must be fine. That inference is exactly backwards for a projection.

A watermark inverts it. For every projection we durably record, in the control database's
``projection_watermarks`` table:

* ``last_event_id`` — the stream id this projection last **confirmed** (acked, not merely
  delivered: a message handed to a consumer that then crashed was never projected);
* ``source_head_event_id`` — the stream head at the moment of the reading, i.e. the thing
  ``last_event_id`` is behind;
* ``lag_events`` — how many events sit between the two, or ``NULL`` when it cannot be computed;
* ``last_success_at`` — when this projection last reported *successfully*;
* ``last_error`` — the last failure, verbatim, when the last report was a failure.

The two rules this module is built around
-----------------------------------------
**1. Unknown lag is NULL, never 0.** A fabricated ``0`` reads as "fully caught up", which is
the single most dangerous wrong answer a projection surface can give — it is the answer a
publication gate would happily act on. Redis cannot always resolve a group's lag (after an
``XSETID``, or after trimming that removed entries the group never read, ``XINFO GROUPS``
returns a NULL ``lag``), and when it cannot, neither can we. See :func:`unconfirmed_events`.

**2. A stale reading dominates a good one.** ``lag_events = 0`` recorded four hours ago does
not mean the projection is current now; it means it *was* current four hours ago, and four
hours of events have arrived since. So :func:`classify` treats staleness as overriding a
recorded zero-lag: the verdict is ``STALE``, not ``CURRENT``. This is the p3 mandate's explicit
requirement — "a stale projector is VISIBLE rather than silently 'current'" — and it is the
whole reason ``last_success_at`` is a column rather than a debug field.

Who writes these rows
---------------------
The control database's *run* tables (``runs``/``step_attempts``/``gate_results``/…) are
orchestrator-owned: one writer, by design (p1). ``projection_watermarks`` is the documented
exception, and deliberately so — **each projector owns its own watermark row**. Nobody else can
know when ``kb-chroma-v1`` confirmed an event; asking the orchestrator to poll on the
projectors' behalf would reintroduce the very indirection this table removes. The exception is
safe because the table is partitioned by ``projection`` (one row per projector, no shared
rows), and because SQLite in WAL mode serialises the writes behind ``busy_timeout``.

Two refresh paths land the rows, and both matter:

* the **consumer loop** (``scripts/kb_worker.py``) calls :func:`record_from_batch` after each
  batch, reporting the exact entry id it just acked. This is the authoritative reading — the
  worker *knows* what it confirmed;
* a **poller** (the Control Room, the p4 control packet, a cron) calls :func:`refresh_all`,
  which derives every group's position from Redis without consuming anything. This is what
  keeps an *idle* system's watermarks fresh: ``kb_worker.py`` exits after twelve idle polls, so
  without a poller a healthy quiet system would slowly age into ``STALE``. With one, staleness
  means what it should — nothing has been able to look.

Layering
--------
``control`` is tier 2 and ``knowledge`` is tier 1, so reading the stream contract
(``knowledge.knowledge_stream``) from here runs *with* the dependency direction
(``tests/test_dependency_direction.py``). The Redis handle is always **injected** — no function
in this module opens a connection — which is what lets the tests prove the lag arithmetic and
the staleness rule against a fake client, with no live Redis anywhere.

What this phase does NOT do
---------------------------
p3 owns the watermark rows, the consumer-loop wiring, and the read surfaces. It does not render
the control packet (p4 builds ``scripts/control_status.py`` and consumes :func:`projection_lag`
from here), does not touch the instruction surfaces (p5), and does not publish (p6).
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from agentic_dynamics.control.control_db import (
    ControlDB,
    ControlDBError,
    ProjectionWatermark,
)
from agentic_dynamics.knowledge import knowledge_stream as ks

# ── Vocabulary: consumer group ⇄ projection name ─────────────────────────────────────────────

#: How long a projection may go without a successful report before it is called STALE.
#:
#: [H] 900s (15 minutes). The reasoning, not a round number picked for looking round: the
#: consumer loop reports on every batch and blocks for at most ``BLOCK_TIMEOUT_MS`` (10s)
#: between polls, so a *running* projector refreshes on the order of seconds; a poller running
#: on any sane schedule refreshes on the order of minutes. Fifteen minutes is therefore far
#: outside the healthy band — long enough that ordinary scheduling jitter, a slow batch, or a
#: brief Redis reconnect never trips it, short enough that a genuinely dead projector is
#: visible within one operator's attention span rather than the next morning.
DEFAULT_STALE_AFTER_S = 900

#: Environment override, so an operator can tighten the threshold during a publication window
#: (when a fifteen-minute blind spot is fifteen minutes too many) without editing code.
STALE_AFTER_ENV = "FINOPS_PROJECTION_STALE_S"


def projection_name(group: str) -> str:
    """Map a consumer group name onto its short projection name.

    ``kb-chroma-v1`` → ``chroma``. The short name is what the control packet and the Control
    Room render (``projection_lag: {registry: 0, chroma: 3, neo4j: 3}``): the ``kb-`` prefix and
    the ``-v1`` suffix are transport details of the stream contract, and repeating them in every
    operator-facing surface would be noise.

    Derived rather than hard-coded so a fifth consumer group added to
    ``knowledge_stream.CONSUMER_GROUPS`` cannot silently arrive without a watermark — it gets a
    projection name automatically, and :data:`PROJECTIONS` grows with it.
    """
    name = group.strip()
    if name.startswith("kb-"):
        name = name[len("kb-"):]
    # Strip a trailing "-v<N>" version segment; anything else is kept verbatim, because
    # inventing a name for a group we do not recognise would be worse than echoing it.
    head, sep, tail = name.rpartition("-")
    if sep and tail.startswith("v") and tail[1:].isdigit():
        name = head
    return name or group


def group_name(projection: str) -> str | None:
    """Inverse of :func:`projection_name`: the consumer group behind a projection name.

    Returns ``None`` for an unknown projection rather than guessing a group name — a guessed
    group would be polled against a stream position that does not exist, and would report a
    confident, wrong watermark.
    """
    for group in ks.CONSUMER_GROUPS:
        if projection_name(group) == projection:
            return group
    return None


#: Every projection this module knows about, in a stable, name-sorted order (the control packet
#: and the Control Room both render deterministically off this).
PROJECTIONS: tuple[str, ...] = tuple(sorted(projection_name(g) for g in ks.CONSUMER_GROUPS))


class ProjectionHealth(str, Enum):
    """The operator-facing verdict for one projection.

    A ``str`` enum so the value serialises straight into JSON (the p4 packet) without a
    conversion step that could drift from the vocabulary.
    """

    #: Confirmed up to the stream head, reported recently. The only verdict that means "safe".
    CURRENT = "current"
    #: Behind the head, but reporting — it is consuming, just not finished.
    LAGGING = "lagging"
    #: No successful report inside the staleness window. Its recorded lag is as old as the
    #: reading and must NOT be believed, whatever it says.
    STALE = "stale"
    #: The last report carried an error. The loudest verdict: something tried and failed.
    FAILING = "failing"
    #: Never reported, or lag not computable. Not "fine" — *unknown*, which is a different
    #: answer and the one a publication gate must refuse to act on.
    UNKNOWN = "unknown"


# ── Reading a consumer group's position from Redis ───────────────────────────────────────────


@dataclass(frozen=True)
class ConsumerPosition:
    """What Redis knows about one consumer group's position on the knowledge event stream.

    A pure reading — constructing one consumes nothing and acks nothing, which is what makes it
    safe for an observer (the Control Room, the control packet) to take on every poll.
    """

    group: str
    stream: str
    #: ``XINFO GROUPS`` ``last-delivered-id``: the furthest id *handed to* a consumer. Note that
    #: delivered ≠ confirmed — an entry delivered to a consumer that then died was never
    #: projected, and is still counted as pending.
    last_delivered_id: str
    #: ``XPENDING`` count: delivered but not yet acked.
    pending: int
    #: The oldest pending entry id (``""`` when nothing is pending) — the exact point the
    #: confirmed frontier cannot have passed.
    oldest_pending_id: str
    #: ``XINFO GROUPS`` ``entries-read``/``lag``. ``lag`` is Redis's own count of entries not
    #: yet *delivered* to this group; it is ``None`` when Redis cannot resolve it.
    entries_read: int | None
    lag: int | None
    #: ``XINFO STREAM`` ``last-generated-id`` and ``length`` — the head this group is behind.
    head_event_id: str
    stream_length: int


def _as_int(value: Any) -> int | None:
    """Coerce a Redis field to ``int``, mapping absent/NULL/garbage to ``None``, never to 0.

    The null-not-zero discipline in one helper: Redis returns a genuine NULL ``lag`` when it
    cannot resolve one, and ``int(None)`` would raise while a silent ``or 0`` would fabricate
    "caught up". Both are wrong; ``None`` is the truth.
    """
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def read_position(
    r: Any,
    group: str,
    *,
    stream: str = ks.STREAM_KEY,
) -> ConsumerPosition:
    """Read one consumer group's position from Redis (``XINFO``/``XPENDING``).

    Raises whatever the Redis client raises — a projection surface built on a swallowed
    connection error would report "unknown" for a reason it could have named, and the callers
    here (:func:`refresh_all`, :func:`record_from_batch`) each turn the failure into a recorded
    ``last_error`` at the point where they know which projection it belongs to.

    :param r: an injected Redis client (``decode_responses=True``, as ``knowledge_stream``
        opens it — the field names below are strings).
    :param group: the consumer group name (``kb-chroma-v1``, …).
    :param stream: the stream key; defaults to the knowledge event stream.
    """
    stream_info = r.xinfo_stream(stream)
    head_event_id = str(stream_info.get("last-generated-id") or "")
    stream_length = _as_int(stream_info.get("length")) or 0

    # XINFO GROUPS returns every group; find ours rather than assuming an ordering.
    group_info: dict[str, Any] = {}
    for candidate in r.xinfo_groups(stream):
        if str(candidate.get("name")) == group:
            group_info = candidate
            break

    pending_summary = r.xpending(stream, group) or {}
    pending = _as_int(pending_summary.get("pending")) or 0
    # ``min`` is the oldest pending id. Redis reports it as None when the group has nothing
    # pending; normalise that to "" so the dataclass field stays a plain str.
    oldest_pending_id = str(pending_summary.get("min") or "") if pending else ""

    return ConsumerPosition(
        group=group,
        stream=stream,
        last_delivered_id=str(group_info.get("last-delivered-id") or ""),
        pending=pending,
        oldest_pending_id=oldest_pending_id,
        entries_read=_as_int(group_info.get("entries-read")),
        lag=_as_int(group_info.get("lag")),
        head_event_id=head_event_id,
        stream_length=stream_length,
    )


#: Stream ids meaning "this group has been delivered nothing at all". Redis reports ``0-0`` for
#: a group created at the stream's origin that has never read; an empty string is the defensive
#: case where the field is absent entirely.
NEVER_DELIVERED_IDS = frozenset({"0-0", "0", ""})


def unconfirmed_events(position: ConsumerPosition) -> int | None:
    """How many events this projection has NOT confirmed — the watermark's ``lag_events``.

    Two disjoint populations make up the answer, and counting only one of them is the classic
    way to under-report a stuck projector:

    * **not yet delivered** — Redis's own ``lag`` field: entries on the stream the group has
      never been handed;
    * **delivered but not acked** — ``XPENDING``: entries a consumer took and did not confirm,
      which is precisely what a crashed or wedged consumer leaves behind. A projector stuck
      retrying one poisoned message has ``lag = 0`` and ``pending = 1``; reporting ``0`` would
      call it caught up while it projects nothing at all.

    **When Redis cannot resolve ``lag``.** ``XINFO GROUPS`` returns a NULL ``lag`` (and a NULL
    ``entries-read``) whenever trimming has removed entries a group never read — Redis can no
    longer count what it deleted. This is not exotic: on the live knowledge stream, two of the
    four consumer groups are in exactly that state, and they are the two furthest behind. In
    that case:

    * if the group has been delivered **nothing** (``last-delivered-id`` is ``0-0``), every
      entry currently on the stream is unconfirmed by it, so ``stream_length`` is a sound count
      of what it has not projected. Returning ``None`` here would report the two most
      catastrophically behind projections as merely "unknown" — technically defensible, and a
      strictly worse answer than the one the data supports;
    * otherwise — a group that consumed *some* entries and whose bookkeeping Redis then lost —
      there is no bound short of scanning the stream, which an observer polling on every request
      cannot afford. That case stays ``None``.

    Every value this returns is a **lower bound**: entries trimmed before any consumer read them
    are gone from the stream and countable by nobody. That is the safe direction to be wrong in
    — a lag that under-reports still says "behind", where an over-confident ``0`` would say
    "caught up", which is the one answer a publication gate must never be given wrongly.
    """
    if position.lag is not None:
        return int(position.lag) + int(position.pending)
    if position.last_delivered_id in NEVER_DELIVERED_IDS:
        return int(position.stream_length) + int(position.pending)
    return None


def confirmed_event_id(
    position: ConsumerPosition,
    *,
    acked_event_id: str = "",
    previous: str = "",
) -> str:
    """The id this projection has genuinely **confirmed**, in decreasing order of authority.

    1. ``acked_event_id`` — the consumer loop just XACKed this entry and told us so. Nothing
       beats a first-hand report.
    2. ``position.last_delivered_id`` when ``pending == 0`` — everything delivered has been
       acked, so the delivered frontier *is* the confirmed frontier.
    3. ``previous`` — the frontier already on record. Reached when entries are pending: the
       delivered frontier has run ahead of the confirmed one, and adopting it would credit this
       projection with events it has not projected. Keeping the old value lets the id visibly
       stop moving, which is the honest rendering of a stalled consumer.
    """
    if acked_event_id:
        return acked_event_id
    if position.pending == 0 and position.last_delivered_id:
        return position.last_delivered_id
    return previous


# ── Staleness + health classification ────────────────────────────────────────────────────────


def _now() -> datetime:
    """Current UTC time — one seam, so tests can reason about age without sleeping."""
    return datetime.now(timezone.utc)


def _parse_stamp(stamp: str) -> datetime | None:
    """Parse an ISO-8601 stamp as written by ``control_db``, or ``None`` when unparseable.

    An unparseable stamp is treated as *no* stamp (and therefore as stale) rather than as
    "now": a timestamp we cannot read is not evidence that anything succeeded.

    ``control_db._now()`` writes the repo's house shape — UTC with a literal ``Z`` suffix
    (``2026-09-02T12:00:00Z``) — which ``datetime.fromisoformat`` only learned to parse in
    Python 3.11. This repo runs 3.10, where the ``Z`` raises ``ValueError``, so every stamp
    would silently become "unparseable" and every projection would read STALE forever: the
    surface would be uniformly, uselessly red. Normalising the suffix to the ``+00:00`` form
    3.10 does accept is what keeps that from happening.
    """
    if not stamp:
        return None
    normalised = stamp[:-1] + "+00:00" if stamp.endswith("Z") else stamp
    try:
        parsed = datetime.fromisoformat(normalised)
    except ValueError:
        return None
    # control_db writes UTC; a naive stamp from an older row is interpreted as UTC rather than
    # as local time, which would otherwise shift ages by the host's offset.
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def stale_after_seconds() -> int:
    """The staleness threshold in effect: :data:`STALE_AFTER_ENV` if set and valid, else default."""
    raw = os.environ.get(STALE_AFTER_ENV, "").strip()
    if raw:
        try:
            value = int(raw)
            if value > 0:
                return value
        except ValueError:
            # A malformed override falls back to the documented default rather than raising:
            # a typo in an env var must not take the projection surface offline.
            pass
    return DEFAULT_STALE_AFTER_S


def age_seconds(
    watermark: ProjectionWatermark,
    *,
    now: datetime | None = None,
) -> float | None:
    """Seconds since this projection last reported successfully; ``None`` when it never has.

    ``None`` is not ``0``: "never succeeded" and "succeeded just now" are opposite facts.
    """
    stamp = _parse_stamp(watermark.last_success_at)
    if stamp is None:
        return None
    return ((now or _now()) - stamp).total_seconds()


def is_stale(
    watermark: ProjectionWatermark,
    *,
    max_age_seconds: int | None = None,
    now: datetime | None = None,
) -> bool:
    """Has this projection gone too long without a successful report?

    A watermark with no successful report at all is stale by definition — it has never been
    confirmed current, so it cannot be assumed current.
    """
    age = age_seconds(watermark, now=now)
    if age is None:
        return True
    return age > (max_age_seconds if max_age_seconds is not None else stale_after_seconds())


def classify(
    watermark: ProjectionWatermark | None,
    *,
    max_age_seconds: int | None = None,
    now: datetime | None = None,
) -> ProjectionHealth:
    """The health verdict for one projection. Order matters — see the module docstring.

    1. **no row** → ``UNKNOWN``. A projection that has never reported is not a healthy one.
    2. **``last_error`` set** → ``FAILING``. An error is the loudest fact available; it outranks
       any lag number recorded beside it.
    3. **stale** → ``STALE``, *even when ``lag_events`` is 0*. This is the rule the phase
       mandate names explicitly: a zero recorded four hours ago describes four-hour-old reality,
       and letting it render as ``CURRENT`` is exactly the silent-staleness failure this table
       exists to remove.
    4. **``lag_events is None``** → ``UNKNOWN``. Recent, no error, but the lag could not be
       computed: honest ignorance, not health.
    5. **``lag_events > 0``** → ``LAGGING``. Behind, but reporting — it is working through it.
    6. otherwise → ``CURRENT``.
    """
    if watermark is None:
        return ProjectionHealth.UNKNOWN
    if watermark.last_error:
        return ProjectionHealth.FAILING
    if is_stale(watermark, max_age_seconds=max_age_seconds, now=now):
        return ProjectionHealth.STALE
    if watermark.lag_events is None:
        return ProjectionHealth.UNKNOWN
    if watermark.lag_events > 0:
        return ProjectionHealth.LAGGING
    return ProjectionHealth.CURRENT


# ── Writing watermarks ───────────────────────────────────────────────────────────────────────


def record_position(
    db: ControlDB,
    position: ConsumerPosition,
    *,
    acked_event_id: str = "",
    last_error: str = "",
) -> ProjectionWatermark:
    """Land one projection's watermark from a Redis reading.

    :param db: an OPEN, writable control database. Injected rather than opened here so a caller
        inside a larger transaction (or a test with a ``tmp_path`` database) stays in control of
        the handle's lifetime.
    :param position: the reading from :func:`read_position`.
    :param acked_event_id: the entry the caller just confirmed, when it has one (the consumer
        loop does; a poller does not).
    :param last_error: a failure to record. A non-empty error deliberately does NOT refresh
        ``last_success_at`` — ``control_db.record_watermark`` preserves the previous stamp — so
        a failing projector visibly ages instead of looking healthy on every retry.
    """
    projection = projection_name(position.group)
    previous = db.get_watermark(projection)
    return db.record_watermark(
        projection,
        last_event_id=confirmed_event_id(
            position,
            acked_event_id=acked_event_id,
            previous=previous.last_event_id if previous else "",
        ),
        source_head_event_id=position.head_event_id,
        lag_events=unconfirmed_events(position),
        last_error=last_error,
    )


def record_error(db: ControlDB, group: str, error: str) -> ProjectionWatermark:
    """Record a failure for a projection whose position could not even be read.

    Preserves whatever frontier is already on record: a Redis outage tells us nothing new about
    how far this projection got, only that we can no longer see. Overwriting the ids with blanks
    would destroy real information and replace it with a worse kind of unknown.
    """
    projection = projection_name(group)
    previous = db.get_watermark(projection)
    return db.record_watermark(
        projection,
        last_event_id=previous.last_event_id if previous else "",
        source_head_event_id=previous.source_head_event_id if previous else "",
        # The lag on record was computed at the last successful reading and is now of unknown
        # accuracy. Keeping it would let an old number masquerade as a current one.
        lag_events=None,
        last_error=error,
    )


def record_from_batch(
    db: ControlDB,
    r: Any,
    group: str,
    *,
    acked_event_id: str = "",
    last_error: str = "",
    stream: str = ks.STREAM_KEY,
) -> ProjectionWatermark | None:
    """Refresh one projection's watermark after its consumer processed a batch.

    The consumer loop's entry point (``scripts/kb_worker.py``). Returns ``None`` if the reading
    itself failed *and* the error could not be recorded — the caller treats a ``None`` as
    "watermarking is unavailable", never as "the projection is fine".

    Failures reading Redis are converted into a recorded ``last_error`` rather than propagated:
    ingestion must never stop because bookkeeping about ingestion failed. That is the one place
    where swallowing is right — and it is not silent, because the swallow *writes the error into
    the surface the operator reads*.

    :param last_error: a failure the *caller* observed during the batch (a dead-lettered entry,
        say) to be recorded alongside the fresh Redis reading. Passed in rather than written by
        a second call so that one write carries both the frontier/lag reading and the error —
        a follow-up write would have to blank the lag it just recorded.
    """
    try:
        position = read_position(r, group, stream=stream)
    except Exception as exc:  # noqa: BLE001 — any client/transport failure is recordable
        try:
            return record_error(db, group, f"{type(exc).__name__}: {exc}")
        except ControlDBError:
            return None
    return record_position(
        db, position, acked_event_id=acked_event_id, last_error=last_error
    )


def refresh_all(
    db: ControlDB,
    r: Any,
    *,
    groups: Sequence[str] = ks.CONSUMER_GROUPS,
    stream: str = ks.STREAM_KEY,
) -> list[ProjectionWatermark]:
    """Poll every consumer group and land all four watermarks. The observer's entry point.

    Consumes nothing — this is ``XINFO``/``XPENDING`` only — so it is safe to call from the
    Control Room, the control packet, or a cron on any cadence. It is what keeps an *idle but
    healthy* system's watermarks fresh: the consumer loop exits after twelve idle polls, and
    without a poller its rows would age into ``STALE`` while nothing was actually wrong.

    One group's failure never stops the others: each is read and recorded independently, so a
    broken Neo4j consumer cannot hide the registry's healthy watermark.
    """
    results: list[ProjectionWatermark] = []
    for group in groups:
        watermark = record_from_batch(db, r, group, stream=stream)
        if watermark is not None:
            results.append(watermark)
    return results


# ── Read surfaces (the Control Room + the p4 control packet) ─────────────────────────────────


def watermark_payload(
    watermark: ProjectionWatermark | None,
    *,
    projection: str,
    max_age_seconds: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """One projection rendered as a JSON-ready dict, for any operator-facing surface.

    ``lag_events`` and ``age_seconds`` are ``None`` (JSON ``null``) rather than ``0`` when
    unknown, so a client that renders the raw value cannot accidentally print a reassuring
    number that nothing measured.
    """
    health = classify(watermark, max_age_seconds=max_age_seconds, now=now)
    if watermark is None:
        return {
            "projection": projection,
            "health": health.value,
            "last_event_id": "",
            "source_head_event_id": "",
            "lag_events": None,
            "last_success_at": "",
            "age_seconds": None,
            "last_error": "",
            # An explicit flag, because "has never reported" is a different operational story
            # from "reported, and is behind" — the first means nobody has ever run this
            # projector, the second means it ran and fell behind.
            "reported": False,
        }
    return {
        "projection": watermark.projection,
        "health": health.value,
        "last_event_id": watermark.last_event_id,
        "source_head_event_id": watermark.source_head_event_id,
        "lag_events": watermark.lag_events,
        "last_success_at": watermark.last_success_at,
        "age_seconds": age_seconds(watermark, now=now),
        "last_error": watermark.last_error,
        "reported": True,
    }


def projection_report(
    db: ControlDB,
    *,
    projections: Iterable[str] = PROJECTIONS,
    max_age_seconds: int | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Every known projection, in a stable order, whether or not it has ever reported.

    Iterating the *expected* projections rather than the rows present is the load-bearing
    choice: a projector that has never run has no row, and a surface that listed only existing
    rows would render it as absent — indistinguishable from a projection that does not exist.
    Here it appears with ``health: unknown`` and ``reported: false``, which is a question an
    operator can act on.
    """
    return [
        watermark_payload(
            db.get_watermark(projection),
            projection=projection,
            max_age_seconds=max_age_seconds,
            now=now,
        )
        for projection in projections
    ]


def projection_lag(
    db: ControlDB,
    *,
    projections: Iterable[str] = PROJECTIONS,
) -> dict[str, int | None]:
    """The compact ``{registry: 0, chroma: 3, neo4j: 3}`` block the p4 control packet carries.

    ``None`` for a projection that has never reported or whose lag could not be computed. The
    packet's consumer (the master controller) must treat ``None`` as "do not proceed on this",
    which is only possible because the value is not silently ``0``.
    """
    report = {p["projection"]: p["lag_events"] for p in projection_report(db, projections=projections)}
    return {projection: report.get(projection) for projection in projections}


def unhealthy_projections(
    db: ControlDB,
    *,
    projections: Iterable[str] = PROJECTIONS,
    max_age_seconds: int | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Just the projections that are not ``CURRENT`` — what a gate or an alert reads.

    Deliberately includes ``UNKNOWN``: a publication that depends on a projection nobody can
    vouch for is exactly as unsafe as one that depends on a projection known to be behind.
    """
    return [
        entry
        for entry in projection_report(
            db, projections=projections, max_age_seconds=max_age_seconds, now=now
        )
        if entry["health"] != ProjectionHealth.CURRENT.value
    ]


def read_report(
    path: str | Path | None = None,
    *,
    projections: Iterable[str] = PROJECTIONS,
    max_age_seconds: int | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]] | None:
    """:func:`projection_report` against a read-only handle, or ``None`` if there is no control db.

    The convenience wrapper for observers that do not otherwise hold a handle (the Control Room
    route, the control packet). ``None`` means "no control database" — a *missing* control plane,
    which a caller must render differently from "four projections, all unknown". Opening
    read-only is what keeps this safe: an observer never creates the database, so it can never
    turn "the orchestrator has not run" into an empty database that reads as "there are no runs".
    """
    try:
        with ControlDB.open_read_only(path) as db:
            return projection_report(
                db, projections=projections, max_age_seconds=max_age_seconds, now=now
            )
    except ControlDBError:
        return None


__all__ = [
    "DEFAULT_STALE_AFTER_S",
    "PROJECTIONS",
    "STALE_AFTER_ENV",
    "ConsumerPosition",
    "ProjectionHealth",
    "age_seconds",
    "classify",
    "confirmed_event_id",
    "group_name",
    "is_stale",
    "projection_lag",
    "projection_name",
    "projection_report",
    "read_position",
    "read_report",
    "record_error",
    "record_from_batch",
    "record_position",
    "refresh_all",
    "stale_after_seconds",
    "unconfirmed_events",
    "unhealthy_projections",
    "watermark_payload",
]
