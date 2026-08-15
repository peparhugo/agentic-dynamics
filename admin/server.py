"""Dynamic-code admin portal backend.

Serves the admin dashboard and exposes live experiment telemetry over SSE.

Endpoints:
    GET  /api/matrix           — queue/status matrix (Redis hash + queue)
    GET  /api/status           — SSE stream of status transitions
    GET  /api/events/<cell_id> — SSE stream of a cell's events (replay + live)
    GET  /api/routing          — routing board (Phase 7; stub for now)
    POST /api/experiments      — enqueue/clear the experiment queue
    POST /api/queue/reinterleave — re-interleave story_jobs round-robin by provider
    GET  /api/claude-agents           — Claude background-session roster (Redis read only)
    GET  /api/claude-agents/<id>/logs — one-shot log tail for an external session
    GET  /api/claude-agents/daemon    — read-only `claude daemon status`
    POST /api/claude-agents           — start a `claude --bg` session
    POST /api/claude-agents/<id>/stop|respawn|rm — owned-session lifecycle control
    POST /api/claude-agents/<id>/steer        — interrupt + resume with an adjusted prompt
    POST /api/claude-agents/daemon/stop          — stop the local claude daemon
    GET  /                    — static dashboard (admin/static)

Run:
    python3 admin/server.py      # default port 8000 (FINOPS_PORT override)

Deployment note: ``app.run(threaded=True)`` is Flask's built-in single-process
development server, intended for a local operator tool rather than production.
Each SSE client (``/api/status``, ``/api/events/<cell_id>``) holds one request
thread plus one Redis Pub/Sub subscription for the life of the tab, so there is
no connection cap. For multi-operator use, front it with a threaded gunicorn:

    gunicorn --worker-class gthread --threads 4 --workers 1 \
      --bind 127.0.0.1:8000 'admin.server:app'
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from collections import Counter
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from flask import Flask, Response, jsonify, make_response, request

from instrument.claude_adapter import _resolve_claude_model
from instrument.live import (
    EVENT_CHANNEL_PREFIX,
    EVENT_LOG_MAX,
    EVENT_LOG_PREFIX,
    STATUS_CHANNEL,
    STATUS_KEY,
)
from instrument.routing import compute_routing
from instrument.supervisor import (
    SUPERVISOR_FLAGS_KEY,
    SUPERVISOR_FLAGS_MAX,
    SUPERVISOR_SESSION_CELLS_KEY,
    normalize_flag,
    parse_mapping,
)
from reinterleave_queue import (
    _read_queue as _read_queue_cells,
    _write_queue as _write_queue_cells,
    reinterleave_cells,
)

try:  # Package imports under pytest and WSGI.
    from admin.claude_agents_client import (
        CURSOR_KEY_PREFIX,
        OWNED_SESSIONS_KEY,
        ROSTER_KEY,
        SESSION_ID_PATTERN,
        ClaudeAgentsClient,
        ClaudeAgentsError,
    )
    from admin.design_sessions import DESIGN_SESSIONS_KEY, DesignSessionManager
    from admin.opencode_client import OpenCodeClient, OpenCodeError
except ModuleNotFoundError:  # pragma: no cover - documented ``python admin/server.py`` launch
    from claude_agents_client import (
        CURSOR_KEY_PREFIX,
        OWNED_SESSIONS_KEY,
        ROSTER_KEY,
        SESSION_ID_PATTERN,
        ClaudeAgentsClient,
        ClaudeAgentsError,
    )
    from design_sessions import DESIGN_SESSIONS_KEY, DesignSessionManager
    from opencode_client import OpenCodeClient, OpenCodeError

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))
QUEUE_KEY = "story_jobs"
RESULTS_KEY = "story_results"
HEARTBEAT_SECONDS = 15
MAX_DESIGN_REQUEST_BYTES = 64 * 1024
MAX_DESIGN_PROMPT_CHARS = 12_000
MAX_CLAUDE_AGENT_REQUEST_BYTES = 64 * 1024
MAX_CLAUDE_AGENT_TASK_CHARS = 12_000
MAX_CLAUDE_AGENT_LOG_BYTES = 64 * 1024
CLAUDE_AGENT_ADVISORS = {"fable", "opus", "sonnet"}
CLAUDE_AGENT_ADVISOR_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,80}$")
IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60
ROOT = Path(__file__).resolve().parent.parent
SUPERVISOR_FLAGS_FILE = ROOT / "experiments" / "results" / "supervisor" / "flags.jsonl"
SUPERVISOR_FILE_TAIL_BYTES = 512 * 1024
SUPERVISOR_ACTIVE_WINDOW_SECONDS = int(os.environ.get("SUPERVISOR_ACTIVE_WINDOW", "900"))

app = Flask(__name__, static_folder="static", static_url_path="/static")
_design_manager: DesignSessionManager | None = None
_claude_agents_client: ClaudeAgentsClient | None = None


def _redis() -> redis.Redis:
    import redis

    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)


def _design_sessions() -> DesignSessionManager:
    """Construct the process-local manager around persistent Redis metadata."""
    global _design_manager
    if _design_manager is None:
        configured = os.environ.get("FINOPS_DESIGN_WORKDIRS")
        paths = (
            [Path(item) for item in configured.split(os.pathsep) if item]
            if configured
            else [ROOT]
        )
        workdirs = {
            "repository" if index == 0 else f"repository-{index + 1}": path
            for index, path in enumerate(paths)
        }
        _design_manager = DesignSessionManager(
            root=ROOT,
            redis_factory=_redis,
            opencode=OpenCodeClient(os.environ.get("OPENCODE_SERVER_URL", "http://127.0.0.1:4096")),
            workdirs=workdirs,
        )
    return _design_manager


def _opencode_client() -> OpenCodeClient:
    """Construct the server-side control client without exposing its URL."""
    return OpenCodeClient(os.environ.get("OPENCODE_SERVER_URL", "http://127.0.0.1:4096"))


def _utc_now() -> str:
    """Return a canonical UTC timestamp for API envelopes."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_flag_tail(path: Path) -> tuple[list[str] | None, str | None]:
    """Read a bounded newest-first tail from the append-only JSONL audit file."""
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            start = max(0, size - SUPERVISOR_FILE_TAIL_BYTES)
            handle.seek(start)
            raw = handle.read(SUPERVISOR_FILE_TAIL_BYTES)
    except FileNotFoundError:
        return None, "supervisor flag fallback file is not present"
    except OSError as error:
        return None, f"supervisor flag fallback is unreadable: {error}"

    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if start > 0 and lines:
        # The first item may begin in the middle of a JSON record.
        lines = lines[1:]
    return list(reversed(lines[-SUPERVISOR_FLAGS_MAX:])), None


