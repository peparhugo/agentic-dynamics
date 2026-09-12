"""Analytic read-model routes (steps 6–7): quality/value/arms + queue-SLA/escalation/batch/energy.

``GET /api/quality`` — model quality: Grit (the one formal definition), first-pass,
narration (answer/explanation split), coverage. ``GET /api/stories/<name>/arc`` — the
story session arc (snowball/velocity/β). ``GET /api/value`` — observed-only accepted
outcomes + cost per accepted outcome. ``GET /api/arms/compare`` — the compare/adapt arm
ranking over real executed phases.

Step 7 (rule 4/6/8/9 surfaces, measured where owned): ``GET /api/queue/sla`` — queue depth
+ measured burn/completion trace + the 2× depth rule (writer-less timings named unknown);
``GET /api/escalations`` — recorded cascade events only, E_x labeled; ``GET /api/batch`` —
not-measurable until a ``batch_mode`` marker exists; ``GET /api/energy`` — the EPM/energy
scenario sources ([X]/[C]) + the named measured-energy gap.

Read-only by construction: all handlers are GET and serve the injected services' pure
projections. Absence stays absent (a missing corpus is NAMED in ``degraded``, an unknown
story is a 404); an unreadable input never becomes a zero or a 500.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Response, jsonify, request

if TYPE_CHECKING:  # pragma: no cover - import only for static typing
    from apps.control_room.services.context import ControlRoomServices

#: The injected application context, bound by ``register()`` before any request is served.
_services: ControlRoomServices | None = None


def register(app, services: ControlRoomServices) -> None:
    """Register this module's routes on the Flask app, receiving the application context."""
    global _services
    _services = services
    app.get("/api/quality")(api_quality)
    app.get("/api/stories/<name>/arc")(api_story_arc)
    app.get("/api/value")(api_value)
    app.get("/api/arms/compare")(api_arms_compare)
    app.get("/api/queue/sla")(api_queue_sla)
    app.get("/api/escalations")(api_escalations)
    app.get("/api/batch")(api_batch)
    app.get("/api/energy")(api_energy)


def api_quality() -> Response:
    """P3: the model-quality projection (Grit / first-pass / narration / coverage)."""
    payload, status = _services.quality()
    return jsonify(payload), status


def api_story_arc(name: str) -> Response:
    """P4: the named story's session arc; 404 for an unknown name, named degradation on outage."""
    payload, status = _services.story_arc(name)
    return jsonify(payload), status


def api_value() -> Response:
    """P5: observed-only value rows; optional exact-match ``run`` / ``arm`` filters."""
    payload, status = _services.run_value(
        run=request.args.get("run") or None,
        arm=request.args.get("arm") or None,
    )
    return jsonify(payload), status


def api_arms_compare() -> Response:
    """P6: the arm comparison; optional ``spec`` filter (a named empty state, never an error)."""
    payload, status = _services.arm_comparison(spec=request.args.get("spec") or None)
    return jsonify(payload), status


def api_queue_sla() -> Response:
    """P8: queue depth + measured burn/trace + the 2× depth rule; ``window=<hours>``."""
    window = request.args.get("window", type=int) or 72
    payload, status = _services.sla_queue(window_h=max(1, min(window, 720)))
    return jsonify(payload), status


def api_escalations() -> Response:
    """P9: the cascade surface; optional ``spec`` filter, no invented events."""
    payload, status = _services.escalation(spec=request.args.get("spec") or None)
    return jsonify(payload), status


def api_batch() -> Response:
    """P10: the batch surface (not-measurable + the labeled rule-6 scenario while unowned)."""
    payload, status = _services.batch()
    return jsonify(payload), status


def api_energy() -> Response:
    """Rule 4: the EPM/energy scenario surface (published sources, labeled)."""
    payload, status = _services.energy()
    return jsonify(payload), status
