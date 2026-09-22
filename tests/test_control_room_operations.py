"""Tests for the Control Room's operational read models (step 5, Phase 0).

The properties pinned here are the Phase-0 truth rules:

* the room's live identifiers come FROM THE PACKET — the parity test asserts the attention
  block matches ``build_packet``'s blocks block-for-block (no re-derivation);
* absent data stays absent: an empty packet area renders empty/null and a degraded read is
  named in ``degraded`` — never a fabricated zero or all-clear;
* the read model is pure given its inputs (no clock, no sockets — ``now`` is injected).
"""

from __future__ import annotations

import json
import pytest
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
for _path in (_REPO_ROOT, _REPO_ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from agentic_dynamics.control.control_db import (  # noqa: E402
    AttemptState,
    ControlDB,
    GateVerdict,
    RunState,
)
from agentic_dynamics.control.control_status import build_packet  # noqa: E402
from apps.control_room.services.operations import (  # noqa: E402
    RUN_DETAIL_SCHEMA,
    SCHEMA,
    logs_block,
    operational_snapshot,
    read_run_logs,
    run_detail,
)

_NOW = "2026-09-12T00:00:00+00:00"


def _db(tmp_path) -> ControlDB:
    return ControlDB.open(tmp_path / "control.db")


def _seed_awaiting(db: ControlDB) -> str:
    run = db.create_run(
        spec_name="flow",
        model="m",
        state=RunState.RUNNING,
        reason="start",
        candidate_sha="a" * 40,
    )
    db.transition_run(run.run_id, RunState.AWAITING_APPROVAL, reason="checkpoint")
    return run.run_id


def _seed_failed(db: ControlDB) -> str:
    run = db.create_run(
        spec_name="flow",
        model="m",
        state=RunState.RUNNING,
        reason="start",
        candidate_sha="b" * 40,
    )
    db.transition_run(run.run_id, RunState.FAILED, reason="phase failed")
    return run.run_id


def test_attention_is_a_projection_of_the_packet(tmp_path):
    with _db(tmp_path) as db:
        awaiting_id = _seed_awaiting(db)
        failed_id = _seed_failed(db)

        packet = build_packet(db, repo_head_sha="c" * 40, heartbeats={}, now=_NOW)
        snapshot = operational_snapshot(db, repo_head_sha="c" * 40, heartbeats={}, now=_NOW)

    assert snapshot["schema"] == SCHEMA
    assert snapshot["source"]["packet_schema"] == packet["schema"]
    assert snapshot["source"]["control_epoch"] == packet["control_epoch"]

    # parity: the approval rows are the packet's rows (same run/gate/candidate ids), plus kind.
    approval_ids = {
        (row["run_id"], row["gate_id"], row["candidate_sha"])
        for row in snapshot["attention"]
        if row["kind"] == "approval"
    }
    packet_ids = {
        (row["run_id"], row["gate_id"], row["candidate_sha"])
        for row in packet["awaiting_approvals"]
    }
    assert approval_ids == packet_ids
    assert any(row["run_id"] == awaiting_id for row in snapshot["attention"])

    # the failed run reaches attention with the packet's identifiers.
    failed_ids = {
        (row["run_id"], row["spec_name"])
        for row in snapshot["attention"]
        if row["kind"] == "failed"
    }
    assert (failed_id, "flow") in failed_ids

    # the packet blocks flow through unchanged.
    assert snapshot["active_runs"] == list(packet["active_runs"])
    assert snapshot["projection_lag"] == packet["projection_lag"]


def test_absent_data_stays_absent_and_degraded_is_named(tmp_path):
    with _db(tmp_path) as db:
        snapshot = operational_snapshot(db, repo_head_sha="c" * 40, heartbeats={}, now=_NOW)

    assert snapshot["attention"] == []
    assert snapshot["active_runs"] == []
    # an unreadable surface is NAMED in degraded (the packet's null-not-zero discipline) —
    # never a healthy-looking empty block: with no watermark rows, projection lag is unknown.
    assert any(row.get("surface") == "projection_lag" for row in snapshot["degraded"]), snapshot[
        "degraded"
    ]
    # the lag block itself stays the packet's value (possibly null per projection), never zeros.
    assert isinstance(snapshot["projection_lag"], dict)


def test_run_detail_carries_every_control_record(tmp_path):
    """P1/P2: attempts, gates, approvals, and command receipts come from the records as-is."""
    with _db(tmp_path) as db:
        run_id = _seed_awaiting(db)
        db.record_gate_result(
            run_id,
            step_id="p1",
            verdict=GateVerdict.PASS,
            candidate_sha="a" * 40,
            executor="pytest",
            gate_id="gate-checkpoint",
        )
        db.record_approval(
            run_id, gate_id="gate-checkpoint", candidate_sha="a" * 40, operator="dr-seuss"
        )
        command = db.record_command_intent(
            "approve", actor="aio", run_id=run_id, candidate_sha="a" * 40
        )
        db.complete_command(command.command_id, state="completed", receipt={"approval_id": "x"})

        detail = run_detail(db, run_id)

    assert detail is not None
    assert detail["schema"] == RUN_DETAIL_SCHEMA
    assert detail["run"]["run_id"] == run_id
    assert detail["run"]["state"] == "awaiting_approval"
    assert [gate["gate_id"] for gate in detail["gates"]] == ["gate-checkpoint"]
    assert [apr["operator"] for apr in detail["approvals"]] == ["dr-seuss"]
    assert [(c["verb"], c["state"]) for c in detail["commands"]] == [("approve", "completed")]
    assert '"approval_id"' in detail["commands"][0]["receipt_json"]
    # the raw blocks keep their shape; the derived blocks are ADDITIVE (never a re-shape).
    assert {"schema", "run", "attempts", "gates", "approvals", "commands"} <= set(detail)
    assert {
        "cost",
        "evidence",
        "recorded",
        "delivered_knowledge",
        "prepared",
        "timings",
    } <= set(detail)


def _seed_with_ledger(db: ControlDB, ledger_path: Path) -> str:
    """A run awaiting a checkpoint, one attempt recorded, and a ledger pointer stamped."""
    run = db.create_run(
        spec_name="flow",
        model="m",
        state=RunState.RUNNING,
        reason="start",
        candidate_sha="a" * 40,
    )
    attempt = db.start_attempt(
        run.run_id,
        step_id="implement",
        model=run.model,
        state=AttemptState.RUNNING,
        started_at="2026-09-12T00:00:00Z",
    )
    db.finish_attempt(attempt.attempt_id, AttemptState.OK, ended_at="2026-09-12T00:01:00Z")
    db.transition_run(
        run.run_id,
        RunState.AWAITING_APPROVAL,
        reason="checkpoint",
        ledger_path=str(ledger_path),
    )
    return run.run_id


_LEDGER = {
    "spec_name": "flow",
    "workdir": "/tmp/wt_flow_recorded",
    "cell_id": "cell-9",
    "total_cost_usd": 0.0,
    "phases": [
        {
            "phase": "implement",
            "kind": "agent",
            "status": "ok",
            "cost_usd": 0.0,
            "cost_source": "metered",
            "duration_s": 0.0,
            "leased_at": "2026-09-12T00:00:00Z",
            "first_token_at": None,
            "selected_evidence_ids": ["kb-1"],
            "augmentation_evidence": [
                {
                    "id": "kb-1",
                    "revision": "r1",
                    "source_type": "finding",
                    "locator": "experiments/results/kb/kb-1.json",
                }
            ],
            "fallback_mode": "",
            "retrieval_leg_errors": {"dense": "timeout"},
            "augmentation_versions": {"constructor": "v1"},
            "augmentation_tokens": {"in": 1, "out": 2},
            "augmentation_cost_usd": 0.0,
            "prepared_step_path": ".fleet/prepared_steps/implement.a1.json",
            "prepared_step_prompt_sha256": "a" * 64,
            "final_response": "implemented the endpoint",
        },
        {
            "phase": "verify",
            "kind": "test",
            "status": "ok",
            "test_executed_success": True,
            "evaluator_independent": True,
        },
    ],
}


def test_run_detail_derived_blocks_read_the_recorded_ledger(tmp_path):
    """With a ledger: measured-zero cost, independent verification, delivery, prepared step."""
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json.dumps(_LEDGER), encoding="utf-8")
    with _db(tmp_path) as db:
        run_id = _seed_with_ledger(db, ledger_path)
        detail = run_detail(db, run_id)

    assert detail is not None
    # A MEASURED zero stays a measured zero; it is never collapsed to unknown.
    assert detail["cost"] == {"provenance": "$0.0000 \u00b7 metered"}
    assert detail["evidence"]["measured"] == "independent tests passed"
    assert detail["evidence"]["narration"] == "narration recorded"
    assert detail["evidence"]["receipt"] == "missing"
    assert detail["recorded"] == {"ledger_path": str(ledger_path), "present": True}

    delivered = detail["delivered_knowledge"]
    assert delivered["state"] == "recorded"
    assert delivered["use"] == "not_established"  # selection/delivery only
    phase = delivered["phases"][0]
    assert phase["selected_evidence_ids"] == ["kb-1"]
    assert phase["augmentation_evidence"][0]["locator"] == "experiments/results/kb/kb-1.json"
    assert phase["retrieval_leg_errors"] == {"dense": "timeout"}

    prepared = detail["prepared"]["phases"][0]
    assert prepared["prepared_step_path"] == ".fleet/prepared_steps/implement.a1.json"
    assert prepared["prompt_sha256"] == "a" * 64

    timings = {row["field"]: row for row in detail["timings"] if row.get("scope") is None}
    assert timings["run.started_at"]["state"] == "measured"
    # A duration recorded as 0.0 is a measured zero, not a missing value.
    duration = next(row for row in detail["timings"] if row["field"] == "phase.duration_s")
    assert duration == {
        "field": "phase.duration_s",
        "value": 0.0,
        "state": "measured",
        "scope": "implement",
    }
    # A field the record does not carry stays an explicit unknown — never a fabricated 0.
    first_token = next(row for row in detail["timings"] if row["field"] == "phase.first_token_at")
    assert first_token["state"] == "unknown" and first_token["value"] is None


