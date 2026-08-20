"""Static shell route (``GET /``).

Extracted from ``server.py`` (refactor-repair Debt-1). Serves the vanilla-JS dashboard from
``apps/control_room/static``.
"""
from __future__ import annotations

from flask import Response

from apps.control_room import server


def index() -> Response:
    return server.app.send_static_file("index.html")

def register(app):
    """Register this module's routes on the Flask app (server.py composition root)."""
    app.get("/")(index)
