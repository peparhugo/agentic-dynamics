"""Lease registry — the atomic admission primitives of the fail-closed spend gate.

This module is phase 1 of the ``admission_leases`` work order
(``workflows/repository/admission_leases.yaml``). It provides the *primitives* only: the
admission controller that calls them and the entry-point wiring land in later phases. Nothing
here invokes a model, spawns a process, or spends a cent — the registry is a bookkeeper.

The problem it solves
---------------------
The repo has cost *observability* (the usage ledger: ``scripts/subscription_usage.py``) but no
cost *control*. Two runs can each read "wallet has $98" and both start, because reading a meter
is not the same as reserving against it. The audit's P0 safety contract wants a reservation that
is atomic with respect to every other admission decision — that is what a lease is:

    A lease is an *outstanding claim* on a finite resource, taken BEFORE the spend, released
    AFTER it settles, and reclaimed automatically when it expires.

Two lease kinds, both implemented by the same primitive:

``LeaseKind.BUDGET``
    A claim on spend headroom. Its *unit* is chosen by the provider class (below), because the
    two provider classes have structurally different cost models.

``LeaseKind.CONCURRENCY``
    A claim on N execution slots in a scope (fleet / provider / model / campaign / run). This is
    the throughput knob, and it is sized off the measured coordination tax β (see below).

Two provider classes (the cost-model split, mirroring ``control.model_policy``)
-------------------------------------------------------------------------------
``ProviderClass.PER_TOKEN`` — DeepSeek. Real dollars leave a real wallet per token. A budget
    lease is denominated in **USD** and is checked against a **hard dollar cap**. A per-token
    reservation whose cost provenance is ``CostSource.UNKNOWN`` is DENIED: the audit's rule
    "unknown cost is never free" is enforced at reservation time, not after the money is gone.

``ProviderClass.SUBSCRIPTION`` — Anthropic / OpenAI. Marginal dollar cost inside the plan is
    zero; the finite resource is the provider's rolling **usage window** (Anthropic's 5-hour and
    7-day windows, OpenAI's prolite windows), reported as a percentage. A budget lease is
    therefore denominated in **window percentage points** and is checked against a percentage
    cap. There is NO dollar cap for this class — asking for one is a provider-class boundary
    violation and is refused, exactly like asking for a window-percent cap on DeepSeek.

Sizing the concurrency lease: the measured coordination tax β
--------------------------------------------------------------
``scripts/lab_beta_from_corpus.py`` (preregistered 2026-08-31) fit per-worker efficiency as
``efficiency(N) = c · N^(−β)`` over the session corpus (n=1428) and produced two β's that point
in *opposite* operational directions:

    β_cost   = 0.154  (CI 0.112–0.196)  → "moderate tax"  — running wide is dollar-cheap.
    β_tokens = 0.800  (CI 0.712–0.891)  → "severe tax"    — running wide is throughput-poor.

The consequence for lease sizing, stated plainly: **the coordination tax is paid in throughput,
not in dollars.** A wide fleet does not blow the budget; it wastes wall-clock, because fleet
throughput scales as ``N^(1−β_tokens) = N^0.20`` — the 7th worker buys under 5% of one worker's
baseline output. So the concurrency lease, not the budget lease, is the binding constraint on
fleet width, and it is sized off β_tokens. Both knobs are exposed
(:data:`BETA_TOKENS`, :data:`BETA_COST`) because the *budget* forecast still wants β_cost.

Where the state lives
---------------------
The **framework** Redis (``finops-queue``) db 1 — the same instance ``control.live`` and
``scripts/monitor.py`` use. Never the **story-agent sandbox** (``finops-redis``), which story
agents build Flask/Celery apps against and routinely ``flushdb()``/``flushall()``. A lease
registry on a database that gets flushed by the work it polices is not a lease registry, so the
sandbox is refused at construction time (:class:`LeaseUnavailableError`), not merely discouraged.

The refusal is **host-qualified, not port-only**, because the same instance answers on two
different ports depending on which side of the container boundary you are:

===================================  ==========================  ==========================
Vantage point                        framework (allowed)         sandbox (refused)
===================================  ==========================  ==========================
Host                                 ``127.0.0.1:6380``          ``127.0.0.1:6379``
Inside ``fleet-net``                 ``finops-queue:6379``       (not attached to the net)
===================================  ==========================  ==========================

``infrastructure/docker-compose.experiment.yml`` publishes ``127.0.0.1:6380 -> container 6379``
for ``finops-queue``, so a ladder cell on ``fleet-net`` legitimately sets
``FINOPS_REDIS_HOST=finops-queue`` / ``FINOPS_REDIS_PORT=6379``. A blanket "port 6379 is
forbidden" rule would therefore lock the entire containerized fleet out of the gate while doing
nothing about a misconfigured ``finops-redis`` on some other port. :func:`assert_not_sandbox`
encodes the rule that actually holds: refuse the ``finops-redis`` service by name on any port,
and refuse port 6379 on the *host loopback* — where 6379 unambiguously is the sandbox.

Atomicity: WATCH/MULTI/EXEC, not Lua
------------------------------------
Each reservation is a read-modify-write ("sum the outstanding leases, then add mine if it fits").
That is a compare-and-set, and it is implemented with Redis optimistic concurrency: ``WATCH`` the
scope's keys, read, decide, ``MULTI``/``EXEC``. If any watched key changed in between, Redis
aborts the transaction, redis-py raises ``WatchError``, and we retry from the read
(:data:`DEFAULT_MAX_RETRIES` times) — so two concurrent reservations can never both observe the
same pre-state and both commit.

Lua ``EVAL`` would also be atomic and is the more common idiom. It was deliberately NOT used:
the decision logic (provider-class boundaries, cost-provenance denial, expiry pruning, the loud
field errors) is the *policy* this module exists to state, and in the Lua design that policy
would live in a string that no Python test can exercise — the unit tests would have to
re-implement it, and the re-implementation is what would get tested. With WATCH/MULTI the policy
stays in Python, so the tests drive the real code path and only the *transport* is faked.

Exhausting the retries is itself a denial (:class:`LeaseDeniedError`), not a silent pass: under
pathological contention the gate closes.

Fail-closed, everywhere
-----------------------
Every failure mode denies:

* Redis unreachable, or any unexpected Redis error → :class:`LeaseUnavailableError`.
* Cap exceeded, class boundary violated, unknown per-token cost, retries exhausted →
  :class:`LeaseDeniedError`.
* A missing, ``None``, or ill-typed lease/admission field → :class:`LeaseFieldError`.

All three derive from :class:`AdmissionError`, so a caller that wants "any refusal" catches one
type — but no code path anywhere returns a lease, a zero, or a ``None`` cap on failure. The
audit's collapse-to-zero bug (absent ``total_cost_usd`` → ``0.0``) is the exact shape of error
this module refuses to reproduce: *a missing number is an error, never a zero.*

Public surface
--------------
``reserve_budget`` · ``reserve_concurrency`` · ``release`` · ``expire_leases`` · ``outstanding``
· ``headroom`` · ``leases`` · ``set_cap`` / ``get_cap`` · :class:`AdmissionRecord` ·
:func:`recommended_concurrency` / :func:`fleet_throughput` / :func:`marginal_throughput_gain`.
"""