def test_run_detail_without_a_ledger_names_every_absence(tmp_path):
    """No ledger: cost/provenance, delivery, and the prepared step are NAMED absences."""
    with _db(tmp_path) as db:
        run_id = _seed_awaiting(db)
        detail = run_detail(db, run_id)

    assert detail is not None
    assert detail["cost"] == {"provenance": "unknown"}
    assert detail["evidence"]["measured"] == "test result unknown"
    assert detail["recorded"] == {"ledger_path": None, "present": False}
    assert detail["delivered_knowledge"] == {
        "state": "absent",
        "reason": "no ledger recorded",
        "use": "not_established",
        "phases": [],
    }
    assert detail["prepared"] == {
        "state": "absent",
        "reason": "no ledger recorded",
        "phases": [],
    }
    # Timing rows exist for the run/attempt records even without a ledger; absent fields are
    # explicit unknowns rather than invented zeros.
    assert any(row["state"] == "unknown" for row in detail["timings"])


def test_run_detail_error_envelope_is_http_200_through_the_services_layer(monkeypatch, tmp_path):
    """An unreadable control plane renders as a named 200 envelope, never a 500."""
    from apps.control_room import server

    monkeypatch.setenv("FINOPS_CONTROL_DB", str(tmp_path / "missing" / "control.db"))
    response = server.app.test_client().get("/api/runs/run-anything")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["error"] == "control_db_unavailable"
    assert payload["reason"]


