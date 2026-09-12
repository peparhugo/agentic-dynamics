"""Operational read-model routes (step 5): the room's ONE gate onto the control packet.

``GET /api/operations`` — the packet + attention/triage (the room's live view; the same
identifiers the AIO acts on) and ``GET /api/runs/<run_id>`` — the P1/P2 per-run detail
(attempts, gate verdicts, approvals, command receipts) over the control records.

Read-only by construction: the handlers call the injected services' read models; an
unreadable control plane renders as NAMED degraded data (never a 500, never zeros), and an
unknown run is a 404 — absence is never dressed as a skeleton.
"""
from __future__ import annotations

from flask import Response, jsonify

from apps.control_room.services.context import ControlRoomServices

#: The injected application context, bound by ``register()`` before any request is served.
_services: ControlRoomServices | None = None


def register(app, services: ControlRoomServices) -> None:
    """Register this module's routes on the Flask app, receiving the application context."""
    global _services
    _services = services
    app.get("/api/operations")(api_operations)
    app.get("/api/runs/<run_id>")(api_run_detail)


def api_operations() -> Response:
    """The operational read model: the packet + the attention (decisions-owed) block."""
    payload, status = _services.operations_snapshot()
    return jsonify(payload), status


def api_run_detail(run_id: str) -> Response:
    """The P1/P2 per-run detail; a 404 for an unknown run, named degradation for an outage."""
    payload, status = _services.run_detail(run_id)
    return jsonify(payload), status
