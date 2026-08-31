"""Admission controller + context tests — the gate, driven in both directions.

Both directions means: for every rule the gate states, one test proves it *admits* what it
should and one proves it *refuses* what it should. A gate that only ever says yes is untested,
and a gate that only ever says no is a freeze.

Layout mirrors the implementation's own split:

* ``core.admission_context`` — the portable proof (env round-trip, expiry, the pure validator,
  the bypass guard). No Redis anywhere: this half is stdlib-only by construction.
* ``control.admission`` — the decision (reserve both, refuse if either fails, leave nothing
  outstanding on a refusal, release on settle).

Transport is faked and policy is not: :class:`FakeRedis` from ``tests/test_lease_registry.py``
implements real ``WATCH``/``MULTI``/``EXEC`` semantics, so the registry's actual compare-and-set
loop runs under the controller and only the wire is simulated. The entry-point wiring
(enqueue/worker/spawn/runner/adapters) is exercised in ``tests/test_admission_entry_points.py``.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from agentic_dynamics.control.admission import (
    DEFAULT_WINDOW_RESERVE_PERCENT,
    HARD_CAP_USD_ENV,
    RESERVE_USD_ENV,
    WINDOW_RESERVE_PERCENT_ENV,
    Admission,
    AdmissionController,
    AdmissionDenied,
    AdmissionRequest,
    admission_board,
    admitted,
    concurrency_admitted,
    make_phase_admission,
    resolve_hard_cap_usd,
    resolve_reservation,
)
from agentic_dynamics.control.lease_registry import (
    AdmissionError,
    CostSource,
    LeaseKind,
    LeaseRegistry,
    LeaseScope,
    ProviderClass,
    ScopeKind,
)
from agentic_dynamics.core.admission_context import (
    ADMISSION_ENV_KEYS,
    ADMISSION_REQUIRED_ENV,
    BUDGET_LEASE_ENV,
    EXPIRES_AT_ENV,
    LEASE_REQUEST_FIELDS,
    MODEL_ENV,
    RUN_ID_ENV,
    AdmissionContextError,
    AdmissionRefused,
    LeaseContext,
    admission_required,
    bind_context,
    current_context,
    require_admission,
    validate_lease_fields,
)

# The fake transport lives with the registry's own suite. Dual-path import: pytest puts the
# ``tests/`` directory itself on ``sys.path`` for a direct run, while ``conftest.py`` puts the
# repo root there — the same convention ``scripts/_bootstrap`` uses.
try:
    from tests.test_lease_registry import Clock, FakeRedis
except ImportError:  # pragma: no cover - direct-run path
    from test_lease_registry import Clock, FakeRedis

SUBSCRIPTION_MODEL = "anthropic/claude-opus-5"
PER_TOKEN_MODEL = "deepseek/deepseek-v4-flash"
PRO_MODEL = "deepseek/deepseek-v4-pro"

FLEET = LeaseScope(ScopeKind.FLEET, "ladder")
CAMPAIGN = LeaseScope(ScopeKind.CAMPAIGN, "admission_leases")
ANTHROPIC = LeaseScope(ScopeKind.PROVIDER, "anthropic")
DEEPSEEK = LeaseScope(ScopeKind.PROVIDER, "deepseek")


# ── Fixtures ─────────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def registry(clock: Clock) -> LeaseRegistry:
    """A registry on the fake transport, with deterministic time and numbered lease ids."""
    counter = iter(f"{i:04d}" for i in range(1, 10_000))
    return LeaseRegistry(FakeRedis(), now_fn=clock, id_fn=lambda: next(counter))


@pytest.fixture
def capped_registry(registry: LeaseRegistry) -> LeaseRegistry:
    """A registry with generous caps installed on every scope these tests touch.

    Caps are installed explicitly rather than defaulted because the registry has no default
    cap by design ("an uncapped scope admits nothing"). A fixture that quietly supplied one
    would hide the very behaviour several tests below assert.
    """
    registry.set_cap(LeaseKind.BUDGET, ANTHROPIC, 100.0)     # window percentage points
    registry.set_cap(LeaseKind.BUDGET, DEEPSEEK, 50.0)       # dollars
    registry.set_cap(LeaseKind.BUDGET, CAMPAIGN, 100.0)
    registry.set_cap(LeaseKind.CONCURRENCY, FLEET, 6.0)      # the β_tokens knee
    registry.set_cap(LeaseKind.CONCURRENCY, ANTHROPIC, 4.0)
    registry.set_cap(LeaseKind.CONCURRENCY, DEEPSEEK, 4.0)
    registry.set_cap(LeaseKind.CONCURRENCY, CAMPAIGN, 3.0)
    return registry


@pytest.fixture
def controller(capped_registry: LeaseRegistry, clock: Clock) -> AdmissionController:
    return AdmissionController(capped_registry, now_fn=clock)


@pytest.fixture
def armed():
    """Arm the gate for the duration of a test, and disarm it again afterwards."""
    with patch.dict(os.environ, {ADMISSION_REQUIRED_ENV: "1"}):
        yield


@pytest.fixture(autouse=True)
def clean_admission_env():
    """No test may inherit another's admission env block (or the developer's shell's).

    Autouse because a leaked ``FINOPS_BUDGET_LEASE_ID`` would make a bypass test pass for the
    wrong reason — the guard would find a context and admit, and the test asserting a refusal
    would be the one that broke.
    """
    saved = {k: os.environ.pop(k, None) for k in (*ADMISSION_ENV_KEYS, ADMISSION_REQUIRED_ENV)}
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def subscription_request(**overrides) -> AdmissionRequest:
    """A valid subscription-class request (the common case: opus/sonnet on the plan)."""
    base = {
        "run_id": "run-1",
        "model": SUBSCRIPTION_MODEL,
        "worktree_identity": "wt_admission_leases",
        "result_namespace": "self-wt_admission_leases",
        "budget_scope": ANTHROPIC,
        "concurrency_scopes": (FLEET,),
    }
    base.update(overrides)
    return AdmissionRequest(**base)


def per_token_request(**overrides) -> AdmissionRequest:
    """A valid per-token request: dollars stated, provenance stated, ceiling stated."""
    base = {
        "run_id": "run-ds",
        "model": PER_TOKEN_MODEL,
        "worktree_identity": "wt_admission_leases",
        "result_namespace": "self-wt_admission_leases",
        "amount": 2.50,
        "cost_source": CostSource.ESTIMATED,
        "hard_cap_usd": 10.0,
        "budget_scope": DEEPSEEK,
        "concurrency_scopes": (FLEET,),
    }
    base.update(overrides)
    return AdmissionRequest(**base)


# ═══════════════════════════════════════════════════════════════════════════════════════════
# core.admission_context — the portable proof
# ═══════════════════════════════════════════════════════════════════════════════════════════


def test_context_round_trips_through_the_environment():
    """A context serialised into a launch envelope comes back identical."""
    ctx = LeaseContext(
        run_id="run-1",
        model=SUBSCRIPTION_MODEL,
        budget_lease_id="bud_0001",
        concurrency_lease_ids=("con_0002", "con_0003"),
        reserved_cost_usd=0.0,
        hard_cap_usd=None,
        expires_at=1_003_600.0,
    )
    assert LeaseContext.from_env(ctx.to_env()) == ctx


def test_context_round_trips_a_dollar_cap():
    """The per-token half of the round trip: a real ceiling survives, it does not become None."""
    ctx = LeaseContext(
        run_id="run-ds",
        model=PER_TOKEN_MODEL,
        budget_lease_id="bud_0001",
        reserved_cost_usd=2.5,
        hard_cap_usd=10.0,
        expires_at=1_003_600.0,
    )
    assert LeaseContext.from_env(ctx.to_env()).hard_cap_usd == 10.0


def test_absent_env_block_is_no_context_not_an_error():
    """A clean environment legitimately means "nothing admitted here"."""
    assert LeaseContext.from_env({}) is None
    assert current_context({}) is None


def test_partial_env_block_is_an_error_not_an_absence():
    """A half-written admission is a bug, and reading it as "no admission" would hide it."""
    with pytest.raises(AdmissionContextError, match="partial admission env block"):
        LeaseContext.from_env({EXPIRES_AT_ENV: "1000.0"})
    with pytest.raises(AdmissionContextError, match="incomplete admission env block"):
        LeaseContext.from_env({RUN_ID_ENV: "run-1"})


def test_unparseable_amount_in_the_env_block_is_an_error_never_zero():
    """The audit's collapse-to-zero, at the transport layer: a bad number refuses."""
    env = LeaseContext(
        run_id="r", model="m", budget_lease_id="b", expires_at=1.0
    ).to_env()
    env["FINOPS_ADMISSION_RESERVED_USD"] = "not-a-number"
    with pytest.raises(AdmissionContextError, match="non-numeric"):
        LeaseContext.from_env(env)


