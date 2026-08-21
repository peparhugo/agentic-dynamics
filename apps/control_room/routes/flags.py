"""Supervisor-flag routes (list + steer/interrupt).

Extracted from ``server.py`` (refactor-repair Debt-1). Read-only list plus the two human
actuation routes; ownership revalidation lives in ``services.supervisor`` and the best-effort
actuation emit is called through ``server._emit_actuation_record`` (monkeypatched in tests).
"""
from __future__ import annotations

from flask import Response, jsonify, request

from apps.control_room.services.context import ControlRoomServices
from apps.control_room.services.mutations import _design_mutation_body, _idempotent_design_response

#: The injected application context, bound by ``register()`` before any request is served.
_services: ControlRoomServices | None = None

def api_flags() -> Response:
    """Return newest retained supervisor assessments with exact review metadata."""
    try:
        requested_limit = int(request.args.get("limit", "50"))
    except ValueError:
        requested_limit = 50
    limit = min(100, max(1, requested_limit))
    envelope, status = _services.load_supervisor_flags(limit)
    return jsonify(envelope), status

def api_supervisor_steer(session_id: str) -> Response:
    """Admit an explicit human prompt to one currently flagged native session."""
    body, failure = _design_mutation_body()
    if failure:
        return failure
    assert body is not None
    cell_id = body.get("cell_id")
    prompt = body.get("prompt")
    if not isinstance(cell_id, str) or not cell_id:
        return jsonify({"error": "cell_id is required"}), 400
    if not isinstance(prompt, str) or not prompt.strip():
        return jsonify({"error": "nonblank prompt is required"}), 400
    if len(prompt) > _services.max_design_prompt_chars:
        return jsonify({"error": f"prompt must be at most {_services.max_design_prompt_chars} characters"}), 400

    def steer() -> tuple[Response, int] | Response:
        """Recheck ownership immediately before the OpenCode side effect."""
        _flag, denied = _services.authorize_supervisor_action(session_id, cell_id)
        if denied:
            return denied
        _services.opencode_client().send_input(session_id, prompt.strip(), delivery="steer")
        _services.emit_actuation_record(
            _flag,
            actuation_kind="steer",
            target_cell_id=cell_id,
            requested_action={"prompt": prompt.strip()},
        )
        return jsonify({"action": "steer", "admitted": True, "session_id": session_id})

    return _idempotent_design_response(f"supervisor-steer:{session_id}", body, steer)

def api_supervisor_interrupt(session_id: str) -> Response:
    """Interrupt one flagged native session after exact server confirmation."""
    body, failure = _design_mutation_body()
    if failure:
        return failure
    assert body is not None
    cell_id = body.get("cell_id")
    confirmation = body.get("confirmation")
    if not isinstance(cell_id, str) or not cell_id:
        return jsonify({"error": "cell_id is required"}), 400
    if confirmation != f"INTERRUPT {session_id}":
        return jsonify({"error": f"confirmation must equal INTERRUPT {session_id}"}), 400

    def interrupt() -> tuple[Response, int] | Response:
        """Recheck ownership immediately before the irreversible request."""
        _flag, denied = _services.authorize_supervisor_action(session_id, cell_id)
        if denied:
            return denied
        _services.opencode_client().interrupt(session_id)
        _services.emit_actuation_record(
            _flag,
            actuation_kind="interrupt",
            target_cell_id=cell_id,
        )
        return jsonify({"action": "interrupt", "accepted": True, "session_id": session_id})

    return _idempotent_design_response(f"supervisor-interrupt:{session_id}", body, interrupt)

def register(app, services: ControlRoomServices) -> None:
    """Register this module's routes on the Flask app, receiving the application context."""
    global _services
    _services = services
    app.get("/api/flags")(api_flags)
    app.post("/api/flags/<session_id>/steer")(api_supervisor_steer)
    app.post("/api/flags/<session_id>/interrupt")(api_supervisor_interrupt)
