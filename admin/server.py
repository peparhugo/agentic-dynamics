"""Dynamic-code admin portal backend.

Serves the admin dashboard and exposes live experiment telemetry over SSE.

Endpoints:
    GET  /api/matrix           — queue/status matrix (Redis hash + queue)
    GET  /api/status           — SSE stream of status transitions
    GET  /api/events/<cell_id> — SSE stream of a cell's events (replay + live)
    GET  /api/routing          — routing board (Phase 7; stub for now)
    POST /api/experiments      — enqueue/clear the experiment queue
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
import subprocess
import sys
import time
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from flask import Flask, Response, jsonify, make_response, request

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

try:  # Package imports under pytest and WSGI.
    from admin.design_sessions import DESIGN_SESSIONS_KEY, DesignSessionManager
    from admin.opencode_client import OpenCodeClient, OpenCodeError
except ModuleNotFoundError:  # pragma: no cover - documented ``python admin/server.py`` launch
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
IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60
ROOT = Path(__file__).resolve().parent.parent
SUPERVISOR_FLAGS_FILE = ROOT / "experiments" / "results" / "supervisor" / "flags.jsonl"
SUPERVISOR_FILE_TAIL_BYTES = 512 * 1024
SUPERVISOR_ACTIVE_WINDOW_SECONDS = int(os.environ.get("SUPERVISOR_ACTIVE_WINDOW", "900"))

app = Flask(__name__, static_folder="static", static_url_path="/static")
_design_manager: DesignSessionManager | None = None


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


@app.get("/")
def index() -> Response:
    return app.send_static_file("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("FINOPS_PORT", "8000"))
    # Secure default: loopback only. Bind wider via FINOPS_HOST=0.0.0.0 explicitly.
    host = os.environ.get("FINOPS_HOST", "127.0.0.1")
    app.run(host=host, port=port, threaded=True)
