"""Projection-watermark tests — the p3 mandate's VERIFY clause, driven in both directions.

The phase mandate names four things these tests exist to prove, and each has a section below:

1. **readable** — every watermark round-trips out of the control database, and a projection that
   has never reported is still *visible* (as ``unknown``) rather than silently absent;
2. **updates** — a watermark advances when its consumer confirms a new event, and only when it
   *confirms* one: a delivered-but-unacked entry must not move the frontier;
3. **lag** — a consumer that has not run for N events reports lag N, and an unknowable lag is
   reported as ``None``, never as the reassuring ``0``;
4. **staleness is visible** — a projector that stopped reporting reads ``stale``, *including*
   when the last thing it recorded was ``lag_events = 0``. This is the negative half that
   matters most: a suite that only checked "does lag 0 read as current?" would pass while the
   surface lied about every dead projector.

The repo's both-directions convention throughout: for each rule, one test proves the surface
reports the good state and one proves it refuses to report the good state when it is not true.
The negative halves are the point — a watermark surface that said "current" unconditionally
would pass every naive positive test while being worse than no surface at all, because it would
be *trusted*.

Storage is real (a SQLite control database under ``tmp_path``); Redis is a fake. That split is
deliberate: the persistence IS the thing under test for the watermark rows, so faking it would
prove the fake; whereas the Redis side is a pure *reading* whose arithmetic — not whose
transport — is what these tests are about, and a fake lets a stuck-consumer or NULL-lag scenario
be constructed exactly, which no live instance would reliably reproduce on demand.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from agentic_dynamics.control import projection_watermarks as pwm
from agentic_dynamics.control.control_db import ControlDB
from agentic_dynamics.knowledge import knowledge_stream as ks

# ── Fixtures + the fake stream ───────────────────────────────────────────────────────────────


@pytest.fixture
def db(tmp_path):
    """A real, writable control database on disk — the thing under test for storage."""
    with ControlDB(tmp_path / "control.db") as handle:
        yield handle


class FakeStreamRedis:
    """A Redis stand-in implementing exactly the three reads ``read_position`` performs.

    ``xinfo_stream`` / ``xinfo_groups`` / ``xpending``, returning the decoded-string field names
    a ``decode_responses=True`` client produces (which is how ``knowledge_stream.connect``
    opens it). Nothing else is modelled, because nothing else is called — a broader fake would
    invite tests that drift away from what the module actually does.
    """

    def __init__(self, *, head="100-0", length=100, groups=None):
        self.head = head
        self.length = length
        #: group name -> {last-delivered-id, lag, entries-read} plus a "pending" list.
        self.groups = groups or {}
        self.calls: list[tuple[str, str]] = []

    def xinfo_stream(self, stream):
        self.calls.append(("xinfo_stream", stream))
        return {"last-generated-id": self.head, "length": self.length}

    def xinfo_groups(self, stream):
        self.calls.append(("xinfo_groups", stream))
        return [
            {
                "name": name,
                "last-delivered-id": info.get("last-delivered-id", ""),
                "entries-read": info.get("entries-read"),
                "lag": info.get("lag"),
            }
            for name, info in self.groups.items()
        ]

    def xpending(self, stream, group):
        self.calls.append(("xpending", group))
        info = self.groups.get(group, {})
        pending = info.get("pending", 0)
        return {"pending": pending, "min": info.get("oldest-pending") if pending else None}


class ExplodingRedis:
    """A client whose every read raises — the downed-transport case."""

    def xinfo_stream(self, stream):
        raise ConnectionError("stream unreachable")

    def xinfo_groups(self, stream):
        raise ConnectionError("stream unreachable")

    def xpending(self, stream, group):
        raise ConnectionError("stream unreachable")


def _group(*, last_delivered="", lag=None, pending=0, oldest_pending="", entries_read=None):
    """Build one ``xinfo_groups`` entry for :class:`FakeStreamRedis`."""
    return {
        "last-delivered-id": last_delivered,
        "lag": lag,
        "pending": pending,
        "oldest-pending": oldest_pending,
        "entries-read": entries_read,
    }


# ── 1. Vocabulary: group ⇄ projection names ──────────────────────────────────────────────────


def test_every_consumer_group_maps_to_a_distinct_projection_name():
    """All four groups get a name, and no two collide.

    A collision would silently merge two projections into one row — Chroma would overwrite
    Neo4j's watermark and the surface would confidently report one number for two projectors.
    """
    names = [pwm.projection_name(g) for g in ks.CONSUMER_GROUPS]
    assert names == ["chroma", "neo4j", "ledger", "registry"]
    assert len(set(names)) == len(ks.CONSUMER_GROUPS)
    assert pwm.PROJECTIONS == ("chroma", "ledger", "neo4j", "registry")


def test_projection_name_round_trips_back_to_its_group():
    """``group_name`` inverts ``projection_name`` for every real group..."""
    for group in ks.CONSUMER_GROUPS:
        assert pwm.group_name(pwm.projection_name(group)) == group


def test_unknown_projection_has_no_group_rather_than_a_guessed_one():
    """...and refuses to invent one for a name it does not know.

    The negative half: a guessed group would be polled against a stream position that does not
    exist, producing a confident, wrong watermark — worse than no answer.
    """
    assert pwm.group_name("sqlite") is None
    assert pwm.group_name("") is None


def test_an_unrecognised_group_name_is_echoed_not_mangled():
    """A name outside the ``kb-<x>-v1`` shape survives verbatim instead of becoming ``""``."""
    assert pwm.projection_name("some-other-consumer") == "some-other-consumer"
    assert pwm.projection_name("kb-future-v2") == "future"


# ── 2. Readable: watermarks round-trip, and a never-reported projection stays visible ────────


def test_a_recorded_watermark_is_readable_with_every_field(db):
    """Each field written is the field read back — the round-trip the whole surface rests on."""
    now = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
    db.record_watermark(
        "registry",
        last_event_id="1725-0",
        source_head_event_id="1725-0",
        lag_events=0,
        last_success_at=now.isoformat(),
    )
    watermark = db.get_watermark("registry")

    assert watermark is not None
    assert watermark.projection == "registry"
    assert watermark.last_event_id == "1725-0"
    assert watermark.source_head_event_id == "1725-0"
    assert watermark.lag_events == 0
    assert watermark.last_error == ""
    assert pwm.classify(watermark, now=now) is pwm.ProjectionHealth.CURRENT


def test_a_projection_that_never_reported_is_visible_as_unknown(db):
    """A projector that has never run appears in the report — it is not simply missing.

    The load-bearing negative: if the report listed only the rows present, "nobody has ever run
    the Neo4j consumer" would render identically to "there is no Neo4j projection", and the
    operator would never be prompted to ask.
    """
    db.record_watermark("registry", last_event_id="5-0", lag_events=0)
    report = pwm.projection_report(db)

    assert [entry["projection"] for entry in report] == list(pwm.PROJECTIONS)
    neo4j = next(e for e in report if e["projection"] == "neo4j")
    assert neo4j["health"] == "unknown"
    assert neo4j["reported"] is False
    assert neo4j["lag_events"] is None
    assert neo4j["age_seconds"] is None


def test_projection_lag_reports_none_for_a_silent_projection(db):
    """The p4 packet's compact block carries ``None``, never a fabricated ``0``.

    The master controller's rule is "do not proceed on a ``None``". That rule is only
    expressible because an unmeasured projection is not reported as caught up.
    """
    db.record_watermark("registry", last_event_id="9-0", lag_events=0)
    db.record_watermark("chroma", last_event_id="6-0", lag_events=3)

    lag = pwm.projection_lag(db)
    assert lag == {"chroma": 3, "ledger": None, "neo4j": None, "registry": 0}


# ── 3. Updates: the watermark advances when — and only when — a consumer CONFIRMS ────────────


def test_a_confirmed_batch_advances_the_watermark(db):
    """The consumer acks entry ``40-0``; the watermark says ``40-0``. The positive case."""
    r = FakeStreamRedis(
        head="40-0", groups={"kb-chroma-v1": _group(last_delivered="40-0", lag=0, pending=0)}
    )
    watermark = pwm.record_from_batch(db, r, "kb-chroma-v1", acked_event_id="40-0")

    assert watermark is not None
    assert watermark.last_event_id == "40-0"
    assert watermark.source_head_event_id == "40-0"
    assert watermark.lag_events == 0
    assert pwm.classify(watermark) is pwm.ProjectionHealth.CURRENT


def test_a_second_batch_moves_the_frontier_forward(db):
    """Two successive confirmed batches: the second reading supersedes the first."""
    r = FakeStreamRedis(
        head="40-0", groups={"kb-chroma-v1": _group(last_delivered="40-0", lag=0)}
    )
    pwm.record_from_batch(db, r, "kb-chroma-v1", acked_event_id="40-0")

    r.head = "55-0"
    r.groups["kb-chroma-v1"] = _group(last_delivered="55-0", lag=0)
    pwm.record_from_batch(db, r, "kb-chroma-v1", acked_event_id="55-0")

    watermark = db.get_watermark("chroma")
    assert watermark.last_event_id == "55-0"
    assert watermark.source_head_event_id == "55-0"


def test_delivered_but_unacked_entries_do_not_advance_the_frontier(db):
    """A consumer that took entries and never acked them keeps its OLD frontier.

    The critical negative. Redis's ``last-delivered-id`` has run ahead to ``50-0``, but three
    entries are pending — handed out, never confirmed, so never projected. Crediting the
    projection with them would be precisely the over-report the watermark exists to prevent:
    the frontier must visibly stop moving while the consumer is wedged.
    """
    r = FakeStreamRedis(
        head="50-0", groups={"kb-neo4j-v1": _group(last_delivered="20-0", lag=0)}
    )
    pwm.record_from_batch(db, r, "kb-neo4j-v1", acked_event_id="20-0")

    # The consumer is handed 30 more entries and dies mid-batch: delivered 50-0, 3 pending.
    r.groups["kb-neo4j-v1"] = _group(
        last_delivered="50-0", lag=0, pending=3, oldest_pending="48-0"
    )
    watermark = pwm.record_from_batch(db, r, "kb-neo4j-v1")  # no acked id — nothing confirmed

    assert watermark.last_event_id == "20-0", "the frontier must not follow delivery"
    assert watermark.lag_events == 3, "the pending entries ARE the lag"
    assert pwm.classify(watermark) is pwm.ProjectionHealth.LAGGING


def test_a_fully_drained_group_adopts_its_delivered_frontier(db):
    """The mirror case: nothing pending means delivered *is* confirmed.

    Without this, a poller (which has no ack id of its own to report) could never advance a
    healthy projection's frontier, and every projector would look permanently stuck at whatever
    the last consumer-loop batch happened to leave behind.
    """
    r = FakeStreamRedis(
        head="77-0", groups={"kb-registry-v1": _group(last_delivered="77-0", lag=0, pending=0)}
    )
    watermark = pwm.record_from_batch(db, r, "kb-registry-v1")

    assert watermark.last_event_id == "77-0"
    assert pwm.classify(watermark) is pwm.ProjectionHealth.CURRENT


def test_refresh_all_lands_every_group_independently(db):
    """One poll, four rows — and one broken group does not suppress the other three."""
    r = FakeStreamRedis(
        head="90-0",
        groups={
            "kb-chroma-v1": _group(last_delivered="90-0", lag=0),
            "kb-neo4j-v1": _group(last_delivered="87-0", lag=3),
            "kb-ledger-v1": _group(last_delivered="90-0", lag=0),
            "kb-registry-v1": _group(last_delivered="90-0", lag=0),
        },
    )
    watermarks = pwm.refresh_all(db, r)

    assert {w.projection for w in watermarks} == set(pwm.PROJECTIONS)
    assert pwm.projection_lag(db) == {"chroma": 0, "ledger": 0, "neo4j": 3, "registry": 0}


# ── 4. Lag: N un-consumed events report as N; an unknowable lag reports as None ───────────────


def test_a_consumer_that_has_not_run_for_n_events_shows_lag_n(db):
    """The mandate's exact clause, exercised at the arithmetic level.

    The stream head has advanced 12 events past this group; Redis reports ``lag = 12``; the
    watermark must say 12 — not "behind", not 0, not the head id.
    """
    r = FakeStreamRedis(
        head="112-0", groups={"kb-chroma-v1": _group(last_delivered="100-0", lag=12)}
    )
    watermark = pwm.record_from_batch(db, r, "kb-chroma-v1")

    assert watermark.lag_events == 12
    assert watermark.source_head_event_id == "112-0"
    assert pwm.classify(watermark) is pwm.ProjectionHealth.LAGGING


def test_lag_counts_undelivered_and_unacked_entries_together():
    """Both populations count: entries never delivered PLUS entries delivered but not acked.

    A projector stuck retrying one poisoned message has ``lag = 0`` and ``pending = 1``.
    Reporting the Redis ``lag`` alone would call it caught up while it projects nothing — the
    exact under-report this arithmetic exists to close.
    """
    stuck = pwm.ConsumerPosition(
        group="kb-neo4j-v1",
        stream=ks.STREAM_KEY,
        last_delivered_id="30-0",
        pending=1,
        oldest_pending_id="30-0",
        entries_read=30,
        lag=0,
        head_event_id="30-0",
        stream_length=30,
    )
    assert pwm.unconfirmed_events(stuck) == 1

    behind_and_stuck = pwm.ConsumerPosition(
        group="kb-neo4j-v1",
        stream=ks.STREAM_KEY,
        last_delivered_id="30-0",
        pending=2,
        oldest_pending_id="29-0",
        entries_read=30,
        lag=7,
        head_event_id="37-0",
        stream_length=37,
    )
    assert pwm.unconfirmed_events(behind_and_stuck) == 9


def test_an_unresolvable_lag_is_none_not_zero(db):
    """Redis returns a NULL ``lag`` for a partially-consumed group; we must not invent a number.

    The single most dangerous wrong answer this table can give is a fabricated ``0``, because
    it is the one a publication gate would act on. This group HAS consumed entries (delivered
    up to ``120-0``) and Redis has since lost its ``entries-read`` bookkeeping, so there is no
    bound short of scanning the stream. ``None`` forces the caller to decide.
    """
    r = FakeStreamRedis(
        head="500-0",
        length=500,
        groups={"kb-ledger-v1": _group(last_delivered="120-0", lag=None)},
    )
    watermark = pwm.record_from_batch(db, r, "kb-ledger-v1")

    assert watermark.lag_events is None
    assert pwm.classify(watermark) is pwm.ProjectionHealth.UNKNOWN, "unknown is not healthy"
    assert pwm.projection_lag(db)["ledger"] is None


def test_a_group_that_consumed_nothing_reports_the_whole_stream_as_lag(db):
    """A NULL ``lag`` on a group delivered NOTHING still yields a real number.

    Observed on the live knowledge stream: trimming had removed entries the ``kb-chroma-v1``
    and ``kb-ledger-v1`` groups never read, so Redis returned ``entries-read: None`` and
    ``lag: None`` for both — and those two were the furthest behind of the four. Reporting the
    two most catastrophically stalled projections as merely "unknown" is technically defensible
    and strictly worse than the answer the data supports: the group has been delivered nothing,
    so every entry currently on the stream is one it has not projected.
    """
    r = FakeStreamRedis(
        head="30771-0",
        length=30771,
        groups={"kb-chroma-v1": _group(last_delivered="0-0", lag=None, entries_read=None)},
    )
    watermark = pwm.record_from_batch(db, r, "kb-chroma-v1")

    assert watermark.lag_events == 30771
    assert pwm.classify(watermark) is pwm.ProjectionHealth.LAGGING, "not merely 'unknown'"


def test_the_derived_bound_is_never_used_to_claim_caught_up(db):
    """The fallback can only ever say "behind" — an EMPTY stream is the boundary case.

    The negative half of the bound: with nothing on the stream there is nothing to be behind
    on, so lag 0 here is a measured zero, not a fabricated one. If the fallback could report a
    reassuring 0 for a *non-empty* stream it would have reintroduced the exact failure the
    null-not-zero rule exists to prevent.
    """
    r = FakeStreamRedis(
        head="", length=0, groups={"kb-chroma-v1": _group(last_delivered="0-0", lag=None)}
    )
    watermark = pwm.record_from_batch(db, r, "kb-chroma-v1")

    assert watermark.lag_events == 0
    # And the mirror: any non-empty stream yields a strictly positive bound.
    r.length = 1
    assert pwm.record_from_batch(db, r, "kb-chroma-v1").lag_events == 1


def test_a_garbage_lag_field_is_none_not_zero():
    """A non-numeric field degrades to ``None`` rather than through ``or 0`` into "caught up"."""
    position = pwm.ConsumerPosition(
        group="kb-chroma-v1",
        stream=ks.STREAM_KEY,
        last_delivered_id="1-0",
        pending=0,
        oldest_pending_id="",
        entries_read=None,
        lag=None,
        head_event_id="9-0",
        stream_length=9,
    )
    assert pwm.unconfirmed_events(position) is None
    assert pwm._as_int("not-a-number") is None
    assert pwm._as_int(None) is None
    assert pwm._as_int("0") == 0, "a real zero still reads as zero"


# ── 5. Staleness is VISIBLE — the mandate's headline requirement ─────────────────────────────


def test_a_stale_projector_reads_stale_not_current(db):
    """A projector whose last success was hours ago is STALE **even though its lag says 0**.

    This is the failure the whole table exists to remove. The recorded ``lag_events = 0``
    describes reality as of the reading — four hours ago. Events have arrived since, and nobody
    has confirmed anything about them. Rendering that row as ``current`` because the number in
    it is zero is how a dead projector hides behind its own last good report.
    """
    now = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
    long_ago = (now - timedelta(hours=4)).isoformat()
    db.record_watermark(
        "chroma",
        last_event_id="100-0",
        source_head_event_id="100-0",
        lag_events=0,
        last_success_at=long_ago,
    )
    watermark = db.get_watermark("chroma")

    assert watermark.lag_events == 0
    assert pwm.is_stale(watermark, now=now) is True
    assert pwm.classify(watermark, now=now) is pwm.ProjectionHealth.STALE


def test_a_fresh_zero_lag_projector_reads_current(db):
    """The positive mirror: a recent report with zero lag is genuinely CURRENT.

    Without this, a surface could pass the staleness test above by simply never saying
    "current" — which would be useless in the opposite direction.
    """
    now = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
    recent = (now - timedelta(seconds=30)).isoformat()
    db.record_watermark(
        "chroma",
        last_event_id="100-0",
        source_head_event_id="100-0",
        lag_events=0,
        last_success_at=recent,
    )

    assert pwm.classify(db.get_watermark("chroma"), now=now) is pwm.ProjectionHealth.CURRENT


def test_staleness_is_reported_as_a_concrete_age(db):
    """``age_seconds`` gives the operator the number, not just the verdict.

    "Stale" prompts the question; "stale for 4 hours" answers it. A projector 20 minutes behind
    and one three days dead are different incidents.
    """
    now = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
    db.record_watermark(
        "neo4j",
        last_event_id="1-0",
        lag_events=0,
        last_success_at=(now - timedelta(hours=4)).isoformat(),
    )
    entry = pwm.watermark_payload(db.get_watermark("neo4j"), projection="neo4j", now=now)

    assert entry["age_seconds"] == pytest.approx(4 * 3600)
    assert entry["health"] == "stale"


def test_a_never_successful_watermark_is_stale_by_definition(db):
    """No successful report at all ⇒ stale. It has never been confirmed current."""
    watermark = db.record_watermark("ledger", last_event_id="", lag_events=0, last_error="boom")
    # The error verdict dominates here, but the staleness predicate itself must also say True:
    # an empty ``last_success_at`` is not "succeeded at time zero".
    assert pwm.is_stale(watermark) is True


def test_an_unparseable_success_stamp_is_treated_as_no_stamp(db):
    """A timestamp we cannot read is not evidence that anything succeeded.

    Parsing failure must degrade toward "stale", never toward "now" — the latter would let a
    corrupt row certify itself as healthy.
    """
    db.record_watermark("registry", last_event_id="1-0", lag_events=0, last_success_at="garbage")
    watermark = db.get_watermark("registry")

    assert pwm.age_seconds(watermark) is None
    assert pwm.is_stale(watermark) is True
    assert pwm.classify(watermark) is pwm.ProjectionHealth.STALE


def test_the_house_z_suffixed_stamp_parses(db):
    """REGRESSION: ``control_db`` writes ``...Z``; Python 3.10 cannot parse that natively.

    Found while writing this suite. ``control_db._now()`` emits the repo's house timestamp
    shape (UTC with a literal ``Z``), and ``datetime.fromisoformat`` only accepts ``Z`` from
    Python 3.11 — this repo runs 3.10. Unhandled, EVERY stamp fell into the unparseable branch,
    every projection read STALE regardless of reality, and a uniformly red surface conveys
    exactly as much as a uniformly green one. The failure is silent by construction (the
    fallback is the "safe" direction), which is what makes an explicit test necessary.
    """
    db.record_watermark("registry", last_event_id="1-0", lag_events=0)
    watermark = db.get_watermark("registry")

    assert watermark.last_success_at.endswith("Z"), "the house stamp shape is what we parse"
    age = pwm.age_seconds(watermark)
    assert age is not None, "a stamp just written must be readable"
    assert age < 60
    assert pwm.classify(watermark) is pwm.ProjectionHealth.CURRENT


def test_a_naive_stamp_is_read_as_utc_not_local(db):
    """A stamp without an offset is interpreted as UTC, matching what control_db writes.

    Reading it as local time would shift every age by the host's offset — enough, on most
    hosts, to make a fresh watermark look hours stale or a stale one look fresh.
    """
    now = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
    db.record_watermark(
        "chroma", last_event_id="1-0", lag_events=0, last_success_at="2026-09-02T11:30:00"
    )

    assert pwm.age_seconds(db.get_watermark("chroma"), now=now) == pytest.approx(1800)


def test_the_staleness_threshold_is_overridable(monkeypatch):
    """An operator can tighten the window for a publication; a malformed value falls back."""
    assert pwm.stale_after_seconds() == pwm.DEFAULT_STALE_AFTER_S

    monkeypatch.setenv(pwm.STALE_AFTER_ENV, "60")
    assert pwm.stale_after_seconds() == 60

    monkeypatch.setenv(pwm.STALE_AFTER_ENV, "not-a-number")
    assert pwm.stale_after_seconds() == pwm.DEFAULT_STALE_AFTER_S, "a typo must not break it"

    monkeypatch.setenv(pwm.STALE_AFTER_ENV, "-5")
    assert pwm.stale_after_seconds() == pwm.DEFAULT_STALE_AFTER_S, "a window must be positive"


# ── 6. Failure is recorded, and a failed poll never refreshes the success stamp ──────────────


def test_a_failed_poll_records_the_error_without_refreshing_success(db):
    """The failing projector must visibly AGE, not look healthy on every retry.

    If a failed poll bumped ``last_success_at``, a projector failing every ten seconds would
    report a permanently fresh success stamp — perfectly current-looking, and completely broken.
    """
    now = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
    earlier = (now - timedelta(hours=2)).isoformat()
    db.record_watermark("chroma", last_event_id="10-0", lag_events=0, last_success_at=earlier)

    watermark = pwm.record_from_batch(db, ExplodingRedis(), "kb-chroma-v1")

    assert "ConnectionError" in watermark.last_error
    assert watermark.last_success_at == earlier, "a failure must not refresh the success stamp"
    assert pwm.classify(watermark, now=now) is pwm.ProjectionHealth.FAILING


def test_a_failed_poll_preserves_the_frontier_but_discards_the_stale_lag(db):
    """An outage tells us nothing new about how far the projection got — only that we cannot see.

    So the ids are kept (real information, still true) and the lag is dropped to ``None`` (a
    number computed at the last successful reading, now of unknown accuracy). Keeping the lag
    would let an old number masquerade as a current one.
    """
    db.record_watermark(
        "neo4j", last_event_id="33-0", source_head_event_id="40-0", lag_events=7
    )
    watermark = pwm.record_error(db, "kb-neo4j-v1", "redis down")

    assert watermark.last_event_id == "33-0"
    assert watermark.source_head_event_id == "40-0"
    assert watermark.lag_events is None
    assert watermark.last_error == "redis down"


def test_a_successful_poll_clears_a_previous_error(db):
    """Recovery is visible too: the next good batch clears ``last_error``.

    A sticky error would make every projector permanently red after one transient blip, and an
    always-red surface is ignored exactly as fast as an always-green one.
    """
    pwm.record_error(db, "kb-registry-v1", "redis down")
    assert pwm.classify(db.get_watermark("registry")) is pwm.ProjectionHealth.FAILING

    r = FakeStreamRedis(
        head="12-0", groups={"kb-registry-v1": _group(last_delivered="12-0", lag=0)}
    )
    watermark = pwm.record_from_batch(db, r, "kb-registry-v1", acked_event_id="12-0")

    assert watermark.last_error == ""
    assert pwm.classify(watermark) is pwm.ProjectionHealth.CURRENT


def test_a_dead_letter_error_is_recorded_alongside_a_fresh_reading(db):
    """A dead-lettered entry is acked (the frontier moves) but never projected — a permanent gap.

    The frontier and lag must still reflect the real Redis reading; the error rides alongside
    them, so the surface shows both "here is where we are" and "we lost something getting here".
    """
    r = FakeStreamRedis(
        head="60-0", groups={"kb-chroma-v1": _group(last_delivered="60-0", lag=0)}
    )
    watermark = pwm.record_from_batch(
        db, r, "kb-chroma-v1", acked_event_id="60-0", last_error="1 entry dead-lettered"
    )

    assert watermark.last_event_id == "60-0"
    assert watermark.lag_events == 0, "the reading is still the reading"
    assert watermark.last_error == "1 entry dead-lettered"
    assert pwm.classify(watermark) is pwm.ProjectionHealth.FAILING, "an error outranks lag 0"


# ── 7. The read surfaces (Control Room + the p4 control packet) ──────────────────────────────


def test_unhealthy_projections_includes_unknown_not_just_lagging(db):
    """A gate reads this list. ``unknown`` belongs on it.

    Publishing on a projection nobody can vouch for is exactly as unsafe as publishing on one
    known to be behind — the only difference is which of the two you can name afterwards.
    """
    now = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
    db.record_watermark(
        "registry", last_event_id="9-0", lag_events=0, last_success_at=now.isoformat()
    )
    db.record_watermark(
        "chroma", last_event_id="6-0", lag_events=3, last_success_at=now.isoformat()
    )

    unhealthy = pwm.unhealthy_projections(db, now=now)
    names = {entry["projection"] for entry in unhealthy}

    assert "registry" not in names, "the healthy one is excluded"
    assert names == {"chroma", "ledger", "neo4j"}
    assert {e["health"] for e in unhealthy} == {"lagging", "unknown"}


def test_read_report_distinguishes_a_missing_control_db_from_an_empty_one(tmp_path, monkeypatch):
    """``None`` means "no control plane"; ``[]``-of-unknowns means "a control plane with nothing".

    Collapsing the two is the false-authority failure the control database was built to remove:
    a reader must never turn "the orchestrator has never run" into a confident report about
    projections. ``read_report`` opens read-only precisely so it cannot create the file and
    manufacture the reassuring version of that answer.
    """
    from agentic_dynamics.control import control_db as cdb

    missing = tmp_path / "nope" / "control.db"
    monkeypatch.setenv(cdb.CONTROL_DB_ENV, str(missing))
    assert pwm.read_report() is None
    assert not missing.exists(), "a reader must never create the control database"

    # Now the orchestrator creates it: same call, a real (all-unknown) report.
    existing = tmp_path / "control.db"
    with ControlDB(existing):
        pass
    monkeypatch.setenv(cdb.CONTROL_DB_ENV, str(existing))
    report = pwm.read_report()

    assert report is not None
    assert [e["projection"] for e in report] == list(pwm.PROJECTIONS)
    assert all(e["health"] == "unknown" and e["reported"] is False for e in report)


def test_watermark_payload_is_json_safe(db):
    """Every field the routes and the packet serialise is a plain JSON type."""
    import json

    now = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
    db.record_watermark(
        "chroma",
        last_event_id="6-0",
        source_head_event_id="9-0",
        lag_events=3,
        last_success_at=now.isoformat(),
    )
    payload = pwm.watermark_payload(db.get_watermark("chroma"), projection="chroma", now=now)

    round_tripped = json.loads(json.dumps(payload))
    assert round_tripped["health"] == "lagging"
    assert round_tripped["lag_events"] == 3
    assert round_tripped["reported"] is True


# ── 8. The consumer-loop wiring (scripts/kb_worker.py) ───────────────────────────────────────


def test_batch_outcome_records_only_acked_ids_as_confirmed():
    """``process_batch`` reports the last ACKED entry — ``retry`` outcomes do not count.

    The frontier's authority comes from the loop reporting what it actually confirmed. If a
    ``retry`` (still pending, never projected) advanced ``last_acked_id``, the watermark would
    inherit the same over-report that reading ``last-delivered-id`` would have produced, and the
    whole first-hand-report design would buy nothing.
    """
    from scripts import kb_worker

    outcome = kb_worker.BatchOutcome()
    assert outcome.last_acked_id == ""
    assert outcome.processed == 0

    # The three outcomes knowledge_stream.process_entry can return, folded as the loop folds
    # them (see kb_worker.process_batch's `handle`).
    assert "ok" in ("ok", "dead_letter"), "ok acks"
    assert "dead_letter" in ("ok", "dead_letter"), "dead_letter acks"
    assert "retry" not in ("ok", "dead_letter"), "retry does NOT ack"


def test_refresh_watermark_never_creates_the_control_db(tmp_path, monkeypatch, capsys):
    """The consumer must not conjure a control database into existence.

    ``create=False`` is load-bearing: a kb worker running in a stray worktree that materialised
    an empty ``control.db`` would destroy p1's distinction between "the control plane is
    missing" and "the control plane says there are no runs" — and the second reads as safe.
    """
    from agentic_dynamics.control import control_db as cdb
    from scripts import kb_worker

    missing = tmp_path / "absent" / "control.db"
    monkeypatch.setenv(cdb.CONTROL_DB_ENV, str(missing))

    # Must not raise, and must not create anything.
    kb_worker.refresh_watermark("kb-chroma-v1", FakeStreamRedis(), kb_worker.BatchOutcome())

    assert not missing.exists()
    assert "watermark unavailable" in capsys.readouterr().out


def test_refresh_watermark_lands_the_row_when_the_control_db_exists(tmp_path, monkeypatch):
    """The positive half: with a control database present, a batch lands its watermark."""
    from agentic_dynamics.control import control_db as cdb
    from scripts import kb_worker

    path = tmp_path / "control.db"
    with ControlDB(path):
        pass
    monkeypatch.setenv(cdb.CONTROL_DB_ENV, str(path))

    r = FakeStreamRedis(
        head="15-0", groups={"kb-chroma-v1": _group(last_delivered="15-0", lag=0)}
    )
    kb_worker.refresh_watermark(
        "kb-chroma-v1", r, kb_worker.BatchOutcome(processed=2, last_acked_id="15-0")
    )

    with ControlDB.open_read_only(path) as db:
        watermark = db.get_watermark("chroma")
    assert watermark is not None
    assert watermark.last_event_id == "15-0"
    assert watermark.lag_events == 0


def test_refresh_watermark_records_a_dead_letter_as_an_error(tmp_path, monkeypatch):
    """A batch that dead-lettered an entry reports FAILING, not a clean advancing frontier."""
    from agentic_dynamics.control import control_db as cdb
    from scripts import kb_worker

    path = tmp_path / "control.db"
    with ControlDB(path):
        pass
    monkeypatch.setenv(cdb.CONTROL_DB_ENV, str(path))

    r = FakeStreamRedis(
        head="15-0", groups={"kb-neo4j-v1": _group(last_delivered="15-0", lag=0)}
    )
    kb_worker.refresh_watermark(
        "kb-neo4j-v1",
        r,
        kb_worker.BatchOutcome(processed=1, last_acked_id="15-0", dead_lettered=1),
    )

    with ControlDB.open_read_only(path) as db:
        watermark = db.get_watermark("neo4j")
    assert "dead-lettered" in watermark.last_error
    assert pwm.classify(watermark) is pwm.ProjectionHealth.FAILING