from __future__ import annotations

import json
import math
import os
import time
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

# ── Redis placement (the framework instance — the one that is never flushed) ─────────────────

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))

#: The framework instance as seen FROM THE HOST (``finops-queue`` publishes container 6379 here).
#: A contract constant, deliberately not env-derived, so the correct target is always nameable
#: even when the ambient ``FINOPS_REDIS_*`` env points somewhere else.
FRAMEWORK_HOST_PORT = 6380

#: The compose service name of the framework instance — the in-container spelling of the same
#: server, reached on its INTERNAL port 6379 from ``fleet-net``.
FRAMEWORK_SERVICE_HOST = "finops-queue"

#: The compose service name of the story-agent sandbox. Story agents build Flask/Celery apps
#: against it and call ``flushdb()``/``flushall()`` while testing, so a lease registry there would
#: be erased by the very work it polices. Refused on ANY port.
SANDBOX_SERVICE_HOST = "finops-redis"

#: The sandbox's host-side port. Refused only in combination with a loopback host: inside
#: ``fleet-net`` the same number is the framework instance's internal port (see the module
#: docstring's table), and ``finops-redis`` is not attached to that network at all.
SANDBOX_HOST_PORT = 6379

#: Host spellings that mean "this machine" — the vantage point where 6379 is the sandbox.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "0.0.0.0"})

#: Key prefix for every registry key. Namespacing is a constructor argument so tests (and a
#: future shadow/dry-run mode) can run against an isolated keyspace on the same database.
DEFAULT_NAMESPACE = "finops:lease"

#: Optimistic-concurrency retry budget. Exhaustion is a denial, not a pass.
DEFAULT_MAX_RETRIES = 8

#: Default lease lifetime. A lease is a *claim*, not a record: if the holder dies without
#: releasing, the claim must decay on its own or the registry deadlocks the fleet. 1h comfortably
#: exceeds a story cell and is far shorter than a wedged worker's lifetime.
DEFAULT_TTL_SECONDS = 3600

#: Redis-level TTL on the scope keys themselves, refreshed on every write. Bounds the keyspace so
#: a scope that is never used again disappears instead of accumulating forever. Must be safely
#: larger than any lease TTL (a scope key must never expire out from under a live lease).
KEY_TTL_SECONDS = 7 * 24 * 3600

# ── The measured coordination tax (scripts/lab_beta_from_corpus.py, preregistered 2026-08-31) ─

#: β for tokens — per-worker *throughput* efficiency exponent, ``efficiency(N) = c·N^(−β)``.
#: 0.80 (CI 0.712–0.891, n=1428) — the lab's "severe tax" band. THIS is the concurrency knob.
BETA_TOKENS = 0.8016211763059362

#: β for cost — per-worker *dollar* efficiency exponent. 0.154 (CI 0.112–0.196, n=1428) — the
#: lab's "moderate tax" band. Wide fleets are dollar-cheap; use this for budget forecasting, not
#: for sizing fleet width.
BETA_COST = 0.1542789674206102

#: Source of both estimates, for provenance in an admission record's metadata.
BETA_SOURCE = "experiments/results/lab_beta_from_corpus.json (preregistered 2026-08-31, n=1428)"

#: Stop widening the fleet when the next worker buys less than this fraction of one worker's
#: baseline throughput. At β_tokens this yields a recommendation of 6 concurrent workers.
DEFAULT_MIN_MARGINAL_GAIN = 0.05

#: Absolute ceiling on a recommendation, so a pathological β can never recommend an unbounded
#: fleet. The registry recommends; the operator's cap still governs.
CONCURRENCY_CEILING = 32


# ── Vocabularies ─────────────────────────────────────────────────────────────────────────────


class ProviderClass(str, Enum):
    """How a provider charges — the split that decides a budget lease's unit and cap."""

    #: DeepSeek: real dollars per token, drawn from a real wallet. Unit: USD.
    PER_TOKEN = "per_token"
    #: Anthropic / OpenAI: fixed-price plan with rolling usage windows. Unit: window percent.
    SUBSCRIPTION = "subscription"


class LeaseKind(str, Enum):
    """What finite resource the lease claims."""

    BUDGET = "budget"
    CONCURRENCY = "concurrency"


class ScopeKind(str, Enum):
    """The counter a lease is taken against.

    Scopes are independent counters, not a hierarchy — the admission controller (phase 2) takes
    one lease per scope it wants enforced and treats *all* of them failing-closed. Keeping them
    flat means a per-scope cap can be raised or lowered without reasoning about inheritance.
    """

    FLEET = "fleet"
    PROVIDER = "provider"
    MODEL = "model"
    CAMPAIGN = "campaign"
    RUN = "run"


class CostSource(str, Enum):
    """Provenance of a cost figure — the audit's "five states collapsed into one" fix.

    Defined here, in the admission layer, because *this* is where provenance has teeth: a
    per-token reservation carrying :attr:`UNKNOWN` is denied. Phase 3 wires the adapters and the
    attempt ledger to emit these values; this enum is the single source of the vocabulary.
    """

    #: The provider's own meter reported it. Trustworthy.
    METERED = "metered"
    #: Computed locally from token counts × a price table. Trustworthy enough to reserve against.
    ESTIMATED = "estimated"
    #: No cost figure was available. NOT zero. Denies a per-token reservation.
    UNKNOWN = "unknown"
    #: An estimate that was later settled against the platform meter and matched.
    RECONCILED = "reconciled"


#: Units, kept explicit on every lease so a number can never be read in the wrong currency.
UNIT_USD = "usd"
UNIT_WINDOW_PERCENT = "window_percent"
UNIT_SLOTS = "slots"

#: The unit each provider class denominates a BUDGET lease in.
BUDGET_UNIT_BY_CLASS: dict[ProviderClass, str] = {
    ProviderClass.PER_TOKEN: UNIT_USD,
    ProviderClass.SUBSCRIPTION: UNIT_WINDOW_PERCENT,
}

#: A usage window cannot exceed 100%. A subscription cap above this is a category error (someone
#: passed dollars to a window lease), and the boundary check refuses it.
WINDOW_PERCENT_MAX = 100.0

