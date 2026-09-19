"""``taskman`` — a tiny, dependency-free task manager.

This package is deliberately pure Python and stdlib-only: the behavioural contract in
``tests/flash_ladder/taskman_contract_test.py`` must be satisfiable with nothing more than
the interpreter. The public surface is the :class:`TaskManager` class.

Design goals and the reasoning behind them (the "verbose mode" for this artifact):

* **One obvious state store.** All tasks live in a single insertion-ordered ``dict`` keyed by
  id (``self._tasks``). Dict insertion order *is* creation order, which the contract requires
  as the tie-breaker when priorities are equal. We never rely on a set or a secondary index,
  because a second copy of the truth is a second way to disagree with it.
* **Fail before mutating.** Every operation that can fail validation (unknown id, bad
  priority, unparseable date, dangling dependency, dependency cycle) validates its inputs and
  computes the full new state *before* touching ``self._tasks``. The cycle test explicitly
  asserts state is unchanged after a rejected update, so "validate then commit" is a
  behavioural requirement, not merely a style choice.
* **Defensive reads.** :meth:`TaskManager.get_task` returns a deep copy. A caller can mutate
  the returned dict without corrupting the manager, and two managers can never alias the same
  list. Equality still holds for the round-trip test because copies compare equal.
* **Deterministic ordering.** ``list_tasks`` sorts on ``-priority`` only; Python's sort is
  stable, so equal-priority tasks retain creation order automatically. ``ready_tasks`` applies
  the same ordering so callers get a deterministic sequence rather than set-arbitrary output.
* **Round-trip fidelity.** ``save`` writes creation order and every field, including
  ``created_at``; ``load`` rebuilds a manager with the same insertion order so ids, ordering,
  and equality survive a JSON round trip and newly added tasks keep getting fresh ids.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

__all__ = ["TaskManager"]

#: The only statuses a task may hold. A closed set keeps ``set_status`` honest and makes an
#: accidental typo a loud ``ValueError`` rather than a silently unqueryable state.
VALID_STATUSES = ("todo", "doing", "done")

#: Inclusive bounds for the priority scale (1 = lowest urgency, 5 = highest).
MIN_PRIORITY = 1
MAX_PRIORITY = 5

#: Fields a caller may change through :meth:`TaskManager.update_task`. Restricting the set
#: turns a misspelled keyword into an immediate error instead of a no-op that looks like it
#: worked.
UPDATABLE_FIELDS = frozenset({"title", "status", "priority", "tags", "depends_on", "due_at"})

#: On-disk schema marker. Stored so a future format change has something to branch on; the
#: contract only requires that the file's top level be a JSON object.
SCHEMA_VERSION = 1


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string.

    We keep the timezone offset in the string so the value is unambiguous across machines and
    survives a JSON round trip byte-for-byte.
    """
    return datetime.now(tz=None).astimezone().isoformat()


def _validate_due_at(value: Any) -> Any:
    """Validate a ``due_at`` value, returning it unchanged when it parses.

    ``None`` is the "no due date" sentinel and is always allowed. Any other value must be a
    string that :func:`datetime.fromisoformat` can parse; the *original* text is returned (not
    a re-serialised datetime) so the caller's exact representation round-trips.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"due_at must be an ISO-8601 string or None, got {value!r}")
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:  # pragma: no cover - message forwarded for clarity
        raise ValueError(f"due_at is not a parseable ISO-8601 timestamp: {value!r}") from exc
    return value


def _validate_priority(value: Any) -> int:
    """Return ``value`` if it is an int within ``[MIN_PRIORITY, MAX_PRIORITY]``.

    ``bool`` is rejected explicitly even though it is an ``int`` subclass: ``True`` silently
    meaning priority ``1`` would be a bug waiting to happen.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"priority must be an integer, got {value!r}")
    if not MIN_PRIORITY <= value <= MAX_PRIORITY:
        raise ValueError(
            f"priority must be between {MIN_PRIORITY} and {MAX_PRIORITY}, got {value!r}"
        )
    return value


