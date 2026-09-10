"""Core implementation of the :class:`TaskManager`.

Design C from ``DESIGN.md`` is implemented here. The four axes worth calling out up front:

* **Data model** — every task is an immutable :class:`Task` (frozen dataclass). The manager
  owns derived structure only: ``_tasks`` (id -> Task), ``_dependents`` (dependency id -> the set
  of task ids that depend on it) and ``_order`` (ids sorted for display). Public reads build a
  fresh ``dict`` every time, so a caller can never mutate internal state through a returned value.
* **Ordering** — ``_order`` is maintained continuously sorted by ``(-priority, seq)`` via
  ``bisect.insort``. ``seq`` is a monotonic creation counter, chosen over relying on dict
  insertion order so the "ties keep creation order" rule survives persistence.
* **Persistence** — a versioned canonical snapshot (``schema: taskman/v1``). ``load`` rebuilds
  the adjacency and ordering indexes from the stored records; it never trusts stored edges.
* **Cycle detection** — Kahn's algorithm (topological elimination) over the *candidate* graph,
  run to completion *before* any mutation. A rejected edit therefore cannot leave partial state.

Only the standard library is imported.
"""

from __future__ import annotations

import bisect
import json
import uuid
from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional

#: Statuses the contract allows. Membership is validated on every status write.
VALID_STATUSES: tuple[str, ...] = ("todo", "doing", "done")

#: Inclusive priority range. The contract validates this on ``add_task``/``update_task``.
MIN_PRIORITY: int = 1
MAX_PRIORITY: int = 5

#: Default priority applied when the caller does not supply one.
DEFAULT_PRIORITY: int = 3

#: Persistence envelope version. Bumping this is the signal that a saved file's shape changed.
SCHEMA_VERSION: str = "taskman/v1"


