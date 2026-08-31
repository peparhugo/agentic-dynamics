"""Admission controller — the fail-closed gate every spend entry point calls.

Phase 2 of the ``admission_leases`` work order (``workflows/repository/admission_leases.yaml``).
Phase 1 built the *primitives* (``control.lease_registry``: atomic, TTL'd, per-scope leases);
this module is the *decision* that uses them, and the wiring that puts it in front of every
paid invocation.

The contract, in one sentence
-----------------------------
    Before any paid invocation: reserve the budget lease AND every concurrency lease; if
    either fails, release whatever was already taken and refuse with :class:`AdmissionDenied`.

That "and" is the whole point. The audit's failure mode was two runs each reading "the wallet
has $98" and both starting — reading a meter is not reserving against it. An admission is
therefore all-or-nothing: a run that holds a budget lease but lost the concurrency race is not
half-admitted, it is refused, and its budget lease is released in the same call. Nothing is
left outstanding by a refusal.

The five entry points (the work order's §SHAPE)
-----------------------------------------------
=======================================  =====================================================
Entry point                              What it admits
=======================================  =====================================================
``scripts/enqueue.py``                   one budget lease per queued cell, at queue-fill time,
                                         so the queue never carries unbudgeted work
``scripts/worker.py``                    budget + concurrency before the ``run_story``
                                         subprocess; released after the cell settles
``scripts/analysis_worker.py``           concurrency only — analysis spends no model dollars
``scripts/fleet/spawn_wrapper.py``       the lease block rides the spawn request;
                                         ``validate_spawn`` step 6 refuses a spawn without it
``scripts/run_workflow.py``              a campaign lease for the run + a budget reservation
                                         per phase, injected into ``runtime.workflow_runner``
=======================================  =====================================================

Plus the backstop and the bypass detector:

* ``control.model_policy.ensure_model_allowed`` stays exactly as it was and is called *first*
  inside :meth:`AdmissionController.admit` — the class-level "``deepseek-v4-pro`` needs
  ``FINOPS_ALLOW_PRO=1``" guard now sits **under** the lease gate rather than beside it. Two
  independent refusals in series, not one replacing the other.
* ``adapters.backends.run_agentic`` calls ``core.admission_context.require_admission``, so
  calling a backend *around* this controller is a detectable, refusing event when the gate is
  armed. See ``core.admission_context`` for why that guard lives in tier 0.

Provider classes decide the currency
------------------------------------
Inherited unchanged from the registry: DeepSeek is ``PER_TOKEN`` (a budget lease in **USD**
against a hard dollar cap, and ``CostSource.UNKNOWN`` is a denial), Anthropic/OpenAI are
``SUBSCRIPTION`` (a budget lease in **window percentage points**, no dollar cap — asking for
one is a class-boundary violation). :func:`resolve_reservation` is where a caller turns "I want
to run this model" into the right currency, and it is deliberately unwilling to guess a dollar
figure: an unstated per-token cost resolves to :attr:`CostSource.UNKNOWN`, which the registry
then denies. That is the audit's "unknown cost is never free", enforced at the one place a
caller could otherwise have shrugged.

Arming
------
The gate refuses only when armed (``FINOPS_ADMISSION_REQUIRED=1``); see
``core.admission_context``'s module docstring for the reasoning and for why that is a stated
posture rather than a silent fallback. Every entry point below follows the same shape:

    if not admission_required(): run as before
    else:                        admit → run under the context → release

Public surface
--------------
:class:`AdmissionDenied` · :class:`AdmissionRequest` · :class:`Admission` ·
:class:`AdmissionController` · :func:`default_controller` · :func:`admitted` ·
:func:`resolve_reservation` · :func:`make_phase_admission` · :func:`admission_board`.
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from typing import Any

from agentic_dynamics.control.lease_registry import (
    DEFAULT_TTL_SECONDS,
    AdmissionError,
    AdmissionRecord,
    CostSource,
    Lease,
    LeaseFieldError,
    LeaseKind,
    LeaseRegistry,
    LeaseScope,
    LeaseUnavailableError,
    ProviderClass,
    ScopeKind,
    provider_class_for_model,
)
from agentic_dynamics.control.model_policy import ModelPolicyError, ensure_model_allowed
from agentic_dynamics.control.settlement import settle_run, settlement_enabled
from agentic_dynamics.core.admission_context import (
    AdmissionRefused,
    LeaseContext,
    admission_required,
    bind_context,
)

# ── Reservation defaults (the knobs an operator sets per deployment) ─────────────────────────

#: Explicit per-invocation dollar reservation for a per-token run. There is no default and no
#: fallback estimate: absent this (and an explicit argument), a per-token reservation resolves
#: to :attr:`CostSource.UNKNOWN` and the registry denies it. The audit's finding was that a
#: guessed zero is indistinguishable from a measured zero, so this module guesses nothing.
RESERVE_USD_ENV = "FINOPS_RESERVE_USD"

#: The dollar ceiling a per-token budget lease is checked against, when the scope has no cap
#: installed via ``LeaseRegistry.set_cap``. Same posture: no default value, only an override.
HARD_CAP_USD_ENV = "FINOPS_HARD_CAP_USD"

#: Window percentage points a subscription run reserves. Unlike dollars this DOES have a
#: default, because a subscription window is a bounded, self-replenishing resource whose
#: consumption is knowable a priori as "one run's share" — and because the alternative
#: (denying every subscription run for want of a percentage) would freeze the very models the
#: cost model prefers. One point ≈ 1% of a rolling window.
WINDOW_RESERVE_PERCENT_ENV = "FINOPS_WINDOW_RESERVE_PERCENT"
DEFAULT_WINDOW_RESERVE_PERCENT = 1.0

#: The fleet scope name concurrency is counted against when a caller does not name one. A
#: deployment that runs two independent fleets on one Redis sets this per fleet so their slot
#: counters do not share a ceiling.
FLEET_SCOPE_ENV = "FINOPS_FLEET_SCOPE"
DEFAULT_FLEET_SCOPE = "default"


# ── The refusal ──────────────────────────────────────────────────────────────────────────────


class AdmissionDenied(AdmissionError, AdmissionRefused):  # noqa: N818 — see below
    """The controller refused admission — no paid invocation may follow.

    Inherits from BOTH families on purpose (see ``core.admission_context.AdmissionRefused``):

    * ``except AdmissionError`` — the tier-2 lease vocabulary, for control-plane callers that
      also want cap denials and registry unavailability.
    * ``except AdmissionRefused`` — the tier-0 vocabulary, for ``runtime``/``adapters``
      callers that may not import ``control`` at all.

    ``cause`` carries the underlying lease-layer error when there was one, so an operator can
    tell "cap exceeded" from "Redis unreachable" from "the pro tier is not opted in" without
    parsing the message.

    (The ``N818`` "name exceptions ``…Error``" lint is waived here deliberately: the work order
    specifies this type by name — "refuses with a typed ``AdmissionDenied``" — and *denied* is
    the domain verb the whole gate is written in. ``AdmissionDeniedError`` would read as a
    failure to deny. Every other exception in the layer keeps the suffix.)
    """

    def __init__(self, message: str, *, request: AdmissionRequest | None = None,
                 cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.request = request
        self.cause = cause


# ── The request ──────────────────────────────────────────────────────────────────────────────


@dataclass
class AdmissionRequest:
    """What a caller wants admitted — one paid unit of work.

    A "unit" is whatever the entry point treats as atomic: a queued story cell, a worker's
    subprocess, a workflow phase, a sibling container. The controller does not care which; it
    cares that the unit has an identity (``run_id``), a price (``amount`` + ``cost_source``),
    a physical output surface (``worktree_identity`` / ``result_namespace``, so phase 4 can
    quarantine by identity), and an expiry.
    """

    #: Unique id for this unit of work. Becomes the ``run_id`` on every lease it holds, so the
    #: registry can be queried "what is this run holding?" and the sweeper can attribute an
    #: expired lease to the work that produced output under it.
    run_id: str
    #: ``provider/model`` id. Selects the provider class, hence the budget lease's currency.
    model: str
    #: The worktree this unit may write to — the quarantine handle for its code output.
    worktree_identity: str
    #: The results namespace its output lands in — the quarantine handle for its data output.
    result_namespace: str

    #: The budget reservation, in the provider class's currency: USD for ``PER_TOKEN``, window
    #: percentage points for ``SUBSCRIPTION``. ``None`` means "unstated" and, for a per-token
    #: model, is resolved to a denial rather than to zero (see :func:`resolve_reservation`).
    amount: float | None = None
    #: Provenance of ``amount``. Mandatory for ``PER_TOKEN``; :attr:`CostSource.UNKNOWN` denies.
    cost_source: CostSource | None = None
    #: Dollar ceiling for the admission record (``PER_TOKEN`` only; ``None`` for subscription).
    hard_cap_usd: float | None = None

    #: The counter the budget lease is taken against. Default: the provider's own counter, so
    #: DeepSeek dollars and Anthropic window points never share a ceiling.
    budget_scope: LeaseScope | None = None
    #: Explicit cap for the budget scope; ``None`` uses the cap installed with ``set_cap``.
    budget_cap: float | None = None

    #: Every concurrency counter this unit must fit inside. Default: one fleet-wide counter.
    #: They are ALL required — the audit's contract is "refuse if either reservation fails",
    #: and with several scopes that generalises to "refuse if any fails".
    concurrency_scopes: tuple[LeaseScope, ...] = ()
    #: Set ``False`` for a unit that reserves spend but starts nothing — the queue-fill case
    #: (``scripts/enqueue.py``), where the budget must be claimed at fill time but no execution
    #: slot is occupied until a worker picks the job up. This is an explicit opt-out rather than
    #: "pass an empty tuple", because an empty ``concurrency_scopes`` already means "use the
    #: default fleet counter" and a caller must not be able to disable a lease by omission.
    enforce_concurrency: bool = True
    #: Slots claimed in each concurrency scope (a phase that fans out claims more than one).
    slots: int = 1
    #: Explicit per-scope concurrency caps, keyed by ``LeaseScope``; else the installed caps.
    concurrency_caps: Mapping[LeaseScope, float] = field(default_factory=dict)

    #: Lease lifetime. Past it the claim is gone and phase 4 may quarantine the output.
    ttl_seconds: int = DEFAULT_TTL_SECONDS
    #: Free-form provenance recorded on every lease (cell id, spec name, phase, …).
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def provider(self) -> str:
        """The provider id — the ``provider`` half of ``provider/model``."""
        return self.model.split("/", 1)[0] if "/" in self.model else self.model

    @property
    def provider_class(self) -> ProviderClass:
        """Derived from the model, never stored — the two can then never disagree."""
        return provider_class_for_model(self.model)

    def resolved_budget_scope(self) -> LeaseScope:
        """The budget counter: the explicit one, else this provider's own."""
        return self.budget_scope or LeaseScope(ScopeKind.PROVIDER, self.provider)

    def resolved_concurrency_scopes(self) -> tuple[LeaseScope, ...]:
        """The concurrency counters: none if opted out, else the explicit ones, else the fleet."""
        if not self.enforce_concurrency:
            return ()
        if self.concurrency_scopes:
            return tuple(self.concurrency_scopes)
        fleet = os.environ.get(FLEET_SCOPE_ENV, "").strip() or DEFAULT_FLEET_SCOPE
        return (LeaseScope(ScopeKind.FLEET, fleet),)


