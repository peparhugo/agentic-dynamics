"""The glance projection + event stream (facelift a0 — the one resting screen).

The Control Room's resting screen is no longer a set of destination boards; it is ONE run
ledger that answers the seven operator glance needs (``ON-G1..G7``) at once. That screen
consumes a single read-only projection — ``GET /api/glance`` — whose schema is fixed by
``docs/research/control_room_ia.md`` §10.6 so the Playwright render gate can be deterministic
against committed fixtures.

Two additive, read-only routes live here:

``GET /api/glance``
    The projection: ``control_epoch``, ``source``, ``observed_at``, plus the ``system``,
    ``trust``, ``attention``, ``run_counts``, ``run_sample``, ``cost``, ``health_detail`` and
    ``composition`` blocks. Every block is derived from existing authoritative sources — the
    control packet (``control-status/v1``), the projection watermarks, the fleet worker
    heartbeats, and the subscription-usage snapshot — never from a new persistence plane.
    A value that could not be read is rendered as ``unknown`` (and counted), never as a
    reassuring zero: the same null-not-zero discipline the control plane already enforces.

``GET /api/events``
    A bounded Server-Sent Events stream for the resting screen: an initial ``snapshot`` frame
    (the whole glance payload), a ``replay_complete`` boundary, then ``transition`` frames when
    the durable ``control_epoch`` moves OR the worker/projection health changes at the same
    epoch (a health change is not a run-state move and must not wait for one). The frame
    vocabulary mirrors the render gate's committed SSE contract exactly (``event: snapshot`` /
    ``event: replay_complete`` / ``event: transition``), so the same client code runs under
    fixtures and in production.

The routes are additive on purpose: every pre-existing route on ``apps/control_room/routes``
keeps working and keeps its shape. This module only *reads*; it registers no mutation.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from flask import Response, jsonify, stream_with_context

# The service owns the shared per-run projection so the glance row and the Operations drawer give
# the SAME answer for the same run.  This route only chooses which packet rows to select.
from apps.control_room.services import operations as ops

if TYPE_CHECKING:  # pragma: no cover - import only for static typing
    from flask import Flask

    from apps.control_room.services.context import ControlRoomServices

#: Worst-case wall-clock the SSE stream stays open before it closes and the client reconnects.
#: Bounded on purpose: a resting screen polls the current epoch; it is not a forever socket.
_SSE_MAX_SECONDS = 300

#: How often the stream re-reads the durable control epoch looking for a transition.
_SSE_POLL_SECONDS = 2.0


def _utc_now() -> str:
    """Canonical UTC timestamp for the projection envelope (matches the server convention)."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _unknown_field(age: int = 0) -> dict[str, Any]:
    """A system dimension that could not be observed: ``unknown`` state, explicit age."""
    return {"state": "unknown", "age_seconds": age}


