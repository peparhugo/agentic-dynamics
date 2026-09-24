"""The operational read models (step 5, Phase 0): the room reads the ONE packet.

Why this module exists — the Phase-0 truth rule made structural: on main, the Control Room
never consumed ``control.control_status`` at all. Every surface re-derived its own version of
"what is true right now" (routes reading Redis, flags, session files), which is precisely how
three readers produce three answers. This module is the room's ONE gate onto live state: it
builds the packet and derives presentation-ready blocks from it, so:

* every live identifier the room shows (``run_id`` / ``gate_id`` / ``candidate_sha``) comes
  from the packet — the same values the AIO acts on, never a re-derivation;
* availability is carried, not flattened: a block that could not be read stays named in
  ``degraded``, an absent value stays ``null``, and nothing is rendered as a fabricated zero
  or an all-clear;
* rows pass through with their packet fields intact (plus a ``kind`` discriminator), so this
  layer can never invent a field the authority did not return.

``operational_snapshot`` is intentionally read-only and pure given its inputs: it opens no
sockets, reads no clock (``now`` is injected through to ``build_packet``), and never writes.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from agentic_dynamics.control.control_db import TERMINAL_RUN_STATES, RunState
from agentic_dynamics.control.control_status import active_run_ref, build_packet, run_ref
from agentic_dynamics.control.live import EVENT_LOG_MAX, EVENT_LOG_PREFIX
from apps.control_room.services import run_evidence

#: The read model's schema id (additive; the source packet's schema rides in ``source``).
SCHEMA = "control-room-operations/v1"

#: The per-run detail's schema id (step 5, P1/P2).
RUN_DETAIL_SCHEMA = "control-room-run-detail/v1"

#: The fleet job board (the supervisor's Redis key; each job record carries its ``run_id``).
FLEET_JOBS_KEY = "fleet:jobs"

#: How many retained events the run detail's logs block carries (a bounded tail).
LOGS_EVENT_LIMIT = 50

# ``RunState`` is the authority for this roster.  Keeping the order derived from the enum makes
# adding a lifecycle state a visible contract change instead of silently dropping it from the room.
RUN_STATE_ORDER = tuple(state.value for state in RunState)


def _event_display_value(value: Any) -> str:
    """Serialize rich event values without losing structured tool evidence in the read model."""
    if value is None or value == "":
        return ""
    if isinstance(value, (Mapping, list, tuple)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _child_activity(
    raw_events: list[str],
    *,
    state: str,
    cell_ids: list[str],
    resolution_basis: str,
    total: int,
    slice_limit: int = LOGS_EVENT_LIMIT,
    reason: str = "",
) -> dict[str, Any]:
    """Describe child-session evidence in exactly the selected bounded event slice.

    A child is recorded only when the producer explicitly carries ``child_session_id`` on the
    event or its part.  In particular, an empty result means ``absent`` in this slice; it does
    not mean that the run had no children outside the retained evidence.  Keeping this helper
    server-owned lets the run-detail and SSE read models use identical evidence and vocabulary.
    """
    child_session_ids: list[str] = []
    for payload in raw_events[: max(slice_limit, 0)]:
        try:
            event = json.loads(payload)
        except (TypeError, ValueError):
            continue
        if not isinstance(event, Mapping):
            continue
        part = event.get("part") if isinstance(event.get("part"), Mapping) else {}
        child_session_id = event.get("child_session_id") or part.get("child_session_id")
        child_session_id = str(child_session_id or "").strip()
        if child_session_id and child_session_id not in child_session_ids:
            child_session_ids.append(child_session_id)

    if state in {"unavailable", "unbound"}:
        activity_state = "unavailable"
        activity_reason = reason or f"child activity unavailable because logs are {state}"
    elif child_session_ids:
        activity_state = "recorded"
        activity_reason = reason
    else:
        activity_state = "absent"
        activity_reason = reason or "no child events recorded in the bounded retained slice"

    return {
        "state": activity_state,
        "cell_ids": list(cell_ids),
        "resolution_basis": resolution_basis or state,
        "slice_bound": max(slice_limit, 0),
        "observed_events": min(len(raw_events), max(slice_limit, 0)),
        "total_events": int(total or 0),
        "child_session_ids": child_session_ids,
        "reason": activity_reason,
    }


def logs_block(
    *,
    cell_id: str,
    cell_ids: list[str] | None = None,
    state: str,
    reason: str = "",
    raw_events: list[str] | None = None,
    total: int = 0,
    match: str = "",
    job_id: str = "",
    live_cell_id: str = "",
    stream_match: str = "",
    resolution_basis: str = "",
    slice_limit: int = LOGS_EVENT_LIMIT,
) -> dict[str, Any]:
    """The run's event-log block: a NAMED state, a bounded parsed tail, no fabricated values.

    States: ``recorded`` (the selected stream's retained tail was read), ``unbound`` (no fleet
    job on the board references this run), ``unavailable`` (the event store could not be read —
    the reason names it). ``events`` is oldest-first for the reader; the producer stores
    newest-first (LPUSH + LTRIM at ``EVENT_LOG_MAX``), and ``history_capped`` reports whether the
    run-scoped evidence itself reaches the producer's bounded window rather than implying the
    shared stream's full tail belongs to this run.
    """
    selected_raw_events = list(raw_events or [])[: max(slice_limit, 0)]
    events: list[dict[str, Any]] = []
    for payload in selected_raw_events:
        malformed = False
        try:
            event = json.loads(payload)
        except (TypeError, ValueError):
            event = {"type": "malformed", "text": str(payload)}
            malformed = True
        if not isinstance(event, Mapping):
            event = {"type": "malformed", "text": str(event)}
            malformed = True
        part = event.get("part") if isinstance(event.get("part"), Mapping) else {}
        tool_state = part.get("state") if isinstance(part.get("state"), Mapping) else {}
        text = part.get("text", event.get("text", ""))
        timestamp = (
            event.get("timestamp") or event.get("time") or part.get("timestamp") or part.get("time")
        )
        events.append(
            {
                # Keep both names: ``ts`` is the existing drawer contract, while ``timestamp``
                # makes the producer's recorded field explicit to the live and replay renderers.
                "ts": timestamp,
                "timestamp": timestamp,
                "class": "malformed" if malformed else str(event.get("type") or "event"),
                "text": str(text if text is not None else ""),
                "id": str(event.get("id") or ""),
                "part_id": str(part.get("id") or ""),
                "tool": str(part.get("tool") or event.get("tool") or ""),
                "tool_input": _event_display_value(
                    tool_state.get("input")
                    if tool_state.get("input") is not None
                    else event.get("tool_input") or event.get("input") or ""
                ),
                "tool_output": _event_display_value(
                    tool_state.get("output")
                    if tool_state.get("output") is not None
                    else event.get("tool_output") or event.get("output") or ""
                ),
                "child_session_id": str(
                    event.get("child_session_id") or part.get("child_session_id") or ""
                ),
                "malformed": malformed,
            }
        )
    named_resolution_basis = resolution_basis or match or state
    return {
        "state": state,
        "cell_id": cell_id,
        "cell_ids": list(cell_ids or []),
        "reason": reason,
        "events": events,
        "count": int(total or 0),
        "history_capped": int(total or 0) >= EVENT_LOG_MAX,
        "match": match,
        # The in-flight binding (2026-09-22): the run's FLEET JOB stream carries only the
        # orchestrator's milestones; the sibling phase cells publish the agent's own events
        # under ``events_log:<spec>:<phase>``. When a live phase stream is bound, ``cell_id``
        # is that stream (what the drawer reads and Follow-live subscribes to) and
        # ``job_id`` keeps the fleet identity named; ``stream_match`` names the basis.
        "job_id": job_id,
        "live_cell_id": live_cell_id,
        "stream_match": stream_match,
        "resolution_basis": named_resolution_basis,
        "slice_bound": max(slice_limit, 0),
        "child_activity": _child_activity(
            selected_raw_events,
            state=state,
            cell_ids=list(cell_ids or []),
            resolution_basis=named_resolution_basis,
            total=total,
            slice_limit=slice_limit,
            reason=reason,
        ),
    }


def _event_epoch(value: Any) -> float | None:
    """A tolerant event timestamp read in SECONDS (live events stamp milliseconds)."""
    ts = _epoch(value)
    if ts is None:
        return None
    return ts / 1000.0 if ts > 1e11 else ts


def _recorded_event_epoch(payload: Any) -> float | None:
    """Return an event's recorded timestamp, or ``None`` when it has no usable timestamp.

    The live publisher has emitted both top-level ``timestamp`` and legacy ``time`` fields, while
    some event producers place the stamp on the nested part.  Membership in a run window is only
    provable from one of these recorded values; an event without one is never assigned silently.
    """
    try:
        event = json.loads(payload)
    except (TypeError, ValueError):
        return None
    if not isinstance(event, Mapping):
        return None
    part = event.get("part") if isinstance(event.get("part"), Mapping) else {}
    for candidate in (
        event.get("timestamp"),
        event.get("time"),
        part.get("timestamp"),
        part.get("time"),
    ):
        timestamp = _event_epoch(candidate)
        if timestamp is not None:
            return timestamp
    return None


def _filter_run_events(
    raw_events: list[str], *, started_at: str, ended_at: str
) -> tuple[list[str], str]:
    """Keep only events provably inside the selected run's recorded time window.

    The Redis list is a shared, bounded phase tail for some live runs, so its length and position
    cannot establish run membership.  When the run has no recorded boundary (only possible for a
    direct caller outside the normal run-detail path), events are retained as ``unscoped`` and the
    reason says so.  Once either boundary is recorded, untimestamped events are excluded and the
    reason names that treatment.
    """
    start = _event_epoch(started_at)
    end = _event_epoch(ended_at)
    if start is None and end is None:
        return list(raw_events), "run window unavailable; retained events are unscoped"

    selected: list[str] = []
    untimestamped = 0
    for payload in raw_events:
        timestamp = _recorded_event_epoch(payload)
        if timestamp is None:
            untimestamped += 1
            continue
        if start is not None and timestamp < start:
            continue
        if end is not None and timestamp > end:
            continue
        selected.append(payload)

    if untimestamped:
        return selected, f"{untimestamped} untimestamped events excluded from run-scoped tail"
    return selected, ""


def _live_phase_cell(redis_client: Any, spec_name: str, started_at: str) -> str:
    """The phase-cell stream currently carrying this run's agent output (in-flight binding).

    The fleet job's own stream carries only orchestrator milestones ("phase prior ok"); the
    sibling cells publish their agent events under ``events_log:<spec>:<phase>``
    (``FINOPS_CELL_ID``). For an IN-FLIGHT run the drawer should read and follow the newest
    phase stream qualified by the run's own start, so "Follow live" shows the agent's output
    and steps rather than the orchestrator's summary — the miss the 2026-09-22 review found
    (the drawer followed the JOB stream and showed two events while the agent streamed
    hundreds).

    Best-effort and honest: an absent scan surface, an unreadable store, or no stream whose
    newest event lands at/after the run's start returns ``""`` and the caller keeps the
    job-stream binding (never a guessed neighbour).
    """
    if not spec_name:
        return ""
    started = _epoch(started_at) or 0.0
    try:
        keys = list(redis_client.scan_iter(match=f"{EVENT_LOG_PREFIX}{spec_name}:*", count=200))
    except Exception:  # noqa: BLE001 — a store without the scan surface degrades to the job tail
        return ""
    best: tuple[float, str] | None = None
    for key in keys:
        try:
            newest = redis_client.lindex(key, 0)
        except Exception:  # noqa: BLE001
            continue
        if not newest:
            continue
        try:
            event = json.loads(newest)
        except (TypeError, ValueError):
            continue
        if not isinstance(event, Mapping):
            continue
        part = event.get("part") if isinstance(event.get("part"), Mapping) else {}
        ts = None
        for candidate in (event.get("timestamp"), event.get("time"), part.get("time")):
            ts = _event_epoch(candidate)
            if ts:
                break
        if ts is None or ts + 1.0 < started:
            continue
        name = str(key)[len(EVENT_LOG_PREFIX) :]
        if best is None or ts > best[0]:
            best = (ts, name)
    return best[1] if best else ""


def resolve_live_cell(redis_client: Any, cell_id: str) -> tuple[str, str]:
    """Resolve a FLEET JOB cell id to its run's live phase stream (``(cell, basis)``).

    Workflow runs appear in the room's cell list under their FLEET JOB id, whose own event
    stream carries only orchestrator milestones ("phase prior ok" — two events for a whole
    run) while the agent publishes under ``events_log:<spec>:<phase>`` (the sibling cell's
    ``FINOPS_CELL_ID``). This resolves a job cell to the newest live phase stream qualified
    by the job's own acceptance time — the SAME in-flight rule the run drawer applies
    (2026-09-22, operator-flagged): a job entry that already carries a ``run_id`` (finished)
    passes through unchanged, as does any id that is not a fleet job.

    Best-effort and honest: an unreadable board or no qualifying phase stream returns the
    requested id with an empty basis — the caller streams what it asked for.
    """
    if not cell_id:
        return cell_id, ""
    try:
        board = redis_client.hgetall(FLEET_JOBS_KEY) or {}
    except Exception:  # noqa: BLE001 — an unreadable store never redirects the stream
        return cell_id, ""
    entry: dict[str, Any] | None = None
    for job_id, payload in board.items():
        if str(job_id) != cell_id:
            continue
        try:
            parsed = json.loads(payload)
        except (TypeError, ValueError):
            return cell_id, ""
        entry = dict(parsed) if isinstance(parsed, Mapping) else None
        break
    if entry is None or str(entry.get("run_id") or ""):
        return cell_id, ""
    spec = str(entry.get("spec") or "")
    spec_name = spec.rsplit("/", 1)[-1].removesuffix(".yaml") if spec else ""
    if not spec_name:
        return cell_id, ""
    phase_cell = _live_phase_cell(redis_client, spec_name, str(entry.get("ts") or ""))
    if not phase_cell or phase_cell == cell_id:
        return cell_id, ""
    return phase_cell, f"job {cell_id} -> live phase stream {phase_cell}"


def _board_row_cells(job_id: str, entry: Mapping[str, Any]) -> list[str]:
    """Return the cell identities represented by one fleet-board row.

    Current fleet rows use their hash field (the job id) as the cell identity.  Some board
    producers also attach an explicit ``cell_id`` or a ``cells`` list when one run owns more
    than one cell.  Accepting all three forms keeps the resolver aligned with the recorded board
    contract without inventing cells when a row carries none.
    """
    values: Any = entry.get("cells")
    if isinstance(values, Mapping):
        values = [values[key] for key in sorted(values)]
    elif not isinstance(values, (list, tuple)):
        values = [entry.get("cell_id") or job_id]

    cell_ids: list[str] = []
    for value in values:
        if isinstance(value, Mapping):
            value = value.get("cell_id") or value.get("id")
        value = str(value or "").strip()
        if value and value not in cell_ids:
            cell_ids.append(value)
    return cell_ids or [job_id]


def _find_board_rows(
    entries: list[tuple[str, dict]], identity: str
) -> list[tuple[str, dict, list[str]]]:
    """Find every board row matching a run, job, or cell identity.

    Redis hash iteration order is not a semantic ordering guarantee, so rows are ordered by their
    stable hash identity before the union is built.  A cell identity matches its containing row;
    a run identity matches every row for that run.  Returning all rows, rather than the first one,
    prevents a multi-row run from losing later cells.
    """
    matches: list[tuple[str, dict, list[str]]] = []
    for job_id, entry in sorted(entries, key=lambda item: str(item[0])):
        cells = _board_row_cells(job_id, entry)
        identities = {str(job_id), str(entry.get("job_id") or ""), str(entry.get("run_id") or "")}
        if identity in identities or identity in cells:
            matches.append((job_id, entry, cells))
    return matches


def _union_board_cells(rows: list[tuple[str, dict, list[str]]]) -> list[str]:
    """Flatten matching board rows into a stable, duplicate-free cell list."""
    cells: list[str] = []
    for _job_id, _entry, row_cells in rows:
        for cell_id in row_cells:
            if cell_id not in cells:
                cells.append(cell_id)
    return cells


def resolve_event_stream(redis_client: Any, requested_id: str) -> dict[str, Any]:
    """Resolve an operator identifier to one event stream and its evidence boundary.

    The operator may arrive with a control-db run id, a fleet job id, or a native cell id.  The
    fleet board is the server-side identity index for all three.  Returning the complete resolution
    in one object is intentional: replay and live delivery must not independently resolve the
    identifier and accidentally subscribe to a different stream.

    ``started_at`` and ``ended_at`` are copied from the matching board row.  An in-flight row has
    no durable run start yet, so its accepted ``ts`` is the narrowest recorded lower boundary
    available to the live stream.  Events outside that boundary, including untimestamped events
    when a boundary exists, are excluded by :func:`_filter_run_events` at both delivery points.
    """
    requested = str(requested_id or "")
    resolution: dict[str, Any] = {
        "requested_id": requested,
        "resolved_id": requested,
        "resolution_basis": "passthrough",
        "cell_ids": [requested] if requested else [],
        "run_id": "",
        "started_at": "",
        "ended_at": "",
        "stream_match": "",
        "reason": "",
    }
    if not requested:
        return resolution

    try:
        board = redis_client.hgetall(FLEET_JOBS_KEY) or {}
    except Exception as exc:  # noqa: BLE001 — an unreadable index never invents a stream
        resolution["reason"] = f"{type(exc).__name__}: {exc}"
        return resolution

    entries: list[tuple[str, dict]] = []
    for job_id, payload in board.items():
        try:
            entry = json.loads(payload)
        except (TypeError, ValueError):
            continue
        if isinstance(entry, Mapping):
            entries.append((str(job_id), dict(entry)))

    rows = _find_board_rows(entries, requested)
    if not rows:
        return resolution

    job_id, entry, _row_cells = rows[0]
    cell_ids = _union_board_cells(rows)
    if str(entry.get("run_id") or "") == requested:
        basis = "by_run_id"
    elif requested == job_id or str(entry.get("job_id") or "") == requested:
        basis = "by_job_id"
    else:
        basis = "by_cell_id"

    resolved_id = requested if basis == "by_cell_id" else (cell_ids[0] if cell_ids else job_id)
    run_id = str(entry.get("run_id") or "")
    started_at = str(entry.get("started_at") or entry.get("start_at") or entry.get("ts") or "")
    ended_at = str(entry.get("ended_at") or entry.get("completed_at") or "")
    stream_match = ""
    if basis == "by_job_id" and not run_id:
        spec = str(entry.get("spec") or "")
        spec_name = spec.rsplit("/", 1)[-1].removesuffix(".yaml") if spec else ""
        if spec_name:
            phase_cell = _live_phase_cell(redis_client, spec_name, started_at)
            if phase_cell and phase_cell != resolved_id:
                resolved_id = phase_cell
                stream_match = "by_phase_time"

    resolution.update(
        {
            "resolved_id": resolved_id,
            "resolution_basis": basis,
            "cell_ids": cell_ids,
            "run_id": run_id,
            "started_at": started_at,
            "ended_at": ended_at,
            "stream_match": stream_match,
        }
    )
    return resolution


def read_run_logs(
    redis_client: Any,
    run_id: str,
    *,
    spec_name: str = "",
    started_at: str = "",
    ended_at: str = "",
    limit: int = LOGS_EVENT_LIMIT,
) -> dict[str, Any]:
    """Resolve the run's event stream and read its run-scoped retained tail.

    Two match bases, both NAMED on the block (``match``):

    * ``by_run_id`` — the fleet job board entry whose ``run_id`` is this run. The fleet writes
      that field when the job COMPLETES (the ledger is the source), so a finished run always
      resolves exactly.
    * ``by_spec_time`` — for an IN-FLIGHT run the board entry carries no ``run_id`` yet (only
      job_id/spec/ts/status). The fallback matches the spec's job accepted nearest before the
      run's own start. ``campaign_concurrency = 1`` is what makes this unambiguous: a spec
      has at most one live job, so spec + time identifies it without guessing across specs.

    A missing board entry is ``unbound``; any Redis failure is ``unavailable`` with the reason
    named; the match basis is always reported, never implied.  The selected stream is read in
    full, then filtered by the run's recorded ``started_at``/``ended_at`` window before the
    bounded display tail, count, and history state are derived.  Events without a recorded
    timestamp are excluded with a named reason because they cannot prove run membership.
    """
    try:
        board = redis_client.hgetall(FLEET_JOBS_KEY) or {}
    except Exception as exc:  # noqa: BLE001 — an unreadable store is named, never a 500
        return logs_block(cell_id="", state="unavailable", reason=f"{type(exc).__name__}: {exc}")
    entries: list[tuple[str, dict]] = []
    for job_id, payload in board.items():
        try:
            entry = json.loads(payload)
        except (TypeError, ValueError):
            continue
        if isinstance(entry, Mapping):
            entries.append((str(job_id), dict(entry)))
    cell_id = ""
    cell_ids: list[str] = []
    selected_job_id = ""
    match = ""
    rows = _find_board_rows(entries, run_id)
    if rows:
        cell_ids = _union_board_cells(rows)
        cell_id, match = cell_ids[0], "by_run_id"
        selected_job_id = rows[0][0]
    if not cell_id and spec_name:
        cell_id, match = _match_job_by_spec_time(entries, spec_name, started_at)
        rows = _find_board_rows(entries, cell_id) if cell_id else []
        cell_ids = _union_board_cells(rows) if rows else ([cell_id] if cell_id else [])
        selected_job_id = rows[0][0] if rows else cell_id
    if not cell_id:
        return logs_block(
            cell_id="",
            state="unbound",
            reason="no fleet job on the board references this run",
        )
    # IN-FLIGHT (a job entry without a run_id — ``by_spec_time``): the job's own stream holds
    # only orchestrator milestones, so bind the newest live PHASE stream — the agent's output
    # and steps — for both the retained tail and Follow-live. Finished runs (``by_run_id``)
    # keep the job tail: it carries every phase's milestone.
    stream_cell = ""
    if match == "by_spec_time":
        stream_cell = _live_phase_cell(redis_client, spec_name, started_at)
    read_cell = stream_cell or cell_id
    try:
        raw = redis_client.lrange(f"{EVENT_LOG_PREFIX}{read_cell}", 0, -1)
    except Exception as exc:  # noqa: BLE001
        return logs_block(
            cell_id=read_cell,
            cell_ids=cell_ids,
            state="unavailable",
            reason=f"{type(exc).__name__}: {exc}",
        )
    filtered, filter_reason = _filter_run_events(
        list(raw or []), started_at=started_at, ended_at=ended_at
    )
    bounded = filtered[: max(limit, 0)]
    return logs_block(
        cell_id=read_cell,
        cell_ids=cell_ids,
        job_id=selected_job_id or cell_id,
        live_cell_id=stream_cell,
        state="recorded",
        reason=filter_reason,
        raw_events=list(reversed(bounded)),
        total=len(filtered),
        match=match,
        stream_match="by_phase_time" if stream_cell else "",
        resolution_basis=match,
        slice_limit=limit,
    )


#: The in-flight fallback's tolerance: a job accepted within this many seconds of the run's
#: start is a candidate (the acceptance precedes the orchestrator's first write by seconds).
SPEC_TIME_WINDOW_S = 600.0


def _match_job_by_spec_time(
    entries: list[tuple[str, dict]], spec_name: str, started_at: str
) -> tuple[str, str]:
    """The in-flight fallback: the spec's job accepted nearest before the run's start."""
    started = _epoch(started_at)
    best: tuple[float, str] | None = None
    suffix = f"{spec_name}.yaml"
    for job_id, entry in entries:
        spec = str(entry.get("spec") or "")
        if not spec.endswith(suffix):
            continue
        accepted = _epoch(entry.get("ts"))
        if started is not None and accepted is not None:
            delta = started - accepted
            if delta < -SPEC_TIME_WINDOW_S or delta > SPEC_TIME_WINDOW_S:
                continue
            distance = abs(delta)
        else:
            distance = 0.0
        if best is None or distance < best[0]:
            best = (distance, job_id)
    return (best[1], "by_spec_time") if best else ("", "")


def _epoch(value: Any) -> float | None:
    """A tolerant epoch read: float seconds, a numeric string, or an ISO-8601 timestamp."""
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    try:
        from datetime import datetime

        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _age_label(started_at: Any, now: Any | None) -> str:
    """Render a server-owned age label, or a named unknown when no reference time was supplied.

    The browser must not read its own clock to order or age operational rows.  The service accepts
    an injected reference time so tests and fixture generation remain deterministic.
    """
    started = _epoch(started_at)
    reference = _epoch(now)
    if started is None or reference is None:
        return "unknown"
    seconds = max(0, int(reference - started))
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def _run_ref(
    db: Any, ref: Mapping[str, Any], *, attention_ids: set[str], now: Any | None
) -> dict[str, Any]:
    """Enrich one packet reference with the service-owned roster facets.

    ``control_status`` remains the source for lifecycle identity and phase progress.  The
    additive facets are read from the same control records and recorded ledger that the drawer
    uses, so a row and its drawer cannot disagree about cost provenance, attempt depth, receipt,
    narration, or the workspace target.
    """
    enriched = dict(ref)
    run_id = str(ref.get("run_id") or "")
    detail = run_detail(db, run_id)
    ledger = run_evidence.recorded_ledger(detail)
    evidence = (detail or {}).get("evidence") or {}
    state = str(ref.get("state") or "")
    completed = ref.get("phases_completed")
    total = ref.get("phases_total")
    if completed is None or total is None:
        enriched["phase.progress"] = "unknown — incomplete phase progress"
    else:
        enriched["phase.progress"] = f"{completed}/{total}"
    enriched.update(
        {
            "run.live": "live"
            if state not in {s.value for s in TERMINAL_RUN_STATES}
            else "not-live",
            "terminal.target": run_evidence._workspace_target(detail, ledger),
            "attempt.number": run_evidence._attempt_number(detail),
            "cost.provenance": (detail or {}).get("cost", {}).get("provenance", "unknown"),
            "decision.eligibility": (
                "approve"
                if state == RunState.AWAITING_APPROVAL.value
                else "promote"
                if state == RunState.PROMOTABLE.value
                else "inspect"
            ),
            "decision.receipt": run_evidence._receipt_state(detail),
            "evidence.advisory": evidence.get("narration", "unknown"),
            "attention.state": "active" if run_id in attention_ids else "none",
            "attention.kind": "attention" if run_id in attention_ids else "",
            "started.age": _age_label(ref.get("started_at"), now),
        }
    )
    return enriched


def state_screens_from_runs(runs: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Build the complete state-screen roster from the authoritative ``RunState`` enum.

    Every screen carries the exact run references assigned to that state and a server-owned
    count.  Empty states remain present, which makes the roster exhaustive and distinguishes
    "no run is in this state" from "the state was never modelled".
    """
    screens: list[dict[str, Any]] = []
    for state in RUN_STATE_ORDER:
        members = [dict(run) for run in runs if str(run.get("state") or "") == state]
        screens.append(
            {
                "state": state,
                "label": state.replace("_", " "),
                "count": len(members),
                "runs": members,
            }
        )
    return screens


