"""``taskman`` — a tiny, pure-Python, stdlib-only task manager.

The package exposes a single public class, :class:`TaskManager`, which models a
collection of tasks with priorities, tags, dependencies, and an optional due
date.  It is deliberately dependency-free (only the standard library is used)
so it can run in the most restricted execution environments.

Design overview
---------------
* **Storage** — tasks live in a plain ``dict`` keyed by task id.  Python dicts
  preserve insertion order, which gives us free "creation order" for the
  priority tie-break without maintaining a separate sequence counter.
* **Ids** — generated with :func:`uuid.uuid4`, guaranteeing uniqueness without
  any shared mutable counter that save/load would have to restore.
* **Immutability at the boundary** — every public read returns a deep copy, so
  callers can never mutate internal state by accident.
* **Fail atomically** — validation (priority range, due-date parsing, unknown
  dependency ids, dependency cycles) happens against a candidate snapshot; the
  live state is only mutated once every check has passed.  A rejected update
  therefore leaves the manager exactly as it was.
"""

from __future__ import annotations

# The manager is split into its own module to keep this package surface a thin
# re-export; the public API is intentionally just ``TaskManager``.
from taskman.manager import TaskManager

__all__ = ["TaskManager"]

__version__ = "1.0.0"
