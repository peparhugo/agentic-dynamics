"""Pure-Python, stdlib-only task-management package.

The public entry point is :class:`TaskManager`, a small dependency-aware to-do store used
by the ``flash_ladder`` contract test. Importing the package must never pull in a
third-party dependency, so this module only re-exports the stdlib-backed implementation.
"""

from taskman.manager import VALID_STATUSES, TaskManager

__all__ = ["TaskManager", "VALID_STATUSES"]
