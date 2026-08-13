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
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from flask import Flask, Response, jsonify, request

from instrument.live import (
    EVENT_CHANNEL_PREFIX,
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
    return Response(
        generator,
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.get("/api/matrix")
def api_matrix():
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
    return jsonify(
        {
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
    )


@app.get("/api/status")
def api_status():
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
    log_key = f"{EVENT_LOG_PREFIX}{cell_id}"
    channel = f"{EVENT_CHANNEL_PREFIX}{cell_id}"

    def gen():
        r = _redis()
        try:
            history = r.lrange(log_key, 0, -1)
            for payload in reversed(history):
                yield f"data: {payload}\n\n"
        except Exception:
            pass

        pubsub = r.pubsub()
        pubsub.subscribe(channel)
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