def test_run_detail_unknown_run_is_none_not_a_skeleton(tmp_path):
    with _db(tmp_path) as db:
        assert run_detail(db, "run-does-not-exist") is None


def test_operator_loop_blocked_to_durable_receipt(tmp_path):
    """The step-5 acceptance, end to end over the read models.

    blocked run -> inspect the evidence through ``run_detail`` -> take the packet's eligible
    action -> the decision and its durable receipt are visible, and the packet stops asking.
    """
    with _db(tmp_path) as db:
        run_id = _seed_awaiting(db)
        db.record_gate_result(
            run_id,
            step_id="d5",
            verdict=GateVerdict.PASS,
            candidate_sha="a" * 40,
            executor="pytest",
            gate_id="gate-d5",
        )

        packet_before = build_packet(db, repo_head_sha="c" * 40, heartbeats={}, now=_NOW)
        snapshot_before = operational_snapshot(db, repo_head_sha="c" * 40, heartbeats={}, now=_NOW)
        detail_before = run_detail(db, run_id)

        # 1) blocked: the packet offers approve, bound to the exact gate + candidate.
        assert {
            "action": "approve",
            "run_id": run_id,
            "gate_id": "gate-d5",
            "candidate_sha": "a" * 40,
        } in packet_before["safe_actions"]
        # 2) the room shows the SAME identifiers (parity with the authority).
        assert any(
            row["run_id"] == run_id and row["gate_id"] == "gate-d5"
            for row in snapshot_before["attention"]
            if row["kind"] == "approval"
        )
        # 3) evidence: the gate is on record; no approval yet; no fabricated attempts.
        assert [gate["gate_id"] for gate in detail_before["gates"]] == ["gate-d5"]
        assert detail_before["approvals"] == []
        assert detail_before["attempts"] == []  # absent stays absent (never attempt=1)

        # 4) take the eligible action: approve (intent + approval + durable receipt).
        command = db.record_command_intent(
            "approve", actor="aio", run_id=run_id, candidate_sha="a" * 40
        )
        db.record_approval(run_id, gate_id="gate-d5", candidate_sha="a" * 40, operator="dr-seuss")
        db.complete_command(command.command_id, state="completed", receipt={"approval_id": "apr-1"})

        packet_after = build_packet(db, repo_head_sha="c" * 40, heartbeats={}, now=_NOW)
        detail_after = run_detail(db, run_id)

    # 5) the decision is recorded and the packet stops asking; the receipt is durable.
    assert packet_after["awaiting_approvals"] == []
    assert [apr["operator"] for apr in detail_after["approvals"]] == ["dr-seuss"]
    assert [(c["verb"], c["state"]) for c in detail_after["commands"]] == [("approve", "completed")]
    assert '"approval_id"' in detail_after["commands"][0]["receipt_json"]


