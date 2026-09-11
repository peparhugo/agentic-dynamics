"""Core implementation of the ``taskman`` package.

Design summary (the "why" behind the shape of this module):

* **Single source of truth.** A :class:`TaskManager` owns one ordered mapping of
  ``task_id -> _Task``. Every public method reads or writes only through that mapping, so
  validation and mutation happen in one place and an operation that fails validation can be
  made atomic simply by validating before touching the mapping.
* **Dataclass records, dict-facing API.** Internally a task is a frozen-ish dataclass
  (:class:`_Task`) — explicit fields, no "stringly typed" dict lookups inside the logic. The
  public contract (and the JSON on disk) speaks plain dicts, so :meth:`_Task.to_dict`
  converts at the boundary. Returning a *copy* keeps callers from mutating internal state
  through the returned dict.
* **Explicit creation order for stable ties.** ``list_tasks`` orders by priority descending
  and, on ties, by creation order. Python's sort is stable, but relying on dict insertion
  order would couple the ordering rule to the container; instead every task carries a
  monotonic ``_seq`` that is persisted and restored, making the tie-break explicit and
  round-trip safe.
* **Cycle detection as reachability.** The dependency graph is kept acyclic as an invariant.
  Adding a new task can never create a cycle (a brand-new node has no inbound edges), so only
  ``update_task`` has to check. The check is a DFS from the proposed dependencies looking for
  a path back to the task being edited; if one exists the update is rejected *before* any
  state is written, which is what "leaves state unchanged" demands.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = ["TaskManager", "VALID_STATUSES", "MIN_PRIORITY", "MAX_PRIORITY"]

#: The only statuses the contract recognises. Kept as a tuple so it is immutable and ordered.
VALID_STATUSES: tuple[str, ...] = ("todo", "doing", "done")

#: Inclusive priority bounds (1 = highest urgency, 5 = lowest).
MIN_PRIORITY = 1
MAX_PRIORITY = 5

#: Default priority assigned when the caller does not supply one.
DEFAULT_PRIORITY = 3

#: Schema tag written into saved files; lets a future loader detect incompatible payloads.
SCHEMA_VERSION = 1


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string.

    A helper (rather than an inline call) keeps every timestamp produced by the manager in a
    single, consistently formatted place.
    """
    return datetime.now(timezone.utc).isoformat()


def _validate_priority(priority: Any) -> int:
    """Validate and return ``priority``.

    Raises:
        ValueError: if ``priority`` is not an integer inside the inclusive 1..5 range.
            ``bool`` is rejected explicitly even though it subclasses ``int``, because
            ``priority=True`` is almost certainly a caller mistake and should be loud.
    """
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError(
            f"priority must be an int in {MIN_PRIORITY}..{MAX_PRIORITY}, got {priority!r}"
        )
    if not (MIN_PRIORITY <= priority <= MAX_PRIORITY):
        raise ValueError(f"priority must be in {MIN_PRIORITY}..{MAX_PRIORITY}, got {priority!r}")
    return priority


def _validate_status(status: Any) -> str:
    """Validate and return ``status``.

    Raises:
        ValueError: if ``status`` is not one of :data:`VALID_STATUSES`.
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
    return status


def _validate_due_at(due_at: Any) -> str | None:
    """Validate ``due_at`` and return the value to store.

    ``None`` is allowed and preserved. A non-``None`` value must be a string parseable by
    :func:`datetime.datetime.fromisoformat`; the *original string* is what gets stored so the
    exact caller-supplied representation survives a round-trip (the contract compares the
    stored value to the input string literally).

    Raises:
        ValueError: if the value is neither ``None`` nor a parseable ISO-8601 string.
    """
    if due_at is None:
        return None
    if not isinstance(due_at, str):
        raise ValueError(f"due_at must be an ISO-8601 string or None, got {due_at!r}")
    try:
        datetime.fromisoformat(due_at)
    except ValueError as exc:  # re-raise with context; fromisoformat's own message is terse
        raise ValueError(f"due_at is not a parseable ISO-8601 date: {due_at!r}") from exc
    return due_at


def _normalize_str_list(values: Iterable[str] | None, *, field_name: str) -> list[str]:
    """Return a fresh list for a list-typed field, turning ``None`` into ``[]``.

    A defensive copy is taken so the caller's list object can never be aliased into internal
    state. Elements are coerced to ``str`` to guarantee JSON-serialisability.
    """
    if values is None:
        return []
    return [str(v) for v in values]


@dataclass
class _Task:
    """Internal record for one task.

    Attributes mirror the public dict shape, plus ``_seq`` which is an internal-only monotonic
    creation counter used purely as the deterministic tie-breaker for equal priorities.
    """

    id: str
    title: str
    status: str = "todo"
    priority: int = DEFAULT_PRIORITY
    tags: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    due_at: str | None = None
    created_at: str = ""
    _seq: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Return a public, detached copy of this task.

        Nested lists are copied too, so a caller mutating the returned dict cannot corrupt
        the manager's state.
        """
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "priority": self.priority,
            "tags": list(self.tags),
            "depends_on": list(self.depends_on),
            "due_at": self.due_at,
            "created_at": self.created_at,
        }


