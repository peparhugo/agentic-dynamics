"""The append-only journal and its pure projection.

This is the heart of the chosen design: **the journal is the source of truth**.
The manager owns one mutable field -- the event list -- and the visible
``{task_id: Task}`` state is *derived* by folding that list.  Every mutation:

1. builds the candidate event,
2. folds ``existing + candidate`` into a trial state,
3. validates the trial (schema, referential integrity, acyclicity),
4. only on success adopts the longer list *and* the trial state together.

Because step 4 is the only mutation, a failed validation cannot leave a partial
edit behind -- "state unchanged" is structural, not best-effort.  Because the
projection is a pure function of the events, replaying a persisted journal
reconstructs the exact same state (``TaskManager.load`` is literally the fold).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from ._model import Task, apply_patch, from_record

#: The three journal operations.  ``patch`` carries only the changed fields;
#: ``add`` carries a full record (including the internal ``seq``); ``delete``
#: carries no payload.
OP_ADD = "add"
OP_PATCH = "patch"
OP_DELETE = "delete"


@dataclass(frozen=True)
class Event:
    """One immutable entry in the append-only journal."""

    op: str
    task_id: str
    data: Mapping[str, Any]


def project(events: Iterable[Event]) -> dict[str, Task]:
    """Fold a journal into the task mapping it describes (pure).

    Unknown ops raise rather than being skipped: a journal that cannot be fully
    interpreted is corrupt, and silently ignoring an entry would manufacture
    state that no event actually produced.
    """
    tasks: dict[str, Task] = {}
    for event in events:
        if event.op == OP_ADD:
            tasks[event.task_id] = from_record(event.data)
        elif event.op == OP_PATCH:
            tasks[event.task_id] = apply_patch(tasks[event.task_id], event.data)
        elif event.op == OP_DELETE:
            tasks.pop(event.task_id, None)
        else:  # pragma: no cover - only reachable from a hand-corrupted journal
            raise ValueError(f"unknown journal op: {event.op!r}")
    return tasks


def event_to_dict(event: Event) -> dict[str, Any]:
    """Serialize an event to a JSON-ready dict."""
    return {"op": event.op, "task_id": event.task_id, "data": dict(event.data)}


def event_from_dict(payload: Mapping[str, Any]) -> Event:
    """Deserialize a :class:`Event` written by :func:`event_to_dict`."""
    return Event(op=payload["op"], task_id=payload["task_id"], data=dict(payload.get("data", {})))
