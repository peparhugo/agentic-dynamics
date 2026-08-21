"""Static shell route (``GET /``).

Extracted from ``server.py`` (refactor-repair Debt-1). Serves the vanilla-JS dashboard from
``apps/control_room/static``. The handler closes over the ``app`` passed to ``register`` rather
than importing the server module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Response

if TYPE_CHECKING:  # pragma: no cover - import only for static typing
    from flask import Flask

    from apps.control_room.services.context import ControlRoomServices


def register(app: Flask, services: ControlRoomServices) -> None:
    """Register the static shell route on the Flask app (server.py composition root)."""

    def index() -> Response:
        return app.send_static_file("index.html")

    app.get("/")(index)