def _read_control_state() -> tuple[dict[str, Any] | None, dict[str, dict[str, Any]]]:
    """Read the packet AND the per-run detail records it references, or ``(None, {})``.

    ``build_packet`` is a pure function of its inputs; the impure collection (git HEAD, worker
    heartbeats) happens here and its failures are passed through as ``degraded`` notes rather
    than raised. A missing control database is a *missing control plane* — distinct from an
    empty one — so it becomes ``None`` and the caller renders ``unknown``/``down`` for the
    control dimension instead of pretending there are no runs.

    The run details are composed from the SAME existing read service the Operations lens uses
    (``services.operations.run_detail``): attempts, gates, approvals and the command journal.
    They are read here, on the same read-only handle and in the same pass as the packet, because
    the glance row must never re-infer an attempt number, a receipt or a workspace binding that
    the control records already answer (or answer "nothing recorded").
    """
    from agentic_dynamics.control import control_status
    from agentic_dynamics.control.control_db import ControlDB, ControlDBError
    from apps.control_room.services import operations as ops

    try:
        head_sha, head_error = control_status.read_repo_head_sha()
    except Exception:  # noqa: BLE001 — a collector failure is a note, never a 500
        head_sha, head_error = "", "git_unavailable"
    try:
        heartbeats, heartbeat_error = control_status.read_worker_heartbeats()
    except Exception:  # noqa: BLE001
        heartbeats, heartbeat_error = {}, "redis_unavailable"

    degraded: list[dict[str, str]] = []
    if head_error:
        degraded.append({"surface": "repo_head_sha", "reason": str(head_error)})
    if heartbeat_error:
        degraded.append({"surface": "unhealthy_workers", "reason": str(heartbeat_error)})
    try:
        with ControlDB.open_read_only() as db:
            packet = control_status.build_packet(
                db, repo_head_sha=head_sha, heartbeats=heartbeats, degraded=degraded
            )
            details: dict[str, dict[str, Any]] = {}
            refs = (
                list(packet.get("active_runs", []))
                + list(packet.get("promotable_runs", []))
                + list(packet.get("failed_runs", []))
            )
            for ref in refs:
                run_id = str(ref.get("run_id") or "")
                if not run_id or run_id in details:
                    continue
                try:
                    detail = ops.run_detail(db, run_id)
                except Exception:  # noqa: BLE001 — one bad run never blanks the whole roster
                    detail = None
                if detail is not None:
                    details[run_id] = detail
            return packet, details
    except ControlDBError:
        return None, {}
    except Exception:  # noqa: BLE001 — any read failure degrades the projection, never crashes it
        return None, {}


def _projection_report() -> list[dict[str, Any]] | None:
    """Read the per-projection watermarks, or ``None`` when there is no control database."""
    from agentic_dynamics.control import projection_watermarks as pwm

    try:
        return pwm.read_report()
    except Exception:  # noqa: BLE001
        return None


def _worker_health(packet: dict[str, Any] | None) -> dict[str, Any]:
    """The `workers` system dimension + the matching `R3b` detail string.

    ``read_worker_heartbeats``'s empty dict means "observed, nobody registered" only when the
    matching ``degraded`` note is absent; a note naming ``unhealthy_workers`` means nobody could
    look, so the state is ``unknown`` rather than ``up``.
    """
    if packet is None:
        return {"state": "unknown", "age_seconds": 0, "detail": "control plane unavailable"}
    notes = {str(n.get("surface")) for n in packet.get("degraded", [])}
    observed = "unhealthy_workers" not in notes
    unhealthy = packet.get("unhealthy_workers", [])
    if not observed:
        return {"state": "unknown", "age_seconds": 0, "detail": "workers not observed"}
    if unhealthy:
        return {
            "state": "degraded",
            "age_seconds": 0,
            "detail": f"{len(unhealthy)} unhealthy",
        }
    return {"state": "up", "age_seconds": 0, "detail": "0 unhealthy"}


