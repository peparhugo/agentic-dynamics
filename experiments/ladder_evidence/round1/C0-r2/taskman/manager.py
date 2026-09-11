"""Core implementation of the :mod:`taskman` in-memory task manager.

Design notes
------------
* **Pure stdlib.** The package deliberately depends only on :mod:`datetime`,
  :mod:`json`, and :mod:`typing`, so it can run in the most constrained
  flash-ladder cell (no third-party imports to fail).
* **Ordered storage.** Tasks live in a ``dict`` keyed by id (``self._tasks``) and
  the creation order is tracked separately (``self._order``). Python dicts are
  insertion-ordered, but keeping an explicit order list makes the
  "ties keep creation order" requirement independent of any dict-order
  guarantee and survives a JSON round-trip, which does not promise key order.
* **Private ordering field avoided.** The public task dict contains only the
  contract fields; ordering lives outside it so a caller comparing
  ``get_task`` payloads never sees implementation detail.
* **Validate before mutating.** Every operation that can fail (bad priority,
  unknown dependency, cycle) computes and validates the complete new state
  first, then applies it. That is what makes the contract's
  "leaving state unchanged" clause hold for a cycle rejection.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Iterable

# The single source of truth for the status vocabulary. Anything else is a
# ``ValueError`` at the boundary rather than an invalid state inside a task.
VALID_STATUSES = ("todo", "doing", "done")

# The inclusive priority band the contract specifies.
MIN_PRIORITY = 1
MAX_PRIORITY = 5

# The mutable fields ``update_task`` understands. Restricting the set keeps a
# typo (``updat_task(id, titel=...)``) loud instead of a silent no-op.
_MUTABLE_FIELDS = ("title", "priority", "tags", "depends_on", "due_at")

# The JSON schema version written by :meth:`TaskManager.save`. It is recorded so
# a future format can be detected rather than mis-parsed.
_SCHEMA_VERSION = 1


def _validate_priority(priority: Any) -> int:
    """Return ``priority`` if it is an integer in the inclusive 1..5 band.

    ``bool`` is a subclass of ``int`` in Python; it is rejected explicitly so
    ``True`` cannot silently become priority ``1``. Floats (``3.0``) are also
    rejected because the contract speaks of an integer priority level.
    """
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError(f"priority must be an integer in {MIN_PRIORITY}..{MAX_PRIORITY}")
    if not MIN_PRIORITY <= priority <= MAX_PRIORITY:
        raise ValueError(f"priority must be in {MIN_PRIORITY}..{MAX_PRIORITY}, got {priority!r}")
    return priority


def _validate_status(status: Any) -> str:
    """Return ``status`` if it is one of :data:`VALID_STATUSES`."""
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
    return status


def _validate_due_at(due_at: Any) -> str | None:
    """Return a normalised ISO-8601 string, or ``None``.

    ``None`` is the "no deadline" sentinel. Any non-``None`` value must be a
    string parseable by :meth:`datetime.datetime.fromisoformat`; the original
    string is preserved verbatim so ``save``/``load`` round-trips it exactly
    (re-serialising a parsed datetime can change the offset spelling).
    """
    if due_at is None:
        return None
    if not isinstance(due_at, str):
        raise ValueError("due_at must be an ISO-8601 string or None")
    try:
        datetime.fromisoformat(due_at)
    except ValueError as exc:  # re-raise with a clearer message
        raise ValueError(f"due_at is not a valid ISO-8601 datetime: {due_at!r}") from exc
    return due_at


def _normalise_str_list(values: Any, *, field: str) -> list[str]:
    """Coerce ``values`` into a fresh list of strings.

    ``None`` means "empty", matching the contract's defaults. Any other iterable
    is materialised into a new list so the caller cannot mutate internal state
    through a shared reference. Elements must be strings (task ids / tags).
    """
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{field} must be an iterable of strings, not a single string")
    try:
        items = list(values)
    except TypeError as exc:
        raise ValueError(f"{field} must be an iterable of strings") from exc
    for item in items:
        if not isinstance(item, str):
            raise ValueError(f"{field} entries must be strings, got {item!r}")
    return items


class TaskManager:
    """An in-memory, dependency-aware task manager with JSON persistence.

    The manager owns a mapping of task ids to task records. A task record is a
    plain ``dict`` with the keys ``id``, ``title``, ``status``, ``priority``,
    ``tags``, ``depends_on``, ``due_at`` and ``created_at``. Callers only ever
    receive shallow copies, so they cannot corrupt internal state.
    """

    def __init__(self) -> None:
        # id -> task record. A normal dict; iteration order is not relied upon
        # for ordering (``_order`` is), but it gives O(1) lookup.
        self._tasks: dict[str, dict[str, Any]] = {}
        # Task ids in creation order — the tie-breaker for equal priorities.
        self._order: list[str] = []
        # Monotonic counter backing the human-readable, collision-free ids.
        self._next_seq: int = 1

    # ------------------------------------------------------------------ ids
    def _mint_id(self) -> str:
        """Return a fresh unique id and advance the counter.

        A simple ``t<seq>`` scheme is enough: the counter is monotonic within a
        manager, and :meth:`load` restores it from the persisted value so ids
        minted after a round-trip cannot collide with loaded ones.
        """
        task_id = f"t{self._next_seq}"
        self._next_seq += 1
        return task_id

    # ------------------------------------------------------------- read side
    def get_task(self, task_id: str) -> dict[str, Any]:
        """Return a copy of the task with ``task_id``.

        Raises :class:`KeyError` for an unknown id, as the contract requires.
        A deep-ish copy (new dict, new lists) is returned so callers cannot
        mutate the manager's internal record.
        """
        try:
            task = self._tasks[task_id]
        except KeyError:
            raise KeyError(task_id) from None
        return self._copy(task)

    @staticmethod
    def _copy(task: dict[str, Any]) -> dict[str, Any]:
        """Return a shallow-deep copy of ``task`` (lists are duplicated)."""
        return {
            "id": task["id"],
            "title": task["title"],
            "status": task["status"],
            "priority": task["priority"],
            "tags": list(task["tags"]),
            "depends_on": list(task["depends_on"]),
            "due_at": task["due_at"],
            "created_at": task["created_at"],
        }

    # ------------------------------------------------------------ write side
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

        Validation happens before the record is inserted, so a rejected
        ``add_task`` leaves the manager exactly as it was.
        """
        if not isinstance(title, str):
            raise ValueError("title must be a string")
        priority = _validate_priority(priority)
        tag_list = _normalise_str_list(tags, field="tags")
        dep_list = _normalise_str_list(depends_on, field="depends_on")
        due_at = _validate_due_at(due_at)

        # Dependencies must already exist. A brand-new task cannot participate
        # in a cycle yet (nothing can depend on an id that does not exist), so
        # the unknown-id check is the whole cycle story at creation time.
        for dep in dep_list:
            if dep not in self._tasks:
                raise ValueError(f"unknown dependency id: {dep!r}")

        task_id = self._mint_id()
        self._tasks[task_id] = {
            "id": task_id,
            "title": title,
            "status": "todo",
            "priority": priority,
            "tags": tag_list,
            "depends_on": dep_list,
            "due_at": due_at,
            "created_at": datetime.now().isoformat(),
        }
        self._order.append(task_id)
        return task_id

    def update_task(self, task_id: str, **fields: Any) -> dict[str, Any]:
        """Update one or more mutable fields of an existing task.

        Unknown ids raise :class:`KeyError`; unknown field names raise
        :class:`ValueError`. All new values are validated, and cycle freedom is
        proven, before anything is written — a rejected update is atomic.
        """
        if task_id not in self._tasks:
            raise KeyError(task_id)
        unknown = set(fields) - set(_MUTABLE_FIELDS)
        if unknown:
            raise ValueError(f"unknown task fields: {sorted(unknown)}")

        task = self._tasks[task_id]

        # Stage every requested change in ``candidate`` first.
        candidate = self._copy(task)

        if "title" in fields:
            if not isinstance(fields["title"], str):
                raise ValueError("title must be a string")
            candidate["title"] = fields["title"]
        if "priority" in fields:
            candidate["priority"] = _validate_priority(fields["priority"])
        if "tags" in fields:
            candidate["tags"] = _normalise_str_list(fields["tags"], field="tags")
        if "due_at" in fields:
            candidate["due_at"] = _validate_due_at(fields["due_at"])
        if "depends_on" in fields:
            dep_list = _normalise_str_list(fields["depends_on"], field="depends_on")
            for dep in dep_list:
                if dep not in self._tasks:
                    raise ValueError(f"unknown dependency id: {dep!r}")
            if self._creates_cycle(task_id, dep_list):
                raise ValueError("dependency update would create a cycle")
            candidate["depends_on"] = dep_list

        # Nothing raised: commit the staged record in place.
        task.update(candidate)
        return self._copy(task)

    def delete_task(self, task_id: str) -> None:
        """Delete a task, refusing while other tasks still depend on it.

        Direct dependents are checked (the contract's wording); a transitive
        dependent is necessarily reachable through a direct one, so refusing on
        the direct edge is sufficient to keep the graph closed.
        """
        if task_id not in self._tasks:
            raise KeyError(task_id)
        dependents = [
            other_id for other_id, other in self._tasks.items() if task_id in other["depends_on"]
        ]
        if dependents:
            raise ValueError(f"cannot delete {task_id!r}: depended on by {sorted(dependents)}")
        del self._tasks[task_id]
        self._order.remove(task_id)

    def set_status(self, task_id: str, status: str) -> dict[str, Any]:
        """Set a task's status, validating both the id and the status value."""
        if task_id not in self._tasks:
            raise KeyError(task_id)
        self._tasks[task_id]["status"] = _validate_status(status)
        return self._copy(self._tasks[task_id])

    # -------------------------------------------------------------- queries
    def list_tasks(
        self,
        *,
        status: str | None = None,
        priority: int | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return matching tasks ordered by priority descending.

        Ties retain creation order (discovered from ``self._order``). All
        filters are conjunctive when supplied.
        """
        order_index = {tid: index for index, tid in enumerate(self._order)}
        selected = [
            task
            for task in self._tasks.values()
            if (status is None or task["status"] == status)
            and (priority is None or task["priority"] == priority)
            and (tag is None or tag in task["tags"])
        ]
        selected.sort(key=lambda task: (-task["priority"], order_index[task["id"]]))
        return [self._copy(task) for task in selected]

    def ready_tasks(self) -> list[dict[str, Any]]:
        """Return not-done tasks whose dependencies are all ``done``.

        Ordering matches :meth:`list_tasks` (priority descending, creation-order
        ties) so a scheduler can consume the list directly.
        """
        ready = [
            task
            for task in self._tasks.values()
            if task["status"] != "done"
            and all(self._tasks[dep]["status"] == "done" for dep in task["depends_on"])
        ]
        order_index = {tid: index for index, tid in enumerate(self._order)}
        ready.sort(key=lambda task: (-task["priority"], order_index[task["id"]]))
        return [self._copy(task) for task in ready]

    # ---------------------------------------------------------- cycle check
    def _creates_cycle(self, task_id: str, new_deps: list[str]) -> bool:
        """Would ``task_id`` depending on ``new_deps`` close a cycle?

        Walks the dependency edges (``X depends_on Y`` is an edge ``X -> Y``)
        from each proposed dependency. If the walk can reach ``task_id``, the
        new edge is rejected. ``task_id`` is treated as currently having
        ``new_deps`` so an update is evaluated as a whole, not against its stale
        edge set.
        """
        adjacency: dict[str, list[str]] = {
            tid: list(task["depends_on"]) for tid, task in self._tasks.items()
        }
        adjacency[task_id] = list(new_deps)

        stack = list(new_deps)
        seen: set[str] = set()
        while stack:
            current = stack.pop()
            if current == task_id:
                return True
            if current in seen:
                continue
            seen.add(current)
            stack.extend(adjacency.get(current, ()))
        return False

    # ----------------------------------------------------------- persistence
    def save(self, path: str) -> None:
        """Write the whole manager to ``path`` as JSON.

        The on-disk shape is a JSON object (the contract asserts
        ``isinstance(json.loads(...), dict)``) carrying a version, the id
        counter, and the tasks in creation order.
        """
        payload = {
            "version": _SCHEMA_VERSION,
            "next_seq": self._next_seq,
            "tasks": [self._copy(self._tasks[tid]) for tid in self._order],
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=False)

    @classmethod
    def load(cls, path: str) -> "TaskManager":
        """Reconstruct a manager previously written by :meth:`save`."""
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)

        manager = cls()
        tasks = payload.get("tasks", [])
        for record in tasks:
            task_id = record["id"]
            # Re-validate on read so a hand-edited / corrupted file fails loudly
            # rather than seeding the manager with an invalid record.
            manager._tasks[task_id] = {
                "id": task_id,
                "title": record["title"],
                "status": _validate_status(record["status"]),
                "priority": _validate_priority(record["priority"]),
                "tags": _normalise_str_list(record.get("tags"), field="tags"),
                "depends_on": _normalise_str_list(record.get("depends_on"), field="depends_on"),
                "due_at": _validate_due_at(record.get("due_at")),
                "created_at": record["created_at"],
            }
            manager._order.append(task_id)

        # Restore the id counter. Prefer the persisted value; fall back to one
        # past the highest numeric suffix so a file lacking the field still
        # cannot mint a duplicate id.
        next_seq = payload.get("next_seq")
        if not isinstance(next_seq, int) or next_seq < 1:
            next_seq = 1
            for task_id in manager._order:
                if task_id.startswith("t") and task_id[1:].isdigit():
                    next_seq = max(next_seq, int(task_id[1:]) + 1)
        manager._next_seq = next_seq
        return manager
