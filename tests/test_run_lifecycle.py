"""Tests for the run heartbeat + the zombie-run sweep (``control_db_evidence`` e2).

Both directions, per the phase mandate:

* the heartbeat is a *liveness proof*, not a state transition: it upserts
  ``run_heartbeats`` without touching ``runs``/``run_transitions``/the epoch, and the
  orchestrator-side thread beats until the process dies;
* the sweep cancels a ``running`` run whose heartbeat has expired via the LEGITIMATE transition
  API (``transition_run`` over ``ALLOWED_TRANSITIONS`` — the append-only transition log gains the
  row), never raw SQL; it does NOT touch a run with a fresh heartbeat (VERIFY c) nor a run with
  no heartbeat row (unknown ≠ dead); and a per-run transition failure is reported and never
  aborts the pass (VERIFY d).

The database is always real (a SQLite file under ``tmp_path``) — the transition-log claim is a
claim about SQLite transactions, and a mocked database would prove nothing about them.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

from agentic_dynamics.control.control_db import (
    ControlDB,
    ControlDBError,
    RunState,
    UnknownRunError,
)
from agentic_dynamics.control.run_lifecycle import (
    RunHeartbeatThread,
    ZombieSweepReport,
    classify_running_run,
    sweep_zombie_runs,
)

# A heartbeat interval short enough for a deterministic thread test without slowing the suite.
TEST_HEARTBEAT_INTERVAL_S = 1


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _past(seconds_ago: float) -> str:
    return _iso(_now_utc() - timedelta(seconds=seconds_ago))


@pytest.fixture()
def db(tmp_path):
    handle = ControlDB.open(tmp_path / "control" / "control.db")
    yield handle
    handle.close()


def make_running_run(db, *, spec_name="control_db_evidence", at=None) -> str:
    return db.create_run(
        spec_name=spec_name,
        model="deepseek/deepseek-v4-flash",
        state=RunState.RUNNING,
        started_at=at,
    ).run_id


# ── The heartbeat storage (control_db) ───────────────────────────────────────────────────────


def test_record_run_heartbeat_upserts_and_does_not_bump_the_epoch(db):
    """A beat is a liveness proof, NOT a state change: upserting it updates last_seen_at /
    beat_count and leaves the control epoch + transition log untouched."""
    run_id = make_running_run(db)
    epoch_before = db.control_epoch()
    transitions_before = len(db.transitions(run_id))  # the creation transition only
    old_stamp = _past(60)
    newer_stamp = _past(30)

    first = db.record_run_heartbeat(run_id, actor="orchestrator", at=old_stamp)
    assert first.beat_count == 1
    assert first.last_seen_at == old_stamp

    second = db.record_run_heartbeat(run_id, actor="orchestrator", at=newer_stamp)
    assert second.beat_count == 2
    assert second.last_seen_at == newer_stamp

    # No run_transitions row was appended (not a state change) and the epoch did not move.
    assert len(db.transitions(run_id)) == transitions_before
    assert db.control_epoch() == epoch_before


def test_record_run_heartbeat_refuses_an_unknown_run(db):
    """A beat for a run that was never recorded would be a proof of life for a phantom."""
    with pytest.raises(UnknownRunError):
        db.record_run_heartbeat("run-does-not-exist")


# ── The sweep classification ─────────────────────────────────────────────────────────────────


def test_classify_running_run_is_three_valued(db):
    """live / zombie / unknown — a run with NO heartbeat row is never called a zombie."""
    run_id = make_running_run(db)
    run = db.get_run(run_id)
    cutoff = _iso(_now_utc() - timedelta(seconds=600))

    assert classify_running_run(run, None, cutoff=cutoff) == "unknown"

    fresh = db.record_run_heartbeat(run_id, at=_iso(_now_utc()))
    assert classify_running_run(run, fresh, cutoff=cutoff) == "live"

    stale = db.record_run_heartbeat(run_id, at=_past(3600))
    assert classify_running_run(run, stale, cutoff=cutoff) == "zombie"


# ── The zombie-run sweep ─────────────────────────────────────────────────────────────────────


def test_sweep_cancels_a_zombie_via_the_legitimate_transition_api(db):
    """(b) A 'running' run whose heartbeat expired (no heartbeat for N minutes) is transitioned
    to CANCELLED through transition_run — the append-only run_transitions log gains the row."""
    zombie = make_running_run(db)
    db.record_run_heartbeat(zombie, at=_past(3600))  # beat over an hour ago

    report = sweep_zombie_runs(db, stale_after_seconds=600)

    assert report.examined == 1
    assert zombie in report.zombie_ids
    assert len(report.cancelled) == 1
    entry = report.cancelled[0]
    assert entry["run_id"] == zombie
    assert entry["from_state"] == "running"
    assert "zombie" in entry["reason"]

    # The run really moved — through the API, so the history is append-only and honest.
    assert db.get_run(zombie).state is RunState.CANCELLED
    history = db.transitions(zombie)
    assert history[-1].from_state is RunState.RUNNING
    assert history[-1].to_state is RunState.CANCELLED
    assert history[-1].actor == "zombie-sweep"
    assert "last heartbeat" in history[-1].reason
    # Cancellation is terminal: a second sweep leaves the (now terminal) run alone.
    report2 = sweep_zombie_runs(db, stale_after_seconds=600)
    assert report2.examined == 0


def test_sweep_never_touches_a_live_run_with_a_fresh_heartbeat(db):
    """(c) A live run with a fresh heartbeat is NOT touched — not cancelled, not transitioned."""
    live = make_running_run(db)
    db.record_run_heartbeat(live, at=_iso(_now_utc()))  # beat right now

    report = sweep_zombie_runs(db, stale_after_seconds=600)

    assert report.cancelled == ()
    assert live in report.live
    assert db.get_run(live).state is RunState.RUNNING
    assert db.transitions(live)[-1].to_state is RunState.RUNNING  # creation only


def test_sweep_reports_unknown_runs_and_leaves_them_alone(db):
    """A 'running' run with NO heartbeat row is reported as unknown and left running — absence
    of evidence of life is not evidence of death."""
    orphan = make_running_run(db)  # never beat (a pre-e2 run, or dead before its first beat)

    report = sweep_zombie_runs(db, stale_after_seconds=600)

    assert orphan in report.unknown
    assert report.cancelled == ()
    assert db.get_run(orphan).state is RunState.RUNNING


def test_sweep_dry_run_cancels_nothing(db):
    """--dry-run previews the zombies the sweep WOULD cancel without transitioning anything."""
    zombie = make_running_run(db)
    db.record_run_heartbeat(zombie, at=_past(3600))

    report = sweep_zombie_runs(db, stale_after_seconds=600, dry_run=True)

    assert len(report.would_cancel) == 1
    assert report.cancelled == ()
    assert zombie in report.zombie_ids
    assert db.get_run(zombie).state is RunState.RUNNING  # untouched


def test_sweep_mixes_live_unknown_and_zombie_in_one_pass(db):
    """One pass accounts for every running run, partitioning examined into the three buckets."""
    zombie = make_running_run(db)
    db.record_run_heartbeat(zombie, at=_past(3600))
    live = make_running_run(db)
    db.record_run_heartbeat(live, at=_iso(_now_utc()))
    unknown = make_running_run(db)

    report = sweep_zombie_runs(db, stale_after_seconds=600)

    assert report.examined == 3
    assert zombie in report.zombie_ids
    assert live in report.live
    assert unknown in report.unknown
    # The parts add up to the whole.
    assert len(report.cancelled) + len(report.live) + len(report.unknown) == report.examined
    assert db.get_run(live).state is RunState.RUNNING
    assert db.get_run(unknown).state is RunState.RUNNING


def test_sweep_failure_on_one_run_never_aborts_the_pass(db, monkeypatch):
    """(d) A per-run transition refusal is recorded in errors and the sweep continues — a sweep
    failure never fails a run, not even the one it is trying to cancel."""
    failing = make_running_run(db)
    db.record_run_heartbeat(failing, at=_past(3600))
    succeeding = make_running_run(db)
    db.record_run_heartbeat(succeeding, at=_past(3600))

    original = db.transition_run

    def flaky(run_id, new_state, **kwargs):
        if run_id == failing:
            raise ControlDBError("simulated refusal: the orchestrator just transitioned it")
        return original(run_id, new_state, **kwargs)

    monkeypatch.setattr(db, "transition_run", flaky)

    report = sweep_zombie_runs(db, stale_after_seconds=600)

    assert any(failing in error for error in report.errors)
    assert len(report.cancelled) == 1
    assert report.cancelled[0]["run_id"] == succeeding
    assert db.get_run(succeeding).state is RunState.CANCELLED
    assert db.get_run(failing).state is RunState.RUNNING  # the failed row was left untouched


def test_sweep_report_serializes(db):
    """The report renders to a stable, JSON-ready dict (the CLI's machine surface)."""
    live = make_running_run(db)
    db.record_run_heartbeat(live, at=_iso(_now_utc()))
    report = sweep_zombie_runs(db, stale_after_seconds=600)
    as_dict = report.to_dict()
    assert set(as_dict) == {
        "examined", "cancelled", "would_cancel", "live", "unknown", "errors",
    }
    assert isinstance(report, ZombieSweepReport)


# ── The orchestrator-side heartbeat thread ───────────────────────────────────────────────────


def _noop_log(_msg):
    pass


def test_heartbeat_thread_beats_until_stopped(db, tmp_path):
    """A started thread proves the run is alive (fresh beats accumulate); stop() halts it."""
    run_id = make_running_run(db)
    thread = RunHeartbeatThread(
        db.path, run_id, interval_s=TEST_HEARTBEAT_INTERVAL_S, log=_noop_log
    )
    thread.start()
    try:
        # Poll for at least two beats (the immediate one + one scheduled). The generous 5s
        # deadline makes the claim comfortable rather than marginal: any slow CI still sees the
        # thread beat more than once at a 1s interval.
        deadline = time.monotonic() + 5.0
        beat_count = 0
        while time.monotonic() < deadline:
            heartbeat = db.run_heartbeat(run_id)
            if heartbeat is not None and heartbeat.beat_count >= 2:
                beat_count = heartbeat.beat_count
                break
            time.sleep(0.05)
        heartbeat = db.run_heartbeat(run_id)
        assert heartbeat is not None
        assert heartbeat.beat_count >= 2  # immediate beat + at least one scheduled beat
        assert beat_count >= 2
        # The most recent beat is fresh (inside the staleness window).
        fresh_cutoff = _iso(_now_utc() - timedelta(seconds=600))
        assert heartbeat.last_seen_at >= fresh_cutoff
    finally:
        thread.stop()

    # stop() is idempotent and the run is untouched by the heartbeat (no transitions added).
    thread.stop()
    assert db.get_run(run_id).state is RunState.RUNNING
    assert len(db.transitions(run_id)) == 1


def test_heartbeat_thread_failure_is_swallowed_and_logged(db):
    """(d) A failed beat is logged and swallowed — a bookkeeping outage never fails the run."""
    messages: list[str] = []
    # Point the beat at a run that does not exist: record_run_heartbeat refuses, the thread logs
    # and moves on rather than raising.
    thread = RunHeartbeatThread(
        db.path, "run-no-such-run", interval_s=TEST_HEARTBEAT_INTERVAL_S,
        log=messages.append,
    )
    thread._beat()
    assert messages, "the failed beat must have been logged"
    assert "no run" in messages[0] or "beat skipped" in messages[0]
