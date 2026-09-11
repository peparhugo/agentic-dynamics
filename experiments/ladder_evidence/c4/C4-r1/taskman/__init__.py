"""``taskman`` -- a pure-Python, stdlib-only task manager.

Public API::

    from taskman import TaskManager

    manager = TaskManager()
    task_id = manager.add_task("write docs", priority=5, tags=["docs"])
    manager.set_status(task_id, "doing")
    manager.save("tasks.json")
    manager = TaskManager.load("tasks.json")

The package exposes exactly one class, :class:`TaskManager`, and one schema
marker, ``SCHEMA_ID`` (stamped into saved documents so a future format change
can be detected rather than mis-read).  There are no third-party imports
anywhere in the package.
"""

from .manager import SCHEMA_ID, TaskManager

__all__ = ["TaskManager", "SCHEMA_ID"]

__version__ = "1.0.0"
