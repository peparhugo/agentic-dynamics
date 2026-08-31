"""Settlement — reconciling what a run *reserved* against what the provider actually charged.

Phase 3 of the ``admission_leases`` work order (``workflows/repository/admission_leases.yaml``)
closes the audit's item 5: *"reconcile estimated and metered cost after execution"*. A lease is
taken **before** a run, against a forecast; the provider's own meter only knows the truth
**after**. Without a settlement step the two numbers never meet, and the framework's dollar
figures stay forecasts forever — which is exactly how a $0.00 forecast became a $0.00 fact.

The shape of the reconciliation
-------------------------------
Both provider classes settle, but against different meters, because they are different kinds of
scarcity:

``PER_TOKEN`` (DeepSeek) — **dollars**
    Settled against the platform meter's per-day buckets
    (``deepseek_platform.days[].estimated_cost_usd`` in the usage ledger). The meter is the
    authoritative record of what the wallet was actually charged.

``SUBSCRIPTION`` (Anthropic / OpenAI) — **window percentage points**
    Settled against the rolling usage windows (``providers.<p>.windows[].used_percent``). There
    are no marginal dollars to reconcile inside a fixed-price plan; the scarce resource is the
    window, so that is what the settlement measures movement in.

What "matches" means, and why the tolerance is two-sided
--------------------------------------------------------
A settlement compares the reserved amount to the observed one and returns a
:class:`SettlementStatus`:

``MATCHED``    the observation is within tolerance of the reservation. The cost's provenance is
               upgraded to :attr:`CostSource.RECONCILED` — an estimate that the provider's own
               meter subsequently agreed with, which is the strongest claim the framework can
               make about a dollar figure short of a direct invoice line.
``OVERSPENT``  the run cost MORE than it reserved. The lease under-protected the wallet; this is
               the finding that resizes the next reservation, and phase 4 may quarantine on it.
``UNDERSPENT`` the run cost LESS than it reserved. Not an error — reserving too much only costs
               headroom — but it is recorded, because a chronically over-reserving scope
               throttles the fleet for no reason (the β coordination tax paid for nothing).
``UNSETTLED``  the meter had nothing to say (no ledger, no bucket for the day, provider absent).
               The reservation stands and the provenance is NOT upgraded. This is the honest
               "we still do not know" state and it is deliberately not an error either: a
               missing meter reading must never be settled as $0.

The tolerance is two-sided and relative-with-a-floor
(``max(abs_tolerance, rel_tolerance × reserved)``) so that a $0.01 reservation is not judged by
the same absolute yardstick as a $50 one, and so a reservation of exactly $0 still has a usable
band. Nothing here is a policy decision about what to *do* with an overspend — this module
reports; ``control.admission`` and phase 4's watcher act.

Purity
------
:func:`settle` and the extractors are pure functions of an already-loaded ledger dict, so they
are testable without Redis, without the network, and without a real usage snapshot.
:func:`load_usage_ledger` and :func:`record_settlement` are the only I/O, and both degrade to a
stated absence rather than raising.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from agentic_dynamics.core.cost_provenance import (
    METHOD_PLATFORM_METER_DAILY,
    METHOD_WINDOW_USAGE,
    CostObservation,
    CostSource,
    ProviderClass,
    provider_class_or_none,
)
from agentic_dynamics.core.paths import PROJECT_ROOT

# ── Where the meters live ────────────────────────────────────────────────────────────────────

#: The usage ledger written by ``scripts/subscription_usage.py`` (schema ``subscription-usage/v3``)
#: and refreshed through the Control Room's polite 15-minute cache. Settlement READS it and never
#: writes it — the fetcher owns that file.
USAGE_LEDGER_RELPATH = Path("experiments") / "results" / "usage" / "subscription_usage_latest.json"

#: Durable, append-only settlement records — one JSON line per settled run. Separate from the
#: usage ledger because that file is a *snapshot* (overwritten each fetch) while this is a
#: *history* (the audit trail of every reservation the framework has closed out).
SETTLEMENT_RELPATH = Path("experiments") / "results" / "settlement" / "settlements.jsonl"

#: Default match band: $0.01 absolute, or 10% of the reservation, whichever is larger. The
#: absolute floor exists because sub-cent differences are rounding in the meter's own
#: token→dollar arithmetic; the relative term exists because a fixed cent is meaningless at $50.
DEFAULT_ABS_TOLERANCE_USD = 0.01
DEFAULT_REL_TOLERANCE = 0.10

#: Window settlement is denominated in percentage points, so it gets its own floor: a window
#: reading is reported to whole/one-decimal percents and moves in coarse steps.
DEFAULT_ABS_TOLERANCE_PERCENT = 1.0


class SettlementStatus(str, Enum):
    """The outcome of comparing a reservation to the provider's meter."""

    #: Observed ≈ reserved. Provenance upgrades to ``RECONCILED``.
    MATCHED = "matched"
    #: Observed > reserved + tolerance. The lease under-protected the budget.
    OVERSPENT = "overspent"
    #: Observed < reserved − tolerance. Headroom was held and not used.
    UNDERSPENT = "underspent"
    #: The meter had nothing to say. NOT a zero; the reservation stands unreconciled.
    UNSETTLED = "unsettled"


