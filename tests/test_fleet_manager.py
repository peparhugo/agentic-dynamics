"""Tests for the fleet manager's ``submit`` verb (p1_submit_contract).

The fleet-manager's job is narrow and deliberately dumb: mint a job id, LPUSH the submit
command onto ``fleet:commands``, and record a "launching" entry on the board. It does NOT
validate the request — that is the orchestrator's spawn-wrapper's job
(``scripts/fleet/spawn_wrapper.py:validate_submit_request``, covered in
``tests/test_spawn_wrapper.py``). These tests cover the supervisor-tier half of the contract:
the LPUSH shape, the board record, the caller-stable request key (reconcile, never
double-queue), and that nothing here refuses a concurrent submit for the same or another spec
(there is no orchestrator lock; the ONE named refusal is a request key reused for a different
submission).
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

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

    def hget(self, key: str, field: str) -> str | None:
        return self._hashes.get(key, {}).get(field)

    def lpush(self, key: str, *values: str) -> int:
        self._lists.setdefault(key, []).extend(values)
        return len(self._lists[key])

    def llen(self, key: str) -> int:
        return len(self._lists.get(key, []))

    def scan_iter(self, match: str | None = None, count: int | None = None):
        return iter([])

    def hgetall(self, key: str) -> dict[str, str]:
        return {}

    def eval(self, script: str, numkeys: int, *keys_and_args) -> list[str]:
        """Emulate the request-keyed submit script (single-threaded fake => atomic here).

        Contract: reconcile when the key exists, otherwise claim + queue + record, returning
        ``[first, record_json]`` — the NEW job id on the claim path, the EXISTING entry JSON
        on the reconcile path.
        """
        requests_key, commands_key, jobs_key = keys_and_args[0:3]
        request_key, job_id, command_raw, record_raw, entry_raw = keys_and_args[3:8]
        existing = self._hashes.get(requests_key, {}).get(request_key)
        if existing:
            try:
                entry = json.loads(existing)
                existing_job = str((entry or {}).get("job_id") or "")
            except (TypeError, ValueError):
                existing_job = ""
            return [existing, self._hashes.get(jobs_key, {}).get(existing_job, "")]
        self._hashes.setdefault(requests_key, {})[request_key] = str(entry_raw)
        self._lists.setdefault(commands_key, []).append(str(command_raw))
        self._hashes.setdefault(jobs_key, {})[str(job_id)] = str(record_raw)
        return [str(job_id), str(record_raw)]


def test_send_submit_command_lpushes_a_bounded_submit_command():
    fm = _fleet_manager()
    r = _FakeRedis()
    cmd = fm._send_submit_command(
        r,
        spec="workflows/repository/fleet_job_submission.yaml",
        goal="g",
        model="anthropic/claude-sonnet-5",
        workdir="/tmp/wt_x",
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
        r,
        spec="workflows/repository/fleet_job_submission.yaml",
        goal="g",
        model="deepseek/deepseek-v4-pro",
        workdir="/tmp/wt_y",
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
        r,
        spec="workflows/repository/fleet_job_submission.yaml",
        goal="a",
        model="anthropic/claude-sonnet-5",
        workdir="/tmp/wt_a",
    )
    cmd_b = fm._send_submit_command(
        r,
        spec="workflows/repository/fleet_job_submission.yaml",
        goal="b",
        model="openai/gpt-5.6-luna",
        workdir="/tmp/wt_b",
    )
    assert cmd_a["job_id"] != cmd_b["job_id"]
    board = fm.build_board(r)
    job_ids = {j["job_id"] for j in board["jobs"]}
    assert job_ids == {cmd_a["job_id"], cmd_b["job_id"]}
    assert len(r._lists[fm.COMMANDS_KEY]) == 2


# ── record_job_status: the launching -> running -> completed/failed transitions ──────────


def test_record_job_status_preserves_identifying_fields_across_transitions():
    fm = _fleet_manager()
    r = _FakeRedis()
    cmd = fm._send_submit_command(
        r,
        spec="workflows/repository/fleet_job_submission.yaml",
        goal="g",
        model="anthropic/claude-sonnet-5",
        workdir="/tmp/wt_z",
    )
    fm.record_job_status(r, cmd["job_id"], "running")
    fm.record_job_status(
        r,
        cmd["job_id"],
        "completed",
        returncode=0,
        ledger="experiments/results/workflows/fleet_job_submission/x.json",
    )
    board = fm.build_board(r)
    job = board["jobs"][0]
    assert job["job_id"] == cmd["job_id"]
    assert job["spec"] == "workflows/repository/fleet_job_submission.yaml"
    assert job["model"] == "anthropic/claude-sonnet-5"
    assert job["status"] == "completed"
    assert job["returncode"] == 0
    assert job["ledger"] == "experiments/results/workflows/fleet_job_submission/x.json"


def test_record_job_status_failed_carries_the_error_reason():
    fm = _fleet_manager()
    r = _FakeRedis()
    cmd = fm._send_submit_command(
        r,
        spec="workflows/repository/fleet_job_submission.yaml",
        goal="g",
        model="deepseek/deepseek-v4-pro",
        workdir="/tmp/wt_fail",
    )
    fm.record_job_status(r, cmd["job_id"], "failed", returncode=1, error="compose run exited 1")
    board = fm.build_board(r)
    job = board["jobs"][0]
    assert job["status"] == "failed"
    assert job["returncode"] == 1
    assert job["error"] == "compose run exited 1"


def test_record_job_status_on_an_unknown_job_id_still_writes_a_record():
    # A refused submit never went through record_job_launch (fleet_manager didn't mint it in
    # this test) — record_job_status must still produce a renderable record, not raise.
    fm = _fleet_manager()
    r = _FakeRedis()
    record = fm.record_job_status(r, "orphan-job", "failed", error="boom")
    assert record["job_id"] == "orphan-job"
    assert record["status"] == "failed"
    board = fm.build_board(r)
    assert board["jobs"][0]["job_id"] == "orphan-job"


def test_send_submit_command_carries_an_optional_image():
    fm = _fleet_manager()
    r = _FakeRedis()
    cmd = fm._send_submit_command(
        r,
        spec="workflows/repository/fleet_job_submission.yaml",
        goal="g",
        model="anthropic/claude-sonnet-5",
        workdir="/tmp/wt_x",
        image="fleet/job-example",
    )
    assert cmd["image"] == "fleet/job-example"
    queued = [json.loads(raw) for raw in r._lists[fm.COMMANDS_KEY]]
    assert queued == [cmd]


def test_send_submit_command_omits_image_field_when_not_given():
    fm = _fleet_manager()
    r = _FakeRedis()
    cmd = fm._send_submit_command(
        r,
        spec="workflows/repository/fleet_job_submission.yaml",
        goal="g",
        model="anthropic/claude-sonnet-5",
        workdir="/tmp/wt_x",
    )
    assert "image" not in cmd


def test_submit_cli_dispatches_through_main(monkeypatch, capsys):
    # A true end-to-end CLI check: main()'s "submit" branch parses --spec/--goal/--model/
    # --workdir and drives the same _send_submit_command path the unit tests above exercise
    # directly — only _connect() is faked out (no real Redis in this test).
    fm = _fleet_manager()
    r = _FakeRedis()
    monkeypatch.setattr(fm, "_connect", lambda: r)

    rc = fm.main(
        [
            "submit",
            "--spec",
            "workflows/repository/fleet_job_submission.yaml",
            "--goal",
            "g",
            "--model",
            "anthropic/claude-sonnet-5",
            "--workdir",
            "/tmp/wt_cli",
        ]
    )
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


def test_submit_cli_dispatches_the_optional_image_flag(monkeypatch):
    fm = _fleet_manager()
    r = _FakeRedis()
    monkeypatch.setattr(fm, "_connect", lambda: r)

    rc = fm.main(
        [
            "submit",
            "--spec",
            "workflows/repository/fleet_job_submission.yaml",
            "--goal",
            "g",
            "--model",
            "anthropic/claude-sonnet-5",
            "--workdir",
            "/tmp/wt_cli",
            "--image",
            "fleet/job-example",
        ]
    )
    assert rc == 0
    queued = [json.loads(raw) for raw in r._lists[fm.COMMANDS_KEY]]
    assert queued[0]["image"] == "fleet/job-example"


def test_send_submit_command_carries_the_extended_identity():
    """The extended submit identity (spec digest, continuation, admission) survives the
    manager's LPUSH hop — the orchestrator + broker re-validate it at the later gates."""
    fm = _fleet_manager()
    r = _FakeRedis()
    cmd = fm._send_submit_command(
        r,
        spec="workflows/repository/fleet_job_submission.yaml",
        goal="g",
        model="anthropic/claude-sonnet-5",
        workdir="/tmp/wt_x",
        spec_sha256="a" * 64,
        resume=True,
        parent_run_id="run-1",
        admission={"required": True, "campaign_budget_usd": 20.0},
    )
    assert cmd["spec_sha256"] == "a" * 64
    assert cmd["resume"] is True
    assert cmd["parent_run_id"] == "run-1"
    assert cmd["admission"] == {"required": True, "campaign_budget_usd": 20.0}
    queued = [json.loads(raw) for raw in r._lists[fm.COMMANDS_KEY]]
    assert queued == [cmd]


