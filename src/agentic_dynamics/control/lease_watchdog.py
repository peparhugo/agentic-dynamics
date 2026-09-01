"""Lease watchdog — the observe-only expiry rail of the fail-closed admission layer.

Phase 4 of the ``admission_leases`` work order, second half (the ledger it writes into is
:mod:`agentic_dynamics.control.quarantine`). This module answers one question on a cadence:

    Which leases expired while their work was still running, and what does that imply about
    what that work produced?

It answers it and *stops there*. It kills nothing, retries nothing, resumes nothing, and steers
nothing — it extends the supervisor's flag-only rail
(``docs/architecture/current/supervisor_design.md``), and inherits its constraint verbatim. The
work order's own verification says so: "the flag is advisory (no automatic steering)."

Why an expiry rail exists at all
--------------------------------
Phase 1 made leases TTL'd, and :meth:`LeaseRegistry.expire_leases` reclaims the *headroom* of an
expired claim. That is enough for the budget arithmetic and not nearly enough for integrity:
reclaiming a claim does not stop the process that held it. A worker whose lease expired at 14:00
and that kept writing until 15:30 spent ninety minutes of unreserved compute, and everything it
wrote in that window is output the system never admitted. The registry's sweep silently makes
the books balance again. The watchdog's job is to make sure they balance *honestly*.

The two expiry classes are not treated alike
--------------------------------------------
This is the substantive judgement in the module, so it is stated plainly:

``CONCURRENCY`` expiry → **flag only.**
    A concurrency lease is a claim on a *slot*. Overrunning it means the fleet was briefly wider
    than its cap — a throughput problem, and by the measured coordination tax the expensive kind
    (β_tokens = 0.80 severe: fleet throughput scales as N^0.20, so an extra worker mostly buys
    contention). But it says nothing about whether the output is accounted-for. Quarantining on
    a slot overrun would mark clean, fully-paid-for work as contaminated, and a quarantine that
    fires on healthy work is one operators learn to ignore.

``BUDGET`` expiry → **flag AND quarantine.**
    A budget lease is a claim on *spend*. Work that outlives it has been spending against no
    reservation, so its cost is unverified by construction — the audit's definition of
    contaminated. Both output surfaces named on the admission record (``worktree_identity`` and
    ``result_namespace``) are marked, because a run writes code to one and data to the other and
    either alone is a half-quarantine that the other half silently reintroduces.

Both classes are *observed*; only one of them implies contamination. Keeping that distinction is
what makes the quarantine ledger worth reading.

Where the identity comes from
-----------------------------
The watchdog only ever sees :class:`~agentic_dynamics.control.lease_registry.Lease` objects, so
the quarantine handles must travel on the lease. ``AdmissionController.admit`` stamps
``worktree_identity`` and ``result_namespace`` into every lease's ``metadata`` for exactly this
reason (phase 2's ``AdmissionRequest`` docstring already promised "so phase 4 can quarantine by
identity"). A budget lease that arrives *without* them is itself reported — as an
``unattributable`` observation — rather than dropped: an expired budget lease we cannot attribute
to an output surface is a worse state than one we can, and it must not vanish because a field
was missing.

The watchdog window
-------------------
:data:`WATCHDOG_INTERVAL_S` (default 300s, ``FINOPS_LEASE_WATCHDOG_INTERVAL``) is the cadence,
and therefore the guarantee the work order asks to verify: *an expired lease produces a flag
within the watchdog window*. The bound is one interval, because the sweep is total — every scope
reachable from the registry index is walked on every pass, so no expired lease can be missed for
more than one cycle regardless of when it expired.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from agentic_dynamics.control.lease_registry import (
    AdmissionError,
    Lease,
    LeaseKind,
    LeaseRegistry,
)
from agentic_dynamics.control.quarantine import (
    QuarantineKind,
    QuarantineReason,
    QuarantineRecord,
    QuarantineRegistry,
)
from agentic_dynamics.control.supervisor import (
    SUPERVISOR_FLAGS_KEY,
    SUPERVISOR_FLAGS_MAX,
    canonical_json,
    normalize_flag,
)

# ── Cadence and vocabulary ───────────────────────────────────────────────────────────────────

#: Seconds between passes. Also the bound in "a flag appears within the watchdog window".
WATCHDOG_INTERVAL_S = int(os.environ.get("FINOPS_LEASE_WATCHDOG_INTERVAL", "300"))

#: The flag ``status`` values this rail emits. Distinct strings so the Control Room can filter
#: lease flags out of the session-supervision flags they share a list with.
FLAG_STATUS_CONCURRENCY = "lease_expired_concurrency"
FLAG_STATUS_BUDGET = "lease_expired_budget"

#: ``source`` recorded on every quarantine this module opens — the provenance an operator reads
#: to tell an automatic mark from an operator's manual one.
WATCHDOG_SOURCE = "lease_watchdog"

#: Metadata keys the admission controller stamps onto every lease; the quarantine handles.
WORKTREE_METADATA_KEY = "worktree_identity"
NAMESPACE_METADATA_KEY = "result_namespace"


def _iso(epoch: float) -> str:
    """Epoch seconds → ISO-8601 UTC ``Z`` form, matching ``supervisor.utc_now()``'s shape."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


