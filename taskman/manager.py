"""The :class:`TaskManager` store and every rule the contract fixes.

Design summary
--------------

* **Mutable store, immutable records.** The manager owns ``id -> record`` where
  a record is a plain ``dict``. Once a record is stored it is never mutated;
  every change constructs a *fresh* record. That keeps "candidate state" cheap
  to describe: a candidate is just the current mapping with one entry replaced.
* **Validate a candidate, then commit.** :meth:`TaskManager.add_task` and
  :meth:`TaskManager.update_task` assemble the complete prospective state and run
  every check (priority, due date, dependency existence, acyclicity) against it
  *before* assigning to ``self._tasks``. A rejected edit therefore cannot leave
  a partial write behind -- the cycle test asserts exactly this.
* **Ordering is derived, never stored.** Python ``dict`` keeps insertion order,
  and ``list.sort`` is stable, so sorting by ``-priority`` alone yields
  priority-descending order with creation order as the free tie-break. No
  separate sequence counter is needed.
* **Stdlib only.** :mod:`json`, :mod:`uuid`, :mod:`datetime` -- nothing else.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

#: Stamp written into saved documents so a future format change is detectable
#: (a loader can refuse an alien file instead of half-reading it).
SCHEMA_ID = "taskman/v1"

#: The only statuses the contract recognises.
VALID_STATUSES: tuple[str, ...] = ("todo", "doing", "done")

#: The inclusive priority band.
MIN_PRIORITY = 1
MAX_PRIORITY = 5

#: Sentinel distinguishing "argument omitted" from "argument set to None" in
#: :meth:`TaskManager.update_task` -- ``due_at=None`` is a legal update value and
#: must not be confused with "leave unchanged".
_UNSET: Any = object()


def validate_priority(priority: Any) -> int:
    """Return ``priority`` iff it is an int in the inclusive 1..5 band.

    ``bool`` is rejected explicitly even though it is an ``int`` subclass: a
    caller passing ``True``/``False`` meant a flag, not a priority of 1/0.
    """
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError(f"priority must be an integer, got {priority!r}")
    if not MIN_PRIORITY <= priority <= MAX_PRIORITY:
        raise ValueError(f"priority must be in {MIN_PRIORITY}..{MAX_PRIORITY}, got {priority!r}")
    return priority


def validate_status(status: Any) -> str:
    """Return ``status`` iff it is one of :data:`VALID_STATUSES`."""
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
    return status


def validate_due_at(due_at: Any) -> str | None:
    """Return the ISO-8601 string ``due_at`` iff it parses, else raise.

    The caller's original string is preserved verbatim rather than being
    re-serialised, so a save/load round-trip is byte-for-byte what the caller
    supplied. ``None`` means "no due date" and is always allowed.
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


def normalize_str_list(value: Iterable[str] | str | None, *, field: str) -> list[str]:
    """Coerce a tags/dependency argument to a fresh, de-duplicated list.

    A bare string is treated as one element (``"infra"`` -> ``["infra"]``) so a
    caller who forgets the list does not get a character split. Duplicates are
    removed while first-seen order is kept: a task is neither tagged by nor
    depends on the same thing twice. A fresh list is always returned so the
    caller can never share mutable state with the store.
    """
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    seen: dict[str, None] = {}
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field} entries must be strings, got {item!r}")
        seen.setdefault(item, None)
    return list(seen)


def find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    """Return a dependency cycle (as a list of ids) or ``None`` when acyclic.

    Edges point from a task to the tasks it depends on, so a cycle is a closed
    walk ``a -> b -> ... -> a``. An iterative three-colour DFS is used: a child
    still marked GRAY is an ancestor on the current search path, i.e. the
    back-edge that closes the cycle. Iterative rather than recursive so a deep
    chain cannot hit Python's recursion limit.
    """
    white, gray, black = 0, 1, 2
    colour: dict[str, int] = {}
    for root in graph:
        if colour.get(root, white) != white:
            continue
        colour[root] = gray
        # Each frame carries the node and an iterator over its children, so the
        # walk can resume mid-way without materialising an adjacency list.
        stack: list[tuple[str, Any]] = [(root, iter(graph.get(root, ())))]
        while stack:
            node, children = stack[-1]
            for child in children:
                state = colour.get(child, white)
                if state == gray:
                    # Reconstruct the cycle from the live search path.
                    path = [frame[0] for frame in stack]
                    return path[path.index(child) :]
                if state == white:
                    colour[child] = gray
                    stack.append((child, iter(graph.get(child, ()))))
                    break
            else:
                # Every child explored without closing a cycle: finalise node.
                colour[node] = black
                stack.pop()
    return None


