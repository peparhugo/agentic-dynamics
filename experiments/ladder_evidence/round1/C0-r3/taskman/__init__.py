"""``taskman`` — a tiny, pure-Python, stdlib-only task manager.

The package intentionally exposes a single public name, :class:`TaskManager`,
so the behavioural contract in ``tests/flash_ladder/taskman_contract_test.py``
can be satisfied with a minimal, dependency-free surface.

Design notes
------------
* **Stdlib only.** The only external imports are :mod:`json` (persistence),
  :mod:`uuid` (unique ids), :mod:`datetime` (timestamps / due-date parsing), and
  :mod:`copy` (defensive copies of list-valued fields).
* **Dict-shaped records.** A task is a plain ``dict`` so callers can compare
  records structurally (``loaded.get_task(id) == manager.get_task(id)``) and so
  JSON serialisation is trivial.
* **Creation-order stability.** Tasks are held in an insertion-ordered mapping;
  :meth:`TaskManager.list_tasks` performs a *stable* priority-descending sort,
  which naturally makes equal-priority tasks keep their creation order.
"""

from __future__ import annotations

from .manager import TaskManager

__all__ = ["TaskManager"]
