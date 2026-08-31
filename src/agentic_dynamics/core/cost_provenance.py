"""Cost provenance — where a dollar figure came from, and whether it may be trusted.

This module is the tier-0 half of phase 3 of the ``admission_leases`` work order
(``workflows/repository/admission_leases.yaml``). It holds *vocabulary only*: the
:class:`CostSource` enum, the :class:`ProviderClass` split, the estimation-method names, and
the pure resolver that turns "what the backend told us" into a provenance-tagged observation.
No Redis, no network, no pricing table, no clock — standard library only, importable from
any plane.

The bug this module exists to kill
----------------------------------
The audit's finding was a **five-state collapse**: five genuinely different situations all
arrived downstream as the single float ``0.0``.

===========================================  =========================  ==================
situation                                    before                     after
===========================================  =========================  ==================
provider metered the run at exactly $0        ``estimated_cost_usd=0.0`` ``METERED``, 0.0
provider reported no cost field at all        ``estimated_cost_usd=0.0`` ``UNKNOWN``, None
session never reached a model call            ``estimated_cost_usd=0.0`` ``UNKNOWN``, None
backend reported a placeholder zero           ``estimated_cost_usd=0.0`` ``ESTIMATED`` (*)
cost was estimated from tokens × price table  ``estimated_cost_usd=X``   ``ESTIMATED``
===========================================  =========================  ==================

(*) A placeholder zero alongside a non-zero token count is *recorded* as a reported zero
(:attr:`CostObservation.reported_cost_usd` is ``0.0``, not ``None`` — so it stays
distinguishable from an absent figure) but is not *believed* as the final figure: tokens were
demonstrably spent, so the price table supplies the number and the source is ``ESTIMATED``.

Why the vocabulary lives in tier 0
----------------------------------
Three planes need it and none of them may import ``control``:

* ``adapters`` — emits the provenance (``AgenticResult.cost_source``).
* ``experiment`` — carries it on the attempt ledger (``LEDGER_FIELDS``).
* ``core.admission_context`` — refuses a per-token invocation whose cost is ``UNKNOWN``.

``tests/test_dependency_direction.py::test_tier1_to_tier2_edges_are_exactly_pinned`` pins the
complete plane→control edge set to the two ``control.live`` telemetry edges, and
``test_core_imports_nothing_from_higher_tiers`` forbids ``core → control`` outright. So the
vocabulary lives here and ``control.lease_registry`` — where provenance has *teeth*, since an
``UNKNOWN`` per-token reservation is denied — imports and re-exports it. Same shape as
``core.admission_context`` (contract in tier 0, decision in tier 2); see that module's
docstring for the full rationale.

Public surface
--------------
:class:`CostSource` · :class:`ProviderClass` · :data:`PROVIDER_CLASSES` ·
:func:`provider_class_or_none` · :func:`is_per_token_model` · :data:`ESTIMATION_METHODS` ·
:class:`CostObservation` · :func:`resolve_cost_observation`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

# ── Provenance ───────────────────────────────────────────────────────────────────────────────


class CostSource(str, Enum):
    """Provenance of a cost figure — the audit's "five states collapsed into one" fix.

    A ``str`` enum so a value serialises to its own name in JSON/JSONL (the ledger, the
    admission record, the lease payload) without a custom encoder, and so a plain string read
    back from a ledger compares equal to the member.

    The four states are ordered by trust, and the gate reads that order directly:

    * :attr:`METERED` and :attr:`RECONCILED` are the provider's own arithmetic.
    * :attr:`ESTIMATED` is ours — good enough to *reserve* against, since reserving too much
      only costs headroom, never money.
    * :attr:`UNKNOWN` is the absence of a figure, and it is the one value that **denies** a
      per-token reservation. It is emphatically not ``0.0``.
    """

    #: The provider's own meter reported it. Trustworthy. A metered ``0.0`` is a real zero.
    METERED = "metered"
    #: Computed locally from token counts × a price table. Trustworthy enough to reserve against.
    ESTIMATED = "estimated"
    #: No cost figure was available. NOT zero. Denies a per-token reservation.
    UNKNOWN = "unknown"
    #: An estimate later settled against the platform meter / usage window, and matched.
    RECONCILED = "reconciled"


#: The provenance values a per-token (real-dollar) invocation may carry. ``UNKNOWN`` is absent
#: from this set by design — that absence *is* the "unknown cost is never free" rule, expressed
#: once so every enforcement point (the registry, the admission record, the adapter guard) can
#: test membership rather than re-deriving the policy from an ``is`` comparison.
TRUSTED_COST_SOURCES: frozenset[CostSource] = frozenset(
    {CostSource.METERED, CostSource.ESTIMATED, CostSource.RECONCILED}
)


def coerce_cost_source(value: Any) -> CostSource | None:
    """Parse a ``CostSource`` from a member, a string, or ``None`` — never guessing.

    Used at every deserialisation boundary (env block, lease payload, ledger row). An
    unrecognised string returns ``None`` ("no provenance stated") rather than raising or
    defaulting to a trusted value: the callers all treat ``None`` as untrusted, so a typo
    degrades to a refusal instead of to a silent permission.
    """
    if isinstance(value, CostSource):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return CostSource(value.strip().lower())
    except ValueError:
        return None


# ── Estimation methods ───────────────────────────────────────────────────────────────────────
#
# When ``cost_source`` is ESTIMATED or RECONCILED, ``estimation_method`` records *how*. This
# is the field that makes a re-derivation possible: a figure whose method is
# ``token_price_table`` can be recomputed from the ledger's token counts and a pricing version,
# while one whose method is ``platform_meter_daily`` cannot (it came from an external meter).

#: Provider's own per-step/per-result cost field, summed or taken cumulatively.
METHOD_PROVIDER_METER = "provider_meter"
#: ``measurement.efficiency`` pricing table applied to the attempt's own token counts.
METHOD_TOKEN_PRICE_TABLE = "token_price_table"
#: DeepSeek platform meter's per-day buckets (``deepseek_platform.days[].estimated_cost_usd``).
METHOD_PLATFORM_METER_DAILY = "platform_meter_daily"
#: A subscription provider's rolling usage window (``providers.<p>.windows[].used_percent``).
METHOD_WINDOW_USAGE = "window_usage"

#: The closed vocabulary. A method outside this set is a typo, and the ledger validator says so
#: rather than accepting free-form provenance that no consumer can interpret.
ESTIMATION_METHODS: frozenset[str] = frozenset(
    {
        METHOD_PROVIDER_METER,
        METHOD_TOKEN_PRICE_TABLE,
        METHOD_PLATFORM_METER_DAILY,
        METHOD_WINDOW_USAGE,
    }
)


# ── Provider classes ─────────────────────────────────────────────────────────────────────────


class ProviderClass(str, Enum):
    """How a provider charges — the split that decides a budget lease's unit and cap."""

    #: DeepSeek: real dollars per token, drawn from a real wallet. Unit: USD.
    PER_TOKEN = "per_token"
    #: Anthropic / OpenAI: fixed-price plan with rolling usage windows. Unit: window percent.
    SUBSCRIPTION = "subscription"