def _normalise_id_list(value: Any, field: str) -> list[str]:
    """Copy a dependency/tag style input into a fresh list of ids.

    ``None`` becomes the empty list. Strings are rejected rather than silently exploded into
    characters, which is the classic foot-gun when callers write ``depends_on="a"``.
    """
    if value is None:
        return []
    if isinstance(value, str):
        raise ValueError(f"{field} must be a list of ids, not a bare string")
    try:
        return [str(item) for item in value]
    except TypeError as exc:
        raise ValueError(f"{field} must be an iterable of ids, got {value!r}") from exc


class TaskManager:
    """In-memory task store with validation, dependency ordering, and JSON persistence.

    The manager is intentionally small. Its contract is exact ordering and exact validation, so
    the implementation keeps a single dict of plain-dict tasks and performs every check up front.
    """

    def __init__(self) -> None:
        """Create an empty manager.

        No mutable default is shared between instances: each manager gets its own dict, so two
        managers can never leak tasks into one another (a risk the tests probe by constructing
        several managers and comparing a saved/loaded pair).
        """
        self._tasks: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------ creation

    def add_task(
        self,
        title: str,
        *,
        priority: int = 3,
        tags: list[str] | None = None,
        depends_on: list[str] | None = None,
        due_at: str | None = None,
    ) -> str:
        """Create a task and return its freshly minted unique id.

        Defaults are status ``todo``, priority ``3``, empty tags/dependencies, and no due date.
        ``depends_on`` ids must already exist; a brand-new task cannot introduce a cycle, so
        only existence is checked here. All validation happens before the task is stored.
        """
        _validate_priority(priority)
        validated_due = _validate_due_at(due_at)
        tag_list = _normalise_id_list(tags, "tags")
        dep_list = _normalise_id_list(depends_on, "depends_on")
        self._require_known(dep_list)

        task_id = self._new_id()
        self._tasks[task_id] = {
            "id": task_id,
            "title": title,
            "status": "todo",
            "priority": priority,
            "tags": tag_list,
            "depends_on": dep_list,
            "due_at": validated_due,
            "created_at": _now_iso(),
        }
        return task_id

    # ------------------------------------------------------------------ reads

    def get_task(self, task_id: str) -> dict[str, Any]:
        """Return a deep copy of the task, or raise ``KeyError`` if it does not exist."""
        return copy.deepcopy(self._require_known_one(task_id))

    def list_tasks(
        self,
        *,
        status: str | None = None,
        priority: int | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return tasks matching every supplied filter, highest priority first.

        Filters compose (all supplied conditions must hold). Ties in priority keep creation
        order: we sort only on ``-priority`` and rely on the stability of Python's sort over the
        insertion-ordered source dict.
        """
        selected = [
            task
            for task in self._tasks.values()
            if (status is None or task["status"] == status)
            and (priority is None or task["priority"] == priority)
            and (tag is None or tag in task["tags"])
        ]
        selected.sort(key=lambda task: -task["priority"])
        return copy.deepcopy(selected)

    def ready_tasks(self) -> list[dict[str, Any]]:
        """Return not-done tasks whose dependencies are *all* done.

        A ``doing`` task still counts as not-done and therefore remains eligible: readiness
        answers "can this start / continue?", not "has it not started?". Output uses the same
        priority-then-creation ordering as :meth:`list_tasks` so callers see a stable sequence.
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
            # A dependency can never be missing in practice (add/update validate it and delete
            # refuses while dependents exist), but the guard keeps a corrupt load from raising.
        ]
        ready.sort(key=lambda task: -task["priority"])
        return copy.deepcopy(ready)

    # ------------------------------------------------------------------ mutation

    def update_task(self, task_id: str, **fields: Any) -> dict[str, Any]:
        """Update the named fields on a task and return the updated copy.

        Unknown ids raise ``KeyError``. Unknown keyword fields raise ``TypeError``. All field
        validation, including dependency existence and cycle detection, happens against a
        *candidate* copy before the live task is touched, so a rejected update leaves state
        exactly as it was.
        """
        task = self._require_known_one(task_id)
        unknown = set(fields) - UPDATABLE_FIELDS
        if unknown:
            raise TypeError(f"cannot update unknown field(s): {sorted(unknown)}")

        candidate = copy.deepcopy(task)

        if "title" in fields:
            candidate["title"] = fields["title"]
        if "status" in fields:
            candidate["status"] = self._validate_status(fields["status"])
        if "priority" in fields:
            candidate["priority"] = _validate_priority(fields["priority"])
        if "tags" in fields:
            candidate["tags"] = _normalise_id_list(fields["tags"], "tags")
        if "due_at" in fields:
            candidate["due_at"] = _validate_due_at(fields["due_at"])
        if "depends_on" in fields:
            deps = _normalise_id_list(fields["depends_on"], "depends_on")
            self._require_known(deps)
            self._assert_no_cycle(task_id, deps)
            candidate["depends_on"] = deps

        self._tasks[task_id] = candidate
        return copy.deepcopy(candidate)

    def set_status(self, task_id: str, status: str) -> None:
        """Set a task's status; invalid statuses raise ``ValueError``, unknown ids ``KeyError``."""
        self._require_known_one(task_id)
        self._tasks[task_id]["status"] = self._validate_status(status)

    def delete_task(self, task_id: str) -> None:
        """Delete a task, refusing while any other task lists it as a dependency.

        The refusal is status-independent: a completed dependent still represents a historical
        edge, and removing its prerequisite would leave a dangling reference.
        """
        self._require_known_one(task_id)
        dependents = [
            other["id"]
            for other in self._tasks.values()
            if other["id"] != task_id and task_id in other["depends_on"]
        ]
        if dependents:
            raise ValueError(
                f"cannot delete task {task_id!r}: still required by {sorted(dependents)}"
            )
        del self._tasks[task_id]

    # ------------------------------------------------------------------ persistence

    def save(self, path: str) -> None:
        """Write the manager to ``path`` as a JSON object.

        The task list preserves creation order and carries every field, so :meth:`load` can
        reconstruct an equal manager. The top level is an object (not a bare array) to leave
        room for the schema marker and future metadata.
        """
        payload = {
            "version": SCHEMA_VERSION,
            "tasks": copy.deepcopy(list(self._tasks.values())),
        }
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "TaskManager":
        """Reconstruct a manager previously written by :meth:`save`."""
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        # Tolerate a bare list in case an older/hand-written file skipped the envelope.
        records = payload["tasks"] if isinstance(payload, dict) else payload

        manager = cls()
        for record in records:
            task = copy.deepcopy(record)
            manager._tasks[task["id"]] = task
        return manager

    # ------------------------------------------------------------------ internals

    def _new_id(self) -> str:
        """Mint an id that is not already in use.

        ``uuid4`` makes collisions astronomically unlikely, but we still loop: a collision would
        silently overwrite a task, so the cheap re-draw is worth the certainty.
        """
        while True:
            candidate = uuid.uuid4().hex
            if candidate not in self._tasks:
                return candidate

    def _require_known_one(self, task_id: str) -> dict[str, Any]:
        """Return the live stored task or raise ``KeyError``."""
        try:
            return self._tasks[task_id]
        except KeyError:
            raise KeyError(f"unknown task id: {task_id!r}") from None

    def _require_known(self, ids: list[str]) -> None:
        """Raise ``ValueError`` for the first dependency id that does not exist."""
        for dependency in ids:
            if dependency not in self._tasks:
                raise ValueError(f"unknown dependency id: {dependency!r}")

    @staticmethod
    def _validate_status(status: Any) -> str:
        """Return ``status`` if it is one of :data:`VALID_STATUSES`, else raise ``ValueError``."""
        if status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
        return status

    def _assert_no_cycle(self, task_id: str, deps: list[str]) -> None:
        """Raise ``ValueError`` if ``task_id`` depending on ``deps`` would create a cycle.

        Cycle direction: ``task_id`` depends on each dep, and each dep may in turn depend on
        others. A cycle exists when any of those transitive dependencies points back at
        ``task_id``. We DFS from every dep, following ``depends_on`` edges, bounded by the known
        task set (which is acyclic before this change).
        """
        for start in deps:
            stack = [start]
            seen: set[str] = set()
            while stack:
                node = stack.pop()
                if node == task_id:
                    raise ValueError(f"dependency cycle: {task_id!r} -> {deps!r} closes a loop")
                if node in seen:
                    continue
                seen.add(node)
                stack.extend(
                    dep
                    for dep in self._tasks.get(node, {}).get("depends_on", [])
                    if dep not in seen
                )
