"""The queue-timing writer (step 8, G-30/G-32) — one append-only row per settled job.

The worker observes both ends of a job's queue life — when it was enqueued (stamped into the
Redis payload by ``scripts/enqueue.py``) and when it started/ended being served — and until
this module existed it discarded the measurement: ``worker.py`` computed ``elapsed`` and only
logged it (the rule map's G-30 "elapsed computed then discarded"). The row is appended to
``experiments/results/queue_timings.jsonl`` (append-only; one JSON object per line, newest
last) so the Control Room's P8 projection can serve REAL queue-wait/service times instead of
the named unknowns it had to render.

Semantics, pinned:

* ``queue_wait_ms`` = (started - enqueued) × 1000 — measured across processes, so timestamps
  are epoch seconds (``time.time``); a negative delta (clock skew / re-queue) clamps to 0,
  never a negative wait;
* ``service_time_ms`` = (ended - started) × 1000 — always present on a settled row;
* ``due_at`` / ``deadline_slack_ms`` exist ONLY when the enqueue stamped an SLA horizon
  (``--due-hours``): without a policy the keys are ABSENT (an unknown, never 0). A settled
  job's slack is ``due_at - ended_at`` (negative = the deadline was breached — recorded, not
  hidden).

Appends are **best-effort for the worker** (a disk problem must not kill a finished job) but
loud: :func:`append_timing` returns a warning string instead of raising, and the caller logs it.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

#: The append-only timing ledger, repo-root relative (the same root the worker writes logs under).
QUEUE_TIMINGS_REL = Path("experiments/results/queue_timings.jsonl")


def finite_number(value: Any) -> float | None:
    """``float(value)`` for a real finite number, else ``None`` (bools and junk rejected)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):  # NaN / inf
        return None
    return number


def stamp_enqueue(cells: list[dict[str, Any]], *, due_hours: float | None = None, now: float | None = None) -> None:
    """Stamp transport timestamps onto freshly-built cells (in place; idempotent per cell).

    ``enqueued_at`` is stamped once per cell object; a cell that already carries one (e.g. an
    interleave's existing queue rows) keeps it — its wait is real elapsed time since it first
    entered the queue. ``due_at`` is stamped (from the same enqueue moment) only when the
    caller declares an SLA horizon.
    """
    current = time.time() if now is None else now
    for cell in cells:
        if "enqueued_at" not in cell:
            cell["enqueued_at"] = current
        if due_hours is not None and "due_at" not in cell:
            cell["due_at"] = cell["enqueued_at"] + float(due_hours) * 3600.0


def timing_row(
    cell: dict[str, Any],
    *,
    status: str,
    started_at: float,
    ended_at: float,
    enqueued_at: float | None = None,
) -> dict[str, Any]:
    """One settled job's timing row. Pure; epoch-second inputs.

    ``enqueued_at`` defaults to the cell's own stamp when it carries one; a payload without a
    stamp (pre-step-8 or hand-built cells) yields no ``queue_wait_ms`` — the field is absent,
    never a fabricated wait.
    """
    row: dict[str, Any] = {
        "cell_id": str(cell.get("cell_id") or ""),
        "story": str(cell.get("story") or ""),
        "model": str(cell.get("model") or ""),
        "status": str(status),
        "started_at": started_at,
        "ended_at": ended_at,
        "service_time_ms": round((ended_at - started_at) * 1000.0, 3),
    }
    enqueued = finite_number(enqueued_at) or finite_number(cell.get("enqueued_at"))
    if enqueued is not None:
        row["enqueued_at"] = enqueued
        row["queue_wait_ms"] = round(max(0.0, started_at - enqueued) * 1000.0, 3)
    due_at = finite_number(cell.get("due_at"))
    if due_at is not None:
        row["due_at"] = due_at
        row["deadline_slack_ms"] = round((due_at - ended_at) * 1000.0, 3)
    return row


def append_timing(row: dict[str, Any], *, path: Path = QUEUE_TIMINGS_REL) -> str | None:
    """Append one row to the timing ledger; ``None`` on success, a warning string on failure."""
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
        return None
    except OSError as exc:
        return f"could not append queue timing to {path}: {exc}"
