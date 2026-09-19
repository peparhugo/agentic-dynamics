"""``taskman`` — a tiny, pure-Python, stdlib-only task manager.

This package is deliberately lean: it carries no third-party imports so it can be
executed in constrained environments (the flash-ladder cell image) with nothing
but the standard library. The public surface is a single class, re-exported here
so callers can simply ``from taskman import TaskManager``.

The behavioural contract this implementation must satisfy lives in
``tests/flash_ladder/taskman_contract_test.py``; that file is the authority and is
never modified by the implementation.
"""

from __future__ import annotations

from .manager import TaskManager

__all__ = ["TaskManager"]