def test_bind_context_sets_both_carriers_and_restores_both():
    """In-process (ContextVar) and cross-process (environ), bound and unbound together."""
    ctx = LeaseContext(run_id="r", model="m", budget_lease_id="b", expires_at=9e9)
    assert current_context() is None
    with bind_context(ctx):
        assert current_context() == ctx           # the ContextVar
        assert os.environ[BUDGET_LEASE_ENV] == "b"  # the environment
    assert current_context() is None
    assert BUDGET_LEASE_ENV not in os.environ


def test_bind_context_restores_the_environment_even_when_the_body_raises():
    """A crashed run must not leave its admission stamped on the process for the next one."""
    ctx = LeaseContext(run_id="r", model="m", budget_lease_id="b", expires_at=9e9)
    with pytest.raises(ValueError), bind_context(ctx):
        raise ValueError("phase blew up")
    assert BUDGET_LEASE_ENV not in os.environ
    assert current_context() is None


def test_nested_bind_restores_the_outer_admission_not_a_deletion():
    """A nested admission must not leak, and must not erase the one it was nested inside."""
    outer = LeaseContext(run_id="outer", model="m", budget_lease_id="b-out", expires_at=9e9)
    inner = LeaseContext(run_id="inner", model="m", budget_lease_id="b-in", expires_at=9e9)
    with bind_context(outer):
        with bind_context(inner):
            assert os.environ[RUN_ID_ENV] == "inner"
        assert os.environ[RUN_ID_ENV] == "outer"


