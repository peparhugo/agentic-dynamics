"""The :class:`TaskManager` store and its validation rules.

Design summary (full rationale in ``taskman/DESIGN.md``):

* A task is an immutable :class:`Task` value object.  Nothing ever mutates a
  stored record in place; a state change replaces the record for that id.
* Every mutation validates a **candidate** state *before* committing it.  That
  is what makes "a rejected edit leaves state unchanged" a structural property
  rather than a best-effort rollback: the only assignment to the live mapping
  happens after all checks pass.
* Ordering is derived, never stored: tasks sort by ``(-priority, seq)`` where
  ``seq`` is the creation counter.  This gives priority-descending order with a
  deterministic, stable tie-break on creation order.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

#: Stamp written into saved documents so a format change is detectable.
SCHEMA_ID = "taskman/v1"

#: The statuses the contract recognises.
VALID_STATUSES: tuple[str, ...] = ("todo", "doing", "done")

#: Inclusive priority band.
MIN_PRIORITY = 1
MAX_PRIORITY = 5

#: Sentinel distinguishing "argument omitted" from "argument set to None" in
#: :meth:`TaskManager.update_task` (``due_at=None`` is a legal update value).
_UNSET: Any = object()


@dataclass(frozen=True)
class Task:
    """An immutable task record.

    ``tags`` and ``depends_on`` are stored as tuples so the record is hashable
    and truly immutable; :meth:`to_public` converts them back to the ``list``
    shape the contract exposes, as fresh copies so callers cannot mutate the
    store through a returned value.
    """

    id: str
    title: str
    status: str
    priority: int
    tags: tuple[str, ...]
    depends_on: tuple[str, ...]
    due_at: str | None
    created_at: str
    seq: int

    def to_public(self) -> dict[str, Any]:
        """Project the record to the contract's plain-dict shape (fresh lists)."""
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


def validate_priority(priority: Any) -> int:
    """Return ``priority`` iff it is an int inside the inclusive 1..5 band.

    ``bool`` is rejected explicitly despite being an ``int`` subclass: a caller
    passing ``True``/``False`` meant a flag, not a priority of 1/0.
    """
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError(
            f"priority must be an integer in {MIN_PRIORITY}..{MAX_PRIORITY}, got {priority!r}"
        )
    if not MIN_PRIORITY <= priority <= MAX_PRIORITY:
        raise ValueError(f"priority must be in {MIN_PRIORITY}..{MAX_PRIORITY}, got {priority!r}")
    return priority


def validate_status(status: Any) -> str:
    """Return ``status`` iff it is one of :data:`VALID_STATUSES`."""
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
    return status


