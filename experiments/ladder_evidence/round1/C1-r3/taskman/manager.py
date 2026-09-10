"""Pure-Python, stdlib-only implementation of the ``taskman`` contract.

DESIGN EXPLORATION
==================

Before writing any code, here are three **materially different** internal
designs.  They differ in all four axes the brief names — data model, ordering,
persistence, cycle detection — not merely in code style.

Design A — "Mutable record table with local DFS" (the obvious one)
------------------------------------------------------------------
* **Data model:** ``self.tasks: dict[str, dict]`` — the live task dicts *are*
  the stored state; mutating one mutates the store.
* **Ordering:** no stored order at all; ``list_tasks`` does a stable
  ``sorted(tasks.values(), key=lambda t: -t["priority"])`` and relies on
  ``dict`` insertion order for the tie-break.
* **Persistence:** ``json.dump(self.tasks)`` — a snapshot of the materialised
  state; ``load`` reads it straight back.
* **Cycle detection:** local depth-first search: when a task's ``depends_on``
  changes, walk forward from the changed node and look for a path back to it.

Design B — "Typed records plus an explicit reverse-dependency index"
--------------------------------------------------------------------
* **Data model:** an immutable ``Task`` record per id, held in a dict, plus a
  second dict ``dependents: dict[str, set[str]]`` (reverse edges) maintained
  alongside the forward ``depends_on`` list.
* **Ordering:** a monotonic integer ``order`` stamped on each record at
  creation and stored on the record itself.
* **Persistence:** serialise the record table; rebuild the reverse index by
  scanning on load.
* **Cycle detection:** reverse-reachability: adding ``t -> d`` cycles the graph
  iff ``t`` is already reachable from ``d`` through ``dependents``.

Design C (CHOSEN) — "Event-sourced log with a speculative pure fold"
--------------------------------------------------------------------
* **Data model:** the *only* authoritative state is ``self._events``, an
  append-only list of small JSON-native operation events (``add`` / ``update``
  / ``delete``).  The materialised view (task records, creation order, reverse
  index) is a pure function of that log and is rebuilt by folding it.  A task
  is never mutated in place; history is data.
* **Ordering:** creation order is the position of a task's ``add`` event in
  the log (rebuilt on every fold) — the log itself is the clock, so no
  separate counter can drift from it.
* **Persistence:** ``save`` writes ``{"schema": "taskman/v1", "events": [...]}``
  — the *log*, not the view.  ``load`` replays it.  (The contract requires the
  file to parse as a JSON *object*, which is why the log is wrapped in a dict
  rather than serialised as a bare JSON array.)
* **Cycle detection:** whole-graph.  Every mutation is *speculatively folded* —
  the candidate event is appended to a throwaway copy of the log, the view is
  recomputed, and Kahn's topological sort is run over the entire graph.  If a
  cycle exists the speculative commit raises and the real log is never
  touched, so "state unchanged on failure" is structural rather than a
  hand-managed rollback.

Why choose C?  A is the default a hurried implementation reaches for: a dict
of dicts, an in-place ``json.dump``, and a local DFS.  C is the design furthest
from it — state is derived, persistence is a replay, ordering is implied by the
log, and cycle detection is a global invariant checked on a hypothetical
future instead of a local search on the present.  It is also the safest for the
contract's atomicity clause: because nothing is mutated until the speculative
fold proves the invariant, there is no failure path that can leave a partial
edit behind.

The rest of this module is that Design C implementation.
"""

from __future__ import annotations

import json
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = ["TaskManager"]

#: The closed set of legal statuses (the contract's state machine).
VALID_STATUSES: tuple[str, ...] = ("todo", "doing", "done")

#: Creation default and inclusive priority bounds, straight from the contract.
DEFAULT_PRIORITY = 3
MIN_PRIORITY = 1
MAX_PRIORITY = 5

#: The mutable fields an ``update`` event is allowed to carry.
UPDATABLE_FIELDS = frozenset({"title", "status", "priority", "tags", "depends_on", "due_at"})

#: Persistence envelope tag.  Bump only on a breaking on-disk change.
_STATE_SCHEMA = "taskman/v1"


# ---------------------------------------------------------------------------
# Field validators — each returns the normalised value or raises ValueError.
# Keeping them pure and standalone makes the speculative fold easy to reason
# about: validation happens *before* any candidate event is constructed.
# ---------------------------------------------------------------------------