#: Provider id → class. Mirrors ``control.model_policy``'s cost model. Deliberately a closed
#: allowlist: an unrecognised provider is NOT assumed to be free (see
#: :func:`provider_class_for_provider`).
PROVIDER_CLASSES: dict[str, ProviderClass] = {
    "deepseek": ProviderClass.PER_TOKEN,
    "anthropic": ProviderClass.SUBSCRIPTION,
    "openai": ProviderClass.SUBSCRIPTION,
}


# ── Errors (every one of them a denial) ──────────────────────────────────────────────────────


class AdmissionError(RuntimeError):
    """Base class for every admission refusal. Catching this catches all three failure modes."""


class LeaseDeniedError(AdmissionError):
    """The reservation was refused: cap exceeded, class boundary violated, or contention."""


class LeaseUnavailableError(AdmissionError):
    """The registry could not be consulted (Redis down / misconfigured) — so nothing is admitted.

    Separate from :class:`LeaseDeniedError` so an operator can tell "the gate said no" from "the gate
    could not be reached". Both refuse; only the second is an infrastructure problem.
    """


class LeaseFieldError(AdmissionError):
    """A required lease/admission field is missing, ``None``, or the wrong type.

    This is the loud-error contract: the audit found absent costs silently coerced to ``0.0``,
    which made "free" and "unmeasured" indistinguishable. Nothing in this module substitutes a
    default for a missing number.
    """


# ── Value objects ────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LeaseScope:
    """One counter: a ``(kind, name)`` pair, e.g. ``(ScopeKind.MODEL, "deepseek-v4-pro")``."""

    kind: ScopeKind
    name: str

    def __post_init__(self) -> None:
        """Validate eagerly — a malformed scope must fail at construction, not at key-build."""
        if not isinstance(self.kind, ScopeKind):
            raise LeaseFieldError(f"scope kind must be a ScopeKind, got {self.kind!r}")
        if not isinstance(self.name, str) or not self.name.strip():
            raise LeaseFieldError(f"scope name must be a non-empty string, got {self.name!r}")
        # ':' is the key separator. Allowing it in a name would let "fleet:a" and "fleet" + "a"
        # collide, i.e. one scope could silently spend another's headroom.
        if ":" in self.name:
            raise LeaseFieldError(
                f"scope name {self.name!r} must not contain ':' (the key separator) — "
                f"it would alias another scope's counter"
            )

    @property
    def token(self) -> str:
        """The ``<kind>:<name>`` fragment used inside every key for this scope."""
        return f"{self.kind.value}:{self.name}"

    def __str__(self) -> str:
        return self.token


