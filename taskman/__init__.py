"""``taskman`` — a tiny, pure-Python, stdlib-only task manager.

Design goals (and the reasoning behind each choice)
---------------------------------------------------
* **No third-party dependencies.** The only imports are ``json``, ``uuid`` and
  ``datetime`` from the standard library, so the package can be dropped into any
  Python 3.10+ environment without an install step. This keeps the behavioural
  contract in ``tests/flash_ladder/taskman_contract_test.py`` portable.
* **A dataclass-like record, but stored as a plain ``dict``.** The contract reads
  task fields with mapping syntax (``task["priority"]``), so the public surface
  must be dict-shaped. Internally we still keep a dedicated record shape by always
  constructing records through :meth:`TaskManager._new_record`; every mutator
  routes through the same validators, so the invariant "a stored record is valid"
  holds at all times.
* **Creation order is first-class state.** ``list_tasks`` must break priority ties
  by creation order, and JSON round-trips must preserve that order. We therefore
  keep an explicit ``_order`` list of ids alongside the ``_tasks`` mapping; we do
  not rely on dict insertion order alone, because a future ``load`` that rebuilds
  from a mapping would silently lose it.
* **Transactional mutation.** Every operation that could leave the store in an
  invalid state (notably adding or changing ``depends_on``) validates a *candidate*
  graph first and only commits once the candidate is proven acyclic and
  referentially complete. This is what lets ``update_task`` refuse a cycle while
  leaving both tasks untouched, exactly as the contract demands.
* **Defensive copying at the boundary.** Readers receive deep-ish copies, so a
  caller that mutates the returned ``tags``/``depends_on`` lists cannot corrupt
  the manager's internal state.

The public class is :class:`TaskManager`; all other names are private helpers.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Iterable, Mapping

# The closed set of legal workflow states. Anything else is a programming error
# on the caller's side, so we surface it as ``ValueError`` rather than coercing.
VALID_STATUSES = ("todo", "doing", "done")

# Inclusive priority band. The contract treats priority as a 1..5 severity where
# 5 is the most urgent, and ``list_tasks`` sorts descending on it.
_MIN_PRIORITY = 1
_MAX_PRIORITY = 5
_DEFAULT_PRIORITY = 3

# Schema marker written into every save file. Keeping it explicit means a future
# format change can be detected and migrated instead of being silently
# misinterpreted.
_SAVE_FORMAT_VERSION = 1


class TaskManager:
    """An in-memory task store with JSON persistence.

    All mutating operations validate their inputs and either fully succeed or
    raise without changing state. Unknown task ids consistently raise
    :class:`KeyError`; malformed values raise :class:`ValueError`.
    """

    def __init__(self, tasks: Iterable[Mapping[str, Any]] | None = None) -> None:
        """Create a manager, optionally seeding it from an ordered record list.

        Args:
            tasks: An iterable of already-validated task records, in creation
                order. Passing records here is how :meth:`load` rehydrates a
                manager; it is intentionally not part of the contract test's
                direct usage but keeps load/save symmetric.
        """
        # ``_tasks`` maps id -> record; ``_order`` records creation order so
        # priority ties keep the order in which tasks were added.
        self._tasks: dict[str, dict[str, Any]] = {}
        self._order: list[str] = []
        for record in tasks or ():
            self._insert_record(record)

    # ------------------------------------------------------------------ reads

    def get_task(self, task_id: str) -> dict[str, Any]:
        """Return a defensive copy of the task identified by ``task_id``.

        Raises:
            KeyError: if no task with that id exists.
        """
        return self._copy(self._require(task_id))

    def list_tasks(
        self,
        *,
        status: str | None = None,
        priority: int | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return tasks matching every supplied filter, newest-priority first.

        Filters are conjunctive (AND). Ordering is priority descending with ties
        broken by creation order — a stable sort over the creation-ordered list
        gives exactly that, because Python's sort is stable.
        """
        selected = [self._tasks[tid] for tid in self._order]
        if status is not None:
            selected = [t for t in selected if t["status"] == status]
        if priority is not None:
            selected = [t for t in selected if t["priority"] == priority]
        if tag is not None:
            selected = [t for t in selected if tag in t["tags"]]
        # ``reverse=True`` on priority only; stability preserves creation order
        # among equal priorities because the input list is already in that order.
        selected.sort(key=lambda t: t["priority"], reverse=True)
        return [self._copy(t) for t in selected]

    def ready_tasks(self) -> list[dict[str, Any]]:
        """Return not-done tasks whose dependencies are all done.

        A ``done`` task is never "ready". A task with no dependencies is ready as
        soon as it is not done. Results use the same priority-desc ordering as
        :meth:`list_tasks` so callers get a stable, meaningful queue.
        """
        ready_ids: list[str] = []
        for tid in self._order:
            task = self._tasks[tid]
            if task["status"] == "done":
                continue
            if all(self._tasks[dep]["status"] == "done" for dep in task["depends_on"]):
                ready_ids.append(tid)
        ready_ids.sort(key=lambda tid: self._tasks[tid]["priority"], reverse=True)
        return [self._copy(self._tasks[tid]) for tid in ready_ids]

    # ----------------------------------------------------------------- writes

    def add_task(
        self,
        title: str,
        *,
        priority: int = _DEFAULT_PRIORITY,
        tags: Iterable[str] | None = None,
        depends_on: Iterable[str] | None = None,
        due_at: str | None = None,
    ) -> str:
        """Create a task and return its freshly minted unique id.

        Validation happens before any state is written, so a rejected call is
        always a no-op. A new task id cannot introduce a cycle (it has no
        dependents yet), but we still run the referential check on
        ``depends_on`` and reject unknown ids.
        """
        self._validate_priority(priority)
        self._validate_due_at(due_at)
        dependency_ids = self._normalise_dependencies(depends_on)
        self._validate_dependencies_exist(dependency_ids)

        task_id = uuid.uuid4().hex  # 128 bits of entropy; collision-proof in practice.
        record = self._new_record(
            task_id=task_id,
            title=title,
            priority=priority,
            tags=tags,
            depends_on=dependency_ids,
            due_at=due_at,
        )
        self._insert_record(record)
        return task_id

    def update_task(self, task_id: str, **fields: Any) -> dict[str, Any]:
        """Patch the named fields of ``task_id`` and return the updated copy.

        Only whitelisted fields are honoured. Validation is performed against a
        *candidate* record and a candidate dependency graph; the store is
        committed only after the candidate passes, so a rejected update (e.g. one
        that would close a cycle) leaves every task exactly as it was.

        Raises:
            KeyError: unknown task id.
            ValueError: invalid priority, status, due date, or dependency set
                (including a cycle).
        """
        current = self._require(task_id)

        # Start from a copy and apply typed coercions/validations field by field.
        candidate = self._copy(current)

        if "title" in fields:
            candidate["title"] = fields["title"]
        if "priority" in fields:
            self._validate_priority(fields["priority"])
            candidate["priority"] = fields["priority"]
        if "tags" in fields:
            candidate["tags"] = self._normalise_tags(fields["tags"])
        if "due_at" in fields:
            self._validate_due_at(fields["due_at"])
            candidate["due_at"] = fields["due_at"]
        if "status" in fields:
            self._validate_status(fields["status"])
            candidate["status"] = fields["status"]
        if "depends_on" in fields:
            dependency_ids = self._normalise_dependencies(fields["depends_on"])
            self._validate_dependencies_exist(dependency_ids)
            if task_id in dependency_ids:
                # A self-loop is the smallest possible cycle; reject explicitly
                # so the error message is clearer than a generic cycle report.
                raise ValueError(f"task {task_id!r} cannot depend on itself")
            candidate["depends_on"] = dependency_ids

        self._assert_acyclic_with(task_id, candidate)

        # Commit only after all validation succeeded.
        self._tasks[task_id] = candidate
        return self._copy(candidate)

    def set_status(self, task_id: str, status: str) -> dict[str, Any]:
        """Transition a task to ``status`` (one of todo/doing/done)."""
        return self.update_task(task_id, status=status)

    def delete_task(self, task_id: str) -> None:
        """Delete a task, refusing while any other task still depends on it.

        Raises:
            KeyError: unknown task id.
            ValueError: at least one remaining task lists ``task_id`` as a
                dependency. Silently cascading would be surprising; the caller
                must resolve dependents first.
        """
        self._require(task_id)
        dependents = [tid for tid in self._order if task_id in self._tasks[tid]["depends_on"]]
        if dependents:
            raise ValueError(
                f"task {task_id!r} cannot be deleted while depended on by {dependents!r}"
            )
        del self._tasks[task_id]
        self._order.remove(task_id)

    # ------------------------------------------------------------- persistence

    def save(self, path: str) -> None:
        """Serialise the manager to a JSON file at ``path``.

        The on-disk shape is ``{"version": 1, "tasks": [record, ...]}`` — a list
        (not a mapping) so creation order survives the round trip. Records are
        already JSON-native (strings, ints, lists, ``None``).
        """
        payload = {
            "version": _SAVE_FORMAT_VERSION,
            "tasks": [self._copy(self._tasks[tid]) for tid in self._order],
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)

    @classmethod
    def load(cls, path: str) -> "TaskManager":
        """Read a manager back from a file produced by :meth:`save`.

        Raises:
            ValueError: if the file is not in the expected ``taskman`` format.
        """
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict) or "tasks" not in payload:
            raise ValueError(f"{path!r} is not a taskman save file")
        records = payload["tasks"]
        if not isinstance(records, list):
            raise ValueError(f"{path!r} has a malformed task list")
        return cls(tasks=records)

    # ----------------------------------------------------------- record helpers

    def _new_record(
        self,
        *,
        task_id: str,
        title: str,
        priority: int,
        tags: Iterable[str] | None,
        depends_on: list[str],
        due_at: str | None,
    ) -> dict[str, Any]:
        """Build a validated default record for a brand-new task."""
        return {
            "id": task_id,
            "title": title,
            "status": "todo",
            "priority": priority,
            "tags": self._normalise_tags(tags),
            "depends_on": list(depends_on),
            "due_at": due_at,
            "created_at": datetime.now().astimezone().isoformat(),
        }

    def _insert_record(self, record: Mapping[str, Any]) -> None:
        """Insert an already-validated record, preserving order and id uniqueness."""
        task_id = record["id"]
        if task_id in self._tasks:
            raise ValueError(f"duplicate task id {task_id!r}")
        self._tasks[task_id] = self._copy_record(record)
        self._order.append(task_id)

    def _require(self, task_id: str) -> dict[str, Any]:
        """Return the internal record for ``task_id`` or raise ``KeyError``."""
        try:
            return self._tasks[task_id]
        except KeyError:
            # Re-raise with a consistent, helpful message while keeping the
            # exception type the contract expects.
            raise KeyError(task_id) from None

    @staticmethod
    def _copy(record: Mapping[str, Any]) -> dict[str, Any]:
        """Return a shallow copy with the mutable list fields duplicated.

        This prevents callers from mutating ``tags``/``depends_on`` through a
        returned reference and thereby bypassing validation.
        """
        clone = dict(record)
        clone["tags"] = list(clone.get("tags", []))
        clone["depends_on"] = list(clone.get("depends_on", []))
        return clone

    @classmethod
    def _copy_record(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        """Copy a record while filling any absent optional field with its default."""
        clone = cls._copy(record)
        clone.setdefault("status", "todo")
        clone.setdefault("priority", _DEFAULT_PRIORITY)
        clone.setdefault("tags", [])
        clone.setdefault("depends_on", [])
        clone.setdefault("due_at", None)
        return clone

    # ------------------------------------------------------------ validation

    @staticmethod
    def _validate_priority(priority: Any) -> None:
        """Reject priorities outside the inclusive 1..5 band."""
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ValueError(f"priority must be an integer, got {priority!r}")
        if not _MIN_PRIORITY <= priority <= _MAX_PRIORITY:
            raise ValueError(
                f"priority must be between {_MIN_PRIORITY} and {_MAX_PRIORITY}, got {priority!r}"
            )

    @staticmethod
    def _validate_status(status: Any) -> None:
        """Reject any status outside the closed todo/doing/done set."""
        if status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES!r}, got {status!r}")

    @staticmethod
    def _validate_due_at(due_at: Any) -> None:
        """Require that ``due_at`` is ``None`` or an ISO-8601 parseable string.

        We validate by parsing but store the *original* string so that exact
        formatting (e.g. an explicit ``+00:00`` suffix) round-trips unchanged.
        """
        if due_at is None:
            return
        if not isinstance(due_at, str):
            raise ValueError(f"due_at must be an ISO-8601 string, got {due_at!r}")
        try:
            datetime.fromisoformat(due_at)
        except ValueError:
            raise ValueError(f"due_at is not a valid ISO-8601 timestamp: {due_at!r}") from None

    @staticmethod
    def _normalise_tags(tags: Iterable[str] | None) -> list[str]:
        """Coerce ``tags`` to a fresh list, defaulting ``None`` to empty."""
        if tags is None:
            return []
        return list(tags)

    @staticmethod
    def _normalise_dependencies(depends_on: Iterable[str] | None) -> list[str]:
        """Coerce ``depends_on`` to a fresh list, defaulting ``None`` to empty.

        Duplicates are removed while preserving first-seen order, so a caller
        passing ``[a, a]`` does not create a spurious two-edge cycle or a
        double-counted dependency.
        """
        if depends_on is None:
            return []
        seen: list[str] = []
        for dependency in depends_on:
            if dependency not in seen:
                seen.append(dependency)
        return seen

    def _validate_dependencies_exist(self, dependency_ids: Iterable[str]) -> None:
        """Raise ``ValueError`` if any dependency id is not a known task."""
        for dependency in dependency_ids:
            if dependency not in self._tasks:
                raise ValueError(f"unknown dependency id {dependency!r}")

    def _assert_acyclic_with(self, task_id: str, candidate: Mapping[str, Any]) -> None:
        """Verify that applying ``candidate`` for ``task_id`` introduces no cycle.

        We materialise the *candidate* dependency graph (current graph with one
        node replaced) and run Kahn's topological sort over it. If not every node
        can be peeled off, a cycle exists and the update is refused. Because this
        operates on a copy, the live store is never touched on failure.
        """
        graph: dict[str, list[str]] = {
            tid: list(self._tasks[tid]["depends_on"]) for tid in self._order
        }
        graph[task_id] = list(candidate["depends_on"])
        if _has_cycle(graph):
            raise ValueError(f"dependency update for {task_id!r} would introduce a cycle")


def _has_cycle(graph: Mapping[str, list[str]]) -> bool:
    """Return ``True`` if the dependency graph contains a directed cycle.

    Nodes are task ids; an edge ``task -> dependency`` means "task waits on
    dependency". A cycle therefore means no valid execution order exists.

    Kahn's algorithm: repeatedly remove nodes with in-degree zero (no remaining
    dependencies). If any nodes remain, a cycle is present. We rebuild the graph
    in "dependency -> dependents" orientation for the algorithm, which also lets
    us ignore ids that are not present as nodes (they cannot participate in a
    cycle inside this graph).
    """
    nodes = set(graph)
    dependents: dict[str, list[str]] = {node: [] for node in nodes}
    indegree: dict[str, int] = {}
    for node, dependencies in graph.items():
        counted = [dep for dep in dependencies if dep in nodes]
        indegree[node] = len(counted)
        for dependency in counted:
            dependents[dependency].append(node)

    queue = [node for node in nodes if indegree[node] == 0]
    processed = 0
    while queue:
        node = queue.pop()
        processed += 1
        for dependent in dependents[node]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                queue.append(dependent)
    return processed != len(nodes)


__all__ = ["TaskManager"]