#: Provider id → class. Deliberately a **closed allowlist**: an unrecognised provider is NOT
#: assumed subscription-class (which would read as "free"). The tier-2 resolver
#: (``control.lease_registry.provider_class_for_provider``) raises on a miss; the tier-0
#: resolver below returns ``None``, and its callers treat ``None`` as "cannot prove this is
#: free", which is the same refusal expressed without a control-plane exception type.
PROVIDER_CLASSES: dict[str, ProviderClass] = {
    "deepseek": ProviderClass.PER_TOKEN,
    "anthropic": ProviderClass.SUBSCRIPTION,
    "openai": ProviderClass.SUBSCRIPTION,
}


def provider_class_or_none(provider: str) -> ProviderClass | None:
    """Map a provider id to its cost class, or ``None`` when it is not classified.

    The non-raising twin of ``control.lease_registry.provider_class_for_provider``. Tier 0 has
    no admission exception hierarchy to raise from, and the guard that consumes this needs to
    answer one question — "must this invocation prove its cost?" — for which "unclassified"
    and "per-token" both mean *yes*. See :func:`is_per_token_model`.
    """
    if not isinstance(provider, str) or not provider.strip():
        return None
    return PROVIDER_CLASSES.get(provider.strip().lower())


def is_per_token_model(model: str) -> bool:
    """True when invoking ``model`` spends real per-token dollars.

    Fail-closed on both unknowns: an unparseable model id and an unclassified provider both
    return ``True``, because the consequence of a false ``True`` is an unnecessary refusal
    while the consequence of a false ``False`` is unmetered spend. Only a provider *explicitly*
    classified :attr:`ProviderClass.SUBSCRIPTION` returns ``False``.
    """
    if not isinstance(model, str) or not model.strip():
        return True
    provider = model.split("/", 1)[0] if "/" in model else model
    return provider_class_or_none(provider) is not ProviderClass.SUBSCRIPTION


# ── The observation ──────────────────────────────────────────────────────────────────────────


