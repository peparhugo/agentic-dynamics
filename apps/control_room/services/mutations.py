"""Mutation trust-boundary + idempotency helpers for the Control Room's JSON mutations.

Extracted from ``server.py`` (refactor-repair Debt-1). Every mutating route funnels through
``*_mutation_body`` (loopback + same-origin + JSON + size-cap + Idempotency-Key) and an
``_idempotent_*_response`` (Redis ``SET NX`` reserve/replay). Error translation maps expected
manager/client failures to HTTP without leaking internals.
"""
from __future__ import annotations

import hashlib
import json
from contextlib import suppress
from urllib.parse import urlsplit

from flask import Response, jsonify, make_response, request

from apps.control_room import server
from apps.control_room.clients.claude_agents_client import (
    OWNED_SESSIONS_KEY,
    SESSION_ID_PATTERN,
    ClaudeAgentsError,
)
from apps.control_room.clients.opencode_client import OpenCodeError


def _design_mutation_body() -> tuple[dict | None, tuple[Response, int] | None]:
    """Enforce the unauthenticated control plane's local JSON trust boundary."""
    remote = request.remote_addr or ""
    if remote not in {"127.0.0.1", "::1", "localhost"}:
        return None, (jsonify({"error": "loopback access required"}), 403)
    if urlsplit(request.host_url).hostname not in {"127.0.0.1", "::1", "localhost"}:
        return None, (jsonify({"error": "loopback Host required"}), 403)
    origin = request.headers.get("Origin")
    if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
        return None, (jsonify({"error": "cross-origin request rejected"}), 403)
    if not request.is_json:
        return None, (jsonify({"error": "application/json request required"}), 415)
    if request.content_length is not None and request.content_length > server.MAX_DESIGN_REQUEST_BYTES:
        return None, (jsonify({"error": "request body too large"}), 413)
    idempotency_key = request.headers.get("Idempotency-Key", "")
    if not idempotency_key or len(idempotency_key) > 200:
        return None, (jsonify({"error": "Idempotency-Key header required"}), 400)
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return None, (jsonify({"error": "JSON object required"}), 400)
    return body, None

def _idempotent_design_response(
    operation: str, body: dict, action
) -> tuple[Response, int] | Response:
    """Reserve and replay one JSON mutation result using Redis atomic ``SET NX``."""
    supplied_key = request.headers["Idempotency-Key"]
    request_digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    cache_id = hashlib.sha256(f"{operation}\0{supplied_key}".encode()).hexdigest()
    cache_key = f"control_room:idempotency:{cache_id}"
    reservation = json.dumps({"state": "pending", "request_digest": request_digest})
    try:
        redis_client = server._redis()
        reserved = redis_client.set(
            cache_key,
            reservation,
            nx=True,
            ex=server.IDEMPOTENCY_TTL_SECONDS,
        )
        if not reserved:
            existing_raw = redis_client.get(cache_key)
            existing = json.loads(existing_raw) if existing_raw else {}
            if existing.get("request_digest") != request_digest:
                return (
                    jsonify({"error": "Idempotency-Key was already used with a different request"}),
                    409,
                )
            if existing.get("state") == "complete":
                return jsonify(existing.get("body", {})), int(existing.get("status", 200))
            return (
                jsonify({"error": "matching mutation is still in progress", "retryable": True}),
                409,
            )
    except Exception as error:
        return jsonify({"error": f"idempotency store unavailable: {error}"}), 503

    try:
        response = make_response(action())
    except Exception as error:
        response = make_response(_design_error(error))
    completed = json.dumps({
        "state": "complete",
        "request_digest": request_digest,
        "status": response.status_code,
        "body": response.get_json(silent=True) or {},
    })
    with suppress(Exception):
        redis_client.set(cache_key, completed, ex=server.IDEMPOTENCY_TTL_SECONDS)
    # The action already completed. A cache-write failure must not invite a
    # new-key retry that duplicates paid or filesystem-changing work.
    return response

def _design_error(error: Exception) -> tuple[Response, int]:
    """Translate expected manager failures without leaking server internals."""
    if isinstance(error, KeyError):
        return jsonify({"error": "design session not found"}), 404
    if isinstance(error, OpenCodeError):
        return jsonify({"error": str(error), "code": "opencode_unavailable"}), error.status
    if isinstance(error, ValueError):
        return jsonify({"error": str(error)}), 400
    return jsonify({"error": str(error), "code": "design_session_error"}), 503

