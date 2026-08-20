"""Claude background-session routes (roster/logs/daemon/start/stop/respawn/rm/steer/daemon-stop).

Extracted from ``server.py`` (refactor-repair Debt-1). One-shot CLI control via
``ClaudeAgentsClient`` (``clients.claude_agents_client``), reached through ``server._claude_agents``
(monkeypatched in tests); ownership is enforced server-side before any subprocess call.
"""
from __future__ import annotations

import json
from contextlib import suppress

from flask import Response, jsonify, make_response

from agentic_dynamics.adapters.claude_adapter import _resolve_claude_model
from apps.control_room import server
from apps.control_room.clients.claude_agents_client import (
    CURSOR_KEY_PREFIX,
    OWNED_SESSIONS_KEY,
    ROSTER_KEY,
    SESSION_ID_PATTERN,
    ClaudeAgentsError,
)
from apps.control_room.services.mutations import (
    _claude_agent_mutation_body,
    _idempotent_claude_agent_response,
    _require_owned_claude_agent,
)


def api_claude_agents() -> Response:
    """Read the supervisor-maintained roster; never calls the ``claude`` CLI.

    A missing or unparseable roster is a rendering concern, not a hard
    failure: the fleet section shows a "supervisor not running" state while
    the rest of the Control Room stays unaffected. ``workdirs`` is an
    additive label list (mirroring ``/api/design-sessions``) so the start
    form never needs a raw filesystem path from the browser.
    """
    workdirs = [{"key": key, "label": path.name or key} for key, path in server._claude_agent_workdirs().items()]
    try:
        raw = server._redis().get(ROSTER_KEY)
        agents = json.loads(raw) if raw else None
        if not isinstance(agents, list):
            raise ValueError("roster unavailable")
    except Exception:
        return jsonify({"error": "supervisor_unavailable", "agents": [], "workdirs": workdirs}), 200
    return jsonify({"agents": agents, "workdirs": workdirs})

def api_claude_agent_logs(session_id) -> Response:
    """One-shot, best-effort log tail for external sessions (owned sessions use SSE)."""
    if not SESSION_ID_PATTERN.fullmatch(session_id):
        return jsonify({"error": "invalid session id"}), 400
    try:
        logs = server._claude_agents().get_logs(session_id)
    except ClaudeAgentsError as error:
        return jsonify({"error": str(error), "code": error.code}), 502
    encoded = logs.encode("utf-8", errors="replace")
    truncated = len(encoded) > server.MAX_CLAUDE_AGENT_LOG_BYTES
    body = encoded[:server.MAX_CLAUDE_AGENT_LOG_BYTES].decode("utf-8", errors="replace")
    response = make_response(body)
    response.headers["Content-Type"] = "text/plain; charset=utf-8"
    response.headers["X-Claude-Agent-Log-Truncated"] = "true" if truncated else "false"
    response.headers["X-Claude-Agent-Log-Note"] = "one-shot best-effort tail, not a live stream"
    return response

def api_claude_agents_daemon() -> Response:
    """Read-only ``claude daemon status``; no control affordance is attached here."""
    try:
        status = server._claude_agents().daemon_status()
    except ClaudeAgentsError as error:
        return jsonify({"running": False, "error": str(error), "code": error.code}), 200
    return jsonify(status)