def _validate_priority(priority: Any) -> int:
    """Return ``priority`` if it is an int in ``1..5``; otherwise ``ValueError``.

    ``bool`` is deliberately rejected even though it subclasses ``int``: a
    boolean is not a priority level, and silently treating ``True`` as ``1``
    would hide a caller's type error.
    """
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError(
            f"priority must be an int in {MIN_PRIORITY}..{MAX_PRIORITY}, got {priority!r}"
        )
    if not MIN_PRIORITY <= priority <= MAX_PRIORITY:
        raise ValueError(f"priority must be in {MIN_PRIORITY}..{MAX_PRIORITY}, got {priority!r}")
    return priority


def _validate_status(status: Any) -> str:
    """Return ``status`` if it is one of ``todo``/``doing``/``done``; else ``ValueError``."""
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
    return status


def _validate_due_at(due_at: Any) -> str | None:
    """Validate an ISO-8601 due date.

    ``None`` is the contract default and passes through.  A string is kept
    *verbatim* (the contract round-trips the exact text), but it must parse as
    an ISO-8601 timestamp — an unparseable value is a ``ValueError``.
    """
    if due_at is None:
        return None
    if not isinstance(due_at, str):
        raise ValueError(f"due_at must be an ISO-8601 string or None, got {due_at!r}")
    try:
        datetime.fromisoformat(due_at)
    except ValueError as exc:  # re-raise with context; type is part of the contract
        raise ValueError(f"due_at is not a valid ISO-8601 timestamp: {due_at!r}") from exc
    return due_at


def _normalise_tags(tags: Any) -> list[str]:
    """Coerce an optional tag iterable into a fresh ``list`` (default empty)."""
    return list(tags) if tags else []


def _normalise_deps(depends_on: Any) -> list[str]:
    """Coerce an optional dependency iterable into a fresh ``list`` (default empty)."""
    return list(depends_on) if depends_on else []


def _copy_task(task: dict[str, Any]) -> dict[str, Any]:
    """Return a defensive copy of a task record.

    The lists are copied so a caller can never mutate stored state through the
    dict handed back by :meth:`TaskManager.get_task`.
    """
    copied = dict(task)
    copied["tags"] = list(task["tags"])
    copied["depends_on"] = list(task["depends_on"])
    return copied


# ---------------------------------------------------------------------------
# The materialised view — a pure fold of the event log.
# ---------------------------------------------------------------------------


class _State:
    """The derived, in-memory view of the event log.

    This is *never* the source of truth.  It is rebuilt from scratch by
    :meth:`TaskManager._fold`; the only reason it exists as an object is so the
    expensive part (indexing) can be cached between reads.
    """

    __slots__ = ("tasks", "order", "dependents")

    def __init__(self) -> None:
        #: id -> public task record (a dict, contract-facing).
        self.tasks: dict[str, dict[str, Any]] = {}
        #: task ids in creation order — the stable tie-break for listings.
        self.order: list[str] = []
        #: reverse edges: dependency id -> set of ids that depend on it.
        #: This is what makes ``delete`` refusal and Kahn's sort cheap.
        self.dependents: dict[str, set[str]] = {}


