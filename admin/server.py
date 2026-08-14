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
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from flask import Flask, Response, jsonify, request

from instrument.live import (
    EVENT_CHANNEL_PREFIX,
    EVENT_LOG_MAX,
    EVENT_LOG_PREFIX,
    STATUS_CHANNEL,
    STATUS_KEY,
)
from instrument.routing import compute_routing

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))
QUEUE_KEY = "story_jobs"
RESULTS_KEY = "story_results"
HEARTBEAT_SECONDS = 15

app = Flask(__name__, static_folder="static", static_url_path="/static")


def _redis():
    import redis

    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)


def _sse(generator):
    """Return a response configured for an unbuffered SSE connection."""
    return Response(
        generator,
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


def _reported_number(value):
    """Return valid reported telemetry as a float, or ``None``.

    Telemetry is observational rather than billing data, so malformed values
    must be ignored instead of coerced. In particular, booleans are excluded
    even though Python treats them as integers.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number >= 0 else None


def _event_timestamp(event, part):
    """Return a supplied event timestamp without inventing server time."""
    for container in (event, part):
        for key in ("timestamp", "time", "created_at", "createdAt"):
            value = container.get(key)
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                return value
    return None


def _identity_number(value):
    """Format a telemetry number identically to the browser identity helper."""
    if value is None:
        return ""
    return f"{value:.12f}".rstrip("0").rstrip(".") or "0"


def _step_sample(payload):
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


def _retained_telemetry(redis_client, cell_ids):
    """Build an additive retained-window snapshot from existing event logs.

    Each log is independently optional. A transient per-cell read failure does
    not erase the baseline matrix response; ``available`` records that the
    telemetry extension is incomplete while the legacy status data remains
    usable.
    """
    cells = {}
    total_cost = 0.0
    input_tokens = 0.0
    output_tokens = 0.0
    cost_samples = input_samples = output_samples = 0
    available = True

    for cell_id in cell_ids:
        try:
            history = redis_client.lrange(f"{EVENT_LOG_PREFIX}{cell_id}", 0, -1)
        except Exception:
            history = []
            available = False

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
        cell_inputs = [sample["input_tokens"] for sample in samples if sample["input_tokens"] is not None]
        cell_outputs = [sample["output_tokens"] for sample in samples if sample["output_tokens"] is not None]
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
        "cells": cells,
    }


@app.get("/api/matrix")
def api_matrix():
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
    response["telemetry"] = _retained_telemetry(r, statuses)
    return jsonify(response)


@app.get("/api/status")
def api_status():
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


@app.get("/api/events/<cell_id>")
def api_events(cell_id):
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
def api_routing():
    summary_path = (
        Path(__file__).resolve().parent.parent / "experiments" / "results" / "_results_summary.json"
    )
    try:
        data = json.loads(summary_path.read_text())
        entries = data.get("entries", [])
    except (OSError, json.JSONDecodeError):
        return jsonify(
            {"_meta": {"tasks_analyzed": 0}, "per_task": [], "strategies": {}, "note": "no results summary yet"}
        )
    return jsonify(compute_routing(entries))


@app.post("/api/experiments")
def api_experiments():
    body = request.get_json(silent=True) or {}
    action = body.get("action", "enqueue")
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


@app.get("/")
def index():
    return app.send_static_file("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("FINOPS_PORT", "8000"))
    app.run(host="0.0.0.0", port=port, threaded=True)