@dataclass(frozen=True)
class Settlement:
    """One reservation, closed out against a meter.

    Frozen: a settlement is a record of a comparison at a moment. Re-settling later (after a
    fresher meter fetch) produces a *new* record, so the history shows how the picture changed.
    """

    run_id: str
    provider: str
    model: str
    #: What the lease reserved, in the provider class's unit (USD / window percentage points).
    reserved_amount: float
    #: What the meter says was actually consumed, or ``None`` when it had nothing to say.
    observed_amount: float | None
    #: ``observed − reserved``; ``None`` when unsettled. Positive = overspend.
    variance: float | None
    status: SettlementStatus
    #: The provenance the attempt should carry AFTER settlement. ``RECONCILED`` only on a
    #: match — a mismatch keeps the figure honest as ``METERED``/``ESTIMATED``, and an
    #: unsettled comparison leaves the original provenance untouched.
    cost_source: CostSource
    #: Which meter answered (a ``core.cost_provenance`` estimation method), or ``None``.
    estimation_method: str | None
    #: The unit ``reserved_amount``/``observed_amount`` are denominated in.
    unit: str
    #: Free-form provenance for the audit line: which day bucket, which window, why unsettled.
    detail: str = ""
    #: When the comparison was made (ISO-8601 UTC).
    settled_at: str = ""

    @property
    def is_reconciled(self) -> bool:
        """True when the meter agreed with the reservation."""
        return self.status is SettlementStatus.MATCHED

    @property
    def settled_cost_usd(self) -> float | None:
        """The settled figure in DOLLARS, or ``None`` for a window/unsettled settlement.

        A subscription settlement is denominated in window percentage points, and turning
        those into dollars would be an invention — the ledger field stays ``None`` rather than
        carrying a fabricated amount.
        """
        if self.unit != "usd":
            return None
        return self.observed_amount

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe projection — the durable settlement line."""
        return {
            "run_id": self.run_id,
            "provider": self.provider,
            "model": self.model,
            "reserved_amount": self.reserved_amount,
            "observed_amount": self.observed_amount,
            "variance": self.variance,
            "status": self.status.value,
            "cost_source": self.cost_source.value,
            "estimation_method": self.estimation_method,
            "unit": self.unit,
            "detail": self.detail,
            "settled_at": self.settled_at,
            # The two ledger fields (``LEDGER_FIELDS``) an attempt record carries after
            # settlement, projected here so the ingestion path does not have to re-derive them.
            "settled_cost_usd": self.settled_cost_usd,
            "settlement_status": self.status.value,
        }

    def apply_to(self, observation: CostObservation) -> CostObservation:
        """Return the post-settlement cost observation for an attempt.

        On a match the figure becomes the meter's own and the provenance becomes
        ``RECONCILED``. Otherwise the original observation is returned untouched — settlement
        never silently overwrites a run's own measurement with a day-level aggregate.
        """
        if not self.is_reconciled or self.settled_cost_usd is None:
            return observation
        return CostObservation(
            cost_usd=self.settled_cost_usd,
            source=CostSource.RECONCILED,
            estimation_method=self.estimation_method,
            reported_cost_usd=observation.reported_cost_usd,
        )


# ── Loading the meter ────────────────────────────────────────────────────────────────────────


def load_usage_ledger(root: Path | None = None) -> dict[str, Any] | None:
    """Read the usage-ledger snapshot, or ``None`` when it is absent/unreadable.

    Never raises and never fetches: settlement is a *post-run* step that must not add a network
    call (or a failure mode) to the run's critical path. A missing ledger yields ``UNSETTLED``,
    which is the honest outcome — the alternative, treating "no meter" as "$0 spent", is the
    exact bug this work order exists to remove.
    """
    base = root if root is not None else PROJECT_ROOT
    path = Path(base) / USAGE_LEDGER_RELPATH
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def platform_day_cost_usd(ledger: dict[str, Any] | None, date: str) -> float | None:
    """The DeepSeek platform meter's charge for one UTC calendar day, or ``None``.

    Reads ``deepseek_platform.days[]`` — the authoritative per-(key, model) token buckets the
    meter reports, priced by ``scripts/subscription_usage.py``. Returns ``None`` (not ``0.0``)
    when the block is absent, unhealthy, or has no bucket for ``date``: a day the meter has not
    reported on is unknown, not free.
    """
    if not isinstance(ledger, dict):
        return None
    block = ledger.get("deepseek_platform")
    if not isinstance(block, dict) or not block.get("ok"):
        return None
    for day in block.get("days") or []:
        if isinstance(day, dict) and day.get("date") == date:
            value = day.get("estimated_cost_usd")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
            return None
    return None


def window_used_percent(
    ledger: dict[str, Any] | None, provider: str, *, window: str = ""
) -> float | None:
    """A subscription provider's window utilisation in percentage points, or ``None``.

    With no ``window`` name the MAXIMUM utilisation across the provider's windows is returned:
    a subscription run is constrained by whichever window is closest to its limit (the 5-hour
    window binds long before the 7-day one), so the max is the figure a reservation is really
    competing for.
    """
    if not isinstance(ledger, dict):
        return None
    providers = ledger.get("providers")
    if not isinstance(providers, dict):
        return None
    block = providers.get(provider)
    if not isinstance(block, dict) or not block.get("ok"):
        return None
    values: list[float] = []
    for entry in block.get("windows") or []:
        if not isinstance(entry, dict):
            continue
        if window and entry.get("name") != window:
            continue
        used = entry.get("used_percent")
        if isinstance(used, (int, float)) and not isinstance(used, bool):
            values.append(float(used))
    return max(values) if values else None


# ── The comparison ───────────────────────────────────────────────────────────────────────────


def classify_variance(
    reserved: float,
    observed: float,
    *,
    abs_tolerance: float,
    rel_tolerance: float = DEFAULT_REL_TOLERANCE,
) -> SettlementStatus:
    """Compare an observation to a reservation within a relative-with-a-floor band.

    The band is ``max(abs_tolerance, rel_tolerance × |reserved|)``: the floor keeps a tiny (or
    zero) reservation from being judged by a band of zero, and the relative term keeps a large
    reservation from being failed by rounding.
    """
    band = max(abs(abs_tolerance), abs(rel_tolerance) * abs(reserved))
    delta = observed - reserved
    if abs(delta) <= band:
        return SettlementStatus.MATCHED
    return SettlementStatus.OVERSPENT if delta > 0 else SettlementStatus.UNDERSPENT


def settle(
    *,
    run_id: str,
    model: str,
    reserved_amount: float,
    ledger: dict[str, Any] | None,
    date: str = "",
    now: datetime | None = None,
    abs_tolerance_usd: float = DEFAULT_ABS_TOLERANCE_USD,
    abs_tolerance_percent: float = DEFAULT_ABS_TOLERANCE_PERCENT,
    rel_tolerance: float = DEFAULT_REL_TOLERANCE,
) -> Settlement:
    """Settle one run's reservation against the appropriate meter. Pure.

    Args:
        run_id: The admitted unit's id (the join key to its leases and ledger records).
        model: ``provider/model`` — selects the provider class, hence which meter answers.
        reserved_amount: What the budget lease claimed, in that class's unit.
        ledger: An already-loaded usage-ledger dict (see :func:`load_usage_ledger`), or ``None``.
        date: UTC calendar day (``YYYY-MM-DD``) for the per-token day bucket. Defaults to
            ``now``'s date.
        now: Injectable clock, so the settlement timestamp is deterministic under test.

    Returns a :class:`Settlement` in every case — including ``UNSETTLED``. Settlement never
    raises: it is a post-run bookkeeping step, and a bookkeeping failure must not be able to
    fail a run that has already completed.
    """
    moment = now or datetime.now(timezone.utc)
    settled_at = moment.isoformat()
    day = date or moment.strftime("%Y-%m-%d")
    provider = model.split("/", 1)[0] if "/" in model else model
    provider_class = provider_class_or_none(provider)

    def unsettled(unit: str, detail: str) -> Settlement:
        """An honest non-answer: the reservation stands, provenance is NOT upgraded."""
        return Settlement(
            run_id=run_id, provider=provider, model=model,
            reserved_amount=reserved_amount, observed_amount=None, variance=None,
            status=SettlementStatus.UNSETTLED, cost_source=CostSource.UNKNOWN,
            estimation_method=None, unit=unit, detail=detail, settled_at=settled_at,
        )

    if provider_class is ProviderClass.SUBSCRIPTION:
        observed = window_used_percent(ledger, provider)
        if observed is None:
            return unsettled(
                "window_percent",
                f"no usage window reported for subscription provider {provider!r}",
            )
        status = classify_variance(
            reserved_amount, observed,
            abs_tolerance=abs_tolerance_percent, rel_tolerance=rel_tolerance,
        )
        return Settlement(
            run_id=run_id, provider=provider, model=model,
            reserved_amount=reserved_amount, observed_amount=observed,
            variance=observed - reserved_amount, status=status,
            # A matched window settlement is RECONCILED; a mismatch stays METERED — the window
            # reading is the provider's own number either way, it simply did not agree.
            cost_source=(
                CostSource.RECONCILED if status is SettlementStatus.MATCHED
                else CostSource.METERED
            ),
            estimation_method=METHOD_WINDOW_USAGE,
            unit="window_percent",
            detail=f"max window utilisation for {provider} at {settled_at}",
            settled_at=settled_at,
        )

    if provider_class is ProviderClass.PER_TOKEN:
        observed = platform_day_cost_usd(ledger, day)
        if observed is None:
            return unsettled(
                "usd", f"platform meter has no bucket for {day} (or the block is unhealthy)"
            )
        status = classify_variance(
            reserved_amount, observed,
            abs_tolerance=abs_tolerance_usd, rel_tolerance=rel_tolerance,
        )
        return Settlement(
            run_id=run_id, provider=provider, model=model,
            reserved_amount=reserved_amount, observed_amount=observed,
            variance=observed - reserved_amount, status=status,
            cost_source=(
                CostSource.RECONCILED if status is SettlementStatus.MATCHED
                else CostSource.METERED
            ),
            estimation_method=METHOD_PLATFORM_METER_DAILY,
            unit="usd",
            detail=f"deepseek platform meter day bucket {day}",
            settled_at=settled_at,
        )

    # Unclassified provider: no meter is known to answer for it. Fail-closed by silence —
    # UNSETTLED, never a $0 settlement that would read as "this run was free".
    return unsettled("usd", f"provider {provider!r} has no declared cost class or meter")


# ── The durable record ───────────────────────────────────────────────────────────────────────


def record_settlement(settlement: Settlement, *, root: Path | None = None) -> Path | None:
    """Append a settlement to the durable JSONL, returning the path (or ``None`` on failure).

    Best-effort by design: the run has already finished and its output already exists, so a
    write failure here must not raise into a completed run's teardown. A ``None`` return is the
    caller's signal that the audit line was not persisted.
    """
    base = root if root is not None else PROJECT_ROOT
    path = Path(base) / SETTLEMENT_RELPATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as handle:
            handle.write(json.dumps(settlement.to_dict(), sort_keys=True) + "\n")
        return path
    except OSError:
        return None


def settle_run(
    *,
    run_id: str,
    model: str,
    reserved_amount: float,
    date: str = "",
    root: Path | None = None,
    persist: bool = True,
    now: datetime | None = None,
) -> Settlement:
    """Load the meter, settle, and (by default) append the audit line. The wired entry point.

    This is what a post-run hook calls: one function that never raises and always returns a
    :class:`Settlement`, so a caller's teardown is a single unconditional line.
    """
    settlement = settle(
        run_id=run_id, model=model, reserved_amount=reserved_amount,
        ledger=load_usage_ledger(root), date=date, now=now,
    )
    if persist:
        record_settlement(settlement, root=root)
    return settlement


#: Opt-in switch for the automatic post-run settlement hook, following the repo's ``FINOPS_*``
#: convention (``FINOPS_KB_WRITE``, ``FINOPS_ACTUATION_ARMED``, ``FINOPS_ADMISSION_REQUIRED``).
#: OFF by default: settlement reads a snapshot that a *separate* fetcher refreshes, and firing
#: it on every run against a stale snapshot would manufacture spurious variances. The operator
#: turns it on together with the usage-ledger refresh cadence.
SETTLEMENT_ENABLED_ENV = "FINOPS_SETTLEMENT_ENABLED"


def settlement_enabled(env: dict[str, str] | None = None) -> bool:
    """True when the operator has armed automatic post-run settlement."""
    source = os.environ if env is None else env
    return (source.get(SETTLEMENT_ENABLED_ENV) or "").strip().lower() in {
        "1", "true", "yes", "on",
    }