@dataclass(frozen=True)
class Lease:
    """One outstanding claim. Immutable: a lease is released or expired, never edited."""

    lease_id: str
    kind: LeaseKind
    scope: LeaseScope
    provider_class: ProviderClass
    #: USD, window percentage points, or slots — read :attr:`unit` before reading this.
    amount: float
    unit: str
    #: Cap in force when this lease was granted, recorded so an audit can replay the decision.
    hard_cap: float
    #: Epoch seconds (UTC). Past ⇒ the lease is expired and no longer counts as outstanding.
    expires_at: float
    granted_at: float
    run_id: str
    cost_source: CostSource | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def expires_at_iso(self) -> str:
        """The expiry as an ISO-8601 UTC string (for admission records and flags)."""
        return datetime.fromtimestamp(self.expires_at, tz=timezone.utc).isoformat()

    def is_expired(self, now: float) -> bool:
        """True once the claim has decayed. Expiry is ``>=`` so a zero-TTL lease is born dead."""
        return now >= self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe projection — the exact payload stored in Redis."""
        return {
            "lease_id": self.lease_id,
            "kind": self.kind.value,
            "scope_kind": self.scope.kind.value,
            "scope_name": self.scope.name,
            "provider_class": self.provider_class.value,
            "amount": self.amount,
            "unit": self.unit,
            "hard_cap": self.hard_cap,
            "expires_at": self.expires_at,
            "granted_at": self.granted_at,
            "run_id": self.run_id,
            "cost_source": self.cost_source.value if self.cost_source else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Lease:
        """Rebuild a lease from its stored payload, refusing anything malformed.

        A corrupt record is a :class:`LeaseFieldError`, never a partially-populated lease: a
        lease whose ``amount`` failed to parse would silently under-count the outstanding total,
        which is precisely the double-spend this registry exists to prevent.
        """
        missing = [
            k
            for k in ("lease_id", "kind", "scope_kind", "scope_name", "provider_class",
                      "amount", "unit", "hard_cap", "expires_at", "granted_at", "run_id")
            if payload.get(k) is None
        ]
        if missing:
            raise LeaseFieldError(f"stored lease is missing required field(s): {missing}")
        raw_source = payload.get("cost_source")
        try:
            return cls(
                lease_id=str(payload["lease_id"]),
                kind=LeaseKind(payload["kind"]),
                scope=LeaseScope(ScopeKind(payload["scope_kind"]), str(payload["scope_name"])),
                provider_class=ProviderClass(payload["provider_class"]),
                amount=float(payload["amount"]),
                unit=str(payload["unit"]),
                hard_cap=float(payload["hard_cap"]),
                expires_at=float(payload["expires_at"]),
                granted_at=float(payload["granted_at"]),
                run_id=str(payload["run_id"]),
                cost_source=CostSource(raw_source) if raw_source else None,
                metadata=dict(payload.get("metadata") or {}),
            )
        except (ValueError, TypeError) as exc:
            raise LeaseFieldError(f"stored lease is malformed: {exc}") from exc


@dataclass
class AdmissionRecord:
    """The audit's admission record — what was admitted, on whose authority, until when.

    This is the durable justification for a paid run: every field is required precisely because
    the audit found each one missing somewhere. It binds the leases (``lease_ids``) to the money
    (``reserved_cost_usd`` / ``hard_cap_usd``), the money to its provenance (``cost_source``),
    and all of it to the physical result surface (``worktree_identity`` / ``result_namespace``)
    so contaminated output can be quarantined by identity rather than by guesswork.

    Construction does not validate (so a caller can build it up field by field); call
    :meth:`validate` — which :meth:`to_dict` does for you — before persisting or trusting it.
    """

    run_id: str
    lease_ids: tuple[str, ...]
    #: Dollars reserved. For a subscription run this is legitimately ``0.0`` (marginal cost
    #: inside the plan is zero); for a per-token run it MUST be > 0 — see :meth:`validate`.
    reserved_cost_usd: float | None
    #: The dollar ceiling in force. ``None`` is legal ONLY for a subscription run, which has no
    #: dollar cap by construction. ``None`` on a per-token run is a missing field, not "no cap".
    hard_cap_usd: float | None
    cost_source: CostSource | None
    provider: str
    model: str
    #: Epoch seconds (UTC) — the earliest expiry among ``lease_ids``. Past this, the run's claim
    #: is gone and phase 4's watcher may quarantine whatever it produced.
    expires_at: float | None
    #: The worktree this run may write to (e.g. ``wt_admission_leases``).
    worktree_identity: str
    #: The results namespace its output lands in — the quarantine handle.
    result_namespace: str

    @property
    def provider_class(self) -> ProviderClass:
        """Derived, never stored — so ``provider`` and its class can never disagree."""
        return provider_class_for_provider(self.provider)

    def validate(self) -> None:
        """Raise :class:`LeaseFieldError` / :class:`LeaseDeniedError` unless the record is complete.

        Collects *every* problem before raising, so an operator fixes one error message rather
        than peeling them off one at a time.
        """
        problems: list[str] = []

        for name in ("run_id", "provider", "model", "worktree_identity", "result_namespace"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{name} must be a non-empty string (got {value!r})")

        if not self.lease_ids or not all(
            isinstance(lid, str) and lid.strip() for lid in self.lease_ids
        ):
            problems.append(
                f"lease_ids must be a non-empty sequence of lease ids (got {self.lease_ids!r}) "
                f"— an admitted run holds at least one lease"
            )

        if not _is_real_number(self.expires_at):
            problems.append(f"expires_at must be epoch seconds (got {self.expires_at!r})")

        if not _is_real_number(self.reserved_cost_usd) or (self.reserved_cost_usd or 0) < 0:
            problems.append(
                f"reserved_cost_usd must be a non-negative number (got "
                f"{self.reserved_cost_usd!r}) — a missing cost is an error, never 0.0"
            )

        if not isinstance(self.cost_source, CostSource):
            problems.append(f"cost_source must be a CostSource (got {self.cost_source!r})")

        if problems:
            raise LeaseFieldError(
                "admission record is incomplete: " + "; ".join(problems)
            )

        # Class-specific rules run only once the shape is known-good, so their messages are
        # about policy rather than about a field that was never filled in.
        if self.provider_class is ProviderClass.PER_TOKEN:
            if self.cost_source is CostSource.UNKNOWN:
                raise LeaseDeniedError(
                    f"run {self.run_id!r} on per-token provider {self.provider!r} has "
                    f"cost_source=unknown — unknown cost is never free; instrument the cost or "
                    f"route to a subscription model"
                )
            if not _is_real_number(self.hard_cap_usd) or (self.hard_cap_usd or 0) <= 0:
                raise LeaseFieldError(
                    f"hard_cap_usd must be a positive dollar ceiling for per-token provider "
                    f"{self.provider!r} (got {self.hard_cap_usd!r})"
                )
            if (self.reserved_cost_usd or 0) <= 0:
                raise LeaseFieldError(
                    f"reserved_cost_usd must be > 0 for per-token provider {self.provider!r} "
                    f"(got {self.reserved_cost_usd!r}) — a per-token run that reserves nothing "
                    f"is an unbudgeted run"
                )
            if (self.reserved_cost_usd or 0) > (self.hard_cap_usd or 0):
                raise LeaseDeniedError(
                    f"reserved_cost_usd {self.reserved_cost_usd} exceeds hard_cap_usd "
                    f"{self.hard_cap_usd} for run {self.run_id!r}"
                )
        else:
            # Subscription: no dollar cap exists. Supplying one means the caller believes this
            # provider bills per token — a provider-class boundary violation, refused loudly
            # rather than silently ignored.
            if self.hard_cap_usd is not None:
                raise LeaseDeniedError(
                    f"provider {self.provider!r} is subscription-class and has NO dollar cap; "
                    f"hard_cap_usd={self.hard_cap_usd!r} crosses the provider-class boundary "
                    f"(reserve window percentage points instead)"
                )
            if (self.reserved_cost_usd or 0) > 0:
                raise LeaseDeniedError(
                    f"provider {self.provider!r} is subscription-class: marginal dollar cost is "
                    f"zero, so reserved_cost_usd must be 0.0 (got {self.reserved_cost_usd!r})"
                )

    def to_dict(self) -> dict[str, Any]:
        """Validate, then project to the durable JSON shape (the audit line)."""
        self.validate()
        return {
            "run_id": self.run_id,
            "lease_ids": list(self.lease_ids),
            "reserved_cost_usd": self.reserved_cost_usd,
            "hard_cap_usd": self.hard_cap_usd,
            "cost_source": self.cost_source.value if self.cost_source else None,
            "provider": self.provider,
            "provider_class": self.provider_class.value,
            "model": self.model,
            "expires_at": self.expires_at,
            "expires_at_iso": datetime.fromtimestamp(
                float(self.expires_at or 0.0), tz=timezone.utc
            ).isoformat(),
            "worktree_identity": self.worktree_identity,
            "result_namespace": self.result_namespace,
        }


# ── Provider-class resolution ────────────────────────────────────────────────────────────────


def provider_class_for_provider(provider: str) -> ProviderClass:
    """Map a provider id to its cost class, refusing anything unrecognised.

    Fail-closed by omission: an unknown provider does NOT default to subscription (which would
    mean "free"). It raises, so a new provider must be classified deliberately.
    """
    if not isinstance(provider, str) or not provider.strip():
        raise LeaseFieldError(f"provider must be a non-empty string (got {provider!r})")
    key = provider.strip().lower()
    try:
        return PROVIDER_CLASSES[key]
    except KeyError:
        raise LeaseFieldError(
            f"provider {provider!r} has no declared cost class "
            f"(known: {sorted(PROVIDER_CLASSES)}) — an unclassified provider is never assumed "
            f"free; add it to PROVIDER_CLASSES"
        ) from None


def provider_class_for_model(model: str) -> ProviderClass:
    """Map a ``provider/model`` id (e.g. ``deepseek/deepseek-v4-pro``) to its cost class."""
    if not isinstance(model, str) or "/" not in model:
        raise LeaseFieldError(
            f"model must be a 'provider/model' id (got {model!r}) — the provider prefix is what "
            f"selects the cost class"
        )
    return provider_class_for_provider(model.split("/", 1)[0])


# ── Redis target validation ──────────────────────────────────────────────────────────────────


def assert_not_sandbox(host: str, port: int) -> None:
    """Raise :class:`LeaseUnavailableError` if ``(host, port)`` is the story-agent sandbox.

    The two refusal rules, and why each is host-qualified rather than port-only:

    1. ``finops-redis`` by name, on any port. The sandbox is identified by *identity*, not by the
       port it happens to be published on, so re-publishing it elsewhere does not sneak it past.
    2. Port 6379 on the host loopback. From the host, 6379 is unambiguously the sandbox
       (``finops-queue`` is published on 6380 there). From inside ``fleet-net``, 6379 is the
       framework instance's *internal* port and ``finops-redis`` is not on the network at all —
       so ``finops-queue:6379`` must remain allowed or every containerized cell loses the gate.

    Anything else passes: the registry does not try to prove the target is correct, only that it
    is not the one instance that is known to be periodically erased.
    """
    normalized = (host or "").strip().lower()
    if normalized == SANDBOX_SERVICE_HOST:
        raise LeaseUnavailableError(
            f"refusing to place the lease registry on {SANDBOX_SERVICE_HOST!r} — story agents "
            f"call flushall() there; the framework instance is {FRAMEWORK_SERVICE_HOST!r} "
            f"(host {FRAMEWORK_HOST_PORT}, in-network {SANDBOX_HOST_PORT})"
        )
    if normalized in LOOPBACK_HOSTS and int(port) == SANDBOX_HOST_PORT:
        raise LeaseUnavailableError(
            f"refusing to place the lease registry on {host}:{port} — on the host loopback "
            f"{SANDBOX_HOST_PORT} is {SANDBOX_SERVICE_HOST} (the story-agent sandbox, which is "
            f"flushed by the work it would police); the framework instance is "
            f"{FRAMEWORK_SERVICE_HOST} on 127.0.0.1:{FRAMEWORK_HOST_PORT}"
        )


# ── The β knobs (concurrency sizing) ─────────────────────────────────────────────────────────


def per_worker_efficiency(n: int, beta: float = BETA_TOKENS) -> float:
    """``efficiency(N) = N^(−β)`` — the lab's fitted form. ``n=1`` is the baseline (1.0)."""
    if n < 1:
        raise LeaseFieldError(f"concurrency must be >= 1 (got {n})")
    return float(n) ** (-beta)