def test_context_expiry_is_inclusive():
    """``>=``, so a zero-TTL admission is born dead (matching ``Lease.is_expired``)."""
    ctx = LeaseContext(run_id="r", model="m", budget_lease_id="b", expires_at=1000.0)
    assert not ctx.is_expired(999.9)
    assert ctx.is_expired(1000.0)
    assert ctx.is_expired(1000.1)


# ── the bypass guard (the work order's "a bypass attempt is detectable") ─────────────────────


def test_disarmed_gate_admits_an_unadmitted_call():
    """Default posture: the gate is off, and nothing changes for an existing caller."""
    assert not admission_required()
    assert require_admission(SUBSCRIPTION_MODEL) is None


def test_armed_gate_refuses_an_unadmitted_call(armed):
    """THE bypass detector: armed + no context = refusal."""
    with pytest.raises(AdmissionContextError, match="bypassed the admission controller"):
        require_admission(SUBSCRIPTION_MODEL)


def test_armed_gate_admits_a_live_context(armed):
    """The other direction: a live admission passes the same guard."""
    ctx = LeaseContext(
        run_id="r", model=SUBSCRIPTION_MODEL, budget_lease_id="b", expires_at=9e9
    )
    with bind_context(ctx):
        assert require_admission(SUBSCRIPTION_MODEL) == ctx


def test_armed_gate_refuses_an_expired_context(armed):
    """The claim is gone: work continuing past it is unbudgeted (and phase 4's quarantine input)."""
    ctx = LeaseContext(run_id="r", model=SUBSCRIPTION_MODEL, budget_lease_id="b", expires_at=500.0)
    with bind_context(ctx), pytest.raises(AdmissionContextError, match="expired"):
        require_admission(SUBSCRIPTION_MODEL, now=501.0)


def test_armed_gate_refuses_a_context_granted_for_another_model(armed):
    """An admission is priced per provider class and is not transferable.

    The concrete attack: hold a subscription admission (window points, no dollar cap) and use
    it to invoke a per-token model, spending real wallet dollars against a window reservation.
    """
    ctx = LeaseContext(
        run_id="r", model=SUBSCRIPTION_MODEL, budget_lease_id="b", expires_at=9e9
    )
    with bind_context(ctx), pytest.raises(AdmissionContextError, match="not transferable"):
        require_admission(PRO_MODEL)


def test_env_carried_context_satisfies_the_guard_in_a_child_process(armed):
    """The cross-process half: a child sees the parent's admission through the environment only.

    Simulated by writing the env block WITHOUT binding the ContextVar — which is exactly the
    state a freshly-exec'd subprocess is in.
    """
    ctx = LeaseContext(
        run_id="r", model=SUBSCRIPTION_MODEL, budget_lease_id="b", expires_at=9e9
    )
    with patch.dict(os.environ, ctx.to_env()):
        assert require_admission(SUBSCRIPTION_MODEL) == ctx


# ── the pure lease-block validator (shared with the fleet wrapper) ───────────────────────────


