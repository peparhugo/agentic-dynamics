"""``taskman`` — a tiny, pure-Python, stdlib-only task manager.

Design rationale
----------------
The contract test (``tests/flash_ladder/taskman_contract_test.py``) pins a small,
self-contained behavioural surface.  We deliberately keep the whole implementation
in a single module so the package is trivially importable and auditable:

* **Storage.**  Tasks live in a single ``dict`` keyed by id.  Python's ``dict``
  preserves insertion order, which is exactly the "ties keep creation order"
  requirement for :meth:`TaskManager.list_tasks`, so we get stable ordering for
  free and only need a *stable* sort on priority.
* **Records.**  Each task is a plain ``dict`` (the contract indexes task fields
  like ``task["id"]``), normalised at every write so callers cannot smuggle in
  mutable aliases or partial field sets.
* **Validation is fail-closed and pre-mutational.**  Every public mutator first
  validates its entire input *and* simulates the resulting dependency graph for
  cycles before touching live state.  That is what lets
  ``test_cycle_detection_leaves_state_unchanged`` pass: a rejected update leaves
  both tasks byte-for-byte as they were.
* **Dependencies.**  ``depends_on`` is a directed edge ``task -> dependency``.
  "Ready" means not-done and every dependency is done.  A cycle is any cycle in
  that directed graph; we detect it with a colour-marked DFS (white/grey/black).

Only the standard library is used (``json``, ``uuid``, ``datetime``).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Set

__all__ = ["TaskManager"]

#: The only statuses the contract accepts.  A tuple (immutable) so callers cannot
#: mutate the canonical set; membership checks against it are O(#statuses).
VALID_STATUSES: tuple[str, ...] = ("todo", "doing", "done")

#: Inclusive bounds for ``priority``.  Kept as named constants so the error
#: messages and the validator can never drift apart.
MIN_PRIORITY = 1
MAX_PRIORITY = 5

#: Default priority when the caller does not specify one.
DEFAULT_PRIORITY = 3


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string.

    ``timespec="seconds"`` keeps the value compact and human-readable while still
    satisfying the contract's requirement that ``created_at`` is a non-empty
    string.  We use an explicit ``+00:00`` offset rather than ``Z`` because
    ``datetime.fromisoformat`` only understands ``Z`` from Python 3.11 onward and
    this package targets 3.10+.
    """
    return datetime.utcnow().replace(microsecond=0).isoformat() + "+00:00"


def _validate_priority(priority: Any) -> int:
    """Validate and normalise a priority value.

    The contract requires an ``int`` in the inclusive range 1..5.  ``bool`` is a
    subclass of ``int`` in Python, so ``True``/``False`` are explicitly rejected
    to avoid surprising ``priority=True`` -> ``1`` coercion.
    """
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError(f"priority must be an integer, got {priority!r}")
    if not (MIN_PRIORITY <= priority <= MAX_PRIORITY):
        raise ValueError(
            f"priority must be between {MIN_PRIORITY} and {MAX_PRIORITY}, got {priority!r}"
        )
    return priority


def _validate_due_at(due_at: Any) -> Optional[str]:
    """Validate an optional ISO-8601 ``due_at`` value and echo it back.

    ``None`` is allowed (no due date).  A string must be parseable by
    ``datetime.fromisoformat``; the *original string* is preserved verbatim so the
    round-trip test observes exactly the value it supplied.  Any non-string,
    non-``None`` value is rejected.
    """
    if due_at is None:
        return None
    if not isinstance(due_at, str):
        raise ValueError(f"due_at must be an ISO-8601 string or None, got {due_at!r}")
    try:
        datetime.fromisoformat(due_at)
    except ValueError as exc:  # re-raise as our own ValueError with context
        raise ValueError(f"due_at is not a valid ISO-8601 timestamp: {due_at!r}") from exc
    return due_at


def _normalise_tags(tags: Any) -> List[str]:
    """Copy a tag iterable into a fresh list, rejecting ``str``/non-iterables.

    Copying matters: the caller of ``add_task(..., tags=["a"])`` must not be able
    to mutate the stored task by holding onto the original list.  A bare string is
    explicitly rejected because iterating it would silently explode into
    per-character tags.
    """
    if tags is None:
        return []
    if isinstance(tags, str) or not isinstance(tags, Iterable):
        raise ValueError(f"tags must be an iterable of strings, got {tags!r}")
    result = list(tags)
    for tag in result:
        if not isinstance(tag, str):
            raise ValueError(f"each tag must be a string, got {tag!r}")
    return result


