"""P8 ``sla_queue`` — queue depth + the SLA buffer surface (d3 §5 P8, rule 9).

What is measured is served as measured; what has no writer is rendered as an explicit unknown —
never as a timing, and never as zero:

* **queue depth** — the live queue count (the emitted half);
* **completion trace + burn** — from the control DB's ``step_attempts`` (started/ended are
  measured); durations are computed, never invented;
* **breach rate** — the pinned ``sla_behavior`` metric via the SHARED
  ``reporting.workflow_metrics.sla_behavior`` (the same implementation the website pipeline
  uses), over phases whose ledgers actually recorded the breach fields; ``None`` (not
  measurable) is reported with the missing fields, never as a clean record;
* **queue_wait_ms / service_time_ms / due_at / deadline_slack** — the step-8 writers land here:
  ``scripts/enqueue.py`` stamps ``enqueued_at`` (and an SLA horizon with ``--due-hours``), and
  the worker appends one settled row per job to the timing ledger. Live queue jobs show a
  measured ``queue_wait_so_far_ms`` (now − enqueued) and ``pending``/``not_yet`` states for the
  fields that only exist after service — never a fake zero; settled jobs appear under
  ``recent_completions`` with their real queue-wait/service/slack values. A payload without an
  enqueue stamp keeps the named unknown (an absence, not a number);
* **the 2× queue-depth rule** (rule 9's operator decision: "never batch jobs whose SLA is
  under 2x observed queue depth") is surfaced from the MEASURED depth only; the block-level
  horizon reports whether a per-job SLA horizon was stamped.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_dynamics.reporting.workflow_metrics import (
    BREACH_FIELDS,
    breach_view,
    sla_behavior,
)
from agentic_dynamics.runtime.queue_timings import finite_number

SCHEMA = "sla-queue/v1"

#: How many completed attempts the trace shows.
TRACE_LIMIT = 20

#: How many settled timing rows ``recent_completions`` serves (newest first).
COMPLETIONS_LIMIT = 50

#: Default burn/breach window in hours (also used by the room's query parameter).
DEFAULT_WINDOW_H = 72


def _unknown(reason: str, *, gap: str = "", cls: str = "") -> dict[str, Any]:
    """The canonical unknown block — a named absence, never a fabricated value."""
    out: dict[str, Any] = {"state": "unknown", "reason": reason}
    if gap:
        out["gap"] = gap
    if cls:
        out["class"] = cls
    return out


def _pending(reason: str, cls: str = "[M]") -> dict[str, Any]:
    """A field that has no value YET (a job still queued/running) — distinct from unknown."""
    return {"state": "pending", "reason": reason, "class": cls}


def _parse_ts(text: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp (``Z`` accepted); ``None`` when unparseable."""
    if not isinstance(text, str) or not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def load_breach_views(results_dir: Path) -> tuple[list[dict[str, Any]], int]:
    """Phase breach views from every workflow run ledger, returning ``(views, n_ledgers)``.

    A missing directory is an honest empty population; unreadable files are skipped.
    """
    if not results_dir.is_dir():
        return [], 0
    views: list[dict[str, Any]] = []
    n_ledgers = 0
    for path in sorted(results_dir.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("phases"), list):
            continue
        n_ledgers += 1
        for phase in payload["phases"]:
            if isinstance(phase, dict):
                views.append(breach_view(phase))
    return views, n_ledgers


def load_job_timings(path: Path) -> tuple[list[dict[str, Any]], int]:
    """Settled job-timing rows from the worker's append-only ledger (newest last in-file).

    Returns ``(rows, n_skipped)`` — unreadable lines are counted and skipped, never guessed.
    A missing file is an honest empty population (no job has settled yet).
    """
    rows: list[dict[str, Any]] = []
    skipped = 0
    if not path.is_file():
        return rows, skipped
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows, skipped
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            skipped += 1
            continue
        if not isinstance(payload, dict) or not str(payload.get("cell_id") or ""):
            skipped += 1
            continue
        rows.append(payload)
    return rows, skipped


def _live_job_row(job: dict[str, Any], now_ts: float) -> dict[str, Any]:
    """One queued/running job: live wait where measurable, pending/unknown where not."""
    row: dict[str, Any] = {
        "job_id": str(job.get("job_id") or job.get("id") or job.get("cell_id") or "")
    }
    enqueued = finite_number(job.get("enqueued_at"))
    if enqueued is not None:
        row["enqueued_at"] = enqueued
        row["queue_wait_so_far_ms"] = round(max(0.0, now_ts - enqueued) * 1000.0, 3)
        row["queue_wait_ms"] = _pending(
            "settles when the job completes — the worker writes it under recent_completions"
        )
    else:
        row["queue_wait_ms"] = _unknown(
            "no enqueue stamp on this payload (a pre-step-8 cell)", gap="G-30", cls="[M]"
        )
    row["service_time_ms"] = _pending("the job has not been served yet")
    due = finite_number(job.get("due_at"))
    if due is not None:
        row["due_at"] = due
        row["deadline_slack_so_far_ms"] = round((due - now_ts) * 1000.0, 3)
    else:
        row["due_at"] = _unknown(
            "no SLA horizon stamped (enqueue --due-hours)", gap="G-32", cls="[P]"
        )
        row["deadline_slack"] = _unknown(
            "no SLA horizon stamped (enqueue --due-hours)", gap="G-32", cls="[P]"
        )
    return row


