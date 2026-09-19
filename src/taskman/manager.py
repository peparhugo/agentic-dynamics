"""Pure-stdlib task manager implementing the flash-ladder ``taskman`` contract.

Design notes
------------
* **Storage.** Tasks live in a plain ``dict`` keyed by id. Python dicts preserve
  insertion order, which is exactly the "creation order" tie-breaker the contract
  wants for ``list_tasks``: a stable sort by descending priority therefore keeps
  same-priority tasks in the order they were added (and, after a reload, in the
  order they were serialised).
* **Ids.** ``uuid4().hex`` gives collision-free ids without any counter state, so a
  manager round-tripped through ``save``/``load`` can keep adding tasks without
  risking a duplicate id.
* **Validation is atomic.** Every mutating method validates its whole input and
  (for dependencies) proves the graph stays acyclic *before* touching the stored
  record, so a rejected update leaves the manager byte-for-byte unchanged.  This is
  what the contract's cycle test asserts.
* **Copies on the boundary.** ``get_task``/``list_tasks``/``ready_tasks`` return
  deep copies, so a caller mutating a returned dict cannot corrupt manager state.

The module deliberately depends only on the standard library (``copy``, ``json``,
``uuid``, ``datetime``, ``pathlib``) — the contract requires stdlib-only.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# The three legal lifecycle states.  ``todo`` is the default for a new task.
VALID_STATUSES: tuple[str, ...] = ("todo", "doing", "done")

# Priority is an inclusive 1..5 band; 3 is the documented default.
PRIORITY_MIN: int = 1
PRIORITY_MAX: int = 5
DEFAULT_PRIORITY: int = 3

# The fields ``update_task`` may change.  Keeping this an explicit allow-list means a
# typo raises loudly instead of silently creating a stray key on the record.
_UPDATABLE_FIELDS: frozenset[str] = frozenset({"title", "priority", "tags", "depends_on", "due_at"})


def _utc_now_iso() -> str:
    """Return the current UTC instant as an ISO-8601 string (the ``created_at`` form)."""
    return datetime.now(timezone.utc).isoformat()


def _validate_priority(priority: Any) -> int:
    """Return ``priority`` if it is an int in 1..5, else raise ``ValueError``.

    ``bool`` is rejected explicitly even though it subclasses ``int`` — ``True``
    would otherwise sail through as priority 1, which is a confusing silent bug.
    """
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError(
            f"priority must be an integer in {PRIORITY_MIN}..{PRIORITY_MAX}, got {priority!r}"
        )
    if not PRIORITY_MIN <= priority <= PRIORITY_MAX:
        raise ValueError(f"priority must be in {PRIORITY_MIN}..{PRIORITY_MAX}, got {priority!r}")
    return priority


def _validate_due_at(due_at: Any) -> Optional[str]:
    """Validate an optional ISO-8601 ``due_at`` and return it unchanged.

    The original string is stored verbatim (never re-formatted) so that a legal
    timestamp round-trips byte-for-byte, which the contract checks explicitly.
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


def _normalise_str_list(value: Any, field: str) -> list[str]:
    """Coerce an optional sequence of strings into a fresh ``list[str]``.

    ``None`` becomes ``[]`` (the documented default).  A bare string is rejected so
    ``tags="infra"`` can never be silently iterated into ``["i", "n", ...]``.
    """
    if value is None:
        return []
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field} must be a list of strings or None, got {value!r}")
    items = list(value)
    for item in items:
        if not isinstance(item, str):
            raise ValueError(f"{field} must contain only strings, got {item!r}")
    return items


