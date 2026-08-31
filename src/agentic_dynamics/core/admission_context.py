"""Admission context — the portable proof that a paid invocation was admitted.

This module is the tier-0 half of phase 2 of the ``admission_leases`` work order
(``workflows/repository/admission_leases.yaml``). It holds *vocabulary only*: the env-var
contract, the :class:`LeaseContext` value object, the in-process carrier, and the pure
structural validators. The *decision* — reserving against Redis, checking caps, refusing —
lives in ``control.admission`` (tier 2), which builds on everything here.

Why the split is not optional
-----------------------------
The bypass guard has to fire inside ``adapters.backends.run_agentic``: that is the single
function every paid model invocation passes through, so it is the only place a "was this run
admitted?" question can be asked of *all* spend. But ``adapters`` is tier 1 and ``control`` is
tier 2, and ``tests/test_dependency_direction.py::test_tier1_to_tier2_edges_are_exactly_pinned``
asserts that the complete set of plane→control edges is the two pinned telemetry edges
(``opencode``/``claude_adapter`` → ``control.live``). An ``adapters.backends → control.admission``
edge would break that guard, and weakening the guard to admit it would re-open the hole the
guard exists to close.

So the layering follows the same shape as the Debt-2 Router/TelemetryPublisher inversion:

* **tier 0 (here)** — the *contract*: what an admission looks like once granted, how it crosses
  a process boundary, and whether a given context is structurally valid and still live.
* **tier 2 (``control.admission``)** — the *decision*: reserve the leases, mint the context,
  release them, refuse when either reservation fails.

Everything in this module is pure with respect to the outside world: standard library only, no
Redis, no network, no clock except the one you pass in. It can be imported from any plane.

The two carriers, and why there are two
---------------------------------------
An admission has to survive two very different boundaries:

``ContextVar`` (in-process)
    ``run_workflow`` admits a phase and then calls ``run_agentic`` in the same process. A
    context variable is the right carrier: it is implicitly scoped, thread-safe, and restored
    exactly on scope exit even when the phase raises.

Environment variables (cross-process)
    ``scripts/worker.py`` admits a cell and then ``subprocess.run``s ``scripts/run_story.py``;
    the fleet orchestrator admits a phase and then ``docker run``s a sibling container. Neither
    child shares the parent's memory, so the context has to be *serialised into the launch
    envelope*. The env-var block below is that serialisation, and it is deliberately the same
    five lease fields the fleet spawn request carries — one vocabulary, three transports.

:func:`current_context` reads the ContextVar first and falls back to the environment, so a
child process launched by an admitted parent sees the parent's admission without any code in
between having to thread it through.

Arming: ``FINOPS_ADMISSION_REQUIRED``
-------------------------------------
The gate is **armed by the operator**, not by import. ``FINOPS_ADMISSION_REQUIRED=1`` makes
:func:`require_admission` refuse an unadmitted invocation; unset (the default) makes it a no-op
and every entry point behaves exactly as it did before this phase.

That default is a deliberate reading of the work order's hard rule 3 — *"THE FREEZE STAYS: this
workflow does not lift the freeze. Its deliverable is the gate that will lift it"*. No scope has
a cap installed yet (:meth:`LeaseRegistry.set_cap` has zero production call sites), and an
uncapped scope admits nothing, so arming the gate here would deny **every** run rather than
gate it. Arming is the operator's freeze-exit decision, made once the caps are installed; the
deliverable of this phase is that the gate is *there and correct* when they flip it.

Fail-closed still means fail-closed: when the gate IS armed, a missing context, an expired
context, an unreachable registry, or a failed reservation all refuse. Disarmed is a stated
posture, not a silent fallback.

Public surface
--------------
:class:`AdmissionRefused` / :class:`AdmissionContextError` · :class:`LeaseContext` ·
:func:`current_context` · :func:`bind_context` · :func:`admission_required` ·
:func:`require_admission` · :func:`validate_lease_fields` · :data:`LEASE_REQUEST_FIELDS`.
"""

from __future__ import annotations

import math
import os
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

# ── The env-var contract (the cross-process transport) ───────────────────────────────────────

