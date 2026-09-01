"""Telemetry + experiment-control routes (matrix/status/events/routing/experiments/reinterleave).

Extracted from ``server.py`` (refactor-repair Debt-1). Read-only telemetry plus the two
experiment-queue mutations; all shared state (``server._redis``, Redis keys, ``EVENT_LOG_MAX``)
is read through ``server.*`` so the tests' monkeypatches keep working.

``api_matrix``'s review stage is read through ``_services.review_stage_source`` — the injected
review authority. This module deliberately does NOT import a concrete review summariser: which
authority answers for the review population (the files on disk, a Redis queue, a test double) is
a composition-root decision, not a route-level one.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time

from flask import Response, jsonify, request

from agentic_dynamics.control import projection_watermarks
from agentic_dynamics.control.admission import admission_board
from agentic_dynamics.control.lease_registry import (
    AdmissionError,
    LeaseKind,
    LeaseRegistry,
    LeaseScope,
    ScopeKind,
)
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
from apps.control_room.services.context import ControlRoomServices
from apps.control_room.services.design_sessions import DESIGN_SESSIONS_KEY
from apps.control_room.services.mutations import _design_mutation_body, _idempotent_design_response
from apps.control_room.services.subscription_usage import (
    CACHE_TTL_SECONDS,
    MIN_REFRESH_INTERVAL_SECONDS,
    UsageUnavailableError,
    history_summary,
    load_or_refresh,
)
from apps.control_room.services.telemetry import (
    _parse_phases,
    _retained_telemetry,
    _sse,
    _tail_stamps,
)

#: The injected application context, bound by ``register()`` before any request is served.
_services: ControlRoomServices | None = None


def api_matrix() -> Response:
    """Return the legacy fleet matrix plus the three-stage pipeline view."""
    try:
        r = _services.redis()
        execute = stage_summary(r, _services.queue_key, STATUS_KEY, _services.results_key)
        analyze = stage_summary(r, _services.analysis_queue_key, _services.analysis_status_key)
        # The review population comes from the INJECTED authority, never a hard-wired import:
        # the composition root binds the file-derived source in production (see
        # ControlRoomServices.review_stage_source), and a test binds its own to isolate this
        # route from the filesystem entirely.
        review = _services.review_stage_source(r)
        phase_payloads = r.hgetall(PHASE_KEY)
    except Exception:
        return jsonify({"error": "redis_unavailable", "cells": {}}), 503

    # Keep the legacy flat fields (``total``, ``queued``, ``cells``, …) derived
    # from the execute stage so existing clients keep working; the three-stage
    # ``stages`` block and the ``phases`` block are purely additive.
    # The live dimension of the phases board: each phase entry gains {live, last_phase_ts,
    # age_seconds}. `_tail_stamps` reads the newest retained event per phase cell (one pipeline,
    # best-effort) so a phase without its own published-at stamp can still be dated by the
    # runner's telemetry — and a run with neither renders age-unknown, never mislabeled.
    tails = _tail_stamps(r, list(phase_payloads))
    phases = _parse_phases(phase_payloads, tails=tails)
    # Runner-truth liveness (live_board follow-up, 2026-09-01): a cell whose status is
    # "running" but whose phase liveness says DEFINITIVELY historical is an ENDED run with a
    # stale status — a killed/interrupted runner never publishes its terminal status, so
    # story_status keeps "running" forever. The window, not the publishing process, decides.
    # Age-UNKNOWN phases are never flipped (the "never mislabeled" rule — no stamps means we
    # do not know, so the legacy status stands); only a phase with a real age past the window
    # re-presents the cell as "ended" (outcome unknown-but-over) rather than falsely live.
    stale_running = {
        cid
        for cid, p in phases.items()
        if not p.get("live") and isinstance(p.get("age_seconds"), (int, float))
    }
    cells = dict(execute["cells"])
    stale_running_flipped = 0
    for cid, status in cells.items():
        if status == "running" and cid in stale_running:
            cells[cid] = "ended"
            stale_running_flipped += 1
    running = execute["running"] - stale_running_flipped
    response = {
        "total": execute["total"],
        "remaining_in_queue": execute["remaining_in_queue"],
        "queued": execute["queued"],
        "running": running,
        "done": execute["done"],
        "failed": execute["failed"],
        "timeout": execute["timeout"],
        "completed": execute["completed"],
        "results_saved": execute["results_saved"],
        "cells": cells,
        "phases": phases,
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
    # Knowledge projection health, additively (control_db_publication p3). The board answers
    # "what is executing"; without this it could not answer "did the results get projected",
    # and an operator reading a green board had no way to know the registry was 400 events
    # behind. Read through the control database, not Redis, so it survives the 503 above being
    # the wrong answer for this block — and best-effort, because a missing control database
    # must degrade the projections panel, never the fleet matrix.
    response["projections"] = projection_watermarks.read_report() or []
    return jsonify(response)


def api_projections() -> Response:
    """Return every knowledge projection's watermark — the operator's projection surface.

    One row per consumer group of the knowledge event stream (registry / chroma / neo4j /
    ledger), each carrying how far it has confirmed, how far behind the stream head it is, when
    it last reported, and its health verdict.

    Three response shapes, deliberately distinct because they are three different situations
    and only one of them is safe:

    * **200 with rows** — the control database answered. A projection that has never reported
      still appears, as ``health: "unknown"`` / ``reported: false``: "nobody has ever run this
      projector" is a fact an operator can act on, and omitting the row would render it as
      indistinguishable from a projection that does not exist.
    * **503 ``control_db_unavailable``** — there is no control database to read. NOT an empty
      list: "no control plane" and "a control plane reporting nothing" are opposite answers,
      and collapsing them is exactly the false-authority failure the control db was built to
      remove.
    * **500** — never; failures here are one of the two above.
    """
    report = projection_watermarks.read_report()
    if report is None:
        return jsonify(
            {
                "error": "control_db_unavailable",
                "detail": "no control database — has the orchestrator run?",
                "projections": [],
            }
        ), 503
    unhealthy = [p for p in report if p["health"] != "current"]
    return jsonify(
        {
            "projections": report,
            # The compact block the p4 control packet carries, rendered here too so the portal
            # and the packet can never disagree about a number they both publish.
            "projection_lag": {p["projection"]: p["lag_events"] for p in report},
            "unhealthy": [p["projection"] for p in unhealthy],
            "stale_after_seconds": projection_watermarks.stale_after_seconds(),
        }
    )


def api_status() -> Response:
    """Stream status transitions while preserving the existing SSE payload."""

    def gen():
        r = _services.redis()
        pubsub = r.pubsub()
        pubsub.subscribe(STATUS_CHANNEL)
        last_beat = time.time()
        try:
            while True:
                msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg:
                    yield f"data: {msg['data']}\n\n"
                elif time.time() - last_beat >= _services.heartbeat_seconds:
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
        r = _services.redis()
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
                elif time.time() - last_beat >= _services.heartbeat_seconds:
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
    summary_path = _services.root / "experiments" / "results" / "_results_summary.json"
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

#: The lease counters the admission board reports beside the provider usage snapshot. Fixed
#: rather than discovered, because a dashboard needs a stable set of rows: these are the scopes
#: the wired entry points actually reserve against (``scripts/worker.py`` takes fleet +
#: provider, ``scripts/analysis_worker.py`` takes ``fleet:analysis``, ``scripts/enqueue.py``
#: takes the provider budget). Campaign scopes are per-spec and therefore not enumerable here;
#: they are visible through ``control.admission.admission_board`` directly.
ADMISSION_BOARD_SCOPES: tuple[tuple[LeaseKind, LeaseScope], ...] = (
    (LeaseKind.CONCURRENCY, LeaseScope(ScopeKind.FLEET, "default")),
    (LeaseKind.CONCURRENCY, LeaseScope(ScopeKind.FLEET, "analysis")),
    (LeaseKind.BUDGET, LeaseScope(ScopeKind.PROVIDER, "deepseek")),
    (LeaseKind.BUDGET, LeaseScope(ScopeKind.PROVIDER, "anthropic")),
    (LeaseKind.BUDGET, LeaseScope(ScopeKind.PROVIDER, "openai")),
    (LeaseKind.CONCURRENCY, LeaseScope(ScopeKind.PROVIDER, "deepseek")),
    (LeaseKind.CONCURRENCY, LeaseScope(ScopeKind.PROVIDER, "anthropic")),
    (LeaseKind.CONCURRENCY, LeaseScope(ScopeKind.PROVIDER, "openai")),
)

def _admission_block() -> dict:
    """The live lease state for the admission board, or a stated unavailable reason.

    Best-effort *for the dashboard only*. This is the one place in the admission layer where a
    registry failure does NOT refuse: nothing is being admitted here, the route is read-only,
    and a downed lease registry must not take the Control Room's usage page with it. The
    distinction is the whole "telemetry degrades, admission does not" rule — degrading here is
    safe precisely because no decision follows.
    """
    try:
        return admission_board(LeaseRegistry.from_env(), ADMISSION_BOARD_SCOPES)
    except AdmissionError as exc:
        return {"available": False, "error": str(exc)}


def api_subscription_usage() -> Response:
    """Serve provider subscription usage + the admission board through the polite cache.

    Two halves of one question, deliberately on one route (``admission_leases`` p2 makes this
    "the admission telemetry surface"):

    * ``providers`` / ``deepseek_platform`` — what the providers say has been *consumed*
      (15-min TTL cache; ``?refresh=1`` refetches, never more than once per
      ``MIN_REFRESH_INTERVAL_SECONDS``, because dashboard polls must not hammer the OAuth
      endpoints).
    * ``admission`` — what the leases say has been *reserved but not yet spent*.

    The second is exactly the number the first cannot show, and it is what the caps are sized
    against, so separating them onto two endpoints would leave an operator correlating by hand
    the two figures that only mean something together.
    """
    force = request.args.get("refresh") == "1"
    try:
        payload, served_from, age = load_or_refresh(_services.redis, _services.root, force=force)
    except UsageUnavailableError as error:
        return jsonify(
            {
                "schema": "subscription-usage/v3",
                "error": "subscription_usage_unavailable",
                "state": error.state,
                "cache": {
                    "age_seconds": error.age_seconds,
                    "ttl_seconds": CACHE_TTL_SECONDS,
                    "min_refresh_seconds": MIN_REFRESH_INTERVAL_SECONDS,
                },
            }
        ), 503

    refetched = served_from == "live"
    return jsonify(
        {
            "schema": payload.get("schema", "subscription-usage/v3"),
            "providers": payload["providers"],
            "deepseek": payload.get("deepseek"),
            "deepseek_platform": payload.get("deepseek_platform"),
            "fetched_at": payload.get("fetched_at"),
            "stale": bool(payload.get("stale", False)) or served_from == "disk-cache",
            "served_from": served_from,
            "refetched_now": refetched,
            "refresh_error": payload.get("refresh_error"),
            "history": history_summary(_services.root),
            "admission": _admission_block(),
            "cache": {
                "age_seconds": age,
                "ttl_seconds": CACHE_TTL_SECONDS,
                "min_refresh_seconds": MIN_REFRESH_INTERVAL_SECONDS,
            },
        }
    )

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
            cwd=_services.root,
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
        r = _services.redis()
        before = read_queue(r)
        after = reinterleave_cells(before)
        write_queue(r, after)
        return jsonify(
            {
                "ok": True,
                "count": len(before),
                "before": provider_summary(before),
                "after": provider_summary(after),
            }
        ), 200

    return _idempotent_design_response("queue-reinterleave", body, reinterleave)


def register(app, services: ControlRoomServices) -> None:
    """Register this module's routes on the Flask app, receiving the application context."""
    global _services
    _services = services
    app.get("/api/matrix")(api_matrix)
    app.get("/api/status")(api_status)
    app.get("/api/projections")(api_projections)
    app.get("/api/events/<cell_id>")(api_events)
    app.get("/api/routing")(api_routing)
    app.get("/api/subscription-usage")(api_subscription_usage)
    app.post("/api/experiments")(api_experiments)
    app.post("/api/queue/reinterleave")(api_queue_reinterleave)