def test_send_submit_command_carries_the_execution_settings():
    """The manager passes the execution block through unchanged (the orchestrator + broker
    re-validate it; the manager's job is that it survives the hop)."""
    fm = _fleet_manager()
    r = _FakeRedis()
    execution = {
        "backend": "opencode",
        "thinking_effort": "high",
        "thinking_budget_tokens": 12000,
        "output_token_limit": 64000,
        "timeout_seconds": 2400,
        "no_commit": False,
    }
    cmd = fm._send_submit_command(
        r,
        spec="workflows/repository/fleet_job_submission.yaml",
        goal="g",
        model="anthropic/claude-sonnet-5",
        workdir="/tmp/wt_x",
        execution=execution,
    )
    assert cmd["execution"] == execution


def test_send_submit_command_carries_reserve_and_cap():
    """The manager passes the reserve/cap fields through unchanged (the orchestrator's armed
    gate reads them from the environment; the manager's job is that they survive the hop)."""
    fm = _fleet_manager()
    r = _FakeRedis()
    cmd = fm._send_submit_command(
        r,
        spec="workflows/repository/fleet_job_submission.yaml",
        goal="g",
        model="deepseek/deepseek-v4-flash",
        workdir="/tmp/wt_x",
        admission={"required": True, "reserve_usd": 0.6, "hard_cap_usd": 1.0},
    )
    assert cmd["admission"]["reserve_usd"] == 0.6
    assert cmd["admission"]["hard_cap_usd"] == 1.0


# ── The AIO binding identity in the submit envelope (Unit D) ──────────────────


def test_send_submit_command_carries_the_aio_binding_identity():
    """The manager's job is that the identity SURVIVES the hop, unchecked — the wrapper and
    the broker each resolve the binding by identity before any launch."""
    import json

    fm = _fleet_manager()
    r = _FakeRedis()
    aio = {
        "native_session_id": "ses_aio",
        "agent": "aio-control",
        "binding_id": "a" * 64,
        "task_revision": 2,
    }
    cmd = fm._send_submit_command(r, spec="s", goal="g", model="m", workdir="/tmp/w", aio=aio)
    assert cmd["actor"] == "aio"
    assert cmd["aio"] == aio
    queued = [json.loads(raw) for raw in r._lists[fm.COMMANDS_KEY]]
    assert queued[0]["aio"]["native_session_id"] == "ses_aio"
    assert queued[0]["actor"] == "aio"


def test_send_submit_command_without_aio_carries_no_actor(monkeypatch):
    fm = _fleet_manager()
    r = _FakeRedis()
    cmd = fm._send_submit_command(r, spec="s", goal="g", model="m", workdir="/tmp/w")
    assert "aio" not in cmd and "actor" not in cmd


def test_submit_cli_dispatches_the_aio_identity_flags(monkeypatch):
    """The tool's flags reach the envelope verbatim: tool → manager metadata path."""
    import json

    fm = _fleet_manager()
    r = _FakeRedis()
    monkeypatch.setattr(fm, "_connect", lambda: r)
    rc = fm.main(
        [
            "submit",
            "--spec",
            "workflows/repository/fleet_job_submission.yaml",
            "--goal",
            "g",
            "--model",
            "anthropic/claude-sonnet-5",
            "--workdir",
            "/tmp/wt_cli_aio",
            "--aio-session-id",
            "ses_cli",
            "--aio-agent",
            "aio-control",
            "--binding-id",
            "b" * 64,
            "--task-revision",
            "5",
        ]
    )
    assert rc == 0
    queued = [json.loads(raw) for raw in r._lists[fm.COMMANDS_KEY]]
    assert queued[0]["actor"] == "aio"
    assert queued[0]["aio"] == {
        "native_session_id": "ses_cli",
        "agent": "aio-control",
        "binding_id": "b" * 64,
        "task_revision": 5,
    }


# ── The caller-stable request key (2026-09-16 delivery simplification, Unit 2) ──

_REQ_SPEC = "workflows/repository/fleet_job_submission.yaml"


def _keyed_submit(fm, r, *, request_key="req-A", retry_safe=False, **overrides):
    """One keyed submit with the default request inputs (overridable per case)."""
    kwargs = dict(spec=_REQ_SPEC, goal="g", model="anthropic/claude-sonnet-5", workdir="/tmp/wt_x")
    kwargs.update(overrides)
    return fm._send_submit_command(r, request_key=request_key, retry_safe=retry_safe, **kwargs)


def test_a_keyed_retry_reconciles_to_the_existing_job_and_queues_nothing():
    """The lost-response repair: a retry with the SAME key and inputs returns the EXISTING
    job identity (with its board status) and never queues a second command."""
    fm = _fleet_manager()
    r = _FakeRedis()
    first = _keyed_submit(fm, r)
    assert first.get("reconciled") is None
    assert len(r._lists[fm.COMMANDS_KEY]) == 1

    retry = _keyed_submit(fm, r)
    assert retry["job_id"] == first["job_id"]
    assert retry["reconciled"] is True
    assert retry["status"] == "launching"
    assert retry["request_key"] == "req-A"
    assert len(r._lists[fm.COMMANDS_KEY]) == 1  # no second command


def test_the_request_key_rides_the_command_the_record_and_the_fingerprint_index():
    fm = _fleet_manager()
    r = _FakeRedis()
    cmd = _keyed_submit(fm, r)
    assert cmd["request_key"] == "req-A"
    record = json.loads(r._hashes[fm.JOBS_KEY][cmd["job_id"]])
    assert record["request_key"] == "req-A" and record["status"] == "launching"
    entry = json.loads(r._hashes[fm.REQUESTS_KEY]["req-A"])
    assert entry["job_id"] == cmd["job_id"]
    assert len(entry["fingerprint"]) == 64  # the reconcile evidence is retained
    assert entry["workdir"] == cmd["workdir"]  # the RESOLVED workspace is retained too