def _claude_agent_mutation_body() -> tuple[dict | None, tuple[Response, int] | None]:
    """Enforce the same local JSON trust boundary as design-session mutations.

    Duplicated rather than shared with ``_design_mutation_body`` so that
    ``/api/design-sessions*`` behavior can never change as a side effect of
    this feature (docs/scope.md §4).
    """
    remote = request.remote_addr or ""
    if remote not in {"127.0.0.1", "::1", "localhost"}:
        return None, (jsonify({"error": "loopback access required"}), 403)
    if urlsplit(request.host_url).hostname not in {"127.0.0.1", "::1", "localhost"}:
        return None, (jsonify({"error": "loopback Host required"}), 403)
    origin = request.headers.get("Origin")
    if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
        return None, (jsonify({"error": "cross-origin request rejected"}), 403)
    if not request.is_json:
        return None, (jsonify({"error": "application/json request required"}), 415)
    if request.content_length is not None and request.content_length > server.MAX_CLAUDE_AGENT_REQUEST_BYTES:
        return None, (jsonify({"error": "request body too large"}), 413)
    idempotency_key = request.headers.get("Idempotency-Key", "")
    if not idempotency_key or len(idempotency_key) > 200:
        return None, (jsonify({"error": "Idempotency-Key header required"}), 400)
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return None, (jsonify({"error": "JSON object required"}), 400)
    return body, None

def _claude_agent_error(error: Exception) -> tuple[Response, int]:
    """Translate expected claude-agent failures without leaking server internals."""
    if isinstance(error, ClaudeAgentsError):
        return jsonify({"error": str(error), "code": error.code}), 502
    if isinstance(error, ValueError):
        return jsonify({"error": str(error)}), 400
    return jsonify({"error": str(error), "code": "claude_agent_error"}), 503

def _idempotent_claude_agent_response(
    operation: str, body: dict, action
) -> tuple[Response, int] | Response:
    """Sibling of ``_idempotent_design_response`` under a distinct cache namespace.

    Duplicated (rather than parameterized and shared) for the same reason as
    ``_claude_agent_mutation_body``: ``/api/design-sessions*`` retry/replay
    behavior must not change as a side effect of this feature.
    """
    supplied_key = request.headers["Idempotency-Key"]
    request_digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    cache_id = hashlib.sha256(f"claude-agent:{operation}\0{supplied_key}".encode()).hexdigest()
    cache_key = f"control_room:idempotency:{cache_id}"
    reservation = json.dumps({"state": "pending", "request_digest": request_digest})
    try:
        redis_client = server._redis()
        reserved = redis_client.set(
            cache_key,
            reservation,
            nx=True,
            ex=server.IDEMPOTENCY_TTL_SECONDS,
        )
        if not reserved:
            existing_raw = redis_client.get(cache_key)
            existing = json.loads(existing_raw) if existing_raw else {}
            if existing.get("request_digest") != request_digest:
                return (
                    jsonify({"error": "Idempotency-Key was already used with a different request"}),
                    409,
                )
            if existing.get("state") == "complete":
                return jsonify(existing.get("body", {})), int(existing.get("status", 200))
            return (
                jsonify({"error": "matching mutation is still in progress", "retryable": True}),
                409,
            )
    except Exception as error:
        return jsonify({"error": f"idempotency store unavailable: {error}"}), 503

    try:
        response = make_response(action())
    except Exception as error:
        response = make_response(_claude_agent_error(error))
    completed = json.dumps({
        "state": "complete",
        "request_digest": request_digest,
        "status": response.status_code,
        "body": response.get_json(silent=True) or {},
    })
    with suppress(Exception):
        redis_client.set(cache_key, completed, ex=server.IDEMPOTENCY_TTL_SECONDS)
    return response

def _require_owned_claude_agent(redis_client, session_id: str) -> tuple[Response, int] | None:
    """Reject, before any subprocess call, an id absent from the owned set.

    This is the server-side half of the ownership boundary (docs/spec.md
    §1.2/§3.3): Stop/Respawn/Rm must be rejected for external sessions even
    if a client bypasses the hidden UI affordance.
    """
    if not SESSION_ID_PATTERN.fullmatch(session_id):
        return jsonify({"error": "invalid session id"}), 400
    try:
        owned = redis_client.sismember(OWNED_SESSIONS_KEY, session_id)
    except Exception as error:
        return jsonify({"error": f"ownership check unavailable: {error}"}), 503
    if not owned:
        return (
            jsonify({"error": "session not started from the Control Room; manage it with the claude CLI directly"}),
            403,
        )
    return None
