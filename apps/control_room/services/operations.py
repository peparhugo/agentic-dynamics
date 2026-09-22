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

from agentic_dynamics.control.control_status import build_packet
from agentic_dynamics.control.live import EVENT_LOG_MAX, EVENT_LOG_PREFIX
from apps.control_room.services import run_evidence

#: The read model's schema id (additive; the source packet's schema rides in ``source``).
SCHEMA = "control-room-operations/v1"

#: The per-run detail's schema id (step 5, P1/P2).
RUN_DETAIL_SCHEMA = "control-room-run-detail/v1"

#: The fleet job board (the supervisor's Redis key; each job record carries its ``run_id``).
FLEET_JOBS_KEY = "fleet:jobs"

#: How many retained job events the run detail's logs block carries (a bounded tail).
LOGS_EVENT_LIMIT = 50

# The operator-facing situations are deliberately separate from the control database's
# lifecycle enum.  A run can be ``running`` while the room has no run-bound stall evidence,
# and ``promotable`` is a blocked decision rather than a successful terminal outcome.
STATE_SCREENS: tuple[tuple[str, str], ...] = (
    ("running", "Running"),
    ("blocked", "Blocked"),
    ("stalled", "Stalled"),
    ("failed", "Failed"),
    ("escalated", "Escalated"),
    ("done", "Done"),
)


def logs_block(
    *,
    cell_id: str,
    state: str,
    reason: str = "",
    raw_events: list[str] | None = None,
    total: int = 0,
    match: str = "",
    job_id: str = "",
    live_cell_id: str = "",
    stream_match: str = "",
) -> dict[str, Any]:
    """The run's job-log block: a NAMED state, a bounded parsed tail, no fabricated values.

    States: ``recorded`` (the job's retained tail was read), ``unbound`` (no fleet job on the
    board references this run), ``unavailable`` (the event store could not be read — the reason
    names it). ``events`` is oldest-first for the reader; the producer stores newest-first
    (LPUSH + LTRIM at ``EVENT_LOG_MAX``), and ``history_capped`` reports the producer's own
    bounded-window eviction rather than implying the tail is the whole history.
    """
    events: list[dict[str, Any]] = []
    for payload in raw_events or []:
        try:
            event = json.loads(payload)
        except (TypeError, ValueError):
            event = {"type": "event", "text": str(payload)}
        if not isinstance(event, Mapping):
            event = {"type": "event", "text": str(event)}
        part = event.get("part") if isinstance(event.get("part"), Mapping) else {}
        text = part.get("text", event.get("text", ""))
        events.append(
            {
                "ts": part.get("time") or event.get("time") or None,
                "class": str(event.get("type") or "event"),
                "text": str(text if text is not None else ""),
                "id": str(event.get("id") or ""),
            }
        )
    return {
        "state": state,
        "cell_id": cell_id,
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
    }


def _event_epoch(value: Any) -> float | None:
    """A tolerant event timestamp read in SECONDS (live events stamp milliseconds)."""
    ts = _epoch(value)
    if ts is None:
        return None
    return ts / 1000.0 if ts > 1e11 else ts


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