#: The arming switch. ``"1"``/``"true"``/``"yes"``/``"on"`` arms the gate; anything else
#: (including unset) leaves it disarmed. Follows the repo's ``FINOPS_*`` opt-in convention
#: (``FINOPS_KB_WRITE``, ``FINOPS_ACTUATION_ARMED``) rather than inventing a new one.
ADMISSION_REQUIRED_ENV = "FINOPS_ADMISSION_REQUIRED"

#: The run this admission was granted to. Also the ``run_id`` on every one of its leases.
RUN_ID_ENV = "FINOPS_ADMISSION_RUN_ID"

#: The model the admission was priced for. A mismatch at invocation time is a refusal: an
#: admission for haiku is not an admission for deepseek-v4-pro.
MODEL_ENV = "FINOPS_ADMISSION_MODEL"

#: The budget lease's id (spend headroom — USD or window percentage points).
BUDGET_LEASE_ENV = "FINOPS_BUDGET_LEASE_ID"

#: The concurrency leases' ids, comma-separated (one per enforced scope: fleet, provider, …).
CONCURRENCY_LEASE_ENV = "FINOPS_CONCURRENCY_LEASE_IDS"

#: Dollars reserved. Legitimately ``0.0`` for a subscription run; never a stand-in for "unknown".
RESERVED_USD_ENV = "FINOPS_ADMISSION_RESERVED_USD"

#: The dollar ceiling in force. Empty string ⇒ ``None`` ⇒ subscription class (no dollar cap).
HARD_CAP_USD_ENV = "FINOPS_ADMISSION_HARD_CAP_USD"

#: Epoch seconds (UTC) at which the admission's earliest lease expires.
EXPIRES_AT_ENV = "FINOPS_ADMISSION_EXPIRES_AT"

#: Every env key this module owns — the exact set :meth:`LeaseContext.to_env` writes and
#: :func:`bind_context` restores. Kept as one tuple so a caller can scrub the whole block
#: (a child that must NOT inherit the parent's admission unsets exactly these).
ADMISSION_ENV_KEYS: tuple[str, ...] = (
    RUN_ID_ENV,
    MODEL_ENV,
    BUDGET_LEASE_ENV,
    CONCURRENCY_LEASE_ENV,
    RESERVED_USD_ENV,
    HARD_CAP_USD_ENV,
    EXPIRES_AT_ENV,
)

#: The lease fields a spawn/enqueue request carries, in the work order's own wording:
#: "the spawn request gains the lease fields (reserved_cost_usd, hard_cap_usd, budget_lease_id,
#: concurrency_lease_id, expires_at)". :func:`validate_lease_fields` is the pure checker for
#: exactly this block, shared by ``scripts/fleet/spawn_wrapper.py`` (step 6) and the controller
#: so the two surfaces can never drift.
LEASE_REQUEST_FIELDS: tuple[str, ...] = (
    "reserved_cost_usd",
    "hard_cap_usd",
    "budget_lease_id",
    "concurrency_lease_id",
    "expires_at",
)

#: A ``FINOPS_*`` flag is set only on an explicit truthy value — the convention
#: ``scripts/fleet/spawn_wrapper.py`` already uses for the write flags.
_TRUTHY = frozenset({"1", "true", "True", "yes", "on"})


# ── Errors ───────────────────────────────────────────────────────────────────────────────────


class AdmissionRefused(RuntimeError):  # noqa: N818 — the domain verb, see the class docstring
    """Base class for every admission refusal that a tier-0/tier-1 caller can catch.

    ``control.admission.AdmissionDenied`` inherits from BOTH this class and
    ``control.lease_registry.AdmissionError``, so:

    * ``except AdmissionRefused`` (importable from any plane) catches *every* refusal —
      the bypass guard's and the controller's alike. This is what ``runtime`` and ``adapters``
      catch, because they may not import ``control``.
    * ``except AdmissionError`` (tier 2) catches the lease-layer family — cap denials, class
      boundary violations, Redis unavailability — plus controller denials.

    One refusal, two vocabularies, no duplicated hierarchy.

    (``N818`` waived: this is the base of a *refusal* family whose members read as verbs at the
    call site — ``except AdmissionRefused`` says what happened. Its concrete subclass
    :class:`AdmissionContextError` does carry the suffix, as does every error in the lease
    layer; only the two verb-named bases are exempt.)
    """