def test_valid_lease_block_passes():
    ctx = LeaseContext(
        run_id="r", model="m", budget_lease_id="b", concurrency_lease_ids=("c",),
        reserved_cost_usd=1.0, hard_cap_usd=5.0, expires_at=9e9,
    )
    assert validate_lease_fields(ctx.to_request_fields()) == []


def test_missing_lease_block_is_an_error_when_required_and_fine_when_not():
    assert validate_lease_fields({}, required=False) == []
    errors = validate_lease_fields({}, required=True)
    assert errors and "missing entirely" in errors[0]


def test_partial_lease_block_is_always_an_error():
    """Even unarmed. A request that LOOKS budgeted and is not is worse than one that plainly isn't."""
    errors = validate_lease_fields({"budget_lease_id": "b"}, required=False)
    assert errors and "partial lease block" in errors[0]


@pytest.mark.parametrize(
    "bad, fragment",
    [
        ({"reserved_cost_usd": None}, "never 0.0"),
        ({"reserved_cost_usd": "1.00"}, "never 0.0"),
        ({"reserved_cost_usd": True}, "never 0.0"),        # bool is an int in Python
        ({"reserved_cost_usd": float("nan")}, "never 0.0"),  # nan > cap is False → would admit
        ({"reserved_cost_usd": -1.0}, "non-negative"),
        ({"budget_lease_id": ""}, "budget_lease_id"),
        ({"hard_cap_usd": 0.0}, "positive number or None"),
        ({"hard_cap_usd": 0.5}, "exceeds hard_cap_usd"),   # reserved 1.0 > cap 0.5
        ({"hard_cap_usd": None}, "without a ceiling"),     # dollars reserved, no cap
        ({"expires_at": None}, "epoch seconds"),
    ],
)
def test_malformed_lease_block_is_refused_field_by_field(bad, fragment):
    """Each field's own failure mode, named. None of them may degrade to a default."""
    block = {
        "reserved_cost_usd": 1.0,
        "hard_cap_usd": 5.0,
        "budget_lease_id": "b",
        "concurrency_lease_id": "c",
        "expires_at": 9e9,
    }
    block.update(bad)
    errors = validate_lease_fields(block)
    assert errors, f"{bad} was accepted"
    assert any(fragment in e for e in errors), f"{bad} -> {errors}"


def test_subscription_block_may_legitimately_have_no_dollar_cap():
    """``hard_cap_usd=None`` with ``reserved_cost_usd=0.0`` is the subscription class, not a hole."""
    assert validate_lease_fields({
        "reserved_cost_usd": 0.0,
        "hard_cap_usd": None,
        "budget_lease_id": "b",
        "concurrency_lease_id": "",
        "expires_at": 9e9,
    }) == []


def test_lease_request_fields_are_the_work_orders_five():
    """The vocabulary is pinned: the fleet wrapper's step 6 and the controller share this list."""
    assert set(LEASE_REQUEST_FIELDS) == {
        "reserved_cost_usd", "hard_cap_usd", "budget_lease_id",
        "concurrency_lease_id", "expires_at",
    }


# ═══════════════════════════════════════════════════════════════════════════════════════════
# resolve_reservation — where "how much?" is answered, or refused
# ═══════════════════════════════════════════════════════════════════════════════════════════


def test_subscription_reservation_defaults_to_a_stated_window_share():
    amount, source = resolve_reservation(SUBSCRIPTION_MODEL, env={})
    assert amount == DEFAULT_WINDOW_RESERVE_PERCENT
    assert source is CostSource.ESTIMATED


def test_subscription_reservation_honours_the_operator_override():
    amount, _ = resolve_reservation(SUBSCRIPTION_MODEL, env={WINDOW_RESERVE_PERCENT_ENV: "2.5"})
    assert amount == 2.5


def test_unstated_per_token_cost_resolves_to_unknown_not_zero():
    """The audit's rule at its origin: nothing here invents a dollar figure."""
    amount, source = resolve_reservation(PER_TOKEN_MODEL, env={})
    assert source is CostSource.UNKNOWN
    # The 0.0 is the *amount*; the UNKNOWN beside it is what makes the reservation refuse. The
    # pair, not the number, is the answer — that is precisely the five-states-collapsed fix.
    assert amount == 0.0


def test_stated_per_token_cost_is_estimated():
    amount, source = resolve_reservation(PER_TOKEN_MODEL, env={RESERVE_USD_ENV: "3.25"})
    assert (amount, source) == (3.25, CostSource.ESTIMATED)


