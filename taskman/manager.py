"""Pure-stdlib implementation of the ``taskman`` task store.

Design summary
--------------
* A task is represented as a plain ``dict`` at the public boundary, but the
  store keeps its own private record.  Reads hand back *copies*, so a caller can
  never mutate stored state through a returned value.
* Every mutation builds and validates a **candidate** state first and only then
  commits it.  "A rejected edit leaves state unchanged" is therefore structural
  rather than a best-effort rollback: the live mapping is assigned exactly once,
  after every check has passed.
* Ordering is derived, never stored.  Tasks sort by ``(-priority, seq)`` where
  ``seq`` is a monotonic creation counter, giving priority-descending order with
  a stable tie-break on creation order.
* Only the Python standard library is used (``json``, ``uuid``, ``datetime``).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

#: The statuses the behavioural contract recognises.
VALID_STATUSES = ("todo", "doing", "done")

#: Inclusive priority band accepted by the contract.
MIN_PRIORITY = 1
MAX_PRIORITY = 5

#: Sentinel distinguishing "argument omitted" from "argument set to None" in
#: :meth:`TaskManager.update_task` (``due_at=None`` is a legal update value).
_UNSET = object()


def validate_priority(priority):
    """Return ``priority`` iff it is an int inside the inclusive 1..5 band.

    ``bool`` is rejected explicitly even though it is an ``int`` subclass: a
    caller passing ``True``/``False`` meant a flag, not a priority.
    """
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError(
            f"priority must be an integer in {MIN_PRIORITY}..{MAX_PRIORITY}, got {priority!r}"
        )
    if not MIN_PRIORITY <= priority <= MAX_PRIORITY:
        raise ValueError(f"priority must be in {MIN_PRIORITY}..{MAX_PRIORITY}, got {priority!r}")
    return priority


def validate_status(status):
    """Return ``status`` iff it is one of :data:`VALID_STATUSES`."""
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
    return status


def validate_due_at(due_at):
    """Return the ISO-8601 string ``due_at`` iff it parses, else raise ``ValueError``.

    The original string is preserved verbatim (not re-serialised) so a
    save/load round-trip is byte-for-byte for the caller's chosen
    representation.  ``None`` means "no due date" and is always allowed.
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


def normalize_list(value, *, field):
    """Coerce a tags/dependency argument to a de-duplicated, order-preserving tuple.

    A bare string is treated as a single element (``"infra"`` -> ``("infra",)``)
    so a caller who forgets the list brackets does not get a character split.
    Duplicates are removed while first-seen order is kept, because a task is
    neither tagged by nor dependent on the same thing twice.
    """
    if value is None:
        return ()
    if isinstance(value, str):
        value = (value,)
    seen = {}
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field} entries must be strings, got {item!r}")
        seen.setdefault(item, None)
    return tuple(seen)


def find_cycle(dependencies):
    """Return a dependency cycle as a list of ids, or ``None`` when acyclic.

    Edges point from a task to the tasks it depends on, so a cycle is a closed
    walk ``a -> b -> ... -> a``.  An iterative three-colour DFS detects it: a
    child still coloured GRAY is an ancestor on the current search path, i.e.
    the back-edge that closes the cycle.  Iterative (not recursive) so a deep
    chain cannot hit Python's recursion limit.
    """
    white, gray, black = 0, 1, 2
    colour = {}
    for root in dependencies:
        if colour.get(root, white) != white:
            continue
        colour[root] = gray
        stack = [(root, iter(dependencies.get(root, ())))]
        while stack:
            node, children = stack[-1]
            for child in children:
                state = colour.get(child, white)
                if state == gray:
                    path = [frame[0] for frame in stack]
                    return path[path.index(child) :]
                if state == white:
                    colour[child] = gray
                    stack.append((child, iter(dependencies.get(child, ()))))
                    break
            else:
                colour[node] = black
                stack.pop()
    return None