class TaskManager:
    """In-memory task store with an explicit dependency graph and JSON persistence.

    The manager deliberately keeps *all* logic (validation, ordering, cycle detection) in this
    one class. The public surface is intentionally tiny: :meth:`add_task`, :meth:`get_task`,
    :meth:`update_task`, :meth:`delete_task`, :meth:`set_status`, :meth:`list_tasks`,
    :meth:`ready_tasks`, :meth:`save`, and :meth:`load`.
    """

    def __init__(self) -> None:
        """Create an empty manager with a zeroed creation counter."""
        self._tasks: dict[str, _Task] = {}
        self._seq = 0

    # ------------------------------------------------------------------ lookups

    def _require(self, task_id: str) -> _Task:
        """Return the stored task for ``task_id`` or raise ``KeyError``.

        Centralising this means every method that takes an id reports an unknown id in exactly
        the same way (a bare ``KeyError`` carrying the offending id).
        """
        try:
            return self._tasks[task_id]
        except KeyError:
            raise KeyError(task_id) from None

    def _validate_dependencies(self, depends_on: list[str]) -> list[str]:
        """Validate that every dependency id exists; return the list unchanged.

        Unknown dependency ids are a caller error (``ValueError``), distinct from a lookup of
        an unknown *task* (``KeyError``) — the contract draws this line.
        """
        for dep_id in depends_on:
            if dep_id not in self._tasks:
                raise ValueError(f"unknown dependency id: {dep_id!r}")
        return depends_on

    def _would_create_cycle(self, task_id: str, proposed_deps: list[str]) -> bool:
        """Return ``True`` if giving ``task_id`` the ``proposed_deps`` would close a cycle.

        The check is a depth-first search over the *existing* dependency edges starting from
        each proposed dependency. Because the stored graph is acyclic by construction, a cycle
        can only appear if the edited task is reachable from one of its own proposed
        dependencies. An iterative stack is used so long chains cannot hit Python's recursion
        limit.
        """
        stack = list(proposed_deps)
        seen: set[str] = set()
        while stack:
            current = stack.pop()
            if current == task_id:
                return True
            if current in seen:
                continue
            seen.add(current)
            stack.extend(self._tasks[current].depends_on)
        return False

    # ------------------------------------------------------------------ mutations

    def add_task(
        self,
        title: str,
        *,
        priority: int = DEFAULT_PRIORITY,
        tags: Iterable[str] | None = None,
        depends_on: Iterable[str] | None = None,
        due_at: str | None = None,
    ) -> str:
        """Create a task and return its freshly minted unique id.

        Validation happens before the task is inserted, so a rejected ``add_task`` leaves the
        store exactly as it was. A newly created node cannot participate in a cycle (it has no
        inbound edges yet), so only dependency *existence* needs checking here.
        """
        priority = _validate_priority(priority)
        due_at = _validate_due_at(due_at)
        deps = self._validate_dependencies(_normalize_str_list(depends_on, field_name="depends_on"))

        self._seq += 1
        task_id = uuid.uuid4().hex
        self._tasks[task_id] = _Task(
            id=task_id,
            title=str(title),
            status="todo",
            priority=priority,
            tags=_normalize_str_list(tags, field_name="tags"),
            depends_on=list(deps),
            due_at=due_at,
            created_at=_utc_now_iso(),
            _seq=self._seq,
        )
        return task_id

    def get_task(self, task_id: str) -> dict[str, Any]:
        """Return a detached copy of the task's public fields.

        Raises:
            KeyError: if ``task_id`` is unknown.
        """
        return self._require(task_id).to_dict()

    def update_task(self, task_id: str, **changes: Any) -> None:
        """Apply ``changes`` to a task atomically.

        Supported fields: ``title``, ``priority``, ``tags``, ``depends_on``, ``due_at``, and
        ``status``. All candidate values are validated *first*; only if every check passes is
        any field written. That ordering is what makes the cycle-rejection guarantee
        ("leaves state unchanged") hold.

        Raises:
            KeyError: if ``task_id`` is unknown.
            ValueError: on an invalid field value, an unknown dependency, or a cycle.
            TypeError: if an unsupported field name is supplied.
        """
        task = self._require(task_id)

        # Validate into local candidates first — no mutation until the very end.
        new_title = str(changes["title"]) if "title" in changes else task.title
        new_priority = (
            _validate_priority(changes["priority"]) if "priority" in changes else task.priority
        )
        new_tags = (
            _normalize_str_list(changes["tags"], field_name="tags")
            if "tags" in changes
            else list(task.tags)
        )
        deps = (
            self._normalize_and_validate_deps(changes["depends_on"])
            if "depends_on" in changes
            else list(task.depends_on)
        )
        new_due_at = _validate_due_at(changes["due_at"]) if "due_at" in changes else task.due_at
        new_status = _validate_status(changes["status"]) if "status" in changes else task.status

        # A cycle is only possible once we actually intend to change the dependency set.
        if "depends_on" in changes and self._would_create_cycle(task_id, deps):
            raise ValueError(f"dependency update for {task_id!r} would create a cycle")

        unknown = set(changes) - {"title", "priority", "tags", "depends_on", "due_at", "status"}
        if unknown:
            raise TypeError(f"unsupported task field(s): {sorted(unknown)}")

        # Commit point: every value is validated, so these assignments cannot fail.
        task.title = new_title
        task.priority = new_priority
        task.tags = new_tags
        task.depends_on = deps
        task.due_at = new_due_at
        task.status = new_status

    def _normalize_and_validate_deps(self, depends_on: Iterable[str] | None) -> list[str]:
        """Normalise a dependency iterable and confirm every id exists."""
        return self._validate_dependencies(_normalize_str_list(depends_on, field_name="depends_on"))

    def set_status(self, task_id: str, status: str) -> None:
        """Set a task's status after validating it.

        Raises:
            KeyError: if ``task_id`` is unknown.
            ValueError: if ``status`` is not one of :data:`VALID_STATUSES`.
        """
        task = self._require(task_id)
        task.status = _validate_status(status)

    def delete_task(self, task_id: str) -> None:
        """Delete a task, refusing while other tasks depend on it.

        Raises:
            KeyError: if ``task_id`` is unknown.
            ValueError: if any surviving task lists ``task_id`` in ``depends_on``.
        """
        self._require(task_id)
        dependents = [t.id for t in self._tasks.values() if task_id in t.depends_on]
        if dependents:
            raise ValueError(f"cannot delete {task_id!r}: still required by {dependents}")
        del self._tasks[task_id]

    # ------------------------------------------------------------------ queries

    def _ordered(self) -> list[_Task]:
        """Return all stored tasks in the canonical listing order.

        Priority descending, then creation order ascending. The sort key is explicit
        (``(-priority, _seq)``) rather than relying on sort stability over insertion order.
        """
        return sorted(self._tasks.values(), key=lambda t: (-t.priority, t._seq))

    def list_tasks(
        self,
        *,
        status: str | None = None,
        priority: int | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return tasks matching the supplied filters, in canonical order.

        All filters are optional and combine with AND. ``tag`` matches by membership in the
        task's tag list. Invalid ``status``/``priority`` values are treated as ordinary
        filters that simply match nothing, rather than raising — filtering is a read.
        """
        results = [
            t
            for t in self._ordered()
            if (status is None or t.status == status)
            and (priority is None or t.priority == priority)
            and (tag is None or tag in t.tags)
        ]
        return [t.to_dict() for t in results]

    def ready_tasks(self) -> list[dict[str, Any]]:
        """Return not-done tasks whose dependencies are all ``done``.

        The result honours the same canonical order as :meth:`list_tasks`, so "what should I
        work on next" reads consistently with the rest of the API.
        """
        ready = [
            t
            for t in self._ordered()
            if t.status != "done" and all(self._tasks[dep].status == "done" for dep in t.depends_on)
        ]
        return [t.to_dict() for t in ready]

    # ------------------------------------------------------------------ persistence

    def save(self, path: str) -> None:
        """Serialise the manager to a JSON file at ``path``.

        The payload is a dict (the contract checks ``isinstance(..., dict)``) carrying the
        schema version and every task as a flat record, including the internal creation
        sequence so ordering survives the round-trip.
        """
        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "tasks": [
                {
                    **task.to_dict(),
                    "_seq": task._seq,
                }
                for task in self._ordered()
            ],
        }
        Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True))

    @classmethod
    def load(cls, path: str) -> TaskManager:
        """Load a manager previously written by :meth:`save`.

        Raises:
            ValueError: if the file is not valid JSON or lacks the expected shape.
        """
        try:
            payload = json.loads(Path(path).read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"could not load taskman state from {path!r}") from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("tasks"), list):
            raise ValueError(f"malformed taskman state in {path!r}")

        manager = cls()
        max_seq = 0
        for record in payload["tasks"]:
            task = _Task(
                id=str(record["id"]),
                title=str(record["title"]),
                status=str(record.get("status", "todo")),
                priority=int(record.get("priority", DEFAULT_PRIORITY)),
                tags=_normalize_str_list(record.get("tags"), field_name="tags"),
                depends_on=_normalize_str_list(record.get("depends_on"), field_name="depends_on"),
                due_at=record.get("due_at"),
                created_at=str(record.get("created_at", "")),
                _seq=int(record.get("_seq", 0)),
            )
            manager._tasks[task.id] = task
            max_seq = max(max_seq, task._seq)
        # Resume the counter above every restored sequence so new tasks still sort last.
        manager._seq = max_seq
        return manager