def _public(record: dict[str, Any]) -> dict[str, Any]:
    """Project a stored record to a fresh plain-dict copy for the caller.

    ``tags`` / ``depends_on`` are copied out as new lists so a caller cannot
    mutate the store through a returned value.
    """
    return {
        "id": record["id"],
        "title": record["title"],
        "status": record["status"],
        "priority": record["priority"],
        "tags": list(record["tags"]),
        "depends_on": list(record["depends_on"]),
        "due_at": record["due_at"],
        "created_at": record["created_at"],
    }


class TaskManager:
    """An in-memory task store with JSON persistence.

    The manager owns ``id -> record`` and nothing else; all ordering is derived
    at read time. Every public read returns copies, and every write validates a
    candidate state before committing it.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}

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

        Defaults are the contract's: status ``"todo"``, priority ``3``, empty
        tags/dependencies, and no due date. Validation runs against a candidate
        state before the record is stored, so a rejected ``add_task`` leaves the
        store entirely untouched.
        """
        if not isinstance(title, str):
            raise ValueError(f"title must be a string, got {title!r}")
        validated_priority = validate_priority(priority)
        normalized_tags = normalize_str_list(tags, field="tags")
        normalized_deps = normalize_str_list(depends_on, field="depends_on")
        validated_due = validate_due_at(due_at)

        self._check_dependencies_exist(normalized_deps)

        task_id = uuid.uuid4().hex
        record = {
            "id": task_id,
            "title": title,
            "status": "todo",
            "priority": validated_priority,
            "tags": normalized_tags,
            "depends_on": normalized_deps,
            "due_at": validated_due,
            # A non-empty ISO-8601 timestamp; the contract only requires a
            # truthy string, but a real timestamp keeps the record useful.
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Assemble the whole prospective state, validate it, then commit.
        candidate_state = dict(self._tasks)
        candidate_state[task_id] = record
        self._check_acyclic(candidate_state)

        self._tasks = candidate_state
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
        """Update the supplied fields of ``task_id``; leave the others alone.

        An unknown id raises ``KeyError`` before any field validation. The whole
        edit is validated against a candidate state and only committed on
        success, so a rejected update (e.g. one that would create a cycle)
        leaves the prior state exactly intact.
        """
        current = self._tasks[task_id]  # KeyError for an unknown id, as required.

        new_title = current["title"] if title is _UNSET else title
        if not isinstance(new_title, str):
            raise ValueError(f"title must be a string, got {new_title!r}")
        new_priority = current["priority"] if priority is _UNSET else validate_priority(priority)
        new_tags = current["tags"] if tags is _UNSET else normalize_str_list(tags, field="tags")
        new_deps = (
            current["depends_on"]
            if depends_on is _UNSET
            else normalize_str_list(depends_on, field="depends_on")
        )
        new_due = current["due_at"] if due_at is _UNSET else validate_due_at(due_at)

        self._check_dependencies_exist(new_deps)

        updated = {
            "id": current["id"],
            "title": new_title,
            "status": current["status"],
            "priority": new_priority,
            "tags": new_tags,
            "depends_on": new_deps,
            "due_at": new_due,
            "created_at": current["created_at"],
        }
        candidate_state = dict(self._tasks)
        candidate_state[task_id] = updated
        self._check_acyclic(candidate_state)

        self._tasks = candidate_state

    def delete_task(self, task_id: str) -> None:
        """Delete ``task_id`` unless another task still depends on it.

        An unknown id raises ``KeyError``; a still-referenced id raises
        ``ValueError`` and removes nothing.
        """
        if task_id not in self._tasks:
            raise KeyError(task_id)
        dependents = [
            record["id"] for record in self._tasks.values() if task_id in record["depends_on"]
        ]
        if dependents:
            raise ValueError(
                f"cannot delete task {task_id!r}: still required by {sorted(dependents)!r}"
            )
        del self._tasks[task_id]

    def set_status(self, task_id: str, status: str) -> None:
        """Set the status of ``task_id`` to one of todo/doing/done.

        An unknown id raises ``KeyError``; an invalid status raises
        ``ValueError`` and changes nothing.
        """
        current = self._tasks[task_id]  # KeyError for an unknown id.
        validated = validate_status(status)
        updated = dict(current)
        updated["status"] = validated
        self._tasks[task_id] = updated

    # ------------------------------------------------------------------- read

    def get_task(self, task_id: str) -> dict[str, Any]:
        """Return a copy of the task as a plain dict (unknown id -> ``KeyError``)."""
        return _public(self._tasks[task_id])

    def list_tasks(
        self,
        *,
        status: str | None = None,
        priority: int | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return tasks matching every supplied filter, priority-descending.

        Filters compose conjunctively. Ties on priority keep creation order,
        which falls out of a stable sort over insertion-ordered records. Each
        result is a fresh copy.
        """
        selected = [
            record
            for record in self._tasks.values()
            if (status is None or record["status"] == status)
            and (priority is None or record["priority"] == priority)
            and (tag is None or tag in record["tags"])
        ]
        return [_public(record) for record in self._ordered(selected)]

    def ready_tasks(self) -> list[dict[str, Any]]:
        """Return not-done tasks whose dependencies are all done, ordered.

        A task with no dependencies is ready as soon as it is created; a task is
        never ready once it is ``done``. A dependency id that is somehow missing
        is treated as unsatisfied (defensive; the store normally cannot hold
        one). Results are fresh copies.
        """
        ready = [
            record
            for record in self._tasks.values()
            if record["status"] != "done"
            and all(
                dep in self._tasks and self._tasks[dep]["status"] == "done"
                for dep in record["depends_on"]
            )
        ]
        return [_public(record) for record in self._ordered(ready)]

    # ------------------------------------------------------------ persistence

    def save(self, path: str) -> None:
        """Write the manager to ``path`` as a JSON document.

        Tasks are written as a list in insertion (creation) order, so ordering
        survives a load without a stored sequence counter. A schema stamp lets a
        loader recognise the format.
        """
        payload = {
            "schema": SCHEMA_ID,
            "tasks": [dict(record) for record in self._tasks.values()],
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")

    @classmethod
    def load(cls, path: str) -> TaskManager:
        """Reconstruct a manager from a document written by :meth:`save`.

        Loading is a literal rehydration: the saved document is the authority
        and was already valid when written, so there is no re-validation of
        dependencies or cycles. A file that is not a taskman document raises
        ``ValueError`` rather than being guessed at.
        """
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA_ID:
            raise ValueError(f"{path!r} is not a {SCHEMA_ID} document")

        manager = cls()
        for raw in payload.get("tasks", []):
            manager._tasks[raw["id"]] = {
                "id": raw["id"],
                "title": raw["title"],
                "status": raw["status"],
                "priority": raw["priority"],
                "tags": list(raw.get("tags", [])),
                "depends_on": list(raw.get("depends_on", [])),
                "due_at": raw.get("due_at"),
                "created_at": raw["created_at"],
            }
        return manager

    # --------------------------------------------------------------- internal

    def _ordered(self, records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sort by priority descending; the stable sort keeps creation order."""
        return sorted(records, key=lambda record: -record["priority"])

    def _check_dependencies_exist(self, depends_on: Iterable[str]) -> None:
        """Raise ``ValueError`` for the first dependency id that is unknown."""
        for dep in depends_on:
            if dep not in self._tasks:
                raise ValueError(f"unknown dependency id: {dep!r}")

    def _check_acyclic(self, state: dict[str, dict[str, Any]]) -> None:
        """Raise ``ValueError`` if the candidate graph contains a cycle."""
        graph = {task_id: record["depends_on"] for task_id, record in state.items()}
        cycle = find_cycle(graph)
        if cycle is not None:
            raise ValueError(f"dependency cycle detected: {' -> '.join(cycle)}")
