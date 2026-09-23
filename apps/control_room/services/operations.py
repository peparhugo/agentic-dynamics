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

``operational_snapshot`` is intentionally read-only and deterministic when ``now`` is injected:
it opens no sockets and never writes.  The production context may omit ``now`` for a live age;
the service then takes one server-side instant and uses it for every row in that snapshot.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import asdict
from datetime import datetime
from typing import Any

from agentic_dynamics.control.control_db import RunState
from agentic_dynamics.control.control_status import build_packet
from agentic_dynamics.control.live import EVENT_LOG_MAX, EVENT_LOG_PREFIX
from agentic_dynamics.control.run_lifecycle import stale_after_s
from apps.control_room.services import run_evidence

#: The read model's schema id (additive; the source packet's schema rides in ``source``).
SCHEMA = "control-room-operations/v1"

#: The per-run detail's schema id (step 5, P1/P2).
RUN_DETAIL_SCHEMA = "control-room-run-detail/v1"

#: The operator-facing screens that have evidence in the current control-plane schema.  The
#: ``escalated`` screen from the research wireframe is intentionally absent: no current record
#: carries an escalation transition, so showing it would manufacture a situation.  ``unknown``
#: is the honest screen for lifecycle states that are reachable but do not map to a named resting
#: screen (for example, a queued or quarantined run).
OPERATOR_STATE_SCREENS = (
    "running",
    "blocked",
    "stalled",
    "failed",
    "done",
    "unknown",
)

#: The database is the authority for lifecycle reachability.  Keeping this tuple beside the
#: projection makes the contract explicit and lets the fixture/gate prove that no UI-only state
#: has entered the roster.
RUN_STATE_ROSTER = tuple(state.value for state in RunState)

#: Lifecycle states that the control packet already exposes as active work.  The packet's own
#: arrays remain untouched; this set is used only for the additive all-state Operations roster.
PACKET_ACTIVE_STATES = frozenset(
    {
        RunState.QUEUED.value,
        RunState.RUNNING.value,
        RunState.AWAITING_APPROVAL.value,
        RunState.VERIFYING.value,
        RunState.PROMOTING.value,
        RunState.MERGED.value,
        RunState.PROJECTING.value,
    }
)

#: The fleet job board (the supervisor's Redis key; each job record carries its ``run_id``).
FLEET_JOBS_KEY = "fleet:jobs"

#: How many retained job events the run detail's logs block carries (a bounded tail).
LOGS_EVENT_LIMIT = 50


def _epoch(value: Any) -> float | None:
    """Read seconds from an epoch value or an ISO-8601 timestamp.

    The browser must not compare a run timestamp with its own wall clock: doing so makes a
    deterministic fixture impossible and lets two clients disagree about the same run.  This
    tolerant parser keeps the service boundary compatible with both the control database's ISO
    strings and the test gate's injected numeric instants.
    """
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
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _age_seconds(started_at: Any, now: Any) -> int | None:
    """Return a non-negative, whole-second age, or ``None`` when either instant is unknown."""
    started = _epoch(started_at)
    moment = _epoch(now)
    if started is None or moment is None:
        return None
    return max(0, int(moment - started))


def _age_label(age_seconds: int | None) -> str:
    """Render the service-owned age token used by both the board and the drawer."""
    if age_seconds is None:
        return "age unknown"
    if age_seconds < 60:
        return f"{age_seconds}s ago"
    if age_seconds < 3600:
        return f"{age_seconds // 60}m ago"
    if age_seconds < 86400:
        return f"{age_seconds // 3600}h ago"
    return f"{age_seconds // 86400}d ago"


