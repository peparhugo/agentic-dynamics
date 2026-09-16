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


# ── record_job_status: the launching -> running -> completed/failed transitions ──────────


def test_record_job_status_preserves_identifying_fields_across_transitions():
    fm = _fleet_manager()
    r = _FakeRedis()
    cmd = fm._send_submit_command(
        r, spec="workflows/repository/fleet_job_submission.yaml", goal="g",
        model="anthropic/claude-sonnet-5", workdir="/tmp/wt_z",
    )
    fm.record_job_status(r, cmd["job_id"], "running")
    fm.record_job_status(
        r, cmd["job_id"], "completed",
        returncode=0, ledger="experiments/results/workflows/fleet_job_submission/x.json",
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
        r, spec="workflows/repository/fleet_job_submission.yaml", goal="g",
        model="deepseek/deepseek-v4-pro", workdir="/tmp/wt_fail",
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
        r, spec="workflows/repository/fleet_job_submission.yaml", goal="g",
        model="anthropic/claude-sonnet-5", workdir="/tmp/wt_x", image="fleet/job-example",
    )
    assert cmd["image"] == "fleet/job-example"
    queued = [json.loads(raw) for raw in r._lists[fm.COMMANDS_KEY]]
    assert queued == [cmd]


def test_send_submit_command_omits_image_field_when_not_given():
    fm = _fleet_manager()
    r = _FakeRedis()
    cmd = fm._send_submit_command(
        r, spec="workflows/repository/fleet_job_submission.yaml", goal="g",
        model="anthropic/claude-sonnet-5", workdir="/tmp/wt_x",
    )
    assert "image" not in cmd


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


def test_submit_cli_dispatches_the_optional_image_flag(monkeypatch):
    fm = _fleet_manager()
    r = _FakeRedis()
    monkeypatch.setattr(fm, "_connect", lambda: r)

    rc = fm.main([
        "submit", "--spec", "workflows/repository/fleet_job_submission.yaml",
        "--goal", "g", "--model", "anthropic/claude-sonnet-5", "--workdir", "/tmp/wt_cli",
        "--image", "fleet/job-example",
    ])
    assert rc == 0
    queued = [json.loads(raw) for raw in r._lists[fm.COMMANDS_KEY]]
    assert queued[0]["image"] == "fleet/job-example"


def test_send_submit_command_carries_the_extended_identity():
    """The extended submit identity (spec digest, continuation, admission) survives the
    manager's LPUSH hop — the orchestrator + broker re-validate it at the later gates."""
    fm = _fleet_manager()
    r = _FakeRedis()
    cmd = fm._send_submit_command(
        r, spec="workflows/repository/fleet_job_submission.yaml", goal="g",
        model="anthropic/claude-sonnet-5", workdir="/tmp/wt_x",
        spec_sha256="a" * 64, resume=True, parent_run_id="run-1",
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
    execution = {"backend": "opencode", "thinking_effort": "high",
                 "thinking_budget_tokens": 12000, "output_token_limit": 64000,
                 "timeout_seconds": 2400, "no_commit": False}
    cmd = fm._send_submit_command(
        r, spec="workflows/repository/fleet_job_submission.yaml", goal="g",
        model="anthropic/claude-sonnet-5", workdir="/tmp/wt_x", execution=execution,
    )
    assert cmd["execution"] == execution


def test_send_submit_command_carries_reserve_and_cap():
    """The manager passes the reserve/cap fields through unchanged (the orchestrator's armed
    gate reads them from the environment; the manager's job is that they survive the hop)."""
    fm = _fleet_manager()
    r = _FakeRedis()
    cmd = fm._send_submit_command(
        r, spec="workflows/repository/fleet_job_submission.yaml", goal="g",
        model="deepseek/deepseek-v4-flash", workdir="/tmp/wt_x",
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
    cmd = fm._send_submit_command(
        r, spec="s", goal="g", model="m", workdir="/tmp/w", aio=aio
    )
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
    rc = fm.main([
        "submit",
        "--spec", "workflows/repository/fleet_job_submission.yaml",
        "--goal", "g", "--model", "anthropic/claude-sonnet-5", "--workdir", "/tmp/wt_cli_aio",
        "--aio-session-id", "ses_cli", "--aio-agent", "aio-control",
        "--binding-id", "b" * 64, "--task-revision", "5",
    ])
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
        "submit", "--spec", "workflows/repository/fleet_job_submission.yaml",
        "--goal", "g", "--model", "anthropic/claude-sonnet-5", "--workdir", "/tmp/wt_cli",
        "--request-key", "req-cli",
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
        "submit", "--spec", "workflows/repository/fleet_job_submission.yaml",
        "--goal", "g", "--model", "anthropic/claude-sonnet-5", "--workdir", "/tmp/wt_cli",
        "--request-key", "req-cli",
    ]
    assert fm.main(base) == 0
    conflicting = [
        "submit", "--spec", "workflows/repository/control_room_new_ui.yaml",
        "--goal", "g", "--model", "anthropic/claude-sonnet-5", "--workdir", "/tmp/wt_cli",
        "--request-key", "req-cli",
    ]
    assert fm.main(conflicting) == 2
    assert "request key" in capsys.readouterr().err
