"""Core implementation of the ``TaskManager``.

Design rationale (readability + maintainability):

* **One store, insertion-ordered.** Tasks live in a single ``dict`` keyed by task
  id. Python 3.7+ guarantees dict insertion order, so the mapping itself records
  *creation order* for free. ``list_tasks`` sorts by ``-priority`` with a stable
  sort, which means equal-priority tasks keep that creation order without a
  separate sequence field. That avoids leaking bookkeeping keys into the task
  payload, so a saved/loaded task compares equal to its in-memory original.
* **Validation happens before mutation.** Every mutator validates all of its
  inputs (priority range, date parseability, dependency existence, cycle safety)
  *before* touching ``self._tasks``. This is what lets the cycle test demand that
  a rejected ``update_task`` leave state completely unchanged.
* **Copies at the boundary.** ``get_task`` / ``list_tasks`` / ``ready_tasks``
  hand out deep copies so callers cannot mutate internal state by accident.
* **Ids are opaque strings.** ``uuid4`` gives collision-free ids without an
  ordering assumption; a guard loop keeps the invariant even in the (vanishingly
  unlikely) event of a clash.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime
from typing import Any

#: The complete set of legal task statuses. Anything else is a ``ValueError``.
_VALID_STATUSES = ("todo", "doing", "done")

#: Inclusive priority bounds; the contract fixes them at 1..5.
_MIN_PRIORITY = 1
_MAX_PRIORITY = 5

#: Default priority when the caller does not supply one.
_DEFAULT_PRIORITY = 3


def _copy_task(task: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of ``task`` so internal state cannot be mutated by callers."""
    return copy.deepcopy(task)


def _validate_priority(priority: Any) -> int:
    """Validate a priority value and return it unchanged.

    ``bool`` is a subclass of ``int`` but is not a meaningful priority, so it is
    rejected explicitly rather than silently coerced (``True`` would otherwise
    pass as ``1``).
    """
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError(
            f"priority must be an integer in {_MIN_PRIORITY}..{_MAX_PRIORITY}, got {priority!r}"
        )
    if not _MIN_PRIORITY <= priority <= _MAX_PRIORITY:
        raise ValueError(f"priority must be in {_MIN_PRIORITY}..{_MAX_PRIORITY}, got {priority!r}")
    return priority


def _validate_due_at(due_at: Any) -> str | None:
    """Validate an ISO-8601 ``due_at`` string, returning it (or ``None``) unchanged.

    We keep the *original string* rather than a normalised datetime: the contract
    round-trips the exact text (``"2030-01-02T03:04:05+00:00"`` in, same out), and
    storing the caller's string is the least surprising behaviour for a JSON model.
    """
    if due_at is None:
        return None
    if not isinstance(due_at, str):
        raise ValueError(f"due_at must be an ISO-8601 string or None, got {due_at!r}")
    try:
        datetime.fromisoformat(due_at)
    except ValueError as exc:
        raise ValueError(f"due_at is not a parseable ISO-8601 timestamp: {due_at!r}") from exc
    return due_at


def _validate_tags(tags: Any) -> list[str]:
    """Validate an optional tag collection and return a fresh list.

    ``None`` means "no tags"; a string is treated as a single tag would be a
    footgun, so a bare string is rejected rather than iterated character by
    character.
    """
    if tags is None:
        return []
    if isinstance(tags, (str, bytes)):
        raise ValueError("tags must be a sequence of strings, not a bare string")
    return list(tags)


def _validate_depends_on(
    depends_on: Any, tasks: dict[str, dict[str, Any]], *, self_id: str | None
) -> list[str]:
    """Validate a dependency list against the live store.

    Every referenced id must already exist. ``self_id`` (when re-validating an
    existing task during ``update_task``) is excluded from the "must exist" check
    because a task legitimately does not depend on itself by id-presence rules;
    self-reference is handled by the cycle check instead, which would reject it.
    """
    if depends_on is None:
        return []
    if isinstance(depends_on, (str, bytes)):
        raise ValueError("depends_on must be a sequence of task ids, not a bare string")
    deps = list(depends_on)
    for dep in deps:
        if dep == self_id:
            # A self-edge is always a cycle; let the cycle checker report it with
            # a consistent error type (ValueError) and message class.
            raise ValueError(f"task {self_id!r} cannot depend on itself")
        if dep not in tasks:
            raise ValueError(f"unknown dependency id: {dep!r}")
    return deps