def test_unparseable_reservation_env_refuses_rather_than_defaulting():
    with pytest.raises(AdmissionDenied, match="not a dollar amount"):
        resolve_reservation(PER_TOKEN_MODEL, env={RESERVE_USD_ENV: "cheap"})
    with pytest.raises(AdmissionDenied, match="not a number"):
        resolve_reservation(SUBSCRIPTION_MODEL, env={WINDOW_RESERVE_PERCENT_ENV: "some"})


def test_subscription_never_gets_a_dollar_cap_even_if_one_is_offered():
    """Provider-class boundary: a subscription plan has no dollar ceiling by construction."""
    assert resolve_hard_cap_usd(SUBSCRIPTION_MODEL, hard_cap_usd=99.0) is None
    assert resolve_hard_cap_usd(PER_TOKEN_MODEL, env={HARD_CAP_USD_ENV: "12.5"}) == 12.5


# ═══════════════════════════════════════════════════════════════════════════════════════════
# AdmissionController.admit — both leases, or neither
# ═══════════════════════════════════════════════════════════════════════════════════════════


def test_admit_takes_both_leases(controller: AdmissionController):
    admission = controller.admit(subscription_request())
    assert isinstance(admission, Admission)
    assert admission.budget_lease.kind is LeaseKind.BUDGET
    assert [lease.kind for lease in admission.concurrency_leases] == [LeaseKind.CONCURRENCY]
    assert len(admission.lease_ids) == 2
    assert controller.registry.outstanding(LeaseKind.BUDGET, ANTHROPIC) == pytest.approx(1.0)
    assert controller.registry.outstanding(LeaseKind.CONCURRENCY, FLEET) == 1.0


def test_admit_records_the_audit_line(controller: AdmissionController):
    """Every field the audit found missing somewhere is present and validated."""
    record = controller.admit(subscription_request()).record.to_dict()
    assert record["run_id"] == "run-1"
    assert record["provider_class"] == ProviderClass.SUBSCRIPTION.value
    assert record["cost_source"] == CostSource.ESTIMATED.value
    assert record["hard_cap_usd"] is None            # subscription: no dollar cap
    assert record["reserved_cost_usd"] == 0.0        # subscription: zero marginal dollars
    assert record["worktree_identity"] == "wt_admission_leases"
    assert record["result_namespace"] == "self-wt_admission_leases"
    assert len(record["lease_ids"]) == 2


def test_admit_a_per_token_run_reserves_real_dollars(controller: AdmissionController):
    admission = controller.admit(per_token_request())
    assert admission.record.reserved_cost_usd == 2.50
    assert admission.record.hard_cap_usd == 10.0
    assert admission.budget_lease.unit == "usd"
    assert controller.registry.outstanding(LeaseKind.BUDGET, DEEPSEEK) == pytest.approx(2.50)


def test_per_token_run_with_unknown_cost_is_denied(controller: AdmissionController):
    """"Unknown cost is never free" — the denial happens BEFORE the money is gone."""
    with pytest.raises(AdmissionDenied, match="cost_source=unknown"):
        controller.admit(per_token_request(amount=None, cost_source=None))


def test_a_denied_admission_leaves_nothing_outstanding(controller: AdmissionController):
    """A refusal never leaks a claim — the headroom is exactly as it was."""
    before_budget = controller.registry.outstanding(LeaseKind.BUDGET, DEEPSEEK)
    before_slots = controller.registry.outstanding(LeaseKind.CONCURRENCY, FLEET)
    with pytest.raises(AdmissionDenied):
        controller.admit(per_token_request(amount=None, cost_source=None))
    assert controller.registry.outstanding(LeaseKind.BUDGET, DEEPSEEK) == before_budget
    assert controller.registry.outstanding(LeaseKind.CONCURRENCY, FLEET) == before_slots


def test_budget_lease_is_released_when_the_concurrency_lease_fails(
    controller: AdmissionController, capped_registry: LeaseRegistry
):
    """The all-or-nothing rule, at the seam the audit's contract is actually about.

    The budget lease succeeds and the concurrency lease then fails; the run must NOT end up
    half-admitted, and the dollars it reserved must not stay claimed.
    """
    capped_registry.set_cap(LeaseKind.CONCURRENCY, FLEET, 1.0)
    first = controller.admit(subscription_request(run_id="run-a"))
    assert first is not None

    budget_before = capped_registry.outstanding(LeaseKind.BUDGET, ANTHROPIC)
    with pytest.raises(AdmissionDenied, match="concurrency reservation failed"):
        controller.admit(subscription_request(run_id="run-b"))
    # The refused run's budget lease was released; only run-a's remains.
    assert capped_registry.outstanding(LeaseKind.BUDGET, ANTHROPIC) == pytest.approx(budget_before)


