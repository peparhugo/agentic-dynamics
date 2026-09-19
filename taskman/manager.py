"""The :class:`TaskManager` implementation.

Design notes
------------
* **Storage** — tasks are held in a single ``dict`` keyed by task id.  Python
  guarantees insertion order for dicts, so that dict doubles as the creation
  order used to break priority ties in :meth:`TaskManager.list_tasks`.  Updating
  an existing task re-assigns its key, which preserves its original position.
* **Ids** — opaque ``uuid4().hex`` strings, so no counter state has to survive a
  save/load round trip.
* **Validation is eager and side-effect-free** — every public mutator validates
  its full input (and, where dependencies change, the whole graph) *before* it
  touches state, which is what lets a rejected update leave state unchanged.
* **Copies out** — read paths return freshly copied dicts so callers cannot
  mutate the manager's internal state by accident.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

#: The only statuses the model accepts, in their canonical order.
VALID_STATUSES = ("todo", "doing", "done")

#: Inclusive priority range (1 = lowest, 5 = highest).
MIN_PRIORITY = 1
MAX_PRIORITY = 5

#: Sentinel distinguishing "argument omitted" from an explicit ``None``.
_UNSET = object()


def _validate_priority(priority: Any) -> int:
    """Return ``priority`` if it is an int in 1..5, else raise ``ValueError``."""
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError(f"priority must be an int in 1..5, got {priority!r}")
    if not MIN_PRIORITY <= priority <= MAX_PRIORITY:
        raise ValueError(f"priority must be in {MIN_PRIORITY}..{MAX_PRIORITY}, got {priority!r}")
    return priority


def _validate_due_at(due_at: Any) -> Optional[str]:
    """Validate an ISO-8601 due date, returning it unchanged (a string or ``None``).

    The original string is preserved verbatim so a save/load round trip is
    byte-for-byte faithful rather than a re-serialisation of a parsed datetime.
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