def operator_state_for_run(
    state: str,
    *,
    heartbeat_age_seconds: int | None = None,
    stale_after_seconds: int = 600,
) -> tuple[str, str]:
    """Map a reachable :class:`RunState` to a truthful operator screen.

    ``stalled`` is emitted only with positive heartbeat-age evidence.  ``escalated`` is not in
    the mapping because the current ``StepAttemptRecord`` has no escalation fields; omitting an
    unsupported screen is safer than presenting a manufactured escalation.  Terminal states such
    as ``cancelled`` and ``quarantined`` remain visible through the raw lifecycle value and use
    ``unknown`` as their operator screen because they are audit states, not one of the six named
    resting screens in the accepted research contract.
    """
    if (
        state == RunState.RUNNING.value
        and heartbeat_age_seconds is not None
        and heartbeat_age_seconds > stale_after_seconds
    ):
        return (
            "stalled",
            f"heartbeat age {heartbeat_age_seconds}s exceeds {stale_after_seconds}s",
        )
    mapping = {
        RunState.RUNNING.value: "running",
        RunState.VERIFYING.value: "running",
        RunState.PROMOTING.value: "running",
        RunState.PROJECTING.value: "running",
        RunState.AWAITING_APPROVAL.value: "blocked",
        RunState.FAILED.value: "failed",
        RunState.PROMOTABLE.value: "done",
        RunState.MERGED.value: "done",
        RunState.PUBLISHED.value: "done",
    }
    screen = mapping.get(state, "unknown")
    if screen == "done" and state == RunState.PROMOTABLE.value:
        return screen, "promotable; permanence decision is still owed"
    if screen == "unknown":
        return screen, f"lifecycle state {state!r} has no named operator screen"
    return screen, ""


def project_run_rows(
    entries: list[Mapping[str, Any]],
    attention: list[Mapping[str, Any]],
    *,
    now: Any,
    heartbeat_ages: Mapping[str, int | None] | None = None,
    stale_after_seconds: int = 600,
) -> list[dict[str, Any]]:
    """Build the canonical Operations roster from server-side inputs.

    The function is deliberately pure.  The real service supplies rows from ``ControlDB`` and
    heartbeat evidence; the browser-free render gate supplies deterministic fixture rows through
    this same function.  That arrangement prevents a hand-authored fixture twin from silently
    disagreeing with the live read model.
    """
    attention_by_run: dict[str, Mapping[str, Any]] = {}
    for item in attention:
        run_id = str(item.get("run_id") or "")
        if run_id and run_id not in attention_by_run:
            attention_by_run[run_id] = item

    projected: list[dict[str, Any]] = []
    for entry in entries:
        row = dict(entry)
        run_id = str(row.get("run_id") or "")
        state = str(row.get("state") or "unknown")
        age = _age_seconds(row.get("started_at"), now)
        heartbeat_age = (heartbeat_ages or {}).get(run_id)
        screen, screen_reason = operator_state_for_run(
            state,
            heartbeat_age_seconds=heartbeat_age,
            stale_after_seconds=stale_after_seconds,
        )
        attention_entry = attention_by_run.get(run_id)
        row["age_seconds"] = age
        row["started_age"] = _age_label(age)
        row["attention"] = {
            "state": "active" if attention_entry else "none",
            "kind": str((attention_entry or {}).get("kind") or ""),
            "reason": str(
                (attention_entry or {}).get("purpose")
                or (attention_entry or {}).get("reason")
                or ""
            ),
        }
        row["state_screen"] = {
            "run_id": run_id,
            "screen": screen,
            "lifecycle_state": state,
            "reason": screen_reason,
            "started_age": row["started_age"],
        }
        projected.append(row)
    return projected


def _record_run_ref(run: Any) -> dict[str, Any]:
    """Create the packet-shaped identity block for a run absent from a packet subset."""
    return {
        "run_id": run.run_id,
        "spec_name": run.spec_name,
        "state": run.state.value,
        "candidate_sha": run.candidate_sha,
        "model": run.model,
        "started_at": run.started_at,
    }