def test_all_concurrency_scopes_are_required(
    controller: AdmissionController, capped_registry: LeaseRegistry
):
    """"Refuse if either fails", generalised: with several scopes, ANY failure refuses."""
    capped_registry.set_cap(LeaseKind.CONCURRENCY, ANTHROPIC, 0.5)  # the second scope is full
    with pytest.raises(AdmissionDenied, match="concurrency reservation failed"):
        controller.admit(subscription_request(concurrency_scopes=(FLEET, ANTHROPIC)))
    # And the FIRST scope's lease was unwound too — no partial slot is left held.
    assert capped_registry.outstanding(LeaseKind.CONCURRENCY, FLEET) == 0.0


def test_budget_cap_is_enforced(controller: AdmissionController, capped_registry: LeaseRegistry):
    capped_registry.set_cap(LeaseKind.BUDGET, DEEPSEEK, 3.0)
    controller.admit(per_token_request(run_id="a", amount=2.0))
    with pytest.raises(AdmissionDenied, match="budget reservation failed"):
        controller.admit(per_token_request(run_id="b", amount=2.0))


def test_uncapped_scope_admits_nothing(registry: LeaseRegistry):
    """Unconfigured never means unlimited — the registry has no default cap on purpose."""
    controller = AdmissionController(registry)
    with pytest.raises(AdmissionDenied, match="no hard cap"):
        controller.admit(subscription_request())


def test_model_policy_backstop_denies_the_pro_tier(controller: AdmissionController):
    """The class-level guard survives underneath the lease gate (the work order's item (e))."""
    os.environ.pop("FINOPS_ALLOW_PRO", None)
    with pytest.raises(AdmissionDenied, match="per-token pro tier"):
        controller.admit(per_token_request(model=PRO_MODEL))


def test_model_policy_backstop_passes_with_the_opt_in(controller: AdmissionController):
    """And it is a backstop, not a wall: the documented opt-in still works."""
    with patch.dict(os.environ, {"FINOPS_ALLOW_PRO": "1"}):
        admission = controller.admit(per_token_request(model=PRO_MODEL))
    assert admission.record.model == PRO_MODEL


def test_unclassified_provider_is_never_assumed_free(controller: AdmissionController):
    with pytest.raises(AdmissionDenied, match="no declared cost class"):
        controller.admit(subscription_request(model="acme/some-model"))


def test_registry_unreachable_denies(clock: Clock):
    """Fail-closed on infrastructure: telemetry degrades, admission does not."""
    server = FakeRedis()
    server.fail_with = ConnectionError("redis is down")
    controller = AdmissionController(LeaseRegistry(server, now_fn=clock), now_fn=clock)
    with pytest.raises(AdmissionDenied):
        controller.admit(subscription_request())


def test_release_returns_the_headroom(controller: AdmissionController):
    admission = controller.admit(subscription_request())
    assert controller.registry.outstanding(LeaseKind.CONCURRENCY, FLEET) == 1.0
    released = controller.release(admission)
    assert len(released) == 2
    assert controller.registry.outstanding(LeaseKind.CONCURRENCY, FLEET) == 0.0
    assert controller.registry.outstanding(LeaseKind.BUDGET, ANTHROPIC) == 0.0


def test_release_is_idempotent(controller: AdmissionController):
    admission = controller.admit(subscription_request())
    controller.release(admission)
    assert controller.release(admission) == []


def test_expired_leases_stop_counting_against_the_cap(
    controller: AdmissionController, capped_registry: LeaseRegistry, clock: Clock
):
    """The TTL is the guarantee behind release: a crashed holder cannot wedge a scope."""
    capped_registry.set_cap(LeaseKind.CONCURRENCY, FLEET, 1.0)
    controller.admit(subscription_request(run_id="crashed", ttl_seconds=60))
    with pytest.raises(AdmissionDenied):
        controller.admit(subscription_request(run_id="next"))
    clock.advance(61)
    assert controller.admit(subscription_request(run_id="next")) is not None


# ── the admission's own projections ─────────────────────────────────────────────────────────


def test_admission_expires_with_its_shortest_claim(
    controller: AdmissionController, clock: Clock
):
    """``expires_at`` is the MINIMUM: an admission dies with whichever lease dies first."""
    admission = controller.admit(subscription_request(ttl_seconds=900))
    assert admission.expires_at == clock.now + 900
    assert admission.context().expires_at == admission.expires_at


