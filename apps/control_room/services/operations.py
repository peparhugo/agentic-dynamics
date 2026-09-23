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
* packet blocks pass through with their fields intact, while the additive ``runs`` projection
  carries only named joins over the packet and the existing ``run_evidence`` records; the room
  never lets the browser invent attention, order, age, or a lifecycle situation.

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


def _format_age_seconds(seconds: int | None) -> str:
    """Format a measured age without turning an absent timestamp into ``0s ago``.

    The browser used to read ``started_at`` and consult its own clock.  That made a screenshot's
    answer depend on when it was taken, and it let two clients disagree about the same run.  The
    service now formats the injected observation interval once; ``age unknown`` is deliberately a
    word rather than a numeric fallback when the interval cannot be measured.
    """
    if seconds is None:
        return "age unknown"
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def _age_fields(started_at: Any, now: Any | None) -> dict[str, Any]:
    """Return the named started-age fields from one injected observation instant.

    ``now`` is an input to this read model, not an implicit call to the wall clock.  That keeps
    fixture rendering deterministic and makes the provenance boundary explicit: a missing or
    malformed timestamp produces ``unknown`` rather than an invented age.
    """
    started = _epoch(started_at)
    observed = _epoch(now)
    if started is None or observed is None:
        return {
            "started.age": "age unknown",
            "started.age_seconds": None,
            "started.age_state": "unknown",
        }
    age = max(0, int(observed - started))
    return {
        "started.age": _format_age_seconds(age),
        "started.age_seconds": age,
        "started.age_state": "measured",
    }


def _operator_state(run: Mapping[str, Any], detail: Mapping[str, Any] | None) -> str:
    """Map recorded lifecycle/evidence to the six named operator situations.

    This is a presentation mapping, not a new lifecycle state.  It only names ``escalated`` when
    an attempt actually records both escalation tiers, and it preserves ``awaiting_approval`` as
    ``blocked`` rather than collapsing a designed stop into ``failed``.  A future producer may
    emit an explicit ``stalled`` observation; without that observation an ordinary running row is
    not silently relabelled as stalled.
    """
    state = str(run.get("state") or "")
    if state == "stalled":
        return "stalled"
    if state == "awaiting_approval":
        return "blocked"
    if state == "failed":
        return "failed"
    if state in {"merged", "projecting", "published"}:
        return "done"
    for attempt in (detail or {}).get("attempts") or []:
        if attempt.get("escalation_from") and attempt.get("escalation_to"):
            return "escalated"
    if state in {"queued", "running", "verifying", "promoting"}:
        return "running"
    return "unknown"