def fleet_throughput(n: int, beta: float = BETA_TOKENS) -> float:
    """Aggregate fleet output relative to one worker: ``N · N^(−β) = N^(1−β)``.

    At β_tokens=0.80 this is ``N^0.20``: ten workers deliver ~1.6× one worker's throughput.
    That is the coordination tax, and it is why fleet width is capped by a concurrency lease.
    """
    return float(n) * per_worker_efficiency(n, beta)


def marginal_throughput_gain(n: int, beta: float = BETA_TOKENS) -> float:
    """What the ``n+1``-th worker adds, in units of one baseline worker's throughput."""
    return fleet_throughput(n + 1, beta) - fleet_throughput(n, beta)


def recommended_concurrency(
    beta: float = BETA_TOKENS,
    *,
    min_marginal_gain: float = DEFAULT_MIN_MARGINAL_GAIN,
    ceiling: int = CONCURRENCY_CEILING,
) -> int:
    """Widest fleet still worth running: the last ``n`` whose next worker earns its keep.

    Walks ``n`` upward while ``marginal_throughput_gain(n) >= min_marginal_gain``. With the
    measured β_tokens=0.80 and the 5% default this returns **6** — the seventh worker buys under
    5% of a baseline worker while consuming a full slot.

    This is a *recommendation* for sizing a cap, not an enforcement point: the enforced number is
    whatever cap the operator installs via :meth:`LeaseRegistry.set_cap`.
    """
    if not (0.0 <= beta < 1.0):
        raise LeaseFieldError(
            f"beta must be in [0, 1) for a meaningful recommendation (got {beta}) — "
            f"beta >= 1 means added workers reduce total throughput"
        )
    if min_marginal_gain <= 0:
        raise LeaseFieldError(f"min_marginal_gain must be > 0 (got {min_marginal_gain})")
    n = 1
    while n < ceiling and marginal_throughput_gain(n, beta) >= min_marginal_gain:
        n += 1
    return n


# ── Internal helpers ─────────────────────────────────────────────────────────────────────────


