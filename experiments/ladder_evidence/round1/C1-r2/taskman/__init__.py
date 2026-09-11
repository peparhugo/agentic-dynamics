"""``taskman`` — a pure-Python, stdlib-only task manager.

The package exposes a single public entry point, :class:`TaskManager`. The internal design
(immutable task records, derived adjacency indexes, an incrementally maintained ordering, a
versioned rebuild-on-load snapshot, and Kahn topological cycle detection) is documented in
``DESIGN.md`` beside this file.

Only the standard library is used.
"""

from .manager import Task, TaskManager

__all__ = ["Task", "TaskManager"]
