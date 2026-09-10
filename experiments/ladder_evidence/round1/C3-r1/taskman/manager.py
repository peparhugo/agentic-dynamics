"""Core task-manager implementation for the ``taskman`` package.

Design notes (chosen internally — see the module-level docstring of the package):

* **Storage** — tasks live in one insertion-ordered ``dict`` keyed by id. A plain
  ``dict`` preserves creation order for free (Python 3.7+), which is exactly the
  tie-breaker ``list_tasks`` needs for equal priorities, so no separate sequence
  number has to be maintained.
* **Reverse index** — ``_dependents`` maps ``task_id -> {ids that depend on it}``.
  Keeping it alongside the forward ``depends_on`` edges makes the two expensive
  questions cheap: "may I delete this?" is a set lookup, and dependency-graph
  walks for cycle detection do not have to scan every task.
* **Cycle detection** — a new edge can only ever introduce a cycle that passes
  through the task being edited (the rest of the graph was already acyclic), so
  a single reachability check from the candidate dependencies back to the edited
  task is sufficient. It runs *before* any mutation, which is what makes the
  "leaves state unchanged" guarantee trivially true.
* **Isolation** — :meth:`TaskManager.get_task` and :meth:`TaskManager.list_tasks`
  return deep copies, so a caller cannot mutate the manager's internal state by
  editing a returned dictionary or list.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = ["TaskManager"]

#: The closed set of lifecycle statuses a task may occupy.
VALID_STATUSES = ("todo", "doing", "done")

#: Inclusive bounds for the integer ``priority`` field (1 = highest, 5 = lowest).
PRIORITY_MIN = 1
PRIORITY_MAX = 5

#: The default priority applied when the caller does not supply one.
DEFAULT_PRIORITY = 3

#: Identifier used to distinguish "argument omitted" from an explicit ``None``
#: in :meth:`TaskManager.update_task`. A genuine ``None`` is a meaningful value
#: for ``due_at`` (meaning "no deadline"), so the two cases must not be conflated.
_UNSET: Any = object()

#: Bump when the on-disk representation changes shape; :meth:`TaskManager.load`
#: refuses documents written by an unknown future schema rather than guessing.
SCHEMA = "taskman/v1"


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with an explicit offset.

    Timezone-aware output (the ``+00:00`` suffix) keeps stored timestamps
    unambiguous when a file saved on one machine is loaded on another.
    """
    return datetime.now(timezone.utc).isoformat()


def _validate_priority(priority: Any) -> int:
    """Validate ``priority`` and return it as a plain ``int`` (or raise).

    ``bool`` is deliberately rejected even though it is an ``int`` subclass:
    ``True``/``False`` would silently become priorities 1/0, which is almost
    certainly a caller bug rather than an intent to set a priority.
    """
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError(f"priority must be an integer, got {priority!r}")
    if not (PRIORITY_MIN <= priority <= PRIORITY_MAX):
        raise ValueError(
            f"priority must be between {PRIORITY_MIN} and {PRIORITY_MAX}, got {priority!r}"
        )
    return priority


def _validate_due_at(due_at: Any) -> str | None:
    """Validate an optional due date, returning the untouched string.

    The value is validated but *not* normalised: the contract's round-trip test
    requires the exact string that was supplied to come back out, so reformatting
    through ``datetime`` (which could change offsets or drop sub-second digits)
    would be wrong. Parseability is the only thing being checked here.
    """
    if due_at is None:
        return None
    if not isinstance(due_at, str):
        raise ValueError(f"due_at must be an ISO-8601 string or None, got {due_at!r}")
    try:
        datetime.fromisoformat(due_at)
    except ValueError as exc:  # re-raise with a message that names the field
        raise ValueError(f"due_at is not a valid ISO-8601 date: {due_at!r}") from exc
    return due_at


def _coerce_tags(tags: Any) -> list[str]:
    """Return a fresh list of string tags.

    Accepting ``None`` as "no tags" matches the ``add_task`` default. A copy is
    always made so the caller's list cannot alias the manager's internal state.
    """
    if tags is None:
        return []
    return [str(tag) for tag in tags]