def _normalise_depends_on(depends_on: Any) -> List[str]:
    """Copy a dependency iterable into a fresh list of ids.

    As with tags, the list is copied and a bare string is rejected so a single id
    cannot be interpreted as a sequence of characters.
    """
    if depends_on is None:
        return []
    if isinstance(depends_on, str) or not isinstance(depends_on, Iterable):
        raise ValueError(f"depends_on must be an iterable of task ids, got {depends_on!r}")
    result = list(depends_on)
    for dep in result:
        if not isinstance(dep, str):
            raise ValueError(f"each depends_on entry must be a string id, got {dep!r}")
    return result


class TaskManager:
    """An in-memory collection of tasks with dependency tracking.

    The manager owns a ``dict`` of task-id -> task-record.  All access goes
    through the public methods; the internal ``_tasks`` mapping is an
    implementation detail (copies are returned from reads so callers cannot
    mutate state behind the manager's back).
    """

    def __init__(self) -> None:
        """Create an empty task manager."""
        # id -> normalised task record (a plain dict, as the contract expects).
        self._tasks: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _require(self, task_id: str) -> Dict[str, Any]:
        """Return the live record for ``task_id`` or raise ``KeyError``.

        The contract draws a firm line between "unknown id" (``KeyError``) and
        "known id, bad value" (``ValueError``); centralising the lookup keeps
        that distinction consistent across every method.
        """
        if task_id not in self._tasks:
            raise KeyError(task_id)
        return self._tasks[task_id]

    def _copy(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Return a shallow copy with list-valued fields defensively copied.

        Reads hand the caller a snapshot.  Mutating ``tags``/``depends_on`` on the
        returned dict therefore cannot corrupt manager state, while scalar fields
        (title, priority, status, timestamps) are safe to share as values.
        """
        snapshot = dict(record)
        snapshot["tags"] = list(record["tags"])
        snapshot["depends_on"] = list(record["depends_on"])
        return snapshot

    @staticmethod
    def _detect_cycle(graph: Dict[str, List[str]]) -> bool:
        """Return ``True`` if the directed ``graph`` contains any cycle.

        A classic three-colour DFS.  ``white`` = not yet visited, ``grey`` = on
        the current recursion stack, ``black`` = fully explored.  Encountering a
        grey node means we have looped back onto the active path, i.e. a cycle.
        Iterative-free recursion is fine here: task graphs are tiny and the
        recursion depth is bounded by the number of tasks.
        """
        white, grey, black = 0, 1, 2
        colour: Dict[str, int] = {node: white for node in graph}

        def visit(node: str) -> bool:
            colour[node] = grey
            for neighbour in graph.get(node, []):
                # A dependency id that is not a node in the graph is external to
                # this check (it will be validated separately); skip it so a
                # missing node cannot masquerade as a cycle.
                if neighbour not in colour:
                    continue
                if colour[neighbour] == grey:
                    return True  # back-edge -> cycle
                if colour[neighbour] == white and visit(neighbour):
                    return True
            colour[node] = black
            return False

        return any(colour[node] == white and visit(node) for node in list(colour))

    def _would_cycle(self, task_id: str, new_deps: List[str]) -> bool:
        """Check whether making ``task_id`` depend on ``new_deps`` creates a cycle.

        We build the prospective graph from a *copy* of the live edges, swap in
        the proposed dependency list for the edited task, then run the cycle
        detector.  Nothing touches ``self._tasks`` — this is the heart of the
        "state unchanged on rejected update" guarantee.
        """
        graph: Dict[str, List[str]] = {
            tid: list(record["depends_on"]) for tid, record in self._tasks.items()
        }
        graph[task_id] = list(new_deps)
        return self._detect_cycle(graph)

    def _validate_dependencies(self, depends_on: List[str]) -> None:
        """Ensure every dependency id refers to an existing task.

        Unknown ids are a ``ValueError`` (not ``KeyError``) per the contract.
        Self-dependencies are rejected here too — a task depending on itself is
        always a cycle, and catching it early yields a clearer error.
        """
        for dep in depends_on:
            if dep not in self._tasks:
                raise ValueError(f"unknown dependency id: {dep!r}")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def add_task(
        self,
        title: str,
        *,
        priority: int = DEFAULT_PRIORITY,
        tags: Optional[Iterable[str]] = None,
        depends_on: Optional[Iterable[str]] = None,
        due_at: Optional[str] = None,
    ) -> str:
        """Create a task and return its unique id.

        Defaults: ``status="todo"``, ``priority=3``, empty ``tags``/``depends_on``,
        ``due_at=None``.  All validation runs before the record is inserted, so a
        failed ``add_task`` never leaves a partial task behind.
        """
        # Normalise / validate every field up front (fail before mutating).
        if not isinstance(title, str) or not title:
            raise ValueError("title must be a non-empty string")
        priority = _validate_priority(priority)
        tags = _normalise_tags(tags)
        depends_on = _normalise_depends_on(depends_on)
        due_at = _validate_due_at(due_at)
        self._validate_dependencies(depends_on)

        # Generate a collision-resistant id.  ``uuid4`` is 122 bits of entropy;
        # we still loop defensively so uniqueness holds even under a (astronomically
        # unlikely) collision.
        task_id = uuid.uuid4().hex
        while task_id in self._tasks:
            task_id = uuid.uuid4().hex

        # Build the canonical record.  Dependency cycles are impossible for a
        # brand-new id (nothing can point at it yet), but we keep a self-dep guard
        # via the explicit self-reference check inside cycle detection below for
        # symmetry with update_task.
        record: Dict[str, Any] = {
            "id": task_id,
            "title": title,
            "status": "todo",
            "priority": priority,
            "tags": tags,
            "depends_on": depends_on,
            "due_at": due_at,
            "created_at": _utc_now_iso(),
        }
        # A new task cannot introduce a cycle unless it depends on itself (only
        # possible if its own id were already known, which it is not).  The check
        # is cheap and documents the invariant.
        if self._would_cycle(task_id, depends_on):
            raise ValueError("dependency cycle detected")
        self._tasks[task_id] = record
        return task_id

    def get_task(self, task_id: str) -> Dict[str, Any]:
        """Return a snapshot of the task with ``task_id``.

        Raises ``KeyError`` for an unknown id.
        """
        return self._copy(self._require(task_id))

    def update_task(self, task_id: str, **fields: Any) -> Dict[str, Any]:
        """Update mutable fields of an existing task.

        Recognised fields are ``title``, ``priority``, ``tags``, ``depends_on``
        and ``due_at`` (``status`` is changed via :meth:`set_status` and ``id`` /
        ``created_at`` are immutable).  Validation — including cycle detection for
        a tentative ``depends_on`` — happens entirely before mutation, so a
        rejected update leaves state untouched.  Unknown ids raise ``KeyError``.
        """
        record = self._require(task_id)  # KeyError for unknown id

        # Validate the fields we intend to change, collecting a staged patch.  We
        # do not write anything until the whole patch (and the cycle check) passes.
        patch: Dict[str, Any] = {}
        for key, value in fields.items():
            if key == "title":
                if not isinstance(value, str) or not value:
                    raise ValueError("title must be a non-empty string")
                patch["title"] = value
            elif key == "priority":
                patch["priority"] = _validate_priority(value)
            elif key == "tags":
                patch["tags"] = _normalise_tags(value)
            elif key == "depends_on":
                deps = _normalise_depends_on(value)
                self._validate_dependencies(deps)
                patch["depends_on"] = deps
            elif key == "due_at":
                patch["due_at"] = _validate_due_at(value)
            elif key in ("id", "created_at", "status"):
                # Explicitly reject in-place changes to derived/controlled fields:
                # silent acceptance would let callers desynchronise the record.
                raise ValueError(f"field {key!r} cannot be updated via update_task")
            else:
                raise ValueError(f"unknown field: {key!r}")

        # Cycle check against the *prospective* dependency list.
        if "depends_on" in patch and self._would_cycle(task_id, patch["depends_on"]):
            raise ValueError("dependency cycle detected")

        # All checks passed — commit the patch atomically.
        record.update(patch)
        return self._copy(record)

    def delete_task(self, task_id: str) -> None:
        """Delete a task, refusing while other tasks still depend on it.

        Unknown ids raise ``KeyError``.  A dependency held by any other task makes
        this a ``ValueError`` so callers must clear dependents first.
        """
        self._require(task_id)  # KeyError for unknown id
        dependents = [tid for tid, rec in self._tasks.items() if task_id in rec["depends_on"]]
        if dependents:
            raise ValueError(f"cannot delete {task_id!r}; depended on by {sorted(dependents)!r}")
        del self._tasks[task_id]

    def set_status(self, task_id: str, status: str) -> None:
        """Set a task's status to one of ``todo``/``doing``/``done``.

        Unknown ids raise ``KeyError``; an unrecognised status raises
        ``ValueError`` and leaves the current status unchanged.
        """
        record = self._require(task_id)  # KeyError for unknown id
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status {status!r}; expected one of {VALID_STATUSES!r}")
        record["status"] = status

    def list_tasks(
        self,
        *,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return tasks matching optional filters, priority-descending.

        Ordering: highest priority first, ties broken by creation order (which is
        the natural insertion order of the underlying dict).  ``list.sort`` is
        guaranteed stable, so sorting only on the negative priority preserves
        insertion order within equal priorities.  All filters are ANDed.
        """
        result = list(self._tasks.values())
        if status is not None:
            result = [rec for rec in result if rec["status"] == status]
        if priority is not None:
            result = [rec for rec in result if rec["priority"] == priority]
        if tag is not None:
            result = [rec for rec in result if tag in rec["tags"]]
        # Stable sort by priority descending; ties retain insertion order.
        result.sort(key=lambda rec: rec["priority"], reverse=True)
        return [self._copy(rec) for rec in result]

    def ready_tasks(self) -> List[Dict[str, Any]]:
        """Return all not-done tasks whose dependencies are all done.

        A task is ready when its status is not ``done`` and every id in its
        ``depends_on`` list points to a task currently in the ``done`` state.
        The result is returned in the same priority-descending order as
        :meth:`list_tasks` for a consistent caller experience.
        """
        done_ids: Set[str] = {tid for tid, rec in self._tasks.items() if rec["status"] == "done"}
        ready = [
            rec
            for rec in self._tasks.values()
            if rec["status"] != "done" and all(dep in done_ids for dep in rec["depends_on"])
        ]
        ready.sort(key=lambda rec: rec["priority"], reverse=True)
        return [self._copy(rec) for rec in ready]

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def save(self, path: str) -> None:
        """Serialise all tasks to a JSON file at ``path``.

        The on-disk shape is ``{"tasks": [...]}`` (a dict, as the contract
        asserts) so the format has room to grow (e.g. a schema version) without
        breaking older readers.  Tasks are written in creation order, and the
        containing object is created if necessary.
        """
        payload = {"tasks": [self._copy(rec) for rec in self._tasks.values()]}
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=False)

    @classmethod
    def load(cls, path: str) -> "TaskManager":
        """Load a manager previously written by :meth:`save`.

        The raw JSON is parsed and then re-validated/re-normalised through the
        same code paths used by the mutators, so a hand-edited or corrupt file
        fails loudly rather than injecting malformed state.  The original
        ``id``/``created_at`` values are preserved so round-trips are exact.
        """
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict) or not isinstance(payload.get("tasks"), list):
            raise ValueError("invalid task file: expected an object with a 'tasks' list")

        manager = cls()
        for raw in payload["tasks"]:
            if not isinstance(raw, dict):
                raise ValueError("invalid task file: each task must be an object")
            record = manager._normalise_loaded_record(raw)
            manager._tasks[record["id"]] = record

        # Post-load validation: a dependency may legitimately appear after its
        # dependent in creation order, so existence can only be checked once the
        # whole file is in memory.  We also reject a persisted cycle here; a
        # corrupt file must fail loudly rather than rebuild an illegal state.
        for record in manager._tasks.values():
            manager._validate_dependencies(record["depends_on"])
        graph = {tid: list(rec["depends_on"]) for tid, rec in manager._tasks.items()}
        if manager._detect_cycle(graph):
            raise ValueError("invalid task file: dependency cycle detected")
        return manager

    def _normalise_loaded_record(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Validate one deserialised task record and rebuild it canonically.

        Kept private because it is only meaningful while ``load`` is
        reconstructing state; it enforces every invariant the live manager does
        (valid id/status/priority, parseable ``due_at``, non-empty
        ``created_at``) and fills sensible defaults for any omitted optional
        field.  Dependency existence and acyclicity are checked by ``load`` after
        all records are in memory, since a dependency may appear later in
        creation order.
        """
        task_id = raw.get("id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("invalid task file: every task needs a non-empty string id")
        if task_id in self._tasks:
            raise ValueError(f"invalid task file: duplicate task id {task_id!r}")

        status = raw.get("status", "todo")
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status {status!r} in task {task_id!r}")

        created_at = raw.get("created_at")
        if not isinstance(created_at, str) or not created_at:
            raise ValueError(f"invalid created_at in task {task_id!r}")

        # Reuse the public normalisers so save/load cannot accept a shape that
        # add_task/update_task would reject.
        record: Dict[str, Any] = {
            "id": task_id,
            "title": raw.get("title", ""),
            "status": status,
            "priority": _validate_priority(raw.get("priority", DEFAULT_PRIORITY)),
            "tags": _normalise_tags(raw.get("tags")),
            "depends_on": _normalise_depends_on(raw.get("depends_on")),
            "due_at": _validate_due_at(raw.get("due_at")),
            "created_at": created_at,
        }

        # Dependencies must exist.  Because the file is written in creation order,
        # a dependency normally appears earlier; a forward reference is caught by
        # a second pass after all tasks are loaded (see load's post-check below).
        return record

    def __len__(self) -> int:
        """Number of tasks currently held (a small ergonomic convenience)."""
        return len(self._tasks)

    def __contains__(self, task_id: object) -> bool:
        """Support ``task_id in manager`` without exposing the internal dict."""
        return task_id in self._tasks

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        """Developer-friendly representation (not part of the contract)."""
        return f"TaskManager(tasks={len(self._tasks)})"
