"""``taskman`` -- a pure-Python, stdlib-only task manager.

Public surface::

    from taskman import TaskManager

See :mod:`taskman.manager` for the implementation and design notes.
"""

from __future__ import annotations

from taskman.manager import MAX_PRIORITY, MIN_PRIORITY, VALID_STATUSES, TaskManager

__all__ = ["TaskManager", "VALID_STATUSES", "MIN_PRIORITY", "MAX_PRIORITY"]