def _all_run_entries(
    db: Any, packet: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int | None]]:
    """Read every lifecycle state once and attach run-heartbeat evidence for stalled screens."""
    packet_entries = [
        *packet.get("active_runs", []),
        *packet.get("promotable_runs", []),
        *packet.get("failed_runs", []),
    ]
    by_id = {str(row.get("run_id")): dict(row) for row in packet_entries}
    now = packet.get("_projection_now")
    rows: list[dict[str, Any]] = []
    heartbeat_ages: dict[str, int | None] = {}
    for run in db.runs():
        row = by_id.get(run.run_id, _record_run_ref(run))
        rows.append(row)
        heartbeat = db.run_heartbeat(run.run_id)
        heartbeat_ages[run.run_id] = (
            _age_seconds(heartbeat.last_seen_at, now) if heartbeat is not None else None
        )
    return rows, heartbeat_ages


def _worker_health(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Name the worker read state instead of turning an unavailable source into ``0``."""
    degraded = packet.get("degraded", [])
    worker_note = next((row for row in degraded if row.get("surface") == "unhealthy_workers"), None)
    if worker_note is not None:
        return {
            "state": "unavailable",
            "count": None,
            "value": "unavailable",
            "reason": str(worker_note.get("reason") or "workers were not observed"),
        }
    unhealthy = list(packet.get("unhealthy_workers", []))
    return {
        "state": "recorded",
        "count": len(unhealthy),
        "value": str(len(unhealthy)),
        "reason": "observed worker heartbeats",
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


def operational_snapshot(
    db: Any,
    *,
    repo_head_sha: str,
    heartbeats: Mapping[str, Mapping[str, Any]] | None,
    now: Any | None = None,
) -> dict[str, Any]:
    """The room's operational view: packet parity plus server-owned presentation projections.

    ``attention`` is the decisions-owed view: every awaiting approval (with the purpose the
    operator owes) and every failed run, carrying the packet's own identifiers. It is a
    projection of the packet, not a second source of truth — the parity test asserts the
    identifiers match block-for-block.  The additive ``runs`` roster is read from the same
    control database snapshot so terminal states such as ``cancelled`` and ``quarantined`` do not
    disappear merely because the compact packet has no dedicated block for them.
    """
    # ``build_packet`` expects numeric seconds when it has heartbeat input.  The public service
    # boundary also accepts the ISO string used by the database/tests, so normalize once here and
    # use the same instant for worker health, run ages, and stalled-run evidence.
    projection_now = _epoch(now)
    if projection_now is None:
        projection_now = time.time()
    packet = build_packet(
        db,
        repo_head_sha=repo_head_sha,
        heartbeats=heartbeats,
        now=projection_now,
    )

    attention: list[dict[str, Any]] = []
    for entry in packet.get("awaiting_approvals", []):
        # pass-through with a discriminator: the packet's fields are carried verbatim.
        attention.append({"kind": "approval", **dict(entry)})
    for entry in packet.get("failed_runs", []):
        attention.append({"kind": "failed", **dict(entry)})

    entries, heartbeat_ages = _all_run_entries(
        db,
        {**packet, "_projection_now": projection_now},
    )
    runs = project_run_rows(
        entries,
        attention,
        now=projection_now,
        heartbeat_ages=heartbeat_ages,
        stale_after_seconds=stale_after_s(),
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
        "active_runs": list(packet.get("active_runs", [])),
        "promotable_runs": list(packet.get("promotable_runs", [])),
        "failed_runs": list(packet.get("failed_runs", [])),
        # Additive, totally ordered state roster.  ``state_screens`` is intentionally parallel
        # to ``runs``; the fixture/gate checks the identity and order rather than accepting two
        # independently authored lists.
        "runs": runs,
        "state_screens": [dict(row["state_screen"]) for row in runs],
        "unhealthy_workers": list(packet.get("unhealthy_workers", [])),
        "worker_health": _worker_health(packet),
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
    # The drawer receives the same server-owned age/state vocabulary as the board.  It is an
    # additive block so the raw ``run`` record remains an exact control-db reading.
    heartbeat = db.run_heartbeat(run_id)
    now = time.time()
    view = project_run_rows(
        [detail["run"]],
        [],
        now=now,
        heartbeat_ages={
            run_id: _age_seconds(heartbeat.last_seen_at, now) if heartbeat is not None else None
        },
        stale_after_seconds=stale_after_s(),
    )
    detail["run_view"] = view[0]
    return detail