class TaskManager:
    """An in-memory collection of tasks with dependency-aware validation.

    All state mutations go through the public methods below; the internal
    contract is that a method either fully succeeds or leaves the manager
    untouched (an *atomic* API), which the dependency-cycle test relies on.
    """

    def __init__(self) -> None:
        # id -> task dict. Insertion order is creation order.
        self._tasks: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------ reads

    def get_task(self, task_id: str) -> Dict[str, Any]:
        """Return a copy of the task with ``task_id``; raise ``KeyError`` if unknown."""
        return copy.deepcopy(self._task_or_raise(task_id))

    def list_tasks(
        self,
        *,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return tasks matching the optional filters, ordered by priority desc.

        Ties in priority keep creation order (the sort is stable and the input is
        already in insertion order).  Each filter is an exact-match predicate.
        """
        selected = [
            task
            for task in self._tasks.values()
            if (status is None or task["status"] == status)
            and (priority is None or task["priority"] == priority)
            and (tag is None or tag in task["tags"])
        ]
        selected.sort(key=lambda task: task["priority"], reverse=True)
        return copy.deepcopy(selected)

    def ready_tasks(self) -> List[Dict[str, Any]]:
        """Return not-done tasks all of whose dependencies are done.

        A task with no dependencies is ready as soon as it is not done.
        """
        ready = [
            task
            for task in self._tasks.values()
            if task["status"] != "done"
            and all(
                self._tasks[dep]["status"] == "done"
                for dep in task["depends_on"]
                if dep in self._tasks
            )
        ]
        ready.sort(key=lambda task: task["priority"], reverse=True)
        return copy.deepcopy(ready)

    # ----------------------------------------------------------------- writes

    def add_task(
        self,
        title: str,
        *,
        priority: int = 3,
        tags: Optional[Iterable[str]] = None,
        depends_on: Optional[Iterable[str]] = None,
        due_at: Optional[str] = None,
    ) -> str:
        """Create a task and return its unique id.

        Validates priority, due date, and every dependency id *before* inserting
        anything, so a partially-created task can never be observed.
        """
        _validate_priority(priority)
        _validate_due_at(due_at)
        deps = self._resolve_dependencies(depends_on)

        task_id = uuid.uuid4().hex
        self._tasks[task_id] = {
            "id": task_id,
            "title": title,
            "status": "todo",
            "priority": priority,
            "tags": list(tags) if tags is not None else [],
            "depends_on": deps,
            "due_at": due_at,
            "created_at": datetime.now().astimezone().isoformat(),
        }
        return task_id

    def update_task(self, task_id: str, **fields: Any) -> Dict[str, Any]:
        """Update the given fields on an existing task and return the new state.

        Supported fields: ``title``, ``status``, ``priority``, ``tags``,
        ``depends_on``, ``due_at``.  The update is validated as a whole (including
        a cycle check when ``depends_on`` changes) and applied only if every
        validation passes.
        """
        current = self._task_or_raise(task_id)

        # Build the candidate next state without mutating the stored task yet.
        candidate = copy.deepcopy(current)
        unknown = set(fields) - {
            "title",
            "status",
            "priority",
            "tags",
            "depends_on",
            "due_at",
        }
        if unknown:
            raise ValueError(f"unknown task field(s): {', '.join(sorted(unknown))}")

        if "title" in fields:
            candidate["title"] = fields["title"]
        if "status" in fields:
            candidate["status"] = self._validate_status(fields["status"])
        if "priority" in fields:
            candidate["priority"] = _validate_priority(fields["priority"])
        if "tags" in fields:
            candidate["tags"] = list(fields["tags"]) if fields["tags"] is not None else []
        if "due_at" in fields:
            candidate["due_at"] = _validate_due_at(fields["due_at"])
        if "depends_on" in fields:
            candidate["depends_on"] = self._resolve_dependencies(fields["depends_on"])

        # A dependency edit is the only change that can introduce a cycle.
        if "depends_on" in fields:
            self._assert_acyclic(task_id, candidate["depends_on"])

        self._tasks[task_id] = candidate
        return copy.deepcopy(candidate)

    def delete_task(self, task_id: str) -> None:
        """Delete a task, refusing while any other task still depends on it."""
        self._task_or_raise(task_id)
        dependents = [
            other["id"]
            for other in self._tasks.values()
            if other["id"] != task_id and task_id in other["depends_on"]
        ]
        if dependents:
            raise ValueError(f"cannot delete task {task_id!r}; still required by {dependents!r}")
        del self._tasks[task_id]

    def set_status(self, task_id: str, status: str) -> None:
        """Set a task's status to one of ``todo``/``doing``/``done``."""
        self._task_or_raise(task_id)
        self._tasks[task_id]["status"] = self._validate_status(status)

    # ----------------------------------------------------------- persistence

    def save(self, path: str) -> None:
        """Write the full task list to ``path`` as JSON.

        The on-disk payload is a single object (``{"tasks": [...]}``) whose list
        order is creation order, so loading restores both content and tie-break
        ordering.
        """
        payload = {"tasks": list(self._tasks.values())}
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=False)

    @classmethod
    def load(cls, path: str) -> "TaskManager":
        """Reconstruct a manager from a file written by :meth:`save`."""
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)

        manager = cls()
        # Insert in stored order so creation order survives the round trip.
        for task in payload.get("tasks", []):
            manager._tasks[task["id"]] = copy.deepcopy(task)
        return manager

    # -------------------------------------------------------------- internals

    def _task_or_raise(self, task_id: str) -> Dict[str, Any]:
        """Return the internal task dict or raise ``KeyError`` for an unknown id."""
        try:
            return self._tasks[task_id]
        except KeyError:
            raise KeyError(f"unknown task id: {task_id!r}") from None

    @staticmethod
    def _validate_status(status: Any) -> str:
        """Return ``status`` if it is a known status, else raise ``ValueError``."""
        if status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
        return status

    def _resolve_dependencies(self, depends_on: Optional[Iterable[str]]) -> List[str]:
        """Normalise a dependency iterable, rejecting unknown ids.

        Duplicates are dropped while preserving first-seen order.
        """
        if depends_on is None:
            return []
        resolved: List[str] = []
        for dep in depends_on:
            if dep not in self._tasks:
                raise ValueError(f"unknown dependency id: {dep!r}")
            if dep not in resolved:
                resolved.append(dep)
        return resolved

    def _assert_acyclic(self, task_id: str, new_deps: Iterable[str]) -> None:
        """Raise ``ValueError`` if attaching ``new_deps`` to ``task_id`` forms a cycle.

        Cycle detection is a DFS over the dependency graph (edge ``task -> dep``),
        using the stored graph with ``task_id``'s edges overridden by the proposed
        ones.  A node is "in progress" on the current DFS stack, which is exactly
        the condition for a back-edge and therefore a cycle.
        """
        graph: Dict[str, List[str]] = {
            tid: list(task["depends_on"]) for tid, task in self._tasks.items()
        }
        graph[task_id] = list(new_deps)

        state: Dict[str, int] = {}  # 0/unset = unvisited, 1 = on stack, 2 = finished

        def visit(node: str) -> bool:
            mark = state.get(node, 0)
            if mark == 1:
                return True  # back-edge: we reached a node still on the stack
            if mark == 2:
                return False
            state[node] = 1
            for dep in graph.get(node, []):
                if visit(dep):
                    return True
            state[node] = 2
            return False

        for node in graph:
            if visit(node):
                raise ValueError(f"dependency cycle detected involving {task_id!r}")
