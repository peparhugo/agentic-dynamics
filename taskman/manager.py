"""Core implementation of the ``taskman`` task manager.

Design notes (verbose mode — this package is a public behavioural contract):

* **Immutable records.**  A task is a frozen :class:`Task` dataclass.  A mutation
  never edits a stored record in place; it *replaces* the record for an id.  This
  makes "reject leaves state unchanged" a structural property rather than a
  discipline: an operation that raises has not yet assigned the new mapping.

* **Validate-then-commit.**  Every write builds a candidate mapping, runs all of
  the checks (priority band, parseable ``due_at``, referential integrity of
  dependencies, cycle detection), and only then commits by assignment.

* **Derived ordering.**  Nothing stores a sort key.  Python's ``dict`` preserves
  insertion order, so the mapping itself *is* creation order; ``list_tasks`` uses
  a stable sort on priority, which therefore breaks ties by creation order.

* **Persistence.**  ``save`` writes a small JSON document; ``load`` rehydrates it
  literally, preserving creation order.  The persisted document is the authority,
  so loading does not re-run validation.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

__all__ = ["TaskManager"]

#: The three permitted lifecycle states, in their natural progression order.
VALID_STATUSES: tuple[str, ...] = ("todo", "doing", "done")

#: Inclusive priority band; 5 is the most important, 1 the least.
PRIORITY_MIN = 1
PRIORITY_MAX = 5


@dataclass(frozen=True)
class Task:
    """An immutable task record.

    ``tags`` and ``depends_on`` are tuples so that a record can never be mutated
    through an aliased list.  They are projected back to fresh lists by
    :meth:`to_dict`, which is what the public API returns.
    """

    id: str
    title: str
    status: str = "todo"
    priority: int = 3
    tags: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    due_at: str | None = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Project the record to the plain-dict shape the contract exposes.

        Fresh ``tags``/``depends_on`` lists are created on every call so callers
        cannot mutate manager state through a returned value.
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
    """An in-memory, dependency-aware task board.

    The only state is an ordered mapping ``id -> Task``.  Its insertion order is
    the creation order used as the deterministic tie-break for listing.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    # ------------------------------------------------------------------ reads

    def get_task(self, task_id: str) -> dict[str, Any]:
        """Return a copy of the task with ``task_id``.

        Raises ``KeyError`` for an unknown id.
        """

        return self._require(task_id).to_dict()

    def list_tasks(
        self,
        *,
        status: str | None = None,
        priority: int | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return tasks matching every supplied filter, most important first.

        Exactly one of the three filters may be supplied (or none).  Ordering is
        priority descending; ties keep creation order because the sort is stable
        over the insertion-ordered task mapping.
        """

        selected = [
            task
            for task in self._tasks.values()
            if (status is None or task.status == status)
            and (priority is None or task.priority == priority)
            and (tag is None or tag in task.tags)
        ]
        selected.sort(key=lambda task: -task.priority)
        return [task.to_dict() for task in selected]

    def ready_tasks(self) -> list[dict[str, Any]]:
        """Return not-done tasks whose dependencies are all done.

        Ordered the same way as :meth:`list_tasks` (priority descending, creation
        order for ties) so the ready queue is deterministic.
        """

        done = {task.id for task in self._tasks.values() if task.status == "done"}
        ready = [
            task
            for task in self._tasks.values()
            if task.status != "done" and all(dep in done for dep in task.depends_on)
        ]
        ready.sort(key=lambda task: -task.priority)
        return [task.to_dict() for task in ready]

    # ----------------------------------------------------------------- writes

    def add_task(
        self,
        title: str,
        *,
        priority: int = 3,
        tags: Iterable[str] | None = None,
        depends_on: Iterable[str] | None = None,
        due_at: str | None = None,
    ) -> str:
        """Create a task and return its freshly generated unique id.

        Validation order matters for the contract: bad ``priority``/``due_at`` and
        unknown dependencies all raise ``ValueError`` *without* creating a task.
        """

        checked_priority = self._validate_priority(priority)
        checked_due_at = self._validate_due_at(due_at)
        checked_tags = self._normalize_strings(tags, "tags")
        checked_deps = self._normalize_strings(depends_on, "depends_on")
        self._require_known_dependencies(checked_deps)

        # A brand-new node has no incoming edges, so it cannot close a cycle; the
        # id is generated only once every check has passed.
        task_id = uuid.uuid4().hex
        task = Task(
            id=task_id,
            title=title,
            status="todo",
            priority=checked_priority,
            tags=checked_tags,
            depends_on=checked_deps,
            due_at=checked_due_at,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._tasks[task_id] = task
        return task_id

    def update_task(self, task_id: str, **changes: Any) -> None:
        """Apply ``changes`` to an existing task.

        Raises ``KeyError`` for an unknown id and ``ValueError`` for an unknown
        field or any invalid value.  A rejected update leaves the manager exactly
        as it was, because the replacement record is committed only at the end.
        """

        current = self._require(task_id)
        allowed = {"title", "status", "priority", "tags", "depends_on", "due_at"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"unknown field(s): {', '.join(sorted(unknown))}")

        # Build a validated candidate; nothing is committed until all of it holds.
        candidate_fields: dict[str, Any] = {}
        if "title" in changes:
            candidate_fields["title"] = changes["title"]
        if "status" in changes:
            candidate_fields["status"] = self._validate_status(changes["status"])
        if "priority" in changes:
            candidate_fields["priority"] = self._validate_priority(changes["priority"])
        if "tags" in changes:
            candidate_fields["tags"] = self._normalize_strings(changes["tags"], "tags")
        if "due_at" in changes:
            candidate_fields["due_at"] = self._validate_due_at(changes["due_at"])
        if "depends_on" in changes:
            deps = self._normalize_strings(changes["depends_on"], "depends_on")
            self._require_known_dependencies(deps)
            candidate_fields["depends_on"] = deps

        candidate = replace(current, **candidate_fields)

        # Cycle check over the whole graph with the candidate in place.  Done
        # before assignment so a cycle raises with the original state intact.
        graph = {
            tid: (candidate if tid == task_id else task).depends_on
            for tid, task in self._tasks.items()
        }
        if self._graph_has_cycle(graph):
            raise ValueError(f"update to {task_id!r} would create a dependency cycle")

        self._tasks[task_id] = candidate

    def set_status(self, task_id: str, status: str) -> None:
        """Move a task to one of :data:`VALID_STATUSES`.

        Unknown ids raise ``KeyError``; an unrecognised status raises
        ``ValueError``.
        """

        current = self._require(task_id)
        self._tasks[task_id] = replace(current, status=self._validate_status(status))

    def delete_task(self, task_id: str) -> None:
        """Delete a task, refusing while any other task depends on it.

        Raises ``KeyError`` for an unknown id and ``ValueError`` if a dependent
        exists (the delete would leave a dangling dependency).
        """

        self._require(task_id)
        dependents = [task.id for task in self._tasks.values() if task_id in task.depends_on]
        if dependents:
            raise ValueError(
                f"cannot delete {task_id!r}: still required by {', '.join(sorted(dependents))}"
            )
        del self._tasks[task_id]

    # ----------------------------------------------------------------- persistence

    def save(self, path: str) -> None:
        """Serialise the board to ``path`` as a JSON object.

        The task list is written in creation order and read back the same way, so
        listing order survives a round-trip.
        """

        document = {
            "version": 1,
            "tasks": [task.to_dict() for task in self._tasks.values()],
        }
        Path(path).write_text(json.dumps(document, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "TaskManager":
        """Rehydrate a board written by :meth:`save`.

        The persisted document is the authority, so no re-validation is applied
        on load; creation order is restored from the list order.
        """

        document = json.loads(Path(path).read_text(encoding="utf-8"))
        manager = cls()
        for raw in document.get("tasks", []):
            task = Task(
                id=raw["id"],
                title=raw["title"],
                status=raw["status"],
                priority=raw["priority"],
                tags=tuple(raw.get("tags", ())),
                depends_on=tuple(raw.get("depends_on", ())),
                due_at=raw.get("due_at"),
                created_at=raw.get("created_at", ""),
            )
            manager._tasks[task.id] = task
        return manager

    # ----------------------------------------------------------------- internals

    def _require(self, task_id: str) -> Task:
        """Return the stored record or raise ``KeyError`` for an unknown id."""

        try:
            return self._tasks[task_id]
        except KeyError:
            raise KeyError(task_id) from None

    @staticmethod
    def _validate_priority(priority: Any) -> int:
        """Return ``priority`` if it is an integer within 1..5, else raise."""

        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ValueError(f"priority must be an int, got {priority!r}")
        if not PRIORITY_MIN <= priority <= PRIORITY_MAX:
            raise ValueError(
                f"priority must be in {PRIORITY_MIN}..{PRIORITY_MAX}, got {priority!r}"
            )
        return priority

    @staticmethod
    def _validate_status(status: Any) -> str:
        """Return ``status`` if it is one of :data:`VALID_STATUSES`, else raise."""

        if status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
        return status

    @staticmethod
    def _validate_due_at(due_at: str | None) -> str | None:
        """Validate an optional ISO-8601 timestamp, returning it **verbatim**.

        The contract asserts the stored value equals the caller's string, so we
        validate parseability but never normalise.  ``fromisoformat`` predates the
        ``Z`` suffix in this package's supported Python, so a trailing ``Z`` is
        translated before parsing.
        """

        if due_at is None:
            return None
        if not isinstance(due_at, str):
            raise ValueError(f"due_at must be an ISO-8601 string, got {due_at!r}")
        candidate = due_at[:-1] + "+00:00" if due_at.endswith("Z") else due_at
        try:
            datetime.fromisoformat(candidate)
        except ValueError:
            raise ValueError(f"due_at is not a parseable ISO-8601 timestamp: {due_at!r}") from None
        return due_at

    @staticmethod
    def _normalize_strings(values: Iterable[str] | None, field: str) -> tuple[str, ...]:
        """Coerce an optional iterable of strings to a tuple, rejecting non-strings."""

        if values is None:
            return ()
        try:
            items = tuple(values)
        except TypeError:
            raise ValueError(f"{field} must be an iterable of strings") from None
        for item in items:
            if not isinstance(item, str):
                raise ValueError(f"{field} entries must be strings, got {item!r}")
        return items

    def _require_known_dependencies(self, depends_on: Iterable[str]) -> None:
        """Raise ``ValueError`` if any dependency id is not a known task."""

        unknown = [dep for dep in depends_on if dep not in self._tasks]
        if unknown:
            raise ValueError(f"unknown dependency id(s): {', '.join(sorted(unknown))}")

    @staticmethod
    def _graph_has_cycle(graph: Mapping[str, tuple[str, ...]]) -> bool:
        """Return True if the ``id -> depends_on`` graph contains a cycle.

        Kahn's algorithm: repeatedly remove nodes with no outstanding dependency.
        If some nodes remain, the remainder is (or is downstream of) a cycle.
        Iterative, so a very deep dependency chain cannot exhaust the stack.
        """

        remaining = {node: set(deps & graph.keys()) for node, deps in graph.items()}
        ready = [node for node, deps in remaining.items() if not deps]
        removed = 0
        while ready:
            node = ready.pop()
            removed += 1
            for other, deps in remaining.items():
                if node in deps:
                    deps.discard(node)
                    if not deps:
                        ready.append(other)
        return removed != len(graph)