class TaskManager:
    """An in-memory collection of tasks with dependency-aware ordering.

    The class is intentionally small and synchronous: every public method either
    returns a value or raises one of the two contract error types —
    ``KeyError`` for an unknown id, ``ValueError`` for an invalid argument or an
    illegal graph mutation.
    """

    def __init__(self, tasks: Optional[list[dict[str, Any]]] = None) -> None:
        """Create a manager, optionally pre-populated from ``tasks`` records.

        Records are inserted in order so their creation-order tie-break survives.
        """
        self._tasks: dict[str, dict[str, Any]] = {}
        if tasks:
            for record in tasks:
                self._tasks[record["id"]] = copy.deepcopy(record)

    # ── internal helpers ──────────────────────────────────────────────────────

    def _record(self, task_id: str) -> dict[str, Any]:
        """Return the stored record for ``task_id`` or raise ``KeyError``."""
        try:
            return self._tasks[task_id]
        except KeyError:
            raise KeyError(f"unknown task id: {task_id!r}") from None

    @staticmethod
    def _copy(record: dict[str, Any]) -> dict[str, Any]:
        """Return a deep copy so callers cannot mutate manager-owned state."""
        return copy.deepcopy(record)

    def _validate_dependency_ids(self, depends_on: list[str]) -> None:
        """Reject any dependency that does not name an existing task."""
        for dep in depends_on:
            if dep not in self._tasks:
                raise ValueError(f"unknown dependency id: {dep!r}")

    def _ensure_acyclic(self, task_id: str, depends_on: list[str]) -> None:
        """Raise ``ValueError`` if making ``task_id`` depend on ``depends_on`` cycles.

        Edges point task -> dependency, so a cycle exists exactly when ``task_id`` is
        reachable by following ``depends_on`` links from any of its proposed
        dependencies.  A self-dependency is the trivial case and is caught too.
        """
        seen: set[str] = set()
        stack: list[str] = list(depends_on)
        while stack:
            current = stack.pop()
            if current == task_id:
                raise ValueError(f"dependency cycle detected: {task_id!r} would depend on itself")
            if current in seen:
                continue
            seen.add(current)
            task = self._tasks.get(current)
            if task is not None:
                stack.extend(task["depends_on"])

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add_task(
        self,
        title: str,
        *,
        priority: int = DEFAULT_PRIORITY,
        tags: Optional[list[str]] = None,
        depends_on: Optional[list[str]] = None,
        due_at: Optional[str] = None,
    ) -> str:
        """Create a task and return its freshly minted unique id.

        Defaults: status ``todo``, priority ``3``, empty ``tags``/``depends_on``,
        ``None`` due date, and a non-empty ``created_at`` timestamp.
        """
        if not isinstance(title, str) or not title:
            raise ValueError("title must be a non-empty string")
        clean_priority = _validate_priority(priority)
        clean_due_at = _validate_due_at(due_at)
        clean_tags = _normalise_str_list(tags, "tags")
        clean_deps = _normalise_str_list(depends_on, "depends_on")
        self._validate_dependency_ids(clean_deps)

        task_id = uuid.uuid4().hex
        # A brand-new id cannot yet be reachable, but running the same proof keeps
        # the invariant in one place and guards against future id reuse.
        self._ensure_acyclic(task_id, clean_deps)

        self._tasks[task_id] = {
            "id": task_id,
            "title": title,
            "status": "todo",
            "priority": clean_priority,
            "tags": clean_tags,
            "depends_on": clean_deps,
            "due_at": clean_due_at,
            "created_at": _utc_now_iso(),
        }
        return task_id

    def get_task(self, task_id: str) -> dict[str, Any]:
        """Return a copy of the task record, or raise ``KeyError`` if unknown."""
        return self._copy(self._record(task_id))

    def update_task(self, task_id: str, **fields: Any) -> dict[str, Any]:
        """Update allowed fields on an existing task and return the updated copy.

        Validation happens before mutation: if anything is invalid (bad priority or
        ``due_at``, an unknown dependency, or a dependency cycle) the stored record
        is left exactly as it was.
        """
        task = self._record(task_id)

        unknown = set(fields) - _UPDATABLE_FIELDS
        if unknown:
            raise ValueError(f"cannot update unknown field(s): {sorted(unknown)}")

        # Build the validated patch first; only then commit it to the record.
        patch: dict[str, Any] = {}
        if "title" in fields:
            if not isinstance(fields["title"], str) or not fields["title"]:
                raise ValueError("title must be a non-empty string")
            patch["title"] = fields["title"]
        if "priority" in fields:
            patch["priority"] = _validate_priority(fields["priority"])
        if "due_at" in fields:
            patch["due_at"] = _validate_due_at(fields["due_at"])
        if "tags" in fields:
            patch["tags"] = _normalise_str_list(fields["tags"], "tags")
        if "depends_on" in fields:
            deps = _normalise_str_list(fields["depends_on"], "depends_on")
            self._validate_dependency_ids(deps)
            self._ensure_acyclic(task_id, deps)
            patch["depends_on"] = deps

        task.update(patch)
        return self._copy(task)

    def delete_task(self, task_id: str) -> None:
        """Delete a task, refusing while any other task still depends on it."""
        self._record(task_id)
        dependents = [t["id"] for t in self._tasks.values() if task_id in t["depends_on"]]
        if dependents:
            raise ValueError(f"cannot delete {task_id!r}: still required by {dependents}")
        del self._tasks[task_id]

    def set_status(self, task_id: str, status: str) -> dict[str, Any]:
        """Transition a task to ``todo``/``doing``/``done`` and return its copy."""
        self._record(task_id)
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status {status!r}; expected one of {VALID_STATUSES}")
        self._tasks[task_id]["status"] = status
        return self._copy(self._tasks[task_id])

    # ── queries ───────────────────────────────────────────────────────────────

    def list_tasks(
        self,
        *,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        tag: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Return tasks matching every supplied filter, priority-descending.

        Ties on priority preserve creation order (the dict's insertion order plus a
        stable sort).  With no filters, every task is returned.
        """
        if status is not None and status not in VALID_STATUSES:
            raise ValueError(f"invalid status {status!r}; expected one of {VALID_STATUSES}")
        if priority is not None:
            priority = _validate_priority(priority)

        matched: list[dict[str, Any]] = []
        for task in self._tasks.values():
            if status is not None and task["status"] != status:
                continue
            if priority is not None and task["priority"] != priority:
                continue
            if tag is not None and tag not in task["tags"]:
                continue
            matched.append(self._copy(task))

        matched.sort(key=lambda t: -t["priority"])
        return matched

    def ready_tasks(self) -> list[dict[str, Any]]:
        """Return not-done tasks whose dependencies are all done.

        Ordered priority-descending for the same reason as ``list_tasks``.
        """
        ready: list[dict[str, Any]] = []
        for task in self._tasks.values():
            if task["status"] == "done":
                continue
            if all(self._tasks[dep]["status"] == "done" for dep in task["depends_on"]):
                ready.append(self._copy(task))
        ready.sort(key=lambda t: -t["priority"])
        return ready

    # ── persistence ───────────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        """Serialise the manager to ``path`` as a JSON object (stdlib ``json``)."""
        payload = {
            "version": 1,
            "tasks": [self._copy(t) for t in self._tasks.values()],
        }
        Path(path).write_text(json.dumps(payload, indent=2))

    @classmethod
    def load(cls, path: str) -> "TaskManager":
        """Reconstruct a manager from a file written by :meth:`save`."""
        data = json.loads(Path(path).read_text())
        records = data.get("tasks", []) if isinstance(data, dict) else data
        return cls(tasks=list(records))
