"""``taskman`` — a tiny pure-Python, stdlib-only task manager.

Public surface::

    from taskman import TaskManager

    manager = TaskManager()
    task_id = manager.add_task("write docs", priority=2, tags=["docs"])
    manager.set_status(task_id, "doing")
    manager.save("tasks.json")
    restored = TaskManager.load("tasks.json")

The package deliberately depends on nothing outside the Python standard library
(``json``, ``uuid``, ``datetime``, ``copy``, ``pathlib``) so it can be dropped
into any environment without a dependency resolution step.

Internal design
---------------
* Tasks are stored in an insertion-ordered ``dict`` keyed by a generated id; the
  insertion order is reused as the creation-order tie-breaker for ordering by
  priority.
* A reverse "dependents" index is maintained alongside the forward
  ``depends_on`` edges so delete-refusal and cycle detection do not scan the
  whole store.
* All validation happens before mutation, which guarantees that rejected
  operations (bad priority, unknown dependency, dependency cycle) leave the
  manager in its prior state.
"""

from __future__ import annotations

from .manager import DEFAULT_PRIORITY, PRIORITY_MAX, PRIORITY_MIN, VALID_STATUSES, TaskManager

__all__ = [
    "TaskManager",
    "VALID_STATUSES",
    "PRIORITY_MIN",
    "PRIORITY_MAX",
    "DEFAULT_PRIORITY",
]
