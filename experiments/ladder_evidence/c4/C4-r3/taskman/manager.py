"""The :class:`TaskManager` implementation.

Design notes
------------
* State is a single insertion-ordered ``dict`` mapping ``task_id -> task``.
  Python 3.7+ guarantees dict insertion order, which we rely on to break
  priority ties in *creation order* (see :meth:`TaskManager.list_tasks`).
* All public read methods return **deep copies** so callers cannot mutate the
  manager's internal state by holding on to a returned dict.  This keeps the
  invariants (unknown dependencies, acyclic graph, validated priorities)
  enforceable at every write site.
* Validation is done *before* any mutation, and a prospective update is tested
  against a copy of the dependency graph, so a rejected write leaves the
  manager byte-for-byte unchanged.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

__all__ = ["TaskManager"]

# The closed set of lifecycle states.  Anything else is a programming error the
# caller should learn about immediately rather than silently storing.
VALID_STATUSES = ("todo", "doing", "done")

# Inclusive priority bounds; 5 is the most important task.
MIN_PRIORITY = 1
MAX_PRIORITY = 5
DEFAULT_PRIORITY = 3

# Fields a caller is allowed to set through add/update.  ``id`` and
# ``created_at`` are manager-owned and therefore deliberately absent.
_MUTABLE_FIELDS = ("title", "priority", "tags", "depends_on", "due_at")


class TaskManager:
    """An in-memory collection of tasks with dependency tracking.

    Example
    -------
    >>> tm = TaskManager()
    >>> a = tm.add_task("write docs", priority=4)
    >>> b = tm.add_task("review docs", depends_on=[a])
    >>> [t["id"] for t in tm.ready_tasks()] == [a]
    True
    """

    def __init__(self) -> None:
        """Create an empty manager."""
        # task_id -> task dict (insertion order == creation order).
        self._tasks: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------ #
    # Construction helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _validate_priority(priority: Any) -> int:
        """Return ``priority`` unchanged if it is a valid 1..5 int.

        Booleans are rejected explicitly because ``True``/``False`` are
        ``int`` subclasses in Python and would otherwise sneak through as 1/0.
        """
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ValueError(f"priority must be an integer in {MIN_PRIORITY}..{MAX_PRIORITY}")
        if not (MIN_PRIORITY <= priority <= MAX_PRIORITY):
            raise ValueError(f"priority must be in {MIN_PRIORITY}..{MAX_PRIORITY}")
        return priority

    @staticmethod
    def _validate_due_at(due_at: Any) -> Optional[str]:
        """Validate an ISO-8601 timestamp, returning it as the stored string.

        We keep the caller's original string (rather than a parsed
        ``datetime``) so a save/load round-trip preserves it exactly.  ``None``
        means "no due date".
        """
        if due_at is None:
            return None
        if not isinstance(due_at, str):
            raise ValueError("due_at must be an ISO-8601 string or None")
        try:
            datetime.fromisoformat(due_at)
        except ValueError as exc:  # normalise the error type/message
            raise ValueError(f"due_at is not a valid ISO-8601 timestamp: {due_at!r}") from exc
        return due_at

    @staticmethod
    def _validate_tags(tags: Any) -> List[str]:
        """Return a fresh list of tags.

        ``None`` becomes the empty list.  A bare string is rejected so callers
        do not accidentally get per-character tags.
        """
        if tags is None:
            return []
        if isinstance(tags, str):
            raise ValueError("tags must be an iterable of strings, not a bare string")
        return [str(tag) for tag in tags]

    def _validate_depends_on(self, depends_on: Any, *, task_id: Optional[str] = None) -> List[str]:
        """Validate a dependency list against the current graph.

        Every referenced id must already exist.  ``task_id``, when given, is
        the id of the task being edited; a self-reference is a cycle and is
        rejected here (it would also be caught by the graph check).  Duplicates
        are collapsed while preserving first-seen order.
        """
        if depends_on is None:
            return []
        if isinstance(depends_on, str):
            raise ValueError("depends_on must be an iterable of task ids, not a bare string")

        resolved: List[str] = []
        for dep_id in depends_on:
            if dep_id not in self._tasks:
                raise ValueError(f"unknown dependency: {dep_id!r}")
            if task_id is not None and dep_id == task_id:
                raise ValueError("a task cannot depend on itself")
            if dep_id not in resolved:
                resolved.append(dep_id)
        return resolved

    def _find_cycle(self, tasks: Dict[str, Dict[str, Any]]) -> Optional[List[str]]:
        """Return a cycle (list of ids) in ``tasks``, or ``None`` if acyclic.

        Iterative depth-first search with an explicit colour map
        (white/grey/black): a back-edge to a *grey* node is a cycle.  Keeping
        it iterative avoids recursion limits on deep dependency chains.
        """
        white, grey, black = 0, 1, 2
        colour = {task_id: white for task_id in tasks}
        parent: Dict[str, Optional[str]] = {task_id: None for task_id in tasks}

        for start in tasks:
            if colour[start] != white:
                continue
            # Stack of (node, iterator over its dependencies).
            stack: List[Any] = [(start, iter(tasks[start]["depends_on"]))]
            colour[start] = grey
            while stack:
                node, deps = stack[-1]
                for dep in deps:
                    if dep not in tasks:
                        # Defence in depth: unknown deps are rejected on write,
                        # but never let a stray edge break the traversal.
                        continue
                    if colour[dep] == grey:
                        # Reconstruct the cycle for a useful error message.
                        path = [dep]
                        cursor: Optional[str] = node
                        while cursor is not None and cursor != dep:
                            path.append(cursor)
                            cursor = parent[cursor]
                        path.append(dep)
                        path.reverse()
                        return path
                    if colour[dep] == white:
                        parent[dep] = node
                        colour[dep] = grey
                        stack.append((dep, iter(tasks[dep]["depends_on"])))
                        break
                else:
                    # Exhausted this node's dependencies: it is finished.
                    colour[node] = black
                    stack.pop()
        return None

    def _assert_acyclic(self, tasks: Dict[str, Dict[str, Any]]) -> None:
        """Raise ``ValueError`` if the candidate ``tasks`` graph has a cycle."""
        cycle = self._find_cycle(tasks)
        if cycle is not None:
            raise ValueError(f"dependency cycle detected: {' -> '.join(cycle)}")

    @staticmethod
    def _normalise_fields(
        manager: "TaskManager",
        *,
        priority: Any = DEFAULT_PRIORITY,
        tags: Any = None,
        depends_on: Any = None,
        due_at: Any = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate a full set of mutable fields and return their clean form."""
        return {
            "priority": manager._validate_priority(priority),
            "tags": manager._validate_tags(tags),
            "depends_on": manager._validate_depends_on(depends_on, task_id=task_id),
            "due_at": manager._validate_due_at(due_at),
        }

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
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

        Defaults: status ``todo``, priority ``3``, empty tags/dependencies and
        no due date.  ``priority`` outside ``1..5``, an unparseable ``due_at``
        or an unknown dependency id raise ``ValueError``; the manager is left
        untouched on any failure.
        """
        if not isinstance(title, str):
            raise ValueError("title must be a string")

        # Allocate the id first so cycle detection can reason about the full
        # candidate graph, but do not mutate ``self._tasks`` until it is safe.
        task_id = uuid.uuid4().hex
        fields = self._normalise_fields(
            self,
            priority=priority,
            tags=tags,
            depends_on=depends_on,
            due_at=due_at,
            task_id=None,  # the new id cannot be in depends_on (unknown yet)
        )

        candidate = copy.deepcopy(self._tasks)
        candidate[task_id] = {
            "id": task_id,
            "title": title,
            "status": "todo",
            "priority": fields["priority"],
            "tags": fields["tags"],
            "depends_on": fields["depends_on"],
            "due_at": fields["due_at"],
            "created_at": datetime.now().astimezone().isoformat(),
        }
        self._assert_acyclic(candidate)
        self._tasks = candidate
        return task_id

    def get_task(self, task_id: str) -> Dict[str, Any]:
        """Return a deep copy of ``task_id``'s state.

        Unknown ids raise ``KeyError``.
        """
        if task_id not in self._tasks:
            raise KeyError(task_id)
        return copy.deepcopy(self._tasks[task_id])

    def update_task(self, task_id: str, **fields: Any) -> None:
        """Update one or more mutable fields on ``task_id``.

        Unknown ids raise ``KeyError``; unknown field names, invalid values, an
        unknown dependency or a dependency cycle raise ``ValueError``.  All
        validation happens against a candidate copy, so a rejected update
        leaves the manager unchanged.
        """
        if task_id not in self._tasks:
            raise KeyError(task_id)
        unknown = set(fields) - set(_MUTABLE_FIELDS)
        if unknown:
            raise ValueError(f"unknown field(s): {', '.join(sorted(unknown))}")

        current = self._tasks[task_id]
        # Start from the existing values, then overlay the caller's changes so
        # a partial update validates against the untouched fields too.
        priority = fields.get("priority", current["priority"])
        tags = fields.get("tags", current["tags"])
        depends_on = fields.get("depends_on", current["depends_on"])
        due_at = fields.get("due_at", current["due_at"])
        title = fields.get("title", current["title"])
        if not isinstance(title, str):
            raise ValueError("title must be a string")

        normalised = self._normalise_fields(
            self,
            priority=priority,
            tags=tags,
            depends_on=depends_on,
            due_at=due_at,
            task_id=task_id,
        )

        candidate = copy.deepcopy(self._tasks)
        candidate[task_id].update(
            {
                "title": title,
                "priority": normalised["priority"],
                "tags": normalised["tags"],
                "depends_on": normalised["depends_on"],
                "due_at": normalised["due_at"],
            }
        )
        self._assert_acyclic(candidate)
        self._tasks = candidate

    def delete_task(self, task_id: str) -> None:
        """Delete ``task_id``.

        Unknown ids raise ``KeyError``.  Deletion is refused with ``ValueError``
        while any other task still depends on it, so the dependency graph never
        develops dangling edges.
        """
        if task_id not in self._tasks:
            raise KeyError(task_id)
        dependents = [
            other_id for other_id, task in self._tasks.items() if task_id in task["depends_on"]
        ]
        if dependents:
            raise ValueError(f"task {task_id!r} is depended on by {', '.join(sorted(dependents))}")
        del self._tasks[task_id]

    def set_status(self, task_id: str, status: str) -> None:
        """Transition ``task_id`` to ``status``.

        ``status`` must be one of ``todo``/``doing``/``done`` (else
        ``ValueError``); an unknown id raises ``KeyError``.  Transitions are
        currently unrestricted (any valid state may follow any other), which
        keeps the manager flexible for callers that need to reopen a task.
        """
        if task_id not in self._tasks:
            raise KeyError(task_id)
        if status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
        self._tasks[task_id]["status"] = status

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    def list_tasks(
        self,
        *,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return tasks matching the optional filters, priority-descending.

        Ties on priority keep creation order, which falls out of the
        insertion-ordered backing dict plus a stable sort.  ``None`` means "do
        not filter on this dimension".
        """
        if status is not None and status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")

        selected = [
            task
            for task in self._tasks.values()
            if (status is None or task["status"] == status)
            and (priority is None or task["priority"] == priority)
            and (tag is None or tag in task["tags"])
        ]
        # ``sorted`` is stable, so equal priorities retain insertion order.
        selected.sort(key=lambda task: task["priority"], reverse=True)
        return [copy.deepcopy(task) for task in selected]

    def ready_tasks(self) -> List[Dict[str, Any]]:
        """Return not-``done`` tasks whose dependencies are all ``done``.

        A task with no dependencies is trivially ready.  The result keeps
        creation order; callers that care about execution priority can pipe it
        through :meth:`list_tasks`.
        """
        ready: List[Dict[str, Any]] = []
        for task in self._tasks.values():
            if task["status"] == "done":
                continue
            if all(self._tasks[dep]["status"] == "done" for dep in task["depends_on"]):
                ready.append(copy.deepcopy(task))
        return ready

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def save(self, path: str) -> None:
        """Serialise the manager to ``path`` as JSON (UTF-8)."""
        payload = {
            "version": 1,
            # A list keeps the on-disk creation order explicit rather than
            # relying on JSON object key ordering.
            "tasks": list(self._tasks.values()),
        }
        Path(path).write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "TaskManager":
        """Rebuild a manager from JSON written by :meth:`save`.

        Malformed payloads raise ``ValueError`` so callers get a single,
        predictable failure mode for bad input files.
        """
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"could not load task file {path!r}: {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("tasks"), list):
            raise ValueError(f"task file {path!r} has an unexpected shape")

        manager = cls()
        # First pass: place every raw task so that the second pass can resolve
        # dependencies regardless of file ordering (save writes creation order,
        # but a hand-edited file need not).
        for entry in payload["tasks"]:
            if not isinstance(entry, dict) or "id" not in entry:
                raise ValueError(f"task file {path!r} contains a malformed task entry")
            manager._tasks[entry["id"]] = {
                "id": entry["id"],
                "title": entry.get("title", ""),
                "status": entry.get("status", "todo"),
                "priority": entry.get("priority", DEFAULT_PRIORITY),
                "tags": entry.get("tags"),
                "depends_on": entry.get("depends_on"),
                "due_at": entry.get("due_at"),
                "created_at": entry.get("created_at", ""),
            }

        # Second pass: validate through the same normalisers used on write so a
        # corrupt file is rejected rather than silently loaded.
        for task_id, task in manager._tasks.items():
            normalised = manager._normalise_fields(
                manager,
                priority=task["priority"],
                tags=task["tags"],
                depends_on=task["depends_on"],
                due_at=task["due_at"],
                task_id=task_id,
            )
            if task["status"] not in VALID_STATUSES:
                raise ValueError(
                    f"task file {path!r} contains an invalid status: {task['status']!r}"
                )
            task.update(
                {
                    "priority": normalised["priority"],
                    "tags": normalised["tags"],
                    "depends_on": normalised["depends_on"],
                    "due_at": normalised["due_at"],
                }
            )
        manager._assert_acyclic(manager._tasks)
        return manager
