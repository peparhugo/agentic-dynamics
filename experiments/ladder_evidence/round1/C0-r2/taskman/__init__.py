"""``taskman`` — a tiny, dependency-aware task manager (pure Python, stdlib only).

The public surface is :class:`TaskManager`. See :mod:`taskman.manager` for the
implementation and its design notes.

Example
-------
>>> from taskman import TaskManager
>>> manager = TaskManager()
>>> first = manager.add_task("write docs", priority=5)
>>> second = manager.add_task("publish", depends_on=[first])
>>> [task["id"] for task in manager.ready_tasks()]
['t1']
"""

from __future__ import annotations

from taskman.manager import VALID_STATUSES, TaskManager

__all__ = ["TaskManager", "VALID_STATUSES"]
