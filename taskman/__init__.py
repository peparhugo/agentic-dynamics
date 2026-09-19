"""``taskman`` -- a pure-Python, stdlib-only task manager.

The package's entire public surface is :class:`TaskManager`::

    from taskman import TaskManager

    manager = TaskManager()
    task_id = manager.add_task("write docs", priority=5, tags=["docs"])
    manager.set_status(task_id, "doing")

Design goals, in priority order:

1. **Stdlib only.** No third-party import appears anywhere in this package; the
   only imports are :mod:`json`, :mod:`uuid`, and :mod:`datetime`.
2. **Validate before commit.** Every mutation builds a *candidate* state and
   validates it completely before the live mapping is touched. This is what
   makes "a rejected edit leaves state unchanged" (a contract requirement for
   dependency cycles) a structural property rather than a best-effort rollback.
3. **Reads are copies.** A caller can never mutate the store through a value
   returned by ``get_task`` / ``list_tasks`` / ``ready_tasks``.
"""

from .manager import SCHEMA_ID, TaskManager

__all__ = ["TaskManager", "SCHEMA_ID"]

__version__ = "1.0.0"
