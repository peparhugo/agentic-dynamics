"""``taskman`` — a pure-Python, stdlib-only task manager.

The public surface is exactly one class, :class:`TaskManager`.  See
:mod:`taskman.manager` for the design rationale (three enumerated internal
designs and the one deliberately chosen) and the implementation.

Only the standard library is imported anywhere in this package, and the
behavioural contract lives in ``tests/flash_ladder/taskman_contract_test.py``.
"""

from __future__ import annotations

from taskman.manager import TaskManager

__all__ = ["TaskManager"]
