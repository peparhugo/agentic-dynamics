"""``TaskManager`` -- the public, event-sourced task store.

The contract (``tests/flash_ladder/taskman_contract_test.py``) is the whole
specification; this module is a thin, validating shell around the journal in
:mod:`taskman._journal` and the graph helpers in :mod:`taskman._graph`.  The
manager itself holds no mutable task state to get out of sync -- it holds the
event list and the fold of that list, and it updates them in lockstep.

Storage is stdlib-only JSON.  ``save`` writes the journal (not the projected
tasks) so a file is a durable, replayable history: ``load`` reconstructs the
store by folding it.  The JSON top level is an object (``{"schema", "events"}``)
as the contract asserts ``isinstance(json.loads(path.read_text()), dict)``.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping

from ._graph import find_cycle, order_tasks
from ._journal import OP_ADD, OP_DELETE, OP_PATCH, Event, event_from_dict, event_to_dict, project
from ._model import (
    Task,
    normalize_depends,
    normalize_tags,
    to_public,
    utc_now_iso,
    validate_due_at,
    validate_priority,
    validate_status,
)

#: Schema tag written into every saved file, so a future reader can branch on it.
SCHEMA_ID = "taskman/v1"

#: Fields a caller may change through :meth:`TaskManager.update_task`.
_UPDATABLE_FIELDS = frozenset({"title", "status", "priority", "tags", "depends_on", "due_at"})


class TaskManager:
    """An in-memory, event-sourced task manager with JSON persistence.

    All public methods are side-effect-free with respect to validation failures:
    a rejected call appends nothing, so the store is exactly as it was.
    """

    def __init__(self) -> None:
        #: The append-only journal -- the single source of truth.
        self._events: list[Event] = []
        #: The cached pure fold of ``_events``; always kept in sync with it.
        self._tasks: dict[str, Task] = {}
        #: Monotonic creation counter; feeds ``Task.seq`` for tie-breaking and is
        #: derived from the add events so it never regresses across a delete/load.
        self._next_seq: int = 0

    # ------------------------------------------------------------------ reads

    def get_task(self, task_id: str) -> dict[str, Any]:
        """Return the public dict for ``task_id``; raise ``KeyError`` if unknown."""
        return to_public(self._require(task_id))

    def list_tasks(
        self,
        *,
        status: str | None = None,
        priority: int | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return matching tasks ordered by priority descending, then creation.

        Filters are conjunctive: every supplied keyword must match.  ``tag``
        matches membership in the task's tag list.  Filtering uses the *raw*
        values (no validation) so asking for a status or priority that simply
        matches nothing yields an empty list rather than an error.
        """
        selected = [
            task
            for task in self._tasks.values()
            if (status is None or task.status == status)
            and (priority is None or task.priority == priority)
            and (tag is None or tag in task.tags)
        ]
        return [to_public(task) for task in order_tasks(selected)]

    def ready_tasks(self) -> list[dict[str, Any]]:
        """Return not-done tasks whose dependencies are *all* done.

        Dependencies are validated to exist on write, so a completed dependency
        set is a simple membership test.  Ordering matches :meth:`list_tasks`.
        """
        done = {task.id for task in self._tasks.values() if task.status == "done"}
        ready = [
            task
            for task in self._tasks.values()
            if task.status != "done" and all(dep in done for dep in task.depends_on)
        ]
        return [to_public(task) for task in order_tasks(ready)]

    # ----------------------------------------------------------------- writes

    def add_task(
        self,
        title: Any,
        *,
        priority: int = 3,
        tags: Iterable[str] | str | None = None,
        depends_on: Iterable[str] | str | None = None,
        due_at: Any = None,
    ) -> str:
        """Create a task and return its generated unique id.

        Validation order matters for error quality: field-level checks run first
        (priority, due date), then referential integrity (every dependency must
        already exist), then the graph check (the new task cannot close a cycle).
        Since the new id does not exist before this call, a dependency naming it
        is rejected by the existence check -- a self-loop is impossible here, but
        the cycle pass still runs so a single invariant holds for all writes.
        """
        priority = validate_priority(priority)
        tags_n = normalize_tags(tags)
        deps_n = normalize_depends(depends_on)
        due = validate_due_at(due_at)
        self._require_known_deps(deps_n)

        task_id = uuid.uuid4().hex
        record = {
            "id": task_id,
            "title": title,
            "status": "todo",
            "priority": priority,
            "tags": list(tags_n),
            "depends_on": list(deps_n),
            "due_at": due,
            "created_at": utc_now_iso(),
            "seq": self._next_seq,
        }
        trial = self._commit_candidate(Event(OP_ADD, task_id, record))
        if trial is not None:
            self._next_seq += 1
        return task_id

    def update_task(self, task_id: str, **fields: Any) -> None:
        """Apply a partial update to ``task_id``; unknown ids raise ``KeyError``.

        Unrecognised keyword names raise ``ValueError`` rather than being silently
        dropped -- a typo that quietly did nothing would be worse than an error.
        An empty update is a no-op.  Any validation failure (bad priority/date,
        unknown dependency, or a cycle) leaves the journal untouched.
        """
        self._require(task_id)
        unknown = set(fields) - _UPDATABLE_FIELDS
        if unknown:
            raise ValueError(f"unknown task field(s): {sorted(unknown)}")

        patch: dict[str, Any] = {}
        if "title" in fields:
            patch["title"] = fields["title"]
        if "priority" in fields:
            patch["priority"] = validate_priority(fields["priority"])
        if "tags" in fields:
            patch["tags"] = list(normalize_tags(fields["tags"]))
        if "due_at" in fields:
            patch["due_at"] = validate_due_at(fields["due_at"])
        if "status" in fields:
            patch["status"] = validate_status(fields["status"])
        if "depends_on" in fields:
            deps = normalize_depends(fields["depends_on"])
            self._require_known_deps(deps)
            patch["depends_on"] = list(deps)
        if not patch:
            return  # nothing to do; do not append a meaningless event
        self._commit_candidate(Event(OP_PATCH, task_id, patch))

    def set_status(self, task_id: str, status: str) -> None:
        """Set ``task_id``'s status; invalid statuses raise ``ValueError``.

        Existence is checked before the vocabulary, matching the contract's
        ``KeyError`` for an unknown id even when the status is also bad.
        """
        current = self._require(task_id)
        status = validate_status(status)
        if current.status == status:
            return  # idempotent; no event needed
        self._commit_candidate(Event(OP_PATCH, task_id, {"status": status}))

    def delete_task(self, task_id: str) -> None:
        """Delete ``task_id``; refuses while other tasks depend on it."""
        self._require(task_id)
        dependents = [task.id for task in self._tasks.values() if task_id in task.depends_on]
        if dependents:
            raise ValueError(f"cannot delete {task_id!r}: still required by {sorted(dependents)}")
        self._commit_candidate(Event(OP_DELETE, task_id, {}))

    # -------------------------------------------------------------- persistence

    def save(self, path: str | Path) -> None:
        """Write the journal to ``path`` as a JSON object.

        Persisting events (rather than the projected dict) means the file is the
        durable history: loading it is replay, not a lossy deserialize.
        """
        payload = {
            "schema": SCHEMA_ID,
            "events": [event_to_dict(event) for event in self._events],
        }
        Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True))

    @classmethod
    def load(cls, path: str | Path) -> "TaskManager":
        """Reconstruct a manager by replaying the journal at ``path``.

        Accepts either the schema object this class writes or a bare event list,
        so a hand-authored file is usable too.  Values are not re-validated: they
        passed validation when they were first appended.
        """
        raw = json.loads(Path(path).read_text())
        event_payloads = raw["events"] if isinstance(raw, Mapping) else raw
        manager = cls()
        manager._events = [event_from_dict(payload) for payload in event_payloads]
        manager._tasks = project(manager._events)
        # Continue the sequence past every add ever recorded -- including tasks
        # since deleted -- so creation-order tie-breaking stays globally unique.
        manager._next_seq = (
            max(
                (event.data["seq"] for event in manager._events if event.op == OP_ADD),
                default=-1,
            )
            + 1
        )
        return manager

    # ---------------------------------------------------------------- internals

    def _require(self, task_id: str) -> Task:
        """Return the internal task or raise ``KeyError`` (never ``IndexError``)."""
        try:
            return self._tasks[task_id]
        except KeyError:
            raise KeyError(task_id) from None

    def _require_known_deps(self, deps: Iterable[str]) -> None:
        """Raise ``ValueError`` listing any dependency id this store does not hold."""
        missing = [dep for dep in deps if dep not in self._tasks]
        if missing:
            raise ValueError(f"unknown dependency id(s): {missing}")

    def _commit_candidate(self, event: Event) -> dict[str, Task] | None:
        """Validate ``event`` against a trial fold, then adopt it if valid.

        Returns the new projection, or ``None`` for a no-op.  The manager's real
        state is only reassigned after the trial passes every check, which is what
        makes a rejected edit leave no trace.
        """
        trial = project([*self._events, event])
        cycle = find_cycle({task.id: task.depends_on for task in trial.values()})
        if cycle is not None:
            raise ValueError(f"dependency cycle detected: {' -> '.join(cycle)}")
        self._events.append(event)
        self._tasks = trial
        return trial
