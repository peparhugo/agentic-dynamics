"""Analytic read-model routes (step 6, P3/P4/P5/P6): the room's quality/value/arm surfaces.

``GET /api/quality`` — model quality: Grit (the one formal definition), first-pass,
narration (answer/explanation split), coverage. ``GET /api/stories/<name>/arc`` — the
story session arc (snowball/velocity/β). ``GET /api/value`` — observed-only accepted
outcomes + cost per accepted outcome. ``GET /api/arms/compare`` — the compare/adapt arm
ranking over real executed phases.

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