def test_operations_handlers_serve_the_services_payload(monkeypatch):
    """The route layer is thin: it renders whatever the injected services return, with the
    services' status codes — 200 for the packet, 404 for an unknown run.

    ``monkeypatch.setattr`` snapshots the real module global first, so this test cannot leak
    its fake context into the shared ``server.app`` (a flaky pollution when it ran before the
    admin tests).
    """
    from flask import Flask

    from apps.control_room.routes import operations as route_ops

    class _FakeServices:
        def operations_snapshot(self):
            return {"schema": "control-room-operations/v1", "degraded": []}, 200

        def run_detail(self, run_id):
            if run_id == "run-1":
                return {"schema": "control-room-run-detail/v1", "run": {"run_id": run_id}}, 200
            return {"error": "run not found", "run_id": run_id}, 404

    monkeypatch.setattr(route_ops, "_services", _FakeServices())
    app = Flask(__name__)
    route_ops.register(app, route_ops._services)
    client = app.test_client()

    assert client.get("/api/operations").status_code == 200
    detail = client.get("/api/runs/run-1")
    assert detail.status_code == 200
    assert detail.get_json()["run"]["run_id"] == "run-1"
    assert client.get("/api/runs/nope").status_code == 404


class _FakeRedis:
    """The smallest Redis stand-in for the run-log reads (hgetall/lrange/llen)."""

    def __init__(self, board=None, logs=None, *, fail=None):
        self._board = board or {}
        self._logs = logs or {}
        self._fail = fail

    def _check(self, op):
        if self._fail == op:
            raise ConnectionError("redis unavailable")

    def hgetall(self, key):
        self._check("hgetall")
        assert key == "fleet:jobs"
        return self._board

    def lrange(self, key, start, end):
        self._check("lrange")
        return list(self._logs.get(key, []))

    def llen(self, key):
        self._check("llen")
        return len(self._logs.get(key, []))


def _board(run_id: str, job_id: str) -> dict[str, str]:
    return {job_id: json.dumps({"job_id": job_id, "run_id": run_id, "status": "completed"})}


def test_logs_block_is_a_named_state_never_a_fabricated_zero():
    """The block's honesty rules: a named state, a reason when not recorded, parsed events."""
    block = logs_block(
        cell_id="", state="unbound", reason="no fleet job on the board references this run"
    )
    assert block["state"] == "unbound"
    assert block["cell_id"] == ""
    assert block["events"] == []
    assert block["count"] == 0
    assert "no fleet job" in block["reason"]
    assert block["history_capped"] is False


