"""Control Room route modules (refactor-repair Debt-1).

The 28 routes, grouped by surface, extracted from ``server.py``. Each submodule exposes a
``register(app)`` function; :func:`register` wires them all. Route handlers read shared state
(``server._redis``, Redis keys, paths, constants) through ``server.*`` at request time so the
tests' monkeypatches keep working.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import only for static typing
    from flask import Flask


def register(app: Flask) -> None:
    """Register every route module on ``app`` (called once by ``server.py``)."""
    from . import claude_agents, design_sessions, flags, index, registry, telemetry

    telemetry.register(app)
    flags.register(app)
    registry.register(app)
    design_sessions.register(app)
    claude_agents.register(app)
    index.register(app)