def test_admission_env_names_every_lease(controller: AdmissionController):
    admission = controller.admit(subscription_request(concurrency_scopes=(FLEET, ANTHROPIC)))
    env = admission.env()
    assert env[BUDGET_LEASE_ENV] == admission.budget_lease.lease_id
    assert env["FINOPS_CONCURRENCY_LEASE_IDS"].split(",") == [
        lease.lease_id for lease in admission.concurrency_leases
    ]
    assert env[MODEL_ENV] == SUBSCRIPTION_MODEL


# ── verify(): the registry-backed bypass check ──────────────────────────────────────────────


def test_verify_accepts_a_genuine_admission(controller: AdmissionController):
    admission = controller.admit(subscription_request())
    controller.verify(admission.context())  # does not raise


def test_verify_rejects_a_forged_context(controller: AdmissionController):
    """A hand-set ``FINOPS_BUDGET_LEASE_ID`` names no lease the registry ever granted."""
    forged = LeaseContext(
        run_id="attacker", model=SUBSCRIPTION_MODEL,
        budget_lease_id="bud_forged", expires_at=9e9,
    )
    with pytest.raises(AdmissionDenied, match="not outstanding"):
        controller.verify(forged)


def test_verify_rejects_a_released_admission(controller: AdmissionController):
    """A child that inherited an envelope whose parent has since released it."""
    admission = controller.admit(subscription_request())
    controller.release(admission)
    with pytest.raises(AdmissionDenied, match="not outstanding"):
        controller.verify(admission.context())


def test_verify_rejects_an_expired_context(controller: AdmissionController, clock: Clock):
    admission = controller.admit(subscription_request(ttl_seconds=60))
    clock.advance(61)
    with pytest.raises(AdmissionDenied, match="expired"):
        controller.verify(admission.context())


# ═══════════════════════════════════════════════════════════════════════════════════════════
# admitted() / concurrency_admitted() — the scoped helpers
# ═══════════════════════════════════════════════════════════════════════════════════════════


def test_admitted_binds_the_context_inside_and_releases_after(
    armed, controller: AdmissionController, clock: Clock
):
    with admitted(subscription_request(), controller=controller) as admission:
        assert current_context().budget_lease_id == admission.budget_lease.lease_id
        # ``now=clock.now`` because the controller runs on the injected clock: judging the
        # fixture's lease against the wall clock would read every admission as long expired.
        assert require_admission(SUBSCRIPTION_MODEL, now=clock.now) is not None
    assert current_context() is None
    assert controller.registry.outstanding(LeaseKind.CONCURRENCY, FLEET) == 0.0


def test_admitted_releases_even_when_the_body_raises(controller: AdmissionController):
    with pytest.raises(RuntimeError), admitted(subscription_request(), controller=controller):
        raise RuntimeError("the cell died")
    assert controller.registry.outstanding(LeaseKind.CONCURRENCY, FLEET) == 0.0
    assert controller.registry.outstanding(LeaseKind.BUDGET, ANTHROPIC) == 0.0


def test_concurrency_admitted_is_inert_when_disarmed():
    """Analysis work runs unchanged until an operator arms the gate."""
    with concurrency_admitted(FLEET, run_id="analysis:x") as lease:
        assert lease is None


def test_concurrency_admitted_reserves_and_releases_a_slot(
    armed, capped_registry: LeaseRegistry
):
    """A slot with no dollars: the honest model for work that costs CPU and not money."""
    with concurrency_admitted(FLEET, run_id="analysis:x", registry=capped_registry) as lease:
        assert lease is not None
        assert lease.unit == "slots"
        assert capped_registry.outstanding(LeaseKind.CONCURRENCY, FLEET) == 1.0
    assert capped_registry.outstanding(LeaseKind.CONCURRENCY, FLEET) == 0.0


def test_concurrency_admitted_refuses_a_full_scope(armed, capped_registry: LeaseRegistry):
    capped_registry.set_cap(LeaseKind.CONCURRENCY, FLEET, 1.0)
    # The first slot is HELD across the second attempt — that is what makes the refusal
    # meaningful, so the nesting is the test, not incidental structure.
    with (
        concurrency_admitted(FLEET, run_id="a", registry=capped_registry),
        pytest.raises(AdmissionDenied, match="concurrency admission denied"),
        concurrency_admitted(FLEET, run_id="b", registry=capped_registry),
    ):
        pytest.fail("the second slot must not be granted")