def test_a_key_reused_for_any_changed_execution_input_refuses():
    """Reviewer finding (2026-09-16): reconciliation compares the FULL execution-relevant
    fingerprint — the spec filename alone is not the request. Every changed input refuses."""
    fm = _fleet_manager()
    r = _FakeRedis()
    _keyed_submit(fm, r)
    changed_cases = [
        # The same spec path with a DIFFERENT digest (an edited workflow) — the case a
        # filename-only comparison silently discarded.
        {"spec_sha256": "a" * 64},
        {"goal": "a different goal"},
        {"model": "deepseek/deepseek-v4-flash"},
        {"workdir": "/tmp/wt_other"},
        {"resume": True, "parent_run_id": "run-2"},
        {"admission": {"required": True, "campaign_budget_usd": 5.0}},
        {"execution": {"backend": "opencode"}},
    ]
    for overrides in changed_cases:
        with pytest.raises(fm.RequestKeyConflictError, match="DIFFERENT request"):
            _keyed_submit(fm, r, **overrides)
    assert len(r._lists[fm.COMMANDS_KEY]) == 1  # nothing after the original submission


def test_a_missing_board_record_reconciles_the_identity_with_an_unknown_status():
    """Same request + missing board record: the identity is still proven by the retained
    fingerprint — reconcile it and report the lifecycle as unknown, never fabricate one. A
    CHANGED request with the record missing must still refuse (the reviewer's observation:
    the record is not the evidence)."""
    fm = _fleet_manager()
    r = _FakeRedis()
    first = _keyed_submit(fm, r)
    del r._hashes[fm.JOBS_KEY][first["job_id"]]
    retry = _keyed_submit(fm, r)
    assert retry["job_id"] == first["job_id"] and retry["reconciled"] is True
    assert retry["status"] == "unknown" and retry["board_record"] == "missing"
    with pytest.raises(fm.RequestKeyConflictError, match="DIFFERENT request"):
        _keyed_submit(fm, r, goal="changed while the board record is missing")
    # The reviewer's exact repro: with the record missing, a DIFFERENT spec filename must
    # still refuse — the fingerprint index, not the board record, is the evidence.
    with pytest.raises(fm.RequestKeyConflictError, match="DIFFERENT request"):
        _keyed_submit(fm, r, spec="workflows/repository/control_room_new_ui.yaml")
    assert len(r._lists[fm.COMMANDS_KEY]) == 1


def test_missing_or_corrupt_stored_evidence_is_an_explicit_unresolved_state():
    """Missing evidence must NOT silently reconcile (or silently re-queue): a stored entry
    without a fingerprint, and an unparseable entry, each refuse as UNRESOLVED."""
    fm = _fleet_manager()
    r = _FakeRedis()
    first = _keyed_submit(fm, r)
    r._hashes[fm.REQUESTS_KEY]["req-A"] = json.dumps({"job_id": first["job_id"]})
    with pytest.raises(fm.RequestKeyUnresolvedError, match="missing evidence"):
        _keyed_submit(fm, r)
    r._hashes[fm.REQUESTS_KEY]["req-A"] = "not-json"
    with pytest.raises(fm.RequestKeyUnresolvedError, match="unreadable stored identity"):
        _keyed_submit(fm, r)
    assert len(r._lists[fm.COMMANDS_KEY]) == 1


def test_retry_safe_derives_a_stable_key_and_reconciles():
    """The ordinary path retains its OWN identity before sending: with retry_safe and no
    explicit key, an identical retry reconciles automatically. A CHANGED input derives a
    different key — it becomes a NEW independent request, never a silent reconcile to the
    old job (the reviewer's silent-discard failure cannot occur on this path)."""
    fm = _fleet_manager()
    r = _FakeRedis()
    first = _keyed_submit(fm, r, request_key=None, retry_safe=True)
    assert str(first["request_key"]).startswith("auto:")
    retry = _keyed_submit(fm, r, request_key=None, retry_safe=True)
    assert retry["job_id"] == first["job_id"] and retry["reconciled"] is True
    changed = _keyed_submit(fm, r, request_key=None, retry_safe=True, goal="changed")
    assert changed.get("reconciled") is None and changed["job_id"] != first["job_id"]
    assert len(r._lists[fm.COMMANDS_KEY]) == 2


def test_an_explicit_key_wins_over_retry_safe():
    """An explicit key is how a caller FORCES an independent run (or names its own retry)."""
    fm = _fleet_manager()
    r = _FakeRedis()
    cmd = _keyed_submit(fm, r, request_key="req-explicit", retry_safe=True)
    assert cmd["request_key"] == "req-explicit"


def test_task_identity_scopes_the_retry_key_across_logical_tasks():
    """Reviewer finding (2026-09-16): identical inputs from a DIFFERENT logical task are a
    different submission. Retry-safe keys are scoped by the durable task identity (the AIO
    binding's task_identity): same task = retry reconciles; different task = a new job."""
    fm = _fleet_manager()
    r = _FakeRedis()
    a1 = _keyed_submit(fm, r, request_key=None, retry_safe=True, task_identity="task-a")
    a2 = _keyed_submit(fm, r, request_key=None, retry_safe=True, task_identity="task-a")
    b1 = _keyed_submit(fm, r, request_key=None, retry_safe=True, task_identity="task-b")
    assert a1["job_id"] == a2["job_id"] and a2["reconciled"] is True
    assert b1.get("reconciled") is None
    assert b1["job_id"] != a1["job_id"]
    assert a1["request_key"] != b1["request_key"]
    assert b1["task_identity"] == "task-b"
    assert len(r._lists[fm.COMMANDS_KEY]) == 2  # one command per logical task


