"""``taskman`` — a tiny, pure-Python, stdlib-only task manager.

The package exposes a single public surface: :class:`TaskManager`, an in-memory
store of tasks keyed by a unique id, with optional dependency edges between them.

Design notes (verbose mode — the reasoning behind each choice is recorded here so a
future reader can see *why* the code is shaped the way it is):

* **Stdlib only.** The contract calls for a pure-Python, dependency-free package, so
  the implementation imports only ``json``, ``uuid`` and ``datetime``. No third-party
  packages, no I/O beyond the explicit ``save`` / ``load`` pair.
* **Plain dicts as records.** The contract test reads task fields by string key
  (``task["id"]``, ``task["depends_on"]`` ...). Plain ``dict`` records are the
  smallest thing that satisfies that read shape and JSON round-trips for free — a
  custom record class would add translation code without buying anything here.
* **An id-keyed dict preserves creation order.** CPython dicts are insertion ordered,
  so storing tasks in ``self._tasks`` gives us the "ties keep creation order"
  tie-break required by ``list_tasks`` for free, with no separate sequence counter.
* **One implementation module.** ``__init__`` deliberately only re-exports; the logic
  lives in :mod:`taskman.manager` so the package layout stays a thin, readable split.
"""

from __future__ import annotations

from taskman.manager import TaskManager

__all__ = ["TaskManager"]