# ── What one pass produces ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LeaseObservation:
    """One expired lease, as the watchdog saw it. Pure observation — no action implied."""

    lease_id: str
    kind: str
    scope: str
    run_id: str
    model: str
    provider_class: str
    amount: float
    unit: str
    expires_at: float
    #: How long the claim had been dead when the sweep found it. The operator's urgency signal,
    #: and the number that shows whether the watchdog is actually running on its cadence.
    overdue_seconds: float
    worktree_identity: str = ""
    result_namespace: str = ""

    @property
    def attributable(self) -> bool:
        """True when at least one quarantine handle travelled with the lease.

        An unattributable budget expiry is still reported; it just cannot be turned into a
        quarantine, because there is no identity to mark.
        """
        return bool(self.worktree_identity or self.result_namespace)

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe projection, with the derived ISO stamp humans read."""
        payload = asdict(self)
        payload["expires_at_iso"] = _iso(self.expires_at)
        payload["attributable"] = self.attributable
        return payload


@dataclass
class WatchdogResult:
    """Everything one pass observed and recorded — the return value and the report shape."""

    #: Every expired lease reclaimed by this pass.
    observations: list[LeaseObservation] = field(default_factory=list)
    #: Advisory supervisor flags emitted (one per observation).
    flags: list[dict[str, Any]] = field(default_factory=list)
    #: Quarantines newly opened. Shorter than ``observations`` by design: concurrency expiries
    #: never quarantine, and a re-observed contamination is idempotent (already open ⇒ no entry).
    quarantines: list[QuarantineRecord] = field(default_factory=list)
    #: Budget expiries carrying no identity — reported, un-quarantinable. See the module docstring.
    unattributable: list[LeaseObservation] = field(default_factory=list)
    #: Non-fatal problems (a Redis hiccup on the hot path, a scope that would not sweep). The
    #: pass continues past these: one bad scope must not cost the others their observation.
    errors: list[str] = field(default_factory=list)

    @property
    def steering_actions(self) -> int:
        """Always ``0``. Present so the advisory contract is *assertable*, not just documented.

        The observe-only rule is the kind of constraint that erodes quietly — someone adds "and
        also kill the process" in six months and no test notices. A counter that the tests pin
        to zero makes that edit visible.
        """
        return 0

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe projection — what ``--json`` prints and what the Control Room can render."""
        return {
            "observations": [o.to_dict() for o in self.observations],
            "flags": self.flags,
            "quarantines": [q.to_dict() for q in self.quarantines],
            "unattributable": [o.to_dict() for o in self.unattributable],
            "errors": self.errors,
            "steering_actions": self.steering_actions,
            "advisory": True,
        }


# ── Observation ──────────────────────────────────────────────────────────────────────────────


def observe(lease: Lease, *, now: float) -> LeaseObservation:
    """Project an expired :class:`Lease` into the watchdog's flat observation shape.

    Reads the quarantine handles out of ``lease.metadata`` defensively: a lease predating the
    controller's identity stamping (or one taken by a caller that bypassed the controller) has
    no handles, and that is a *reportable* state, not a crash and not a silent empty string
    masquerading as an identity.
    """
    metadata = lease.metadata or {}
    worktree = str(metadata.get(WORKTREE_METADATA_KEY) or "").strip()
    namespace = str(metadata.get(NAMESPACE_METADATA_KEY) or "").strip()
    return LeaseObservation(
        lease_id=lease.lease_id,
        kind=lease.kind.value,
        scope=lease.scope.token,
        run_id=lease.run_id,
        model=str(metadata.get("model") or ""),
        provider_class=lease.provider_class.value,
        amount=lease.amount,
        unit=lease.unit,
        expires_at=lease.expires_at,
        overdue_seconds=max(0.0, now - lease.expires_at),
        worktree_identity=worktree,
        result_namespace=namespace,
    )