def test_submit_cli_carries_the_task_identity(tmp_path, monkeypatch, capsys):
    fm = _fleet_manager()
    r = _FakeRedis()
    monkeypatch.setattr(fm, "_connect", lambda: r)
    rc = fm.main(
        [
            "submit",
            "--spec",
            "workflows/repository/fleet_job_submission.yaml",
            "--goal",
            "g",
            "--model",
            "anthropic/claude-sonnet-5",
            "--workdir",
            "/tmp/wt_cli",
            "--retry-safe",
            "--task-identity",
            "session:ses_x",
            "--json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["task_identity"] == "session:ses_x"
    queued = [json.loads(raw) for raw in r._lists[fm.COMMANDS_KEY]]
    assert queued[0]["task_identity"] == "session:ses_x"
    record = json.loads(r._hashes[fm.JOBS_KEY][queued[0]["job_id"]])
    assert record["task_identity"] == "session:ses_x"


def test_without_a_key_or_retry_safe_an_identical_submit_is_an_independent_new_run():
    """No key = an independent submission: identical parameters mint a SECOND job — an
    intentional repeat is a new run, never content deduplication."""
    fm = _fleet_manager()
    r = _FakeRedis()
    a = _keyed_submit(fm, r, request_key=None)
    b = _keyed_submit(fm, r, request_key=None)
    assert a["job_id"] != b["job_id"]
    assert len(r._lists[fm.COMMANDS_KEY]) == 2


def test_submit_cli_reconciles_a_keyed_retry(monkeypatch, capsys):
    fm = _fleet_manager()
    r = _FakeRedis()
    monkeypatch.setattr(fm, "_connect", lambda: r)
    argv = [
        "submit",
        "--spec",
        "workflows/repository/fleet_job_submission.yaml",
        "--goal",
        "g",
        "--model",
        "anthropic/claude-sonnet-5",
        "--workdir",
        "/tmp/wt_cli",
        "--request-key",
        "req-cli",
    ]
    assert fm.main(argv) == 0
    assert "launching" in capsys.readouterr().out
    assert fm.main(argv) == 0
    retry_out = capsys.readouterr().out
    assert "fleet:jobs[" in retry_out and "reconciled" in retry_out
    assert len(r._lists[fm.COMMANDS_KEY]) == 1


def test_submit_cli_refuses_a_conflicting_key_with_exit_2(monkeypatch, capsys):
    fm = _fleet_manager()
    r = _FakeRedis()
    monkeypatch.setattr(fm, "_connect", lambda: r)
    base = [
        "submit",
        "--spec",
        "workflows/repository/fleet_job_submission.yaml",
        "--goal",
        "g",
        "--model",
        "anthropic/claude-sonnet-5",
        "--workdir",
        "/tmp/wt_cli",
        "--request-key",
        "req-cli",
    ]
    assert fm.main(base) == 0
    conflicting = [
        "submit",
        "--spec",
        "workflows/repository/control_room_new_ui.yaml",
        "--goal",
        "g",
        "--model",
        "anthropic/claude-sonnet-5",
        "--workdir",
        "/tmp/wt_cli",
        "--request-key",
        "req-cli",
    ]
    assert fm.main(conflicting) == 2
    assert "request key" in capsys.readouterr().err


# ── The workspace preparation path (Unit 2) ────────────────────────────────────


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


def _prep_repo(tmp_path, monkeypatch):
    """A real git repo (branch main, one commit) + a tmp worktrees root, wired in."""
    fm = _fleet_manager()
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-b", "main", cwd=repo)
    _git("config", "user.email", "t@example.com", cwd=repo)
    _git("config", "user.name", "test", cwd=repo)
    (repo / "README.md").write_text("x", encoding="utf-8")
    _git("add", "-A", cwd=repo)
    _git("commit", "-m", "init", cwd=repo)
    worktrees = tmp_path / "wtroot"
    worktrees.mkdir()
    monkeypatch.setenv("FINOPS_WORKTREE_ROOT", str(worktrees))
    monkeypatch.setattr(fm, "_REPO_ROOT", repo)
    return fm, repo, worktrees


def test_prepare_workspace_creates_reuses_and_refuses_dirty(tmp_path, monkeypatch):
    fm, repo, worktrees = _prep_repo(tmp_path, monkeypatch)
    path, note, errors = fm.prepare_workspace(
        spec="workflows/repository/demo.yaml", goal="g", model="m"
    )
    assert errors == [] and path is not None and path.exists()
    assert "prepared" in note and path.parent == worktrees
    main_sha = _git("rev-parse", "HEAD", cwd=repo).stdout.strip()
    assert _git("rev-parse", "HEAD", cwd=path).stdout.strip() == main_sha
    assert _git("branch", "--show-current", cwd=path).stdout.strip() == path.name

    # An identical call reuses the same deterministic workspace; nothing is re-created.
    again, note2, errors2 = fm.prepare_workspace(
        spec="workflows/repository/demo.yaml", goal="g", model="m"
    )
    assert errors2 == [] and again == path and "reused" in note2

    # A dirty candidate refuses — never mutated to fit.
    (path / "dirty.txt").write_text("d", encoding="utf-8")
    _p, _n, dirty_errors = fm.prepare_workspace(
        spec="workflows/repository/demo.yaml", goal="g", model="m"
    )
    assert any("uncommitted changes" in e for e in dirty_errors)

    # A different request derives a different workspace (the name carries its digest).
    other, _n, errors4 = fm.prepare_workspace(
        spec="workflows/repository/demo.yaml", goal="other", model="m"
    )
    assert errors4 == [] and other != path


def test_prepare_workspace_refuses_a_non_worktree_candidate(tmp_path, monkeypatch):
    fm, repo, worktrees = _prep_repo(tmp_path, monkeypatch)
    plain = worktrees / "wt_demo_deadbeef"
    plain.mkdir()
    monkeypatch.setattr(fm, "_derived_workspace_path", lambda spec, digest: plain)
    _p, _n, errors = fm.prepare_workspace(spec="s", goal="g", model="m")
    assert any("not a git worktree" in e for e in errors)


def _parent_clone(tmp_path, monkeypatch):
    """A repo + a parent run's PRIVATE CLONE (runs_root/<id>/repo, detached candidate commit)
    + the parent's ledger. Returns (fm, repo, runs_root, clone, candidate)."""
    fm, repo, _worktrees = _prep_repo(tmp_path, monkeypatch)
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    monkeypatch.setenv("FINOPS_RUNS_ROOT", str(runs_root))
    base_sha = _git("rev-parse", "HEAD", cwd=repo).stdout.strip()
    clone = runs_root / "run-parent" / "repo"
    clone.parent.mkdir(parents=True)
    proc = subprocess.run(
        ["git", "clone", "-q", "--no-hardlinks", "--", str(repo), str(clone)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    _git("checkout", "-q", "--detach", base_sha, cwd=clone)
    (clone / "phase.txt").write_text("built", encoding="utf-8")
    _git("add", ".", cwd=clone)
    _git("commit", "-q", "-m", "[workflow] build", cwd=clone)
    candidate = _git("rev-parse", "HEAD", cwd=clone).stdout.strip()
    ledger_dir = repo / "experiments" / "results" / "workflows" / "demo"
    ledger_dir.mkdir(parents=True)
    _write_parent_ledger(ledger_dir, candidate=candidate, completed=True)
    return fm, repo, runs_root, clone, candidate


def _write_parent_ledger(ledger_dir, *, candidate: str, completed: bool) -> None:
    (ledger_dir / "20260916T000000000000Z_run-parent.json").write_text(
        json.dumps(
            {
                "run_id": "run-parent",
                "git_sha": candidate,
                "phases": [{"phase": "build", "status": "ok" if completed else "failed"}],
            }
        ),
        encoding="utf-8",
    )


def test_prepare_workspace_continuation_uses_the_parent_clone_at_the_candidate(
    tmp_path, monkeypatch
):
    """Reviewer finding (2026-09-16): the continuation base is the parent's PRIVATE CLONE —
    the repository that actually contains its committed phases — at the ledger's candidate
    SHA. The declared workdir is never the base: its commits are not there."""
    fm, repo, runs_root, clone, candidate = _parent_clone(tmp_path, monkeypatch)
    path, note, errors = fm.prepare_workspace(
        spec="demo", goal="g", model="m", resume=True, parent_run_id="run-parent"
    )
    assert errors == [] and path == clone
    assert "parent run run-parent" in note and candidate[:12] in note


def test_prepare_workspace_continuation_refuses_without_clone_or_candidate(tmp_path, monkeypatch):
    """No silent fallback: a missing clone or a candidate the clone does not contain refuses
    — the continuation must never start from a tree without the completed work."""
    import shutil as _shutil

    fm, repo, runs_root, clone, candidate = _parent_clone(tmp_path, monkeypatch)
    ledger_dir = repo / "experiments" / "results" / "workflows" / "demo"

    # The clone does not contain the declared candidate: refuse.
    _write_parent_ledger(ledger_dir, candidate="0" * 40, completed=True)
    _p, _n, errors = fm.prepare_workspace(
        spec="demo", goal="g", model="m", resume=True, parent_run_id="run-parent"
    )
    assert any("is not present" in e for e in errors)

    # Completed phases but no candidate SHA: refuse (the tree cannot be identified).
    _write_parent_ledger(ledger_dir, candidate="", completed=True)
    _p, _n, errors = fm.prepare_workspace(
        spec="demo", goal="g", model="m", resume=True, parent_run_id="run-parent"
    )
    assert any("no candidate SHA" in e for e in errors)

    # The clone is gone: refuse — never fall back to the source tree.
    _write_parent_ledger(ledger_dir, candidate=candidate, completed=True)
    _shutil.rmtree(runs_root / "run-parent")
    _p, _n, errors = fm.prepare_workspace(
        spec="demo", goal="g", model="m", resume=True, parent_run_id="run-parent"
    )
    assert any("private clone" in e for e in errors)

    # No ledger at all: refuse with the named parent.
    _shutil.rmtree(ledger_dir)
    _p, _n, errors = fm.prepare_workspace(
        spec="demo", goal="g", model="m", resume=True, parent_run_id="run-missing"
    )
    assert any("no ledger found" in e for e in errors)


def test_prepare_workspace_never_reuses_a_stale_workspace(tmp_path, monkeypatch):
    """Reviewer finding (2026-09-16): a fresh submission is bound to the SELECTED source SHA.
    A workspace created at an older main tip is not reused (and never reset) — a separate,
    SHA-suffixed workspace is created beside it and reused thereafter."""
    fm, repo, worktrees = _prep_repo(tmp_path, monkeypatch)
    first, _n, errors = fm.prepare_workspace(spec="demo.yaml", goal="g", model="m")
    assert errors == [] and first is not None

    (repo / "advance.txt").write_text("x", encoding="utf-8")
    _git("add", "-A", cwd=repo)
    _git("commit", "-m", "advance", cwd=repo)
    new_main = _git("rev-parse", "HEAD", cwd=repo).stdout.strip()

    second, _note, errors2 = fm.prepare_workspace(spec="demo.yaml", goal="g", model="m")
    assert errors2 == [] and second is not None and second != first
    assert second.name.endswith(new_main[:7])
    assert _git("rev-parse", "HEAD", cwd=second).stdout.strip() == new_main
    # The stale workspace is left untouched — never reset to fit.
    assert first.exists()
    assert _git("rev-parse", "HEAD", cwd=first).stdout.strip() != new_main

    # A repeated fresh submission at the same main reuses the suffixed workspace.
    third, _n3, errors3 = fm.prepare_workspace(spec="demo.yaml", goal="g", model="m")
    assert errors3 == [] and third == second


def test_submit_cli_json_result_is_structured(monkeypatch, capsys):
    """The durable interface is the fleet-submit/v1 document — never a parsed log line."""
    fm = _fleet_manager()
    r = _FakeRedis()
    monkeypatch.setattr(fm, "_connect", lambda: r)
    rc = fm.main(
        [
            "submit",
            "--spec",
            "workflows/repository/fleet_job_submission.yaml",
            "--goal",
            "g",
            "--model",
            "anthropic/claude-sonnet-5",
            "--workdir",
            "/tmp/wt_cli",
            "--json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["schema"] == "fleet-submit/v1"
    assert payload["job_id"] and payload["reconciled"] is False
    assert payload["status"] == "launching"
    assert payload["workdir"] == "/tmp/wt_cli"
    assert payload["spec"] == "workflows/repository/fleet_job_submission.yaml"
    assert payload["request_key"] == ""  # no key, no retry-safe: the caller chose neither
    assert payload["prep_note"] == ""


def test_submit_cli_prepares_a_workspace_when_workdir_is_omitted(tmp_path, monkeypatch, capsys):
    fm, repo, worktrees = _prep_repo(tmp_path, monkeypatch)
    r = _FakeRedis()
    monkeypatch.setattr(fm, "_connect", lambda: r)
    rc = fm.main(
        [
            "submit",
            "--spec",
            "workflows/repository/demo.yaml",
            "--goal",
            "g",
            "--model",
            "m",
            "--json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["workdir"].startswith(str(worktrees))
    assert "prepared" in payload["prep_note"]
    assert Path(payload["workdir"]).exists()


def test_submit_cli_retry_skips_workspace_preparation(tmp_path, monkeypatch, capsys):
    """A retry must NEVER re-resolve the workspace: with the key present, preparation is
    skipped entirely (nothing runs) — the same job reconciles even after main advances."""
    fm, repo, worktrees = _prep_repo(tmp_path, monkeypatch)
    r = _FakeRedis()
    monkeypatch.setattr(fm, "_connect", lambda: r)
    argv = [
        "submit",
        "--spec",
        "workflows/repository/demo.yaml",
        "--goal",
        "g",
        "--model",
        "m",
        "--retry-safe",
        "--json",
    ]
    assert fm.main(argv) == 0
    first = json.loads(capsys.readouterr().out.strip())
    first_path = first["workdir"]

    (repo / "advance.txt").write_text("x", encoding="utf-8")
    _git("add", "-A", cwd=repo)
    _git("commit", "-m", "advance", cwd=repo)

    assert fm.main(argv) == 0
    retry = json.loads(capsys.readouterr().out.strip())
    assert retry["job_id"] == first["job_id"] and retry["reconciled"] is True
    assert retry["workdir"] == first_path
    assert "retry: reconciling" in retry["prep_note"]
    # Exactly one workspace (no SHA-suffixed sibling was created) and one queued command.
    made = sorted(p.name for p in worktrees.iterdir())
    assert made == [Path(first_path).name]
    assert len(r._lists[fm.COMMANDS_KEY]) == 1


def test_submit_cli_new_key_after_main_advances_gets_a_fresh_workspace(
    tmp_path, monkeypatch, capsys
):
    """Reviewer repro (2026-09-16): a deliberate new submission (a NEW key) after main
    advances must get a workspace AT the new tip — never the stale one."""
    fm, repo, worktrees = _prep_repo(tmp_path, monkeypatch)
    r = _FakeRedis()
    monkeypatch.setattr(fm, "_connect", lambda: r)
    argv = [
        "submit",
        "--spec",
        "workflows/repository/demo.yaml",
        "--goal",
        "g",
        "--model",
        "m",
        "--retry-safe",
        "--json",
    ]
    assert fm.main(argv) == 0
    first = json.loads(capsys.readouterr().out.strip())

    (repo / "advance.txt").write_text("x", encoding="utf-8")
    _git("add", "-A", cwd=repo)
    _git("commit", "-m", "advance", cwd=repo)
    new_main = _git("rev-parse", "HEAD", cwd=repo).stdout.strip()

    assert fm.main([*argv[:-1], "--request-key", "fresh-1", "--json"]) == 0
    second = json.loads(capsys.readouterr().out.strip())
    assert second["reconciled"] is False
    assert second["workdir"] != first["workdir"]
    assert second["workdir"].endswith(new_main[:7])
    assert Path(second["workdir"]).exists()


def test_explicit_key_retry_reuses_the_recorded_suffixed_workspace(tmp_path, monkeypatch, capsys):
    """Reviewer finding (round 4): a retry resolves the workspace FROM the retained record —
    the SHA-suffixed workspace assigned to the submission is reused (even after another main
    advance) instead of failing as a DIFFERENT request."""
    fm, repo, worktrees = _prep_repo(tmp_path, monkeypatch)
    r = _FakeRedis()
    monkeypatch.setattr(fm, "_connect", lambda: r)
    # 1) a first workspace at main_1 (the base name).
    assert (
        fm.main(
            [
                "submit",
                "--spec",
                "workflows/repository/demo.yaml",
                "--goal",
                "g",
                "--model",
                "m",
                "--retry-safe",
                "--json",
            ]
        )
        == 0
    )
    first = json.loads(capsys.readouterr().out.strip())

    # 2) main advances; a NEW explicit key gets the SHA-suffixed workspace.
    (repo / "advance.txt").write_text("x", encoding="utf-8")
    _git("add", "-A", cwd=repo)
    _git("commit", "-m", "advance", cwd=repo)
    new_main = _git("rev-parse", "HEAD", cwd=repo).stdout.strip()
    assert (
        fm.main(
            [
                "submit",
                "--spec",
                "workflows/repository/demo.yaml",
                "--goal",
                "g",
                "--model",
                "m",
                "--request-key",
                "k1",
                "--json",
            ]
        )
        == 0
    )
    second = json.loads(capsys.readouterr().out.strip())
    assert second["reconciled"] is False
    assert second["workdir"] != first["workdir"]
    assert second["workdir"].endswith(new_main[:7])

    # 3) ANOTHER main advance; the retry with the same key must reconcile to the RECORDED
    #    (suffixed) workspace — not the reconstructed unsuffixed path.
    (repo / "advance2.txt").write_text("x", encoding="utf-8")
    _git("add", "-A", cwd=repo)
    _git("commit", "-m", "advance2", cwd=repo)
    assert (
        fm.main(
            [
                "submit",
                "--spec",
                "workflows/repository/demo.yaml",
                "--goal",
                "g",
                "--model",
                "m",
                "--request-key",
                "k1",
                "--json",
            ]
        )
        == 0
    )
    retry = json.loads(capsys.readouterr().out.strip())
    assert retry["reconciled"] is True
    assert retry["job_id"] == second["job_id"]
    assert retry["workdir"] == second["workdir"]
    assert "retry: reconciling" in retry["prep_note"]
    names = sorted(p.name for p in worktrees.iterdir())
    assert names == sorted([Path(first["workdir"]).name, Path(second["workdir"]).name])


def test_auto_key_retry_reuses_the_recorded_suffixed_workspace(tmp_path, monkeypatch, capsys):
    """The automatic-key variant: a second task's first submission gets the suffixed
    workspace; its retry after another main advance reuses the recorded workspace + job —
    no duplicate is queued."""
    fm, repo, worktrees = _prep_repo(tmp_path, monkeypatch)
    r = _FakeRedis()
    monkeypatch.setattr(fm, "_connect", lambda: r)
    # task-a's first submission creates the base workspace at main_1.
    assert (
        fm.main(
            [
                "submit",
                "--spec",
                "workflows/repository/demo.yaml",
                "--goal",
                "g",
                "--model",
                "m",
                "--retry-safe",
                "--task-identity",
                "task-a",
                "--json",
            ]
        )
        == 0
    )
    first = json.loads(capsys.readouterr().out.strip())

    # main advances; task-b's identical inputs get the SHA-suffixed workspace.
    (repo / "advance.txt").write_text("x", encoding="utf-8")
    _git("add", "-A", cwd=repo)
    _git("commit", "-m", "advance", cwd=repo)
    assert (
        fm.main(
            [
                "submit",
                "--spec",
                "workflows/repository/demo.yaml",
                "--goal",
                "g",
                "--model",
                "m",
                "--retry-safe",
                "--task-identity",
                "task-b",
                "--json",
            ]
        )
        == 0
    )
    second = json.loads(capsys.readouterr().out.strip())
    assert second["reconciled"] is False
    assert second["workdir"] != first["workdir"]

    # ANOTHER advance; task-b's retry must reconcile to the recorded workspace + job.
    (repo / "advance2.txt").write_text("x", encoding="utf-8")
    _git("add", "-A", cwd=repo)
    _git("commit", "-m", "advance2", cwd=repo)
    assert (
        fm.main(
            [
                "submit",
                "--spec",
                "workflows/repository/demo.yaml",
                "--goal",
                "g",
                "--model",
                "m",
                "--retry-safe",
                "--task-identity",
                "task-b",
                "--json",
            ]
        )
        == 0
    )
    retry = json.loads(capsys.readouterr().out.strip())
    assert retry["reconciled"] is True and retry["job_id"] == second["job_id"]
    assert retry["workdir"] == second["workdir"]
    assert len(r._lists[fm.COMMANDS_KEY]) == 2  # one command per logical task


def test_two_successive_continuations_keep_the_canonical_provenance(tmp_path, monkeypatch):
    """Round-5 finding (2026-09-16): for a project WITHOUT an origin remote, cloning a clone
    replaced the recorded canonical git dir with its local origin path — the SECOND
    continuation then failed validation. The validated provenance must survive generations."""
    from agentic_dynamics.core.paths import PathConfig as _PathConfig
    from agentic_dynamics.runtime.run_clone import create_run_clone

    fm, repo, worktrees = _prep_repo(tmp_path, monkeypatch)
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    monkeypatch.setenv("FINOPS_RUNS_ROOT", str(runs_root))
    cfg = _PathConfig.from_env(require_existing=False)
    ledger_dir = repo / "experiments" / "results" / "workflows" / "demo"
    ledger_dir.mkdir(parents=True)

    # Generation 1: the first run's clone (stamped with the canonical git dir).
    gen1 = create_run_clone("run-gen1", source_repo=repo, path_config=cfg)
    git = ["git", "-C", str(gen1.path), "-c", "user.email=t@t", "-c", "user.name=t"]
    (gen1.path / "p1.txt").write_text("one", encoding="utf-8")
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "[workflow] p1"], check=True)
    c1 = subprocess.run(
        ["git", "-C", str(gen1.path), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    (ledger_dir / "20260916T000000000000Z_run-gen1.json").write_text(
        json.dumps(
            {"run_id": "run-gen1", "git_sha": c1, "phases": [{"phase": "p1", "status": "ok"}]}
        ),
        encoding="utf-8",
    )

    # Continuation 1: prepared from gen1 (verified + stamped).
    prep1, _note1, errors1 = fm.prepare_workspace(
        spec="demo", goal="g", model="m", resume=True, parent_run_id="run-gen1"
    )
    assert errors1 == [] and prep1 == gen1.path
    token = fm._stamped_provenance(gen1.path)
    assert token and not token.startswith("origin:")  # the canonical git-dir identity

    # Generation 2: a clone created FROM the prepared workspace (as the run's composition
    # root does) INHERITS the stamp — never the local origin path.
    gen2 = create_run_clone("run-gen2", source_repo=gen1.path, path_config=cfg)
    assert fm._stamped_provenance(gen2.path) == token

    (gen2.path / "p2.txt").write_text("two", encoding="utf-8")
    git2 = ["git", "-C", str(gen2.path), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git2, "add", "-A"], check=True)
    subprocess.run([*git2, "commit", "-qm", "[workflow] p2"], check=True)
    c2 = subprocess.run(
        ["git", "-C", str(gen2.path), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    (ledger_dir / "20260916T000000000001Z_run-gen2.json").write_text(
        json.dumps(
            {"run_id": "run-gen2", "git_sha": c2, "phases": [{"phase": "p2", "status": "ok"}]}
        ),
        encoding="utf-8",
    )

    # Continuation 2: prepared from gen2 — must succeed with the canonical identity intact.
    prep2, _note2, errors2 = fm.prepare_workspace(
        spec="demo", goal="g", model="m", resume=True, parent_run_id="run-gen2"
    )
    assert errors2 == [] and prep2 == gen2.path
    assert fm._stamped_provenance(gen2.path) == token


# ── Unit 3: the submission records itself into the existing task state ────────


def _binding_store(tmp_path):
    """A tmp binding store with ONE real binding for ses_aio.

    Returns ``(store, authorization_id)`` — the exec gate checks the binding's AUTHORIZATION
    identity (round-9), not the content-addressed record id.
    """
    from agentic_dynamics.knowledge import session_ingestion as si

    store = tmp_path / "kb"
    si.init_binding_store(store)
    written = si.write_binding(
        {
            "native_session_id": "ses_aio",
            "resolved_agent": "aio-control",
            "task_identity": "unit-3",
            "original_request": "record the submission into the task state",
        },
        artifact_dir=store,
        publish=False,
    )
    assert written.status == si.BINDING_STATUS_CREATED
    binding = si.read_binding("ses_aio", artifact_dir=store).binding or {}
    return store, si.binding_authorization_id(binding)


def test_a_submission_records_its_job_into_the_task_state(tmp_path, monkeypatch, capsys):
    """Unit 3: the durable submit writes the pending job + one next action into the EXISTING
    binding (labeled [auto], version-guarded) — continuation glue without a reminder."""
    from agentic_dynamics.knowledge import session_ingestion as si

    fm = _fleet_manager()
    r = _FakeRedis()
    monkeypatch.setattr(fm, "_connect", lambda: r)
    store, binding_id = _binding_store(tmp_path)
    monkeypatch.setenv("FINOPS_KB_ARTIFACT_DIR", str(store))

    rc = fm.main(
        [
            "submit",
            "--spec",
            "workflows/repository/fleet_job_submission.yaml",
            "--goal",
            "g",
            "--model",
            "anthropic/claude-sonnet-5",
            "--workdir",
            "/tmp/wt_cli",
            "--aio-session-id",
            "ses_aio",
            "--aio-agent",
            "aio-control",
            "--binding-id",
            binding_id,
            "--task-revision",
            "1",
            "--binding-context-version",
            "1",
            "--retry-safe",
            "--json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["task_note"] == ""  # recorded cleanly

    binding = si.read_binding("ses_aio", artifact_dir=store)
    assert binding.status == si.BINDING_STATUS_FOUND
    next_action = str(binding.binding["next_action"])
    assert "[auto]" in next_action
    assert payload["job_id"] in next_action
    assert payload["request_key"] in next_action
    assert int(binding.binding["context_version"]) == 2
    # The recording is PROGRESS: the authorization identity and epoch are untouched, so the
    # command just minted against them stays authorized (round-9).
    assert si.binding_authorization_id(binding.binding) == binding_id
    assert si.binding_authorization_version(binding.binding) == 1


def test_a_stale_revision_never_overwrites_the_task_state(tmp_path, monkeypatch, capsys):
    """The version guard: a submit carrying an OLD task revision reports the failure and
    leaves the newer binding untouched — a stale session cannot advance the task."""
    from agentic_dynamics.knowledge import session_ingestion as si

    fm = _fleet_manager()
    r = _FakeRedis()
    monkeypatch.setattr(fm, "_connect", lambda: r)
    store, binding_id = _binding_store(tmp_path)
    monkeypatch.setenv("FINOPS_KB_ARTIFACT_DIR", str(store))
    si.update_binding_context(
        "ses_aio",
        context={"next_action": "the newer AIO action"},
        expected_version=1,
        artifact_dir=store,
    )

    rc = fm.main(
        [
            "submit",
            "--spec",
            "workflows/repository/fleet_job_submission.yaml",
            "--goal",
            "g",
            "--model",
            "anthropic/claude-sonnet-5",
            "--workdir",
            "/tmp/wt_cli",
            "--aio-session-id",
            "ses_aio",
            "--aio-agent",
            "aio-control",
            "--binding-id",
            binding_id,
            "--task-revision",
            "1",
            "--binding-context-version",
            "1",
            "--retry-safe",
            "--json",
        ]
    )
    assert rc == 0  # the submission itself is unaffected (the job is durable)
    payload = json.loads(capsys.readouterr().out.strip())
    assert "task state not updated" in payload["task_note"]
    binding = si.read_binding("ses_aio", artifact_dir=store)
    assert binding.binding["next_action"] == "the newer AIO action"  # untouched


def test_a_submission_without_a_store_reports_the_missing_task_update(monkeypatch, capsys):
    """A missing store never fails the submission: the note reports it (best-effort glue)."""
    fm = _fleet_manager()
    r = _FakeRedis()
    monkeypatch.setattr(fm, "_connect", lambda: r)
    monkeypatch.setenv("FINOPS_KB_ARTIFACT_DIR", "/nonexistent/kb-store")
    rc = fm.main(
        [
            "submit",
            "--spec",
            "workflows/repository/fleet_job_submission.yaml",
            "--goal",
            "g",
            "--model",
            "anthropic/claude-sonnet-5",
            "--workdir",
            "/tmp/wt_cli",
            "--aio-session-id",
            "ses_aio",
            "--aio-agent",
            "aio-control",
            "--binding-id",
            "b" * 64,
            "--task-revision",
            "1",
            "--retry-safe",
            "--json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert "task state not updated" in payload["task_note"]


# ── Round 9: recording must not invalidate the queued command ─────────────────


def _submit_fixture(tmp_path, monkeypatch):
    """A canonical repo (origin + the submit spec) + the manager on a fake redis —
    everything the REAL submission validator needs (spec compile + project identity)."""
    fm = _fleet_manager()
    repo = tmp_path / "canonical"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "remote",
            "add",
            "origin",
            "git@github.com:peparhugo/agentic-dynamics.git",
        ],
        check=True,
    )
    spec_src = (
        Path(__file__).resolve().parent.parent
        / "workflows"
        / "repository"
        / "fleet_job_submission.yaml"
    )
    spec_dst = repo / "workflows" / "repository" / "fleet_job_submission.yaml"
    spec_dst.parent.mkdir(parents=True)
    spec_dst.write_bytes(spec_src.read_bytes())
    git = ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "init"], check=True)
    workdir = tmp_path / "wt_entry"
    workdir.mkdir()
    r = _FakeRedis()
    monkeypatch.setattr(fm, "_connect", lambda: r)
    return fm, repo, r, workdir


def _aio_argv(*, auth_id, auth_version, context_version, workdir, extra=()):
    return [
        "submit",
        "--spec",
        "workflows/repository/fleet_job_submission.yaml",
        "--goal",
        "g",
        "--model",
        "anthropic/claude-sonnet-5",
        "--workdir",
        str(workdir),
        "--aio-session-id",
        "ses_aio",
        "--aio-agent",
        "aio-control",
        "--binding-id",
        auth_id,
        "--task-revision",
        str(auth_version),
        "--binding-context-version",
        str(context_version),
        *extra,
        "--json",
    ]


def test_a_recorded_submission_still_passes_delayed_consumption(tmp_path, monkeypatch, capsys):
    """Round-9 regression: the submit's own recording must not invalidate the queued command.
    Mint through the real CLI (which records progress), then validate + dry-run the SAME
    queued command exactly as the worker and the broker would — binding id and revision
    checks included."""
    from scripts.fleet.launch_broker import submit_run
    from scripts.fleet.spawn_wrapper import validate_submit_request

    fm, repo, r, workdir = _submit_fixture(tmp_path, monkeypatch)
    store, auth_id = _binding_store(tmp_path)
    monkeypatch.setenv("FINOPS_KB_ARTIFACT_DIR", str(store))
    monkeypatch.setattr("scripts.fleet.launch_broker.admission_required", lambda: False)

    rc = fm.main(
        _aio_argv(
            auth_id=auth_id,
            auth_version=1,
            context_version=1,
            workdir=workdir,
            extra=("--retry-safe",),
        )
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["task_note"] == ""  # the recording happened (context 1 -> 2)

    command = json.loads(r._lists[fm.COMMANDS_KEY][0])
    # DELAYED CONSUMPTION: the real validator still accepts the queued command.
    errors = validate_submit_request(command, repo_root=repo)
    assert errors == [], errors
    # ... and the broker's dry run reaches the compose decision (the reviewer's surface).
    outcome = submit_run(command, repo_root=repo, dry_run=True)
    assert outcome["ok"] is True


def test_a_genuine_task_change_still_rejects_its_pending_command(tmp_path, monkeypatch, capsys):
    """The stale-task rejection is preserved for genuine changes: an acceptance update
    advances the authorization epoch and the previously queued command is refused."""
    from agentic_dynamics.knowledge import session_ingestion as si
    from scripts.fleet.spawn_wrapper import validate_submit_request

    fm, repo, r, workdir = _submit_fixture(tmp_path, monkeypatch)
    store, auth_id = _binding_store(tmp_path)
    monkeypatch.setenv("FINOPS_KB_ARTIFACT_DIR", str(store))

    assert (
        fm.main(
            _aio_argv(
                auth_id=auth_id,
                auth_version=1,
                context_version=1,
                workdir=workdir,
                extra=("--retry-safe",),
            )
        )
        == 0
    )
    capsys.readouterr()
    command = json.loads(r._lists[fm.COMMANDS_KEY][0])

    si.update_binding_context(
        "ses_aio",
        context={"acceptance": {"text": "the task was redefined", "source": "raw"}},
        expected_version=2,  # after the recording
        artifact_dir=store,
    )
    # The task definition changed: the queued command's authorization is stale.
    errors = validate_submit_request(command, repo_root=repo)
    assert any("stale task revision" in e for e in errors), errors


def test_multiple_pending_submissions_survive_progress_recording(tmp_path, monkeypatch, capsys):
    """Progress recording is per-write, not per-command: two commands minted against the
    same task state both survive each other's recordings — and a repeated reconciliation
    reuses the first job without disturbing either authorization."""
    from scripts.fleet.spawn_wrapper import validate_submit_request

    fm, repo, r, workdir = _submit_fixture(tmp_path, monkeypatch)
    store, auth_id = _binding_store(tmp_path)
    monkeypatch.setenv("FINOPS_KB_ARTIFACT_DIR", str(store))

    assert (
        fm.main(
            _aio_argv(
                auth_id=auth_id,
                auth_version=1,
                context_version=1,
                workdir=workdir,
                extra=("--retry-safe",),
            )
        )
        == 0
    )
    first = json.loads(capsys.readouterr().out.strip())

    # The second submission reads the POST-recording context version (as the tool would).
    assert (
        fm.main(
            _aio_argv(
                auth_id=auth_id,
                auth_version=1,
                context_version=2,
                workdir=workdir,
                extra=("--retry-safe", "--task-identity", "second-pending"),
            )
        )
        == 0
    )
    second = json.loads(capsys.readouterr().out.strip())
    assert second["job_id"] != first["job_id"]

    commands = [json.loads(raw) for raw in r._lists[fm.COMMANDS_KEY]]
    assert len(commands) == 2
    for command in commands:
        errors = validate_submit_request(command, repo_root=repo)
        assert errors == [], (command["job_id"], errors)

    # A repeated reconciliation (the FIRST submission retried) returns its original job.
    assert (
        fm.main(
            _aio_argv(
                auth_id=auth_id,
                auth_version=1,
                context_version=3,
                workdir=workdir,
                extra=("--retry-safe",),
            )
        )
        == 0
    )
    retry = json.loads(capsys.readouterr().out.strip())
    assert retry["reconciled"] is True and retry["job_id"] == first["job_id"]
    assert len(r._lists[fm.COMMANDS_KEY]) == 2  # nothing new queued


def _load_session_open(name: str):
    """Load scripts/session_open.py by path (it lives under scripts/, not the package).

    The same importlib seam tests/test_session_binding.py uses — the capsule composer is the
    carrier under test, and it is deliberately not importable as a package module.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "session_open.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_submission_supersedes_a_completed_next_action_in_the_capsule(
    tmp_path, monkeypatch, capsys
):
    """End-to-end: the REAL submit path records over a stale instruction, and the capsule the
    per-request carrier composes no longer instructs the completed sequence.

    This closes the loop the binding-layer tests leave open — action -> binding -> carrier:
    seed the c15 stale next action, run ``fleet_manager submit`` (the confirmed action the AIO
    actually takes), then compose the capsule from the read-back binding and assert the stale
    instruction is gone while the [auto] job record is the one next action.
    """
    from agentic_dynamics.knowledge import session_ingestion as si

    fm = _fleet_manager()
    r = _FakeRedis()
    monkeypatch.setattr(fm, "_connect", lambda: r)
    store, binding_id = _binding_store(tmp_path)
    monkeypatch.setenv("FINOPS_KB_ARTIFACT_DIR", str(store))

    stale = "After the controller activates PR #77 then call run_workflow"
    si.update_binding_context(
        "ses_aio",
        context={"next_action": stale},
        expected_version=1,
        artifact_dir=store,
        publish=False,
    )

    rc = fm.main(
        [
            "submit",
            "--spec",
            "workflows/repository/fleet_job_submission.yaml",
            "--goal",
            "g",
            "--model",
            "anthropic/claude-sonnet-5",
            "--workdir",
            "/tmp/wt_cli",
            "--aio-session-id",
            "ses_aio",
            "--aio-agent",
            "aio-control",
            "--binding-id",
            binding_id,
            "--task-revision",
            "1",
            "--binding-context-version",
            "2",
            "--retry-safe",
            "--json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["task_note"] == ""  # recorded cleanly

    binding = si.read_binding("ses_aio", artifact_dir=store).binding
    assert binding is not None
    assert "[auto]" in binding["next_action"]
    assert payload["job_id"] in binding["next_action"]
    assert stale not in binding["next_action"]  # replaced, not appended

    # The carrier: composing from the read-back binding must not resurrect the finished sequence.
    module = _load_session_open("session_open_fleet_test")
    capsule = module.compose_capsule(
        binding,
        artifact_dir=store,
        packet={"status": "unavailable", "reason": "test"},
        budget={"verdict": "OK"},
    )
    assert capsule["next_action"]["source"] == "binding"
    assert payload["job_id"] in capsule["text"]
    assert "activate PR #77" not in capsule["next_action"]["text"]
    assert "activate PR #77" not in capsule["text"]