class AdmissionContextError(AdmissionRefused):
    """The gate is armed but no valid, unexpired admission context is present.

    This is the *bypass* refusal specifically: someone called a paid backend without going
    through the controller, or with an admission that has since expired, or with an admission
    granted for a different model. It is distinct from a controller denial (the gate was asked
    and said no) because the operator response differs — a bypass is a wiring bug, a denial is
    a budget fact.
    """


# ── The value object ─────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LeaseContext:
    """The portable proof of an admission — what crosses a process or container boundary.

    Immutable by construction: an admission is granted, carried, and released; it is never
    edited in flight. Everything here is a projection of the leases the controller took, so a
    context can always be traced back to the exact rows in the lease registry.
    """

    #: The admitted run's id — the join key to the registry's leases and the ledger's records.
    run_id: str
    #: The ``provider/model`` id the admission was priced for.
    model: str
    #: The budget lease's id (spend headroom).
    budget_lease_id: str
    #: One concurrency lease id per enforced scope. May be empty when only budget is enforced.
    concurrency_lease_ids: tuple[str, ...] = ()
    #: Dollars reserved. ``0.0`` is legal and *meaningful* for a subscription run (marginal
    #: dollar cost inside the plan is zero) — it is never a stand-in for an unmeasured cost.
    reserved_cost_usd: float = 0.0
    #: The dollar ceiling in force, or ``None`` for a subscription run (which has no dollar
    #: cap by construction). ``None`` on a run that reserved dollars is a missing field.
    hard_cap_usd: float | None = None
    #: Epoch seconds (UTC): the earliest expiry among this admission's leases.
    expires_at: float = 0.0

    # -- lifetime ---------------------------------------------------------------------------

    def is_expired(self, now: float | None = None) -> bool:
        """True once the earliest lease has decayed.

        ``>=`` so a zero-TTL admission is born dead, matching ``Lease.is_expired``. Work that
        continues past this point is exactly what phase 4 quarantines.
        """
        return (time.time() if now is None else now) >= self.expires_at

    # -- transports -------------------------------------------------------------------------

    def to_env(self) -> dict[str, str]:
        """Serialise to the env-var block a child process/container inherits.

        Only :data:`ADMISSION_ENV_KEYS` are produced — never the arming flag, which is the
        parent environment's business and must not be forged by a context.
        """
        return {
            RUN_ID_ENV: self.run_id,
            MODEL_ENV: self.model,
            BUDGET_LEASE_ENV: self.budget_lease_id,
            CONCURRENCY_LEASE_ENV: ",".join(self.concurrency_lease_ids),
            RESERVED_USD_ENV: repr(float(self.reserved_cost_usd)),
            # Empty string, not "None": the absence of a dollar cap is a *subscription* fact,
            # and round-tripping it through a literal "None" would make the parse ambiguous
            # with a genuinely malformed value.
            HARD_CAP_USD_ENV: "" if self.hard_cap_usd is None else repr(float(self.hard_cap_usd)),
            EXPIRES_AT_ENV: repr(float(self.expires_at)),
        }

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> LeaseContext | None:
        """Rebuild a context from an environment block, or ``None`` when none is present.

        "Present" means the two identifying keys (:data:`RUN_ID_ENV`, :data:`BUDGET_LEASE_ENV`)
        are both non-empty. A *partially* populated block is NOT treated as absent — it raises
        :class:`AdmissionContextError`, because a half-written admission is evidence of a bug,
        and silently reading it as "no admission" would turn that bug into an unpoliced run.
        """
        source = os.environ if env is None else env
        run_id = (source.get(RUN_ID_ENV) or "").strip()
        budget_lease_id = (source.get(BUDGET_LEASE_ENV) or "").strip()
        if not run_id and not budget_lease_id:
            # Neither key set: no admission was ever stamped here. That is a legitimate state
            # (the gate may be disarmed); the caller decides whether it is acceptable.
            if not any((source.get(k) or "").strip() for k in ADMISSION_ENV_KEYS):
                return None
            raise AdmissionContextError(
                f"a partial admission env block is present ("
                f"{sorted(k for k in ADMISSION_ENV_KEYS if (source.get(k) or '').strip())}) "
                f"but {RUN_ID_ENV} and {BUDGET_LEASE_ENV} are both empty — refusing to read a "
                f"half-written admission as 'no admission'"
            )
        if not run_id or not budget_lease_id:
            raise AdmissionContextError(
                f"incomplete admission env block: {RUN_ID_ENV}={run_id!r} "
                f"{BUDGET_LEASE_ENV}={budget_lease_id!r} — both are required"
            )

        raw_caps = (source.get(HARD_CAP_USD_ENV) or "").strip()
        try:
            reserved = float((source.get(RESERVED_USD_ENV) or "0").strip() or "0")
            hard_cap = float(raw_caps) if raw_caps else None
            expires_at = float((source.get(EXPIRES_AT_ENV) or "0").strip() or "0")
        except ValueError as exc:
            raise AdmissionContextError(
                f"admission env block holds a non-numeric amount: {exc} — a cost that will not "
                f"parse is an error, never 0.0"
            ) from exc

        concurrency = tuple(
            part.strip()
            for part in (source.get(CONCURRENCY_LEASE_ENV) or "").split(",")
            if part.strip()
        )
        return cls(
            run_id=run_id,
            model=(source.get(MODEL_ENV) or "").strip(),
            budget_lease_id=budget_lease_id,
            concurrency_lease_ids=concurrency,
            reserved_cost_usd=reserved,
            hard_cap_usd=hard_cap,
            expires_at=expires_at,
        )

    def to_request_fields(self) -> dict[str, Any]:
        """Project to the :data:`LEASE_REQUEST_FIELDS` block a spawn/enqueue request carries.

        ``concurrency_lease_id`` is singular in the request vocabulary (the work order's own
        wording) and holds the comma-joined ids, so one field carries however many scopes were
        enforced without changing the request schema.
        """
        return {
            "reserved_cost_usd": float(self.reserved_cost_usd),
            "hard_cap_usd": None if self.hard_cap_usd is None else float(self.hard_cap_usd),
            "budget_lease_id": self.budget_lease_id,
            "concurrency_lease_id": ",".join(self.concurrency_lease_ids),
            "expires_at": float(self.expires_at),
        }

    @classmethod
    def from_request_fields(
        cls, request: Mapping[str, Any], *, run_id: str = "", model: str = ""
    ) -> LeaseContext:
        """Rebuild a context from a request's lease block (the inverse of the above).

        Raises :class:`AdmissionContextError` when the block is invalid, so a caller that
        reaches this point already knows the fields are structurally sound.
        """
        errors = validate_lease_fields(request, required=True)
        if errors:
            raise AdmissionContextError("invalid lease block: " + "; ".join(errors))
        raw_conc = request.get("concurrency_lease_id") or ""
        cap = request.get("hard_cap_usd")
        return cls(
            run_id=run_id or str(request.get("run_id") or ""),
            model=model or str(request.get("model") or ""),
            budget_lease_id=str(request["budget_lease_id"]),
            concurrency_lease_ids=tuple(
                p.strip() for p in str(raw_conc).split(",") if p.strip()
            ),
            reserved_cost_usd=float(request["reserved_cost_usd"]),
            hard_cap_usd=None if cap is None else float(cap),
            expires_at=float(request["expires_at"]),
        )

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe projection (for ledgers, flags, and the Control Room's admission board)."""
        return {
            "run_id": self.run_id,
            "model": self.model,
            "budget_lease_id": self.budget_lease_id,
            "concurrency_lease_ids": list(self.concurrency_lease_ids),
            "reserved_cost_usd": self.reserved_cost_usd,
            "hard_cap_usd": self.hard_cap_usd,
            "expires_at": self.expires_at,
        }


# ── The in-process carrier ───────────────────────────────────────────────────────────────────

#: The current admission for this thread/task. ``None`` means "nothing admitted here" — which
#: is a refusal when the gate is armed, and irrelevant when it is not.
_CURRENT: ContextVar[LeaseContext | None] = ContextVar(
    "agentic_dynamics_admission_context", default=None
)


def current_context(env: Mapping[str, str] | None = None) -> LeaseContext | None:
    """The admission in force here: the ContextVar first, then the environment block.

    The ordering matters. An in-process ``bind_context`` is the most specific statement
    available ("this call is running inside *that* admission"), so it wins; the environment is
    the inherited fallback for a child process whose parent stamped the launch envelope.
    """
    ctx = _CURRENT.get()
    if ctx is not None:
        return ctx
    return LeaseContext.from_env(env)


@contextmanager
def bind_context(
    context: LeaseContext, *, environ: dict[str, str] | None = None
) -> Iterator[LeaseContext]:
    """Make ``context`` the admission in force for the duration of the block.

    Sets **both** carriers — the ContextVar (so in-process calls see it) and the process
    environment (so any subprocess launched inside the block inherits it) — and restores both
    exactly on exit, including on an exception. The environment is restored key by key to its
    prior value, so a nested bind cannot leak the inner admission to the outer scope.

    ``environ`` is injectable purely so tests can drive the env half without mutating the real
    process environment.
    """
    target = os.environ if environ is None else environ
    token = _CURRENT.set(context)
    #: ``None`` records "this key was previously absent", which restores to a *deletion* rather
    #: than to an empty string — an empty string is a different (and invalid) state.
    previous: dict[str, str | None] = {k: target.get(k) for k in ADMISSION_ENV_KEYS}
    try:
        target.update(context.to_env())
        yield context
    finally:
        _CURRENT.reset(token)
        for key, value in previous.items():
            if value is None:
                target.pop(key, None)
            else:
                target[key] = value


# ── The guard ────────────────────────────────────────────────────────────────────────────────


def admission_required(env: Mapping[str, str] | None = None) -> bool:
    """Is the gate armed? (``FINOPS_ADMISSION_REQUIRED`` truthy.)

    See the module docstring for why this defaults to *off*: the caps that make the gate
    grant-capable are not installed yet, and the freeze-exit decision is the operator's.
    """
    source = os.environ if env is None else env
    return str(source.get(ADMISSION_REQUIRED_ENV, "")).strip() in _TRUTHY


def require_admission(
    model: str = "",
    *,
    env: Mapping[str, str] | None = None,
    now: float | None = None,
) -> LeaseContext | None:
    """Refuse an unadmitted paid invocation when the gate is armed.

    This is the **bypass detector** the work order asks for: called at the top of
    ``adapters.backends.run_agentic``, it makes "call the backend directly, skip the
    controller" a detectable, refusing event rather than a silent success.

    Returns the context in force (``None`` when the gate is disarmed and nothing is bound), so
    a caller can also use it to read the admission it is running under.

    Refuses with :class:`AdmissionContextError` when the gate is armed and:

    * no context is present anywhere (the bypass), or
    * the context has expired (the claim is gone; phase 4 quarantines what it produced), or
    * the context names a different model than the one about to be invoked — an admission is
      priced per provider class, so reusing haiku's admission for ``deepseek-v4-pro`` would
      spend real dollars against a window reservation.

    When the gate is disarmed this function does not raise, but it still *parses* whatever
    context is present — a malformed block is a bug worth surfacing either way.
    """
    context = current_context(env)
    if not admission_required(env):
        return context

    if context is None:
        raise AdmissionContextError(
            f"admission is required ({ADMISSION_REQUIRED_ENV}=1) but no lease context is "
            f"present for model {model!r} — this invocation bypassed the admission controller. "
            f"Admit through control.admission.AdmissionController.admit() (or run under "
            f"control.admission.admitted()) before invoking a paid backend."
        )

    if context.is_expired(now):
        raise AdmissionContextError(
            f"admission for run {context.run_id!r} expired at {context.expires_at} — its "
            f"leases are no longer outstanding, so this invocation is unbudgeted. Re-admit "
            f"(and expect the work already produced under the expired lease to be quarantined)."
        )

    # An empty ``model`` on either side means "not stated" and is not evidence of a mismatch:
    # the caller may not know the resolved id yet, and older envelopes predate MODEL_ENV.
    if model and context.model and model != context.model:
        raise AdmissionContextError(
            f"admission for run {context.run_id!r} was granted for model {context.model!r}, "
            f"not {model!r} — an admission is priced per provider class and is not "
            f"transferable between models."
        )
    return context


# ── The pure structural validator (shared by the fleet wrapper and the controller) ───────────


def _is_real_number(value: Any) -> bool:
    """True for a finite int/float that is not a bool.

    ``bool`` is excluded deliberately: ``True`` is an ``int`` in Python, and a ``True`` that
    slipped into a cost field would silently read as ``$1``. NaN/inf are excluded because they
    defeat every subsequent comparison — ``nan > cap`` is ``False``, which would *admit*.
    """
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def validate_lease_fields(
    request: Mapping[str, Any], *, required: bool = True
) -> list[str]:
    """Validate a request's :data:`LEASE_REQUEST_FIELDS` block. Empty list = valid.

    Pure and dependency-free (no Redis, no ``control`` import) so
    ``scripts/fleet/spawn_wrapper.py`` can run it as validation step 6 while keeping its
    stated invariant that validation never requires ``redis``.

    Structural only — it answers "is this lease block well-formed and still live?", never "is
    this lease actually outstanding in the registry?". The second question needs the registry
    and is the controller's (``control.admission.AdmissionController.verify``).

    The rules, each one an audit finding made mechanical:

    1. **All five fields or none.** ``required=False`` permits a wholly absent block (the
       pre-arming path), but a *partially* filled block is always an error — a request carrying
       ``reserved_cost_usd`` and no ``budget_lease_id`` looks budgeted and is not.
    2. **Ids are non-empty strings.** ``budget_lease_id`` is mandatory;
       ``concurrency_lease_id`` may be the empty string (a run that enforces budget only).
    3. **``reserved_cost_usd`` is a finite, non-negative number** — never ``None``, never a
       string, never NaN. A missing cost is an error, not ``0.0``.
    4. **The dollar cap follows the provider class.** ``hard_cap_usd is None`` is legal only
       when nothing was reserved (a subscription run); a run reserving dollars must carry a
       positive cap, and the reservation may not exceed it.
    5. **``expires_at`` is a finite epoch-second number.** Liveness itself is checked by the
       caller against its own clock (see ``now``-aware callers), because a validator that
       reads the wall clock is untestable.
    """
    present = [f for f in LEASE_REQUEST_FIELDS if f in request]
    if not present:
        if required:
            return [
                f"lease block missing entirely: expected {list(LEASE_REQUEST_FIELDS)} "
                f"(admission is armed, so every spend request must carry its leases)"
            ]
        return []

    errors: list[str] = []
    missing = [f for f in LEASE_REQUEST_FIELDS if f not in request]
    if missing:
        errors.append(
            f"partial lease block: {missing} absent while {present} present — a half-declared "
            f"lease is never treated as no lease"
        )
        return errors

    budget_lease_id = request.get("budget_lease_id")
    if not isinstance(budget_lease_id, str) or not budget_lease_id.strip():
        errors.append(
            f"budget_lease_id must be a non-empty string (got {budget_lease_id!r}) — an "
            f"admitted run holds at least a budget lease"
        )

    concurrency_lease_id = request.get("concurrency_lease_id")
    if not isinstance(concurrency_lease_id, str):
        errors.append(
            f"concurrency_lease_id must be a string, possibly empty (got "
            f"{concurrency_lease_id!r})"
        )

    reserved = request.get("reserved_cost_usd")
    if not _is_real_number(reserved) or float(reserved) < 0:  # type: ignore[arg-type]
        errors.append(
            f"reserved_cost_usd must be a finite non-negative number (got {reserved!r}) — a "
            f"missing cost is an error, never 0.0"
        )
        reserved = None

    cap = request.get("hard_cap_usd")
    if cap is None:
        # No dollar cap ⇒ subscription class ⇒ nothing may have been reserved in dollars.
        if reserved is not None and float(reserved) > 0:
            errors.append(
                f"hard_cap_usd is None (subscription class, no dollar cap) but "
                f"reserved_cost_usd={reserved!r} > 0 — dollars were reserved without a ceiling"
            )
    elif not _is_real_number(cap) or float(cap) <= 0:
        errors.append(
            f"hard_cap_usd must be a positive number or None (got {cap!r}) — None means "
            f"'subscription class', never 'no limit'"
        )
    elif reserved is not None and float(reserved) > float(cap):
        errors.append(
            f"reserved_cost_usd {reserved} exceeds hard_cap_usd {cap}"
        )

    expires_at = request.get("expires_at")
    if not _is_real_number(expires_at):
        errors.append(
            f"expires_at must be finite epoch seconds (got {expires_at!r}) — a lease with no "
            f"expiry can wedge a scope forever"
        )
    return errors
