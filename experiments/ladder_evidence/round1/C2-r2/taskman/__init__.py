"""``taskman`` — a small, pure-Python, stdlib-only task manager.

VERBOSE MODE: this module exists to satisfy the behavioural contract in
``tests/flash_ladder/taskman_contract_test.py``. The design is deliberately
plain so the behaviour is easy to reason about and verify:

* **Storage.** Tasks live in a single ``dict`` keyed by id (``self._tasks``).
  Python dictionaries preserve insertion order, which we exploit in two places:
  (a) ``list_tasks`` tie-breaks equal priorities by creation order via a stable
  sort, and (b) ``save``/``load`` round-trips preserve that order for free.
* **Returned values are copies.** Every public read returns a defensive copy
  (``_public``) so a caller mutating a returned dict/list can never corrupt the
  manager's internal state.
* **Validation happens before mutation.** ``update_task`` builds a candidate
  record and validates it (including cycle detection) before committing, so a
  rejected update leaves the manager exactly as it was — the contract's
  "cycle raises ValueError leaving state unchanged" requirement.
* **Stdlib only.** The only imports are ``json``, ``uuid``, ``datetime`` and
  ``pathlib`` — no third-party dependency is available to, or needed by, this
  package.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = ["TaskManager"]

# The frozen vocabulary the contract recognises. Keeping these as module
# constants means "what is a valid status" is stated once.
VALID_STATUSES = ("todo", "doing", "done")
DEFAULT_STATUS = "todo"
DEFAULT_PRIORITY = 3
MIN_PRIORITY = 1
MAX_PRIORITY = 5

# The fields a caller may change through ``update_task``. Anything else is a
# programming error and raises ``TypeError`` rather than being silently ignored.
_UPDATABLE_FIELDS = frozenset({"title", "priority", "tags", "depends_on", "due_at", "status"})


class TaskManager:
    """An in-memory collection of tasks with optional persistence to JSON.

    The manager owns all validation. Callers receive plain dictionaries; a task
    has the shape::

        {
            "id": str,            # unique, generated at add time
            "title": str,
            "status": "todo" | "doing" | "done",
            "priority": int,      # 1 (highest) .. 5 (lowest)
            "tags": list[str],
            "depends_on": list[str],  # ids of prerequisite tasks
            "due_at": str | None,     # original ISO-8601 text, unmodified
            "created_at": str,        # ISO-8601 timestamp (non-empty)
        }
    """

    def __init__(self) -> None:
        # id -> task dict, in creation order.
        self._tasks: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------
    def add_task(
        self,
        title: str,
        *,
        priority: int = DEFAULT_PRIORITY,
        tags: list[str] | None = None,
        depends_on: list[str] | None = None,
        due_at: str | None = None,
    ) -> str:
        """Create a task and return its generated unique id.

        All arguments are validated before the task is stored, so a rejected
        ``add_task`` never leaves a partial record behind.
        """
        # Validate every value first — cheap, and it keeps the store clean.
        checked_priority = self._validate_priority(priority)
        checked_tags = self._normalize_tags(tags)
        checked_due_at = self._validate_due_at(due_at)

        # A fresh uuid4 hex is unique with overwhelming probability; the test
        # only needs 20 distinct ids, which this trivially satisfies.
        task_id = uuid.uuid4().hex

        checked_deps = self._normalize_depends(depends_on)
        # Unknown dependencies are rejected. The new task cannot introduce a
        # cycle (nothing can depend on an id that does not exist yet), so a
        # cycle check here would be redundant — but the existence check is not.
        for dep_id in checked_deps:
            if dep_id not in self._tasks:
                raise ValueError(f"unknown dependency id: {dep_id!r}")

        self._tasks[task_id] = {
            "id": task_id,
            "title": title,
            "status": DEFAULT_STATUS,
            "priority": checked_priority,
            "tags": checked_tags,
            "depends_on": checked_deps,
            "due_at": checked_due_at,
            # Stored as text so the JSON round-trip is byte-for-byte stable.
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return task_id

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def get_task(self, task_id: str) -> dict[str, Any]:
        """Return a defensive copy of the task, or raise ``KeyError``."""
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(task_id)
        return self._public(task)

    def list_tasks(
        self,
        *,
        status: str | None = None,
        priority: int | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return tasks (optionally filtered), highest priority first.

        Ties preserve creation order: Python's sort is stable and we iterate
        ``self._tasks`` in insertion order, so equal priorities never reshuffle.
        """
        selected = list(self._tasks.values())
        if status is not None:
            selected = [t for t in selected if t["status"] == status]
        if priority is not None:
            selected = [t for t in selected if t["priority"] == priority]
        if tag is not None:
            selected = [t for t in selected if tag in t["tags"]]
        # Descending priority: negate the key rather than reverse=True, because
        # reverse=True would also reverse the order of equal-priority ties.
        selected.sort(key=lambda t: -t["priority"])
        return [self._public(t) for t in selected]

    def ready_tasks(self) -> list[dict[str, Any]]:
        """Return not-done tasks whose dependencies are all done.

        A task with no dependencies is ready as soon as it is created. Ordering
        matches ``list_tasks`` (priority desc, ties by creation order).
        """
        ready = [
            t
            for t in self._tasks.values()
            if t["status"] != "done"
            and all(self._tasks[dep]["status"] == "done" for dep in t["depends_on"])
        ]
        ready.sort(key=lambda t: -t["priority"])
        return [self._public(t) for t in ready]

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------
    def update_task(self, task_id: str, **fields: Any) -> None:
        """Update one or more fields of an existing task.

        Validation is performed against a *candidate* copy and only committed
        on success, so a failed update (bad priority, unknown dependency, a
        dependency cycle) leaves the manager untouched.
        """
        if task_id not in self._tasks:
            raise KeyError(task_id)

        unknown = set(fields) - _UPDATABLE_FIELDS
        if unknown:
            raise TypeError(f"unknown task field(s): {sorted(unknown)}")

        # Start from a shallow copy; list fields are replaced below, never
        # mutated in place, so the original record stays intact until commit.
        candidate = dict(self._tasks[task_id])

        for key, value in fields.items():
            if key == "title":
                candidate["title"] = value
            elif key == "priority":
                candidate["priority"] = self._validate_priority(value)
            elif key == "tags":
                candidate["tags"] = self._normalize_tags(value)
            elif key == "due_at":
                candidate["due_at"] = self._validate_due_at(value)
            elif key == "status":
                candidate["status"] = self._validate_status(value)
            elif key == "depends_on":
                deps = self._normalize_depends(value)
                # Existing dependencies must resolve.
                for dep_id in deps:
                    if dep_id not in self._tasks:
                        raise ValueError(f"unknown dependency id: {dep_id!r}")
                candidate["depends_on"] = deps
                # Validate the tentative graph for cycles *before* committing.
                # Build a graph view where only this task differs.
                graph = {
                    tid: (candidate if tid == task_id else t) for tid, t in self._tasks.items()
                }
                if self._has_cycle(graph):
                    raise ValueError(f"dependency cycle introduced by updating {task_id!r}")

        # All validations passed — commit atomically.
        self._tasks[task_id] = candidate

    def delete_task(self, task_id: str) -> None:
        """Delete a task. Refuses while any other task depends on it."""
        if task_id not in self._tasks:
            raise KeyError(task_id)
        dependents = [t["id"] for t in self._tasks.values() if task_id in t["depends_on"]]
        if dependents:
            raise ValueError(f"task {task_id!r} is required by dependents: {dependents!r}")
        del self._tasks[task_id]

    def set_status(self, task_id: str, status: str) -> None:
        """Set a task's status, validating both id and status."""
        if task_id not in self._tasks:
            raise KeyError(task_id)
        self._tasks[task_id]["status"] = self._validate_status(status)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save(self, path: str) -> None:
        """Serialise the manager to a JSON object on disk.

        The payload is a dict (the contract checks ``json.loads(...)`` is a
        dict) carrying an ordered list of tasks; the order round-trips through
        ``load`` because ``list`` preserves it.
        """
        payload = {
            "version": 1,
            "tasks": [self._public(t) for t in self._tasks.values()],
        }
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "TaskManager":
        """Rebuild a manager from a file written by :meth:`save`.

        Records are restored verbatim (including ids and ``created_at``) and in
        their original order, so ``load(path)`` is a true inverse of ``save``.
        """
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        # Accept either the dict envelope we write or a bare list of tasks.
        records = raw.get("tasks", []) if isinstance(raw, dict) else raw

        manager = cls()
        for record in records:
            task = dict(record)
            # Defensive copies of the list fields so the loaded manager does not
            # alias any parsed structures beyond its own record.
            task["tags"] = list(task.get("tags", []))
            task["depends_on"] = list(task.get("depends_on", []))
            manager._tasks[task["id"]] = task
        return manager

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _public(task: dict[str, Any]) -> dict[str, Any]:
        """Return a deep-enough copy so callers cannot mutate our store."""
        return {
            **task,
            "tags": list(task["tags"]),
            "depends_on": list(task["depends_on"]),
        }

    @staticmethod
    def _validate_priority(priority: Any) -> int:
        """Priority must be an int in 1..5; anything else is a ValueError."""
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ValueError(f"priority must be an integer in 1..5, got {priority!r}")
        if not (MIN_PRIORITY <= priority <= MAX_PRIORITY):
            raise ValueError(f"priority must be in 1..5, got {priority!r}")
        return priority

    @staticmethod
    def _validate_status(status: Any) -> str:
        """Status must be one of the recognised values."""
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status: {status!r}")
        return status

    @staticmethod
    def _normalize_tags(tags: list[str] | None) -> list[str]:
        """Copy the tag list; ``None`` means "no tags"."""
        return list(tags) if tags is not None else []

    @staticmethod
    def _normalize_depends(depends_on: list[str] | None) -> list[str]:
        """Copy the dependency list; ``None`` means "no dependencies"."""
        return list(depends_on) if depends_on is not None else []

    @staticmethod
    def _validate_due_at(due_at: Any) -> str | None:
        """Accept ``None`` or any parseable ISO-8601 string; keep the text as-is.

        We store the caller's original string (rather than a re-serialised
        datetime) so the round-trip test compares equal exactly. ``Z`` is
        normalised to ``+00:00`` only for the parse check, never for storage.
        """
        if due_at is None:
            return None
        if not isinstance(due_at, str) or not due_at.strip():
            raise ValueError(f"due_at must be an ISO-8601 string, got {due_at!r}")
        text = due_at.strip()
        parseable = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            datetime.fromisoformat(parseable)
        except ValueError as exc:
            raise ValueError(f"unparseable due_at: {due_at!r}") from exc
        return text

    @staticmethod
    def _has_cycle(graph: dict[str, dict[str, Any]]) -> bool:
        """Return True if the dependency graph contains a cycle.

        Standard iterative-friendly recursive DFS with three colours: WHITE
        (unvisited), GRAY (on the current stack), BLACK (fully explored). An
        edge to a GRAY node is a back edge and therefore a cycle. The graph is
        small (tasks in memory), so recursion depth is not a practical concern.
        """
        white, gray, black = 0, 1, 2
        color = {node: white for node in graph}

        def visit(node: str) -> bool:
            color[node] = gray
            for dep in graph[node]["depends_on"]:
                # Unknown deps cannot occur post-validation, but skip defensively.
                if dep not in graph:
                    continue
                if color[dep] == gray:
                    return True
                if color[dep] == white and visit(dep):
                    return True
            color[node] = black
            return False

        return any(color[node] == white and visit(node) for node in graph)