def _mapping_is_stale(mapping: dict[str, str]) -> bool:
    """Return whether an exact mapping has exceeded the active window."""
    activity = mapping.get("last_activity_at")
    if not activity:
        return False
    try:
        observed = datetime.fromisoformat(activity.replace("Z", "+00:00"))
    except ValueError:
        return False
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - observed).total_seconds() > SUPERVISOR_ACTIVE_WINDOW_SECONDS


def _review_for_flag(redis_client, flag: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    """Resolve current exact mapping first, then an immutable flag snapshot."""
    current = None
    if redis_client is not None:
        try:
            current = parse_mapping(
                redis_client.hget(SUPERVISOR_SESSION_CELLS_KEY, flag["session_id"])
            )
        except Exception as error:
            warnings.append(f"session mapping unavailable: {error}")

    if current and current["session_id"] == flag["session_id"]:
        return {
            "state": "stale" if _mapping_is_stale(current) else "mapped",
            "cell_id": current["cell_id"],
            "source": current["source"],
            "mapped_at": current["mapped_at"],
            "last_activity_at": current.get("last_activity_at"),
        }

    snapshot = parse_mapping(flag.get("review")) or parse_mapping(flag.get("mapping"))
    if snapshot and snapshot["session_id"] != flag["session_id"]:
        snapshot = None
    if snapshot:
        return {
            "state": "snapshot",
            "cell_id": snapshot["cell_id"],
            "source": snapshot["source"],
            "mapped_at": snapshot["mapped_at"],
            "last_activity_at": snapshot.get("last_activity_at"),
        }
    return {"state": "unavailable", "cell_id": None, "source": None, "mapped_at": None}


def _load_supervisor_flags(limit: int) -> tuple[dict[str, Any], int]:
    """Load, validate, deduplicate, and enrich retained supervisor flags."""
    warnings: list[str] = []
    redis_client = None
    redis_readable = False
    file_readable = False
    raw_records: list[str] = []
    source = "none"
    try:
        redis_client = _redis()
        raw_records = redis_client.lrange(SUPERVISOR_FLAGS_KEY, 0, SUPERVISOR_FLAGS_MAX - 1)
        redis_readable = True
        if raw_records:
            source = "redis"
    except Exception as error:
        warnings.append(f"supervisor Redis unavailable: {error}")

    if not raw_records:
        file_records, file_warning = _read_flag_tail(SUPERVISOR_FLAGS_FILE)
        if file_records is not None:
            file_readable = True
            raw_records = file_records
            if raw_records:
                source = "file"
            elif not redis_readable:
                source = "file"
        elif file_warning:
            warnings.append(file_warning)

    flags: list[dict[str, Any]] = []
    seen_sessions: set[str] = set()
    malformed = 0
    for raw in raw_records:
        try:
            decoded = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            malformed += 1
            continue
        flag = normalize_flag(decoded)
        if flag is None:
            malformed += 1
            continue
        if flag["session_id"] in seen_sessions:
            continue
        seen_sessions.add(flag["session_id"])
        review = _review_for_flag(redis_client, flag, warnings)
        flag["review"] = {key: value for key, value in review.items() if key != "last_activity_at"}
        flag["last_activity_at"] = review.get("last_activity_at") or flag.get("last_activity_at")
        flags.append(flag)
        if len(flags) >= limit:
            break
    if malformed:
        warnings.append(f"skipped {malformed} malformed supervisor flag record(s)")

    if source == "file":
        degraded = True
    elif source == "redis":
        degraded = False
    else:
        degraded = not redis_readable
    unavailable = not redis_readable and not file_readable
    envelope = {
        "generated_at": _utc_now(),
        "source": source,
        "degraded": degraded,
        "warnings": list(dict.fromkeys(warnings)),
        "flags": flags,
    }
    return envelope, 503 if unavailable else 200


def _authorize_supervisor_action(
    session_id: str,
    cell_id: str,
) -> tuple[dict[str, Any] | None, tuple[Response, int] | None]:
    """Revalidate retained ownership and exact stream mapping at side-effect time."""
    envelope, status = _load_supervisor_flags(SUPERVISOR_FLAGS_MAX)
    if status == 503:
        return None, (jsonify({"error": "supervisor control state unavailable"}), 503)
    flag = next((item for item in envelope["flags"] if item["session_id"] == session_id), None)
    if flag is None:
        return None, (jsonify({"error": "retained supervisor flag not found"}), 404)
    review = flag.get("review") or {}
    mapped_cell = review.get("cell_id")
    if review.get("state") == "unavailable" or not mapped_cell:
        return None, (jsonify({"error": "supervisor session mapping not found"}), 404)
    if cell_id != mapped_cell:
        return None, (jsonify({"error": "supervisor session mapping changed"}), 409)
    return flag, None


def _claude_agents() -> ClaudeAgentsClient:
    """Construct the process-local ``claude`` CLI wrapper used for one-shot calls.

    Only short, bounded, one-shot mutating commands (start/stop/respawn/rm/
    daemon status/daemon stop) go through this client from Flask request
    handlers; continuous polling belongs to
    ``scripts/claude_agents_supervisor.py`` (docs/spec.md §2.1).
    """
    global _claude_agents_client
    if _claude_agents_client is None:
        _claude_agents_client = ClaudeAgentsClient()
    return _claude_agents_client


def _claude_agent_workdirs() -> dict[str, Path]:
    """Parse the approved-workdir allowlist independently of ``_design_sessions()``.

    A raw filesystem path from the browser is never accepted; only a key into
    this dict is, mirroring ``DesignSessionManager``'s ``workdir_key`` rule.
    """
    configured = os.environ.get("FINOPS_CLAUDE_AGENT_WORKDIRS")
    paths = [Path(item) for item in configured.split(os.pathsep) if item] if configured else [ROOT]
    return {
        "repository" if index == 0 else f"repository-{index + 1}": path
        for index, path in enumerate(paths)
    }


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
    if request.content_length is not None and request.content_length > MAX_DESIGN_REQUEST_BYTES:
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
        redis_client = _redis()
        reserved = redis_client.set(
            cache_key,
            reservation,
            nx=True,
            ex=IDEMPOTENCY_TTL_SECONDS,
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
        redis_client.set(cache_key, completed, ex=IDEMPOTENCY_TTL_SECONDS)
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
    if request.content_length is not None and request.content_length > MAX_CLAUDE_AGENT_REQUEST_BYTES:
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
        redis_client = _redis()
        reserved = redis_client.set(
            cache_key,
            reservation,
            nx=True,
            ex=IDEMPOTENCY_TTL_SECONDS,
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
        redis_client.set(cache_key, completed, ex=IDEMPOTENCY_TTL_SECONDS)
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


def _sse(generator) -> Response:
    """Return a response configured for an unbuffered SSE connection."""
    return Response(
        generator,
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _reported_number(value) -> float | None:
    """Return valid reported telemetry as a float, or ``None``.

    Telemetry is observational rather than billing data, so malformed values
    must be ignored instead of coerced. In particular, booleans are excluded
    even though Python treats them as integers.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number >= 0 else None


def _event_timestamp(event, part) -> str | int | float | None:
    """Return a supplied event timestamp without inventing server time."""
    for container in (event, part):
        for key in ("timestamp", "time", "created_at", "createdAt"):
            value = container.get(key)
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                return value
    return None


def _identity_number(value) -> str:
    """Format a telemetry number identically to the browser identity helper."""
    if value is None:
        return ""
    return f"{value:.12f}".rstrip("0").rstrip(".") or "0"


def _step_sample(payload) -> dict[str, Any] | None:
    """Extract one defensive token/cost sample from a raw event payload.

    Both current events (fields under ``part``) and retained legacy events
    (top-level fields) are supported. A step with no valid token or cost value
    is omitted because it cannot contribute to a chart or aggregate.
    """
    try:
        event = json.loads(payload) if isinstance(payload, str) else payload
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(event, dict):
        return None

    event_type = str(event.get("type", "")).replace("-", "_").lower()
    if event_type != "step_finish":
        return None
    part = event.get("part") if isinstance(event.get("part"), dict) else event
    tokens = part.get("tokens") if isinstance(part.get("tokens"), dict) else {}

    input_tokens = _reported_number(tokens.get("input"))
    output_tokens = _reported_number(tokens.get("output"))
    reasoning_tokens = _reported_number(tokens.get("reasoning"))
    total_tokens = _reported_number(tokens.get("total"))
    cache = tokens.get("cache")
    cache_tokens = _reported_number(cache)
    if isinstance(cache, dict):
        cache_values = [_reported_number(cache.get("read")), _reported_number(cache.get("write"))]
        valid_cache = [value for value in cache_values if value is not None]
        cache_tokens = sum(valid_cache) if valid_cache else None

    # Some providers omit ``total``. Summing only explicitly reported fields
    # yields a useful bar without manufacturing missing token values as zero.
    if total_tokens is None:
        components = [input_tokens, output_tokens, reasoning_tokens, cache_tokens]
        reported_components = [value for value in components if value is not None]
        total_tokens = sum(reported_components) if reported_components else None

    cost = _reported_number(part.get("cost"))
    if cost is None and total_tokens is None:
        return None

    timestamp = _event_timestamp(event, part)
    session_id = event.get("sessionID") or part.get("sessionID")
    identity = "|".join([
        str(session_id or ""),
        str(timestamp if timestamp is not None else ""),
        _identity_number(cost),
        _identity_number(input_tokens),
        _identity_number(output_tokens),
        _identity_number(reasoning_tokens),
        _identity_number(cache_tokens),
        _identity_number(total_tokens),
    ])
    return {
        "identity": identity,
        "timestamp": timestamp,
        "cost": cost,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cache_tokens": cache_tokens,
        "total_tokens": total_tokens,
    }


def _retained_telemetry(redis_client, cell_ids) -> dict[str, Any]:
    """Build an additive retained-window snapshot from existing event logs.

    Each log is independently optional. A transient per-cell read failure does
    not erase the baseline matrix response; ``available`` records that the
    telemetry extension is incomplete while the legacy status data remains
    usable.

    All log reads are issued in a single non-transactional pipeline so the
    fleet snapshot costs one round trip, not one per cell.
    """
    cells = {}
    total_cost = 0.0
    input_tokens = 0.0
    output_tokens = 0.0
    cost_samples = input_samples = output_samples = 0
    available = True
    capped = False

    keys = [f"{EVENT_LOG_PREFIX}{cell_id}" for cell_id in cell_ids]
    try:
        pipe = redis_client.pipeline(transaction=False)
        for key in keys:
            pipe.lrange(key, 0, -1)
        histories = pipe.execute()
    except Exception:
        # A connection-level failure marks telemetry incomplete but must not
        # erase the legacy matrix response (same contract as today).
        histories = [None] * len(cell_ids)

    for cell_id, history in zip(cell_ids, histories):
        if history is None:
            available = False
            history = []
        capped = capped or len(history) >= EVENT_LOG_MAX

        samples = []
        for payload in reversed(history):
            sample = _step_sample(payload)
            if sample is None:
                continue
            samples.append(sample)
            if sample["cost"] is not None:
                total_cost += sample["cost"]
                cost_samples += 1
            if sample["input_tokens"] is not None:
                input_tokens += sample["input_tokens"]
                input_samples += 1
            if sample["output_tokens"] is not None:
                output_tokens += sample["output_tokens"]
                output_samples += 1

        cell_costs = [sample["cost"] for sample in samples if sample["cost"] is not None]
        cell_inputs = [
            sample["input_tokens"] for sample in samples if sample["input_tokens"] is not None
        ]
        cell_outputs = [
            sample["output_tokens"] for sample in samples if sample["output_tokens"] is not None
        ]
        cells[cell_id] = {
            "reported_cost": sum(cell_costs) if cell_costs else None,
            "input_tokens": sum(cell_inputs) if cell_inputs else None,
            "output_tokens": sum(cell_outputs) if cell_outputs else None,
            "latest_cost": cell_costs[-1] if cell_costs else None,
            "samples": samples,
            "history_size": len(history),
            "history_capped": len(history) >= EVENT_LOG_MAX,
            "partial": True,
        }

    return {
        "available": available,
        "provenance": "retained_window",
        "partial": True,
        "reported_cost": total_cost if cost_samples else None,
        "input_tokens": input_tokens if input_samples else None,
        "output_tokens": output_tokens if output_samples else None,
        "cost_samples": cost_samples,
        "history_capped": capped,
        "cells": cells,
    }


@app.get("/api/matrix")
def api_matrix() -> Response:
    """Return the legacy fleet matrix plus additive retained telemetry."""
    try:
        r = _redis()
        remaining = r.llen(QUEUE_KEY)
        statuses = r.hgetall(STATUS_KEY)
        results = r.hgetall(RESULTS_KEY)
    except Exception:
        return jsonify({"error": "redis_unavailable", "cells": {}}), 503

    counts: dict[str, int] = {}
    for status in statuses.values():
        counts[status] = counts.get(status, 0) + 1
    completed = counts.get("done", 0) + counts.get("failed", 0) + counts.get("timeout", 0)
    response = {
        "total": len(statuses),
        "remaining_in_queue": remaining,
        "queued": counts.get("queued", 0),
        "running": counts.get("running", 0),
        "done": counts.get("done", 0),
        "failed": counts.get("failed", 0),
        "timeout": counts.get("timeout", 0),
        "completed": completed,
        "results_saved": len(results),
        "cells": statuses,
    }
    design_stream_ids: list[str] = []
    try:
        for payload in r.hgetall(DESIGN_SESSIONS_KEY).values():
            metadata = json.loads(payload)
            stream_id = metadata.get("stream_id") if isinstance(metadata, dict) else None
            if isinstance(stream_id, str) and stream_id:
                design_stream_ids.append(stream_id)
    except Exception:
        # Fleet telemetry remains useful if optional design metadata is absent.
        pass
    response["telemetry"] = _retained_telemetry(r, [*statuses, *design_stream_ids])
    return jsonify(response)


@app.get("/api/status")
def api_status() -> Response:
    """Stream status transitions while preserving the existing SSE payload."""
    def gen():
        r = _redis()
        pubsub = r.pubsub()
        pubsub.subscribe(STATUS_CHANNEL)
        last_beat = time.time()
        try:
            while True:
                msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg:
                    yield f"data: {msg['data']}\n\n"
                elif time.time() - last_beat >= HEARTBEAT_SECONDS:
                    yield ": ping\n\n"
                    last_beat = time.time()
        finally:
            try:
                pubsub.unsubscribe(STATUS_CHANNEL)
                pubsub.close()
            except Exception:
                pass

    return _sse(gen())


@app.get("/api/flags")
def api_flags() -> Response:
    """Return newest retained supervisor assessments with exact review metadata."""
    try:
        requested_limit = int(request.args.get("limit", "50"))
    except ValueError:
        requested_limit = 50
    limit = min(100, max(1, requested_limit))
    envelope, status = _load_supervisor_flags(limit)
    return jsonify(envelope), status


@app.get("/api/events/<cell_id>")
def api_events(cell_id) -> Response:
    """Replay retained cell events, mark the boundary, then stream live data.

    The named boundary is additive: clients listening through ``onmessage``
    continue to receive the same raw event frames, while Control Room clients
    can exclude replay from the rolling burn-rate window.
    """
    log_key = f"{EVENT_LOG_PREFIX}{cell_id}"
    channel = f"{EVENT_CHANNEL_PREFIX}{cell_id}"

    def gen():
        r = _redis()
        # Subscribe before reading history so an event published during replay
        # is queued by Redis instead of falling through the history/live gap.
        pubsub = r.pubsub()
        pubsub.subscribe(channel)
        try:
            history = r.lrange(log_key, 0, -1)
            for payload in reversed(history):
                yield f"data: {payload}\n\n"
        except Exception:
            pass
        yield f"event: replay_complete\ndata: {json.dumps({'cell_id': cell_id})}\n\n"
        last_beat = time.time()
        try:
            while True:
                msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg:
                    yield f"data: {msg['data']}\n\n"
                elif time.time() - last_beat >= HEARTBEAT_SECONDS:
                    yield ": ping\n\n"
                    last_beat = time.time()
        finally:
            try:
                pubsub.unsubscribe(channel)
                pubsub.close()
            except Exception:
                pass

    return _sse(gen())


@app.get("/api/routing")
def api_routing() -> Response:
    summary_path = (
        Path(__file__).resolve().parent.parent / "experiments" / "results" / "_results_summary.json"
    )
    try:
        data = json.loads(summary_path.read_text())
        entries = data.get("entries", [])
    except (OSError, json.JSONDecodeError):
        return jsonify(
            {
                "_meta": {"tasks_analyzed": 0},
                "per_task": [],
                "strategies": {},
                "note": "no results summary yet",
            }
        )
    return jsonify(compute_routing(entries))


@app.post("/api/experiments")
def api_experiments() -> Response:
    # Never default to a costly action: require an explicit JSON body + action.
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or "action" not in body:
        return jsonify({"error": "missing action"}), 400
    action = body["action"]
    if action not in ("enqueue", "clear"):
        return jsonify({"error": f"unknown action {action!r}"}), 400

    cmd = [sys.executable, "scripts/enqueue.py"]
    if action == "clear":
        cmd.append("--clear")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                              cwd=Path(__file__).resolve().parent.parent)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"ok": proc.returncode == 0, "output": (proc.stdout or proc.stderr).strip()})


@app.post("/api/queue/reinterleave")
def api_queue_reinterleave() -> Response:
    """Re-interleave ``story_jobs`` round-robin across providers.

    Queue-level control (unlike the flagged session interrupts): it needs no
    supervisor flag because it reorders *future* picks without touching any
    running session. The reorder logic is reused verbatim from
    ``scripts/reinterleave_queue.py`` (``reinterleave_cells`` plus the shared
    read/write helpers) so the admin surface and the CLI can never drift.
    """
    body, failure = _design_mutation_body()
    if failure:
        return failure
    assert body is not None

    def reinterleave() -> tuple[Response, int]:
        r = _redis()
        before = _read_queue_cells(r)
        after = reinterleave_cells(before)
        _write_queue_cells(r, after)
        return jsonify({
            "ok": True,
            "count": len(before),
            "before": _provider_summary(before),
            "after": _provider_summary(after),
        }), 200

    return _idempotent_design_response("queue-reinterleave", body, reinterleave)


def _provider_summary(cells: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize a cell list by provider for the reinterleave response.

    Mirrors ``reinterleave_queue.py``'s ``--json`` report so the admin surface
    and the CLI stay consistent: counts per provider, the consumption order of
    provider labels, and the longest run of consecutive same-provider cells.
    """
    providers = [cell["model"].split("/", 1)[0] for cell in cells]
    longest = current = 1 if providers else 0
    for previous, next_ in zip(providers, providers[1:]):
        current = current + 1 if previous == next_ else 1
        longest = max(longest, current)
    return {
        "by_provider": dict(Counter(providers)),
        "order": providers,
        "longest_provider_run": longest,
    }


@app.get("/api/design-sessions")
def api_design_sessions() -> Response:
    """List only portal-owned design sessions and approved workdir labels."""
    try:
        return jsonify(_design_sessions().list_sessions())
    except Exception as error:
        return _design_error(error)


@app.post("/api/design-sessions")
def api_create_design_session() -> Response:
    """Create a native design conversation and submit its artifact prompt."""
    body, failure = _design_mutation_body()
    if failure:
        return failure
    assert body is not None
    intent = body.get("intent", "")
    if not isinstance(intent, str) or len(intent) > MAX_DESIGN_PROMPT_CHARS:
        return (
            jsonify({"error": f"intent must be at most {MAX_DESIGN_PROMPT_CHARS} characters"}),
            400,
        )
    def create():
        session = _design_sessions().create(
            kind=body.get("kind", ""),
            intent=intent,
            model=body.get("model", "") if isinstance(body.get("model", ""), str) else "",
            workdir_key=body.get("workdir", "") if isinstance(body.get("workdir", ""), str) else "",
        )
        return jsonify({"ok": True, "session": session}), 201

    return _idempotent_design_response("create", body, create)


@app.get("/api/design-sessions/<portal_id>/spec")
def api_design_session_spec(portal_id) -> Response:
    """Return the coherent draft, validation, matrix, save, and capability state."""
    try:
        return jsonify(_design_sessions().draft_state(portal_id))
    except Exception as error:
        return _design_error(error)


@app.post("/api/design-sessions/<portal_id>/input")
def api_design_session_input(portal_id) -> Response:
    """Map Send and Steer to native durable prompt admission."""
    body, failure = _design_mutation_body()
    if failure:
        return failure
    assert body is not None
    prompt = body.get("prompt", "")
    if not isinstance(prompt, str) or len(prompt) > MAX_DESIGN_PROMPT_CHARS:
        return (
            jsonify({"error": f"prompt must be at most {MAX_DESIGN_PROMPT_CHARS} characters"}),
            400,
        )
    return _idempotent_design_response(
        f"input:{portal_id}",
        body,
        lambda: jsonify(
            _design_sessions().send_input(
                portal_id,
                prompt=prompt,
                delivery=body.get("delivery", "queue"),
            )
        ),
    )


@app.post("/api/flags/<session_id>/steer")
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
    if len(prompt) > MAX_DESIGN_PROMPT_CHARS:
        return jsonify({"error": f"prompt must be at most {MAX_DESIGN_PROMPT_CHARS} characters"}), 400

    def steer() -> tuple[Response, int] | Response:
        """Recheck ownership immediately before the OpenCode side effect."""
        _flag, denied = _authorize_supervisor_action(session_id, cell_id)
        if denied:
            return denied
        _opencode_client().send_input(session_id, prompt.strip(), delivery="steer")
        return jsonify({"action": "steer", "admitted": True, "session_id": session_id})

    return _idempotent_design_response(f"supervisor-steer:{session_id}", body, steer)


@app.post("/api/flags/<session_id>/interrupt")
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
        _flag, denied = _authorize_supervisor_action(session_id, cell_id)
        if denied:
            return denied
        _opencode_client().interrupt(session_id)
        return jsonify({"action": "interrupt", "accepted": True, "session_id": session_id})

    return _idempotent_design_response(f"supervisor-interrupt:{session_id}", body, interrupt)


@app.post("/api/design-sessions/<portal_id>/interrupt")
def api_design_session_interrupt(portal_id) -> Response:
    """Interrupt native work without changing the browser attachment."""
    _body, failure = _design_mutation_body()
    if failure:
        return failure
    assert _body is not None
    return _idempotent_design_response(
        f"interrupt:{portal_id}",
        _body,
        lambda: jsonify(_design_sessions().interrupt(portal_id)),
    )


@app.post("/api/design-sessions/<portal_id>/save")
def api_design_session_save(portal_id) -> Response:
    """Atomically save a revalidated draft under experiments/specs."""
    body, failure = _design_mutation_body()
    if failure:
        return failure
    assert body is not None
    if "overwrite" in body and not isinstance(body["overwrite"], bool):
        return jsonify({"error": "overwrite must be a boolean"}), 400
    def save():
        result = _design_sessions().save(
            portal_id,
            filename=body.get("filename", "") if isinstance(body.get("filename", ""), str) else "",
            overwrite=body.get("overwrite") is True,
        )
        return jsonify(result), 409 if result.get("conflict") else 200

    return _idempotent_design_response(f"save:{portal_id}", body, save)


@app.post("/api/design-sessions/<portal_id>/run")
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
        result = _design_sessions().run_workflow(
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


@app.get("/api/claude-agents")
def api_claude_agents() -> Response:
    """Read the supervisor-maintained roster; never calls the ``claude`` CLI.

    A missing or unparseable roster is a rendering concern, not a hard
    failure: the fleet section shows a "supervisor not running" state while
    the rest of the Control Room stays unaffected. ``workdirs`` is an
    additive label list (mirroring ``/api/design-sessions``) so the start
    form never needs a raw filesystem path from the browser.
    """
    workdirs = [{"key": key, "label": path.name or key} for key, path in _claude_agent_workdirs().items()]
    try:
        raw = _redis().get(ROSTER_KEY)
        agents = json.loads(raw) if raw else None
        if not isinstance(agents, list):
            raise ValueError("roster unavailable")
    except Exception:
        return jsonify({"error": "supervisor_unavailable", "agents": [], "workdirs": workdirs}), 200
    return jsonify({"agents": agents, "workdirs": workdirs})


@app.get("/api/claude-agents/<session_id>/logs")
def api_claude_agent_logs(session_id) -> Response:
    """One-shot, best-effort log tail for external sessions (owned sessions use SSE)."""
    if not SESSION_ID_PATTERN.fullmatch(session_id):
        return jsonify({"error": "invalid session id"}), 400
    try:
        logs = _claude_agents().get_logs(session_id)
    except ClaudeAgentsError as error:
        return jsonify({"error": str(error), "code": error.code}), 502
    encoded = logs.encode("utf-8", errors="replace")
    truncated = len(encoded) > MAX_CLAUDE_AGENT_LOG_BYTES
    body = encoded[:MAX_CLAUDE_AGENT_LOG_BYTES].decode("utf-8", errors="replace")
    response = make_response(body)
    response.headers["Content-Type"] = "text/plain; charset=utf-8"
    response.headers["X-Claude-Agent-Log-Truncated"] = "true" if truncated else "false"
    response.headers["X-Claude-Agent-Log-Note"] = "one-shot best-effort tail, not a live stream"
    return response


@app.get("/api/claude-agents/daemon")
def api_claude_agents_daemon() -> Response:
    """Read-only ``claude daemon status``; no control affordance is attached here."""
    try:
        status = _claude_agents().daemon_status()
    except ClaudeAgentsError as error:
        return jsonify({"running": False, "error": str(error), "code": error.code}), 200
    return jsonify(status)


@app.post("/api/claude-agents")
def api_start_claude_agent() -> Response:
    """Start one ``claude --bg`` session in an approved workdir and record ownership."""
    body, failure = _claude_agent_mutation_body()
    if failure:
        return failure
    assert body is not None

    workdir_key = body.get("workdir", "")
    if not isinstance(workdir_key, str):
        return jsonify({"error": "workdir must be a string"}), 400
    workdir = _claude_agent_workdirs().get(workdir_key)
    if workdir is None:
        return jsonify({"error": "workdir is not approved"}), 400

    task = body.get("task", "")
    if not isinstance(task, str) or not task.strip() or len(task) > MAX_CLAUDE_AGENT_TASK_CHARS:
        return (
            jsonify({"error": f"task is required and must be at most {MAX_CLAUDE_AGENT_TASK_CHARS} characters"}),
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
        and (advisor in CLAUDE_AGENT_ADVISORS or CLAUDE_AGENT_ADVISOR_ID_PATTERN.fullmatch(advisor))
    ):
        return jsonify({"error": "advisor must be fable, opus, sonnet, or a full model id"}), 400

    def start():
        result = _claude_agents().start_agent(
            task.strip(),
            cwd=str(workdir),
            model=resolved_model,
            advisor=advisor,
            skip_permissions=True,
        )
        session_id = result.get("id")
        if not isinstance(session_id, str) or not SESSION_ID_PATTERN.fullmatch(session_id):
            raise ClaudeAgentsError("claude --bg returned an unusable session id", code="malformed_json")
        _redis().sadd(OWNED_SESSIONS_KEY, session_id)
        return jsonify({"ok": True, "id": session_id}), 201

    return _idempotent_claude_agent_response("start", body, start)


@app.post("/api/claude-agents/<session_id>/stop")
def api_stop_claude_agent(session_id) -> Response:
    """``claude stop`` an owned session. The process ends; Respawn resumes it."""
    body, failure = _claude_agent_mutation_body()
    if failure:
        return failure
    assert body is not None
    rejection = _require_owned_claude_agent(_redis(), session_id)
    if rejection:
        return rejection

    def stop():
        result = _claude_agents().stop_agent(session_id)
        return jsonify({
            "ok": True,
            "id": session_id,
            "note": "process ended; the conversation is preserved and can be resumed with Respawn",
            "result": result,
        })

    return _idempotent_claude_agent_response(f"stop:{session_id}", body, stop)


@app.post("/api/claude-agents/<session_id>/respawn")
def api_respawn_claude_agent(session_id) -> Response:
    """``claude respawn`` an owned session with its conversation intact."""
    body, failure = _claude_agent_mutation_body()
    if failure:
        return failure
    assert body is not None
    rejection = _require_owned_claude_agent(_redis(), session_id)
    if rejection:
        return rejection

    def respawn():
        result = _claude_agents().respawn_agent(session_id)
        return jsonify({"ok": True, "id": session_id, "result": result})

    return _idempotent_claude_agent_response(f"respawn:{session_id}", body, respawn)


@app.post("/api/claude-agents/<session_id>/rm")
def api_rm_claude_agent(session_id) -> Response:
    """``claude rm`` an owned session; the transcript remains on disk."""
    body, failure = _claude_agent_mutation_body()
    if failure:
        return failure
    assert body is not None
    redis_client = _redis()
    rejection = _require_owned_claude_agent(redis_client, session_id)
    if rejection:
        return rejection

    def rm():
        result = _claude_agents().rm_agent(session_id)
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


@app.post("/api/claude-agents/<session_id>/steer")
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
    redis_client = _redis()

    prompt = body.get("prompt", "")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_CLAUDE_AGENT_TASK_CHARS:
        return (
            jsonify({"error": f"prompt is required and must be at most {MAX_CLAUDE_AGENT_TASK_CHARS} characters"}),
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
        and (advisor in CLAUDE_AGENT_ADVISORS or CLAUDE_AGENT_ADVISOR_ID_PATTERN.fullmatch(advisor))
    ):
        return jsonify({"error": "advisor must be fable, opus, sonnet, or a full model id"}), 400

    def steer():
        # Ownership is checked inside the idempotency action (not before it)
        # because a successful steer remaps the owned id — a retried request
        # must replay the cached success rather than 403 on the now-stale id.
        rejection = _require_owned_claude_agent(redis_client, session_id)
        if rejection:
            return rejection
        result = _claude_agents().steer_agent(
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


@app.post("/api/claude-agents/daemon/stop")
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
        result = _claude_agents().daemon_stop(keep_workers=keep_workers)
        return jsonify({"ok": True, "keep_workers": keep_workers, "result": result})

    return _idempotent_claude_agent_response("daemon-stop", body, stop_daemon)


@app.get("/")
def index() -> Response:
    return app.send_static_file("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("FINOPS_PORT", "8000"))
    # Secure default: loopback only. Bind wider via FINOPS_HOST=0.0.0.0 explicitly.
    host = os.environ.get("FINOPS_HOST", "127.0.0.1")
    app.run(host=host, port=port, threaded=True)