def _projection_health(
    report: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """The `projections` system dimension + the aggregate `R3b` detail string.

    The projection with the worst health dominates the system verdict: a single ``stale``
    projector makes the projection dimension ``degraded`` even when the other three are current,
    because the screen must not imply a uniform green over a partially-stale plane.
    """
    if report is None:
        return {"state": "unknown", "age_seconds": 0, "detail": "no projection report"}
    if not report:
        return {"state": "unknown", "age_seconds": 0, "detail": "no projections reported"}
    severity = {"current": 0, "lagging": 1, "stale": 2, "failing": 3, "unknown": 4}
    worst = max(report, key=lambda row: severity.get(str(row.get("health")), 4))
    state = str(worst.get("health") or "unknown")
    lag = worst.get("lag_events")
    age = int(worst.get("age_seconds") or 0)
    lag_text = "lag unknown" if lag is None else f"lag {lag}"
    return {
        "state": "up" if state == "current" else ("degraded" if state in {"lagging"} else "down"),
        "age_seconds": age,
        "detail": f"{state} · {lag_text} · age {age}s",
        "raw_state": state,
        "lag": lag,
    }


def _system_block(
    packet: dict[str, Any] | None, projections: dict[str, Any], workers: dict[str, Any]
) -> dict[str, Any]:
    """Assemble the four independently-named `ON-G1` system dimensions."""
    return {
        "browser": {"state": "up", "age_seconds": 0},
        "control": (
            {"state": "up", "age_seconds": 0}
            if packet is not None
            else {"state": "down", "age_seconds": 0}
        ),
        "workers": {"state": workers["state"], "age_seconds": workers["age_seconds"]},
        "projections": {
            "state": projections["state"],
            "age_seconds": projections["age_seconds"],
        },
    }


def _trust_block(
    packet: dict[str, Any] | None,
    projections: dict[str, Any],
    system: dict[str, Any],
) -> dict[str, Any]:
    """The complete `ON-G6` trust verdict: epoch, worst age, and explicit partial counts.

    The four counts are derived from the projection report and the system dimensions — a
    ``stale``/``failing`` projector increments ``stale_count``; a dimension whose state is
    ``unknown`` increments ``unknown_count``; a ``degraded`` one increments ``degraded_count``.
    """
    epoch = int(packet.get("control_epoch", 0)) if packet else 0
    worst_age = max((int(v.get("age_seconds", 0)) for v in system.values()), default=0)
    degraded = sum(1 for v in system.values() if v.get("state") == "degraded")
    stale = 0
    partial = 0
    unknown = sum(1 for v in system.values() if v.get("state") == "unknown")
    if projections.get("raw_state") in {"stale", "failing"}:
        stale = 1
    if projections.get("raw_state") == "lagging":
        partial = 1
    return {
        "epoch": epoch,
        "worst_age": worst_age,
        "projection_state": str(projections.get("raw_state") or "unknown"),
        "degraded_count": degraded,
        "stale_count": stale,
        "partial_count": partial,
        "unknown_count": unknown,
    }


def _decision(packet: dict[str, Any] | None) -> dict[str, Any]:
    """The highest-priority pending decision, or an explicit ``none``/``unknown``.

    The queue is the packet's own ``awaiting_approvals`` then ``promotable_runs``; the
    eligibility token is the action the packet's DERIVED ``safe_actions`` already vouch for.
    A missing control plane yields ``unknown`` — "no pending decision" is an assertion an
    unread plane cannot support.
    """
    if packet is None:
        return {
            "state": "unknown",
            "target": "unknown",
            "kind": "unknown",
            "epoch": 0,
            "authority": "unknown",
            "eligibility": "unknown",
        }
    epoch = int(packet.get("control_epoch", 0))
    # The packet's `safe_actions` is the DERIVED authority for what may be done; the decision
    # object mirrors only its `approve` entries. The queue itself is `awaiting_approvals`.
    safe = {(str(a.get("action")), str(a.get("run_id"))) for a in packet.get("safe_actions", [])}
    for entry in packet.get("awaiting_approvals", []):
        run_id = str(entry.get("run_id", "none"))
        if ("approve", run_id) in safe or not safe:
            return {
                "state": "pending",
                "target": run_id,
                "kind": "approve",
                "epoch": epoch,
                "authority": "controller",
                "eligibility": "approve",
            }
    promotable = packet.get("promotable_runs", [])
    if promotable:
        return {
            "state": "pending",
            "target": str(promotable[0].get("run_id", "none")),
            "kind": "promote",
            "epoch": epoch,
            "authority": "controller",
            "eligibility": "promote",
        }
    return {
        "state": "none",
        "target": "none",
        "kind": "none",
        "epoch": epoch,
        "authority": "none",
        "eligibility": "none",
    }


def _risk(packet: dict[str, Any] | None) -> dict[str, Any]:
    """The highest-severity run failure/stall/risk, or an explicit ``all clear``/``unknown``.

    An unread control plane yields ``unknown``: the absence of a readable failure list is not
    evidence that there are no failures.
    """
    if packet is None:
        return {"identity": "unknown", "state": "unknown", "action": "unknown"}
    failed = packet.get("failed_runs", [])
    if failed:
        return {
            "identity": str(failed[0].get("run_id", "none")),
            "state": "active",
            "action": "inspect",
        }
    return {"identity": "none", "state": "all-clear", "action": "none"}


def _next_item(
    packet: dict[str, Any] | None, reports: list[dict[str, Any]], workers: dict[str, Any]
) -> dict[str, Any]:
    """The highest remaining item after the reserved decision/risk slots.

    Order: an unread control plane is a process gap; then an unhealthy worker; then a lagging or
    stale projector; then the first promotable run. An empty result is ``none``, never omitted.
    """
    if packet is None:
        return {"identity": "control-plane", "state": "active", "action": "inspect"}
    if workers.get("state") not in {"up", "unknown"}:
        return {"identity": "workers", "state": "active", "action": "inspect"}
    for row in reports:
        if str(row.get("health")) not in {"current"}:
            return {
                "identity": f"projection-{row.get('projection')}",
                "state": "active",
                "action": "inspect",
            }
    return {"identity": "none", "state": "clear", "action": "none"}


def _run_counts(packet: dict[str, Any] | None) -> dict[str, int | None]:
    """Exact running/queued/failed/live counts — the complete `ON-G2` answer, any fleet size.

    An unread control plane yields ``None`` per count (the wire's null-not-zero vocabulary):
    a fabricated zero is exactly the reassuring assertion a missing control plane cannot
    support. The client renders ``null`` as ``unknown``.
    """
    if packet is None:
        return {"running": None, "queued": None, "failed": None, "live": None}
    active = packet.get("active_runs", [])
    running = sum(1 for r in active if r.get("state") in {"running", "verifying", "projecting"})
    queued = sum(1 for r in active if r.get("state") == "queued")
    failed = len(packet.get("failed_runs", []))
    live = sum(1 for r in active if int(r.get("phases_completed", 0)) > 0)
    return {"running": running, "queued": queued, "failed": failed, "live": live}


def _cost_block(services: ControlRoomServices) -> dict[str, Any]:
    """The five `ON-G4` values from the subscription-usage snapshot, or explicit unknowns.

    The snapshot shape is provider-specific; this projection reads the well-known aggregate keys
    and renders any that are absent as ``unknown``. The rule that matters: an unknown cost is
    never drawn as ``$0.00``.
    """
    unknown = {
        "spend": "unknown",
        "burn": "unknown",
        "quota": "unknown",
        "wallet": "unknown",
        "leases": "unknown",
        "money_risk": False,
    }
    try:
        from apps.control_room.services.subscription_usage import load_or_refresh

        payload, _served_from, _age = load_or_refresh(services.redis, services.root)
    except Exception:  # noqa: BLE001 — an unreadable snapshot renders unknown, not zero
        return unknown
    if not isinstance(payload, dict):
        return unknown

    def _first_number(keys: tuple[str, ...]) -> float | None:
        for key in keys:
            for container in (payload, payload.get("aggregate", {}), payload.get("totals", {})):
                if isinstance(container, dict) and isinstance(container.get(key), (int, float)):
                    return float(container[key])
        return None

    spend = _first_number(("spend_usd", "total_spend_usd", "spend"))
    burn = _first_number(("burn_usd_per_hour", "burn_rate", "burn"))
    quota = _first_number(("quota_percent", "worst_window_percent", "quota"))
    wallet = _first_number(("wallet_usd", "wallet_balance_usd", "headroom_usd", "wallet"))
    leases = _first_number(("reserved_usd", "reserved_leases_usd", "leases"))
    if spend is None and burn is None and quota is None and wallet is None and leases is None:
        return unknown
    risk = bool(quota is not None and quota >= 90)
    return {
        "spend": "unknown" if spend is None else f"${spend:,.2f}",
        "burn": "unknown" if burn is None else f"${burn:,.2f}/h",
        "quota": "unknown" if quota is None else f"{quota:.0f}%",
        "wallet": "unknown" if wallet is None else f"${wallet:,.2f}",
        "leases": "unknown" if leases is None else f"${leases:,.2f}",
        "money_risk": risk,
    }


def _composition_block(packet: dict[str, Any] | None) -> dict[str, Any]:
    """Bounded `ON-G7` marginals: model × provider × lifecycle, each capped at 3 buckets.

    Condition is not carried by the control packet (it is a ledger factor), so it renders as an
    explicit ``unknown`` bucket rather than being omitted. Every marginal has exactly the three
    legal buckets ``top`` / ``other`` / ``unknown``; anything past the top bucket folds into
    ``other``.
    """
    from collections import Counter

    empty = {
        "model": {"top": "unknown 0", "other": "0", "unknown": "0"},
        "condition": {"top": "unknown 0", "other": "0", "unknown": "0"},
        "provider": {"top": "unknown 0", "other": "0", "unknown": "0"},
        "lifecycle": {"top": "unknown 0", "other": "0", "unknown": "0"},
    }
    if packet is None:
        return empty
    active = packet.get("active_runs", [])
    failed = packet.get("failed_runs", [])
    runs = list(active) + list(failed)
    if not runs:
        return empty

    def _marginal(values: list[str | None], labeler) -> dict[str, str]:
        present = [v for v in values if v]
        unknown = sum(1 for v in values if not v)
        counts = Counter(present)
        top = counts.most_common(1)
        if not top:
            return {"top": f"unknown {unknown}", "other": "0", "unknown": str(unknown)}
        top_value, top_count = top[0]
        other = sum(counts.values()) - top_count
        return {
            "top": f"{labeler(top_value)} {top_count}",
            "other": str(other),
            "unknown": str(unknown),
        }

    models = [str(r.get("model") or "") for r in runs]
    providers = [m.split("/")[0] if m else "" for m in models]
    lifecycles = [str(r.get("state") or "") for r in runs]
    return {
        "model": _marginal(models, lambda v: str(v).split("/")[-1]),
        "condition": _marginal(["" for _ in runs], lambda v: str(v)),
        "provider": _marginal(providers, lambda v: str(v)),
        "lifecycle": _marginal(lifecycles, lambda v: str(v)),
    }


def build_glance(services: ControlRoomServices) -> dict[str, Any]:
    """Render the whole glance projection from the authoritative read-only sources.

    Pure with respect to the caller: it only reads the control database, the run ledgers it
    points at, Redis, and the usage snapshot, and it never mutates or creates any of them. A
    missing control plane is rendered honestly (``control: down``, counts and decisions
    ``unknown``, epoch 0) rather than raising or asserting a reassuring all-clear.
    """
    packet, details = _read_control_state()
    reports = _projection_report()
    workers = _worker_health(packet)
    projections = _projection_health(reports)
    system = _system_block(packet, projections, workers)
    trust = _trust_block(packet, projections, system)
    epoch = trust["epoch"]
    observed_at = _utc_now()
    attention = {
        str(entry.get("run_id")): entry
        for entry in ops.attention_projection(packet or {}, now=observed_at)
        if entry.get("run_id")
    }

    def _rows(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            ops.run_row(
                run,
                epoch=epoch,
                detail=details.get(str(run.get("run_id") or "")),
                attention_entry=attention.get(str(run.get("run_id") or "")),
                now=observed_at,
            )
            for run in runs
        ]

    sample = _rows(list((packet or {}).get("active_runs", [])))
    sample += _rows(list((packet or {}).get("promotable_runs", [])))
    # Failed runs are part of the roster too, ranked after the active ones.
    sample += _rows(list((packet or {}).get("failed_runs", [])))
    cost = _cost_block(services)
    return {
        "control_epoch": epoch,
        "source": "control_room:/api/glance",
        "observed_at": observed_at,
        "system": system,
        "trust": trust,
        "attention": {
            "decision": _decision(packet),
            "risk": _risk(packet),
            "next": _next_item(packet, reports or [], workers),
            "items": [],
        },
        "run_counts": _run_counts(packet),
        "run_sample": sample,
        "cost": cost,
        "health_detail": {
            "workers": str(workers.get("detail", "unknown")),
            "projections": str(projections.get("detail", "unknown")),
        },
        "composition": _composition_block(packet),
    }


def _sse_frame(event: str, payload: dict[str, Any]) -> str:
    """One Server-Sent Event frame in the committed wire shape (blank-line terminated)."""
    return f"event: {event}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


def _health_signature(payload: dict[str, Any]) -> str:
    """The health VERDICT slice of a glance payload (states + worker detail, never clock ages).

    Health moves independently of the durable ``control_epoch``: a worker heartbeat ages out, a
    projector goes stale, a pure supervisor probe flips a worker from up to degraded — none of
    those is a run-state transition, so an epoch-only trigger leaves the resting screen showing
    old health until the next unrelated state move. This signature is compared in addition to
    the epoch and the whole payload is re-emitted on either change.

    Deliberately excludes the wall-clock ``age_seconds`` values every ``build_glance`` call
    recomputes: including them would make the signature differ on every poll and turn the
    stream into a frame-per-poll storm. Only the states (and the worker count detail, which has
    no clock component) decide whether an update is owed.
    """
    system = payload.get("system") or {}
    slice_ = {
        "states": {name: (dimension or {}).get("state") for name, dimension in system.items()},
        "projection_state": (payload.get("trust") or {}).get("projection_state"),
        "workers_detail": (payload.get("health_detail") or {}).get("workers"),
    }
    return json.dumps(slice_, sort_keys=True, default=str)


def _event_stream(services: ControlRoomServices) -> Iterator[str]:
    """Yield the snapshot, the replay boundary, then change frames until the cap.

    The generator is intentionally small and stateless across reconnects: the client treats the
    first ``snapshot`` as the baseline and re-renders on each ``transition``. A frame is emitted
    when EITHER the durable epoch moves OR the health signature changes (the same-epoch worker/
    projection change the epoch alone cannot express); the whole glance payload is re-emitted
    inside the frame so the client never has to make a second request to resynchronise. The
    ``kind`` is a local reason token, additive to the committed frame vocabulary.
    """
    started = time.monotonic()
    payload = build_glance(services)
    epoch = int(payload.get("control_epoch", 0))
    health = _health_signature(payload)
    yield _sse_frame("snapshot", {"control_epoch": epoch, "glance": payload})
    yield _sse_frame("replay_complete", {"control_epoch": epoch})
    while time.monotonic() - started < _SSE_MAX_SECONDS:
        time.sleep(_SSE_POLL_SECONDS)
        fresh = build_glance(services)
        fresh_epoch = int(fresh.get("control_epoch", 0))
        fresh_health = _health_signature(fresh)
        if fresh_epoch != epoch or fresh_health != health:
            kind = "epoch" if fresh_epoch != epoch else "health"
            epoch = fresh_epoch
            health = fresh_health
            yield _sse_frame("transition", {"control_epoch": epoch, "kind": kind, "glance": fresh})


def register(app: Flask, services: ControlRoomServices) -> None:
    """Register ``GET /api/glance`` and ``GET /api/events`` on the Flask app."""

    def api_glance() -> Response:
        """The one resting-screen projection (read-only; never creates the control database)."""
        return jsonify(build_glance(services))

    def glance_events() -> Response:
        """Bounded SSE stream: snapshot → replay_complete → epoch transitions."""
        return Response(
            stream_with_context(_event_stream(services)),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    app.get("/api/glance")(api_glance)
    # `endpoint=` is explicit: the legacy per-cell stream already owns the `api_events`
    # endpoint name, and Flask refuses two views under one endpoint.
    app.get("/api/events", endpoint="api_glance_events")(glance_events)