def _is_real_number(value: Any) -> bool:
    """True for a finite int/float that is not a bool (``True`` is not a cost of $1)."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


@dataclass(frozen=True)
class CostObservation:
    """One attempt's cost, with the provenance needed to audit or re-derive it.

    Frozen because an observation is a *record of what happened*: the settlement step
    (``control.settlement``) produces a new observation rather than mutating this one, so the
    original backend-reported figure survives alongside the reconciled one.
    """

    #: The figure to bill/report. ``None`` when :attr:`source` is :attr:`CostSource.UNKNOWN` —
    #: the whole point of this module is that "no cost" is not the number zero.
    cost_usd: float | None
    #: Where :attr:`cost_usd` came from.
    source: CostSource
    #: How, when :attr:`source` is ``ESTIMATED``/``RECONCILED``. ``None`` for metered/unknown.
    estimation_method: str | None = None
    #: What the backend itself reported, verbatim and unrepaired — ``None`` when it reported
    #: nothing, ``0.0`` when it reported a zero. This single field is what makes the audit's
    #: "provider-reported zero vs missing cost" distinction observable downstream.
    reported_cost_usd: float | None = None

    @property
    def is_trusted(self) -> bool:
        """True when this figure may back a real-dollar reservation."""
        return self.source in TRUSTED_COST_SOURCES

    @property
    def billable_usd(self) -> float:
        """:attr:`cost_usd` for reporting sums, treating ``None`` as ``0.0``.

        Provided so aggregators do not each invent their own ``or 0.0``. Use it only where a
        sum is wanted; never as an admission input — the gate must see :attr:`source`.
        """
        return float(self.cost_usd) if _is_real_number(self.cost_usd) else 0.0

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe projection — the four fields, in ledger vocabulary."""
        return {
            "cost_usd": self.cost_usd,
            "cost_source": self.source.value,
            "estimation_method": self.estimation_method,
            "reported_cost_usd": self.reported_cost_usd,
        }


def resolve_cost_observation(
    *,
    reported_cost_usd: float | None,
    estimated_cost_usd: float | None = None,
    estimation_method: str = METHOD_TOKEN_PRICE_TABLE,
    tokens_observed: bool = False,
) -> CostObservation:
    """Turn a backend's raw cost reporting into a provenance-tagged observation.

    This is the single decision procedure both adapters run, so the opencode path and the
    Claude CLI path can never disagree about what a missing cost means.

    Args:
        reported_cost_usd: What the backend reported. ``None`` ⇒ it reported nothing. ``0.0``
            ⇒ it reported a zero (kept verbatim on the result either way).
        estimated_cost_usd: The price-table fallback, when one could be computed.
        estimation_method: How ``estimated_cost_usd`` was derived (default: the price table).
        tokens_observed: Whether the transcript reported any token usage. Distinguishes "the
            provider metered this at $0" from "no model call ever happened".

    The rules, in order:

    1. A reported cost **greater than zero** is the provider's meter. ``METERED``.
    2. A reported cost of **exactly zero with no tokens** is a real zero — nothing was
       invoked, so nothing was charged. ``METERED``, and the ``0.0`` is a measurement.
    3. A reported cost of **exactly zero alongside spent tokens** is a placeholder (opencode
       emits ``cost: 0`` for providers it does not price). Tokens were spent, so the estimate
       wins: ``ESTIMATED`` — while ``reported_cost_usd`` keeps the observed zero.
    4. **Nothing reported**, but an estimate exists ⇒ ``ESTIMATED``.
    5. **Nothing reported and nothing estimable** ⇒ ``UNKNOWN`` with ``cost_usd=None``. This
       is the state that denies a per-token admission.
    """
    reported = float(reported_cost_usd) if _is_real_number(reported_cost_usd) else None
    estimate = float(estimated_cost_usd) if _is_real_number(estimated_cost_usd) else None

    # (1) + (2): a positive meter reading, or a zero from a session that never spent tokens.
    if reported is not None and (reported > 0.0 or not tokens_observed):
        return CostObservation(
            cost_usd=reported,
            source=CostSource.METERED,
            estimation_method=None,
            reported_cost_usd=reported,
        )

    # (3) + (4): fall back to the estimate, keeping whatever was reported for the audit trail.
    if estimate is not None:
        return CostObservation(
            cost_usd=estimate,
            source=CostSource.ESTIMATED,
            estimation_method=estimation_method,
            reported_cost_usd=reported,
        )

    # (5) The honest gap. Note ``cost_usd=None``, never 0.0 — that substitution is the bug.
    return CostObservation(
        cost_usd=None,
        source=CostSource.UNKNOWN,
        estimation_method=None,
        reported_cost_usd=reported,
    )
