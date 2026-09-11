"""``taskman`` -- a pure-Python, stdlib-only task manager.

Public API::

    from taskman import TaskManager

    manager = TaskManager()
    task_id = manager.add_task("write docs", priority=5, tags=["docs"])
    manager.set_status(task_id, "doing")
    manager.save("tasks.json")
    manager = TaskManager.load("tasks.json")

Internally the store is **event-sourced**: every change appends an immutable
event to a journal, and the visible task mapping is a pure fold over that
journal.  See ``taskman/DESIGN.md`` for the design space and why this design was
chosen over the more obvious mutable-dict approach.
"""

from .manager import SCHEMA_ID, TaskManager

__all__ = ["TaskManager", "SCHEMA_ID"]

__version__ = "1.0.0"
