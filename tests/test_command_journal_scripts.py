"""Tests for the script-side command-journal helper (step 10).

The act-key discipline is the contract: a fresh act records an intent; a rerun REUSES a crashed
attempt's intent row (the crash evidence must survive); a terminal row advances to a new
suffixed attempt (a retry is a new attempt of the same act); an actor-less begin refuses; any
recording failure raises loudly while a receipt failure warns and never raises.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src", _ROOT / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from _command_journal import (  # noqa: E402
    CommandJournalError,
    begin_command,
    finish_command,
)

from agentic_dynamics.control.control_db import ControlDB  # noqa: E402


def _begin(db_path, **overrides):
    kwargs = {
        "verb": "promote",
        "actor": "aio",
        "rationale": "because the gates passed",
        "act_key": "promote:spec:abc123",
        "run_id": "run-1",
        "candidate_sha": "abc123",
        "target_kind": "run",
        "target_id": "run-1",
    }
    kwargs.update(overrides)
    return begin_command(db_path, **kwargs)


def test_begin_records_the_intent_with_its_fields(tmp_path):
    command = _begin(tmp_path / "control.db")
    assert command.verb == "promote"
    assert command.state == "intent"
    assert command.actor == "aio"
    assert command.rationale == "because the gates passed"
    assert command.idempotency_key == "promote:spec:abc123"
    assert command.run_id == "run-1"
    assert command.candidate_sha == "abc123"


def test_a_rerun_reuses_a_crashed_attempts_intent_row(tmp_path):
    db = tmp_path / "control.db"
    first = _begin(db)
    again = _begin(db)
    assert again.command_id == first.command_id  # the row IS the crash evidence; do not fork it
    assert again.state == "intent"
    with ControlDB.open_read_only(db) as reader:
        assert len(reader.commands()) == 1


def test_a_completed_row_returns_by_default_so_the_guard_can_fire(tmp_path):
    """The review's replay reproduction: promote guards on ``state == "completed"`` — with the
    old helper behavior (always advancing) that guard could NEVER fire, because a replay minted
    a fresh intent instead of returning the finished row."""
    db = tmp_path / "control.db"
    first = _begin(db)
    assert finish_command(db, command_id=first.command_id, state="completed", receipt={"ok": 1}) is None

    again = _begin(db)
    assert again.command_id == first.command_id
    assert again.state == "completed"
    assert again.idempotency_key == "promote:spec:abc123"


def test_completed_advance_is_the_explicit_redeploy_policy(tmp_path):
    """``completed="advance"`` is a per-verb choice (publish's recovery path), never a default."""
    db = tmp_path / "control.db"
    first = _begin(db)
    finish_command(db, command_id=first.command_id, state="completed", receipt={})

    second = _begin(db, completed="advance")
    assert second.command_id != first.command_id
    assert second.idempotency_key == "promote:spec:abc123#2"
    assert second.state == "intent"


def test_failed_and_refused_rows_always_advance(tmp_path):
    """A retry after a recorded failure is a new authorized attempt, not a replay."""
    db = tmp_path / "control.db"
    first = _begin(db)
    finish_command(db, command_id=first.command_id, state="failed", receipt={"err": "push"})

    second = _begin(db)  # default policy: failed rows still advance
    assert second.idempotency_key == "promote:spec:abc123#2"

    finish_command(db, command_id=second.command_id, state="refused", receipt={})
    third = _begin(db)
    assert third.idempotency_key == "promote:spec:abc123#3"


def test_an_unknown_completed_policy_refuses(tmp_path):
    with pytest.raises(CommandJournalError, match="completed must be"):
        _begin(tmp_path / "control.db", completed="replay")


def test_an_actorless_begin_refuses(tmp_path):
    with pytest.raises(CommandJournalError, match="actor"):
        _begin(tmp_path / "control.db", actor="   ")


def test_an_unrecordable_journal_is_a_named_error(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("occupied")  # a path THROUGH a file can never hold the journal
    with pytest.raises(CommandJournalError, match="unavailable"):
        _begin(blocker / "control.db")


def test_a_receipt_records_the_outcome_and_bad_moves_warn(tmp_path):
    db = tmp_path / "control.db"
    command = _begin(db)
    warning = finish_command(
        db, command_id=command.command_id, state="completed", receipt={"squash": "abc"}
    )
    assert warning is None
    with ControlDB.open_read_only(db) as reader:
        done = reader.command(command.command_id)
        assert done.state == "completed"

    # completed -> failed is not in the journal's graph: a warning, never a raise
    warning = finish_command(db, command_id=command.command_id, state="failed", receipt={})
    assert warning is not None
    assert "could not record" in warning


def test_a_missing_command_receipt_warns(tmp_path):
    warning = finish_command(
        tmp_path / "control.db", command_id="cmd-nope", state="completed", receipt={}
    )
    assert warning is not None
    assert "cmd-nope" in warning
