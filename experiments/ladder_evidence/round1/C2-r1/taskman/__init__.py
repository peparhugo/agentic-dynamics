"""``taskman`` — a tiny, dependency-free task manager.

The package exposes a single public class, :class:`TaskManager`, implementing the
behavioural contract pinned by ``tests/flash_ladder/taskman_contract_test.py``:
create/read/update/delete tasks, tag and prioritise them, express dependencies
(including rejecting cycles), query readiness, and round-trip the whole store
through a JSON file.

Design summary (see ``DESIGN.md`` for the longer note):

* **Storage** — an ordered ``dict[str, Task]`` keyed by task id.  Python
  dictionaries preserve insertion order, so the *insertion order is the creation
  order*; that gives the "ties keep creation order" rule for free without a
  second bookkeeping structure, and it survives JSON round-trips because the
  serialised list is written in iteration order.
* **Atomicity** — every mutating operation validates *all* of its inputs (and,
  where relevant, the resulting dependency graph) before touching the store.
  A rejected operation therefore leaves the store byte-for-byte unchanged, which
  the cycle test asserts directly.
* **Encapsulation** — tasks are immutable :class:`~dataclasses.dataclass`
  instances internally, and :meth:`TaskManager.get_task` returns a fresh
  :func:`dataclasses.asdict` copy, so callers can never mutate the store by
  holding on to a returned dict.
* **Stdlib only** — ``uuid`` for collision-free ids, ``datetime`` for
  timestamps and due-date validation, ``json`` for persistence; nothing else.

Nothing here imports the host repository, so the module is safe to lift into a
fresh tree (which is exactly what the flash-ladder scorer does).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

__all__ = ["TaskManager"]

#: The only statuses the contract recognises.  Ordered for deterministic docs.
VALID_STATUSES: tuple[str, ...] = ("todo", "doing", "done")

#: Inclusive range a task priority may occupy.
MIN_PRIORITY: int = 1
MAX_PRIORITY: int = 5

#: Bumped only if the on-disk shape changes incompatibly; written into every
#: ``save`` payload so a future loader can migrate with confidence.
SCHEMA_VERSION: int = 1


def _utc_now_iso() -> str:
    """Return the current UTC instant as an ISO-8601 string.

    Timezone-aware (``+00:00``) so round-tripped timestamps are unambiguous;
    no microseconds are stripped because their presence is harmless to the
    contract and helps debugging.
    """

    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Task:
    """A single task record.

    Frozen so a reference obtained from the store can never be mutated in
    place; :meth:`TaskManager.update_task` builds a replacement with
    :func:`dataclasses.replace` and validation happens *before* the store is
    rebound to it.
    """

    id: str
    title: str
    status: str = "todo"
    priority: int = 3
    tags: list[str] | None = None
    depends_on: list[str] | None = None
    due_at: str | None = None
    created_at: str = ""

    def __post_init__(self) -> None:
        # Normalise the optional collections to real empty lists and give the
        # record a timestamp if the caller did not supply one (load() supplies
        # the persisted value, so this is only a safety net for direct use).
        if self.tags is None:
            object.__setattr__(self, "tags", [])
        if self.depends_on is None:
            object.__setattr__(self, "depends_on", [])
        if not self.created_at:
            object.__setattr__(self, "created_at", _utc_now_iso())


def _coerce_tags(tags: Iterable[str] | None) -> list[str]:
    """Return a defensive copy of ``tags`` as a list (``None`` -> ``[]``)."""

    return list(tags) if tags is not None else []


def _dedupe(items: Iterable[str]) -> list[str]:
    """Remove duplicates from ``items`` while preserving first-seen order."""

    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _validate_priority(priority: Any) -> int:
    """Validate and return a priority within the inclusive 1..5 range.

    ``bool`` is rejected explicitly: it is a subclass of ``int`` in Python, and
    ``True`` silently masquerading as priority 1 is a bug worth surfacing.
    """

    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError(
            f"priority must be an integer in {MIN_PRIORITY}..{MAX_PRIORITY}, got {priority!r}"
        )
    if not MIN_PRIORITY <= priority <= MAX_PRIORITY:
        raise ValueError(f"priority must be in {MIN_PRIORITY}..{MAX_PRIORITY}, got {priority!r}")
    return priority


def _validate_status(status: Any) -> str:
    """Validate and return one of :data:`VALID_STATUSES`."""

    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
    return status


def _validate_due_at(due_at: Any) -> str | None:
    """Validate an ISO-8601 due date, returning it unchanged on success.

    The original string is preserved (not re-serialised) so that
    ``save``/``load`` is an exact round-trip even if a caller chose an
    equivalent-but-differently-spelled ISO form.  A bare ``"Z"`` suffix is
    tolerated because :func:`datetime.fromisoformat` predates it on 3.10.
    """

    if due_at is None:
        return None
    if not isinstance(due_at, str):
        raise ValueError(f"due_at must be an ISO-8601 string or None, got {due_at!r}")
    try:
        datetime.fromisoformat(due_at.replace("Z", "+00:00"))
    except ValueError as exc:  # re-raise with our own message, keep it a ValueError
        raise ValueError(f"due_at is not a parseable ISO-8601 date: {due_at!r}") from exc
    return due_at


class TaskManager:
    """In-memory task store with dependency tracking.

    All public methods raise ``KeyError`` for unknown ids and ``ValueError`` for
    invalid values, exactly as the contract specifies.
    """

    def __init__(self) -> None:
        # Insertion order is the creation order, which is the tie-breaker for
        # priority-descending listings.
        self._tasks: dict[str, Task] = {}

    # ------------------------------------------------------------------ reads
    def get_task(self, task_id: str) -> dict[str, Any]:
        """Return a copy of the task's public fields.

        Unknown ids raise ``KeyError``.  A copy (via :func:`dataclasses.asdict`,
        which also deep-copies the list fields) is returned so a caller cannot
        corrupt the store by mutating the result.
        """

        return asdict(self._tasks[task_id])

    def list_tasks(
        self,
        *,
        status: str | None = None,
        priority: int | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return tasks matching the optional filters, priority-descending.

        Ties on priority retain creation order because :meth:`_ordered_tasks`
        sorts stably over a creation-ordered sequence.  ``tag`` matches if the
        tag appears anywhere in a task's tag list.
        """

        tasks = self._ordered_tasks()
        if status is not None:
            tasks = [task for task in tasks if task.status == status]
        if priority is not None:
            tasks = [task for task in tasks if task.priority == priority]
        if tag is not None:
            tasks = [task for task in tasks if tag in (task.tags or [])]
        return [asdict(task) for task in tasks]

    def ready_tasks(self) -> list[dict[str, Any]]:
        """Return not-done tasks whose dependencies are all ``done``.

        A task with no dependencies is ready as soon as it is not itself done.
        Ordering follows the same priority-descending, creation-order rule as
        :meth:`list_tasks` so the result is deterministic.
        """

        ready: list[Task] = []
        for task in self._ordered_tasks():
            if task.status == "done":
                continue
            if all(self._tasks[dep].status == "done" for dep in (task.depends_on or [])):
                ready.append(task)
        return [asdict(task) for task in ready]

    # ----------------------------------------------------------------- writes
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

        Validation runs in full before the task enters the store, so a rejected
        ``add_task`` is a no-op.  A new node cannot close a cycle (it has no
        incoming edges yet), so only the existence of each dependency is
        checked here.
        """

        validated_priority = _validate_priority(priority)
        validated_due = _validate_due_at(due_at)
        clean_tags = _coerce_tags(tags)
        task_id = uuid.uuid4().hex
        clean_deps = self._validate_dependencies(task_id, depends_on)

        task = Task(
            id=task_id,
            title=title,
            status="todo",
            priority=validated_priority,
            tags=clean_tags,
            depends_on=clean_deps,
            due_at=validated_due,
            created_at=_utc_now_iso(),
        )
        self._tasks[task_id] = task
        return task_id

    def update_task(self, task_id: str, **fields: Any) -> None:
        """Update any subset of a task's mutable fields.

        Unknown ids raise ``KeyError``; unknown field names or invalid values
        raise ``ValueError``.  Because a replacement :class:`Task` is only
        bound into the store after every check (including the cycle check)
        passes, a failed update leaves the store untouched.
        """

        if task_id not in self._tasks:
            raise KeyError(task_id)

        allowed = {"title", "priority", "tags", "depends_on", "due_at", "status"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"unknown task field(s): {sorted(unknown)}")

        current = self._tasks[task_id]
        updates: dict[str, Any] = {}

        if "title" in fields:
            title = fields["title"]
            if not isinstance(title, str):
                raise ValueError(f"title must be a string, got {title!r}")
            updates["title"] = title
        if "priority" in fields:
            updates["priority"] = _validate_priority(fields["priority"])
        if "due_at" in fields:
            updates["due_at"] = _validate_due_at(fields["due_at"])
        if "tags" in fields:
            updates["tags"] = _coerce_tags(fields["tags"])
        if "status" in fields:
            updates["status"] = _validate_status(fields["status"])
        if "depends_on" in fields:
            updates["depends_on"] = self._validate_dependencies(task_id, fields["depends_on"])

        candidate = replace(current, **updates)

        # Cycle check uses the *proposed* dependency list for this node while
        # every other node keeps its current edges.  Running it before the
        # rebind is what makes a cycle rejection state-preserving.
        if "depends_on" in fields and self._creates_cycle(task_id, candidate.depends_on or []):
            raise ValueError(f"update would create a dependency cycle at {task_id!r}")

        self._tasks[task_id] = candidate

    def set_status(self, task_id: str, status: str) -> None:
        """Set a task's status; ``KeyError`` for unknown ids, ``ValueError`` otherwise."""

        validated = _validate_status(status)
        if task_id not in self._tasks:
            raise KeyError(task_id)
        self._tasks[task_id] = replace(self._tasks[task_id], status=validated)

    def delete_task(self, task_id: str) -> None:
        """Delete a task, refusing while any other task still depends on it."""

        if task_id not in self._tasks:
            raise KeyError(task_id)
        dependents = [
            task.id for task in self._tasks.values() if task_id in (task.depends_on or [])
        ]
        if dependents:
            raise ValueError(f"cannot delete {task_id!r}: still required by {sorted(dependents)}")
        del self._tasks[task_id]

    # ------------------------------------------------------------ persistence
    def save(self, path: str | Path) -> None:
        """Write the whole store to ``path`` as a JSON object.

        The payload is ``{"version": <=SCHEMA_VERSION>, "tasks": [...]}`` with
        tasks listed in creation order; a top-level object keeps the file
        self-describing and extensible.
        """

        payload = {
            "version": SCHEMA_VERSION,
            "tasks": [asdict(task) for task in self._tasks.values()],
        }
        Path(path).write_text(json.dumps(payload, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "TaskManager":
        """Reconstruct a manager from a file written by :meth:`save`.

        Tasks are re-inserted in file order, which reproduces the original
        creation order (and therefore the original tie-breaking).  Only known
        fields are read, so a newer payload with extra keys still loads.
        """

        data = json.loads(Path(path).read_text())
        manager = cls()
        known_fields = {field for field in Task.__dataclass_fields__}
        for record in data.get("tasks", []):
            values = {key: value for key, value in record.items() if key in known_fields}
            task = Task(**values)
            manager._tasks[task.id] = task
        return manager

    # --------------------------------------------------------------- internals
    def _ordered_tasks(self) -> list[Task]:
        """All tasks, priority-descending; stable, so ties stay in creation order."""

        return sorted(self._tasks.values(), key=lambda task: -task.priority)

    def _validate_dependencies(self, task_id: str, depends_on: Iterable[str] | None) -> list[str]:
        """Validate dependency ids and return a de-duplicated list.

        Every referenced id must already exist and must not be ``task_id``
        itself (the latter also guards ``update_task`` against a direct
        self-loop).
        """

        if depends_on is None:
            return []
        clean: list[str] = []
        for dep in depends_on:
            if dep == task_id:
                raise ValueError(f"task {task_id!r} cannot depend on itself")
            if dep not in self._tasks:
                raise ValueError(f"unknown dependency id: {dep!r}")
            clean.append(dep)
        return _dedupe(clean)

    def _creates_cycle(self, task_id: str, deps: list[str]) -> bool:
        """Return ``True`` if giving ``task_id`` the edges ``deps`` closes a cycle.

        Builds the adjacency implied by the current store but with ``task_id``'s
        outgoing edges replaced by the proposal, then runs a colour-marking DFS
        (nodes on the active stack are "grey"; a grey node revisited is a
        back-edge, i.e. a cycle).
        """

        adjacency: dict[str, list[str]] = {
            tid: list(task.depends_on or []) for tid, task in self._tasks.items()
        }
        adjacency[task_id] = list(deps)

        visited: set[str] = set()
        on_stack: set[str] = set()

        def visit(node: str) -> bool:
            if node in on_stack:
                return True
            if node in visited:
                return False
            visited.add(node)
            on_stack.add(node)
            for neighbour in adjacency.get(node, []):
                if visit(neighbour):
                    return True
            on_stack.discard(node)
            return False

        return any(visit(node) for node in adjacency)
