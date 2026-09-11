"""Step 2e: the command journal — intent before act, durable receipts, rerun-safe by key.

"Recording is part of the act": a consequential command persists its intent BEFORE the external
effect and its observed outcome AFTER, so a crash between the two leaves visible evidence (a
row in ``state=intent``) rather than a gap. A repeated ``idempotency_key`` returns the existing
row — a re-invocation is idempotent at the journal boundary.
"""

from __future__ import annotations

import pytest

from agentic_dynamics.control.control_db import ControlDB, ControlDBError, RunState


def _db(tmp_path) -> ControlDB:
    return ControlDB.open(tmp_path / "control.db")


def test_intent_then_receipt_round_trip(tmp_path):
    with _db(tmp_path) as db:
        run = db.create_run(
            spec_name="s", model="m", state=RunState.RUNNING, reason="start",
            candidate_sha="a" * 40,
        )
        command = db.record_command_intent(
            "approve", actor="aio", rationale="looks good", run_id=run.run_id,
            candidate_sha=run.candidate_sha, target_kind="gate", target_id="g1",
            idempotency_key="approve:1",
        )
        assert command.state == "intent"
        assert command.rationale == "looks good"

        done = db.complete_command(
            command.command_id, state="completed", receipt={"approval_id": "apr-1"}
        )
        assert done.state == "completed"
        assert '"approval_id"' in done.receipt_json
        assert [c.command_id for c in db.commands(run_id=run.run_id)] == [command.command_id]
        assert db.commands(state="completed")[0].command_id == command.command_id


def test_rerun_safe_by_idempotency_key(tmp_path):
    with _db(tmp_path) as db:
        first = db.record_command_intent("approve", actor="aio", idempotency_key="k1")
        again = db.record_command_intent("approve", actor="aio", idempotency_key="k1")
        assert again.command_id == first.command_id
        assert len(db.commands()) == 1


def test_illegal_state_moves_refuse(tmp_path):
    with _db(tmp_path) as db:
        command = db.record_command_intent("approve", actor="aio")
        db.complete_command(command.command_id, state="refused")
        with pytest.raises(ControlDBError):
            db.complete_command(command.command_id, state="completed")


def test_intent_requires_verb_and_actor(tmp_path):
    with _db(tmp_path) as db:
        with pytest.raises(ControlDBError):
            db.record_command_intent("", actor="aio")
        with pytest.raises(ControlDBError):
            db.record_command_intent("approve", actor="")
