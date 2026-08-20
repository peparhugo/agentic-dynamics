"""Telemetry + experiment-control routes (matrix/status/events/routing/experiments/reinterleave).

Extracted from ``server.py`` (refactor-repair Debt-1). Read-only telemetry plus the two
experiment-queue mutations; all shared state (``server._redis``, Redis keys, ``EVENT_LOG_MAX``)
is read through ``server.*`` so the tests' monkeypatches keep working.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time

from flask import Response, jsonify

from agentic_dynamics.control.live import (
    EVENT_CHANNEL_PREFIX,
    EVENT_LOG_PREFIX,
    PHASE_KEY,
    STATUS_CHANNEL,
    STATUS_KEY,
)
from agentic_dynamics.control.pipeline_status import stage_summary
from agentic_dynamics.control.queue_reinterleave import (
    provider_summary,
    read_queue,
    reinterleave_cells,
    write_queue,
)
from agentic_dynamics.control.routing import compute_routing
from apps.control_room import server
from apps.control_room.services.design_sessions import DESIGN_SESSIONS_KEY
from apps.control_room.services.mutations import _design_mutation_body, _idempotent_design_response
from apps.control_room.services.telemetry import _parse_phases, _retained_telemetry, _sse


def api_matrix() -> Response:
    """Return the legacy fleet matrix plus the three-stage pipeline view."""
    try:
        r = server._redis()
        execute = stage_summary(r, server.QUEUE_KEY, STATUS_KEY, server.RESULTS_KEY)
        analyze = stage_summary(r, server.ANALYSIS_QUEUE_KEY, server.ANALYSIS_STATUS_KEY)
        review = stage_summary(r, server.REVIEW_QUEUE_KEY, server.REVIEW_STATUS_KEY)
        phase_payloads = r.hgetall(PHASE_KEY)
    except Exception:
        return jsonify({"error": "redis_unavailable", "cells": {}}), 503

    # Keep the legacy flat fields (``total``, ``queued``, ``cells``, …) derived
    # from the execute stage so existing clients keep working; the three-stage
    # ``stages`` block and the ``phases`` block are purely additive.
    response = {
        "total": execute["total"],
        "remaining_in_queue": execute["remaining_in_queue"],
        "queued": execute["queued"],
        "running": execute["running"],
        "done": execute["done"],
        "failed": execute["failed"],
        "timeout": execute["timeout"],
        "completed": execute["completed"],
        "results_saved": execute["results_saved"],
        "cells": execute["cells"],
        "phases": _parse_phases(phase_payloads),
    }
    response["stages"] = {"execute": execute, "analyze": analyze, "review": review}
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
    response["telemetry"] = _retained_telemetry(r, [*execute["cells"], *design_stream_ids])
    return jsonify(response)

def api_status() -> Response:
    """Stream status transitions while preserving the existing SSE payload."""
    def gen():
        r = server._redis()
        pubsub = r.pubsub()
        pubsub.subscribe(STATUS_CHANNEL)
        last_beat = time.time()
        try:
            while True:
                msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg:
                    yield f"data: {msg['data']}\n\n"
                elif time.time() - last_beat >= server.HEARTBEAT_SECONDS:
                    yield ": ping\n\n"
                    last_beat = time.time()
        finally:
            try:
                pubsub.unsubscribe(STATUS_CHANNEL)
                pubsub.close()
            except Exception:
                pass

    return _sse(gen())

def api_events(cell_id) -> Response:
    """Replay retained cell events, mark the boundary, then stream live data.

    The named boundary is additive: clients listening through ``onmessage``
    continue to receive the same raw event frames, while Control Room clients
    can exclude replay from the rolling burn-rate window.
    """
    log_key = f"{EVENT_LOG_PREFIX}{cell_id}"
    channel = f"{EVENT_CHANNEL_PREFIX}{cell_id}"

    def gen():
        r = server._redis()
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
                elif time.time() - last_beat >= server.HEARTBEAT_SECONDS:
                    yield ": ping\n\n"
                    last_beat = time.time()
        finally:
            try:
                pubsub.unsubscribe(channel)
                pubsub.close()
            except Exception:
                pass

    return _sse(gen())

def api_routing() -> Response:
    summary_path = server.ROOT / "experiments" / "results" / "_results_summary.json"
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

def api_experiments() -> Response:
    """Enqueue or clear the experiment queue — the most expensive mutation.

    This route spawns ``scripts/enqueue.py`` (real inference cost), so it joins
    every other actuation route under ``_design_mutation_body``'s loopback +
    same-origin + JSON + size-cap + Idempotency-Key boundary (review F1) instead
    of the former bare ``request.get_json`` + action check, which was the only
    mutation surface without the trust gate.
    """
    body, failure = _design_mutation_body()
    if failure:
        return failure
    assert body is not None
    action = body.get("action")
    if action not in ("enqueue", "clear"):
        return jsonify({"error": f"unknown action {action!r}"}), 400

    def enqueue():
        cmd = [sys.executable, "scripts/enqueue.py"]
        if action == "clear":
            cmd.append("--clear")
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=server.ROOT,
        )
        return jsonify({"ok": proc.returncode == 0, "output": (proc.stdout or proc.stderr).strip()})

    return _idempotent_design_response("experiments", body, enqueue)

def api_queue_reinterleave() -> Response:
    """Re-interleave ``story_jobs`` round-robin across providers.

    Queue-level control (unlike the flagged session interrupts): it needs no
    supervisor flag because it reorders *future* picks without touching any
    running session. The reorder logic is shared with the CLI via
    ``instrument.queue_reinterleave`` so the two surfaces can never drift.
    """
    body, failure = _design_mutation_body()
    if failure:
        return failure
    assert body is not None

    def reinterleave() -> tuple[Response, int]:
        r = server._redis()
        before = read_queue(r)
        after = reinterleave_cells(before)
        write_queue(r, after)
        return jsonify({
            "ok": True,
            "count": len(before),
            "before": provider_summary(before),
            "after": provider_summary(after),
        }), 200

    return _idempotent_design_response("queue-reinterleave", body, reinterleave)

def register(app):
    """Register this module's routes on the Flask app (server.py composition root)."""
    app.get("/api/matrix")(api_matrix)
    app.get("/api/status")(api_status)
    app.get("/api/events/<cell_id>")(api_events)
    app.get("/api/routing")(api_routing)
    app.post("/api/experiments")(api_experiments)
    app.post("/api/queue/reinterleave")(api_queue_reinterleave)