# ── The grant ────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Admission:
    """A granted admission: the leases, the audit record, and the portable context.

    Immutable — an admission is granted, carried, and released. To change what a run is allowed
    to spend you release and re-admit, so every change of claim is a registry event.
    """

    #: The audit line (validated at construction by the controller) — the durable justification.
    record: AdmissionRecord
    #: The spend-headroom claim.
    budget_lease: Lease
    #: One claim per enforced concurrency scope (possibly empty for a budget-only admission).
    concurrency_leases: tuple[Lease, ...]

    @property
    def run_id(self) -> str:
        """The admitted unit's id."""
        return self.record.run_id

    @property
    def lease_ids(self) -> tuple[str, ...]:
        """Every lease this admission holds, budget first."""
        return (self.budget_lease.lease_id, *(lease.lease_id for lease in self.concurrency_leases))

    @property
    def expires_at(self) -> float:
        """The EARLIEST expiry among the leases — the admission dies with its shortest claim."""
        return min(lease.expires_at for lease in (self.budget_lease, *self.concurrency_leases))

    def context(self) -> LeaseContext:
        """The portable proof, for the ContextVar and for a child process's launch envelope."""
        return LeaseContext(
            run_id=self.record.run_id,
            model=self.record.model,
            budget_lease_id=self.budget_lease.lease_id,
            concurrency_lease_ids=tuple(
                lease.lease_id for lease in self.concurrency_leases
            ),
            reserved_cost_usd=float(self.record.reserved_cost_usd or 0.0),
            hard_cap_usd=self.record.hard_cap_usd,
            expires_at=self.expires_at,
            # The provenance travels with the reservation. Without it the child process's
            # ``require_admission`` cannot tell a priced per-token claim from an unpriced one,
            # and (fail-closed) would refuse every per-token invocation.
            cost_source=self.record.cost_source,
        )

    def env(self) -> dict[str, str]:
        """The env block to merge into a subprocess/container launch envelope."""
        return self.context().to_env()

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe projection: the admission record plus the leases it is made of."""
        return {
            **self.record.to_dict(),
            "budget_lease": self.budget_lease.to_dict(),
            "concurrency_leases": [lease.to_dict() for lease in self.concurrency_leases],
        }


# ── Reservation resolution (where "how much?" is answered, or refused) ───────────────────────


def resolve_reservation(
    model: str,
    *,
    amount: float | None = None,
    cost_source: CostSource | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[float, CostSource]:
    """Resolve ``(amount, cost_source)`` in the model's provider-class currency.

    The two classes are resolved in deliberately different ways, because their finite resources
    are different in kind:

    **Subscription (Anthropic / OpenAI)** — the resource is a rolling usage window measured in
    percentage points, self-replenishing and bounded at 100. A default share per run is
    meaningful, so an unstated amount resolves to :data:`DEFAULT_WINDOW_RESERVE_PERCENT` (or
    :data:`WINDOW_RESERVE_PERCENT_ENV`) with :attr:`CostSource.ESTIMATED` — a *stated estimate*,
    not a guessed dollar figure. Phase 3 replaces this with the live window reading from the
    usage ledger, at which point the source becomes :attr:`CostSource.METERED`.

    **Per-token (DeepSeek)** — the resource is real money in a real wallet, and there is no
    honest default share of a wallet. An unstated amount therefore resolves to
    ``(0.0, CostSource.UNKNOWN)``, and ``reserve_budget`` **denies** an ``UNKNOWN`` per-token
    reservation. This is the audit's "unknown cost is never free" made structural: the only way
    to run DeepSeek through the gate is to state what you expect it to cost, either as an
    argument or via :data:`RESERVE_USD_ENV`.

    An explicitly supplied ``cost_source`` always wins — phase 3's metered/reconciled figures
    come in that way.
    """
    source = os.environ if env is None else env
    provider_class = provider_class_for_model(model)

    if provider_class is ProviderClass.SUBSCRIPTION:
        if amount is None:
            raw = str(source.get(WINDOW_RESERVE_PERCENT_ENV, "")).strip()
            try:
                amount = float(raw) if raw else DEFAULT_WINDOW_RESERVE_PERCENT
            except ValueError as exc:
                raise AdmissionDenied(
                    f"{WINDOW_RESERVE_PERCENT_ENV}={raw!r} is not a number — refusing rather "
                    f"than falling back to a default the operator did not choose",
                    cause=exc,
                ) from exc
        return float(amount), cost_source or CostSource.ESTIMATED

    # Per-token: dollars, or nothing.
    if amount is None:
        raw = str(source.get(RESERVE_USD_ENV, "")).strip()
        if not raw:
            # NOT zero. The returned UNKNOWN is what makes reserve_budget refuse.
            return 0.0, cost_source or CostSource.UNKNOWN
        try:
            amount = float(raw)
        except ValueError as exc:
            raise AdmissionDenied(
                f"{RESERVE_USD_ENV}={raw!r} is not a dollar amount — an unparseable cost is a "
                f"refusal, never 0.0",
                cause=exc,
            ) from exc
    return float(amount), cost_source or CostSource.ESTIMATED


def resolve_hard_cap_usd(
    model: str,
    *,
    hard_cap_usd: float | None = None,
    env: Mapping[str, str] | None = None,
) -> float | None:
    """Resolve the admission record's dollar ceiling for ``model``.

    ``None`` for a subscription model — that class has no dollar cap by construction, and
    supplying one is a class-boundary violation the record itself refuses. For a per-token
    model: the explicit value, else :data:`HARD_CAP_USD_ENV`, else ``None`` (which the record's
    validator then reports as a *missing field*, not as "no limit").
    """
    if provider_class_for_model(model) is ProviderClass.SUBSCRIPTION:
        return None
    if hard_cap_usd is not None:
        return float(hard_cap_usd)
    source = os.environ if env is None else env
    raw = str(source.get(HARD_CAP_USD_ENV, "")).strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise AdmissionDenied(
            f"{HARD_CAP_USD_ENV}={raw!r} is not a dollar amount — refusing rather than "
            f"admitting against an unparseable ceiling",
            cause=exc,
        ) from exc


# ── The controller ───────────────────────────────────────────────────────────────────────────


class AdmissionController:
    """Checks BOTH leases before any paid invocation, and refuses when either fails.

    Stateless with respect to the run: everything it decides is recorded in the registry, so
    two controllers on two hosts sharing one framework Redis make consistent decisions. The
    only instance state is the registry handle and the clock (injected for deterministic tests).
    """

    def __init__(
        self,
        registry: LeaseRegistry,
        *,
        now_fn=time.time,
        id_fn=None,
    ) -> None:
        """Wrap a lease registry.

        ``now_fn``/``id_fn`` are injected so expiry and run-id minting are deterministic under
        test — the controller never reads the clock or the RNG directly.
        """
        if registry is None:
            raise LeaseUnavailableError(
                "admission controller requires a lease registry; refusing to admit without one"
            )
        self._registry = registry
        self._now_fn = now_fn
        self._id_fn = id_fn or (lambda: uuid.uuid4().hex[:12])

    @property
    def registry(self) -> LeaseRegistry:
        """The underlying lease registry (read-only access for telemetry surfaces)."""
        return self._registry

    # -- the decision -----------------------------------------------------------------------

    def admit(self, request: AdmissionRequest) -> Admission:
        """Reserve every lease this unit needs, or refuse and leave nothing outstanding.

        Order of operations, each step a refusal point:

        1. **Model-policy backstop** — ``ensure_model_allowed`` (the pro-tier opt-in). Runs
           first because it is the cheapest refusal and needs no Redis round-trip.
        2. **Budget lease** — in the provider class's currency, against the scope's hard cap.
           A per-token reservation with ``cost_source=unknown`` dies here.
        3. **Concurrency leases** — one per enforced scope, all required.
        4. **Admission record** — built and ``validate()``d, so a run whose *record* would be
           incomplete never executes even though its leases were grantable.

        If step 3 or 4 fails, every lease taken in steps 2–3 is released before the refusal
        propagates: a denial never leaks a claim. That release is best-effort by necessity (the
        registry may be the thing that failed), and a failure to release is folded into the
        refusal's message rather than masking it.
        """
        # 1 — the class-level backstop, unchanged, now underneath the lease gate.
        try:
            ensure_model_allowed(request.model)
        except ModelPolicyError as exc:
            raise AdmissionDenied(
                f"admission denied for run {request.run_id!r}: {exc}",
                request=request,
                cause=exc,
            ) from exc

        try:
            provider_class = request.provider_class
        except LeaseFieldError as exc:
            # An unclassified provider is never assumed free (the registry's closed allowlist).
            raise AdmissionDenied(
                f"admission denied for run {request.run_id!r}: {exc}",
                request=request,
                cause=exc,
            ) from exc

        amount, cost_source = resolve_reservation(
            request.model, amount=request.amount, cost_source=request.cost_source
        )
        hard_cap_usd = resolve_hard_cap_usd(request.model, hard_cap_usd=request.hard_cap_usd)

        # "Unknown cost is never free", named here rather than left to the registry. The
        # registry DOES enforce it independently (``reserve_budget`` refuses an UNKNOWN
        # per-token reservation — defence in depth, and the reason this is not the only check),
        # but an unstated cost arrives as ``(0.0, UNKNOWN)`` and would trip the registry's
        # amount-must-be-positive rule first. Fail-closed either way; the difference is the
        # message the operator reads, and "reserving nothing is not an admission" sends them
        # looking for the wrong bug. The audit's actual rule deserves to be the one cited.
        if provider_class is ProviderClass.PER_TOKEN and cost_source is CostSource.UNKNOWN:
            raise AdmissionDenied(
                f"admission denied for run {request.run_id!r} on per-token model "
                f"{request.model}: cost_source=unknown. Unknown cost is never free — state the "
                f"expected spend (AdmissionRequest.amount or {RESERVE_USD_ENV}) or route to a "
                f"subscription model.",
                request=request,
            )

        # 2 — the budget lease.
        try:
            budget_lease = self._registry.reserve_budget(
                provider_class,
                request.resolved_budget_scope(),
                amount,
                run_id=request.run_id,
                cost_source=cost_source,
                hard_cap=request.budget_cap,
                ttl_seconds=request.ttl_seconds,
                metadata={**request.metadata, "model": request.model, "kind": "budget"},
            )
        except AdmissionError as exc:
            raise AdmissionDenied(
                f"admission denied for run {request.run_id!r} on {request.model}: budget "
                f"reservation failed — {exc}",
                request=request,
                cause=exc,
            ) from exc

        # 3 — the concurrency leases. Any failure unwinds step 2 as well.
        taken: list[Lease] = [budget_lease]
        concurrency_leases: list[Lease] = []
        try:
            for scope in request.resolved_concurrency_scopes():
                lease = self._registry.reserve_concurrency(
                    scope,
                    request.slots,
                    run_id=request.run_id,
                    hard_cap=request.concurrency_caps.get(scope),
                    ttl_seconds=request.ttl_seconds,
                    metadata={
                        **request.metadata, "model": request.model, "kind": "concurrency",
                    },
                )
                concurrency_leases.append(lease)
                taken.append(lease)
        except AdmissionError as exc:
            unwind = self._release_all(taken)
            raise AdmissionDenied(
                f"admission denied for run {request.run_id!r} on {request.model}: concurrency "
                f"reservation failed — {exc}"
                + (f" (release during unwind also failed: {unwind})" if unwind else ""),
                request=request,
                cause=exc,
            ) from exc

        # 4 — the audit record. Built AFTER the leases so it can name them, validated BEFORE
        #     the caller runs so an incomplete justification stops the run rather than the
        #     bookkeeping.
        record = AdmissionRecord(
            run_id=request.run_id,
            lease_ids=tuple(lease.lease_id for lease in taken),
            # Dollars only for the per-token class: a subscription run's marginal dollar cost
            # inside the plan is genuinely zero, and the record's validator enforces that.
            reserved_cost_usd=(
                amount if provider_class is ProviderClass.PER_TOKEN else 0.0
            ),
            hard_cap_usd=hard_cap_usd,
            cost_source=cost_source,
            provider=request.provider,
            model=request.model,
            expires_at=min(lease.expires_at for lease in taken),
            worktree_identity=request.worktree_identity,
            result_namespace=request.result_namespace,
        )
        try:
            record.validate()
        except AdmissionError as exc:
            unwind = self._release_all(taken)
            raise AdmissionDenied(
                f"admission denied for run {request.run_id!r}: the admission record is not "
                f"valid — {exc}"
                + (f" (release during unwind also failed: {unwind})" if unwind else ""),
                request=request,
                cause=exc,
            ) from exc

        return Admission(
            record=record,
            budget_lease=budget_lease,
            concurrency_leases=tuple(concurrency_leases),
        )

    # -- release ----------------------------------------------------------------------------

    def release(self, admission: Admission) -> list[Lease]:
        """Release every lease an admission holds. Idempotent; returns what was reclaimed.

        Called after the unit settles — successfully or not. Releasing is *not* settlement:
        it returns the headroom, it does not record what was actually spent. Reconciling the
        reservation against the platform meter is phase 3's ``settle``; this method exists so
        the headroom is never held hostage by a crashed run in the meantime (and even if the
        release itself is never reached, the lease's TTL reclaims it — release is the fast
        path, expiry is the guarantee).
        """
        released: list[Lease] = []
        for lease_id in admission.lease_ids:
            lease = self._registry.release(lease_id)
            if lease is not None:
                released.append(lease)
        return released

    def _release_all(self, leases: Sequence[Lease]) -> str:
        """Best-effort unwind used by a *failing* admit. Returns "" or an error summary.

        Deliberately swallows registry errors into a string instead of raising: this runs
        inside the handling of an earlier failure, and replacing a precise "concurrency cap
        exceeded" with a vague "release failed" would destroy the diagnosis. The string is
        appended to the denial message so nothing is lost either.
        """
        problems: list[str] = []
        for lease in leases:
            try:
                self._registry.release(lease.lease_id)
            except AdmissionError as exc:  # the registry is the thing that failed
                problems.append(f"{lease.lease_id}: {exc}")
        return "; ".join(problems)

    # -- verification (the deeper bypass check) ----------------------------------------------

    def verify(self, context: LeaseContext, *, now: float | None = None) -> None:
        """Confirm a context's leases are genuinely outstanding, or raise :class:`AdmissionDenied`.

        ``core.admission_context.require_admission`` answers the *structural* question ("is a
        live-looking context present?") without touching Redis, because it runs in tier 0 on
        every invocation. This answers the *substantive* one: are those lease ids actually in
        the registry right now? It is what catches a forged or stale env block — a child that
        inherited an admission whose parent has since released it, or a hand-set
        ``FINOPS_BUDGET_LEASE_ID``.

        Not called on the hot path (it costs a Redis round-trip per invocation); it is the
        audit tool and the fleet wrapper's optional deep check.
        """
        moment = self._now_fn() if now is None else now
        if context.is_expired(moment):
            raise AdmissionDenied(
                f"admission {context.run_id!r} expired at {context.expires_at} (now {moment})"
            )
        # Walk every scope the registry knows and collect the live ids once, rather than doing
        # a lookup per id: the registry's index is a single hash, and one read is atomic enough
        # for a verification that is by nature a point-in-time statement.
        live = self._live_lease_ids()
        wanted = {context.budget_lease_id, *context.concurrency_lease_ids}
        missing = sorted(w for w in wanted if w and w not in live)
        if missing:
            raise AdmissionDenied(
                f"admission {context.run_id!r} names lease(s) {missing} that are not "
                f"outstanding in the registry — the context is stale or forged"
            )

    def _live_lease_ids(self) -> set[str]:
        """Every unexpired lease id in the registry, across every scope the index knows.

        Walks the registry's own index hash (``lease_id -> scope hash key``) and re-reads each
        distinct scope through the registry's parser, so expiry is judged by exactly the same
        rule a reservation would apply — a lease that is expired-but-unswept counts as absent
        here, matching what ``outstanding`` would say.

        Reaches into the registry's private members deliberately and only here: verification is
        the one operation that needs "every lease, regardless of scope", and adding a public
        registry method for a debugging/audit path would widen phase 1's surface for a caller
        that is not on any hot path.
        """
        registry = self._registry
        try:
            index = registry._r.hgetall(registry._index_key) or {}
        except Exception as exc:  # noqa: BLE001 — fail closed: unverifiable means denied
            raise AdmissionDenied(
                f"cannot verify admission: lease registry unreadable ({exc})", cause=exc
            ) from exc

        ids: set[str] = set()
        for scope_key in {str(value) for value in index.values()}:
            try:
                raw = registry._r.hgetall(scope_key) or {}
            except Exception as exc:  # noqa: BLE001 — fail closed
                raise AdmissionDenied(
                    f"cannot verify admission: scope {scope_key} unreadable ({exc})", cause=exc
                ) from exc
            live, _expired = registry._partition(raw)
            ids.update(lease.lease_id for lease in live)
        return ids


# ── Construction + the scoped helper ─────────────────────────────────────────────────────────


def default_controller(**kwargs: Any) -> AdmissionController:
    """Build a controller against the framework Redis (6380 db1), or raise.

    Deliberately not cached and not lazily degrading: ``LeaseRegistry.from_env`` raises
    :class:`LeaseUnavailableError` when the gate is unreachable, and an entry point that cannot
    reach the gate must refuse rather than proceed. Telemetry degrades; admission does not.
    """
    return AdmissionController(LeaseRegistry.from_env(), **kwargs)


@contextmanager
def admitted(
    request: AdmissionRequest, *, controller: AdmissionController | None = None
) -> Iterator[Admission]:
    """Admit, run the block under the admission, release — even on an exception.

    The canonical entry-point shape::

        with admitted(AdmissionRequest(run_id=..., model=..., ...)) as adm:
            subprocess.run(cmd, env={**os.environ, **adm.env()})

    Inside the block the admission is bound to BOTH carriers
    (``core.admission_context.bind_context``), so an in-process ``run_agentic`` sees it via the
    ContextVar and any subprocess launched inside inherits it via the environment.

    Release always runs. If the release itself fails, the failure is *not* raised over the
    body's own exception — the TTL will reclaim the lease anyway, and masking the real error
    with a bookkeeping one is how a diagnosis gets lost.
    """
    ctrl = controller or default_controller()
    admission = ctrl.admit(request)
    try:
        with bind_context(admission.context()):
            yield admission
    finally:
        # POST-RUN SETTLEMENT (work order p3, audit item 5) — BEFORE the release, so the
        # reservation being settled is still outstanding while it is measured.
        #
        # Here rather than at each call site because ``admitted`` wraps exactly the paths that
        # are real runs (the worker's cells, the workflow's phases); ``scripts/enqueue.py``
        # reserves through ``ctrl.admit`` directly precisely because a queue-fill claims budget
        # for work that has not happened yet and must NOT be settled.
        #
        # Best-effort and opt-in: ``settle_run`` never raises (a bookkeeping failure must not
        # surface over the body's own exception), and ``settlement_enabled()`` is off unless the
        # operator armed it — the meter is a snapshot on its own refresh cadence, and settling
        # every run against a stale one would manufacture variances.
        if settlement_enabled():
            settle_run(
                run_id=admission.run_id,
                model=request.model,
                reserved_amount=float(admission.budget_lease.amount),
            )
        # The lease's TTL is the guarantee; release is only the fast path — so a release
        # failure must never surface over whatever the body was already raising.
        with suppress(AdmissionError):
            ctrl.release(admission)


@contextmanager
def concurrency_admitted(
    scope: LeaseScope,
    count: int = 1,
    *,
    run_id: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    registry: LeaseRegistry | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> Iterator[Lease | None]:
    """Hold a concurrency lease for the duration of a block — for work that costs no dollars.

    The analysis worker is the case this exists for: it runs AST diffs and SonarQube, spends no
    model dollars, and therefore has no provider class, no budget currency, and no admission
    record to validate — but it very much occupies an execution slot, and a fleet of them will
    starve the story workers of CPU just as effectively as a fleet of paid cells.

    Modelling that as a full :class:`AdmissionRequest` would mean inventing a fake model and a
    fake $0 reservation, which is exactly the "a zero that means nothing" the audit found. A
    concurrency-only lease says the true thing: *this occupies a slot and claims no money*.

    Yields the lease when the gate is armed, ``None`` when it is disarmed. Releases on exit,
    including on an exception; the TTL is the backstop if the process dies first.
    """
    if not admission_required():
        yield None
        return
    reg = registry or LeaseRegistry.from_env()
    try:
        lease = reg.reserve_concurrency(
            scope, count, run_id=run_id, ttl_seconds=ttl_seconds, metadata=dict(metadata or {})
        )
    except AdmissionError as exc:
        raise AdmissionDenied(
            f"concurrency admission denied for {run_id!r} on scope {scope}: {exc}", cause=exc
        ) from exc
    try:
        yield lease
    finally:
        # The TTL reclaims it; masking the body's exception with a release error would
        # destroy the diagnosis.
        with suppress(AdmissionError):
            reg.release(lease.lease_id)


# ── The workflow-runner seam (runtime.admission.PhaseAdmission) ──────────────────────────────


def make_phase_admission(
    *,
    spec_name: str,
    worktree_identity: str,
    result_namespace: str,
    controller: AdmissionController | None = None,
    campaign_scope: LeaseScope | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
):
    """Build the ``PhaseAdmission`` callable ``runtime.workflow_runner`` wraps each phase in.

    This is the composition-root half of the Debt-2 pattern, identical in shape to
    ``make_shadow_router``/``make_applying_router``: ``runtime`` declares the protocol
    (``runtime.admission.PhaseAdmission``) and never imports ``control``; the control plane
    supplies the implementation and ``scripts/run_workflow.py`` injects it.

    Each phase reserves against the workflow's **campaign** scope (default:
    ``campaign:<spec_name>``) rather than a per-phase scope, so a five-phase run competes for
    one campaign budget instead of five independent ones — which is what "per-phase budget
    reservation against the workflow's campaign lease" means in the work order.

    Returns a callable ``(phase_name, model) -> context manager``. When the gate is disarmed it
    returns a no-op context manager, so injecting this is safe unconditionally: the runner's
    behaviour is byte-identical until an operator arms the gate.
    """
    scope = campaign_scope or LeaseScope(ScopeKind.CAMPAIGN, spec_name)

    @contextmanager
    def phase_admission(phase_name: str, model: str) -> Iterator[Admission | None]:
        """Admit one phase, or yield ``None`` when the gate is disarmed."""
        if not admission_required():
            yield None
            return
        request = AdmissionRequest(
            run_id=f"{spec_name}:{phase_name}:{uuid.uuid4().hex[:8]}",
            model=model,
            worktree_identity=worktree_identity,
            result_namespace=result_namespace,
            budget_scope=scope,
            concurrency_scopes=(scope,),
            ttl_seconds=ttl_seconds,
            metadata={"spec": spec_name, "phase": phase_name},
        )
        # Settlement happens in ``admitted`` (below), so every real run settles — the worker's
        # cells as well as these phases — without each entry point repeating the hook.
        with admitted(request, controller=controller) as admission:
            yield admission

    return phase_admission


# ── Telemetry (the Control Room's admission board) ───────────────────────────────────────────


def admission_board(
    registry: LeaseRegistry,
    scopes: Sequence[tuple[LeaseKind, LeaseScope]],
) -> dict[str, Any]:
    """Project the leases' live state for the Control Room's ``/api/subscription-usage`` route.

    The work order makes that route "the admission telemetry surface (the leases' data source)":
    the provider usage snapshot it already serves is what the leases are *sized against*, so the
    outstanding leases belong beside it rather than on a separate endpoint an operator would
    have to correlate by hand.

    Read-only and total: a scope with no installed cap reports ``cap: null`` and
    ``headroom: null`` rather than raising, because an uncapped scope is a legitimate (if
    inert) state for a dashboard to display — it means "this counter admits nothing yet".
    """
    rows: list[dict[str, Any]] = []
    for kind, scope in scopes:
        try:
            leases = registry.leases(kind, scope)
            cap = registry.get_cap(kind, scope)
        except AdmissionError as exc:
            rows.append({
                "kind": kind.value,
                "scope": scope.token,
                "error": str(exc),
            })
            continue
        outstanding = sum(lease.amount for lease in leases)
        rows.append({
            "kind": kind.value,
            "scope": scope.token,
            "cap": cap,
            "outstanding": outstanding,
            "headroom": None if cap is None else max(0.0, cap - outstanding),
            "unit": leases[0].unit if leases else None,
            "lease_count": len(leases),
            "leases": [lease.to_dict() for lease in leases],
        })
    return {
        "armed": admission_required(),
        "required_env": "FINOPS_ADMISSION_REQUIRED",
        "scopes": rows,
    }