def build_flag(observation: LeaseObservation) -> dict[str, Any]:
    """Build the advisory supervisor flag for one expired lease.

    Shaped to pass :func:`~agentic_dynamics.control.supervisor.normalize_flag` unchanged so it
    lands in the *same* ``supervisor_flags`` list the Control Room already renders — an operator
    should not need a second board to learn that a lease died. The mapping onto the flag's
    session-shaped fields:

    ``session_id``
        The ``run_id``. The flag vocabulary calls the subject a session; here the subject is an
        admitted unit of work, and the run id is its identity.
    ``title`` / ``model`` / ``status`` / ``why``
        The scope, the model, one of the two lease statuses, and a sentence an operator can act
        on without opening Redis.
    ``lease``
        The full observation, carried as the flag's additive metadata (``supervisor.FLAG_FIELDS``
        is the required core; ``lease`` is in the preserved-extras allowlist).
    """
    if observation.kind == LeaseKind.BUDGET.value:
        status = FLAG_STATUS_BUDGET
        consequence = (
            "work continued past its spend reservation — its output is a quarantine candidate"
        )
    else:
        status = FLAG_STATUS_CONCURRENCY
        consequence = "a worker outlived its execution slot — the fleet ran wider than its cap"

    flag = {
        "at": _iso(observation.expires_at + observation.overdue_seconds),
        "session_id": observation.run_id or f"lease:{observation.lease_id}",
        "title": f"lease {observation.lease_id} ({observation.scope})"[:80],
        "model": observation.model or "?",
        "status": status,
        "why": (
            f"{observation.kind} lease expired {observation.overdue_seconds:.0f}s ago "
            f"({observation.amount:g} {observation.unit} on {observation.scope}): {consequence}. "
            f"Advisory only — no action was taken."
        ),
        "lease": observation.to_dict(),
    }
    normalized = normalize_flag(flag)
    if normalized is None:  # pragma: no cover — defensive; the shape above is fixed
        raise ValueError(f"watchdog built a flag the supervisor rail rejects: {flag!r}")
    return normalized


