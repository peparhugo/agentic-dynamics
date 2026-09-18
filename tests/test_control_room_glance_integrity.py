"""Factual-integrity guards for the Control Room's resting projection (Astra ae212a0 finding 6).

The repaired Operations lens reads the control records; the glance projection had re-inferred
its own version of the same facts and quietly manufactured values the records never carried —
attempt ``1``, workspace ``wt/<run_id>``, ``narration recorded``, a receipt merely because a run
awaits approval, and a dock feed with fixed ages. When the control database was missing it
asserted zero runs, no pending decision and an all-clear, and the SSE stream only fired on
``control_epoch`` moves, so a same-epoch worker-health change never reached the screen.

These tests seed a REAL control database (no network, no Redis) and assert the projection
composes from the existing run-detail records: recorded values where recorded, ``unknown``
where not, and never a fabricated default. The browser-free half pins the client contract.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
for _path in (_REPO_ROOT, _REPO_ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from agentic_dynamics.control import control_status  # noqa: E402
from agentic_dynamics.control.control_db import (  # noqa: E402
    AttemptState,
    ControlDB,
    GateVerdict,
    RunState,
)
from apps.control_room.routes import glance  # noqa: E402

pytestmark = pytest.mark.fast

STATIC = _REPO_ROOT / "apps" / "control_room" / "static"

_UNKNOWN_COST = {
    "spend": "unknown",
    "burn": "unknown",
    "quota": "unknown",
    "wallet": "unknown",
    "leases": "unknown",
    "money_risk": False,
}


def _stub_glance(monkeypatch, db_path: Path) -> None:
    """Point the projection at an injected control database with deterministic collectors."""
    monkeypatch.setenv("FINOPS_CONTROL_DB", str(db_path))
    monkeypatch.setattr(control_status, "read_repo_head_sha", lambda: ("b" * 40, ""))
    monkeypatch.setattr(control_status, "read_worker_heartbeats", lambda: ({}, ""))
    monkeypatch.setattr(glance, "_cost_block", lambda services: dict(_UNKNOWN_COST))


def _seed_awaiting(db_path: Path, *, attempts: int = 1) -> tuple[str, str]:
    """A run awaiting a checkpoint decision, with `attempts` recorded attempt rows."""
    db = ControlDB.open(db_path)
    try:
        run = db.create_run(
            spec_name="flow",
            model="deepseek/deepseek-v4-pro",
            state=RunState.RUNNING,
            reason="start",
            candidate_sha="a" * 40,
        )
        for index in range(attempts):
            attempt = db.start_attempt(
                run.run_id,
                step_id="implement",
                model=run.model,
                state=AttemptState.RUNNING,
                started_at=f"2026-09-12T00:0{index}:00Z",
            )
            db.finish_attempt(
                attempt.attempt_id, AttemptState.OK, ended_at=f"2026-09-12T00:0{index + 1}:00Z"
            )
        db.record_gate_result(
            run.run_id,
            step_id="implement",
            verdict=GateVerdict.PASS,
            candidate_sha="a" * 40,
            executor="pytest",
            gate_id="gate-d5",
        )
        return run.run_id, "a" * 40
    finally:
        db.close()


def _row_for(glance_payload: dict, run_id: str) -> dict:
    rows = {row["session.identity"]: row for row in glance_payload["run_sample"]}
    return rows[run_id]


def test_missing_control_db_asserts_unknown_not_zero_or_all_clear(monkeypatch, tmp_path):
    """A missing control plane leaves counts/decision/risk unknown — never 0/none/all-clear."""
    _stub_glance(monkeypatch, tmp_path / "does-not-exist.db")

    payload = glance.build_glance(object())

    assert payload["run_counts"] == {
        "running": None,
        "queued": None,
        "failed": None,
        "live": None,
    }
    assert payload["attention"]["decision"]["state"] == "unknown"
    assert payload["attention"]["risk"]["state"] == "unknown"
    assert payload["run_sample"] == []


def test_awaiting_run_receipt_is_only_recorded_when_a_receipt_exists(monkeypatch, tmp_path):
    """Awaiting approval implies nothing about the receipt; the records decide."""
    db_path = tmp_path / "control.db"
    run_id, sha = _seed_awaiting(db_path)
    _stub_glance(monkeypatch, db_path)

    before = _row_for(glance.build_glance(object()), run_id)
    assert before["decision.receipt"] == "missing"
    assert before["decision.receipt"] != "recorded"

    db = ControlDB.open(db_path)
    try:
        command = db.record_command_intent("approve", actor="aio", run_id=run_id, candidate_sha=sha)
        db.record_approval(run_id, gate_id="gate-d5", candidate_sha=sha, operator="dr-seuss")
        db.complete_command(command.command_id, state="completed", receipt={"approval_id": "apr-1"})
    finally:
        db.close()

    after = _row_for(glance.build_glance(object()), run_id)
    assert after["decision.receipt"] == "recorded"


def test_attempt_number_comes_from_attempt_records_not_a_default(monkeypatch, tmp_path):
    """A retried phase reads its real attempt depth; no rows stays unknown (never 1)."""
    db_path = tmp_path / "control.db"
    run_id, _sha = _seed_awaiting(db_path, attempts=2)
    _stub_glance(monkeypatch, db_path)

    assert _row_for(glance.build_glance(object()), run_id)["attempt.number"] == "2"

    empty_db = tmp_path / "empty.db"
    db = ControlDB.open(empty_db)
    try:
        run = db.create_run(
            spec_name="flow",
            model="m",
            state=RunState.RUNNING,
            reason="start",
            candidate_sha="c" * 40,
        )
        empty_run = run.run_id
    finally:
        db.close()
    _stub_glance(monkeypatch, empty_db)

    assert _row_for(glance.build_glance(object()), empty_run)["attempt.number"] == "unknown"


def test_workspace_narration_and_events_come_from_the_recorded_ledger(monkeypatch, tmp_path):
    """The row composes the recorded workdir/narration/tests and a real event history."""
    db_path = tmp_path / "control.db"
    run_id, _sha = _seed_awaiting(db_path)
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(
        json.dumps(
            {
                "spec_name": "flow",
                "workdir": "/tmp/wt_flow_recorded",
                "run_id": run_id,
                "phases": [
                    {
                        "name": "test",
                        "kind": "test",
                        "status": "ok",
                        "test_executed_success": True,
                        "final_response": "",
                    },
                    {
                        "name": "implement",
                        "kind": "agent",
                        "status": "ok",
                        "final_response": "implemented the endpoint",
                    },
                ],
                "attempts": [],
            }
        ),
        encoding="utf-8",
    )
    db = ControlDB.open(db_path)
    try:
        db.transition_run(
            run_id, RunState.AWAITING_APPROVAL, reason="checkpoint", ledger_path=str(ledger_path)
        )
    finally:
        db.close()
    _stub_glance(monkeypatch, db_path)

    row = _row_for(glance.build_glance(object()), run_id)

    assert row["terminal.target"] == "/tmp/wt_flow_recorded"
    assert f"wt/{run_id}" not in json.dumps(row)
    assert row["evidence.advisory"] == "narration recorded"
    assert row["evidence.measured"] == "tests passed"
    # A recorded event history with real identifiers/timestamps, never fixed ages.
    events = row["run.events"]
    assert events, "the recorded attempts/gate must surface as events"
    assert all(event["id"] and event["ts"] for event in events)
    assert any(event["class"] == "measured" for event in events)
    assert any(event["class"] == "lifecycle" for event in events)


def test_cell_binding_is_explicit_or_unknown(monkeypatch, tmp_path):
    """`spec.cell` is the recorded binding when one exists, otherwise `unknown`."""
    db_path = tmp_path / "control.db"
    run_id, _sha = _seed_awaiting(db_path)
    _stub_glance(monkeypatch, db_path)
    assert _row_for(glance.build_glance(object()), run_id)["spec.cell"] == "unknown"

    bound_db = tmp_path / "bound.db"
    bound_run, _ = _seed_awaiting(bound_db)
    ledger_path = tmp_path / "bound_ledger.json"
    ledger_path.write_text(
        json.dumps({"run_id": bound_run, "workdir": "/tmp/wt_bound", "cell_id": "cell-42"}),
        encoding="utf-8",
    )
    db = ControlDB.open(bound_db)
    try:
        db.transition_run(
            bound_run, RunState.AWAITING_APPROVAL, reason="checkpoint", ledger_path=str(ledger_path)
        )
    finally:
        db.close()
    _stub_glance(monkeypatch, bound_db)
    assert _row_for(glance.build_glance(object()), bound_run)["spec.cell"] == "cell-42"


def _payload(epoch: int, worker_state: str, detail: str) -> dict:
    return {
        "control_epoch": epoch,
        "system": {"workers": {"state": worker_state, "age_seconds": 0}},
        "health_detail": {"workers": detail},
        "trust": {"projection_state": "current"},
    }


def _drain_stream(monkeypatch, sequence: list[dict]) -> list[str]:
    """Drive `_event_stream` over a fixed payload sequence without real polling delays."""
    calls = {"n": 0}

    def fake_build(services):
        index = min(calls["n"], len(sequence) - 1)
        calls["n"] += 1
        return sequence[index]

    monkeypatch.setattr(glance, "build_glance", fake_build)
    monkeypatch.setattr(glance, "_SSE_POLL_SECONDS", 0)
    monkeypatch.setattr(glance, "_SSE_MAX_SECONDS", 0.02)
    return list(glance._event_stream(object()))


def test_sse_emits_a_frame_when_health_changes_at_the_same_epoch(monkeypatch):
    """Worker health is not a run-state move; the stream must carry it anyway."""
    up = _payload(7, "up", "0 unhealthy")
    degraded = _payload(7, "degraded", "1 unhealthy")

    frames = _drain_stream(monkeypatch, [up, degraded, degraded])
    transitions = [frame for frame in frames if frame.startswith("event: transition")]

    assert len(transitions) == 1, frames
    payload = json.loads(transitions[0].split("data: ", 1)[1])
    assert payload["control_epoch"] == 7
    assert payload["glance"]["system"]["workers"]["state"] == "degraded"
    assert payload["kind"] == "health"


def test_sse_health_frame_ignores_clock_age_drift(monkeypatch):
    """A recomputed age is not a health change; no frame-per-poll storm."""
    first = _payload(7, "up", "0 unhealthy")
    later = _payload(7, "up", "0 unhealthy")
    later["system"]["workers"]["age_seconds"] = 4
    later["trust"]["worst_age"] = 4
    later["health_detail"]["projections"] = "current · lag 0 · age 4s"

    frames = _drain_stream(monkeypatch, [first, later, later])
    assert [frame for frame in frames if frame.startswith("event: transition")] == []


def _read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_dock_binding_never_guesses_an_id() -> None:
    """The dock uses the explicit cell binding only; no fabricated workspace fallback."""
    parity = _read("parity.js")
    match = parity[parity.index("function cellIdFor(") :]
    match = match[: match.index("\n  }") + 4]
    assert 'run["spec.cell"]' in match
    assert "terminal.target" not in match
    assert "session.identity" not in match
    # The stream target the operator sees is the binding (or an explicit unbound marker).
    assert '"unbound"' in parity
    assert "data-event-ts" in parity  # recorded event timestamps reach the feed rows


def test_visual_verify_node_never_greens_an_unknown_measured_token() -> None:
    """The dependency-flow verify node keys off the explicit token; unknown stays unknown."""
    visuals = _read("visuals.js")
    assert "function verifyState(" in visuals
    assert 'verifyState(run["evidence.measured"])' in visuals
    assert '.indexOf("pending") >= 0 ? "unknown" : "ok"' not in visuals


def test_client_feed_renders_recorded_events_not_fixed_ages() -> None:
    """The attempt feed seeds from `run.events`; an empty history says so."""
    app = _read("app.js")
    assert 'run["run.events"]' in app
    assert "no recorded events for this run" in app
    # The fabricated fixed-age history is gone.
    for fabricated in ("age: 2", "age: 4", "age: 6", "age: 8", '"age 0s'):
        assert fabricated not in app, fabricated


def test_client_fallback_declares_unknown_instead_of_all_clear() -> None:
    """A failed projection renders `unknown`; no client-side zero/none/all-clear copy."""
    app = _read("app.js")
    assert "function unavailableGlance(" in app
    fallback = app[app.index("function unavailableGlance(") :]
    fallback = fallback[: fallback.index("\n  }") + 4]
    assert 'state: "unknown"' in fallback
    assert "running: null" in fallback
    assert "all-clear" not in fallback
    assert 'state: "none"' not in fallback


def test_client_handles_stream_disconnect_and_age() -> None:
    """The SSE client names disconnection and stops trusting old health on a stale age."""
    app = _read("app.js")
    for anchor in (
        "source.onerror",
        "source.onopen",
        "data-stream-state",
        "data-stream-age-seconds",
        "STREAM_STALE_SECONDS",
        "lastFrameAt",
        "pollStreamAge",
    ):
        assert anchor in app, anchor


# ── the run-journey repairs: ledger resolution + cost/verdict fidelity ─────────────────────


def test_recorded_ledger_resolves_the_container_spelled_path(tmp_path, monkeypatch):
    """The run's ledger pointer is spelled /repo/... (the container mount) while the room runs
    on the host. Without the mapping, every ledger-derived field silently rendered unknown."""
    ledger = {"workdir": "/tmp/wt_x", "total_cost_usd": 0.5, "phases": []}
    target = tmp_path / "experiments" / "results" / "workflows" / "spec" / "run.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(ledger), encoding="utf-8")
    import agentic_dynamics.core.paths as paths_mod

    monkeypatch.setattr(paths_mod, "PROJECT_ROOT", tmp_path)
    detail = {"run": {"ledger_path": "/repo/experiments/results/workflows/spec/run.json"}}
    assert glance._recorded_ledger(detail) == ledger
    # An unresolvable pointer stays None (unknown), never a fabricated read.
    assert glance._recorded_ledger({"run": {"ledger_path": "/repo/nope.json"}}) is None


def test_cost_provenance_reports_recorded_spend_or_unknown():
    assert (
        glance._cost_provenance({}, {"run": {"cost_usd": 0.027517302}}, None)
        == "$0.0275 · recorded"
    )
    assert (
        glance._cost_provenance(
            {}, {"run": {"cost_usd": 0.5}}, {"phases": [{"cost_source": "estimated"}]}
        )
        == "$0.5000 · estimated"
    )
    assert glance._cost_provenance({"cost_usd": 0.25}, None, None) == "$0.2500 · recorded"
    assert (
        glance._cost_provenance(
            {}, {"run": {"cost_usd": 0.25}}, {"phases": [{"cost_source": "unknown"}]}
        )
        == "$0.2500 · source unknown"
    )
    assert glance._cost_provenance({}, {"run": {"cost_usd": 0.0}}, None) == "unknown"
    assert glance._cost_provenance({}, None, None) == "unknown"


def test_measured_state_names_independent_verification():
    independent = {
        "phases": [{"kind": "test", "test_executed_success": True, "evaluator_independent": True}]
    }
    assert glance._measured_state(None, independent) == "independent tests passed"
    failed = {
        "phases": [{"kind": "test", "test_executed_success": False, "evaluator_independent": True}]
    }
    assert glance._measured_state(None, failed) == "independent tests failed"
    participant = {"phases": [{"kind": "test", "test_executed_success": True}]}
    assert glance._measured_state(None, participant) == "tests passed"
    assert glance._measured_state(None, {"phases": []}) == "no test recorded"


def test_run_detail_drawer_escape_is_drawer_first() -> None:
    """An open drawer consumes Escape before the workbench: the workbench handler delegates to
    the registered drawer closer when the drawer is visible, and the drawer stops its own
    Escape from bubbling (no double-close)."""
    parity = _read("parity.js")
    assert "activeRunDetailClose" in parity
    # The workbench Escape branch consults the drawer's visibility BEFORE closing the workbench.
    workbench_handler = parity[parity.index("function trapFocus(") :]
    workbench_handler = workbench_handler[: workbench_handler.index("\n  }") + 4]
    assert "run-detail-drawer" in workbench_handler
    assert "activeRunDetailClose()" in workbench_handler
    assert workbench_handler.index("activeRunDetailClose()") < workbench_handler.index(
        "closeWorkbench()"
    )
    # The drawer's own Escape stops propagation so it never reaches the workbench handler.
    assert "stopPropagation" in parity
    # The drawer close control is addressable and the opened detail takes focus (reachability).
    assert 'id: "run-detail-close"' in parity
    open_detail = parity[parity.index("function openRunDetail(") :]
    open_detail = open_detail[: open_detail.index("\n  }") + 4]
    assert "run-detail-close" in open_detail
