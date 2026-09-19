"""``taskman`` — a tiny, pure-Python, stdlib-only task manager.

The public surface is a single class, :class:`TaskManager`, which stores tasks in
memory and can serialise them to/from JSON.  The design goals, in order:

* **Behaviour over cleverness** — every rule in the contract (id uniqueness,
  status/priority/due-date validation, dependency existence + acyclicity,
  delete-while-depended-on protection, deterministic ordering) is enforced in
  one obvious place.
* **Atomicity** — a mutating call either fully succeeds or leaves the manager
  byte-for-byte unchanged.  Validation therefore always precedes mutation, and
  multi-field updates are staged on a candidate copy before being committed.
* **No shared mutable state** — each :class:`TaskManager` owns its own storage;
  nothing lives at module or class scope, and list-valued fields are copied on
  both ingress (``add_task``/``update_task``) and egress (``get_task``).
* **Determinism** — tasks carry an internal creation sequence so that sorting
  is stable across save/load and never depends on dict hash order.

Only the standard library is used: ``json``, ``uuid``, ``copy``, ``datetime``.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

__all__ = ["TaskManager"]

#: The only legal task statuses.  ``set_status`` refuses anything else.
VALID_STATUSES: tuple[str, ...] = ("todo", "doing", "done")

#: Inclusive range for ``priority`` (1 = lowest, 5 = highest).
MIN_PRIORITY: int = 1
MAX_PRIORITY: int = 5

#: Default priority applied by :meth:`TaskManager.add_task`.
DEFAULT_PRIORITY: int = 3

#: Fields a caller may change through :meth:`TaskManager.update_task`.
_UPDATABLE_FIELDS: frozenset[str] = frozenset(
    {"title", "priority", "tags", "depends_on", "due_at", "status"}
)

#: Schema tag written into save files so a future format change is detectable.
_SAVE_FORMAT_VERSION: int = 1


class TaskManager:
    """An in-memory collection of tasks with dependency tracking.

    All state is instance-local.  A fresh ``TaskManager()`` is empty; use
    :meth:`load` to restore a previously :meth:`save`-d serialised manager.
    """

    def __init__(self) -> None:
        """Create an empty manager with no tasks and a fresh sequence counter."""
        # ``_tasks`` is the source of truth: task_id -> task record.
        self._tasks: dict[str, dict[str, Any]] = {}
        # ``_order`` records insertion rank per id.  We keep it explicitly rather
        # than relying on dict ordering so that ordering survives a JSON round
        # trip and is robust if the dict is ever rebuilt.
        self._order: dict[str, int] = {}
        # Monotonic counter handed out to each newly created task.
        self._next_order: int = 0

    # ------------------------------------------------------------------
    # Validation helpers (all raise ValueError on bad input)
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_priority(priority: Any) -> None:
        """Ensure *priority* is an ``int`` within 1..5.

        ``bool`` is rejected explicitly even though it is an ``int`` subclass,
        because ``True`` silently masquerading as priority 1 is a bug, not a
        feature.
        """
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ValueError(f"priority must be an integer, got {priority!r}")
        if not MIN_PRIORITY <= priority <= MAX_PRIORITY:
            raise ValueError(
                f"priority must be between {MIN_PRIORITY} and {MAX_PRIORITY}, got {priority!r}"
            )

    @staticmethod
    def _validate_due_at(due_at: Any) -> None:
        """Ensure *due_at* is ``None`` or a parseable ISO-8601 timestamp string.

        The *original* string is preserved on the record (so the exact
        representation round-trips); this only proves it is a real datetime.
        """
        if due_at is None:
            return
        if not isinstance(due_at, str):
            raise ValueError(f"due_at must be an ISO-8601 string or None, got {due_at!r}")
        # Normalise a trailing RFC-3339 "Z" (UTC) for *parsing only*.  Python 3.10's
        # ``fromisoformat`` does not accept "Z" even though it is valid ISO-8601, so
        # translating it here accepts a strict superset of timestamps; the caller's
        # original string is what we store, preserving the exact representation.
        parse_target = due_at[:-1] + "+00:00" if due_at.endswith(("Z", "z")) else due_at
        try:
            datetime.fromisoformat(parse_target)
        except ValueError as exc:
            # Re-raise with task-level context rather than leaking the parser's
            # message; the contract only requires a ValueError.
            raise ValueError(f"due_at is not a valid ISO-8601 timestamp: {due_at!r}") from exc

    @staticmethod
    def _validate_status(status: Any) -> None:
        """Ensure *status* is one of :data:`VALID_STATUSES`."""
        if status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")

    def _validate_dependencies_exist(self, depends_on: list[str]) -> None:
        """Ensure every dependency id refers to a task that already exists.

        Referencing an unknown id is a ``ValueError`` (not a ``KeyError``):
        the caller supplied a bad argument, rather than asking for a missing
        task by id.
        """
        for dep_id in depends_on:
            if dep_id not in self._tasks:
                raise ValueError(f"unknown dependency id: {dep_id!r}")

    # ------------------------------------------------------------------
    # Cycle detection
    # ------------------------------------------------------------------

    @staticmethod
    def _has_cycle(adjacency: dict[str, list[str]]) -> bool:
        """Return ``True`` if the ``depends_on`` graph in *adjacency* has a cycle.

        Standard three-colour depth-first search: WHITE = unvisited (absent
        from ``colour``), GRAY = on the current recursion stack, BLACK =
        finished.  Encountering a GRAY node means a back-edge, i.e. a cycle.
        Walking the *whole* graph (not just the edited node) also catches any
        transitive cycle and is cheap for the task sizes this manager targets.
        """
        colour: dict[str, int] = {}
        # 1 = gray (on stack), 2 = black (done)
        for start in adjacency:
            if colour.get(start):
                continue
            stack: list[tuple[str, int]] = [(start, 0)]
            colour[start] = 1
            while stack:
                node, child_index = stack[-1]
                children = adjacency.get(node, [])
                if child_index < len(children):
                    child = children[child_index]
                    stack[-1] = (node, child_index + 1)
                    state = colour.get(child, 0)
                    if state == 1:
                        # Back-edge to a node still on the stack => cycle.
                        return True
                    if state == 0:
                        colour[child] = 1
                        stack.append((child, 0))
                else:
                    colour[node] = 2
                    stack.pop()
        return False

    def _adjacency_with_override(self, task_id: str, deps: list[str]) -> dict[str, list[str]]:
        """Build the dependency graph, replacing *task_id*'s edges with *deps*.

        Used before committing an update so cycle detection sees the *proposed*
        state while all other tasks keep their current edges.
        """
        adjacency: dict[str, list[str]] = {
            tid: list(task["depends_on"]) for tid, task in self._tasks.items()
        }
        adjacency[task_id] = list(deps)
        return adjacency

    # ------------------------------------------------------------------
    # Creation / lookup
    # ------------------------------------------------------------------

    def _new_id(self) -> str:
        """Mint a collision-free task id.

        ``uuid4`` is used instead of ``len(self._tasks)`` precisely so that
        deleting tasks can never cause a previously-used id to be reissued.
        """
        return uuid.uuid4().hex

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

        Defaults: status ``todo``, priority ``3``, empty ``tags``/``depends_on``,
        and ``None`` due date.  All arguments are validated *before* any state
        changes, so a rejected call creates nothing.
        """
        if not isinstance(title, str) or not title:
            raise ValueError("title must be a non-empty string")
        self._validate_priority(priority)
        self._validate_due_at(due_at)

        # Copy incoming lists so later mutation of the caller's list is invisible.
        dep_ids = list(depends_on) if depends_on is not None else []
        tag_list = list(tags) if tags is not None else []
        self._validate_dependencies_exist(dep_ids)

        task_id = self._new_id()
        # A brand-new task has no dependents, so its edges alone cannot close a
        # cycle; no graph check is needed here.
        self._tasks[task_id] = {
            "id": task_id,
            "title": title,
            "status": "todo",
            "priority": priority,
            "tags": tag_list,
            "depends_on": dep_ids,
            "due_at": due_at,
            # ISO-8601 UTC; the contract only requires a non-empty string.
            "created_at": datetime.now().astimezone().isoformat(),
        }
        self._order[task_id] = self._next_order
        self._next_order += 1
        return task_id

    def get_task(self, task_id: str) -> dict[str, Any]:
        """Return a deep copy of the task record for *task_id*.

        A copy (not the internal dict) is returned so callers cannot mutate
        manager state through the result.  Unknown ids raise ``KeyError``.
        """
        if task_id not in self._tasks:
            raise KeyError(task_id)
        return copy.deepcopy(self._tasks[task_id])

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def update_task(self, task_id: str, **fields: Any) -> None:
        """Update one or more mutable fields of an existing task.

        Supported fields: ``title``, ``priority``, ``tags``, ``depends_on``,
        ``due_at``, ``status``.  The operation is atomic: every field is
        validated against a candidate record first, and only if all pass is the
        record swapped in.  An unknown id raises ``KeyError``; any invalid value
        (bad priority/date/status, unknown dependency, or a dependency edge that
        would create a cycle) raises ``ValueError`` with the original task left
        untouched.
        """
        if task_id not in self._tasks:
            raise KeyError(task_id)

        unknown = set(fields) - _UPDATABLE_FIELDS
        if unknown:
            raise ValueError(f"unknown field(s): {sorted(unknown)}")

        # Stage all changes on a copy; ``self._tasks`` stays pristine until commit.
        candidate = copy.deepcopy(self._tasks[task_id])

        if "title" in fields:
            title = fields["title"]
            if not isinstance(title, str) or not title:
                raise ValueError("title must be a non-empty string")
            candidate["title"] = title
        if "priority" in fields:
            self._validate_priority(fields["priority"])
            candidate["priority"] = fields["priority"]
        if "tags" in fields:
            tags = fields["tags"]
            candidate["tags"] = list(tags) if tags is not None else []
        if "due_at" in fields:
            self._validate_due_at(fields["due_at"])
            candidate["due_at"] = fields["due_at"]
        if "status" in fields:
            self._validate_status(fields["status"])
            candidate["status"] = fields["status"]
        if "depends_on" in fields:
            deps = fields["depends_on"]
            dep_ids = list(deps) if deps is not None else []
            self._validate_dependencies_exist(dep_ids)
            # Reject before committing so the "state unchanged" contract holds.
            if self._has_cycle(self._adjacency_with_override(task_id, dep_ids)):
                raise ValueError("dependency update would create a cycle")
            candidate["depends_on"] = dep_ids

        # All validations passed — commit atomically by replacing the record.
        self._tasks[task_id] = candidate

    def set_status(self, task_id: str, status: str) -> None:
        """Set the status of *task_id* to one of ``todo``/``doing``/``done``.

        Unknown ids raise ``KeyError``; an illegal status raises ``ValueError``
        and changes nothing.
        """
        if task_id not in self._tasks:
            raise KeyError(task_id)
        self._validate_status(status)
        self._tasks[task_id]["status"] = status

    def delete_task(self, task_id: str) -> None:
        """Delete *task_id*, unless another task still depends on it.

        Unknown ids raise ``KeyError``.  If any surviving task lists *task_id*
        in its ``depends_on``, a ``ValueError`` is raised and nothing is removed.
        """
        if task_id not in self._tasks:
            raise KeyError(task_id)
        for task in self._tasks.values():
            if task_id in task["depends_on"]:
                raise ValueError(
                    f"cannot delete {task_id!r}: task {task['id']!r} still depends on it"
                )
        del self._tasks[task_id]
        self._order.pop(task_id, None)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def _creation_rank(self, task_id: str) -> int:
        """Return the stored creation rank for stable tie-breaking."""
        return self._order.get(task_id, 0)

    def list_tasks(
        self,
        *,
        status: str | None = None,
        priority: int | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return tasks matching all supplied filters, priority-descending.

        Ties keep creation order.  ``status``, ``priority`` and ``tag`` combine
        with AND semantics; each may be omitted.
        """
        selected = [
            task
            for task in self._tasks.values()
            if (status is None or task["status"] == status)
            and (priority is None or task["priority"] == priority)
            and (tag is None or tag in task["tags"])
        ]
        # Explicit compound key: higher priority first, then creation rank.
        # Sorting is stable and the rank makes ordering independent of dict order.
        selected.sort(key=lambda t: (-t["priority"], self._creation_rank(t["id"])))
        return copy.deepcopy(selected)

    def ready_tasks(self) -> list[dict[str, Any]]:
        """Return not-done tasks whose dependencies are all ``done``.

        Tasks with no dependencies are ready immediately.  Results are returned
        in creation order.
        """
        ready = [
            task
            for task in self._tasks.values()
            if task["status"] != "done"
            # No dependency may be missing (delete is blocked while depended on)
            # or unfinished.
            and all(self._tasks[dep]["status"] == "done" for dep in task["depends_on"])
        ]
        ready.sort(key=lambda t: self._creation_rank(t["id"]))
        return copy.deepcopy(ready)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Write the manager's tasks to *path* as JSON.

        The payload is a dict so that ``json.loads(...)`` yields a mapping, and
        tasks are written in creation order so the file is stable and diffable.
        """
        ordered = sorted(self._tasks.values(), key=lambda t: self._creation_rank(t["id"]))
        payload = {
            "version": _SAVE_FORMAT_VERSION,
            "tasks": copy.deepcopy(ordered),
        }
        Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True))

    @classmethod
    def load(cls, path: str) -> TaskManager:
        """Load a manager previously written by :meth:`save`.

        State is restored *directly* rather than through :meth:`add_task`, so
        ids and ``created_at`` timestamps are preserved exactly as saved.  The
        file's task order is treated as the creation order.
        """
        payload = json.loads(Path(path).read_text())
        manager = cls()
        for rank, task in enumerate(payload.get("tasks", [])):
            record = copy.deepcopy(task)
            manager._tasks[record["id"]] = record
            manager._order[record["id"]] = rank
        manager._next_order = len(manager._order)
        return manager
