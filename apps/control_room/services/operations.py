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

``operational_snapshot`` is intentionally read-only given its inputs: it opens no sockets and
never writes.  ``now`` is injected for deterministic age derivations; production callers may omit
it to use the service's display clock at the read boundary.
"""

from __future__ import annotations

import json
import time
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

# The operator-facing state screens are a fixed vocabulary from
# ``docs/research/control_room_state_screens.md``.  Keeping the list here makes the wire
# contract total: a readable payload always names every screen, including screens with no
# matching run, while an unreadable payload can name all six as unavailable.
STATE_SCREENS = ("running", "blocked", "stalled", "failed", "escalated", "done")


def _display_epoch(value: Any) -> float | None:
    """Resolve an injected display clock without making the client own time arithmetic."""
    if value is None:
        return time.time()
    parsed = _epoch(value)
    return parsed if parsed is not None else time.time()


def _age_seconds(value: Any, *, now: Any = None) -> int | None:
    """Return recorded timestamp age, or ``None`` when the timestamp cannot be measured."""
    timestamp = _epoch(value)
    if timestamp is None:
        return None
    return max(0, int(_display_epoch(now) - timestamp))


def _age_label(seconds: int | None) -> str:
    """Render the already-measured age as a stable label for the board and drawer."""
    if seconds is None:
        return "age unknown"
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def _screen_for_run(
    run: Mapping[str, Any], detail: Mapping[str, Any] | None, attention: Mapping[str, Any] | None
) -> tuple[str, str]:
    """Map recorded lifecycle/evidence to one documented operator state.

    This is a classification of recorded facts, not a new lifecycle.  In particular, a failed
    run remains ``failed`` and an awaiting approval remains ``blocked``; the client never has to
    infer either from row order or from the presence of an attention item.
    """
    state = str(run.get("state") or "unknown")
    attempts = (detail or {}).get("attempts") or []
    if any(
        isinstance(attempt, Mapping)
        and (attempt.get("escalation_from") or attempt.get("escalation_to"))
        for attempt in attempts
    ):
        return "escalated", "an escalation tier change is recorded"
    if state == "failed":
        return "failed", "the run reached a terminal failure"
    if state == "awaiting_approval":
        return "blocked", "the run is paused for an operator decision"
    if state in {"merged", "projecting", "published", "promotable"}:
        return "done", "the run reached the permanence or publication path"
    if state in {"running", "verifying", "promoting", "queued"}:
        if str((attention or {}).get("kind") or "") == "stalled":
            return "stalled", "the supervisor marked the run stalled"
        return "running", "the run is in the execution path"
    return "running", "the run state is recorded but has no dedicated screen"


def _run_view(
    run: Mapping[str, Any],
    detail: Mapping[str, Any] | None,
    *,
    attention: Mapping[str, Any] | None,
    now: Any = None,
) -> dict[str, Any]:
    """Build the server-owned row facets shared by the board and the glance vocabulary.

    The packet supplies identity and lifecycle.  The run detail supplies ledger-backed evidence.
    This join is deliberately additive: packet fields remain intact, while the fields consumed
    by the rendered roster are explicit and therefore cannot be silently re-derived in JavaScript.
    """
    from apps.control_room.services import run_evidence

    detail_dict = dict(detail or {})
    run_dict = dict(run)
    ledger = run_evidence.recorded_ledger(detail_dict)
    screen, screen_reason = _screen_for_run(run_dict, detail_dict, attention)
    started_age_seconds = _age_seconds(run_dict.get("started_at"), now=now)
    attention_active = attention is not None
    return {
        "session.identity": str(run_dict.get("run_id") or "unknown"),
        "spec.cell": run_evidence._cell_binding(ledger),
        "terminal.target": run_evidence._workspace_target(detail_dict, ledger),
        "command.current": str(run_dict.get("spec_name") or "unknown"),
        "model.provider": str(run_dict.get("model") or "unknown"),
        "attempt.number": run_evidence._attempt_number(detail_dict),
        "phase.progress": (
            f"{run_dict.get('phases_completed', 0)}/{run_dict.get('phases_total', 0)}"
            if "phases_completed" in run_dict or "phases_total" in run_dict
            else "unknown"
        ),
        "lifecycle.state": str(run_dict.get("state") or "unknown"),
        "run.live": "live" if screen == "running" else "not-live",
        "source.commit": str(run_dict.get("candidate_sha") or "unknown"),
        "cost.provenance": run_evidence._cost_provenance(run_dict, detail_dict, ledger),
        "attention.state": "active" if attention_active else "none",
        "attention.kind": str((attention or {}).get("kind") or "none"),
        "attention.rank": 0
        if attention_active or screen in {"blocked", "stalled", "failed"}
        else 1,
        "evidence.advisory": run_evidence._narration_state(detail_dict, ledger),
        "evidence.measured": run_evidence._measured_state(detail_dict, ledger),
        "evidence.source": f"commit {run_dict.get('candidate_sha') or 'unknown'}",
        "decision.eligibility": (
            "approve"
            if screen == "blocked"
            else "promote"
            if str(run_dict.get("state") or "") == "promotable"
            else "inspect"
        ),
        "decision.receipt": run_evidence._receipt_state(detail_dict),
        "started.age": _age_label(started_age_seconds),
        "started_age_seconds": started_age_seconds,
        "state.screen": screen,
        "state.reason": screen_reason,
    }


def _state_screens(
    rows: list[dict[str, Any]], *, unavailable_reason: str | None = None
) -> list[dict[str, Any]]:
    """Return all six named screens, preserving empty and unavailable states explicitly."""
    if unavailable_reason:
        return [
            {
                "name": name,
                "state": "unavailable",
                "reason": unavailable_reason,
                "run_ids": [],
            }
            for name in STATE_SCREENS
        ]
    return [
        {
            "name": name,
            "state": "recorded",
            "reason": "no runs currently in this state",
            "run_ids": [row["run_id"] for row in rows if row.get("state.screen") == name],
        }
        for name in STATE_SCREENS
    ]


def logs_block(
    *,
    cell_id: str,
    state: str,
    reason: str = "",
    raw_events: list[str] | None = None,
    total: int = 0,
    match: str = "",
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
    }


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
    try:
        raw = redis_client.lrange(f"{EVENT_LOG_PREFIX}{cell_id}", 0, limit - 1)
        total = int(redis_client.llen(f"{EVENT_LOG_PREFIX}{cell_id}") or 0)
    except Exception as exc:  # noqa: BLE001
        return logs_block(
            cell_id=cell_id, state="unavailable", reason=f"{type(exc).__name__}: {exc}"
        )
    return logs_block(
        cell_id=cell_id,
        state="recorded",
        raw_events=list(reversed(list(raw or []))),
        total=total,
        match=match,
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

    attention: list[dict[str, Any]] = []
    for entry in packet.get("awaiting_approvals", []):
        # pass-through with a discriminator: the packet's fields are carried verbatim.
        attention.append({"kind": "approval", **dict(entry)})
    for entry in packet.get("failed_runs", []):
        attention.append({"kind": "failed", **dict(entry)})

    attention_by_run = {
        str(entry.get("run_id")): entry for entry in attention if entry.get("run_id")
    }

    # Join each packet reference to the same detail read the drawer uses.  The packet remains the
    # authority for lifecycle and identifiers; this additive view only exposes recorded evidence
    # and server-owned display derivations to the board.
    packet_runs = (
        list(packet.get("active_runs", []))
        + list(packet.get("promotable_runs", []))
        + list(packet.get("failed_runs", []))
    )
    enriched: list[dict[str, Any]] = []
    for run in packet_runs:
        run_id = str(run.get("run_id") or "")
        detail = run_detail(db, run_id, now=now) if run_id else None
        view = _run_view(run, detail, attention=attention_by_run.get(run_id), now=now)
        enriched.append({**dict(run), **view})

    # The service orders the rows once.  The browser must not independently decide which run is
    # urgent, because doing so made the rendered order disagree with the packet's attention view.
    enriched.sort(key=lambda row: (int(row.get("attention.rank", 1)), str(row.get("run_id") or "")))

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
        # Keep the packet's three raw run blocks byte-for-byte intact.  ``run_rows`` is the
        # additive presentation projection; consumers that need packet parity can still compare
        # these blocks directly to ``build_packet``.
        "active_runs": list(packet.get("active_runs", [])),
        "promotable_runs": list(packet.get("promotable_runs", [])),
        "failed_runs": list(packet.get("failed_runs", [])),
        "run_rows": enriched,
        "state_screens": _state_screens(enriched),
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
    now: Any = None,
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
     * ``display`` — the server-measured started age used by the drawer;
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
    started_age_seconds = _age_seconds(detail["run"].get("started_at"), now=now)
    # This display block is intentionally separate from the raw run record.  The drawer gets a
    # server-measured age without making a second client-side clock interpretation of started_at.
    detail["display"] = {
        "started_age": _age_label(started_age_seconds),
        "started_age_seconds": started_age_seconds,
    }
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
