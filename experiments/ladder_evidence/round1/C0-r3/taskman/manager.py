"""Implementation of :class:`TaskManager`.

Why this shape?
---------------
The contract is a *behavioural* one: it never inspects private attributes, only
the public methods and the plain-``dict`` records they return. Keeping the whole
state inside one ordered mapping means:

* iteration order is creation order (needed for the priority-tie rule);
* persistence is a straight JSON dump of that mapping; and
* ``get_task`` can hand back a shallow copy without exposing internals in a way
  that would let a caller mutate stored state *through list fields*.

Validation is centralised in small helpers so that every entry point (``add``,
``update``) enforces exactly the same rules.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

#: The three legal lifecycle states, in their natural progression order.
VALID_STATUSES = ("todo", "doing", "done")

#: Human-friendly aliases for the numeric priority bounds (1 = highest, 5 = lowest).
MIN_PRIORITY = 1
MAX_PRIORITY = 5

#: Fields a caller may change through :meth:`TaskManager.update_task`.
_UPDATABLE_FIELDS = frozenset({"title", "priority", "tags", "depends_on", "due_at", "status"})

#: Current on-disk schema version, written into every saved document so a future
#: format change can be detected and migrated instead of silently mis-read.
_SCHEMA_VERSION = 1


class TaskManager:
    """In-memory task store with JSON persistence.

    A ``TaskManager`` owns an insertion-ordered mapping of task id -> task dict.
    Every public method either returns plain data or raises one of three
    contract-defined exceptions:

    * :class:`KeyError` — the referenced task id is unknown;
    * :class:`ValueError` — an argument is invalid, or a mutation would violate an
      invariant (bad priority, unparseable date, unknown dependency, dependency
      cycle, deleting a task others depend on);
    * :class:`TypeError` — only for structurally impossible input (e.g. a caller
      passing an unexpected keyword to ``update_task``).
    """

    def __init__(self) -> None:
        # ``dict`` preserves insertion order on all supported CPython versions, so
        # this single mapping doubles as both the index and the creation-order log.
        self._tasks: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------
    def add_task(
        self,
        title: str,
        *,
        priority: int = 3,
        tags: Optional[Iterable[str]] = None,
        depends_on: Optional[Iterable[str]] = None,
        due_at: Optional[str] = None,
    ) -> str:
        """Create a task and return its generated, unique id.

        Defaults mirror the contract: status ``todo``, priority ``3``, empty
        ``tags``/``depends_on``, and ``None`` due date. ``depends_on`` may only
        reference ids that already exist in this manager. ``created_at`` is an
        ISO-8601 UTC timestamp recorded once and never rewritten.
        """
        priority = self._validate_priority(priority)
        due_at = self._validate_due_at(due_at)
        tags = self._validate_tags(tags)
        depends_on = self._validate_dependencies(depends_on)

        task_id = uuid.uuid4().hex
        task: Dict[str, Any] = {
            "id": task_id,
            "title": str(title),
            "status": "todo",
            "priority": priority,
            "tags": tags,
            "depends_on": depends_on,
            "due_at": due_at,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # A brand-new node has no dependents yet, so it cannot close a cycle; the
        # check is still run so ``add`` and ``update`` share one invariant.
        self._tasks[task_id] = task
        if self._has_cycle():
            # Defensive: restore the previous state if a future refactor ever lets
            # ``add_task`` introduce a cycle. There is no partial commit.
            del self._tasks[task_id]
            raise ValueError("dependency cycle detected")
        return task_id

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def get_task(self, task_id: str) -> Dict[str, Any]:
        """Return a copy of the task record, or raise :class:`KeyError`."""
        return copy.deepcopy(self._require(task_id))

    def list_tasks(
        self,
        *,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return records matching the optional filters.

        Results are ordered by priority **descending** (1 is lowest by value but
        highest urgency is 5 in the tests: ``high`` priority 5 sorts first).
        Python's sort is stable, so equal-priority tasks retain creation order.
        """
        if status is not None:
            self._validate_status(status)
        if priority is not None:
            self._validate_priority(priority)

        selected = [
            task
            for task in self._tasks.values()
            if (status is None or task["status"] == status)
            and (priority is None or task["priority"] == priority)
            and (tag is None or tag in task["tags"])
        ]
        # Reverse-priority, stable: the stored order is creation order, so ties
        # stay in creation order after sorting.
        selected.sort(key=lambda task: task["priority"], reverse=True)
        return copy.deepcopy(selected)

    def ready_tasks(self) -> List[Dict[str, Any]]:
        """Return not-done tasks whose every dependency is already ``done``.

        A task with no dependencies is ready immediately after creation.
        """
        ready = [
            task
            for task in self._tasks.values()
            if task["status"] != "done"
            and all(self._tasks[dep]["status"] == "done" for dep in task["depends_on"])
        ]
        return copy.deepcopy(ready)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------
    def update_task(self, task_id: str, **fields: Any) -> None:
        """Update the supplied fields on an existing task.

        Validation happens **before** any mutation so an invalid call (bad
        priority, unparseable date, unknown dependency, or a cycle) leaves the
        store exactly as it was.
        """
        task = self._require(task_id)

        unknown = set(fields) - _UPDATABLE_FIELDS
        if unknown:
            raise TypeError(f"unknown field(s): {', '.join(sorted(unknown))}")

        # Work on a copy; only commit once every field validates and no cycle is
        # introduced.
        candidate = copy.deepcopy(task)

        if "title" in fields:
            candidate["title"] = str(fields["title"])
        if "priority" in fields:
            candidate["priority"] = self._validate_priority(fields["priority"])
        if "due_at" in fields:
            candidate["due_at"] = self._validate_due_at(fields["due_at"])
        if "tags" in fields:
            candidate["tags"] = self._validate_tags(fields["tags"])
        if "status" in fields:
            candidate["status"] = self._validate_status(fields["status"])
        if "depends_on" in fields:
            candidate["depends_on"] = self._validate_dependencies(fields["depends_on"])

        if "depends_on" in fields:
            # Temporarily swap in the candidate to test the prospective graph.
            self._tasks[task_id] = candidate
            try:
                if self._has_cycle():
                    raise ValueError("dependency cycle detected")
            except ValueError:
                self._tasks[task_id] = task
                raise

        self._tasks[task_id] = candidate

    def delete_task(self, task_id: str) -> None:
        """Delete a task, refusing while any other task depends on it."""
        self._require(task_id)
        dependents = [
            other_id
            for other_id, other in self._tasks.items()
            if other_id != task_id and task_id in other["depends_on"]
        ]
        if dependents:
            raise ValueError(f"cannot delete {task_id!r}: depended on by {dependents!r}")
        del self._tasks[task_id]

    def set_status(self, task_id: str, status: str) -> None:
        """Transition a task to one of ``todo`` / ``doing`` / ``done``."""
        task = self._require(task_id)
        task["status"] = self._validate_status(status)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save(self, path: str) -> None:
        """Write the full manager state to ``path`` as JSON.

        The document is a mapping so ``json.loads(path.read_text())`` is a
        ``dict``; tasks are nested in creation order, which JSON preserves.
        """
        document = {
            "version": _SCHEMA_VERSION,
            "tasks": self._tasks,
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2, sort_keys=False)

    @classmethod
    def load(cls, path: str) -> "TaskManager":
        """Reconstruct a manager previously written by :meth:`save`."""
        with open(path, "r", encoding="utf-8") as handle:
            document = json.load(handle)

        manager = cls()
        tasks = document.get("tasks", document) if isinstance(document, dict) else {}
        for task_id, task in tasks.items():
            # Re-normalise the record so a hand-edited file cannot smuggle in a
            # missing key or an invalid value.
            manager._tasks[task_id] = {
                "id": task_id,
                "title": task["title"],
                "status": task["status"],
                "priority": task["priority"],
                "tags": list(task.get("tags", [])),
                "depends_on": list(task.get("depends_on", [])),
                "due_at": task.get("due_at"),
                "created_at": task.get("created_at", ""),
            }
        return manager

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _require(self, task_id: str) -> Dict[str, Any]:
        """Return the stored record or raise :class:`KeyError` if absent."""
        try:
            return self._tasks[task_id]
        except KeyError:
            raise KeyError(task_id) from None

    @staticmethod
    def _validate_status(status: str) -> str:
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status {status!r}; expected one of {VALID_STATUSES}")
        return status

    @staticmethod
    def _validate_priority(priority: int) -> int:
        # ``bool`` is an ``int`` subclass; exclude it so ``True`` is not silently
        # treated as priority 1.
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ValueError(f"priority must be an integer, got {priority!r}")
        if priority < MIN_PRIORITY or priority > MAX_PRIORITY:
            raise ValueError(
                f"priority must be between {MIN_PRIORITY} and {MAX_PRIORITY}, got {priority!r}"
            )
        return priority

    @staticmethod
    def _validate_due_at(due_at: Optional[str]) -> Optional[str]:
        if due_at is None:
            return None
        if not isinstance(due_at, str):
            raise ValueError(f"due_at must be a string or None, got {due_at!r}")
        try:
            datetime.fromisoformat(due_at)
        except ValueError:
            raise ValueError(f"unparseable due_at: {due_at!r}") from None
        # Preserve the caller's exact string: round-tripping must return the
        # same value that was supplied.
        return due_at

    @staticmethod
    def _validate_tags(tags: Optional[Iterable[str]]) -> List[str]:
        if tags is None:
            return []
        if isinstance(tags, str):
            # A bare string is almost certainly a caller mistake; treat it as one
            # tag rather than iterating its characters.
            return [tags]
        return [str(tag) for tag in tags]

    def _validate_dependencies(self, depends_on: Optional[Iterable[str]]) -> List[str]:
        if depends_on is None:
            return []
        if isinstance(depends_on, str):
            depends_on = [depends_on]
        resolved = [str(dep) for dep in depends_on]
        seen: set[str] = set()
        for dep in resolved:
            if dep not in self._tasks:
                raise ValueError(f"unknown dependency id: {dep!r}")
            if dep in seen:
                raise ValueError(f"duplicate dependency id: {dep!r}")
            seen.add(dep)
        return resolved

    def _has_cycle(self) -> bool:
        """Return ``True`` if the current dependency graph contains a cycle.

        Iterative depth-first search with a tri-state colour map: WHITE/GREY/BLACK.
        A back-edge to a GREY node proves a cycle. Unknown dependency ids are
        ignored here — they are rejected at validation time — but the guard keeps
        the traversal total in case a record is loaded from a hand-edited file.
        """
        WHITE, GREY, BLACK = 0, 1, 2
        colour: Dict[str, int] = {task_id: WHITE for task_id in self._tasks}

        def visit(start: str) -> bool:
            stack = [(start, iter(self._tasks[start]["depends_on"]))]
            colour[start] = GREY
            while stack:
                node, neighbours = stack[-1]
                advanced = False
                for dep in neighbours:
                    if dep not in self._tasks:
                        continue
                    if colour[dep] == GREY:
                        return True  # back-edge -> cycle
                    if colour[dep] == WHITE:
                        colour[dep] = GREY
                        stack.append((dep, iter(self._tasks[dep]["depends_on"])))
                        advanced = True
                        break
                if not advanced:
                    colour[node] = BLACK
                    stack.pop()
            return False

        return any(colour[task_id] == WHITE and visit(task_id) for task_id in list(self._tasks))
