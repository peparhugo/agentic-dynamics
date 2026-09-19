"""Task manager implementation for the ``taskman`` package.

This module implements the behavioural contract exercised by
``tests/flash_ladder/taskman_contract_test.py``.  It is deliberately **pure
Python and stdlib-only**: the only imports are :mod:`json`, :mod:`datetime`
and typing helpers, so the artifact can be copied into a cell tree and run
without installing anything.

Design notes
------------

* **Instance state.**  Every :class:`TaskManager` owns its own ``_tasks``
  mapping and ``_next_id`` counter.  Nothing is stored at class or module
  level, so two managers can never observe each other's tasks (a common
  false-success mode: a shared counter or registry that makes the first
  instance's tests pass while leaking into the next).
* **Defensive copies.**  ``get_task`` returns a fresh shallow copy of the
  record with its list fields copied.  A caller that mutates the returned
  dict therefore cannot corrupt the store, and a caller that mutates the
  stored list cannot corrupt a previously returned snapshot.
* **Validate-before-mutate.**  ``update_task`` performs every validation
  (priority, due date, unknown dependencies, cycle detection) *before* it
  touches the stored record, so a rejected update leaves the manager exactly
  as it was.
* **Deterministic ids.**  Ids are decimal strings produced by a per-instance
  monotonic counter.  They are unique by construction and, because the
  underlying ``dict`` preserves insertion order, the order tasks were created
  in survives a save/load round trip (needed for priority-tie ordering).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

__all__ = ["TaskManager", "VALID_STATUSES", "MIN_PRIORITY", "MAX_PRIORITY"]

#: The three legal task statuses.  Anything else is a ``ValueError``.
VALID_STATUSES = ("todo", "doing", "done")

#: Inclusive bounds for task priority (1 is highest urgency, 5 lowest).
MIN_PRIORITY = 1
MAX_PRIORITY = 5

#: Sentinel distinguishing "argument omitted" from an explicit ``None``.
#: Needed for ``update_task`` where ``tags=None`` and ``due_at=None`` are
#: meaningful ("clear this field") rather than "leave unchanged".
_UNSET: Any = object()


def _parse_due_at(value: Any) -> str:
    """Validate an ISO-8601 ``due_at`` and return it unchanged.

    The *original* string is returned (not a re-serialised ``datetime``) so
    an exact round trip is possible: the contract asserts the stored value
    equals the caller's input byte-for-byte.  We parse only to reject
    unparseable values.  A trailing ``Z`` (UTC designator) is normalised to
    ``+00:00`` for parsing because :func:`datetime.fromisoformat` did not
    accept ``Z`` before Python 3.11.

    Raises:
        ValueError: if ``value`` is not a string or is not parseable as an
            ISO-8601 timestamp.
    """

    if not isinstance(value, str):
        raise ValueError(f"due_at must be an ISO-8601 string, got {type(value).__name__}")
    candidate = value
    if candidate.endswith(("Z", "z")):
        candidate = candidate[:-1] + "+00:00"
    try:
        datetime.fromisoformat(candidate)
    except ValueError as exc:  # pragma: no cover - message is exercised indirectly
        raise ValueError(f"due_at is not a parseable ISO-8601 timestamp: {value!r}") from exc
    return value


def _validate_priority(priority: Any) -> int:
    """Return ``priority`` if it is an int within 1..5, else raise ``ValueError``.

    ``bool`` is rejected explicitly even though it is an ``int`` subclass:
    silently treating ``True`` as priority 1 would be a surprising coercion.
    """

    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError(
            f"priority must be an int in {MIN_PRIORITY}..{MAX_PRIORITY}, got {priority!r}"
        )
    if not MIN_PRIORITY <= priority <= MAX_PRIORITY:
        raise ValueError(f"priority must be in {MIN_PRIORITY}..{MAX_PRIORITY}, got {priority!r}")
    return priority


def _validate_status(status: Any) -> str:
    """Return ``status`` if it is one of the three legal values, else raise."""

    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
    return status


def _normalise_str_list(value: Any, *, field: str) -> list[str]:
    """Coerce ``value`` into a fresh list of strings.

    ``None`` becomes the empty list (the contract's default).  A single
    string is *not* accepted as a sequence of characters: string inputs are
    rejected so ``tags="ab"`` cannot silently become ``["a", "b"]``.
    """

    if value is None:
        return []
    if isinstance(value, str):
        raise ValueError(f"{field} must be a list of strings, not a bare string")
    try:
        items = list(value)
    except TypeError as exc:
        raise ValueError(f"{field} must be an iterable of strings") from exc
    for item in items:
        if not isinstance(item, str):
            raise ValueError(f"{field} entries must be strings, got {type(item).__name__}")
    return items


class TaskManager:
    """An in-memory task store satisfying the flash-ladder ``taskman`` contract.

    The store is a plain dict keyed by task id; insertion order is the
    creation order and is relied upon for stable priority-tie ordering.
    """

    def __init__(self) -> None:
        # Per-instance state only -- see the module docstring on state leakage.
        self._tasks: dict[str, dict[str, Any]] = {}
        self._next_id: int = 1

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _copy_task(record: Mapping[str, Any]) -> dict[str, Any]:
        """Return an independent copy of ``record``.

        The list fields are copied so the caller cannot mutate the store
        through a value it was handed; scalar fields are immutable.
        """

        copy = dict(record)
        copy["tags"] = list(record["tags"])
        copy["depends_on"] = list(record["depends_on"])
        return copy

    def _new_id(self) -> str:
        """Allocate the next unique id as a decimal string.

        The ``while`` loop guards against a collision with an id restored by
        :meth:`load` (or any future caller that could inject ids) -- a
        collision would silently overwrite a task.
        """

        while str(self._next_id) in self._tasks:
            self._next_id += 1
        task_id = str(self._next_id)
        self._next_id += 1
        return task_id

    def _require(self, task_id: str) -> dict[str, Any]:
        """Return the stored record for ``task_id`` or raise ``KeyError``."""

        try:
            return self._tasks[task_id]
        except KeyError:
            raise KeyError(task_id) from None

    def _check_dependencies(self, depends_on: Iterable[str]) -> list[str]:
        """Validate that every dependency id exists; return a fresh list.

        Unknown ids are a ``ValueError`` (not ``KeyError``) per the contract.
        """

        deps = _normalise_str_list(depends_on, field="depends_on")
        for dep in deps:
            if dep not in self._tasks:
                raise ValueError(f"unknown dependency id: {dep!r}")
        return deps

    @staticmethod
    def _creates_cycle(
        task_id: str,
        depends_on: Iterable[str],
        tasks: Mapping[str, Mapping[str, Any]],
    ) -> bool:
        """Return ``True`` if installing ``task_id -> depends_on`` creates a cycle.

        We walk outward from the proposed dependencies along the *existing*
        edges.  If ``task_id`` is reachable, then adding the proposed edges
        would close a loop.  We only replace ``task_id``'s own outgoing edges,
        so the rest of the graph (a DAG by invariant) is untouched.
        """

        seen: set[str] = set()
        stack: list[str] = list(depends_on)
        while stack:
            current = stack.pop()
            if current == task_id:
                return True
            if current in seen:
                continue
            seen.add(current)
            stack.extend(tasks[current]["depends_on"])
        return False

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def add_task(
        self,
        title: str,
        *,
        priority: int = 3,
        tags: Iterable[str] | None = None,
        depends_on: Iterable[str] | None = None,
        due_at: str | None = None,
    ) -> str:
        """Create a task and return its unique id.

        Defaults follow the contract: status ``todo``, priority ``3``, empty
        tags/dependencies and no due date.  All validation happens before the
        record is inserted, so a rejected ``add_task`` never leaves a partial
        task behind.
        """

        _validate_priority(priority)
        parsed_due = None if due_at is None else _parse_due_at(due_at)
        deps = self._check_dependencies(depends_on)

        task_id = self._new_id()
        # A brand-new id cannot be part of an existing cycle, but run the
        # check anyway so the invariant holds for any future caller that
        # supplies an explicit id.
        if self._creates_cycle(task_id, deps, self._tasks):
            raise ValueError("dependency cycle detected")

        self._tasks[task_id] = {
            "id": task_id,
            "title": title,
            "status": "todo",
            "priority": priority,
            "tags": _normalise_str_list(tags, field="tags"),
            "depends_on": deps,
            "due_at": parsed_due,
            # ISO-8601 UTC timestamp; only required to be a non-empty string.
            "created_at": datetime.now().astimezone().isoformat(),
        }
        return task_id

    def get_task(self, task_id: str) -> dict[str, Any]:
        """Return an independent copy of the task, or raise ``KeyError``."""

        return self._copy_task(self._require(task_id))

    def update_task(
        self,
        task_id: str,
        *,
        title: Any = _UNSET,
        priority: Any = _UNSET,
        tags: Any = _UNSET,
        depends_on: Any = _UNSET,
        due_at: Any = _UNSET,
        status: Any = _UNSET,
    ) -> None:
        """Update the supplied fields on an existing task.

        Unknown ids raise ``KeyError``.  Every field is validated *before* any
        mutation, so a rejected update (bad priority, unknown dependency, a
        dependency cycle) leaves the stored task completely unchanged.
        """

        record = self._require(task_id)

        # Compute the fully-validated replacements first; nothing is written
        # until every check has passed.
        updates: dict[str, Any] = {}

        if title is not _UNSET:
            updates["title"] = title
        if priority is not _UNSET:
            updates["priority"] = _validate_priority(priority)
        if status is not _UNSET:
            updates["status"] = _validate_status(status)
        if tags is not _UNSET:
            updates["tags"] = _normalise_str_list(tags, field="tags")
        if due_at is not _UNSET:
            # An explicit ``None`` clears the due date; a string is validated.
            updates["due_at"] = None if due_at is None else _parse_due_at(due_at)
        if depends_on is not _UNSET:
            deps = self._check_dependencies(depends_on)
            if self._creates_cycle(task_id, deps, self._tasks):
                raise ValueError("dependency cycle detected")
            updates["depends_on"] = deps

        record.update(updates)

    def delete_task(self, task_id: str) -> None:
        """Delete a task, refusing while other tasks depend on it.

        Raises:
            KeyError: ``task_id`` is unknown.
            ValueError: at least one remaining task lists ``task_id`` in its
                ``depends_on``.
        """

        self._require(task_id)
        dependents = [tid for tid, rec in self._tasks.items() if task_id in rec["depends_on"]]
        if dependents:
            raise ValueError(f"cannot delete {task_id!r}; depended on by {sorted(dependents)!r}")
        del self._tasks[task_id]

    def set_status(self, task_id: str, status: str) -> None:
        """Set a task's status, validating the value and the id."""

        record = self._require(task_id)
        record["status"] = _validate_status(status)

    def list_tasks(
        self,
        *,
        status: str | None = None,
        priority: int | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return tasks matching the optional filters, priority-descending.

        Ties keep creation order: we filter the insertion-ordered store into a
        list and sort it stably by descending priority.  Filters combine with
        AND when more than one is supplied.
        """

        result: list[dict[str, Any]] = []
        for record in self._tasks.values():
            if status is not None and record["status"] != status:
                continue
            if priority is not None and record["priority"] != priority:
                continue
            if tag is not None and tag not in record["tags"]:
                continue
            result.append(self._copy_task(record))
        # Python's sort is stable, so equal priorities preserve creation order.
        result.sort(key=lambda rec: rec["priority"], reverse=True)
        return result

    def ready_tasks(self) -> list[dict[str, Any]]:
        """Return not-done tasks whose dependencies are all done.

        Creation order is preserved; the contract only compares the result as
        a set, so no secondary ordering is promised.
        """

        ready: list[dict[str, Any]] = []
        for record in self._tasks.values():
            if record["status"] == "done":
                continue
            if all(self._tasks[dep]["status"] == "done" for dep in record["depends_on"]):
                ready.append(self._copy_task(record))
        return ready

    def save(self, path: str) -> None:
        """Persist the manager to ``path`` as JSON.

        The document is a JSON object carrying the ordered task list and the
        next-id counter, so :meth:`load` can continue allocating without
        colliding with restored ids.
        """

        document = {
            "version": 1,
            "next_id": self._next_id,
            "tasks": [
                dict(rec, tags=list(rec["tags"]), depends_on=list(rec["depends_on"]))
                for rec in self._tasks.values()
            ],
        }
        Path(path).write_text(json.dumps(document, indent=2, ensure_ascii=False))

    @classmethod
    def load(cls, path: str) -> TaskManager:
        """Reconstruct a manager from a file written by :meth:`save`."""

        document = json.loads(Path(path).read_text())
        manager = cls()
        for record in document.get("tasks", []):
            task_id = str(record["id"])
            manager._tasks[task_id] = {
                "id": task_id,
                "title": record.get("title"),
                "status": record.get("status", "todo"),
                "priority": record.get("priority", 3),
                "tags": list(record.get("tags") or []),
                "depends_on": list(record.get("depends_on") or []),
                "due_at": record.get("due_at"),
                "created_at": record.get("created_at", ""),
            }
        # Prefer the persisted counter; fall back to one past the largest
        # numeric id so a hand-edited file still cannot collide.
        counter = document.get("next_id")
        if not isinstance(counter, int):
            counter = 1
        for task_id in manager._tasks:
            if task_id.isdigit():
                counter = max(counter, int(task_id) + 1)
        manager._next_id = counter
        return manager