def _row_events(detail: dict[str, Any] | None, *, limit: int = 8) -> list[dict[str, Any]]:
    """Project recorded control records into the drawer's bounded event history.

    This helper belongs beside the Operations run projection because both the glance row and the
    Operations drawer read the same control records.  It reports selection and delivery only: an
    evidence identifier is never upgraded into a claim that the agent used or caused anything.
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


def run_row(
    run: Mapping[str, Any],
    *,
    epoch: int,
    detail: dict[str, Any] | None,
    attention_entry: Mapping[str, Any] | None = None,
    now: Any | None = None,
    triage_rank: int = 1,
) -> dict[str, Any]:
    """Build the shared server-owned per-run row used by Operations and glance.

    The packet remains the authority for identifiers and lifecycle fields.  The existing
    ``run_evidence`` service remains the authority for cost, attempt, target, evidence, and
    receipt labels.  This function only joins those already-recorded answers and adds the
    presentation facts the served room needs: attention membership, triage rank, named operator
    state, and age measured from the caller's observation instant.
    """
    state = str(run.get("state") or "unknown")
    completed = run.get("phases_completed")
    total = run.get("phases_total")
    progress = f"{completed}/{total}" if completed is not None and total is not None else "unknown"
    run_mapping = dict(run)
    run_mapping.setdefault("run_id", "unknown")
    detail_mapping = detail or {}
    ledger = run_evidence.recorded_ledger(detail_mapping)
    age = _age_fields(run_mapping.get("started_at"), now)
    operator_state = _operator_state(run_mapping, detail_mapping)
    attention_kind = str((attention_entry or {}).get("kind") or "none")
    eligibility = (
        "approve"
        if state == "awaiting_approval"
        else ("promote" if state == "promotable" else "inspect")
    )
    sha = str(run_mapping.get("candidate_sha") or "unknown")
    return {
        "session.identity": str(run_mapping.get("run_id") or "unknown"),
        "spec.cell": run_evidence._cell_binding(ledger),
        "terminal.target": run_evidence._workspace_target(detail_mapping, ledger),
        "command.current": str(run_mapping.get("spec_name") or "unknown"),
        "model.provider": str(run_mapping.get("model") or "unknown"),
        "attempt.number": run_evidence._attempt_number(detail_mapping),
        "phase.progress": progress,
        "lifecycle.state": state,
        "run.live": "live" if state not in {"failed", "cancelled", "quarantined"} else "not-live",
        "source.commit": sha,
        "cost.provenance": run_evidence._cost_provenance(run_mapping, detail_mapping, ledger),
        "attention.state": "active" if attention_entry else "none",
        "attention.kind": attention_kind,
        "evidence.advisory": run_evidence._narration_state(detail_mapping, ledger),
        "evidence.measured": run_evidence._measured_state(detail_mapping, ledger),
        "evidence.source": f"commit {sha}",
        "decision.eligibility": eligibility,
        "decision.receipt": run_evidence._receipt_state(detail_mapping),
        "operator_state": operator_state,
        "triage_rank": triage_rank,
        "state_screen": {
            "state": operator_state,
            "run_id": str(run_mapping.get("run_id") or "unknown"),
            "lifecycle": state,
            "phase": progress,
            "attention": attention_kind,
            "age": age["started.age"],
            "action": eligibility,
        },
        "control_epoch": epoch,
        "run.events": _row_events(detail_mapping),
        **age,
    }


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


def operational_snapshot(
    db: Any,
    *,
    repo_head_sha: str,
    heartbeats: Mapping[str, Mapping[str, Any]] | None,
    now: Any | None = None,
) -> dict[str, Any]:
    """The room's operational view: the packet, plus a triage-ordered ``attention`` block.

    ``attention`` is the decisions-owed view: every awaiting approval (with the purpose the
    operator owes) and every failed run, carrying the packet's own identifiers. It is a
    projection of the packet, not a second source of truth — the parity test asserts the
    identifiers match block-for-block.
    """
    packet = build_packet(db, repo_head_sha=repo_head_sha, heartbeats=heartbeats, now=now)

    # The packet owns the attention membership and all action identifiers.  The service enriches
    # those rows once, then hands the exact same row facts to the roster and the state screens.
    # Keeping this join here prevents the browser from matching two independent arrays and
    # accidentally deciding that a run is urgent because it happens to share an id.
    packet_attention: list[dict[str, Any]] = []
    attention_by_run: dict[str, dict[str, Any]] = {}
    for entry in packet.get("awaiting_approvals", []):
        enriched = {"kind": "approval", **dict(entry)}
        packet_attention.append(enriched)
        attention_by_run.setdefault(str(enriched.get("run_id") or ""), enriched)
    for entry in packet.get("failed_runs", []):
        enriched = {"kind": "failed", **dict(entry)}
        packet_attention.append(enriched)
        attention_by_run.setdefault(str(enriched.get("run_id") or ""), enriched)

    packet_runs = (
        list(packet.get("active_runs", []))
        + list(packet.get("promotable_runs", []))
        + list(packet.get("failed_runs", []))
    )
    details: dict[str, dict[str, Any] | None] = {}
    for entry in packet_runs:
        run_id = str(entry.get("run_id") or "")
        if not run_id:
            continue
        try:
            details[run_id] = run_detail(db, run_id, now=now)
        except Exception:  # noqa: BLE001 — one unreadable ledger names the row's unknowns
            details[run_id] = None

    def row_for(entry: Mapping[str, Any]) -> dict[str, Any]:
        run_id = str(entry.get("run_id") or "")
        attention_entry = attention_by_run.get(run_id)
        # Attention and terminal failure are the first triage tier. The stable packet order is
        # retained inside each tier, so ordering is deterministic without a client comparator.
        preliminary_state = str(entry.get("state") or "")
        rank = 0 if attention_entry or preliminary_state == "failed" else 1
        return run_row(
            entry,
            epoch=int(packet.get("control_epoch") or 0),
            detail=details.get(run_id),
            attention_entry=attention_entry,
            now=now,
            triage_rank=rank,
        )

    all_rows = [row_for(entry) for entry in packet_runs]
    all_rows.sort(key=lambda row: int(row.get("triage_rank", 1)))
    row_by_id = {str(row.get("session.identity")): row for row in all_rows}

    # Attention rows carry the same server-owned state and age as the roster.  The table can
    # therefore render the packet's selection basis directly rather than re-deriving membership.
    attention: list[dict[str, Any]] = []
    for entry in packet_attention:
        row = row_by_id.get(str(entry.get("run_id") or ""), {})
        attention.append(
            {
                **entry,
                "operator_state": row.get("operator_state", "unknown"),
                "started.age": row.get("started.age", "age unknown"),
                "started.age_seconds": row.get("started.age_seconds"),
                "started.age_state": row.get("started.age_state", "unknown"),
            }
        )

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
        # Preserve the packet blocks byte-for-byte for existing machine consumers.  The served
        # board reads the additive ``runs`` projection below, where the presentation fields live;
        # no caller has to reinterpret an enriched row as if it were the control packet itself.
        "active_runs": list(packet.get("active_runs", [])),
        "promotable_runs": list(packet.get("promotable_runs", [])),
        "failed_runs": list(packet.get("failed_runs", [])),
        # ``runs`` is the authoritative display order.  The browser must preserve it; it does
        # not classify or sort rows a second time.
        "runs": all_rows,
        "state_screens": [row["state_screen"] for row in all_rows],
        "unhealthy_workers": list(packet.get("unhealthy_workers", [])),
        "projection_lag": packet.get("projection_lag", {}),
        "safe_actions": list(packet.get("safe_actions", [])),
        "degraded": list(packet.get("degraded", [])),
    }


def run_detail(
    db: Any,
    run_id: str,
    *,
    redis_client: Any | None = None,
    now: Any | None = None,
) -> dict[str, Any] | None:
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
    # The drawer uses this server-owned age.  It intentionally keeps the raw ``started_at`` too:
    # the timestamp is recorded evidence, while ``started_age`` is the presentation answer from
    # the same observation basis as the Operations roster.
    detail["run"].update(_age_fields(detail["run"].get("started_at"), now))
    detail["run"]["started_age"] = detail["run"].get("started.age", "age unknown")
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
