"""Design-session routes (list/create/spec/input/interrupt/save/run).

Extracted from ``server.py`` (refactor-repair Debt-1). All seven routes funnel through the
mutation trust boundary and the ``DesignSessionManager`` (``services.design_sessions``), reached
through ``server._design_sessions`` (monkeypatched in tests).
"""
from __future__ import annotations

from flask import Response, jsonify

from apps.control_room.services.context import ControlRoomServices
from apps.control_room.services.mutations import (
    _design_error,
    _design_mutation_body,
    _idempotent_design_response,
)

#: The injected application context, bound by ``register()`` before any request is served.
_services: ControlRoomServices | None = None

def api_design_sessions() -> Response:
    """List only portal-owned design sessions and approved workdir labels."""
    try:
        return jsonify(_services.design_manager().list_sessions())
    except Exception as error:
        return _design_error(error)

def api_create_design_session() -> Response:
    """Create a native design conversation and submit its artifact prompt."""
    body, failure = _design_mutation_body()
    if failure:
        return failure
    assert body is not None
    intent = body.get("intent", "")
    if not isinstance(intent, str) or len(intent) > _services.max_design_prompt_chars:
        return (
            jsonify({"error": f"intent must be at most {_services.max_design_prompt_chars} characters"}),
            400,
        )
    def create():
        session = _services.design_manager().create(
            kind=body.get("kind", ""),
            intent=intent,
            model=body.get("model", "") if isinstance(body.get("model", ""), str) else "",
            workdir_key=body.get("workdir", "") if isinstance(body.get("workdir", ""), str) else "",
        )
        return jsonify({"ok": True, "session": session}), 201

    return _idempotent_design_response("create", body, create)

def api_design_session_spec(portal_id) -> Response:
    """Return the coherent draft, validation, matrix, save, and capability state."""
    try:
        return jsonify(_services.design_manager().draft_state(portal_id))
    except Exception as error:
        return _design_error(error)

def api_design_session_input(portal_id) -> Response:
    """Map Send and Steer to native durable prompt admission."""
    body, failure = _design_mutation_body()
    if failure:
        return failure
    assert body is not None
    prompt = body.get("prompt", "")
    if not isinstance(prompt, str) or len(prompt) > _services.max_design_prompt_chars:
        return (
            jsonify({"error": f"prompt must be at most {_services.max_design_prompt_chars} characters"}),
            400,
        )
    delivery = body.get("delivery", "queue")
    if not isinstance(delivery, str) or delivery not in _services.design_delivery_modes:
        # The server, not the browser, fixes the delivery-mode set (review F3):
        # an arbitrary body value can no longer silently upgrade a "Send" into
        # a "steer" — only the two server-known modes are ever forwarded.
        return (
            jsonify({"error": f"delivery must be one of {list(_services.design_delivery_modes)}"}),
            400,
        )
    return _idempotent_design_response(
        f"input:{portal_id}",
        body,
        lambda: jsonify(
            _services.design_manager().send_input(
                portal_id,
                prompt=prompt,
                delivery=delivery,
            )
        ),
    )

def api_design_session_interrupt(portal_id) -> Response:
    """Interrupt native work without changing the browser attachment."""
    _body, failure = _design_mutation_body()
    if failure:
        return failure
    assert _body is not None
    return _idempotent_design_response(
        f"interrupt:{portal_id}",
        _body,
        lambda: jsonify(_services.design_manager().interrupt(portal_id)),
    )

def api_design_session_save(portal_id) -> Response:
    """Atomically save a revalidated draft under experiments/specs."""
    body, failure = _design_mutation_body()
    if failure:
        return failure
    assert body is not None
    if "overwrite" in body and not isinstance(body["overwrite"], bool):
        return jsonify({"error": "overwrite must be a boolean"}), 400
    def save():
        result = _services.design_manager().save(
            portal_id,
            filename=body.get("filename", "") if isinstance(body.get("filename", ""), str) else "",
            overwrite=body.get("overwrite") is True,
        )
        return jsonify(result), 409 if result.get("conflict") else 200

    return _idempotent_design_response(f"save:{portal_id}", body, save)

def api_design_session_run(portal_id) -> Response:
    """Launch an explicitly confirmed saved workflow under a new stream ID."""
    body, failure = _design_mutation_body()
    if failure:
        return failure
    assert body is not None
    required = {"goal", "model", "workdir", "timeout", "commit"}
    missing = sorted(required - body.keys())
    if missing:
        return jsonify({"error": f"missing explicit run fields: {missing}"}), 400
    if not isinstance(body["commit"], bool):
        return jsonify({"error": "commit must be a boolean"}), 400
    if not isinstance(body["timeout"], int) or isinstance(body["timeout"], bool):
        return jsonify({"error": "timeout must be an integer"}), 400
    for field in ("thinking_budget_tokens", "output_token_limit"):
        value = body.get(field, 0)
        if not isinstance(value, int) or isinstance(value, bool):
            return jsonify({"error": f"{field} must be an integer"}), 400
    def run():
        result = _services.design_manager().run_workflow(
            portal_id,
            goal=body["goal"] if isinstance(body["goal"], str) else "",
            model=body["model"] if isinstance(body["model"], str) else "",
            workdir_key=body["workdir"] if isinstance(body["workdir"], str) else "",
            timeout=body["timeout"],
            commit=body["commit"] is True,
            backend=body.get("backend") or None,
            thinking_budget_tokens=body.get("thinking_budget_tokens", 0),
            output_token_limit=body.get("output_token_limit", 0),
        )
        return jsonify(result), 202

    return _idempotent_design_response(f"run:{portal_id}", body, run)

def register(app, services: ControlRoomServices) -> None:
    """Register this module's routes on the Flask app, receiving the application context."""
    global _services
    _services = services
    app.get("/api/design-sessions")(api_design_sessions)
    app.post("/api/design-sessions")(api_create_design_session)
    app.get("/api/design-sessions/<portal_id>/spec")(api_design_session_spec)
    app.post("/api/design-sessions/<portal_id>/input")(api_design_session_input)
    app.post("/api/design-sessions/<portal_id>/interrupt")(api_design_session_interrupt)
    app.post("/api/design-sessions/<portal_id>/save")(api_design_session_save)
    app.post("/api/design-sessions/<portal_id>/run")(api_design_session_run)