def order_run_refs(runs: list[Mapping[str, Any]], attention_ids: set[str]) -> list[dict[str, Any]]:
    """Order roster rows with server-owned attention priority and deterministic id ties."""
    return sorted(
        (dict(run) for run in runs),
        key=lambda entry: (
            0 if str(entry.get("run_id") or "") in attention_ids else 1,
            str(entry.get("run_id") or ""),
        ),
    )


def _named_count(value: int | None, *, available: bool, reason: str = "") -> dict[str, Any]:
    """Return a count with an explicit state; an unavailable count is never rendered as zero."""
    if not available:
        return {"state": "unavailable", "value": None, "reason": reason or "source unavailable"}
    return {"state": "recorded", "value": value, "reason": ""}


def _worker_health(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Project worker health with a fail-closed unavailable state."""
    degraded = [
        item
        for item in packet.get("degraded", [])
        if isinstance(item, Mapping) and item.get("surface") == "unhealthy_workers"
    ]
    if degraded:
        return {
            "state": "unavailable",
            "count": None,
            "workers": [],
            "reason": degraded[0].get("reason"),
        }
    workers = packet.get("unhealthy_workers")
    if not isinstance(workers, list):
        return {
            "state": "unavailable",
            "count": None,
            "workers": [],
            "reason": "worker health malformed",
        }
    return {"state": "recorded", "count": len(workers), "workers": list(workers), "reason": ""}


def unavailable_snapshot(
    *, reason: str, degraded: list[Mapping[str, Any]] | None = None
) -> dict[str, Any]:
    """Return the named, HTTP-200 Operations envelope used when the control DB cannot be read."""
    notes = [dict(item) for item in (degraded or [])]
    notes.append({"surface": "control_db", "reason": reason})
    unknown = {
        key: _named_count(None, available=False, reason=reason)
        for key in ("active_runs", "decisions_owed", "promotable_runs")
    }
    return {
        "schema": SCHEMA,
        "source": {
            "packet_schema": "control-status/v1",
            "control_epoch": None,
            "repo_head_sha": "",
        },
        "summary": unknown,
        "attention": [],
        "active_runs": [],
        "promotable_runs": [],
        "unhealthy_workers": [],
        "worker_health": {"state": "unavailable", "count": None, "workers": [], "reason": reason},
        "state_screens": [],
        "projection_lag": {},
        "safe_actions": [],
        "degraded": notes,
    }


def operational_snapshot(
    db: Any,
    *,
    repo_head_sha: str,
    heartbeats: Mapping[str, Mapping[str, Any]] | None,
    now: Any | None = None,
    degraded: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """The room's operational view: packet, server-owned summaries, and state screens.

    ``attention`` is the decisions-owed view: every awaiting approval (with the purpose the
    operator owes) and every failed run, carrying the packet's own identifiers. It is a
    projection of the packet, not a second source of truth — the parity test asserts the
    identifiers match block-for-block.  All values needed by the browser roster are derived here;
    the browser only formats and lays out these read-model values.
    """
    packet = build_packet(
        db,
        repo_head_sha=repo_head_sha,
        heartbeats=heartbeats,
        now=now,
        degraded=degraded or (),
    )

    attention: list[dict[str, Any]] = []
    for entry in packet.get("awaiting_approvals", []):
        # pass-through with a discriminator: the packet's fields are carried verbatim.
        attention.append({"kind": "approval", **dict(entry)})
    for entry in packet.get("failed_runs", []):
        attention.append({"kind": "failed", **dict(entry)})

    attention_ids = {str(entry.get("run_id") or "") for entry in attention}
    # `active_runs` is the packet's complete non-terminal block, including promotable.  Do not
    # append the separate promotable projection to it: that would duplicate those rows on screen.
    active_runs = [
        _run_ref(db, entry, attention_ids=attention_ids, now=now)
        for entry in packet.get("active_runs", [])
    ]
    active_runs = order_run_refs(active_runs, attention_ids)
    promotable_runs = [
        dict(entry) for entry in active_runs if entry.get("state") == RunState.PROMOTABLE.value
    ]
    # State screens answer a different question from the compact packet blocks: they must expose
    # every reachable lifecycle state, including terminal cancelled/quarantined/published rows
    # that the packet intentionally does not carry in its active/failed blocks.
    all_runs: list[dict[str, Any]] = []
    for record in db.runs():
        base = (
            active_run_ref(db, record)
            if record.state not in TERMINAL_RUN_STATES
            else run_ref(record)
        )
        all_runs.append(_run_ref(db, base, attention_ids=attention_ids, now=now))
    worker_health = _worker_health(packet)
    degraded_notes = list(packet.get("degraded", []))
    summary = {
        "active_runs": _named_count(len(active_runs), available=True),
        "decisions_owed": _named_count(len(attention), available=True),
        "promotable_runs": _named_count(len(promotable_runs), available=True),
    }

    return {
        "schema": SCHEMA,
        "source": {
            "packet_schema": packet.get("schema"),
            "control_epoch": packet.get("control_epoch"),
            "repo_head_sha": packet.get("repo_head_sha"),
        },
        "attention": attention,
        # the packet's blocks flow through unchanged — the room renders what the authority
        # returned (or names it in ``degraded``), never a re-derivation.
        "summary": summary,
        "active_runs": active_runs,
        "promotable_runs": promotable_runs,
        "unhealthy_workers": list(packet.get("unhealthy_workers", [])),
        "worker_health": worker_health,
        "state_screens": state_screens_from_runs(all_runs),
        "projection_lag": packet.get("projection_lag", {}),
        "safe_actions": list(packet.get("safe_actions", [])),
        "degraded": degraded_notes,
    }


def run_detail(db: Any, run_id: str, *, redis_client: Any | None = None) -> dict[str, Any] | None:
    """The P1/P2 per-run view: identity, attempts, gates, approvals, command receipts.

    Every raw block is read from the control records AS THEY ARE: a record the database has
    never seen yields an empty list (the DB said none), and an unknown run is ``None`` (the
    route renders 404) — never an invented skeleton. Records pass through via
    ``dataclasses.asdict`` so this layer can not curate away a field or invent one.

    The derived blocks are ADDITIVE (the six raw keys above keep their shape) and reuse the
    service-owned derivations ``glance`` also uses, so the drawer and the glance row can never
    disagree about the same run:

    * ``cost`` — the aggregate's provenance label (measured zero stays metered, absent stays
      unknown, mixed stays mixed);
    * ``evidence`` — the measured verdict, the decision receipt, and the agent's narration;
    * ``recorded`` — the ledger pointer and whether it resolved;
    * ``delivered_knowledge`` — per phase, what was SELECTED and DELIVERED (never "used");
    * ``prepared`` — per phase, the prepared-step reference or a named missing;
    * ``timings`` — one row per timing field actually recorded, each with a measured state;
    * ``logs`` — the run's selected event-stream tail (recorded), or a NAMED absence. The client
      is INJECTED by the context (which owns the accessor); a missing client is ``unavailable``.
    """
    run = db.get_run(run_id)
    if run is None:
        return None
    detail: dict[str, Any] = {
        "schema": RUN_DETAIL_SCHEMA,
        "run": asdict(run) | {"state": run.state.value},
        "attempts": [asdict(row) for row in db.attempts(run_id)],
        "gates": [asdict(row) for row in db.gate_results(run_id)],
        "approvals": [asdict(row) for row in db.approvals(run_id)],
        "commands": [asdict(row) for row in db.commands(run_id=run_id)],
    }
    # The ledger is read ONCE and shared by every ledger-derived block, so cost, evidence,
    # delivery, and prepared-step references all describe the same recorded artifact.
    ledger = run_evidence.recorded_ledger(detail)
    detail["cost"] = run_evidence.cost_block(detail["run"], detail, ledger)
    detail["evidence"] = run_evidence.evidence_block(detail, ledger)
    detail["recorded"] = run_evidence.recorded_block(detail, ledger)
    detail["delivered_knowledge"] = run_evidence.delivered_knowledge_block(ledger)
    detail["prepared"] = run_evidence.prepared_block(ledger)
    detail["timings"] = run_evidence.timings_block(detail, ledger)
    if redis_client is None:
        detail["logs"] = logs_block(
            cell_id="", state="unavailable", reason="no event store bound to the read model"
        )
    else:
        detail["logs"] = read_run_logs(
            redis_client,
            run_id,
            spec_name=str(detail["run"].get("spec_name") or ""),
            started_at=str(detail["run"].get("started_at") or ""),
            ended_at=str(detail["run"].get("ended_at") or ""),
        )
    return detail