def _completions_block(timings: list[dict[str, Any]]) -> dict[str, Any]:
    """The settled jobs' measured timings, newest first, with coverage counts."""
    rows: list[dict[str, Any]] = []
    for timing in timings:
        if not isinstance(timing, dict):
            continue
        cell_id = str(timing.get("cell_id") or "")
        if not cell_id:
            continue
        row: dict[str, Any] = {
            "cell_id": cell_id,
            "story": str(timing.get("story") or ""),
            "model": str(timing.get("model") or ""),
            "status": str(timing.get("status") or ""),
        }
        for key in (
            "enqueued_at",
            "started_at",
            "ended_at",
            "queue_wait_ms",
            "service_time_ms",
            "due_at",
            "deadline_slack_ms",
        ):
            value = finite_number(timing.get(key))
            if value is not None:
                row[key] = value
        rows.append(row)
    rows.sort(key=lambda r: r.get("ended_at") or 0.0, reverse=True)
    return {
        "rows": rows[:COMPLETIONS_LIMIT],
        "n_rows": len(rows),
        "n_with_queue_wait": sum(1 for r in rows if "queue_wait_ms" in r),
        "n_with_deadline": sum(1 for r in rows if "deadline_slack_ms" in r),
    }


def build_sla_queue(
    queue_jobs: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    breach_views: list[dict[str, Any]],
    *,
    timings: list[dict[str, Any]] | None = None,
    window_h: int = DEFAULT_WINDOW_H,
    now: str | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the SLA/queue payload. Pure given its inputs (``now`` is injected).

    ``queue_jobs`` are the live queue's job dicts; ``attempts`` are control-DB step attempts
    (``job_id``/``step_id``/``model``/``state``/``started_at``/``ended_at``); ``timings`` are
    the settled rows from the worker's timing ledger. A timestamp that cannot be parsed leaves
    that attempt out of the timed computations and shows up in the trace with
    ``duration_s: null`` — it is never coerced to a number.
    """
    depth = len(queue_jobs)
    by_state: Counter = Counter(str(j.get("state") or "unknown") for j in queue_jobs)

    # ── completion trace + burn (measured timestamps only) ──
    timed: list[dict[str, Any]] = []
    for row in attempts:
        started = _parse_ts(row.get("started_at"))
        ended = _parse_ts(row.get("ended_at"))
        duration_s = round((ended - started).total_seconds(), 3) if (started and ended) else None
        timed.append(
            {
                "job_id": str(row.get("job_id") or row.get("step_id") or ""),
                "model": str(row.get("model") or ""),
                "state": str(row.get("state") or ""),
                "started_at": row.get("started_at") or None,
                "ended_at": row.get("ended_at") or None,
                "duration_s": duration_s,
            }
        )
    def _trace_sort_key(row: dict[str, Any]) -> tuple[bool, float]:
        """Parsed completions first (newest→oldest); unparseable stamps last, never fabricated."""
        parsed = _parse_ts(row["ended_at"])
        return (parsed is not None, parsed.timestamp() if parsed else 0.0)

    trace = sorted(
        (t for t in timed if t["ended_at"]),
        key=_trace_sort_key,
        reverse=True,
    )[:TRACE_LIMIT]

    now_dt = _parse_ts(now) or datetime.now(timezone.utc)
    now_ts = now_dt.timestamp()
    cutoff = now_ts - window_h * 3600
    completions: list[datetime] = [
        ended
        for row in attempts
        if (ended := _parse_ts(row.get("ended_at"))) is not None and ended.timestamp() >= cutoff
    ]
    if completions:
        span_end = max(completions)
        span_start = min(completions)
        span_h = max((span_end - span_start).total_seconds() / 3600, 1e-6)
        burn: dict[str, Any] = {
            "completions": len(completions),
            "span_h": round(span_h, 4),
            "burn_per_h": round(len(completions) / span_h, 4),
        }
    else:
        burn = {
            "completions": 0,
            "span_h": None,
            "burn_per_h": None,
            "reason": f"no completed attempts in the last {window_h}h window",
        }

    # ── per-job rows: live wait measured; settle-time fields pending, never zero ──
    per_job = [_live_job_row(job, now_ts) for job in queue_jobs]
    stamped_jobs = sum(1 for job in queue_jobs if finite_number(job.get("due_at")) is not None)

    # ── SLA block: the 2× rule from measured depth; horizon stamped or unset; breach shared ──
    breach_values = sla_behavior(breach_views)
    breach_block: dict[str, Any] = (
        {"state": "measured", "class": "[C]", "value": breach_values}
        if breach_values is not None
        else {
            "state": "not_measurable",
            "class": "[C]",
            "missing_fields": list(BREACH_FIELDS),
            "reason": "no workflow phase ledger recorded the breach fields",
        }
    )
    horizon: dict[str, Any] = {
        "state": "stamped" if stamped_jobs else "unset",
        "class": "[P]",
        "stamped_jobs": stamped_jobs,
    }
    if not stamped_jobs:
        horizon["gap"] = "G-33"
        horizon["reason"] = (
            "no per-job SLA horizon is stamped — enqueue --due-hours sets one (G-33)"
        )

    return {
        "schema": SCHEMA,
        "generated_at": now,
        "source": dict(source or {}),
        "queue": {"depth": depth, "by_state": dict(by_state)},
        "burn": burn,
        "completion_trace": trace,
        "recent_completions": _completions_block(list(timings or [])),
        "sla": {
            "horizon": horizon,
            "breach_rate": breach_block,
            "twice_depth_rule": {
                "threshold_jobs": 2 * depth,
                "statement": (
                    "never batch work whose SLA horizon is under 2x observed queue depth "
                    "(keep an on-demand fallback)"
                ),
                "class": "[P]",
                "basis": f"2 x measured queue depth ({depth} jobs)",
            },
        },
        "per_job": per_job,
        "degraded": [],
    }
