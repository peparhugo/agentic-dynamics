"""In-memory task manager satisfying the ``flash_ladder`` behavioural contract.

Design goals
------------
* **Pure Python / stdlib only.** The only imports are ``datetime``, ``json``, ``pathlib``,
  and ``uuid`` — no third-party runtime dependency, so the package imports in any
  interpreter that can run the contract test.
* **Validation happens before mutation.** Every mutating method validates its inputs and
  the resulting dependency graph *first*, then applies the change. This is what lets the
  contract's cycle test assert "raises ``ValueError`` leaving state unchanged": a rejected
  update never leaves a half-applied edit behind.
* **Deterministic ordering.** ``list_tasks`` orders by priority descending and, for ties,
  by creation order. Creation order is preserved explicitly (``_order``) rather than
  relying on incidental ``dict`` iteration order, so it survives a save/load round-trip.

The public surface is exactly what the contract exercises: ``add_task``, ``get_task``,
``update_task``, ``delete_task``, ``set_status``, ``list_tasks``, ``ready_tasks``,
``save``, ``load``. ``TaskManager`` is re-exported from the package ``__init__``.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

#: The only statuses the contract recognises. Anything else is a ``ValueError``.
VALID_STATUSES = ("todo", "doing", "done")

#: ``priority`` is a 1 (lowest) .. 5 (highest) integer, defaulting to 3.
MIN_PRIORITY = 1
MAX_PRIORITY = 5
DEFAULT_PRIORITY = 3

#: Fields ``update_task`` knows how to patch. An unknown keyword is a programming error
#: and is surfaced as a ``ValueError`` rather than silently ignored.
_UPDATABLE_FIELDS = frozenset({"title", "status", "priority", "tags", "depends_on", "due_at"})


class TaskManager:
    """A tiny dependency-aware to-do store.

    Tasks are plain ``dict`` records keyed by an opaque unique id. The manager owns the
    validation rules (priority range, ISO-8601 due dates, dependency existence, acyclicity)
    and the ordering rules (priority desc, then creation order).
    """

    def __init__(self) -> None:
        # id -> task dict. ``dict`` preserves insertion order, but we also keep ``_order``
        # so creation order is explicit and is restored faithfully by ``load``.
        self._tasks: dict[str, dict[str, Any]] = {}
        self._order: list[str] = []

    # ------------------------------------------------------------------ creation

    def add_task(
        self,
        title: str,
        *,
        priority: int = DEFAULT_PRIORITY,
        tags: list[str] | None = None,
        depends_on: list[str] | None = None,
        due_at: str | None = None,
    ) -> str:
        """Create a task and return its unique id.

        Defaults mirror the contract: status ``todo``, priority ``3``, no tags, no
        dependencies, no due date. ``title`` is stored verbatim; ``tags``/``depends_on``
        are copied into fresh lists so later mutation of the caller's list cannot alias
        the stored record.
        """
        self._validate_priority(priority)
        self._validate_due_at(due_at)
        tags = list(tags) if tags is not None else []
        depends_on = list(depends_on) if depends_on is not None else []
        self._validate_dependencies_exist(depends_on)

        task_id = uuid.uuid4().hex
        # A brand-new task can never be referenced yet, so the graph stays acyclic; the
        # explicit check documents the invariant and guards future refactors.
        self._ensure_acyclic(task_id, depends_on)

        self._tasks[task_id] = {
            "id": task_id,
            "title": title,
            "status": "todo",
            "priority": priority,
            "tags": tags,
            "depends_on": depends_on,
            "due_at": due_at,
            "created_at": _utc_now_iso(),
        }
        self._order.append(task_id)
        return task_id

    # -------------------------------------------------------------------- reads

    def get_task(self, task_id: str) -> dict[str, Any]:
        """Return a shallow copy of the task record (unknown id -> ``KeyError``).

        Returning a copy keeps callers from mutating internal state out of band; the
        nested ``tags``/``depends_on`` lists are copied too.
        """
        return self._copy(self._require(task_id))

    def list_tasks(
        self,
        *,
        status: str | None = None,
        priority: int | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return tasks matching all supplied filters, priority descending.

        Ties are broken by creation order. All filters are optional and combine with
        logical AND (``status`` equality, ``priority`` equality, ``tag`` membership).
        """
        selected = [
            self._copy(self._tasks[tid])
            for tid in self._order
            if self._matches(self._tasks[tid], status, priority, tag)
        ]
        # ``sorted`` is stable, so equal priorities retain creation order.
        selected.sort(key=lambda task: task["priority"], reverse=True)
        return selected

    def ready_tasks(self) -> list[dict[str, Any]]:
        """Return not-done tasks whose dependencies are all ``done``.

        A task with no dependencies is ready as soon as it is not done. Dependencies are
        compared by status only — a missing dependency cannot occur because existence is
        validated at write time.
        """
        ready: list[dict[str, Any]] = []
        for task_id in self._order:
            task = self._tasks[task_id]
            if task["status"] == "done":
                continue
            if all(self._tasks[dep]["status"] == "done" for dep in task["depends_on"]):
                ready.append(self._copy(task))
        return ready

    # ----------------------------------------------------------------- mutations

    def update_task(self, task_id: str, **fields: Any) -> dict[str, Any]:
        """Patch one or more fields, validating everything before mutating.

        Unknown ids raise ``KeyError``. Unknown field names, bad priorities, bad due
        dates, unknown dependencies, and dependency cycles all raise ``ValueError`` — and
        in every rejection path the task is left exactly as it was.
        """
        task = self._require(task_id)

        unknown = set(fields) - _UPDATABLE_FIELDS
        if unknown:
            raise ValueError(f"unknown task field(s): {', '.join(sorted(unknown))}")

        # Validate candidate values *without* touching ``task`` yet.
        if "priority" in fields:
            self._validate_priority(fields["priority"])
        if "due_at" in fields:
            self._validate_due_at(fields["due_at"])
        if "status" in fields:
            self._validate_status(fields["status"])
        if "depends_on" in fields:
            depends_on = list(fields["depends_on"])
            self._validate_dependencies_exist(depends_on)
            self._ensure_acyclic(task_id, depends_on)
            fields["depends_on"] = depends_on
        if "tags" in fields:
            fields["tags"] = list(fields["tags"])

        task.update(fields)
        return self._copy(task)

    def set_status(self, task_id: str, status: str) -> None:
        """Set a task's status; unknown status -> ``ValueError``, unknown id -> ``KeyError``."""
        task = self._require(task_id)
        self._validate_status(status)
        task["status"] = status

    def delete_task(self, task_id: str) -> None:
        """Delete a task, refusing (``ValueError``) while others depend on it.

        Unknown id -> ``KeyError``. A task that nothing depends on is removed, and its
        slot in the creation-order list is dropped so it can never be resurrected.
        """
        self._require(task_id)
        dependents = [tid for tid in self._order if task_id in self._tasks[tid]["depends_on"]]
        if dependents:
            raise ValueError(
                f"cannot delete task {task_id!r}: depended on by {', '.join(dependents)}"
            )
        del self._tasks[task_id]
        self._order.remove(task_id)

    # -------------------------------------------------------------- persistence

    def save(self, path: str) -> None:
        """Serialise the whole manager to JSON at ``path``.

        The payload is a top-level object (the contract asserts this) holding the ordered
        task list, so ``load`` can restore creation order exactly.
        """
        payload = {
            "version": 1,
            "tasks": [self._copy(self._tasks[tid]) for tid in self._order],
        }
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> TaskManager:
        """Reconstruct a manager from a file written by :meth:`save`."""
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        manager = cls()
        for record in payload["tasks"]:
            task = {
                "id": record["id"],
                "title": record["title"],
                "status": record["status"],
                "priority": record["priority"],
                "tags": list(record.get("tags", [])),
                "depends_on": list(record.get("depends_on", [])),
                "due_at": record.get("due_at"),
                "created_at": record["created_at"],
            }
            manager._tasks[task["id"]] = task
            manager._order.append(task["id"])
        return manager

    # ----------------------------------------------------------------- internals

    def _require(self, task_id: str) -> dict[str, Any]:
        """Look up a task, raising ``KeyError`` for an unknown id."""
        try:
            return self._tasks[task_id]
        except KeyError:
            raise KeyError(f"unknown task id: {task_id!r}") from None

    @staticmethod
    def _copy(task: dict[str, Any]) -> dict[str, Any]:
        """Shallow-copy a record, deep-copying the list fields callers could mutate."""
        clone = dict(task)
        clone["tags"] = list(task["tags"])
        clone["depends_on"] = list(task["depends_on"])
        return clone

    @staticmethod
    def _matches(
        task: dict[str, Any],
        status: str | None,
        priority: int | None,
        tag: str | None,
    ) -> bool:
        """True when ``task`` satisfies every supplied (non-``None``) filter."""
        if status is not None and task["status"] != status:
            return False
        if priority is not None and task["priority"] != priority:
            return False
        if tag is not None and tag not in task["tags"]:
            return False
        return True

    @staticmethod
    def _validate_status(status: str) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status {status!r}; expected one of {VALID_STATUSES}")

    @staticmethod
    def _validate_priority(priority: Any) -> None:
        # ``bool`` is an ``int`` subclass; reject it explicitly so ``priority=True`` does
        # not silently masquerade as priority 1.
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ValueError(f"priority must be an integer, got {priority!r}")
        if not MIN_PRIORITY <= priority <= MAX_PRIORITY:
            raise ValueError(
                f"priority must be between {MIN_PRIORITY} and {MAX_PRIORITY}, got {priority}"
            )

    @staticmethod
    def _validate_due_at(due_at: str | None) -> None:
        """Require ``due_at`` to be ``None`` or an ISO-8601 timestamp.

        The original string is preserved (not re-serialised) so the contract's exact
        round-trip assertion holds.
        """
        if due_at is None:
            return
        if not isinstance(due_at, str):
            raise ValueError(f"due_at must be an ISO-8601 string or None, got {due_at!r}")
        try:
            datetime.fromisoformat(due_at)
        except ValueError:
            raise ValueError(f"invalid due_at {due_at!r}: expected ISO-8601") from None

    def _validate_dependencies_exist(self, depends_on: list[str]) -> None:
        """Reject dependencies that name tasks we do not have."""
        for dep in depends_on:
            if dep not in self._tasks:
                raise ValueError(f"unknown dependency id: {dep!r}")

    def _ensure_acyclic(self, task_id: str, depends_on: list[str]) -> None:
        """Reject a dependency set that would introduce a cycle.

        Walking the ``depends_on`` edges from each proposed dependency, if we can reach
        ``task_id`` then adding the edge would close a loop. Self-dependency is caught by
        the same walk (``task_id`` is its own start when ``task_id in depends_on``).
        """
        for dep in depends_on:
            if dep == task_id or self._reaches(dep, task_id):
                raise ValueError(f"dependency cycle: {task_id!r} -> {dep!r} would create a loop")

    def _reaches(self, start: str, target: str) -> bool:
        """Depth-first search over ``depends_on`` edges: can ``start`` reach ``target``?"""
        seen: set[str] = set()
        stack = [start]
        while stack:
            current = stack.pop()
            if current == target:
                return True
            if current in seen:
                continue
            seen.add(current)
            # ``current`` is a known task in every validated path; guard defensively.
            node = self._tasks.get(current)
            if node is not None:
                stack.extend(node["depends_on"])
        return False


def _utc_now_iso() -> str:
    """Timestamp helper: timezone-aware ISO-8601 (guaranteed non-empty string)."""
    return datetime.now().astimezone().isoformat()
