"""Immutable value objects and field validators for the ``taskman`` store.

Design note (see ``taskman/DESIGN.md`` for the full rationale).  A task is a
*frozen* dataclass: once constructed it can never be mutated.  A state change
therefore never edits a task in place -- it appends a journal event, and the
manager's visible ``dict`` of tasks is a *pure fold* over that journal
(``taskman._journal.project``).  Keeping the record immutable is what makes the
fold trivially correct and makes "reject a bad edit, leave state unchanged" a
property of the architecture rather than a careful rollback dance.

The public surface required by the contract is a plain ``dict``; :func:`to_public`
is the single place that projection happens, so every read path agrees on the
key set.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

#: The only statuses the contract recognises.
VALID_STATUSES: tuple[str, ...] = ("todo", "doing", "done")

#: Inclusive priority band.
MIN_PRIORITY: int = 1
MAX_PRIORITY: int = 5

#: The exact key set every public task dict carries, in a stable order.
PUBLIC_FIELDS: tuple[str, ...] = (
    "id",
    "title",
    "status",
    "priority",
    "tags",
    "depends_on",
    "due_at",
    "created_at",
)


def validate_priority(priority: Any) -> int:
    """Return ``priority`` iff it is an integer inside the 1..5 band.

    ``bool`` is deliberately rejected even though it is an ``int`` subclass: a
    caller passing ``True``/``False`` almost certainly meant a status or a flag,
    not a priority of 1/0, and silently accepting it would hide that bug.
    """
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError(
            f"priority must be an integer in {MIN_PRIORITY}..{MAX_PRIORITY}, got {priority!r}"
        )
    if not MIN_PRIORITY <= priority <= MAX_PRIORITY:
        raise ValueError(f"priority must be in {MIN_PRIORITY}..{MAX_PRIORITY}, got {priority!r}")
    return priority


def validate_status(status: Any) -> str:
    """Return ``status`` iff it is one of :data:`VALID_STATUSES`."""
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
    return status


def normalize_tags(tags: Iterable[str] | str | None) -> tuple[str, ...]:
    """Coerce ``tags`` to an immutable tuple, preserving order and duplicates.

    A bare string is treated as a single tag (``"infra"`` -> ``("infra",)``) so a
    caller who forgets the list does not get a surprising character split.  Order
    is preserved because tags are user-visible labels; duplicate labels are kept
    because the contract never asks the store to be a set.
    """
    if tags is None:
        return ()
    if isinstance(tags, str):
        return (tags,)
    return tuple(tags)


def normalize_depends(depends_on: Iterable[str] | str | None) -> tuple[str, ...]:
    """Coerce ``depends_on`` to an immutable, de-duplicated tuple.

    Dependency *edges* are set-like, so duplicates are collapsed while first-seen
    order is retained (the ordering keeps error messages and stored JSON stable).
    """
    if depends_on is None:
        return ()
    if isinstance(depends_on, str):
        depends_on = (depends_on,)
    ordered: list[str] = []
    seen: set[str] = set()
    for dep in depends_on:
        if dep not in seen:
            seen.add(dep)
            ordered.append(dep)
    return tuple(ordered)


def validate_due_at(due_at: Any) -> str | None:
    """Validate a due date and return the value to store.

    ``None`` clears the field.  A :class:`datetime.datetime` is stored as its ISO
    string.  A string must parse with :func:`datetime.datetime.fromisoformat`; the
    *original* string is stored (not the re-rendered datetime) so an exact
    round-trip is guaranteed for any format the parser accepts.
    """
    if due_at is None:
        return None
    if isinstance(due_at, datetime):
        return due_at.isoformat()
    if not isinstance(due_at, str):
        raise ValueError(f"due_at must be None, a datetime, or an ISO-8601 string, got {due_at!r}")
    try:
        datetime.fromisoformat(due_at)
    except ValueError as exc:
        raise ValueError(f"due_at is not a parseable ISO-8601 timestamp: {due_at!r}") from exc
    return due_at


def utc_now_iso() -> str:
    """The creation timestamp format (timezone-aware UTC, ISO-8601)."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Task:
    """An immutable task record.

    ``seq`` is a manager-local monotonic creation counter used only to break
    priority ties in the contract's "ties keep creation order" rule.  It is
    internal: :func:`to_public` never exposes it.
    """

    id: str
    title: Any = ""
    status: str = "todo"
    priority: int = 3
    tags: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    due_at: str | None = None
    created_at: str = ""
    seq: int = 0


def to_public(task: Task) -> dict[str, Any]:
    """Project a :class:`Task` onto the contract's plain-dict shape.

    Lists are returned (not the internal tuples) because the contract compares
    ``task["tags"] == []`` and ``task["depends_on"] == [first]``; a fresh list each
    call also stops a caller from mutating store state through the returned dict.
    """
    return {
        "id": task.id,
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "tags": list(task.tags),
        "depends_on": list(task.depends_on),
        "due_at": task.due_at,
        "created_at": task.created_at,
    }


def from_record(record: Mapping[str, Any]) -> Task:
    """Rebuild a :class:`Task` from a journal record (replay-safe, never validates).

    Replay trusts the record: it was validated at the time it was appended.  The
    only transformations are the same normalizations used on the write path, so a
    record read back from disk is identical to the one that produced it.
    """
    return Task(
        id=record["id"],
        title=record.get("title"),
        status=record.get("status", "todo"),
        priority=record.get("priority", 3),
        tags=normalize_tags(record.get("tags")),
        depends_on=normalize_depends(record.get("depends_on")),
        due_at=record.get("due_at"),
        created_at=record.get("created_at", ""),
        seq=record.get("seq", 0),
    )


def apply_patch(task: Task, data: Mapping[str, Any]) -> Task:
    """Apply a validated partial update to ``task``, returning a new record.

    Only the fields the contract allows may change; ``id``, ``created_at`` and
    ``seq`` are immutable identity/ordering data and are never patchable.
    """
    updates: dict[str, Any] = {}
    for key in ("title", "status", "priority", "due_at"):
        if key in data:
            updates[key] = data[key]
    if "tags" in data:
        updates["tags"] = normalize_tags(data["tags"])
    if "depends_on" in data:
        updates["depends_on"] = normalize_depends(data["depends_on"])
    return replace(task, **updates)