def api_start_claude_agent() -> Response:
    """Start one ``claude --bg`` session in an approved workdir and record ownership."""
    body, failure = _claude_agent_mutation_body()
    if failure:
        return failure
    assert body is not None

    workdir_key = body.get("workdir", "")
    if not isinstance(workdir_key, str):
        return jsonify({"error": "workdir must be a string"}), 400
    workdir = server._claude_agent_workdirs().get(workdir_key)
    if workdir is None:
        return jsonify({"error": "workdir is not approved"}), 400

    task = body.get("task", "")
    if not isinstance(task, str) or not task.strip() or len(task) > server.MAX_CLAUDE_AGENT_TASK_CHARS:
        return (
            jsonify({"error": f"task is required and must be at most {server.MAX_CLAUDE_AGENT_TASK_CHARS} characters"}),
            400,
        )

    model = body.get("model")
    resolved_model = None
    if model is not None:
        if not isinstance(model, str):
            return jsonify({"error": "model must be a string"}), 400
        resolved_model = _resolve_claude_model(model) or None

    advisor = body.get("advisor")
    if advisor is not None and not (
        isinstance(advisor, str)
        and (advisor in server.CLAUDE_AGENT_ADVISORS or server.CLAUDE_AGENT_ADVISOR_ID_PATTERN.fullmatch(advisor))
    ):
        return jsonify({"error": "advisor must be fable, opus, sonnet, or a full model id"}), 400

    def start():
        result = server._claude_agents().start_agent(
            task.strip(),
            cwd=str(workdir),
            model=resolved_model,
            advisor=advisor,
            skip_permissions=True,
        )
        session_id = result.get("id")
        if not isinstance(session_id, str) or not SESSION_ID_PATTERN.fullmatch(session_id):
            raise ClaudeAgentsError("claude --bg returned an unusable session id", code="malformed_json")
        server._redis().sadd(OWNED_SESSIONS_KEY, session_id)
        return jsonify({"ok": True, "id": session_id}), 201

    return _idempotent_claude_agent_response("start", body, start)

def api_stop_claude_agent(session_id) -> Response:
    """``claude stop`` an owned session. The process ends; Respawn resumes it."""
    body, failure = _claude_agent_mutation_body()
    if failure:
        return failure
    assert body is not None
    rejection = _require_owned_claude_agent(server._redis(), session_id)
    if rejection:
        return rejection

    def stop():
        result = server._claude_agents().stop_agent(session_id)
        return jsonify({
            "ok": True,
            "id": session_id,
            "note": "process ended; the conversation is preserved and can be resumed with Respawn",
            "result": result,
        })

    return _idempotent_claude_agent_response(f"stop:{session_id}", body, stop)

def api_respawn_claude_agent(session_id) -> Response:
    """``claude respawn`` an owned session with its conversation intact."""
    body, failure = _claude_agent_mutation_body()
    if failure:
        return failure
    assert body is not None
    rejection = _require_owned_claude_agent(server._redis(), session_id)
    if rejection:
        return rejection

    def respawn():
        result = server._claude_agents().respawn_agent(session_id)
        return jsonify({"ok": True, "id": session_id, "result": result})

    return _idempotent_claude_agent_response(f"respawn:{session_id}", body, respawn)

def api_rm_claude_agent(session_id) -> Response:
    """``claude rm`` an owned session; the transcript remains on disk."""
    body, failure = _claude_agent_mutation_body()
    if failure:
        return failure
    assert body is not None
    redis_client = server._redis()
    rejection = _require_owned_claude_agent(redis_client, session_id)
    if rejection:
        return rejection

    def rm():
        result = server._claude_agents().rm_agent(session_id)
        redis_client.srem(OWNED_SESSIONS_KEY, session_id)
        with suppress(Exception):
            redis_client.delete(f"{CURSOR_KEY_PREFIX}{session_id}")
        return jsonify({
            "ok": True,
            "id": session_id,
            "note": (
                "removed from the Claude agents list; transcript remains on disk and is "
                f"reachable via `claude --resume {session_id}` outside the Control Room"
            ),
            "result": result,
        })

    return _idempotent_claude_agent_response(f"rm:{session_id}", body, rm)