@dataclass(frozen=True)
class Task:
    """An immutable task record.

    Frozen-ness is deliberate: a mutation is expressed by building a *new* record with
    :func:`dataclasses.replace` and swapping it in. That keeps a rejected update trivially
    side-effect free — nothing is replaced until every validation has passed.

    ``tags`` and ``depends_on`` are stored as tuples (hashable, immutable); the public
    :meth:`to_dict` converts them to lists to match the JSON/dict shape the contract asserts.
    """

    id: str
    title: str
    status: str
    priority: int
    tags: tuple[str, ...]
    depends_on: tuple[str, ...]
    due_at: Optional[str]
    created_at: str
    #: Monotonic creation counter; the explicit tie-break for equal-priority listing.
    seq: int

    def to_dict(self) -> dict[str, Any]:
        """Return a fresh public ``dict`` for this task.

        ``seq`` is an internal ordering detail and is intentionally omitted from the public
        shape. Lists are rebuilt on every call so mutating a returned value is harmless.
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
    """A collection of dependent, prioritised tasks.

    Example::

        manager = TaskManager()
        first = manager.add_task("write docs", priority=4, tags=["docs"])
        second = manager.add_task("review docs", depends_on=[first])
        manager.set_status(first, "done")
        assert [t["id"] for t in manager.ready_tasks()] == [second]
    """

    #: The persisted envelope version for :meth:`save` / :meth:`load`.
    SCHEMA_VERSION = SCHEMA_VERSION

    def __init__(self) -> None:
        # Primary record store: id -> immutable Task.
        self._tasks: dict[str, Task] = {}
        # Reverse adjacency: dependency id -> set of ids that depend on it. Used both to
        # refuse deleting a task that others depend on and to clean up edges on delete.
        self._dependents: dict[str, set[str]] = {}
        # Display order: task ids sorted by (-priority, seq), maintained incrementally.
        self._order: list[str] = []
        # Monotonic creation counter, handed to each new Task as its ``seq``.
        self._next_seq: int = 0

    # ------------------------------------------------------------------ helpers

    def _order_key(self, task_id: str) -> tuple[int, int]:
        """Sort key for the display order: priority descending, creation order ascending."""
        task = self._tasks[task_id]
        return (-task.priority, task.seq)

    def _insert_index(self, task_id: str) -> None:
        """Insert ``task_id`` into ``_order`` at its sorted position.

        ``_tasks[task_id]`` must already hold the record whose priority/seq define its slot.
        A linear scan would also work, but maintaining the invariant incrementally is the
        ordering choice made in Design C.
        """
        bisect.insort(self._order, task_id, key=self._order_key)

    @staticmethod
    def _new_id() -> str:
        """Return a fresh, process-globally unique identifier for a task."""
        return uuid.uuid4().hex

    @staticmethod
    def _check_priority(priority: Any) -> int:
        """Validate a priority, returning it unchanged (or raising ``ValueError``).

        ``bool`` is rejected explicitly even though it is a subclass of ``int``: accepting
        ``True`` as priority 1 would be a silent surprise for a caller who meant a flag.
        """
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ValueError(f"priority must be an integer in {MIN_PRIORITY}..{MAX_PRIORITY}")
        if not MIN_PRIORITY <= priority <= MAX_PRIORITY:
            raise ValueError(f"priority must be in {MIN_PRIORITY}..{MAX_PRIORITY}, got {priority}")
        return priority

    @staticmethod
    def _check_status(status: Any) -> str:
        """Validate a status against :data:`VALID_STATUSES`."""
        if status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
        return status

    @staticmethod
    def _check_due_at(due_at: Any) -> Optional[str]:
        """Validate an ISO-8601 due date, returning the original string.

        The contract round-trips the exact string the caller supplied, so we validate by
        parsing but store the original text. A trailing ``Z`` is normalised only for the parse
        (Python 3.10's ``fromisoformat`` does not accept it), never for storage.
        """
        if due_at is None:
            return None
        if not isinstance(due_at, str):
            raise ValueError("due_at must be an ISO-8601 string or None")
        candidate = due_at[:-1] + "+00:00" if due_at.endswith("Z") else due_at
        try:
            datetime.fromisoformat(candidate)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"due_at is not a parseable ISO-8601 timestamp: {due_at!r}") from exc
        return due_at

    @staticmethod
    def _check_title(title: Any) -> str:
        """Validate that a title is a string."""
        if not isinstance(title, str):
            raise ValueError("title must be a string")
        return title

    @staticmethod
    def _normalize_tags(tags: Any) -> tuple[str, ...]:
        """Normalise ``tags`` into a tuple of strings.

        ``None`` means "no tags". A bare string is rejected rather than exploded into
        single-character tags, which is the classic iterable-string bug.
        """
        if tags is None:
            return ()
        if isinstance(tags, str):
            raise ValueError("tags must be an iterable of strings, not a single string")
        normalized: list[str] = []
        for tag in tags:
            if not isinstance(tag, str):
                raise ValueError("each tag must be a string")
            if tag not in normalized:
                normalized.append(tag)
        return tuple(normalized)

    def _normalize_depends_on(self, depends_on: Any) -> tuple[str, ...]:
        """Validate dependency ids against the current task set, preserving order.

        Unknown ids raise ``ValueError`` immediately. Duplicates are collapsed while preserving
        first-seen order. This runs before cycle detection so Kahn always sees known nodes.
        """
        if depends_on is None:
            return ()
        if isinstance(depends_on, str):
            raise ValueError("depends_on must be an iterable of task ids, not a single string")
        normalized: list[str] = []
        for dependency in depends_on:
            if dependency not in self._tasks:
                raise ValueError(f"unknown dependency id: {dependency!r}")
            if dependency not in normalized:
                normalized.append(dependency)
        return tuple(normalized)

    # ------------------------------------------------------------------ cycle check

    @staticmethod
    def _has_cycle(candidate: Mapping[str, tuple[str, ...]]) -> bool:
        """Return ``True`` if the dependency graph described by ``candidate`` has a cycle.

        Kahn's algorithm: repeatedly remove nodes with in-degree zero (no unmet dependencies).
        Every removed node is a task whose dependencies were all already removed, i.e. a valid
        processing order. If some node can never be removed, it is part of, or downstream of, a
        directed cycle. This is iterative, so it is immune to the recursion-depth limit that a
        naive DFS would hit on a long chain.

        ``candidate`` maps every task id to its *proposed* dependency tuple.
        """
        # In-degree of a task == number of dependencies it still has outstanding.
        in_degree: dict[str, int] = {task_id: len(deps) for task_id, deps in candidate.items()}
        # Reverse edges, needed to decrement a dependent when its dependency is removed.
        reverse: dict[str, list[str]] = {task_id: [] for task_id in candidate}
        for task_id, deps in candidate.items():
            for dependency in deps:
                reverse[dependency].append(task_id)

        ready: deque[str] = deque(task_id for task_id, degree in in_degree.items() if degree == 0)
        eliminated = 0
        while ready:
            task_id = ready.popleft()
            eliminated += 1
            for dependent in reverse[task_id]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    ready.append(dependent)

        return eliminated != len(candidate)

    def _candidate_graph(self, *, overrides: Mapping[str, tuple[str, ...]] | None = None) -> dict:
        """Build the full id -> dependency map, substituting any ``overrides``."""
        overrides = overrides or {}
        return {
            task_id: overrides.get(task_id, task.depends_on)
            for task_id, task in self._tasks.items()
        }

    # ------------------------------------------------------------------ public API

    def add_task(
        self,
        title: str,
        *,
        priority: int = DEFAULT_PRIORITY,
        tags: Optional[Iterable[str]] = None,
        depends_on: Optional[Iterable[str]] = None,
        due_at: Optional[str] = None,
    ) -> str:
        """Create a task and return its unique id.

        Defaults: status ``todo``, priority ``3``, no tags, no dependencies, no due date.
        Raises ``ValueError`` on an invalid priority/due date, an unknown dependency, or (via
        the candidate graph) a dependency cycle.
        """
        title = self._check_title(title)
        priority = self._check_priority(priority)
        due_at = self._check_due_at(due_at)
        normalized_tags = self._normalize_tags(tags)
        normalized_deps = self._normalize_depends_on(depends_on)

        task_id = self._new_id()
        # A brand-new task cannot be depended upon yet, but running the same Kahn check keeps
        # every write on one validation path and future-proofs the order of checks.
        candidate = self._candidate_graph(overrides={task_id: normalized_deps})
        if self._has_cycle(candidate):
            raise ValueError("dependency cycle detected")

        task = Task(
            id=task_id,
            title=title,
            status="todo",
            priority=priority,
            tags=normalized_tags,
            depends_on=normalized_deps,
            due_at=due_at,
            created_at=datetime.now(timezone.utc).isoformat(),
            seq=self._next_seq,
        )
        # Validate-then-commit: only now does any state change.
        self._tasks[task_id] = task
        for dependency in task.depends_on:
            self._dependents.setdefault(dependency, set()).add(task_id)
        self._insert_index(task_id)
        self._next_seq += 1
        return task_id

    def get_task(self, task_id: str) -> dict[str, Any]:
        """Return a fresh public dict for ``task_id``; raise ``KeyError`` if unknown."""
        if task_id not in self._tasks:
            raise KeyError(f"unknown task id: {task_id!r}")
        return self._tasks[task_id].to_dict()

    def update_task(self, task_id: str, **fields: Any) -> None:
        """Update mutable fields of an existing task.

        Accepted fields: ``title``, ``priority``, ``tags``, ``depends_on``, ``due_at`` and
        ``status``. Unknown ids raise ``KeyError``; invalid values, unknown dependency ids and
        dependency cycles raise ``ValueError``.

        All validation happens against a *candidate* record before anything is written, so a
        rejected update leaves the store exactly as it was.
        """
        if task_id not in self._tasks:
            raise KeyError(f"unknown task id: {task_id!r}")
        current = self._tasks[task_id]

        allowed = {"title", "priority", "tags", "depends_on", "due_at", "status"}
        unknown = set(fields) - allowed
        if unknown:
            raise TypeError(f"unexpected update field(s): {', '.join(sorted(unknown))}")

        # Validate scalars first; fall back to the current value when a field is absent.
        title = self._check_title(fields["title"]) if "title" in fields else current.title
        priority = (
            self._check_priority(fields["priority"]) if "priority" in fields else current.priority
        )
        due_at = self._check_due_at(fields["due_at"]) if "due_at" in fields else current.due_at
        status = self._check_status(fields["status"]) if "status" in fields else current.status
        tags = self._normalize_tags(fields["tags"]) if "tags" in fields else current.tags

        if "depends_on" in fields:
            depends_on = self._normalize_depends_on(fields["depends_on"])
        else:
            depends_on = current.depends_on

        # Cycle check against the whole proposed graph — the structural part of the contract.
        if depends_on != current.depends_on:
            candidate = self._candidate_graph(overrides={task_id: depends_on})
            if self._has_cycle(candidate):
                raise ValueError("dependency cycle detected")

        updated = replace(
            current,
            title=title,
            priority=priority,
            due_at=due_at,
            status=status,
            tags=tags,
            depends_on=depends_on,
        )

        # Commit. Edges only changed if depends_on changed.
        if depends_on != current.depends_on:
            for dependency in current.depends_on:
                self._dependents.get(dependency, set()).discard(task_id)
            for dependency in updated.depends_on:
                self._dependents.setdefault(dependency, set()).add(task_id)
        self._tasks[task_id] = updated

        # Priority is the only field affecting display order; refresh the slot if it moved.
        if priority != current.priority:
            self._order.remove(task_id)
            self._insert_index(task_id)

    def delete_task(self, task_id: str) -> None:
        """Delete a task.

        Raises ``KeyError`` for an unknown id, and ``ValueError`` if any other task depends on
        this one — a dangling dependency is refused rather than silently rewritten.
        """
        if task_id not in self._tasks:
            raise KeyError(f"unknown task id: {task_id!r}")
        dependents = self._dependents.get(task_id)
        if dependents:
            raise ValueError(
                f"cannot delete {task_id!r}: {len(dependents)} task(s) still depend on it"
            )
        task = self._tasks.pop(task_id)
        self._order.remove(task_id)
        # Detach this task from the reverse index of each task it depended on.
        for dependency in task.depends_on:
            self._dependents.get(dependency, set()).discard(task_id)
        self._dependents.pop(task_id, None)

    def set_status(self, task_id: str, status: str) -> None:
        """Set a task's status; unknown ids raise ``KeyError``, bad statuses ``ValueError``."""
        if task_id not in self._tasks:
            raise KeyError(f"unknown task id: {task_id!r}")
        validated = self._check_status(status)
        self._tasks[task_id] = replace(self._tasks[task_id], status=validated)

    def list_tasks(
        self,
        *,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        tag: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Return tasks, ordered priority descending with creation order as the tie-break.

        The optional filters are combined with AND semantics; ``None`` means "do not filter".
        """
        results: list[dict[str, Any]] = []
        for task_id in self._order:
            task = self._tasks[task_id]
            if status is not None and task.status != status:
                continue
            if priority is not None and task.priority != priority:
                continue
            if tag is not None and tag not in task.tags:
                continue
            results.append(task.to_dict())
        return results

    def ready_tasks(self) -> list[dict[str, Any]]:
        """Return not-done tasks whose dependencies are all done, in display order.

        A task with no dependencies is ready as soon as it is not done.
        """
        results: list[dict[str, Any]] = []
        for task_id in self._order:
            task = self._tasks[task_id]
            if task.status == "done":
                continue
            if all(self._tasks[dependency].status == "done" for dependency in task.depends_on):
                results.append(task.to_dict())
        return results

    # ------------------------------------------------------------------ persistence

    def save(self, path: str) -> None:
        """Write a versioned JSON snapshot of the manager to ``path``.

        The document stores records in creation order plus the next sequence value. Derived
        indexes are *not* stored: :meth:`load` rebuilds them, so the file cannot encode an
        inconsistent graph.
        """
        document = {
            "schema": self.SCHEMA_VERSION,
            "next_seq": self._next_seq,
            "tasks": [
                {
                    "id": task.id,
                    "title": task.title,
                    "status": task.status,
                    "priority": task.priority,
                    "tags": list(task.tags),
                    "depends_on": list(task.depends_on),
                    "due_at": task.due_at,
                    "created_at": task.created_at,
                    "seq": task.seq,
                }
                for task in sorted(self._tasks.values(), key=lambda t: t.seq)
            ],
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2, sort_keys=True)
            handle.write("\n")

    @classmethod
    def load(cls, path: str) -> "TaskManager":
        """Load a snapshot written by :meth:`save` and rebuild all derived indexes.

        Raises ``ValueError`` if the document is missing or carries an unrecognised schema.
        """
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
        if not isinstance(document, dict) or document.get("schema") != cls.SCHEMA_VERSION:
            raise ValueError(f"not a {cls.SCHEMA_VERSION} snapshot: {path!r}")

        manager = cls()
        for record in document.get("tasks", []):
            task = Task(
                id=record["id"],
                title=record["title"],
                status=record["status"],
                priority=record["priority"],
                tags=tuple(record.get("tags", ())),
                depends_on=tuple(record.get("depends_on", ())),
                due_at=record.get("due_at"),
                created_at=record["created_at"],
                seq=int(record.get("seq", manager._next_seq)),
            )
            manager._tasks[task.id] = task
            for dependency in task.depends_on:
                manager._dependents.setdefault(dependency, set()).add(task.id)
            manager._next_seq = max(manager._next_seq, task.seq + 1)

        # Rebuild the display order wholesale; the stored list is never trusted.
        manager._order = sorted(
            manager._tasks,
            key=lambda task_id: (-manager._tasks[task_id].priority, manager._tasks[task_id].seq),
        )
        return manager