class TaskManager:
    """A dependency-aware task list backed by an append-only event log.

    See the module docstring for the three-design comparison and the argument
    for this one (Design C).  Every public method is a thin wrapper that turns
    user input into a validated operation event, speculatively folds it, and
    commits only if the resulting graph is acyclic.
    """

    def __init__(self) -> None:
        #: The authoritative history.  Append-only; never mutated in place.
        self._events: list[dict[str, Any]] = []
        #: The cached fold of ``self._events``.
        self._state: _State = _State()

    # -- construction / persistence -----------------------------------------

    @classmethod
    def load(cls, path: str) -> "TaskManager":
        """Reconstruct a manager by replaying the event log at ``path``.

        Persistence stores the *log*, so loading is simply a replay — there is
        no state-migration step and no chance of a snapshot disagreeing with
        the operations that produced it.
        """
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("taskman state file must contain a JSON object")
        if payload.get("schema") != _STATE_SCHEMA:
            raise ValueError(f"unsupported taskman schema: {payload.get('schema')!r}")
        events = payload.get("events")
        if not isinstance(events, list):
            raise ValueError("taskman state file is missing an 'events' list")

        manager = cls()
        manager._events = [dict(event) for event in events]
        manager._state = cls._fold(manager._events)
        # Fail closed: a hand-edited or corrupt log must not load a cyclic graph.
        if not cls._is_acyclic(manager._state):
            raise ValueError("taskman state file contains a dependency cycle")
        return manager

    def save(self, path: str) -> None:
        """Persist the event log as a JSON object (the contract's round trip)."""
        payload = {"schema": _STATE_SCHEMA, "events": self._events}
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # -- public API ----------------------------------------------------------

    def add_task(
        self,
        title: str,
        *,
        priority: int = DEFAULT_PRIORITY,
        tags: Iterable[str] | None = None,
        depends_on: Iterable[str] | None = None,
        due_at: str | None = None,
    ) -> str:
        """Create a task and return its generated unique id.

        Defaults match the contract: status ``todo``, priority ``3``, no tags,
        no dependencies, no due date.  Unknown dependency ids and out-of-range
        priorities are rejected before anything is recorded.
        """
        priority = _validate_priority(priority)
        due_at = _validate_due_at(due_at)
        tag_list = _normalise_tags(tags)
        dep_list = _normalise_deps(depends_on)

        # A dependency must already exist — you cannot point at the future.
        unknown = [dep for dep in dep_list if dep not in self._state.tasks]
        if unknown:
            raise ValueError(f"unknown dependency id(s): {unknown!r}")

        task_id = uuid.uuid4().hex
        self._commit(
            {
                "op": "add",
                "id": task_id,
                "title": title,
                "status": "todo",
                "priority": priority,
                "tags": tag_list,
                "depends_on": dep_list,
                "due_at": due_at,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return task_id

    def get_task(self, task_id: str) -> dict[str, Any]:
        """Return a copy of the task record, or raise ``KeyError`` if unknown."""
        task = self._state.tasks.get(task_id)
        if task is None:
            raise KeyError(task_id)
        return _copy_task(task)

    def update_task(self, task_id: str, **changes: Any) -> None:
        """Apply a partial update, atomically.

        All fields are validated first; the operation is then committed only if
        the speculative fold is still acyclic.  A rejected update leaves the
        log — and therefore the view — untouched.
        """
        if task_id not in self._state.tasks:
            raise KeyError(task_id)

        unknown_fields = set(changes) - UPDATABLE_FIELDS
        if unknown_fields:
            raise ValueError(f"unknown task field(s): {sorted(unknown_fields)!r}")

        fields: dict[str, Any] = {}
        if "title" in changes:
            fields["title"] = changes["title"]
        if "status" in changes:
            fields["status"] = _validate_status(changes["status"])
        if "priority" in changes:
            fields["priority"] = _validate_priority(changes["priority"])
        if "due_at" in changes:
            fields["due_at"] = _validate_due_at(changes["due_at"])
        if "tags" in changes:
            fields["tags"] = _normalise_tags(changes["tags"])
        if "depends_on" in changes:
            dep_list = _normalise_deps(changes["depends_on"])
            unknown = [dep for dep in dep_list if dep not in self._state.tasks]
            if unknown:
                raise ValueError(f"unknown dependency id(s): {unknown!r}")
            fields["depends_on"] = dep_list

        if not fields:  # an empty update is a legal no-op
            return
        self._commit({"op": "update", "id": task_id, "fields": fields})

    def set_status(self, task_id: str, status: str) -> None:
        """Move a task to ``todo``/``doing``/``done``; unknown id -> ``KeyError``."""
        if task_id not in self._state.tasks:
            raise KeyError(task_id)
        status = _validate_status(status)
        self._commit({"op": "update", "id": task_id, "fields": {"status": status}})

    def delete_task(self, task_id: str) -> None:
        """Delete a task, refusing while any other task still depends on it."""
        if task_id not in self._state.tasks:
            raise KeyError(task_id)
        dependents = self._state.dependents.get(task_id)
        if dependents:
            raise ValueError(
                f"cannot delete task {task_id!r}: still required by {sorted(dependents)!r}"
            )
        self._commit({"op": "delete", "id": task_id})

    def list_tasks(
        self,
        *,
        status: str | None = None,
        priority: int | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return tasks matching the optional filters, priority descending.

        Ties keep creation order.  That is not an accident of ``sorted`` here:
        the candidates are gathered by walking ``_state.order`` (creation
        order), and Python's stable sort then preserves it for equal
        priorities.
        """
        matches: list[dict[str, Any]] = []
        for task_id in self._state.order:
            task = self._state.tasks[task_id]
            if status is not None and task["status"] != status:
                continue
            if priority is not None and task["priority"] != priority:
                continue
            if tag is not None and tag not in task["tags"]:
                continue
            matches.append(_copy_task(task))
        matches.sort(key=lambda task: -task["priority"])
        return matches

    def ready_tasks(self) -> list[dict[str, Any]]:
        """Return not-done tasks whose dependencies are all done, priority first."""
        ready: list[dict[str, Any]] = []
        for task_id in self._state.order:
            task = self._state.tasks[task_id]
            if task["status"] == "done":
                continue
            # Every dependency must exist and be done.  A missing dependency
            # (which validation should make impossible) is treated as not-done,
            # so a corrupt graph can only ever under-report readiness.
            if all(
                self._state.tasks.get(dep, {}).get("status") == "done" for dep in task["depends_on"]
            ):
                ready.append(_copy_task(task))
        ready.sort(key=lambda task: -task["priority"])
        return ready

    # -- the event-sourced core ---------------------------------------------

    def _commit(self, event: dict[str, Any]) -> None:
        """Append ``event`` iff its speculative fold is acyclic.

        This is the single place the log grows.  Because the candidate view is
        computed on a throwaway copy, a rejected commit (e.g. a cycle) cannot
        leave partial state behind — the atomicity guarantee is structural.
        """
        candidate = self._fold([*self._events, event])
        if not self._is_acyclic(candidate):
            raise ValueError("dependency cycle detected")
        self._events.append(event)
        self._state = candidate

    @staticmethod
    def _fold(events: Sequence[dict[str, Any]]) -> _State:
        """Replay an event sequence into a fresh :class:`_State`.

        Pure and total: it trusts only well-formed events (they are validated
        before they ever reach the log) and is the one function that knows how
        each operation changes the view.
        """
        state = _State()
        for event in events:
            op = event["op"]
            if op == "add":
                task_id = event["id"]
                task = {
                    "id": task_id,
                    "title": event["title"],
                    "status": event["status"],
                    "priority": event["priority"],
                    "tags": list(event["tags"]),
                    "depends_on": list(event["depends_on"]),
                    "due_at": event["due_at"],
                    "created_at": event["created_at"],
                }
                state.tasks[task_id] = task
                state.order.append(task_id)
                state.dependents.setdefault(task_id, set())
                for dep in task["depends_on"]:
                    state.dependents.setdefault(dep, set()).add(task_id)
            elif op == "update":
                task_id = event["id"]
                task = state.tasks[task_id]
                fields = event["fields"]
                if "depends_on" in fields:
                    # Re-point the reverse index before overwriting the record.
                    old_deps = set(task["depends_on"])
                    new_deps = set(fields["depends_on"])
                    for dep in old_deps - new_deps:
                        state.dependents.get(dep, set()).discard(task_id)
                    for dep in new_deps - old_deps:
                        state.dependents.setdefault(dep, set()).add(task_id)
                task.update(fields)
            elif op == "delete":
                task_id = event["id"]
                task = state.tasks.pop(task_id)
                state.order.remove(task_id)
                for dep in task["depends_on"]:
                    state.dependents.get(dep, set()).discard(task_id)
                state.dependents.pop(task_id, None)
            else:  # pragma: no cover - the log is written only by _commit
                raise ValueError(f"unknown event operation: {op!r}")
        return state

    @staticmethod
    def _is_acyclic(state: _State) -> bool:
        """Return whether the whole dependency graph is a DAG, via Kahn's algorithm.

        Edges run *dependency -> dependent*.  We seed the queue with every node
        that has no unmet dependencies, peel them off, and ask whether every
        node was reached; a node left behind can only be on a cycle.
        """
        # in-degree = number of dependencies a task still has to wait on.
        indegree: dict[str, int] = {task_id: 0 for task_id in state.tasks}
        for task_id, task in state.tasks.items():
            for dep in task["depends_on"]:
                if dep in indegree:  # unknown deps are impossible, but stay safe
                    indegree[task_id] += 1

        queue: deque[str] = deque(tid for tid, degree in indegree.items() if degree == 0)
        visited = 0
        while queue:
            node = queue.popleft()
            visited += 1
            for dependent in state.dependents.get(node, ()):
                if dependent not in indegree:
                    continue
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    queue.append(dependent)
        return visited == len(state.tasks)
