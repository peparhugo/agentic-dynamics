"""The abandon rail: dry-run fidelity, the recorded transition, and its refusals."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from agentic_dynamics.control.control_db import ControlDB, RunState  # noqa: E402

import abandon_run as ar  # noqa: E402


def _db(tmp_path: Path) -> ControlDB:
    return ControlDB.open(tmp_path / "control.db")


def _seed(db: ControlDB, *, state: RunState, spec: str = "flow") -> str:
    """Create a run at 'running' (the only creatable non-queued state) and walk it to `state`."""
    run = db.create_run(
        spec_name=spec,
        model="deepseek/deepseek-v4-flash",
        state=RunState.RUNNING,
        reason="seed",
        candidate_sha="a" * 40,
    )
    if state != RunState.RUNNING:
        # running -> verifying -> promotable is the recorded path (every non-running state is
        # reached by a transition; the db refuses a created-in-promotable row by construction).
        db.transition_run(run.run_id, RunState.VERIFYING, reason="seed: verifying", actor="seed")
        db.transition_run(run.run_id, state, reason="seed: target", actor="seed")
    return run.run_id


def test_dry_run_reports_without_writing(tmp_path: Path):
    """Dry-run is the default: the row is reported and its state is untouched."""
    db = _db(tmp_path)
    run_id = _seed(db, state=RunState.PROMOTABLE)
    doc = ar.run_abandon(
        db, run_ids=(run_id,), reason="stale", operator="tester", dry_run=True
    )
    assert [e["run_id"] for e in doc["would_cancel"]] == [run_id]
    assert doc["cancelled"] == []
    assert db.get_run(run_id).state == RunState.PROMOTABLE


def test_apply_cancels_and_records_the_operator_and_reason(tmp_path: Path):
    """--apply transitions promotable -> cancelled through the API, reason + actor recorded."""
    db = _db(tmp_path)
    run_id = _seed(db, state=RunState.PROMOTABLE)
    doc = ar.run_abandon(
        db,
        run_ids=(run_id,),
        reason="superseded iteration",
        operator="peparhugo",
        dry_run=False,
    )
    assert [e["run_id"] for e in doc["cancelled"]] == [run_id]
    assert db.get_run(run_id).state == RunState.CANCELLED
    transitions = db.transitions(run_id) if hasattr(db, "transitions") else []
    recorded = " ".join(str(getattr(t, "reason", "")) for t in transitions)
    assert "abandoned by peparhugo" in recorded or "superseded iteration" in recorded


def test_refuses_a_non_promotable_row_and_reports_missing_ids(tmp_path: Path):
    """Only promotable rows are this command's business; a running row and an unknown id are
    reported, never silently skipped."""
    db = _db(tmp_path)
    running = _seed(db, state=RunState.RUNNING)
    doc = ar.run_abandon(
        db,
        run_ids=(running, "run-does-not-exist"),
        reason="x",
        operator="tester",
        dry_run=False,
    )
    assert doc["cancelled"] == []
    assert [e["run_id"] for e in doc["refused"]] == [running]
    assert "not promotable" in doc["refused"][0]["reason"]
    assert doc["missing"], "an unknown id must be reported as missing"
    assert db.get_run(running).state == RunState.RUNNING