def _is_real_number(value: Any) -> bool:
    """True for a finite int/float that is not a bool.

    ``bool`` is excluded on purpose: ``isinstance(True, int)`` is ``True`` in Python, and a
    ``True`` that slipped into a cost field would silently reserve $1.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def _require_amount(name: str, value: Any) -> float:
    """Coerce a positive, finite amount or raise loudly. Zero is refused, not tolerated."""
    if not _is_real_number(value):
        raise LeaseFieldError(
            f"{name} must be a finite number (got {value!r}) — a missing amount is an error, "
            f"never 0.0"
        )
    amount = float(value)
    if amount <= 0:
        raise LeaseFieldError(
            f"{name} must be > 0 (got {amount}) — reserving nothing is not an admission"
        )
    return amount


def _watch_error_type() -> type[BaseException]:
    """Resolve redis-py's ``WatchError`` lazily.

    Imported at call time (not module import) so this module can be imported — and its pure
    logic tested — on a machine with no ``redis`` package installed. If it is absent, the
    fallback type never matches, so a transaction conflict falls through to the generic handler
    and becomes a :class:`LeaseUnavailableError`: still fail-closed.
    """
    global _WATCH_ERROR
    if _WATCH_ERROR is None:
        try:
            from redis.exceptions import WatchError

            _WATCH_ERROR = WatchError
        except Exception:  # pragma: no cover - only on a redis-less install

            class _NoWatchError(Exception):
                """Placeholder so ``except`` still has a type to match against."""

            _WATCH_ERROR = _NoWatchError
    return _WATCH_ERROR


_WATCH_ERROR: type[BaseException] | None = None


def _decode(value: Any) -> str:
    """Normalise a Redis value to ``str`` whether or not the client decodes responses."""
    return value.decode() if isinstance(value, bytes) else str(value)


# ── The registry ─────────────────────────────────────────────────────────────────────────────


class LeaseRegistry:
    """Atomic, TTL'd, per-scope leases on the framework Redis.

    Storage layout (two key families, both hashes — no counters):

    ``{ns}:{kind}:{scope_kind}:{scope_name}``
        ``lease_id -> lease JSON``. The outstanding total is the *sum over live members*, so it
        cannot drift the way an ``INCRBY``/``DECRBY`` counter drifts when a holder dies between
        the two operations. Expired members are pruned on read, inside the same transaction that
        writes — so expiry is enforced even if the sweeper never runs.

    ``{ns}:index``
        ``lease_id -> scope hash key``. Lets :meth:`release` and :meth:`expire_leases` find a
        lease from its id alone; callers hold ids, not scopes.

    Caps live in ``{ns}:cap:{kind}:{scope_kind}:{scope_name}`` (a plain string) and are consulted
    when a caller does not pass one explicitly. There is no default cap: an un-capped scope
    refuses every reservation (:class:`LeaseFieldError`) rather than admitting an unbounded one.
    """

    def __init__(
        self,
        client: Any,
        *,
        namespace: str = DEFAULT_NAMESPACE,
        now_fn: Callable[[], float] = time.time,
        id_fn: Callable[[], str] | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        """Wrap an already-connected Redis client.

        ``now_fn`` and ``id_fn`` are injected so TTL expiry and lease identity are deterministic
        under test — the registry never reads the clock or the RNG directly.
        """
        if client is None:
            raise LeaseUnavailableError(
                "lease registry requires a Redis client; refusing to admit anything without one"
            )
        self._r = client
        self._ns = namespace.rstrip(":")
        self._now_fn = now_fn
        self._id_fn = id_fn or (lambda: uuid.uuid4().hex[:16])
        self._max_retries = max(1, int(max_retries))

    # ── construction ────────────────────────────────────────────────────────────────────────

    @classmethod
    def from_env(
        cls,
        *,
        host: str | None = None,
        port: int | None = None,
        db: int | None = None,
        **kwargs: Any,
    ) -> LeaseRegistry:
        """Connect to the framework Redis (6380 db1) or raise :class:`LeaseUnavailableError`.

        Unlike ``control.live``, this does NOT degrade gracefully when Redis is down. Telemetry
        that no-ops costs a dashboard; an admission gate that no-ops costs money.
        """
        host = host or REDIS_HOST
        port = int(port if port is not None else REDIS_PORT)
        db = int(db if db is not None else REDIS_DB)

        # The sandbox guard: story agents flush that instance while testing the apps they build.
        assert_not_sandbox(host, port)
        try:
            import redis

            client = redis.Redis(
                host=host,
                port=port,
                db=db,
                decode_responses=True,  # the registry stores JSON strings
                socket_connect_timeout=2,
                socket_timeout=5,
            )
            client.ping()
        except Exception as exc:
            raise LeaseUnavailableError(
                f"lease registry cannot reach Redis at {host}:{port}/{db} ({exc}) — "
                f"admission is refused while the gate is unreachable"
            ) from exc
        return cls(client, **kwargs)

    # ── keys ────────────────────────────────────────────────────────────────────────────────

    def _scope_key(self, kind: LeaseKind, scope: LeaseScope) -> str:
        """Hash key holding every lease of ``kind`` taken against ``scope``."""
        return f"{self._ns}:{kind.value}:{scope.token}"

    @property
    def _index_key(self) -> str:
        """Hash key mapping every live lease id to its scope hash key."""
        return f"{self._ns}:index"

    def _cap_key(self, kind: LeaseKind, scope: LeaseScope) -> str:
        """String key holding the installed cap for ``(kind, scope)``."""
        return f"{self._ns}:cap:{kind.value}:{scope.token}"

    # ── caps ────────────────────────────────────────────────────────────────────────────────

    def set_cap(self, kind: LeaseKind, scope: LeaseScope, cap: float) -> float:
        """Install the hard cap for a scope. Returns the stored value."""
        value = _require_amount("cap", cap)
        try:
            self._r.set(self._cap_key(kind, scope), repr(value))
        except Exception as exc:
            raise LeaseUnavailableError(f"cannot write cap for {scope}: {exc}") from exc
        return value

    def get_cap(self, kind: LeaseKind, scope: LeaseScope) -> float | None:
        """The installed cap, or ``None`` if the scope has never been capped."""
        try:
            raw = self._r.get(self._cap_key(kind, scope))
        except Exception as exc:
            raise LeaseUnavailableError(f"cannot read cap for {scope}: {exc}") from exc
        if raw is None:
            return None
        try:
            return float(_decode(raw))
        except ValueError as exc:
            raise LeaseFieldError(f"stored cap for {scope} is not a number: {raw!r}") from exc

    def _resolve_cap(
        self, kind: LeaseKind, scope: LeaseScope, explicit: float | None
    ) -> float:
        """Explicit cap, else the installed cap, else refuse.

        There is deliberately no fallback default. An admission layer whose unconfigured state is
        "unlimited" is not an admission layer.
        """
        if explicit is not None:
            return _require_amount("hard_cap", explicit)
        stored = self.get_cap(kind, scope)
        if stored is None:
            raise LeaseFieldError(
                f"no hard cap for {kind.value} scope {scope} — pass hard_cap= or install one "
                f"with set_cap(); an uncapped scope admits nothing"
            )
        return _require_amount("hard_cap", stored)

    # ── reservations ────────────────────────────────────────────────────────────────────────

    def reserve_budget(
        self,
        provider_class: ProviderClass,
        scope: LeaseScope,
        amount: float,
        *,
        run_id: str,
        cost_source: CostSource | None = None,
        hard_cap: float | None = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        metadata: Mapping[str, Any] | None = None,
    ) -> Lease:
        """Atomically reserve spend headroom, or refuse.

        ``amount``'s unit follows ``provider_class``: **USD** for
        :attr:`ProviderClass.PER_TOKEN`, **window percentage points** for
        :attr:`ProviderClass.SUBSCRIPTION`. Mixing them is the provider-class boundary error this
        method refuses (a subscription cap above 100 cannot be a window; see below).

        Refusals:

        * ``cost_source`` missing or :attr:`CostSource.UNKNOWN` on a per-token reservation —
          unknown cost is never free.
        * ``outstanding + amount > hard_cap`` — the cap is a hard ceiling, checked atomically
          against every other live lease in the scope.
        * a subscription cap above 100% — dollars were passed to a window lease.
        * Redis unreachable, or retries exhausted under contention.
        """
        if not isinstance(provider_class, ProviderClass):
            raise LeaseFieldError(
                f"provider_class must be a ProviderClass (got {provider_class!r})"
            )
        amount = _require_amount("amount", amount)
        cap = self._resolve_cap(LeaseKind.BUDGET, scope, hard_cap)
        unit = BUDGET_UNIT_BY_CLASS[provider_class]

        # ── the provider-class boundary ──────────────────────────────────────────────────────
        if provider_class is ProviderClass.PER_TOKEN:
            # Dollars: provenance is mandatory, and "unknown" is a denial, not a zero.
            if cost_source is None:
                raise LeaseFieldError(
                    f"per-token budget lease for run {run_id!r} requires an explicit "
                    f"cost_source ({[c.value for c in CostSource]}) — an unstated cost is not $0"
                )
            if cost_source is CostSource.UNKNOWN:
                raise LeaseDeniedError(
                    f"per-token budget lease for run {run_id!r} denied: cost_source=unknown. "
                    f"Unknown cost is never free — meter or estimate the cost first."
                )
        else:
            # Window percent: a cap above 100 means the caller handed a dollar figure to a
            # subscription lease. Refuse rather than quietly treat 500 "percent" as headroom.
            if cap > WINDOW_PERCENT_MAX:
                raise LeaseDeniedError(
                    f"subscription budget lease for run {run_id!r} denied: hard_cap {cap} "
                    f"exceeds {WINDOW_PERCENT_MAX}% — subscription leases are denominated in "
                    f"window percentage points and have NO dollar cap "
                    f"(provider-class boundary violation)"
                )
            if amount > WINDOW_PERCENT_MAX:
                raise LeaseDeniedError(
                    f"subscription budget lease for run {run_id!r} denied: amount {amount} "
                    f"exceeds {WINDOW_PERCENT_MAX} window percentage points "
                    f"(provider-class boundary violation)"
                )

        return self._reserve(
            kind=LeaseKind.BUDGET,
            scope=scope,
            provider_class=provider_class,
            amount=amount,
            unit=unit,
            hard_cap=cap,
            run_id=run_id,
            cost_source=cost_source,
            ttl_seconds=ttl_seconds,
            metadata=metadata,
        )

    def reserve_concurrency(
        self,
        scope: LeaseScope,
        count: int = 1,
        *,
        run_id: str,
        hard_cap: float | None = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        metadata: Mapping[str, Any] | None = None,
    ) -> Lease:
        """Atomically reserve ``count`` execution slots in ``scope``, or refuse.

        The cap is a *per-scope* number (fleet width, per-provider parallelism, …), never a
        global invariant — that is why the scope is an argument. Size it with
        :func:`recommended_concurrency`, which uses the measured β_tokens=0.80: throughput, not
        dollars, is what a wide fleet burns.

        The lease's ``provider_class`` is :attr:`ProviderClass.SUBSCRIPTION` because a slot costs
        no money by itself; the dollars, if any, are claimed by a separate budget lease.
        """
        if isinstance(count, bool) or not isinstance(count, int):
            raise LeaseFieldError(f"count must be an int number of slots (got {count!r})")
        slots = float(_require_amount("count", count))
        cap = self._resolve_cap(LeaseKind.CONCURRENCY, scope, hard_cap)
        return self._reserve(
            kind=LeaseKind.CONCURRENCY,
            scope=scope,
            provider_class=ProviderClass.SUBSCRIPTION,
            amount=slots,
            unit=UNIT_SLOTS,
            hard_cap=cap,
            run_id=run_id,
            cost_source=None,
            ttl_seconds=ttl_seconds,
            metadata=metadata,
        )

    def _reserve(
        self,
        *,
        kind: LeaseKind,
        scope: LeaseScope,
        provider_class: ProviderClass,
        amount: float,
        unit: str,
        hard_cap: float,
        run_id: str,
        cost_source: CostSource | None,
        ttl_seconds: int,
        metadata: Mapping[str, Any] | None,
    ) -> Lease:
        """The shared compare-and-set: WATCH → read → prune → decide → MULTI/EXEC → retry.

        The whole point of this method is that the *decision* (does ``outstanding + amount`` fit
        under ``hard_cap``?) and the *write* (record my lease) cannot be separated by another
        writer. ``WATCH`` on the scope hash makes Redis abort the ``EXEC`` if anyone touched the
        scope in between; we then re-read and decide again against the new truth.
        """
        if not isinstance(run_id, str) or not run_id.strip():
            raise LeaseFieldError(f"run_id must be a non-empty string (got {run_id!r})")
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
            raise LeaseFieldError(
                f"ttl_seconds must be a positive int (got {ttl_seconds!r}) — a lease with no "
                f"expiry can wedge a scope forever"
            )

        scope_key = self._scope_key(kind, scope)
        index_key = self._index_key

        for _attempt in range(self._max_retries):
            try:
                with self._r.pipeline() as pipe:
                    # WATCH puts the pipeline in immediate mode: the hgetall below executes now,
                    # and EXEC later aborts if either key changed in the meantime.
                    pipe.watch(scope_key, index_key)
                    live, expired = self._partition(pipe.hgetall(scope_key))

                    now = self._now_fn()
                    outstanding = sum(lease.amount for lease in live)
                    if outstanding + amount > hard_cap + _EPSILON:
                        # Denial is raised INSIDE the watch block but outside the transaction:
                        # nothing has been written, and the context manager resets the watch.
                        raise LeaseDeniedError(
                            f"{kind.value} lease denied for run {run_id!r} on scope {scope}: "
                            f"requested {amount} {unit} + outstanding {outstanding} "
                            f"> hard cap {hard_cap} ({len(live)} live lease(s))"
                        )

                    lease = Lease(
                        lease_id=f"{kind.value[:3]}_{self._id_fn()}",
                        kind=kind,
                        scope=scope,
                        provider_class=provider_class,
                        amount=amount,
                        unit=unit,
                        hard_cap=hard_cap,
                        expires_at=now + ttl_seconds,
                        granted_at=now,
                        run_id=run_id,
                        cost_source=cost_source,
                        metadata=dict(metadata or {}),
                    )

                    pipe.multi()
                    # Prune in the same transaction that grants: expiry is enforced by every
                    # writer, so a stalled sweeper can never inflate the outstanding total.
                    if expired:
                        pipe.hdel(scope_key, *expired)
                        pipe.hdel(index_key, *expired)
                    pipe.hset(scope_key, lease.lease_id, _dumps(lease.to_dict()))
                    pipe.hset(index_key, lease.lease_id, scope_key)
                    # Refresh the keyspace TTL so abandoned scopes disappear, live ones persist.
                    pipe.expire(scope_key, KEY_TTL_SECONDS)
                    pipe.expire(index_key, KEY_TTL_SECONDS)
                    pipe.execute()
                    return lease
            except _watch_error_type():
                # Someone else committed against this scope. Re-read and decide again — the
                # retry is what makes concurrent reservations serialise instead of racing.
                continue
            except AdmissionError:
                raise
            except Exception as exc:
                raise LeaseUnavailableError(
                    f"lease registry Redis failure while reserving {kind.value} on {scope}: "
                    f"{exc}"
                ) from exc

        raise LeaseDeniedError(
            f"{kind.value} lease denied for run {run_id!r} on scope {scope}: contention — "
            f"{self._max_retries} optimistic-lock attempts all lost the race. Refusing rather "
            f"than admitting on stale state."
        )

    # ── release / expiry ────────────────────────────────────────────────────────────────────

    def release(self, lease_id: str) -> Lease | None:
        """Release a lease, returning it. Idempotent: an unknown/already-released id gives ``None``.

        Release is deliberately forgiving about *absence* (a double release is harmless and a
        crash-then-expire path is normal) but strict about *corruption*: a stored record that
        cannot be parsed still raises, because that means the scope's outstanding total is
        untrustworthy.
        """
        if not isinstance(lease_id, str) or not lease_id.strip():
            raise LeaseFieldError(f"lease_id must be a non-empty string (got {lease_id!r})")
        index_key = self._index_key

        for _attempt in range(self._max_retries):
            try:
                with self._r.pipeline() as pipe:
                    pipe.watch(index_key)
                    raw_scope_key = pipe.hget(index_key, lease_id)
                    if raw_scope_key is None:
                        pipe.unwatch()
                        return None
                    scope_key = _decode(raw_scope_key)
                    pipe.watch(scope_key)
                    raw_lease = pipe.hget(scope_key, lease_id)

                    pipe.multi()
                    pipe.hdel(scope_key, lease_id)
                    pipe.hdel(index_key, lease_id)
                    pipe.execute()
                    # Parse after the delete: the release must succeed even for a record we
                    # would refuse to *count*, otherwise a corrupt lease is unreleasable.
                    return Lease.from_dict(json.loads(_decode(raw_lease))) if raw_lease else None
            except _watch_error_type():
                continue
            except AdmissionError:
                raise
            except Exception as exc:
                raise LeaseUnavailableError(
                    f"lease registry Redis failure while releasing {lease_id!r}: {exc}"
                ) from exc

        raise LeaseDeniedError(
            f"could not release {lease_id!r}: {self._max_retries} optimistic-lock attempts lost "
            f"the race"
        )

    def expire_leases(self, *, scopes: Iterable[tuple[LeaseKind, LeaseScope]] | None = None) -> list[Lease]:
        """Sweep expired leases and return them (newest-expiry last).

        The returned leases are phase 4's input: an expired *concurrency* lease means a worker
        outlived its slot; an expired *budget* lease means work continued past its reservation
        and its output is a quarantine candidate. This method only reclaims the claim — it never
        kills a process, because the supervisor rail is observe-only.

        ``scopes`` narrows the sweep; the default walks every scope reachable from the index.
        """
        try:
            if scopes is None:
                index = self._r.hgetall(self._index_key) or {}
                scope_keys = sorted({_decode(v) for v in index.values()})
            else:
                scope_keys = sorted({self._scope_key(k, s) for k, s in scopes})
        except AdmissionError:
            raise
        except Exception as exc:
            raise LeaseUnavailableError(f"lease registry Redis failure during sweep: {exc}") from exc

        swept: list[Lease] = []
        for scope_key in scope_keys:
            swept.extend(self._expire_scope(scope_key))
        return sorted(swept, key=lambda lease: lease.expires_at)

    def _expire_scope(self, scope_key: str) -> list[Lease]:
        """Transactionally prune one scope's expired leases; returns what was reclaimed."""
        index_key = self._index_key
        for _attempt in range(self._max_retries):
            try:
                with self._r.pipeline() as pipe:
                    pipe.watch(scope_key, index_key)
                    # Only the expired half is acted on here; the live half is untouched.
                    _live, expired = self._partition(pipe.hgetall(scope_key))
                    if not expired:
                        pipe.unwatch()
                        return []
                    reclaimed = [Lease.from_dict(payload) for payload in expired.values()]
                    pipe.multi()
                    pipe.hdel(scope_key, *expired)
                    pipe.hdel(index_key, *expired)
                    pipe.execute()
                    return reclaimed
            except _watch_error_type():
                continue
            except AdmissionError:
                raise
            except Exception as exc:
                raise LeaseUnavailableError(
                    f"lease registry Redis failure expiring {scope_key}: {exc}"
                ) from exc
        raise LeaseDeniedError(
            f"could not sweep {scope_key}: {self._max_retries} optimistic-lock attempts lost "
            f"the race"
        )

    # ── reads ───────────────────────────────────────────────────────────────────────────────

    def leases(self, kind: LeaseKind, scope: LeaseScope) -> list[Lease]:
        """Every *live* (unexpired) lease in a scope, oldest grant first. Read-only: no pruning."""
        try:
            raw = self._r.hgetall(self._scope_key(kind, scope)) or {}
        except AdmissionError:
            raise
        except Exception as exc:
            raise LeaseUnavailableError(f"lease registry Redis failure reading {scope}: {exc}") from exc
        live, _expired = self._partition(raw)
        return sorted(live, key=lambda lease: (lease.granted_at, lease.lease_id))

    def outstanding(self, kind: LeaseKind, scope: LeaseScope) -> float:
        """Sum of live lease amounts in a scope — the number a reservation is checked against."""
        return sum(lease.amount for lease in self.leases(kind, scope))

    def headroom(self, kind: LeaseKind, scope: LeaseScope, hard_cap: float | None = None) -> float:
        """Remaining capacity: ``cap − outstanding``, floored at 0.

        Advisory only. Never reserve against this value — between the read and the spend another
        run may take the headroom, which is exactly the race the lease exists to close.
        """
        cap = self._resolve_cap(kind, scope, hard_cap)
        return max(0.0, cap - self.outstanding(kind, scope))

    # ── parsing ─────────────────────────────────────────────────────────────────────────────

    def _partition(self, raw: Mapping[Any, Any] | None) -> tuple[list[Lease], dict[str, dict]]:
        """Split a scope hash into ``(live leases, {expired lease_id: payload})``.

        A record that will not parse is a hard error (:class:`LeaseFieldError` from
        :meth:`Lease.from_dict`), never a skipped row: skipping would under-count the outstanding
        total and admit a run that should have been refused.
        """
        now = self._now_fn()
        live: list[Lease] = []
        expired: dict[str, dict] = {}
        for raw_id, raw_payload in (raw or {}).items():
            lease_id = _decode(raw_id)
            try:
                payload = json.loads(_decode(raw_payload))
            except (ValueError, TypeError) as exc:
                raise LeaseFieldError(
                    f"lease {lease_id!r} holds unparseable JSON — the scope's outstanding total "
                    f"cannot be trusted: {exc}"
                ) from exc
            lease = Lease.from_dict(payload)
            if lease.is_expired(now):
                expired[lease_id] = payload
            else:
                live.append(lease)
        return live, expired


#: Float comparison slack for the cap check. Reserving exactly the cap in several instalments
#: (0.1 + 0.2 + 0.7 vs 1.0) must not be refused by binary-float noise; a millionth of a cent (or
#: of a percentage point) is far below any meaningful budget granularity.
_EPSILON = 1e-9


def _dumps(payload: Mapping[str, Any]) -> str:
    """Deterministic JSON — stable ordering keeps stored records diffable and hashable."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))