def validate_due_at(due_at: Any) -> str | None:
    """Return the ISO-8601 string ``due_at`` iff it parses, else raise ``ValueError``.

    The original string is preserved verbatim (not re-serialised) so a
    save/load round-trip is byte-for-byte for the caller's chosen representation.
    ``None`` means "no due date" and is always allowed.
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


def normalize_list(value: Iterable[str] | str | None, *, field: str) -> tuple[str, ...]:
    """Coerce a tags/dependency argument to a de-duplicated, order-preserving tuple.

    A bare string is treated as one element (``"infra"`` -> ``("infra",)``) so a
    caller who forgets the list does not get a character split.  Duplicates are
    removed while first-seen order is kept, because a task neither depends on nor
    is tagged by the same thing twice.
    """
    if value is None:
        return ()
    if isinstance(value, str):
        value = (value,)
    seen: dict[str, None] = {}
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field} entries must be strings, got {item!r}")
        seen.setdefault(item, None)
    return tuple(seen)


def find_cycle(dependencies: Mapping[str, Sequence[str]]) -> list[str] | None:
    """Return a dependency cycle as a list of ids, or ``None`` when acyclic.

    Edges point from a task to the tasks it depends on, so a cycle is a closed
    walk ``a -> b -> ... -> a``.  An iterative three-colour DFS is used: a child
    that is still GRAY is an ancestor on the current search path, i.e. the
    back-edge that closes the cycle.  Iterative (not recursive) so a deep chain
    cannot hit Python's recursion limit.
    """
    white, gray, black = 0, 1, 2
    colour: dict[str, int] = {}
    for root in dependencies:
        if colour.get(root, white) != white:
            continue
        colour[root] = gray
        # Each stack frame carries the node and an iterator over its children,
        # so the search can resume mid-way without materialising adjacency.
        stack: list[tuple[str, Any]] = [(root, iter(dependencies.get(root, ())))]
        while stack:
            node, children = stack[-1]
            for child in children:
                state = colour.get(child, white)
                if state == gray:
                    # Reconstruct the path node -> ... -> child from the stack.
                    path = [frame[0] for frame in stack]
                    return path[path.index(child) :]
                if state == white:
                    colour[child] = gray
                    stack.append((child, iter(dependencies.get(child, ()))))
                    break
            else:
                # All children explored without closing a cycle: finalise node.
                colour[node] = black
                stack.pop()
    return None


class TaskManager:
    """An in-memory task store with JSON persistence.

    The manager owns a mapping of ``task_id -> Task`` and a monotonic creation
    counter.  All public reads return copies; all writes validate a candidate
    state first and only then commit.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        # Monotonic creation counter: the tie-break for equal priorities.
        self._seq = 0

    # ------------------------------------------------------------------ write

    def add_task(
        self,
        title: str,
        *,
        priority: int = 3,
        tags: Iterable[str] | str | None = None,
        depends_on: Iterable[str] | str | None = None,
        due_at: str | None = None,
    ) -> str:
        """Create a task and return its unique id.

        Validation runs before the record is stored, so a rejected ``add_task``
        leaves the store untouched.  ``depends_on`` must reference existing ids;
        the new id cannot be part of a cycle yet (nothing may depend on it), but
        the candidate state is still cycle-checked for a single code path.
        """
        if not isinstance(title, str):
            raise ValueError(f"title must be a string, got {title!r}")
        validated_priority = validate_priority(priority)
        normalized_tags = normalize_list(tags, field="tags")
        normalized_deps = normalize_list(depends_on, field="depends_on")
        validated_due = validate_due_at(due_at)

        task_id = uuid.uuid4().hex
        self._check_dependencies_exist(normalized_deps)

        created_at = datetime.now().astimezone().isoformat()
        candidate = Task(
            id=task_id,
            title=title,
            status="todo",
            priority=validated_priority,
            tags=normalized_tags,
            depends_on=normalized_deps,
            due_at=validated_due,
            created_at=created_at,
            seq=self._seq,
        )

        # Build and validate the whole prospective graph, then commit atomically.
        candidate_state = dict(self._tasks)
        candidate_state[task_id] = candidate
        self._check_acyclic(candidate_state)

        self._tasks = candidate_state
        self._seq += 1
        return task_id

    def update_task(
        self,
        task_id: str,
        *,
        title: Any = _UNSET,
        priority: Any = _UNSET,
        tags: Any = _UNSET,
        depends_on: Any = _UNSET,
        due_at: Any = _UNSET,
    ) -> None:
        """Update the supplied fields of ``task_id``, leaving others untouched.

        Unknown ids raise ``KeyError`` before any field validation.  The update
        is validated against a candidate state and only committed on success, so
        a rejected edit (e.g. a cycle) leaves the prior state exactly intact.
        """
        current = self._tasks[task_id]  # KeyError for an unknown id, as required.

        new_title = current.title if title is _UNSET else title
        if not isinstance(new_title, str):
            raise ValueError(f"title must be a string, got {new_title!r}")
        new_priority = current.priority if priority is _UNSET else validate_priority(priority)
        new_tags = current.tags if tags is _UNSET else normalize_list(tags, field="tags")
        new_deps = (
            current.depends_on
            if depends_on is _UNSET
            else normalize_list(depends_on, field="depends_on")
        )
        new_due = current.due_at if due_at is _UNSET else validate_due_at(due_at)

        self._check_dependencies_exist(new_deps)

        updated = Task(
            id=current.id,
            title=new_title,
            status=current.status,
            priority=new_priority,
            tags=new_tags,
            depends_on=new_deps,
            due_at=new_due,
            created_at=current.created_at,
            seq=current.seq,
        )
        candidate_state = dict(self._tasks)
        candidate_state[task_id] = updated
        self._check_acyclic(candidate_state)

        self._tasks = candidate_state

    def delete_task(self, task_id: str) -> None:
        """Delete ``task_id`` unless another task still depends on it.

        An unknown id raises ``KeyError``; a still-referenced id raises
        ``ValueError`` and nothing is removed.
        """
        if task_id not in self._tasks:
            raise KeyError(task_id)
        dependents = [task.id for task in self._tasks.values() if task_id in task.depends_on]
        if dependents:
            raise ValueError(
                f"cannot delete task {task_id!r}: still required by {sorted(dependents)!r}"
            )
        self._tasks.pop(task_id)

    def set_status(self, task_id: str, status: str) -> None:
        """Set the status of ``task_id`` (must be one of todo/doing/done)."""
        current = self._tasks[task_id]  # KeyError for an unknown id.
        validated = validate_status(status)
        self._tasks[task_id] = Task(
            id=current.id,
            title=current.title,
            status=validated,
            priority=current.priority,
            tags=current.tags,
            depends_on=current.depends_on,
            due_at=current.due_at,
            created_at=current.created_at,
            seq=current.seq,
        )

    # ------------------------------------------------------------------- read

    def get_task(self, task_id: str) -> dict[str, Any]:
        """Return a copy of the task as a plain dict (unknown id -> ``KeyError``)."""
        return self._tasks[task_id].to_public()

    def list_tasks(
        self,
        *,
        status: str | None = None,
        priority: int | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return tasks matching every supplied filter, priority-descending.

        Ties on priority keep creation order (the left-to-right, top-to-bottom
        reading order a user expects).  Each result is a fresh copy.
        """
        selected = [
            task
            for task in self._tasks.values()
            if (status is None or task.status == status)
            and (priority is None or task.priority == priority)
            and (tag is None or tag in task.tags)
        ]
        return [task.to_public() for task in self._ordered(selected)]

    def ready_tasks(self) -> list[dict[str, Any]]:
        """Return not-done tasks whose dependencies are all done, ordered.

        A task with no dependencies is ready as soon as it is created; a task is
        never "ready" once it is ``done``.  Results are fresh copies.
        """
        ready = [
            task
            for task in self._tasks.values()
            if task.status != "done"
            and all(
                dep in self._tasks and self._tasks[dep].status == "done" for dep in task.depends_on
            )
        ]
        return [task.to_public() for task in self._ordered(ready)]

    # ------------------------------------------------------------ persistence

    def save(self, path: str) -> None:
        """Write the manager to ``path`` as a JSON document.

        The document preserves creation order (a list, not a mapping), the
        creation counter (so ordering survives a load), and a schema stamp.
        """
        payload = {
            "schema": SCHEMA_ID,
            "seq": self._seq,
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
                for task in self._tasks.values()
            ],
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")

    @classmethod
    def load(cls, path: str) -> TaskManager:
        """Reconstruct a manager from a document written by :meth:`save`.

        Loading is a literal rehydration of the persisted state -- no
        re-validation of dependencies or cycles, because the saved document is
        the authority and was already valid when written.  A file that is not a
        taskman document raises ``ValueError`` rather than guessing.
        """
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA_ID:
            raise ValueError(f"{path!r} is not a {SCHEMA_ID} document")

        manager = cls()
        manager._seq = int(payload.get("seq", len(payload.get("tasks", []))))
        for raw in payload.get("tasks", []):
            task = Task(
                id=raw["id"],
                title=raw["title"],
                status=raw["status"],
                priority=raw["priority"],
                tags=tuple(raw.get("tags", [])),
                depends_on=tuple(raw.get("depends_on", [])),
                due_at=raw.get("due_at"),
                created_at=raw["created_at"],
                seq=raw["seq"],
            )
            # Insert in ascending seq so dict order also matches creation order.
            manager._tasks[task.id] = task
        return manager

    # --------------------------------------------------------------- internal

    def _ordered(self, tasks: Iterable[Task]) -> list[Task]:
        """Sort by priority descending, then creation sequence ascending."""
        return sorted(tasks, key=lambda task: (-task.priority, task.seq))

    def _check_dependencies_exist(self, depends_on: Iterable[str]) -> None:
        """Raise ``ValueError`` for the first dependency id that is unknown."""
        for dep in depends_on:
            if dep not in self._tasks:
                raise ValueError(f"unknown dependency id: {dep!r}")

    def _check_acyclic(self, state: Mapping[str, Task]) -> None:
        """Raise ``ValueError`` if the candidate graph contains a dependency cycle."""
        graph = {task_id: task.depends_on for task_id, task in state.items()}
        cycle = find_cycle(graph)
        if cycle is not None:
            raise ValueError(f"dependency cycle detected: {' -> '.join(cycle)}")