def api_steer_claude_agent(session_id) -> Response:
    """Steer an owned session: interrupt + resume with an adjusted prompt.

    ``claude`` has no mid-flight send-input for a running background session,
    so steering is stop + ``claude --bg --resume <id> "<prompt>"``. The resume
    returns a *new* session id, which this handler adopts as the owned
    successor (removing the interrupted id from the owned set).
    """
    body, failure = _claude_agent_mutation_body()
    if failure:
        return failure
    assert body is not None
    redis_client = server._redis()

    prompt = body.get("prompt", "")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > server.MAX_CLAUDE_AGENT_TASK_CHARS:
        return (
            jsonify({"error": f"prompt is required and must be at most {server.MAX_CLAUDE_AGENT_TASK_CHARS} characters"}),
            400,
        )

    model = body.get("model")
    resolved_model = None
    if model is not None:
        if not isinstance(model, str):
            return jsonify({"error": "model must be a string"}), 400
        resolved_model = _resolve_claude_model(model) or None

    advisor = body.get("advisor")
    if advisor is not None and not (
        isinstance(advisor, str)
        and (advisor in server.CLAUDE_AGENT_ADVISORS or server.CLAUDE_AGENT_ADVISOR_ID_PATTERN.fullmatch(advisor))
    ):
        return jsonify({"error": "advisor must be fable, opus, sonnet, or a full model id"}), 400

    def steer():
        # Ownership is checked inside the idempotency action (not before it)
        # because a successful steer remaps the owned id — a retried request
        # must replay the cached success rather than 403 on the now-stale id.
        rejection = _require_owned_claude_agent(redis_client, session_id)
        if rejection:
            return rejection
        result = server._claude_agents().steer_agent(
            session_id,
            prompt.strip(),
            model=resolved_model,
            advisor=advisor,
            skip_permissions=True,
        )
        resumed_id = result.get("id")
        if not isinstance(resumed_id, str) or not SESSION_ID_PATTERN.fullmatch(resumed_id):
            raise ClaudeAgentsError("claude --bg --resume returned an unusable session id", code="malformed_json")
        redis_client.sadd(OWNED_SESSIONS_KEY, resumed_id)
        if resumed_id != session_id:
            redis_client.srem(OWNED_SESSIONS_KEY, session_id)
            with suppress(Exception):
                redis_client.delete(f"{CURSOR_KEY_PREFIX}{session_id}")
        return jsonify({
            "ok": True,
            "id": resumed_id,
            "resumed_from": session_id,
            "note": "session interrupted and resumed with the adjusted prompt; the new session id supersedes the previous one",
        }), 200

    return _idempotent_claude_agent_response(f"steer:{session_id}", body, steer)

def api_stop_claude_agents_daemon() -> Response:
    """``claude daemon stop``, the most severe control this feature exposes.

    ``keep_workers`` has no silent default: a missing or non-boolean value is
    rejected in request parsing so the blast-radius choice is always explicit
    in the logged request body, not just the UI copy.
    """
    body, failure = _claude_agent_mutation_body()
    if failure:
        return failure
    assert body is not None
    if "keep_workers" not in body or not isinstance(body["keep_workers"], bool):
        return jsonify({"error": "keep_workers boolean is required"}), 400
    keep_workers = body["keep_workers"]

    def stop_daemon():
        result = server._claude_agents().daemon_stop(keep_workers=keep_workers)
        return jsonify({"ok": True, "keep_workers": keep_workers, "result": result})

    return _idempotent_claude_agent_response("daemon-stop", body, stop_daemon)

def register(app):
    """Register this module's routes on the Flask app (server.py composition root)."""
    app.get("/api/claude-agents")(api_claude_agents)
    app.get("/api/claude-agents/<session_id>/logs")(api_claude_agent_logs)
    app.get("/api/claude-agents/daemon")(api_claude_agents_daemon)
    app.post("/api/claude-agents")(api_start_claude_agent)
    app.post("/api/claude-agents/<session_id>/stop")(api_stop_claude_agent)
    app.post("/api/claude-agents/<session_id>/respawn")(api_respawn_claude_agent)
    app.post("/api/claude-agents/<session_id>/rm")(api_rm_claude_agent)
    app.post("/api/claude-agents/<session_id>/steer")(api_steer_claude_agent)
    app.post("/api/claude-agents/daemon/stop")(api_stop_claude_agents_daemon)