class TaskManager:
    """An in-memory task store with dependencies, priorities and JSON persistence.

    The class is intentionally a plain state container plus a small set of
    invariant-preserving mutators. Every public mutator validates fully before
    touching state, so a failed call always leaves the manager exactly as it
    was.
    """

    def __init__(self) -> None:
        """Create an empty manager."""
        #: ``task_id -> task dict``; insertion order doubles as creation order.
        self._tasks: dict[str, dict[str, Any]] = {}
        #: ``task_id -> set(task_ids that list it in depends_on)``.
        self._dependents: dict[str, set[str]] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _require(self, task_id: str) -> dict[str, Any]:
        """Return the live task record for ``task_id`` or raise ``KeyError``."""
        try:
            return self._tasks[task_id]
        except KeyError:
            raise KeyError(f"unknown task id: {task_id!r}") from None

    def _creates_cycle(self, task_id: str, depends_on: list[str]) -> bool:
        """Return ``True`` if ``task_id``'s proposed dependencies close a cycle.

        The check follows forward dependency edges starting from each proposed
        dependency. If the walk ever arrives back at ``task_id``, the proposed
        edit would form a loop. Only ``task_id``'s edges are overridden, so the
        call is a pure function of the current state.
        """

        def dependencies_of(node: str) -> list[str]:
            if node == task_id:  # candidate edges take precedence
                return depends_on
            return self._tasks[node]["depends_on"]

        seen: set[str] = set()
        stack: list[str] = list(depends_on)
        while stack:
            node = stack.pop()
            if node == task_id:
                return True
            if node in seen:
                continue
            seen.add(node)
            stack.extend(dependencies_of(node))
        return False

    def _link(self, task_id: str, depends_on: list[str]) -> None:
        """Register the reverse-index entries for a task's dependencies."""
        for dependency in depends_on:
            self._dependents.setdefault(dependency, set()).add(task_id)

    def _unlink(self, task_id: str, depends_on: list[str]) -> None:
        """Drop a task's reverse-index entries (used when dependencies change)."""
        for dependency in depends_on:
            holders = self._dependents.get(dependency)
            if holders is not None:
                holders.discard(task_id)
                if not holders:
                    self._dependents.pop(dependency, None)

    def _validate_dependencies(self, depends_on: Any) -> list[str]:
        """Coerce and validate a dependency list, returning a fresh list.

        Every referenced id must already exist. This is checked before any
        mutation so an unknown dependency can never be partially applied.
        """
        if depends_on is None:
            return []
        resolved = [str(dep) for dep in depends_on]
        for dependency in resolved:
            if dependency not in self._tasks:
                raise ValueError(f"unknown dependency id: {dependency!r}")
        return resolved

    # ------------------------------------------------------------------
    # CRUD
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
        """Create a task and return its unique id.

        Defaults: ``status='todo'``, ``priority=3``, empty tags/dependencies and
        no due date. ``ValueError`` is raised for an out-of-range priority, an
        unparseable ``due_at``, an unknown dependency id, or a dependency cycle.
        """
        # Validate everything up front; the task does not exist yet, so failure
        # here provably leaves the store untouched.
        priority = _validate_priority(priority)
        due_at = _validate_due_at(due_at)
        resolved_tags = _coerce_tags(tags)
        resolved_deps = self._validate_dependencies(depends_on)

        # A brand-new id cannot be referenced by existing tasks, so the only
        # possible cycle would be a self-reference; the general check costs
        # little and documents the invariant.
        task_id = uuid.uuid4().hex
        if self._creates_cycle(task_id, resolved_deps):
            raise ValueError("dependency cycle detected")

        record: dict[str, Any] = {
            "id": task_id,
            "title": str(title),
            "status": "todo",
            "priority": priority,
            "tags": resolved_tags,
            "depends_on": resolved_deps,
            "due_at": due_at,
            "created_at": _now_iso(),
        }
        self._tasks[task_id] = record
        self._link(task_id, resolved_deps)
        return task_id

    def get_task(self, task_id: str) -> dict[str, Any]:
        """Return a deep copy of the task, or raise ``KeyError`` if unknown."""
        return copy.deepcopy(self._require(task_id))

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
        """Update the supplied fields of an existing task.

        Fields not passed are left untouched. Unknown ids raise ``KeyError``;
        invalid values raise ``ValueError``. The whole edit is validated (and
        any cycle detected) before state changes, so a rejected update leaves
        the store unchanged.

        Note the sentinel default: ``due_at=None`` explicitly clears the due
        date, whereas omitting ``due_at`` leaves it as-is.
        """
        record = self._require(task_id)  # KeyError for unknown ids

        # Stage the candidate values, reading current values for omitted fields.
        new_title = record["title"] if title is _UNSET else str(title)
        new_priority = record["priority"] if priority is _UNSET else _validate_priority(priority)
        new_tags = record["tags"] if tags is _UNSET else _coerce_tags(tags)
        new_due_at = record["due_at"] if due_at is _UNSET else _validate_due_at(due_at)

        if depends_on is _UNSET:
            new_deps = record["depends_on"]
        else:
            new_deps = self._validate_dependencies(depends_on)
            if self._creates_cycle(task_id, new_deps):
                raise ValueError("dependency cycle detected")

        # Apply. Deps are the only field with a reverse-index side effect, and
        # only when they actually changed.
        record["title"] = new_title
        record["priority"] = new_priority
        record["tags"] = new_tags
        record["due_at"] = new_due_at
        if depends_on is not _UNSET and new_deps != record["depends_on"]:
            self._unlink(task_id, record["depends_on"])
            record["depends_on"] = new_deps
            self._link(task_id, new_deps)
        elif depends_on is not _UNSET:
            record["depends_on"] = new_deps

    def delete_task(self, task_id: str) -> None:
        """Delete a task, or raise if unknown / still depended upon.

        ``KeyError`` for an unknown id. ``ValueError`` if any other task lists
        this one in ``depends_on`` — deleting it would leave dangling edges.
        """
        self._require(task_id)
        dependents = self._dependents.get(task_id)
        if dependents:
            raise ValueError(f"cannot delete {task_id!r}: depended on by {sorted(dependents)!r}")
        record = self._tasks.pop(task_id)
        # Clean the deleted task's own outgoing edges from the reverse index.
        self._unlink(task_id, record["depends_on"])
        self._dependents.pop(task_id, None)

    def set_status(self, task_id: str, status: str) -> None:
        """Transition a task to ``todo``/``doing``/``done``.

        Unknown ids raise ``KeyError``; any status outside the closed set raises
        ``ValueError``.
        """
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status: {status!r} (expected one of {VALID_STATUSES})")
        self._require(task_id)["status"] = status

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def list_tasks(
        self,
        *,
        status: str | None = None,
        priority: int | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return copied tasks matching all supplied filters.

        Ordering is priority descending; ties retain creation order. All filters
        are optional and combine conjunctively.
        """
        matches: list[dict[str, Any]] = []
        for record in self._tasks.values():
            if status is not None and record["status"] != status:
                continue
            if priority is not None and record["priority"] != priority:
                continue
            if tag is not None and tag not in record["tags"]:
                continue
            matches.append(record)
        # ``sorted`` is stable, so equal priorities keep insertion order.
        matches.sort(key=lambda task: task["priority"], reverse=True)
        return copy.deepcopy(matches)

    def ready_tasks(self) -> list[dict[str, Any]]:
        """Return not-done tasks whose dependencies are all done.

        A task with no dependencies is ready immediately. Completed (``done``)
        tasks are never returned.
        """
        ready: list[dict[str, Any]] = []
        for record in self._tasks.values():
            if record["status"] == "done":
                continue
            if all(self._tasks[dep]["status"] == "done" for dep in record["depends_on"]):
                ready.append(record)
        return copy.deepcopy(ready)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save(self, path: str) -> None:
        """Serialise the store to ``path`` as JSON.

        The on-disk shape is a mapping with a ``schema`` tag and a ``tasks``
        mapping keyed by id; :meth:`load` rebuilds the reverse index from the
        embedded ``depends_on`` edges rather than trusting a cached copy.
        """
        document = {
            "schema": SCHEMA,
            "tasks": {task_id: record for task_id, record in self._tasks.items()},
        }
        target = Path(path)
        target.write_text(json.dumps(document, indent=2, sort_keys=True))

    @classmethod
    def load(cls, path: str) -> "TaskManager":
        """Reconstruct a :class:`TaskManager` previously written by :meth:`save`.

        Raises ``ValueError`` for a document whose schema tag is missing or not
        recognised, so a future/foreign file fails loudly instead of loading a
        half-understood state.
        """
        document = json.loads(Path(path).read_text())
        if not isinstance(document, dict) or document.get("schema") != SCHEMA:
            raise ValueError(f"unrecognised taskman document at {path!r}")

        manager = cls()
        for task_id, record in document["tasks"].items():
            # Copy on the way in so the parsed JSON tree is not retained.
            manager._tasks[task_id] = copy.deepcopy(record)
            manager._link(task_id, record["depends_on"])
        return manager
