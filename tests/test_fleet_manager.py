"""Tests for the fleet manager's ``submit`` verb (p1_submit_contract).

The fleet-manager's job is narrow and deliberately dumb: mint a job id, LPUSH the submit
command onto ``fleet:commands``, and record a "launching" entry on the board. It does NOT
validate the request — that is the orchestrator's spawn-wrapper's job
(``scripts/fleet/spawn_wrapper.py:validate_submit_request``, covered in
``tests/test_spawn_wrapper.py``). These tests cover the supervisor-tier half of the contract:
the LPUSH shape, the board record, and that nothing here refuses a concurrent submit (there is
no orchestrator lock).
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _fleet_manager():
    fleet_dir = str(ROOT / "scripts" / "fleet")
    if fleet_dir not in sys.path:
        sys.path.insert(0, fleet_dir)
    return importlib.import_module("fleet_manager")


class _FakeRedis:
    """A minimal redis stand-in covering exactly the calls fleet_manager's submit path makes."""

    def __init__(self) -> None:
        self._hashes: dict[str, dict[str, str]] = {}
        self._lists: dict[str, list[str]] = {}

    def hset(self, key: str, mapping: dict | None = None, **_kw) -> None:
        self._hashes.setdefault(key, {}).update({k: str(v) for k, v in (mapping or {}).items()})

    def hvals(self, key: str) -> list[str]:
        return list(self._hashes.get(key, {}).values())

    def lpush(self, key: str, *values: str) -> int:
        self._lists.setdefault(key, []).extend(values)
        return len(self._lists[key])

    def llen(self, key: str) -> int:
        return len(self._lists.get(key, []))

    def scan_iter(self, match: str | None = None, count: int | None = None):
        return iter([])

    def hgetall(self, key: str) -> dict[str, str]:
        return {}


def test_send_submit_command_lpushes_a_bounded_submit_command():
    fm = _fleet_manager()
    r = _FakeRedis()
    cmd = fm._send_submit_command(
        r, spec="workflows/repository/fleet_job_submission.yaml", goal="g",
        model="anthropic/claude-sonnet-5", workdir="/tmp/wt_x",
    )
    assert cmd["action"] == "submit"
    assert cmd["spec"] == "workflows/repository/fleet_job_submission.yaml"
    assert cmd["model"] == "anthropic/claude-sonnet-5"
    assert cmd["workdir"] == "/tmp/wt_x"
    assert cmd["job_id"] and cmd["nonce"]

    queued = [json.loads(raw) for raw in r._lists[fm.COMMANDS_KEY]]
    assert queued == [cmd]


def test_send_submit_command_records_launching_on_the_board():
    fm = _fleet_manager()
    r = _FakeRedis()
    cmd = fm._send_submit_command(
        r, spec="workflows/repository/fleet_job_submission.yaml", goal="g",
        model="deepseek/deepseek-v4-pro", workdir="/tmp/wt_y",
    )
    board = fm.build_board(r)
    assert len(board["jobs"]) == 1
    job = board["jobs"][0]
    assert job["job_id"] == cmd["job_id"]
    assert job["spec"] == "workflows/repository/fleet_job_submission.yaml"
    assert job["model"] == "deepseek/deepseek-v4-pro"
    assert job["status"] == "launching"


def test_multiple_concurrent_submits_are_all_recorded_no_lock():
    # The design's "ZERO orchestrator lock" rule: nothing here refuses or serializes a second
    # submit while a first is still "launching" — both land on the board independently.
    fm = _fleet_manager()
    r = _FakeRedis()
    cmd_a = fm._send_submit_command(
        r, spec="workflows/repository/fleet_job_submission.yaml", goal="a",
        model="anthropic/claude-sonnet-5", workdir="/tmp/wt_a",
    )
    cmd_b = fm._send_submit_command(
        r, spec="workflows/repository/fleet_job_submission.yaml", goal="b",
        model="openai/gpt-5.6-luna", workdir="/tmp/wt_b",
    )
    assert cmd_a["job_id"] != cmd_b["job_id"]
    board = fm.build_board(r)
    job_ids = {j["job_id"] for j in board["jobs"]}
    assert job_ids == {cmd_a["job_id"], cmd_b["job_id"]}
    assert len(r._lists[fm.COMMANDS_KEY]) == 2


def test_submit_cli_dispatches_through_main(monkeypatch, capsys):
    # A true end-to-end CLI check: main()'s "submit" branch parses --spec/--goal/--model/
    # --workdir and drives the same _send_submit_command path the unit tests above exercise
    # directly — only _connect() is faked out (no real Redis in this test).
    fm = _fleet_manager()
    r = _FakeRedis()
    monkeypatch.setattr(fm, "_connect", lambda: r)

    rc = fm.main([
        "submit", "--spec", "workflows/repository/fleet_job_submission.yaml",
        "--goal", "g", "--model", "anthropic/claude-sonnet-5", "--workdir", "/tmp/wt_cli",
    ])
    assert rc == 0

    queued = [json.loads(raw) for raw in r._lists[fm.COMMANDS_KEY]]
    assert len(queued) == 1
    assert queued[0]["spec"] == "workflows/repository/fleet_job_submission.yaml"
    assert queued[0]["workdir"] == "/tmp/wt_cli"

    board = fm.build_board(r)
    assert board["jobs"][0]["status"] == "launching"

    out = capsys.readouterr().out
    assert "fleet:commands <-" in out
    assert "launching" in out
