"""Control Room route modules (refactor-repair Debt-1; review P2 service context).

The 31 routes, grouped by surface, extracted from ``server.py``. Each submodule exposes a
``register(app, services)`` function; :func:`register` wires them all, forwarding the injected
``ControlRoomServices`` application context. Route handlers read shared state through the injected
``services`` object (``services.redis()``, ``services.design_manager()``, …) rather than importing
``apps.control_room.server`` and reading its private names — the composition root is no longer
used as a service locator. The injected services delegate back to ``server.*`` at call time, so
the tests' monkeypatches keep working.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import only for static typing
    from flask import Flask

    from apps.control_room.services.context import ControlRoomServices


def register(app: Flask, services: ControlRoomServices) -> None:
    """Register every route module on ``app``, injecting the application context.

    Called once by ``server.py``'s composition root. Each submodule stores ``services`` for its
    handlers to read at request time.
    """
    from . import (
        claude_agents,
        design_sessions,
        docs_health,
        flags,
        index,
        registry,
        telemetry,
    )

    telemetry.register(app, services)
    flags.register(app, services)
    registry.register(app, services)
    design_sessions.register(app, services)
    claude_agents.register(app, services)
    docs_health.register(app, services)
    index.register(app, services)
