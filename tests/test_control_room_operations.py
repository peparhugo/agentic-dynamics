"""Tests for the Control Room's operational read models (step 5, Phase 0).

The properties pinned here are the Phase-0 truth rules:

* the room's live identifiers come FROM THE PACKET — the parity test asserts the attention
  block matches ``build_packet``'s blocks block-for-block (no re-derivation);
* absent data stays absent: an empty packet area renders empty/null and a degraded read is
  named in ``degraded`` — never a fabricated zero or all-clear;
* the read model is pure given its inputs (no clock, no sockets — ``now`` is injected).
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
for _path in (_REPO_ROOT, _REPO_ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from agentic_dynamics.control.control_db import (  # noqa: E402
    ControlDB,
    GateVerdict,
    RunState,
)
from agentic_dynamics.control.control_status import build_packet  # noqa: E402
from apps.control_room.services.operations import (  # noqa: E402
    RUN_DETAIL_SCHEMA,
    SCHEMA,
    operational_snapshot,
    run_detail,
)

_NOW = "2026-09-12T00:00:00+00:00"


def _db(tmp_path) -> ControlDB:
    return ControlDB.open(tmp_path / "control.db")


def _seed_awaiting(db: ControlDB) -> str:
    run = db.create_run(
        spec_name="flow", model="m", state=RunState.RUNNING, reason="start",
        candidate_sha="a" * 40,
    )
    db.transition_run(run.run_id, RunState.AWAITING_APPROVAL, reason="checkpoint")
    return run.run_id


def _seed_failed(db: ControlDB) -> str:
    run = db.create_run(
        spec_name="flow", model="m", state=RunState.RUNNING, reason="start",
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
    assert any(row.get("surface") == "projection_lag" for row in snapshot["degraded"]), (
        snapshot["degraded"]
    )
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
    # no invented keys: exactly the documented blocks, each as the database returned it.
    assert set(detail) == {"schema", "run", "attempts", "gates", "approvals", "commands"}


def test_run_detail_unknown_run_is_none_not_a_skeleton(tmp_path):
    with _db(tmp_path) as db:
        assert run_detail(db, "run-does-not-exist") is None


def test_operations_handlers_serve_the_services_payload():
    """The route layer is thin: it renders whatever the injected services return, with the
    services' status codes — 200 for the packet, 404 for an unknown run."""
    from flask import Flask

    from apps.control_room.routes import operations as route_ops

    class _FakeServices:
        def operations_snapshot(self):
            return {"schema": "control-room-operations/v1", "degraded": []}, 200

        def run_detail(self, run_id):
            if run_id == "run-1":
                return {"schema": "control-room-run-detail/v1", "run": {"run_id": run_id}}, 200
            return {"error": "run not found", "run_id": run_id}, 404

    app = Flask(__name__)
    route_ops.register(app, _FakeServices())
    client = app.test_client()

    assert client.get("/api/operations").status_code == 200
    detail = client.get("/api/runs/run-1")
    assert detail.status_code == 200
    assert detail.get_json()["run"]["run_id"] == "run-1"
    assert client.get("/api/runs/nope").status_code == 404
