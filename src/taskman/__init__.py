"""``taskman`` — a pure-Python, stdlib-only task manager.

The public surface is a single name, :class:`TaskManager`, re-exported here so the
contract test's ``taskman.TaskManager`` resolves regardless of internal layout.
"""

from .manager import DEFAULT_PRIORITY, PRIORITY_MAX, PRIORITY_MIN, VALID_STATUSES, TaskManager

__all__ = [
    "TaskManager",
    "DEFAULT_PRIORITY",
    "PRIORITY_MIN",
    "PRIORITY_MAX",
    "VALID_STATUSES",
]
