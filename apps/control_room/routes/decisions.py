"""P11 ``decision_ledger`` route (d3 §5 P11) — the read-only decision ledger.

``GET /api/decisions?category=<one_way_door|cap_raise>`` serves the injected services' decision
projection: recorded decisions (newest first) plus the P0 acts whose decision record is absent,
named in ``missing``. The route is a thin shell — it parses the optional exact-match ``category``
filter and never touches the filesystem or the control DB itself.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Response, jsonify, request

if TYPE_CHECKING:  # pragma: no cover - import only for static typing
    from apps.control_room.services.context import ControlRoomServices

#: The injected application context, bound by ``register()`` before any request is served.
_services: ControlRoomServices | None = None


def register(app, services: ControlRoomServices) -> None:
    """Register this module's route on the Flask app, receiving the application context."""
    global _services
    _services = services
    app.get("/api/decisions")(api_decisions)


def api_decisions() -> Response:
    """P11: recorded decisions + missing-record acts; optional exact-match ``category``."""
    payload, status = _services.decisions(category=request.args.get("category") or None)
    return jsonify(payload), status
