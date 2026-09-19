"""``taskman`` -- a pure-Python, standard-library-only task manager.

The public surface is deliberately small: :class:`TaskManager` is the only
export the behavioural contract requires.  It provides creation, lookup,
mutation, dependency-aware ordering/readiness, and JSON persistence, with all
validation performed before any state change.

It uses only :mod:`json`, :mod:`uuid`, and :mod:`datetime` from the standard
library -- no third-party dependencies.
"""

from .manager import TaskManager

__all__ = ["TaskManager"]