def test_read_run_logs_resolves_the_job_and_parses_the_retained_tail():
    """A bound run reads its job's event tail: newest-first storage is re-ordered oldest-first
    for the reader, and the raw payload's ``part.text`` is what the drawer renders."""
    raw = [
        json.dumps(
            {"type": "step_finish", "part": {"text": "phase implement ok", "tokens": {"total": 7}}}
        ),
        json.dumps({"type": "text", "part": {"text": "workflow fixture — started"}}),
    ]
    redis = _FakeRedis(
        board=_board("run-1", "job-aa"),
        logs={"events_log:job-aa": raw},
    )
    block = read_run_logs(redis, "run-1")
    assert block["state"] == "recorded"
    assert block["cell_id"] == "job-aa"
    assert block["count"] == 2
    assert block["history_capped"] is False
    assert [event["class"] for event in block["events"]] == ["text", "step_finish"]
    assert block["events"][0]["text"].startswith("workflow fixture")
    assert block["events"][1]["text"] == "phase implement ok"


def test_read_run_logs_names_each_absence():
    """An unbound run and an unreadable Redis are both NAMED, never an empty success."""
    unbound = read_run_logs(_FakeRedis(board={}), "run-1")
    assert unbound["state"] == "unbound"
    assert "no fleet job" in unbound["reason"]

    down = read_run_logs(_FakeRedis(fail="hgetall"), "run-1")
    assert down["state"] == "unavailable"
    assert "redis unavailable" in down["reason"]

    tail_down = read_run_logs(_FakeRedis(board=_board("run-1", "job-aa"), fail="lrange"), "run-1")
    assert tail_down["state"] == "unavailable"
    assert tail_down["cell_id"] == "job-aa"
    assert "redis unavailable" in tail_down["reason"]


def test_run_detail_carries_the_run_logs_block(tmp_path):
    """``run_detail`` attaches the logs block from the injected client: a bound job's tail is
    recorded on the detail, and an unbound read is a NAMED state on the same shape."""
    db = _db(tmp_path)
    run = db.create_run(
        spec_name="flow",
        model="m",
        state=RunState.RUNNING,
        reason="start",
        candidate_sha="c" * 40,
    )
    raw = [json.dumps({"type": "step_finish", "part": {"text": "phase prior ok"}})]
    bound = run_detail(
        db,
        run.run_id,
        redis_client=_FakeRedis(
            board=_board(run.run_id, "job-bb"), logs={"events_log:job-bb": raw}
        ),
    )
    assert bound["logs"]["state"] == "recorded"
    assert bound["logs"]["cell_id"] == "job-bb"
    assert bound["logs"]["events"][0]["text"] == "phase prior ok"

    unbound = run_detail(db, run.run_id)
    assert unbound["logs"]["state"] == "unavailable"
    assert unbound["logs"]["reason"]


def test_run_detail_route_reads_the_job_logs_through_the_live_context(monkeypatch, tmp_path):
    """The wiring proof: the real app's ``/api/runs/<id>`` resolves the injected Redis — the
    context's late-binding accessor means a monkeypatched ``server._redis`` wins at call time."""
    server = pytest.importorskip("apps.control_room.server")

    db_file = tmp_path / "control.db"
    db = ControlDB.open(db_file)
    run = db.create_run(
        spec_name="flow",
        model="m",
        state=RunState.RUNNING,
        reason="start",
        candidate_sha="d" * 40,
    )
    db.close()

    monkeypatch.setenv("FINOPS_CONTROL_DB", str(db_file))
    raw = [json.dumps({"type": "step_finish", "part": {"text": "phase prior ok"}})]
    monkeypatch.setattr(
        server,
        "_redis",
        lambda: _FakeRedis(
            board=_board(run.run_id, "job-cc"), logs={"events_log:job-cc": raw}
        ),
    )

    response = server.app.test_client().get(f"/api/runs/{run.run_id}")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["logs"]["state"] == "recorded"
    assert payload["logs"]["cell_id"] == "job-cc"
    assert payload["logs"]["events"][0]["text"] == "phase prior ok"