def _creates_cycle(
    tasks: dict[str, dict[str, Any]], start_id: str, proposed_deps: list[str]
) -> bool:
    """Return ``True`` if wiring ``start_id`` to ``proposed_deps`` introduces a cycle.

    Depth-first search from each proposed dependency: if we can walk the existing
    dependency edges back to ``start_id``, adding the edge would close a loop.
    Using the *proposed* dependency list only at the first hop is sufficient
    because the rest of the graph is unchanged.
    """
    # An empty new-dependency set can never add an edge, so it cannot cycle.
    if not proposed_deps:
        return False

    seen: set[str] = set()
    stack: list[str] = list(proposed_deps)
    while stack:
        current = stack.pop()
        if current == start_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        task = tasks.get(current)
        if task is None:
            # Dangling edge should not exist (validated upstream); treat as a
            # dead end rather than crashing the checker.
            continue
        stack.extend(task["depends_on"])
    return False


class TaskManager:
    """An in-memory collection of tasks with validation, ordering, and persistence.

    The class is intentionally synchronous and side-effect free apart from the
    explicit ``save`` call. Instantiate with no arguments; state starts empty.
    """

    def __init__(self) -> None:
        """Create an empty manager."""
        # id -> task dict. Insertion order *is* creation order.
        self._tasks: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------ ids
    def _new_id(self) -> str:
        """Mint a unique, opaque task id.

        A short hex slice keeps ids readable while the collision loop guarantees
        the uniqueness invariant if a slice ever repeats.
        """
        while True:
            candidate = f"t-{uuid.uuid4().hex[:12]}"
            if candidate not in self._tasks:
                return candidate

    # -------------------------------------------------------------- commands
    def add_task(
        self,
        title: str,
        *,
        priority: int = _DEFAULT_PRIORITY,
        tags: list[str] | None = None,
        depends_on: list[str] | None = None,
        due_at: str | None = None,
    ) -> str:
        """Create a task and return its unique id.

        Validation (priority, due date, tags, dependency existence) runs before
        any state is written, so a rejected ``add_task`` never leaves a partial
        record behind. A brand-new task can only reference *existing* tasks, so a
        cycle is structurally impossible on add; the check is retained for
        uniformity and future-proofing.
        """
        _validate_priority(priority)
        validated_due = _validate_due_at(due_at)
        validated_tags = _validate_tags(tags)
        validated_deps = _validate_depends_on(depends_on, self._tasks, self_id=None)

        # New task ids are not yet in the store; a self/cycle check needs the id,
        # so mint it first, then verify (defensive: deps cannot point at it yet).
        task_id = self._new_id()
        if _creates_cycle(self._tasks, task_id, validated_deps):
            raise ValueError("dependency graph would contain a cycle")

        self._tasks[task_id] = {
            "id": task_id,
            "title": title,
            "status": "todo",
            "priority": priority,
            "tags": validated_tags,
            "depends_on": validated_deps,
            "due_at": validated_due,
            "created_at": datetime.now().astimezone().isoformat(),
        }
        return task_id

    def update_task(self, task_id: str, **fields: Any) -> None:
        """Update selected fields of an existing task.

        Only ``title``, ``priority``, ``tags``, ``depends_on`` and ``due_at`` are
        mutable. All validation is completed against a *candidate* mapping before
        the change is committed, so a cycle rejection leaves the store exactly as
        it was.
        """
        if task_id not in self._tasks:
            raise KeyError(task_id)

        candidate = _copy_task(self._tasks[task_id])

        if "title" in fields:
            candidate["title"] = fields["title"]
        if "priority" in fields:
            candidate["priority"] = _validate_priority(fields["priority"])
        if "tags" in fields:
            candidate["tags"] = _validate_tags(fields["tags"])
        if "due_at" in fields:
            candidate["due_at"] = _validate_due_at(fields["due_at"])
        if "depends_on" in fields:
            deps = _validate_depends_on(fields["depends_on"], self._tasks, self_id=task_id)
            # Cycle check uses the *other* tasks' current edges plus the proposed
            # edges for this task; the candidate is only committed on success.
            prospective = dict(self._tasks)
            prospective[task_id] = candidate
            if _creates_cycle(prospective, task_id, deps):
                raise ValueError("dependency graph would contain a cycle")
            candidate["depends_on"] = deps

        # Unknown/unsupported fields are ignored rather than silently written;
        # the contract only names mutable fields and does not require rejection.
        self._tasks[task_id] = candidate

    def delete_task(self, task_id: str) -> None:
        """Delete a task, refusing if any other task depends on it.

        The referential-integrity guard runs first, so a refused delete is a pure
        no-op.
        """
        if task_id not in self._tasks:
            raise KeyError(task_id)
        for other_id, other in self._tasks.items():
            if other_id != task_id and task_id in other["depends_on"]:
                raise ValueError(f"task {task_id!r} is depended on by {other_id!r}")
        del self._tasks[task_id]

    def set_status(self, task_id: str, status: str) -> None:
        """Set a task's status; unknown ids raise ``KeyError``, bad values ``ValueError``."""
        if task_id not in self._tasks:
            raise KeyError(task_id)
        if status not in _VALID_STATUSES:
            raise ValueError(f"status must be one of {_VALID_STATUSES}, got {status!r}")
        self._tasks[task_id]["status"] = status

    # ---------------------------------------------------------------- queries
    def get_task(self, task_id: str) -> dict[str, Any]:
        """Return a copy of the task with ``task_id``; unknown ids raise ``KeyError``."""
        if task_id not in self._tasks:
            raise KeyError(task_id)
        return _copy_task(self._tasks[task_id])

    def list_tasks(
        self,
        *,
        status: str | None = None,
        priority: int | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return matching tasks ordered by priority descending.

        Filters are conjunctive. Ties in priority preserve creation order because
        the underlying sort is stable and the store is insertion-ordered.
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
        selected.sort(key=lambda t: t["priority"], reverse=True)
        return [_copy_task(task) for task in selected]

    def ready_tasks(self) -> list[dict[str, Any]]:
        """Return not-done tasks whose dependencies are every one of them done.

        The result uses the same priority-descending, creation-order-stable
        ordering as ``list_tasks`` so callers see a consistent queue.
        """
        ready = []
        for task in self._tasks.values():
            if task["status"] == "done":
                continue
            if all(self._tasks[dep]["status"] == "done" for dep in task["depends_on"]):
                ready.append(task)
        ready.sort(key=lambda t: t["priority"], reverse=True)
        return [_copy_task(task) for task in ready]

    # ------------------------------------------------------------ persistence
    def save(self, path: str) -> None:
        """Persist the manager to ``path`` as JSON.

        The on-disk shape is a single JSON object with a ``tasks`` list. A list
        (not a dict) is used so creation order is unambiguous across JSON
        implementations, and the round-trip is exact.
        """
        payload = {
            "version": 1,
            "tasks": [copy.deepcopy(task) for task in self._tasks.values()],
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=False)
            handle.write("\n")

    @classmethod
    def load(cls, path: str) -> "TaskManager":
        """Reconstruct a manager previously written by :meth:`save`.

        Task order in the file is preserved as the new creation order, so
        subsequent tie-breaking matches the saved session.
        """
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        manager = cls()
        for task in payload.get("tasks", []):
            # Re-validate defensively: a hand-edited file should fail loudly via
            # the same ValueError contract rather than poison later operations.
            _validate_priority(task["priority"])
            _validate_due_at(task.get("due_at"))
            manager._tasks[task["id"]] = task
        return manager
