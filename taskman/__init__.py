"""``taskman`` — a pure-Python, stdlib-only task manager.

Public surface:

    from taskman import TaskManager

The implementation lives in :mod:`taskman.manager`; it is re-exported here so the
package can be consumed with a single import.  Only the standard library is used
(``json``, ``uuid``, ``datetime``, ``copy``), matching the contract in
``tests/flash_ladder/taskman_contract_test.py``.
"""

from taskman.manager import TaskManager

__all__ = ["TaskManager"]
