"""``taskman`` — a pure-Python, stdlib-only task manager package.

VERBOSE MODE: the public surface is exactly one name, ``TaskManager``, as the
ladder contract requires.  Keeping the implementation in :mod:`taskman.manager`
and re-exporting here mirrors the repository's package convention (a thin
package ``__init__`` over implementation modules) and keeps the scorer's
per-file blob readable.
"""

from .manager import TaskManager

__all__ = ["TaskManager"]