class TaskManager:
    """An in-memory task store with JSON persistence.

    The manager owns a mapping of ``task_id -> record`` plus a monotonic
    creation counter.  Public reads return copies; every write validates a
    candidate state before committing it.
    """

    def __init__(self):
        self._tasks = {}
        # Monotonic creation counter: the tie-break for equal priorities.
        self._seq = 0

    # --------------------------------------------------------------- writes

    def add_task(self, title, *, priority=3, tags=None, depends_on=None, due_at=None):
        """Create a task and return its unique id.

        Defaults mirror the contract: status ``todo``, priority ``3``, empty
        tags/dependencies, and no due date.  Validation runs before the record
        is stored, so a rejected ``add_task`` leaves the store untouched.  The
        new id cannot be part of a cycle yet (nothing may depend on it), but the
        candidate graph is cycle-checked anyway for a single code path.
        """
        if not isinstance(title, str):
            raise ValueError(f"title must be a string, got {title!r}")
        validated_priority = validate_priority(priority)
        normalized_tags = normalize_list(tags, field="tags")
        normalized_deps = normalize_list(depends_on, field="depends_on")
        validated_due = validate_due_at(due_at)

        # Unknown dependency ids are rejected before the task is created.
        self._check_dependencies_exist(normalized_deps)

        task_id = uuid.uuid4().hex
        record = {
            "id": task_id,
            "title": title,
            "status": "todo",
            "priority": validated_priority,
            "tags": list(normalized_tags),
            "depends_on": list(normalized_deps),
            "due_at": validated_due,
            "created_at": datetime.now().astimezone().isoformat(),
            "seq": self._seq,
        }

        # Build and validate the whole prospective graph, then commit atomically.
        candidate_state = dict(self._tasks)
        candidate_state[task_id] = record
        self._check_acyclic(candidate_state)

        self._tasks = candidate_state
        self._seq += 1
        return task_id

    def update_task(
        self,
        task_id,
        *,
        title=_UNSET,
        priority=_UNSET,
        tags=_UNSET,
        depends_on=_UNSET,
        due_at=_UNSET,
        status=_UNSET,
    ):
        """Update the supplied fields of ``task_id``, leaving the rest untouched.

        An unknown id raises ``KeyError`` before any field validation.  The
        update is validated against a candidate state and committed only on
        success, so a rejected edit (notably a dependency cycle) leaves the
        prior state exactly intact.
        """
        current = self._tasks[task_id]  # KeyError for an unknown id, as required.

        new_title = current["title"] if title is _UNSET else title
        if not isinstance(new_title, str):
            raise ValueError(f"title must be a string, got {new_title!r}")
        new_priority = current["priority"] if priority is _UNSET else validate_priority(priority)
        new_tags = current["tags"] if tags is _UNSET else list(normalize_list(tags, field="tags"))
        new_deps = (
            current["depends_on"]
            if depends_on is _UNSET
            else list(normalize_list(depends_on, field="depends_on"))
        )
        new_due = current["due_at"] if due_at is _UNSET else validate_due_at(due_at)
        new_status = current["status"] if status is _UNSET else validate_status(status)

        self._check_dependencies_exist(new_deps)

        updated = {
            "id": current["id"],
            "title": new_title,
            "status": new_status,
            "priority": new_priority,
            "tags": new_tags,
            "depends_on": new_deps,
            "due_at": new_due,
            "created_at": current["created_at"],
            "seq": current["seq"],
        }
        candidate_state = dict(self._tasks)
        candidate_state[task_id] = updated
        self._check_acyclic(candidate_state)

        self._tasks = candidate_state

    def delete_task(self, task_id):
        """Delete ``task_id`` unless another task still depends on it.

        An unknown id raises ``KeyError``; a still-referenced id raises
        ``ValueError`` and nothing is removed.
        """
        if task_id not in self._tasks:
            raise KeyError(task_id)
        dependents = [rec["id"] for rec in self._tasks.values() if task_id in rec["depends_on"]]
        if dependents:
            raise ValueError(
                f"cannot delete task {task_id!r}: still required by {sorted(dependents)!r}"
            )
        self._tasks.pop(task_id)

    def set_status(self, task_id, status):
        """Set the status of ``task_id`` (must be one of todo/doing/done)."""
        current = self._tasks[task_id]  # KeyError for an unknown id.
        validated = validate_status(status)
        # Replace only the status, preserving every other field (and seq/order).
        self._tasks[task_id] = {**current, "status": validated}

    # ---------------------------------------------------------------- reads

    def get_task(self, task_id):
        """Return a copy of the task as a plain dict (unknown id -> ``KeyError``)."""
        return self._copy(self._tasks[task_id])

    def list_tasks(self, *, status=None, priority=None, tag=None):
        """Return tasks matching every supplied filter, priority-descending.

        Ties on priority keep creation order.  Each result is a fresh copy.
        """
        selected = [
            rec
            for rec in self._tasks.values()
            if (status is None or rec["status"] == status)
            and (priority is None or rec["priority"] == priority)
            and (tag is None or tag in rec["tags"])
        ]
        return [self._copy(rec) for rec in self._ordered(selected)]

    def ready_tasks(self):
        """Return not-done tasks whose dependencies are all done, ordered.

        A task with no dependencies is ready as soon as it is created; a task is
        never "ready" once it is ``done``.  Results are fresh copies.
        """
        ready = [
            rec
            for rec in self._tasks.values()
            if rec["status"] != "done"
            and all(
                dep in self._tasks and self._tasks[dep]["status"] == "done"
                for dep in rec["depends_on"]
            )
        ]
        return [self._copy(rec) for rec in self._ordered(ready)]

    # ---------------------------------------------------------- persistence

    def save(self, path):
        """Write the manager to ``path`` as a JSON document.

        The document preserves creation order (a list, not a mapping) and the
        creation counter, so both survive a round-trip.
        """
        payload = {
            "schema": "taskman/v1",
            "seq": self._seq,
            # Persist the private ``seq`` tie-break as well, so ordering survives
            # a round-trip even though the public dict shape omits it.
            "tasks": [
                dict(rec, tags=list(rec["tags"]), depends_on=list(rec["depends_on"]))
                for rec in self._tasks.values()
            ],
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")

    @classmethod
    def load(cls, path):
        """Reconstruct a manager from a document written by :meth:`save`.

        Loading is a literal rehydration of the persisted state -- no
        re-validation, because the saved document is the authority and was
        already valid when written.  A file that is not a taskman document
        raises ``ValueError`` rather than guessing.
        """
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict) or payload.get("schema") != "taskman/v1":
            raise ValueError(f"{path!r} is not a taskman/v1 document")

        manager = cls()
        tasks = payload.get("tasks", [])
        manager._seq = int(payload.get("seq", len(tasks)))
        for raw in tasks:
            # Rehydrate in persisted (creation) order so dict order is stable.
            manager._tasks[raw["id"]] = {
                "id": raw["id"],
                "title": raw["title"],
                "status": raw["status"],
                "priority": raw["priority"],
                "tags": list(raw.get("tags", [])),
                "depends_on": list(raw.get("depends_on", [])),
                "due_at": raw.get("due_at"),
                "created_at": raw["created_at"],
                "seq": raw["seq"],
            }
        return manager

    # ------------------------------------------------------------- internal

    @staticmethod
    def _copy(record):
        """Return a fresh dict with fresh list fields (no shared nested state)."""
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

    @staticmethod
    def _ordered(tasks):
        """Sort by priority descending, then creation sequence ascending."""
        return sorted(tasks, key=lambda rec: (-rec["priority"], rec["seq"]))

    def _check_dependencies_exist(self, depends_on):
        """Raise ``ValueError`` for the first dependency id that is unknown."""
        for dep in depends_on:
            if dep not in self._tasks:
                raise ValueError(f"unknown dependency id: {dep!r}")

    def _check_acyclic(self, state):
        """Raise ``ValueError`` if the candidate graph contains a cycle."""
        graph = {task_id: tuple(rec["depends_on"]) for task_id, rec in state.items()}
        cycle = find_cycle(graph)
        if cycle is not None:
            raise ValueError(f"dependency cycle detected: {' -> '.join(cycle)}")