def emit_flag(
    flag: dict[str, Any],
    *,
    redis_client: Any = None,
    flags_path: Any = None,
) -> None:
    """Persist one advisory flag: durable JSONL first, bounded Redis hot list second.

    The order and the best-effort Redis half mirror ``scripts/supervise.py:emit_flag`` and
    ``control.orphan_sweep.record_orphan`` exactly — a downed framework Redis must never cost an
    observation its durable record. ``flags_path`` is optional so a caller (the Control Room) can
    ask for the hot path alone.
    """
    payload = canonical_json(flag)
    if flags_path is not None:
        from pathlib import Path

        path = Path(flags_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    if redis_client is not None:
        try:
            redis_client.lpush(SUPERVISOR_FLAGS_KEY, payload)
            redis_client.ltrim(SUPERVISOR_FLAGS_KEY, 0, SUPERVISOR_FLAGS_MAX - 1)
        except Exception:  # noqa: BLE001 — the durable write already landed
            pass


# ── The one-pass driver ──────────────────────────────────────────────────────────────────────


def sweep_once(
    registry: LeaseRegistry,
    quarantine: QuarantineRegistry,
    *,
    redis_client: Any = None,
    flags_path: Any = None,
    now: float | None = None,
) -> WatchdogResult:
    """One full pass: sweep expired leases → flag every one → quarantine the budget expiries.

    Total over the registry index, so the "flag within one watchdog window" bound holds no matter
    when a lease died. Returns the pass's :class:`WatchdogResult`; raises nothing for a partial
    failure — a scope that will not sweep is recorded in ``errors`` and the rest of the pass
    proceeds, because a single unreachable scope silencing every other observation would be the
    worst possible failure mode for a watchdog.

    :param registry: the lease registry to sweep (its ``expire_leases`` reclaims the headroom).
    :param quarantine: the contamination ledger to open entries in.
    :param redis_client: framework Redis for the flags hot list; ``None`` ⇒ durable-only.
    :param flags_path: durable ``flags.jsonl``; ``None`` ⇒ hot-path-only.
    :param now: clock seam (epoch seconds) for deterministic tests.
    """
    result = WatchdogResult()
    moment = now if now is not None else datetime.now(timezone.utc).timestamp()

    # The sweep both reclaims and reports. If it fails wholesale there is nothing to observe --
    # record why and return an empty (not a fabricated-clean) pass.
    try:
        expired: Sequence[Lease] = registry.expire_leases()
    except AdmissionError as exc:
        result.errors.append(f"lease sweep failed, no expiries could be observed: {exc}")
        return result

    for lease in expired:
        observation = observe(lease, now=moment)
        result.observations.append(observation)

        # 1 — the flag. Every expiry gets one, both classes, always advisory.
        try:
            flag = build_flag(observation)
            emit_flag(flag, redis_client=redis_client, flags_path=flags_path)
            result.flags.append(flag)
        except (OSError, ValueError) as exc:
            result.errors.append(f"flag emission failed for lease {lease.lease_id}: {exc}")

        # 2 — the quarantine, for BUDGET expiries only (see the module docstring's split).
        if lease.kind is not LeaseKind.BUDGET:
            continue
        if not observation.attributable:
            result.unattributable.append(observation)
            result.errors.append(
                f"budget lease {lease.lease_id} (run {lease.run_id!r}) expired without a "
                f"{WORKTREE_METADATA_KEY}/{NAMESPACE_METADATA_KEY} — its output cannot be "
                f"quarantined by identity and must be reviewed by hand"
            )
            continue
        result.quarantines.extend(
            _quarantine_observation(observation, quarantine, errors=result.errors)
        )

    return result


def _quarantine_observation(
    observation: LeaseObservation,
    quarantine: QuarantineRegistry,
    *,
    errors: list[str],
) -> list[QuarantineRecord]:
    """Mark both output surfaces of one expired budget lease. Idempotent; never raises.

    Both surfaces, because a run writes code to the worktree and data to the results namespace;
    marking one and not the other leaves a path by which the contaminated half re-enters an
    aggregate. Failures are collected rather than raised so one unwritable ledger entry does not
    abort the remaining observations in the pass.
    """
    opened: list[QuarantineRecord] = []
    targets = (
        (QuarantineKind.WORKTREE, observation.worktree_identity),
        (QuarantineKind.RESULT_NAMESPACE, observation.result_namespace),
    )
    why = (
        f"budget lease {observation.lease_id} on {observation.scope} expired "
        f"{observation.overdue_seconds:.0f}s before this sweep while run "
        f"{observation.run_id!r} was still live: output produced after "
        f"{_iso(observation.expires_at)} is unaccounted-for."
    )
    for kind, identity in targets:
        if not identity:
            # The other surface was present, so the expiry is attributable and already marked;
            # a missing second handle is a gap in the record, not an unattributable expiry.
            continue
        try:
            record = quarantine.quarantine(
                kind,
                identity,
                reason=QuarantineReason.BUDGET_LEASE_EXPIRED,
                why=why,
                source=WATCHDOG_SOURCE,
                run_id=observation.run_id,
                lease_ids=(observation.lease_id,),
                metadata={
                    "scope": observation.scope,
                    "model": observation.model,
                    "provider_class": observation.provider_class,
                    "reserved_amount": observation.amount,
                    "unit": observation.unit,
                    "expires_at": observation.expires_at,
                    "overdue_seconds": observation.overdue_seconds,
                },
            )
        except Exception as exc:  # noqa: BLE001 — one failed mark must not end the pass
            errors.append(f"quarantine of {kind.value} {identity!r} failed: {exc}")
            continue
        if record is not None:
            opened.append(record)
    return opened


def format_report(result: WatchdogResult) -> str:
    """A one-screen human summary of a pass — what ``scripts/lease_watchdog.py`` prints."""
    if not result.observations and not result.errors:
        return "lease watchdog: no expired leases (advisory pass, nothing to report)"

    lines = [
        f"lease watchdog: {len(result.observations)} expired lease(s), "
        f"{len(result.flags)} flag(s), {len(result.quarantines)} new quarantine(s) "
        f"— ADVISORY, {result.steering_actions} steering actions taken"
    ]
    for observation in result.observations:
        lines.append(
            f"  [{observation.kind}] {observation.lease_id} run={observation.run_id or '?'} "
            f"scope={observation.scope} overdue={observation.overdue_seconds:.0f}s "
            f"wt={observation.worktree_identity or '—'} ns={observation.result_namespace or '—'}"
        )
    for record in result.quarantines:
        lines.append(f"  [QUARANTINE] {record.entry_id} — {record.reason.value}")
    for observation in result.unattributable:
        lines.append(
            f"  [UNATTRIBUTABLE] budget lease {observation.lease_id} — review by hand"
        )
    for error in result.errors:
        lines.append(f"  [error] {error}")
    return "\n".join(lines)


def report_json(result: WatchdogResult) -> str:
    """The machine-readable pass report (``--json``), stable-keyed for diffing across runs."""
    return json.dumps(result.to_dict(), sort_keys=True, indent=2)
