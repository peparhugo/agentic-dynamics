"""Pure-Python, stdlib-only task manager.

VERBOSE MODE: This module deliberately contains no third-party imports and no
persistence beyond :mod:`json`.  The behavioural contract lives in
``tests/flash_ladder/taskman_contract_test.py``; every design decision below is
annotated with the contract clause it exists to satisfy.

Design decisions and why:

* **Identity** — ids are ``uuid.uuid4().hex`` values.  A UUID needs no
  persisted counter, so a manager reconstructed by :meth:`TaskManager.load`
  can never mint a colliding id by forgetting where its counter stopped
  (contract: ids are unique).  Creation order is preserved separately by the
  insertion order of the backing ``dict``.
* **Ordering** — the backing store is a plain ``dict`` (insertion ordered on
  every supported interpreter).  ``list_tasks`` applies a *stable* sort by
  priority, so equal-priority tasks retain creation order for free.
* **Validation before mutation** — ``update_task`` computes and validates the
  complete new field set before touching the store, which is what lets a
  rejected dependency cycle leave state byte-for-byte unchanged.
* **Defensive copies** — ``get_task`` / ``list_tasks`` / ``ready_tasks`` return
  copies, so a caller mutating a returned list cannot silently corrupt the
  manager's internal invariants.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

__all__ = ["TaskManager"]

# The closed set of legal statuses.  Anything else is a ValueError (contract:
# "statuses are todo/doing/done (else ValueError)").
VALID_STATUSES = ("todo", "doing", "done")

# Inclusive priority band required by the contract.
MIN_PRIORITY = 1
MAX_PRIORITY = 5

# Fields a caller may change through update_task.  ``status`` is intentionally
# excluded: it has its own dedicated verb (set_status).
_UPDATABLE_FIELDS = frozenset(("title", "priority", "tags", "depends_on", "due_at"))


def _validate_priority(priority: Any) -> int:
    """Return ``priority`` if it is an integer in ``[1, 5]``, else raise.

    ``bool`` is rejected explicitly even though it subclasses ``int`` — ``True``
    silently meaning priority 1 would be a footgun, and the contract treats
    priorities as a small closed integer band.
    """
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError(
            f"priority must be an int in {MIN_PRIORITY}..{MAX_PRIORITY}, got {priority!r}"
        )
    if not MIN_PRIORITY <= priority <= MAX_PRIORITY:
        raise ValueError(f"priority must be in {MIN_PRIORITY}..{MAX_PRIORITY}, got {priority!r}")
    return priority


def _validate_due_at(due_at: Any) -> Optional[str]:
    """Validate ``due_at`` and return it **verbatim**.

    The contract asserts an exact string round-trip
    (``"2030-01-02T03:04:05+00:00"`` in equals out), so the parsed value is
    discarded and the caller's original string is stored.  ``None`` means "no
    deadline" and is always allowed.
    """
    if due_at is None:
        return None
    if not isinstance(due_at, str):
        raise ValueError(f"due_at must be an ISO-8601 string or None, got {due_at!r}")
    try:
        # fromisoformat supports the offset-bearing timestamps in the contract.
        datetime.fromisoformat(due_at)
    except ValueError as exc:
        raise ValueError(f"due_at is not a parseable ISO-8601 timestamp: {due_at!r}") from exc
    return due_at


def _normalize_id_list(value: Any, field: str) -> List[str]:
    """Coerce ``None`` to ``[]`` and otherwise materialise a fresh list.

    A fresh list is important: the manager must not alias a caller-owned list,
    or a later external mutation would bypass validation.  ``None`` is the
    documented default for both ``tags`` and ``depends_on``.
    """
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field} must be a list of ids, got {value!r}")
    return list(value)


def _copy_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """Return a shallow copy with the two list fields duplicated.

    The task record is flat apart from ``tags`` / ``depends_on``, so one level
    of copying is sufficient to fully isolate internal state.
    """
    duplicate = dict(task)
    duplicate["tags"] = list(task["tags"])
    duplicate["depends_on"] = list(task["depends_on"])
    return duplicate


class TaskManager:
    """In-memory task store implementing the flash-ladder contract.

    All query verbs return copies and all mutation verbs validate before they
    write, so a raised ``ValueError``/``KeyError`` never leaves partial state.
    """

    def __init__(self) -> None:
        # Insertion-ordered by construction; that order is the tie-breaker for
        # equal-priority listing and the on-disk order for save/load.
        self._tasks: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------
    def add_task(
        self,
        title: str,
        *,
        priority: int = 3,
        tags: Optional[Sequence[str]] = None,
        depends_on: Optional[Sequence[str]] = None,
        due_at: Optional[str] = None,
    ) -> str:
        """Create a task and return its unique id.

        Defaults per contract: status ``todo``, priority ``3``, empty
        ``tags``/``depends_on``, ``None`` due date.  Every supplied field is
        validated *before* the task is inserted, so a rejected dependency leaves
        no orphan record behind.
        """
        _validate_priority(priority)
        due_at = _validate_due_at(due_at)
        tag_list = _normalize_id_list(tags, "tags")
        dep_list = _normalize_id_list(depends_on, "depends_on")

        # A brand-new task has no inbound edges, so only existence of the
        # dependencies needs checking; a cycle involving it is impossible.
        self._validate_dependencies(dep_list, task_id=None)

        task_id = uuid.uuid4().hex
        self._tasks[task_id] = {
            "id": task_id,
            "title": title,
            "status": "todo",
            "priority": priority,
            "tags": tag_list,
            "depends_on": dep_list,
            "due_at": due_at,
            # Non-empty ISO timestamp; only ever asserted to be a non-empty str.
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return task_id

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def get_task(self, task_id: str) -> Dict[str, Any]:
        """Return a copy of the task, or raise ``KeyError`` if unknown."""
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(task_id)
        return _copy_task(task)

    def list_tasks(
        self,
        *,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return copies of matching tasks ordered by priority descending.

        ``None`` filters are ignored.  The sort is stable, so ties keep
        creation order (contract: "ties keep creation order").
        """
        selected = []
        for task in self._tasks.values():
            if status is not None and task["status"] != status:
                continue
            if priority is not None and task["priority"] != priority:
                continue
            if tag is not None and tag not in task["tags"]:
                continue
            selected.append(task)
        # reverse=True inverts the key comparison but NOT stability: equal
        # priorities stay in the insertion order they were appended in.
        selected.sort(key=lambda task: task["priority"], reverse=True)
        return [_copy_task(task) for task in selected]

    def ready_tasks(self) -> List[Dict[str, Any]]:
        """Return not-done tasks whose dependencies are all done.

        A done task is never "ready" again, and a task with no dependencies is
        ready immediately (``all([])`` is ``True``).
        """
        ready = []
        for task in self._tasks.values():
            if task["status"] == "done":
                continue
            if all(self._tasks[dep]["status"] == "done" for dep in task["depends_on"]):
                ready.append(task)
        return [_copy_task(task) for task in ready]

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------
    def update_task(self, task_id: str, **fields: Any) -> Dict[str, Any]:
        """Update the supplied fields of a task.

        Known id raises ``KeyError``.  All new values are validated first and
        committed in a single ``update`` call, which guarantees the cycle case
        "leaves state unchanged".
        """
        if task_id not in self._tasks:
            raise KeyError(task_id)

        unknown = set(fields) - _UPDATABLE_FIELDS
        if unknown:
            raise ValueError(f"unknown task field(s): {sorted(unknown)}")

        # Stage the validated values; nothing is written until every field passes.
        staged: Dict[str, Any] = {}
        if "title" in fields:
            staged["title"] = fields["title"]
        if "priority" in fields:
            staged["priority"] = _validate_priority(fields["priority"])
        if "due_at" in fields:
            staged["due_at"] = _validate_due_at(fields["due_at"])
        if "tags" in fields:
            staged["tags"] = _normalize_id_list(fields["tags"], "tags")
        if "depends_on" in fields:
            dep_list = _normalize_id_list(fields["depends_on"], "depends_on")
            # Existence + cycle check happen BEFORE the write below.
            self._validate_dependencies(dep_list, task_id=task_id)
            staged["depends_on"] = dep_list

        self._tasks[task_id].update(staged)
        return _copy_task(self._tasks[task_id])

    def set_status(self, task_id: str, status: str) -> None:
        """Set a task's status; unknown id -> ``KeyError``, bad status -> ``ValueError``."""
        if task_id not in self._tasks:
            raise KeyError(task_id)
        if status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
        self._tasks[task_id]["status"] = status

    def delete_task(self, task_id: str) -> None:
        """Delete a task, refusing while any other task depends on it.

        Unknown id -> ``KeyError``; a surviving dependent -> ``ValueError``
        (deleting it would dangle a dependency).
        """
        if task_id not in self._tasks:
            raise KeyError(task_id)
        for other in self._tasks.values():
            if task_id in other["depends_on"]:
                raise ValueError(f"task {task_id!r} is depended on by {other['id']!r}")
        del self._tasks[task_id]

    # ------------------------------------------------------------------
    # Dependency validation
    # ------------------------------------------------------------------
    def _validate_dependencies(self, deps: Sequence[str], task_id: Optional[str]) -> None:
        """Reject unknown dependency ids and dependency cycles.

        ``task_id`` is the task whose ``depends_on`` is being proposed (``None``
        during creation, when no cycle is possible).  A cycle exists exactly
        when the task is reachable from one of the proposed dependencies by
        following ``depends_on`` edges forward.
        """
        for dep in deps:
            if dep not in self._tasks:
                raise ValueError(f"unknown dependency id: {dep!r}")
        if task_id is not None and self._reachable(task_id, deps):
            raise ValueError(f"dependency cycle would be introduced by {task_id!r}")

    def _reachable(self, target: str, starts: Sequence[str]) -> bool:
        """Iterative DFS: is ``target`` reachable from any id in ``starts``?"""
        stack = list(starts)
        seen = set()
        while stack:
            current = stack.pop()
            if current == target:
                return True
            if current in seen:
                continue
            seen.add(current)
            # Safe: every id in the store has a well-formed depends_on list, and
            # unknown ids were rejected before this method is reached.
            stack.extend(self._tasks[current]["depends_on"])
        return False

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save(self, path: str) -> None:
        """Write the whole store to ``path`` as a JSON object.

        The payload is a top-level ``dict`` (the contract asserts as much) whose
        ``tasks`` list preserves creation order.  Lists are copied so a save
        never exposes internal state.
        """
        payload = {
            "version": 1,
            "tasks": [_copy_task(task) for task in self._tasks.values()],
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    @classmethod
    def load(cls, path: str) -> "TaskManager":
        """Rebuild a manager from a :meth:`save` payload.

        Insertion order is replayed in file order, so creation-order tie
        breaking survives the round trip.
        """
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        manager = cls()
        for task in payload["tasks"]:
            manager._tasks[task["id"]] = _copy_task(task)
        return manager
