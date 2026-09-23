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

from agentic_dynamics.control.control_db import RunState, TERMINAL_RUN_STATES
from agentic_dynamics.control.control_status import active_run_ref, build_packet, run_ref
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

# ``RunState`` is the authority for this roster.  Keeping the order derived from the enum makes
# adding a lifecycle state a visible contract change instead of silently dropping it from the room.
RUN_STATE_ORDER = tuple(state.value for state in RunState)


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
    failed_runs = [
        _run_ref(db, entry, attention_ids=attention_ids, now=now)
        for entry in packet.get("failed_runs", [])
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