def read_run_logs(
    redis_client: Any,
    run_id: str,
    *,
    spec_name: str = "",
    started_at: str = "",
    limit: int = LOGS_EVENT_LIMIT,
) -> dict[str, Any]:
    """Resolve the run's fleet job and read its retained event tail (read-only, honest states).

    Two match bases, both NAMED on the block (``match``):

    * ``by_run_id`` — the fleet job board entry whose ``run_id`` is this run. The fleet writes
      that field when the job COMPLETES (the ledger is the source), so a finished run always
      resolves exactly.
    * ``by_spec_time`` — for an IN-FLIGHT run the board entry carries no ``run_id`` yet (only
      job_id/spec/ts/status). The fallback matches the spec's job accepted nearest before the
      run's own start. ``campaign_concurrency = 1`` is what makes this unambiguous: a spec
      has at most one live job, so spec + time identifies it without guessing across specs.

    A missing board entry is ``unbound``; any Redis failure is ``unavailable`` with the reason
    named; the match basis is always reported, never implied.
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
    match = ""
    for job_id, entry in entries:
        if str(entry.get("run_id") or "") == run_id:
            cell_id, match = job_id, "by_run_id"
            break
    if not cell_id and spec_name:
        cell_id, match = _match_job_by_spec_time(entries, spec_name, started_at)
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
        raw = redis_client.lrange(f"{EVENT_LOG_PREFIX}{read_cell}", 0, limit - 1)
        total = int(redis_client.llen(f"{EVENT_LOG_PREFIX}{read_cell}") or 0)
    except Exception as exc:  # noqa: BLE001
        return logs_block(
            cell_id=read_cell, state="unavailable", reason=f"{type(exc).__name__}: {exc}"
        )
    return logs_block(
        cell_id=read_cell,
        job_id=cell_id,
        live_cell_id=stream_cell,
        state="recorded",
        raw_events=list(reversed(list(raw or []))),
        total=total,
        match=match,
        stream_match="by_phase_time" if stream_cell else "",
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


def _age_label(value: Any, *, now: Any | None) -> str:
    """Render a recorded timestamp as a stable, named age for the browser.

    The browser used to read ``started_at`` and compare it with its own clock.  That made the
    same run disagree between the Operations table and the glance row, and made fixture captures
    depend on when Playwright happened to run.  The service owns the comparison now; when the
    observation instant is unavailable the honest value is ``unknown``, never ``0s``.
    """
    started = _epoch(value)
    observed = _epoch(now)
    if started is None or observed is None:
        return "unknown"
    seconds = max(0, int(observed - started))
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    return f"{hours // 24}d"


def _row_events(detail: dict[str, Any] | None, *, limit: int = 8) -> list[dict[str, Any]]:
    """Project only recorded control events into the shared run row.

    This is intentionally a selection projection, not causal interpretation.  The drawer may
    display these events, but the service does not claim that one event caused another.
    """
    if not detail:
        return []
    events: list[dict[str, Any]] = []
    for attempt in detail.get("attempts") or []:
        events.append(
            {
                "id": str(attempt.get("attempt_id") or ""),
                "ts": str(attempt.get("started_at") or ""),
                "class": "lifecycle",
                "text": (
                    f"attempt {run_evidence._token(attempt.get('attempt_no'))} "
                    f"{run_evidence._token(attempt.get('state'))} · "
                    f"{str(attempt.get('model') or 'model unknown')}"
                ),
            }
        )
    for gate in detail.get("gates") or []:
        events.append(
            {
                "id": str(gate.get("gate_id") or ""),
                "ts": str(gate.get("ended_at") or gate.get("started_at") or ""),
                "class": "measured",
                "text": (
                    f"gate {str(gate.get('gate_id') or 'unnamed')} "
                    f"{run_evidence._token(gate.get('verdict'))} · "
                    f"{str(gate.get('executor') or 'executor unknown')}"
                ),
            }
        )
    for approval in detail.get("approvals") or []:
        events.append(
            {
                "id": str(approval.get("approval_id") or ""),
                "ts": str(approval.get("decided_at") or ""),
                "class": "policy",
                "text": f"approved by {str(approval.get('operator') or 'unknown')}",
            }
        )
    for command in detail.get("commands") or []:
        receipt = " · receipt" if str(command.get("receipt_json") or "").strip() else ""
        events.append(
            {
                "id": str(command.get("command_id") or ""),
                "ts": str(command.get("created_at") or ""),
                "class": "source",
                "text": (
                    f"{str(command.get('verb') or 'command')} "
                    f"{run_evidence._token(command.get('state'))}{receipt}"
                ),
            }
        )
    events.sort(key=lambda event: (event["ts"], event["id"]))
    return events[-limit:] if limit > 0 else events


def _operator_state(run: Mapping[str, Any], detail: dict[str, Any] | None) -> str:
    """Map a lifecycle row to the named operator state screens.

    Escalation wins because it is an advisory boundary on an otherwise running or completed
    attempt.  Stall is not inferred from age alone: without a run-bound heartbeat or phase
    status the service returns ``running`` and leaves the dedicated stalled screen unbound.
    """
    attempts = (detail or {}).get("attempts") or []
    if any(
        str(attempt.get("escalation_from") or "").strip()
        or str(attempt.get("escalation_to") or "").strip()
        for attempt in attempts
        if isinstance(attempt, Mapping)
    ):
        return "escalated"
    state = str(run.get("state") or "unknown")
    if state in {"awaiting_approval", "promotable"}:
        return "blocked"
    if state == "failed":
        return "failed"
    if state in {"merged", "projecting", "published"}:
        return "done"
    return "running" if state in {"queued", "running", "verifying", "promoting"} else "unknown"


def attention_projection(
    packet: Mapping[str, Any], *, now: Any | None = None
) -> list[dict[str, Any]]:
    """Build the decisions-owed list once, including server-owned order and age values."""
    attention: list[dict[str, Any]] = []
    for entry in packet.get("awaiting_approvals", []):
        attention.append({"kind": "approval", **dict(entry)})
    for entry in packet.get("failed_runs", []):
        attention.append({"kind": "failed", **dict(entry)})
    # A promotable run is a controller decision even though it is not in `awaiting_approvals`.
    for entry in packet.get("promotable_runs", []):
        attention.append(
            {
                "kind": "promotion",
                **dict(entry),
                "gate_id": "",
                "purpose": "candidate verified; awaiting the permanence decision",
            }
        )
    priority = {"failed": 0, "approval": 1, "promotion": 2}
    for index, entry in enumerate(attention):
        entry["attention.state"] = "active"
        entry["attention.order"] = index
        entry["started.age"] = _age_label(entry.get("started_at"), now=now)
    attention.sort(
        key=lambda entry: (priority.get(str(entry.get("kind")), 99), str(entry.get("run_id")))
    )
    for index, entry in enumerate(attention):
        entry["attention.order"] = index
    return attention


def run_row(
    run: Mapping[str, Any],
    *,
    epoch: int,
    detail: dict[str, Any] | None,
    attention_entry: Mapping[str, Any] | None = None,
    now: Any | None = None,
) -> dict[str, Any]:
    """Project one packet run reference into the shared Operations/glance row schema.

    The packet supplies identity and lifecycle fields; ``run_evidence`` supplies recorded ledger
    facts; this function supplies only presentation labels such as the age and operator state.
    It never fills an absent record with a guessed attempt, workspace, receipt, or event.
    """
    state = str(run.get("state") or "unknown")
    completed = run.get("phases_completed")
    total = run.get("phases_total")
    progress = "unknown" if completed is None or total is None else f"{completed}/{total}"
    sha = str(run.get("candidate_sha") or "unknown")
    ledger = run_evidence.recorded_ledger({"run": dict(run)} | (detail or {}))
    attention_entry = attention_entry or {}
    operator_state = _operator_state(run, detail)
    eligibility = (
        "approve"
        if state == "awaiting_approval"
        else "promote"
        if state == "promotable"
        else "inspect"
    )
    return {
        **dict(run),
        "session.identity": str(run.get("run_id") or "unknown"),
        "spec.cell": run_evidence._cell_binding(ledger),
        "terminal.target": run_evidence._workspace_target(detail, ledger),
        "command.current": str(run.get("spec_name") or "unknown"),
        "model.provider": str(run.get("model") or "unknown"),
        "attempt.number": run_evidence._attempt_number(detail),
        "phase.progress": progress,
        "lifecycle.state": state,
        "run.live": "live"
        if state not in {"failed", "cancelled", "quarantined", "published"}
        else "not-live",
        "source.commit": sha,
        "cost.provenance": run_evidence._cost_provenance(dict(run), detail, ledger),
        "attention.state": str(attention_entry.get("attention.state") or "none"),
        "attention.kind": str(attention_entry.get("kind") or "none"),
        "attention.order": attention_entry.get("attention.order"),
        "evidence.advisory": run_evidence._narration_state(detail, ledger),
        "evidence.measured": run_evidence._measured_state(detail, ledger),
        "evidence.source": f"commit {sha}",
        "decision.eligibility": eligibility,
        "decision.receipt": run_evidence._receipt_state(detail),
        "started.age": _age_label(run.get("started_at"), now=now),
        "operator.state": operator_state,
        "operator.state_reason": (
            "no run-bound heartbeat or phase stall evidence recorded"
            if operator_state == "running"
            else ""
        ),
        "control_epoch": epoch,
        "run.events": _row_events(detail),
    }


def state_screens(rows: list[dict[str, Any]], *, available: bool = True) -> list[dict[str, Any]]:
    """Return all six named state screens, including honest empty/unbound screens."""
    screens: list[dict[str, Any]] = []
    for key, label in STATE_SCREENS:
        selected = [row for row in rows if row.get("operator.state") == key]
        if not available:
            screens.append(
                {
                    "key": key,
                    "label": label,
                    "state": "unavailable",
                    "reason": "control database could not be read",
                    "runs": [],
                }
            )
        elif selected:
            screens.append(
                {"key": key, "label": label, "state": "recorded", "reason": "", "runs": selected}
            )
        else:
            reason = (
                "no run-bound heartbeat or phase stall evidence recorded"
                if key == "stalled"
                else "no run in this state was returned by the control packet"
            )
            screens.append(
                {"key": key, "label": label, "state": "unbound", "reason": reason, "runs": []}
            )
    return screens


def operational_snapshot(
    db: Any,
    *,
    repo_head_sha: str,
    heartbeats: Mapping[str, Mapping[str, Any]] | None,
    now: Any | None = None,
) -> dict[str, Any]:
    """The room's operational view: packet blocks plus server-owned run projections.

    The raw packet arrays remain available for callers that need the control-status contract.
    ``runs`` and the enriched arrays are additive read models: one service computes attention,
    order, age, evidence fields, and state screens so the board and drawer cannot disagree.
    """
    packet = build_packet(db, repo_head_sha=repo_head_sha, heartbeats=heartbeats, now=now)
    attention = attention_projection(packet, now=now)
    refs: list[dict[str, Any]] = []
    refs.extend(packet.get("active_runs", []))
    refs.extend(packet.get("promotable_runs", []))
    refs.extend(packet.get("failed_runs", []))
    attention_by_run = {
        str(entry.get("run_id")): entry for entry in attention if entry.get("run_id")
    }
    rows: list[dict[str, Any]] = []
    for ref in refs:
        detail = run_detail(db, str(ref.get("run_id") or "")) if ref.get("run_id") else None
        rows.append(
            run_row(
                ref,
                epoch=int(packet.get("control_epoch") or 0),
                detail=detail,
                attention_entry=attention_by_run.get(str(ref.get("run_id"))),
                now=now,
            )
        )
    rows.sort(
        key=lambda row: (
            row.get("attention.order") is None,
            row.get("attention.order") if row.get("attention.order") is not None else 999999,
            str(row.get("run_id") or ""),
        )
    )
    counts = {
        "active": len(packet.get("active_runs", [])),
        "attention": len(attention),
        "promotable": len(packet.get("promotable_runs", [])),
        "unhealthy_workers": len(packet.get("unhealthy_workers", [])),
    }

    return {
        "schema": SCHEMA,
        "source": {
            "packet_schema": packet.get("schema"),
            "control_epoch": packet.get("control_epoch"),
            "repo_head_sha": packet.get("repo_head_sha"),
        },
        "attention": attention,
        # Raw packet blocks stay available for packet parity; the enriched `runs` array is the
        # board's row source.  This preserves the control-status contract while making the
        # presentation projection authoritative.
        "active_runs": list(packet.get("active_runs", [])),
        "promotable_runs": list(packet.get("promotable_runs", [])),
        "failed_runs": list(packet.get("failed_runs", [])),
        "runs": rows,
        "counts": counts,
        "state_screens": state_screens(rows),
        "unhealthy_workers": list(packet.get("unhealthy_workers", [])),
        "projection_lag": packet.get("projection_lag", {}),
        "safe_actions": list(packet.get("safe_actions", [])),
        "degraded": list(packet.get("degraded", [])),
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
    * ``logs`` — the run's fleet-job event tail (recorded), or a NAMED absence. The client is
      INJECTED by the context (which owns the accessor); a missing client is ``unavailable``.
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
        )
    return detail
