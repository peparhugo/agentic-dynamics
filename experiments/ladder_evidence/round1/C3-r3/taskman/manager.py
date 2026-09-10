"""Core implementation of :class:`TaskManager`.

Design notes
------------
* **Storage model.** Tasks live in a single ``dict[str, dict]`` keyed by id.
  Python 3.7+ guarantees dict insertion order, so *creation order* falls out
  for free and needs no separate sequence counter. That matters for the
  contract's tie-breaking rule ("equal priority keeps creation order"): a
  stable sort over insertion order reproduces it exactly, before and after a
  JSON round-trip (the serializer writes tasks in list order).
* **Defensive copies.** ``get_task``/``list_tasks`` return ``deepcopy``s so a
  caller cannot mutate internal state by accident (e.g. appending to the
  returned ``tags`` list). This keeps validation meaningful: every write goes
  through a public mutator that validates first.
* **Validate-before-mutate.** Any operation that can fail (bad priority,
  unknown dependency, cycle) computes and checks the full new state *before*
  touching the store. The contract requires a rejected edit to leave state
  unchanged, and an all-or-nothing approach is the simplest way to guarantee
  that invariant.
* **Ids.** ``uuid4().hex`` gives collision-free ids without coordination and
  without a counter that would need persisting. They are opaque strings; the
  contract only requires uniqueness.
* **Timestamps.** ``created_at`` is an ISO-8601 UTC string. ``due_at`` is
  validated for parseability but stored *verbatim* — the contract asserts the
  exact input string round-trips, so normalising it would be wrong.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# --- frozen policy constants -------------------------------------------------
# These three names are the single source of truth for the rules; every method
# below references them rather than re-typing literals, so changing a rule is a
# one-line edit. They are exported for callers that want to validate up front.
TASK_STATUSES = ("todo", "doing", "done")
MIN_PRIORITY = 1
MAX_PRIORITY = 5

#: Fields a caller is allowed to set on ``update_task``. Anything outside this
#: set is a typo, not a feature, so it is rejected loudly (TypeError).
_UPDATABLE_FIELDS = frozenset({"title", "status", "priority", "tags", "depends_on", "due_at"})


class TaskManager:
    """An in-memory, JSON-persistable store of tasks.

    The class intentionally exposes a small, explicit API instead of the raw
    dictionaries: every mutation validates its inputs, and every read hands back
    a copy. That makes the store's invariants (valid status, acyclic
    dependencies, no dangling dependency ids, unique ids) true by construction
    rather than by convention.
    """

    # ------------------------------------------------------------------ setup
    def __init__(self) -> None:
        # ``_tasks`` maps id -> task record. Insertion order is creation order.
        self._tasks: dict[str, dict[str, Any]] = {}

    # --------------------------------------------------------------- creation
    def add_task(
        self,
        title: str,
        *,
        priority: int = 3,
        tags: Iterable[str] | None = None,
        depends_on: Iterable[str] | None = None,
        due_at: str | None = None,
    ) -> str:
        """Create a task and return its freshly minted unique id.

        ``title`` is intentionally the only positional argument: everything else
        has a documented default (priority 3, no tags, no dependencies, no due
        date), matching the contract's stated defaults.

        Raises
        ------
        ValueError
            If ``priority`` is outside ``1..5``, ``due_at`` is not a parseable
            ISO-8601 timestamp, or any id in ``depends_on`` is unknown.
        """
        priority = self._validate_priority(priority)
        due_at = self._validate_due_at(due_at)
        tag_list = self._normalise_str_list(tags, field="tags")
        dep_list = self._normalise_str_list(depends_on, field="depends_on")

        # A new task cannot create a cycle with *existing* tasks unless it (or a
        # transitive dependency) points back at itself, which is impossible for
        # an id that did not exist a moment ago. We still run the closure check
        # so dangling ids are rejected with the same message as elsewhere.
        self._validate_dependencies(dep_list)

        task_id = uuid.uuid4().hex
        self._tasks[task_id] = {
            "id": task_id,
            "title": title,
            "status": "todo",  # every task starts in the backlog
            "priority": priority,
            "tags": tag_list,
            "depends_on": dep_list,
            "due_at": due_at,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return task_id

    # ------------------------------------------------------------------ reads
    def get_task(self, task_id: str) -> dict[str, Any]:
        """Return a defensive copy of the task, or raise ``KeyError`` if absent."""
        return copy.deepcopy(self._require(task_id))

    def list_tasks(
        self,
        *,
        status: str | None = None,
        priority: int | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return tasks matching the optional filters, ordered priority desc.

        Ties keep creation order because :func:`sorted` is stable and the source
        iterable is in insertion (creation) order. Filters compose with AND, so
        ``status="doing", priority=5`` means both must hold.
        """
        selected = [
            task
            for task in self._tasks.values()
            # ``status``/``priority`` are compared exactly; ``tag`` is membership
            # in the task's tag list (a task may carry many tags).
            if (status is None or task["status"] == status)
            and (priority is None or task["priority"] == priority)
            and (tag is None or tag in task["tags"])
        ]
        selected.sort(key=lambda task: task["priority"], reverse=True)
        return [copy.deepcopy(task) for task in selected]

    def ready_tasks(self) -> list[dict[str, Any]]:
        """Return not-done tasks whose dependencies are all done.

        "Ready" is the scheduling predicate: nothing blocks the task. A task
        with no dependencies is trivially ready; a done task is never returned
        because it is already finished.
        """
        ready: list[dict[str, Any]] = []
        for task in self._tasks.values():
            if task["status"] == "done":
                continue
            # Every dependency must exist (validated on write) *and* be done.
            if all(self._tasks.get(dep, {}).get("status") == "done" for dep in task["depends_on"]):
                ready.append(copy.deepcopy(task))
        return ready

    # ------------------------------------------------------------------ writes
    def update_task(self, task_id: str, **fields: Any) -> dict[str, Any]:
        """Apply ``fields`` to an existing task and return the updated copy.

        Unknown ids raise ``KeyError``; unknown field names raise ``TypeError``.
        Validation is all-or-nothing: if *any* supplied field is invalid the
        store is left exactly as it was. That is what allows the contract's
        cycle test to assert the original ``depends_on`` survived a rejected
        edit.
        """
        current = self._require(task_id)

        unknown = set(fields) - _UPDATABLE_FIELDS
        if unknown:
            names = ", ".join(sorted(unknown))
            raise TypeError(f"update_task got unexpected field(s): {names}")

        # Build the candidate record by starting from a copy of the current one.
        # Nothing is committed until every field has been validated.
        candidate = copy.deepcopy(current)

        if "priority" in fields:
            candidate["priority"] = self._validate_priority(fields["priority"])
        if "due_at" in fields:
            candidate["due_at"] = self._validate_due_at(fields["due_at"])
        if "title" in fields:
            candidate["title"] = fields["title"]
        if "tags" in fields:
            candidate["tags"] = self._normalise_str_list(fields["tags"], field="tags")
        if "status" in fields:
            candidate["status"] = self._validate_status(fields["status"])
        if "depends_on" in fields:
            dep_list = self._normalise_str_list(fields["depends_on"], field="depends_on")
            self._validate_dependencies(dep_list)
            # The candidate is only installed if the new edges stay acyclic.
            self._validate_no_cycle(task_id, dep_list)
            candidate["depends_on"] = dep_list

        self._tasks[task_id] = candidate
        return copy.deepcopy(candidate)

    def delete_task(self, task_id: str) -> None:
        """Delete a task, refusing while other tasks depend on it.

        Raises ``KeyError`` for an unknown id and ``ValueError`` if any other
        task lists ``task_id`` as a dependency — deleting it would leave a
        dangling edge, which the store forbids.
        """
        self._require(task_id)
        dependents = [t["id"] for t in self._tasks.values() if task_id in t["depends_on"]]
        if dependents:
            raise ValueError(f"cannot delete task {task_id!r}: still required by {dependents}")
        del self._tasks[task_id]

    def set_status(self, task_id: str, status: str) -> dict[str, Any]:
        """Set a task's status; unknown ids raise ``KeyError``, bad status ``ValueError``."""
        task = self._require(task_id)
        task["status"] = self._validate_status(status)
        return copy.deepcopy(task)

    # ------------------------------------------------------------ persistence
    def save(self, path: str) -> None:
        """Write the whole store to ``path`` as JSON.

        The top-level value is an object (``{"version": ..., "tasks": [...]}``)
        rather than a bare list, so the format can gain fields without a
        breaking change and so the contract's ``isinstance(..., dict)``
        assertion holds. Tasks are written in creation order to preserve the
        tie-break ordering across a round-trip.
        """
        payload = {
            "version": 1,
            "tasks": [copy.deepcopy(task) for task in self._tasks.values()],
        }
        Path(path).write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "TaskManager":
        """Rebuild a manager from a file written by :meth:`save`.

        The loader trusts the file's internal shape only so far: it re-installs
        records in file order (preserving creation order) and does not re-run
        validation, because the file was produced by a manager that already
        enforced every invariant. A malformed file surfaces as the natural
        ``json``/``KeyError`` error rather than a silent empty store.
        """
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        manager = cls()
        for task in raw["tasks"]:
            manager._tasks[task["id"]] = copy.deepcopy(task)
        return manager

    # ---------------------------------------------------------------- helpers
    def _require(self, task_id: str) -> dict[str, Any]:
        """Fetch the live record or raise ``KeyError`` — the single existence gate."""
        try:
            return self._tasks[task_id]
        except KeyError:
            # Re-raise with a friendlier message while keeping the KeyError type
            # the contract expects.
            raise KeyError(f"unknown task id: {task_id!r}") from None

    @staticmethod
    def _validate_priority(priority: Any) -> int:
        """Return ``priority`` if it is an int in ``1..5``, else raise ``ValueError``.

        ``bool`` is excluded explicitly because ``True`` is an ``int`` in Python
        and would otherwise slip through as priority 1.
        """
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ValueError(f"priority must be an integer, got {priority!r}")
        if not (MIN_PRIORITY <= priority <= MAX_PRIORITY):
            raise ValueError(
                f"priority must be between {MIN_PRIORITY} and {MAX_PRIORITY}, got {priority}"
            )
        return priority

    @staticmethod
    def _validate_status(status: Any) -> str:
        """Return ``status`` if it is one of the three known states."""
        if status not in TASK_STATUSES:
            raise ValueError(f"status must be one of {TASK_STATUSES}, got {status!r}")
        return status

    @staticmethod
    def _validate_due_at(due_at: Any) -> str | None:
        """Validate an ISO-8601 timestamp, returning it unchanged (or ``None``).

        The value is *not* normalised: the contract requires the caller's exact
        string to survive a round-trip, so this is a pure parse check.
        """
        if due_at is None:
            return None
        if not isinstance(due_at, str):
            raise ValueError(f"due_at must be an ISO-8601 string, got {due_at!r}")
        try:
            datetime.fromisoformat(due_at)
        except ValueError:
            raise ValueError(f"due_at is not a valid ISO-8601 timestamp: {due_at!r}") from None
        return due_at

    @staticmethod
    def _normalise_str_list(values: Iterable[str] | None, *, field: str) -> list[str]:
        """Materialise an optional iterable into a fresh list, rejecting non-strings.

        A fresh list (never the caller's object) prevents aliasing: mutating the
        list passed to ``add_task`` afterwards cannot reach into the store.
        """
        if values is None:
            return []
        result = list(values)
        for value in result:
            if not isinstance(value, str):
                raise ValueError(f"{field} entries must be strings, got {value!r}")
        return result

    def _validate_dependencies(self, depends_on: Iterable[str]) -> None:
        """Ensure every dependency id exists; raise ``ValueError`` otherwise."""
        for dep in depends_on:
            if dep not in self._tasks:
                raise ValueError(f"unknown dependency id: {dep!r}")

    def _validate_no_cycle(self, task_id: str, depends_on: Iterable[str]) -> None:
        """Raise ``ValueError`` if installing ``depends_on`` on ``task_id`` makes a cycle.

        Dependency edges point *toward* prerequisites (``a -> b`` means "a
        depends on b"), so a cycle exists iff ``task_id`` is reachable from one
        of its proposed dependencies by transitively following those edges. A
        plain DFS with a ``visited`` set is sufficient and safe against
        pre-existing diamond shapes.
        """
        if task_id in depends_on:
            raise ValueError(f"task {task_id!r} cannot depend on itself")

        visited: set[str] = set()
        stack = list(depends_on)
        while stack:
            node = stack.pop()
            if node == task_id:
                # We walked back to the origin: adding these edges closes a loop.
                raise ValueError(f"dependency cycle detected involving task {task_id!r}")
            if node in visited:
                continue
            visited.add(node)
            stack.extend(self._tasks.get(node, {}).get("depends_on", []))