# ═══════════════════════════════════════════════════════════════════════════════════════════
# make_phase_admission — the runtime seam's control-side implementation
# ═══════════════════════════════════════════════════════════════════════════════════════════


def test_phase_admission_is_inert_when_disarmed(controller: AdmissionController):
    gate = make_phase_admission(
        spec_name="admission_leases", worktree_identity="wt", result_namespace="ns",
        controller=controller,
    )
    with gate("p2_admission_controller", SUBSCRIPTION_MODEL) as admission:
        assert admission is None
    assert controller.registry.outstanding(LeaseKind.CONCURRENCY, CAMPAIGN) == 0.0


def test_phase_admission_reserves_against_the_campaign_scope(
    armed, controller: AdmissionController
):
    """Per-phase reservation against the WORKFLOW's campaign lease (the work order's item (d))."""
    gate = make_phase_admission(
        spec_name="admission_leases", worktree_identity="wt", result_namespace="ns",
        controller=controller,
    )
    with gate("p2_admission_controller", SUBSCRIPTION_MODEL) as admission:
        assert admission is not None
        assert admission.budget_lease.scope == CAMPAIGN
        assert controller.registry.outstanding(LeaseKind.CONCURRENCY, CAMPAIGN) == 1.0
        assert admission.record.run_id.startswith("admission_leases:p2_admission_controller:")
    assert controller.registry.outstanding(LeaseKind.CONCURRENCY, CAMPAIGN) == 0.0


def test_phase_admission_refuses_when_the_campaign_budget_is_exhausted(
    armed, controller: AdmissionController, capped_registry: LeaseRegistry
):
    """Five phases against one campaign budget: the run stops when the campaign is spent."""
    capped_registry.set_cap(LeaseKind.BUDGET, CAMPAIGN, 1.5)  # 1 phase at 1.0 window point fits
    gate = make_phase_admission(
        spec_name="admission_leases", worktree_identity="wt", result_namespace="ns",
        controller=controller,
    )
    # p1's lease is held while p2 is attempted — the campaign budget is shared, and that
    # sharing is exactly what the second phase must be refused for.
    with (
        gate("p1", SUBSCRIPTION_MODEL),
        pytest.raises(AdmissionDenied, match="budget reservation failed"),
        gate("p2", SUBSCRIPTION_MODEL),
    ):
        pytest.fail("the second phase must not be admitted")


def test_phase_admission_refusal_is_catchable_as_the_tier_zero_family(
    armed, controller: AdmissionController, capped_registry: LeaseRegistry
):
    """``runtime`` catches ``AdmissionRefused``; it may not import ``control``'s hierarchy."""
    capped_registry.set_cap(LeaseKind.BUDGET, CAMPAIGN, 0.5)
    gate = make_phase_admission(
        spec_name="admission_leases", worktree_identity="wt", result_namespace="ns",
        controller=controller,
    )
    with pytest.raises(AdmissionRefused), gate("p1", SUBSCRIPTION_MODEL):
        pytest.fail("unreachable")


def test_admission_denied_is_catchable_from_both_vocabularies():
    """The double inheritance is load-bearing, not decoration."""
    assert issubclass(AdmissionDenied, AdmissionError)   # tier-2 lease family
    assert issubclass(AdmissionDenied, AdmissionRefused)  # tier-0 refusal family


# ═══════════════════════════════════════════════════════════════════════════════════════════
# admission_board — the Control Room's telemetry projection
# ═══════════════════════════════════════════════════════════════════════════════════════════


def test_admission_board_reports_outstanding_and_headroom(
    controller: AdmissionController, capped_registry: LeaseRegistry
):
    controller.admit(subscription_request())
    board = admission_board(
        capped_registry,
        [(LeaseKind.CONCURRENCY, FLEET), (LeaseKind.BUDGET, ANTHROPIC)],
    )
    slots = next(r for r in board["scopes"] if r["scope"] == FLEET.token)
    assert slots["cap"] == 6.0
    assert slots["outstanding"] == 1.0
    assert slots["headroom"] == 5.0
    assert slots["unit"] == "slots"
    assert slots["lease_count"] == 1
    assert board["armed"] is False  # this test does not arm the gate


def test_admission_board_reports_an_uncapped_scope_without_raising(registry: LeaseRegistry):
    """A dashboard may legitimately display "this counter admits nothing yet"."""
    board = admission_board(registry, [(LeaseKind.CONCURRENCY, FLEET)])
    row = board["scopes"][0]
    assert row["cap"] is None
    assert row["headroom"] is None
    assert row["outstanding"] == 0
