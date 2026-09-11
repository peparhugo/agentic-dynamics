"""Core implementation of :class:`TaskManager`.

Everything here is standard library only.  See the package docstring for the
high-level design rationale.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union

__all__ = ["TaskManager"]

# The three legal lifecycle states.  Anything else is a ValueError.
VALID_STATUSES = ("todo", "doing", "done")

# Priority is a small, bounded integer scale (1 = lowest .. 5 = highest).
MIN_PRIORITY = 1
MAX_PRIORITY = 5
DEFAULT_PRIORITY = 3

# Bumped whenever the on-disk JSON shape changes, so future loaders can branch.
SCHEMA_VERSION = 1

# The set of fields a caller may hand to ``update_task``.  Unknown names are
# rejected rather than silently ignored, which surfaces typos early.
_UPDATABLE_FIELDS = frozenset({"title", "priority", "tags", "depends_on", "due_at", "status"})


class TaskManager:
    """An in-memory collection of tasks with deterministic ordering rules.

    Tasks are stored as dictionaries and identified by a unique string id.
    Public read methods return deep copies so the manager owns its own state.
    """

    def __init__(self, tasks: Optional[Iterable[Mapping[str, Any]]] = None) -> None:
        """Create a manager, optionally seeded with already-built tasks.

        ``tasks`` is primarily used by :meth:`load` to rebuild a manager from a
        saved payload.  Each entry is normalised and validated in the same way
        as :meth:`add_task`, so an externally-supplied task cannot corrupt the
        invariants (valid status/priority, existing dependencies, no cycles).

        Two passes are required: every task must be registered before
        dependencies can be checked, because a saved list may reference a task
        that appears earlier or later in the iteration order.
        """
        # Insertion-ordered mapping: id -> normalised task dict.  Order here is
        # "creation order" and feeds the stable sort in ``list_tasks``.
        self._tasks: "Dict[str, Dict[str, Any]]" = {}

        for raw in tasks or ():
            task = self._normalise_loaded_task(raw)
            # Reject duplicate ids loudly instead of silently overwriting.
            if task["id"] in self._tasks:
                raise ValueError(f"duplicate task id: {task['id']!r}")
            self._tasks[task["id"]] = task

        # Second pass: every dependency must now resolve, and the graph as a
        # whole must be acyclic.
        known = set(self._tasks)
        for task in self._tasks.values():
            for dep_id in task["depends_on"]:
                if dep_id not in known:
                    raise ValueError(f"unknown dependency id: {dep_id!r}")
        self._assert_acyclic(self._tasks)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add_task(
        self,
        title: str,
        *,
        priority: int = DEFAULT_PRIORITY,
        tags: Optional[Sequence[str]] = None,
        depends_on: Optional[Sequence[str]] = None,
        due_at: Optional[str] = None,
    ) -> str:
        """Create a task and return its unique id.

        Defaults match the contract: status ``todo``, priority ``3``, no tags,
        no dependencies, and no due date.  All validation happens before the
        task is inserted, so a failed call mutates nothing.
        """
        # Validate the scalar fields first — cheap checks before graph work.
        self._validate_priority(priority)
        self._validate_due_at(due_at)
        normalised_tags = self._normalise_tags(tags)
        normalised_deps = self._normalise_depends_on(depends_on)

        # Unknown dependencies are a caller error; reject before inserting.
        known = set(self._tasks)
        for dep_id in normalised_deps:
            if dep_id not in known:
                raise ValueError(f"unknown dependency id: {dep_id!r}")

        task_id = uuid.uuid4().hex
        task: Dict[str, Any] = {
            "id": task_id,
            "title": title,
            "status": "todo",
            "priority": priority,
            "tags": normalised_tags,
            "depends_on": normalised_deps,
            "due_at": due_at,
            "created_at": self._now(),
        }

        # A brand-new task cannot be referenced by anyone yet, so it cannot
        # introduce a cycle; still, the acyclicity invariant is cheap to assert.
        candidate = dict(self._tasks)
        candidate[task_id] = task
        self._assert_acyclic(candidate)

        self._tasks[task_id] = task
        return task_id

    def get_task(self, task_id: str) -> Dict[str, Any]:
        """Return a deep copy of the task with ``task_id``.

        Unknown ids raise :class:`KeyError`.  The copy isolates internal state.
        """
        return copy.deepcopy(self._require_task(task_id))

    def update_task(self, task_id: str, **fields: Any) -> Dict[str, Any]:
        """Update one or more fields on an existing task.

        Only the fields in ``_UPDATABLE_FIELDS`` are accepted; anything else is
        a :class:`ValueError`.  All new values are validated against a copy of
        the task and the resulting graph is checked for cycles *before* the
        live state is replaced, so a rejected update is a no-op.
        """
        existing = self._require_task(task_id)

        unknown = set(fields) - _UPDATABLE_FIELDS
        if unknown:
            raise ValueError(f"unknown task field(s): {sorted(unknown)!r}")

        # Work on a copy so a mid-validation failure cannot partially apply.
        updated = copy.deepcopy(existing)

        if "title" in fields:
            updated["title"] = fields["title"]
        if "priority" in fields:
            self._validate_priority(fields["priority"])
            updated["priority"] = fields["priority"]
        if "due_at" in fields:
            self._validate_due_at(fields["due_at"])
            updated["due_at"] = fields["due_at"]
        if "tags" in fields:
            updated["tags"] = self._normalise_tags(fields["tags"])
        if "status" in fields:
            updated["status"] = self._validate_status(fields["status"])
        if "depends_on" in fields:
            deps = self._normalise_depends_on(fields["depends_on"])
            known = set(self._tasks)
            for dep_id in deps:
                if dep_id not in known:
                    raise ValueError(f"unknown dependency id: {dep_id!r}")
            updated["depends_on"] = deps

        # Build the candidate graph with this task swapped in and verify it is
        # still acyclic; only then commit.
        candidate = dict(self._tasks)
        candidate[task_id] = updated
        self._assert_acyclic(candidate)

        self._tasks[task_id] = updated
        return copy.deepcopy(updated)

    def delete_task(self, task_id: str) -> None:
        """Remove a task.

        Raises :class:`KeyError` for an unknown id, and :class:`ValueError` if
        any *other* task still depends on it (delete the dependents first).
        """
        self._require_task(task_id)
        dependents = [
            other["id"]
            for other in self._tasks.values()
            if other["id"] != task_id and task_id in other["depends_on"]
        ]
        if dependents:
            raise ValueError(f"cannot delete {task_id!r}; still required by {sorted(dependents)!r}")
        del self._tasks[task_id]

    def set_status(self, task_id: str, status: str) -> Dict[str, Any]:
        """Transition a task to ``todo``, ``doing`` or ``done``.

        An unrecognised status raises :class:`ValueError`; an unknown id raises
        :class:`KeyError`.
        """
        task = self._require_task(task_id)
        task["status"] = self._validate_status(status)
        return copy.deepcopy(task)

    def list_tasks(
        self,
        *,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return tasks, newest priority first, optionally filtered.

        Ordering is priority descending; ties are broken by creation order
        (dict insertion order) thanks to Python's stable sort.  Filters compose
        with AND semantics.
        """
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

        The result follows the same priority-descending, creation-order rules
        as :meth:`list_tasks`.
        """
        ready = [
            task
            for task in self._tasks.values()
            if task["status"] != "done"
            and all(self._tasks[dep]["status"] == "done" for dep in task["depends_on"])
        ]
        ready.sort(key=lambda task: task["priority"], reverse=True)
        return [copy.deepcopy(task) for task in ready]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save(self, path: Union[str, Path]) -> None:
        """Serialise the manager to ``path`` as JSON.

        The payload is a dict with a schema version and the ordered task list,
        which makes the round-trip lossless (including creation order).
        """
        payload = {
            "version": SCHEMA_VERSION,
            "tasks": [copy.deepcopy(task) for task in self._tasks.values()],
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=False)
            handle.write("\n")

    @classmethod
    def load(cls, path: Union[str, Path]) -> "TaskManager":
        """Rebuild a manager previously written by :meth:`save`.

        Tolerates a bare list of tasks for robustness, but the canonical form is
        the versioned dict emitted by :meth:`save`.
        """
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, Mapping):
            tasks = payload.get("tasks", [])
        else:
            # Backwards/forwards tolerant: accept a naked list of task dicts.
            tasks = payload
        return cls(tasks)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _require_task(self, task_id: str) -> Dict[str, Any]:
        """Return the live (internal) task, or raise KeyError if unknown."""
        try:
            return self._tasks[task_id]
        except KeyError:
            raise KeyError(task_id) from None

    @staticmethod
    def _now() -> str:
        """Return an ISO-8601 UTC timestamp."""
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _validate_priority(priority: Any) -> None:
        """Reject non-integers and values outside ``1..5`` with ValueError."""
        # ``bool`` is an ``int`` subclass; treat it as invalid for clarity.
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ValueError(f"priority must be an integer: {priority!r}")
        if not (MIN_PRIORITY <= priority <= MAX_PRIORITY):
            raise ValueError(
                f"priority must be between {MIN_PRIORITY} and {MAX_PRIORITY}: {priority!r}"
            )

    @staticmethod
    def _validate_status(status: Any) -> str:
        """Return ``status`` unchanged if legal, else raise ValueError."""
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status {status!r}; expected one of {VALID_STATUSES!r}")
        return status

    @staticmethod
    def _validate_due_at(due_at: Any) -> None:
        """Ensure ``due_at`` is ``None`` or a parseable ISO-8601 string."""
        if due_at is None:
            return
        if not isinstance(due_at, str):
            raise ValueError(f"due_at must be an ISO-8601 string: {due_at!r}")
        try:
            # ``fromisoformat`` is stdlib and accepts the timezone-offset form
            # the contract uses (e.g. ``2030-01-02T03:04:05+00:00``).
            datetime.fromisoformat(due_at)
        except ValueError:
            raise ValueError(f"unparseable due_at: {due_at!r}") from None

    @staticmethod
    def _normalise_tags(tags: Optional[Sequence[str]]) -> List[str]:
        """Return a defensive list copy; ``None`` means no tags."""
        if tags is None:
            return []
        # Materialise any iterable (tuple, generator) into a fresh list.
        return list(tags)

    @staticmethod
    def _normalise_depends_on(depends_on: Optional[Sequence[str]]) -> List[str]:
        """Return a de-duplicated, order-preserving list of dependency ids."""
        if depends_on is None:
            return []
        seen: "Dict[str, None]" = {}
        for dep_id in depends_on:
            seen.setdefault(dep_id, None)
        return list(seen)

    def _normalise_loaded_task(self, raw: Mapping[str, Any]) -> Dict[str, Any]:
        """Coerce a persisted/supplied task mapping into the canonical shape.

        This is stricter than :meth:`add_task` only in that it also accepts an
        explicit ``status``/``created_at`` (which ``add_task`` derives); every
        invariant still holds.
        """
        try:
            task_id = raw["id"]
            title = raw["title"]
        except KeyError as exc:  # pragma: no cover - defensive
            raise ValueError(f"task missing required field: {exc.args[0]!r}") from None

        priority = raw.get("priority", DEFAULT_PRIORITY)
        self._validate_priority(priority)

        status = raw.get("status", "todo")
        self._validate_status(status)

        due_at = raw.get("due_at")
        self._validate_due_at(due_at)

        tags = self._normalise_tags(raw.get("tags"))
        depends_on = self._normalise_depends_on(raw.get("depends_on"))

        created_at = raw.get("created_at") or self._now()
        if not isinstance(created_at, str) or not created_at:
            raise ValueError("created_at must be a non-empty string")

        return {
            "id": task_id,
            "title": title,
            "status": status,
            "priority": priority,
            "tags": tags,
            "depends_on": depends_on,
            "due_at": due_at,
            "created_at": created_at,
        }

    @staticmethod
    def _assert_acyclic(tasks: Mapping[str, Mapping[str, Any]]) -> None:
        """Raise ValueError if the dependency graph contains a cycle.

        Standard three-colour depth-first search: ``WHITE`` = unvisited,
        ``GREY`` = on the current recursion stack, ``BLACK`` = fully explored.
        A back-edge to a GREY node is a cycle.  Only dependency edges are
        consulted, via each task's ``depends_on`` list.
        """
        WHITE, GREY, BLACK = 0, 1, 2
        colour: "Dict[str, int]" = {task_id: WHITE for task_id in tasks}

        def visit(node: str) -> None:
            colour[node] = GREY
            for dep in tasks[node]["depends_on"]:
                # Dependencies are validated to exist before this is called.
                state = colour.get(dep, BLACK)
                if state == GREY:
                    raise ValueError("dependency cycle detected")
                if state == WHITE:
                    visit(dep)
            colour[node] = BLACK

        for task_id in tasks:
            if colour[task_id] == WHITE:
                visit(task_id)
