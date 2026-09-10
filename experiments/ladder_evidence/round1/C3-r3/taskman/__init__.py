"""``taskman`` — a tiny, dependency-free task manager.

This package exists to satisfy the behavioural contract in
``tests/flash_ladder/taskman_contract_test.py``. It is deliberately
**pure Python and stdlib-only**: no third-party imports, no persistence
backends beyond a plain JSON file, so a consumer can vendor it without
pulling anything in.

Public surface
--------------
The only object consumers need is :class:`TaskManager`, re-exported here so
``from taskman import TaskManager`` works without knowing the internal module
layout. :data:`TASK_STATUSES` and :data:`MIN_PRIORITY` / :data:`MAX_PRIORITY`
are exported as well so callers can validate against the same constants the
manager enforces rather than duplicating the literals.
"""

from __future__ import annotations

from .manager import (
    MAX_PRIORITY,
    MIN_PRIORITY,
    TASK_STATUSES,
    TaskManager,
)

# ``__all__`` is the explicit public API. Keeping it authored (rather than
# inferred) means a future helper added to ``manager`` is *not* silently
# promoted to public surface — a small but real stability win.
__all__ = [
    "TaskManager",
    "TASK_STATUSES",
    "MIN_PRIORITY",
    "MAX_PRIORITY",
]

__version__ = "1.0.0"
