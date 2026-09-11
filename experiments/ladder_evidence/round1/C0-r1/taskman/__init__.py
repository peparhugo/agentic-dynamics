"""``taskman`` — a tiny, dependency-free task manager.

Public surface:

* :class:`TaskManager` — in-memory store with priorities, tags, a validated dependency graph,
  and JSON persistence.

Only the standard library is used; importing this package has no side effects.
"""

from __future__ import annotations

from .manager import (
    MAX_PRIORITY,
    MIN_PRIORITY,
    VALID_STATUSES,
    TaskManager,
)

__all__ = ["TaskManager", "VALID_STATUSES", "MIN_PRIORITY", "MAX_PRIORITY"]
__version__ = "1.0.0"
