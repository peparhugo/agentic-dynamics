"""Lease-registry tests — the atomic admission primitives, driven in both directions.

Both directions means: for every rule the registry states, one test proves the rule *grants* what
it should and one proves it *refuses* what it should. A gate that only ever says yes is untested.

Transport is faked, policy is not. :class:`FakeRedis` implements the small command subset the
registry uses (hash get/set/del, string get/set, expire) plus real ``WATCH``/``MULTI``/``EXEC``
semantics: it tracks a version per key and aborts ``EXEC`` with redis-py's own ``WatchError`` if a
watched key changed since ``WATCH``. That is what makes the atomicity tests meaningful — the
registry's real compare-and-set loop runs, and only the wire is simulated.

``FakeRedis.before_execute`` is the concurrency hook: it fires inside the watch window, letting a
test act as the competing writer that a real race would have been.

A final integration test runs the same flows against a live framework Redis (6380 db1) when one
is reachable, and skips otherwise — the conftest convention for optional infrastructure.
"""

from __future__ import annotations

import json
import socket
import uuid

import pytest

from agentic_dynamics.control.lease_registry import (
    BETA_COST,
    BETA_TOKENS,
    DEFAULT_MAX_RETRIES,
    FRAMEWORK_HOST_PORT,
    FRAMEWORK_SERVICE_HOST,
    LOOPBACK_HOSTS,
    REDIS_HOST,
    REDIS_PORT,
    SANDBOX_HOST_PORT,
    SANDBOX_SERVICE_HOST,
    WINDOW_PERCENT_MAX,
    AdmissionRecord,
    CostSource,
    Lease,
    LeaseDeniedError,
    LeaseFieldError,
    LeaseKind,
    LeaseRegistry,
    LeaseScope,
    LeaseUnavailableError,
    ProviderClass,
    ScopeKind,
    assert_not_sandbox,
    fleet_throughput,
    marginal_throughput_gain,
    provider_class_for_model,
    provider_class_for_provider,
    recommended_concurrency,
)

# ── The fake transport (WATCH/MULTI/EXEC, faithfully) ────────────────────────────────────────


class FakeRedis:
    """In-memory Redis double with real optimistic-concurrency semantics.

    Only the commands the registry issues are implemented; anything else is intentionally absent
    so a future command has to be added here deliberately rather than silently no-op.
    """

    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.strings: dict[str, str] = {}
        self.expires: dict[str, int] = {}
        #: Bumped on every write to a key — the ``WATCH`` invalidation signal.
        self.versions: dict[str, int] = {}
        #: Fires once inside each watch window (before EXEC); a test uses it to play the racer.
        self.before_execute = None
        #: Raised by every command when set — the "Redis is down" simulation.
        self.fail_with: Exception | None = None

    # -- internal ---------------------------------------------------------------------------

    def _check(self) -> None:
        if self.fail_with is not None:
            raise self.fail_with

    def _bump(self, key: str) -> None:
        self.versions[key] = self.versions.get(key, 0) + 1

    # -- direct commands --------------------------------------------------------------------

    def ping(self) -> bool:
        self._check()
        return True

    def hgetall(self, key: str) -> dict[str, str]:
        self._check()
        return dict(self.hashes.get(key, {}))

    def hget(self, key: str, field: str) -> str | None:
        self._check()
        return self.hashes.get(key, {}).get(field)

    def hset(self, key: str, field: str, value: str) -> int:
        self._check()
        self.hashes.setdefault(key, {})[field] = value
        self._bump(key)
        return 1

    def hdel(self, key: str, *fields: str) -> int:
        self._check()
        bucket = self.hashes.get(key, {})
        removed = sum(1 for f in fields if bucket.pop(f, None) is not None)
        if removed:
            self._bump(key)
        return removed

    def get(self, key: str) -> str | None:
        self._check()
        return self.strings.get(key)

    def set(self, key: str, value: str) -> bool:
        self._check()
        self.strings[key] = value
        self._bump(key)
        return True

    def expire(self, key: str, seconds: int) -> bool:
        self._check()
        self.expires[key] = seconds
        return True

    def pipeline(self, transaction: bool = True) -> FakePipeline:
        self._check()
        return FakePipeline(self)


class FakePipeline:
    """The transactional half of :class:`FakeRedis`.

    Mirrors redis-py: after ``watch()`` commands execute immediately; ``multi()`` switches to
    buffering; ``execute()`` applies the buffer only if no watched key moved.
    """

    def __init__(self, server: FakeRedis) -> None:
        self._server = server
        self._watched: dict[str, int] = {}
        self._buffer: list[tuple] = []
        self._buffering = False

    def __enter__(self) -> FakePipeline:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.reset()

    # -- watch / transaction control ---------------------------------------------------------

    def watch(self, *keys: str) -> bool:
        self._server._check()
        if self._buffering:
            raise RuntimeError("cannot WATCH inside MULTI")
        for key in keys:
            self._watched[key] = self._server.versions.get(key, 0)
        return True

    def unwatch(self) -> bool:
        self._server._check()
        self._watched.clear()
        return True

    def multi(self) -> None:
        self._server._check()
        self._buffering = True

    def reset(self) -> None:
        self._watched.clear()
        self._buffer.clear()
        self._buffering = False

    # -- commands (immediate before multi(), buffered after) ---------------------------------

    def hgetall(self, key: str):
        return self._dispatch("hgetall", key)

    def hget(self, key: str, field: str):
        return self._dispatch("hget", key, field)

    def hset(self, key: str, field: str, value: str):
        return self._dispatch("hset", key, field, value)

    def hdel(self, key: str, *fields: str):
        return self._dispatch("hdel", key, *fields)

    def expire(self, key: str, seconds: int):
        return self._dispatch("expire", key, seconds)

    def _dispatch(self, name: str, *args):
        self._server._check()
        if self._buffering:
            self._buffer.append((name, args))
            return self
        return getattr(self._server, name)(*args)

    def execute(self) -> list:
        """Apply the buffer, or raise ``WatchError`` if a watched key changed."""
        from redis.exceptions import WatchError

        self._server._check()
        # The concurrency hook stands in for another process committing mid-window.
        hook, self._server.before_execute = self._server.before_execute, None
        if hook is not None:
            hook()
        for key, seen_version in self._watched.items():
            if self._server.versions.get(key, 0) != seen_version:
                self.reset()
                raise WatchError(f"watched key {key!r} changed")
        results = [getattr(self._server, name)(*args) for name, args in self._buffer]
        self.reset()
        return results


# ── Fixtures / builders ──────────────────────────────────────────────────────────────────────


class Clock:
    """An injectable monotonic clock, so TTL expiry is exercised without sleeping."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def server() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def registry(server: FakeRedis, clock: Clock) -> LeaseRegistry:
    """A registry with deterministic time and monotonically numbered lease ids."""
    counter = iter(f"{i:04d}" for i in range(1, 10_000))
    return LeaseRegistry(server, now_fn=clock, id_fn=lambda: next(counter))


FLEET = LeaseScope(ScopeKind.FLEET, "ladder")
DEEPSEEK = LeaseScope(ScopeKind.PROVIDER, "deepseek")
CAMPAIGN = LeaseScope(ScopeKind.CAMPAIGN, "admission_leases")


# ── β knobs: the concurrency lease is sized on throughput, not dollars ───────────────────────


def test_beta_constants_match_the_measured_lab_bands():
    """The two β's are the lab's main estimates: moderate on cost, severe on tokens."""
    assert abs(BETA_COST - 0.154) < 0.001
    assert abs(BETA_TOKENS - 0.802) < 0.001
    # The whole sizing argument in one assertion: throughput is taxed ~5x harder than dollars.
    assert BETA_TOKENS > 5 * BETA_COST


def test_fleet_throughput_is_sublinear_under_the_token_tax():
    """N workers deliver N^(1-β) — ten workers are worth well under two."""
    assert fleet_throughput(1) == pytest.approx(1.0)
    assert fleet_throughput(10) == pytest.approx(10 ** (1 - BETA_TOKENS), rel=1e-9)
    assert fleet_throughput(10) < 2.0
    # Monotone but decelerating: each extra worker helps less than the one before.
    gains = [marginal_throughput_gain(n) for n in range(1, 8)]
    assert all(g > 0 for g in gains)
    assert gains == sorted(gains, reverse=True)


def test_recommended_concurrency_from_measured_beta_tokens():
    """β_tokens=0.80 at the 5% default recommends 6 — the 7th worker stops earning its keep."""
    assert recommended_concurrency() == 6
    # ``marginal_throughput_gain(n)`` is what worker n+1 adds: the 6th still earns its keep,
    # the 7th does not — which is exactly where the walk stops.
    assert marginal_throughput_gain(5) >= 0.05
    assert marginal_throughput_gain(6) < 0.05


def test_recommended_concurrency_on_beta_cost_is_far_wider():
    """The dollar tax alone would permit a much wider fleet — which is exactly the trap.

    Sizing a fleet on β_cost (0.154, "moderate") recommends a width that β_tokens (0.80,
    "severe") shows is throughput-wasteful. The registry documents both knobs and sizes the
    concurrency lease on the token tax.
    """
    assert recommended_concurrency(BETA_COST) > 3 * recommended_concurrency(BETA_TOKENS)


def test_recommended_concurrency_refuses_a_meaningless_beta():
    """β >= 1 means added workers reduce total output — refuse rather than return a number."""
    with pytest.raises(LeaseFieldError):
        recommended_concurrency(1.0)
    with pytest.raises(LeaseFieldError):
        recommended_concurrency(BETA_TOKENS, min_marginal_gain=0.0)


# ── Provider-class boundaries ────────────────────────────────────────────────────────────────


def test_provider_classes_follow_the_cost_model():
    assert provider_class_for_provider("deepseek") is ProviderClass.PER_TOKEN
    assert provider_class_for_provider("anthropic") is ProviderClass.SUBSCRIPTION
    assert provider_class_for_provider("openai") is ProviderClass.SUBSCRIPTION
    assert provider_class_for_model("deepseek/deepseek-v4-pro") is ProviderClass.PER_TOKEN
    assert provider_class_for_model("anthropic/claude-opus-5") is ProviderClass.SUBSCRIPTION


def test_unknown_provider_is_never_assumed_free():
    """An unclassified provider raises — it does NOT default to the zero-marginal-cost class."""
    with pytest.raises(LeaseFieldError, match="no declared cost class"):
        provider_class_for_provider("mystery-corp")
    with pytest.raises(LeaseFieldError):
        provider_class_for_model("bare-model-id-without-a-provider")


# ── Scope hygiene ────────────────────────────────────────────────────────────────────────────


def test_scope_name_may_not_contain_the_key_separator():
    """``fleet:a`` as a name would alias another scope's counter — refused at construction."""
    with pytest.raises(LeaseFieldError, match="key separator"):
        LeaseScope(ScopeKind.FLEET, "ladder:wide")
    with pytest.raises(LeaseFieldError):
        LeaseScope(ScopeKind.FLEET, "   ")


# ── Redis placement ──────────────────────────────────────────────────────────────────────────


def test_the_framework_target_is_nameable_independently_of_the_ambient_env():
    """The contract constants are fixed, so the correct instance is nameable even under a
    ``FINOPS_REDIS_*`` env that points elsewhere (a ladder cell's env points at
    ``finops-queue:6379``, which is the SAME server on its internal port)."""
    assert FRAMEWORK_HOST_PORT == 6380
    assert FRAMEWORK_SERVICE_HOST == "finops-queue"
    assert SANDBOX_SERVICE_HOST == "finops-redis"
    assert SANDBOX_HOST_PORT == 6379
    assert "127.0.0.1" in LOOPBACK_HOSTS and "localhost" in LOOPBACK_HOSTS


@pytest.mark.parametrize(
    ("host", "port"),
    [
        ("finops-redis", 6379),   # the sandbox by name, on its own port
        ("finops-redis", 6380),   # ...and on any other port: identity, not port number
        ("127.0.0.1", 6379),      # on the host loopback, 6379 IS the sandbox
        ("localhost", 6379),
        ("::1", 6379),
    ],
)
def test_the_story_agent_sandbox_is_refused(host, port):
    """A registry on the instance story agents ``flushall()`` is not a registry."""
    with pytest.raises(LeaseUnavailableError):
        assert_not_sandbox(host, port)
    with pytest.raises(LeaseUnavailableError):
        LeaseRegistry.from_env(host=host, port=port)


@pytest.mark.parametrize(
    ("host", "port"),
    [
        ("finops-queue", 6379),   # inside fleet-net: the framework instance's INTERNAL port
        ("127.0.0.1", 6380),      # from the host: the framework instance's published port
    ],
)
def test_the_framework_instance_is_allowed_from_both_vantage_points(host, port):
    """The guard must not lock the containerized fleet out: on ``fleet-net`` the framework
    instance genuinely answers on 6379, and ``finops-redis`` is not attached to that network."""
    assert_not_sandbox(host, port)  # does not raise


def test_the_ambient_env_target_is_not_the_sandbox():
    """Whatever this process's ``FINOPS_REDIS_*`` resolves to, it must not be the sandbox —
    on the host that means 6380, inside a ladder cell it means ``finops-queue:6379``."""
    assert_not_sandbox(REDIS_HOST, REDIS_PORT)


def test_registry_without_a_client_admits_nothing():
    with pytest.raises(LeaseUnavailableError):
        LeaseRegistry(None)


# ── Budget leases: grant ─────────────────────────────────────────────────────────────────────


def test_reserve_budget_grants_and_records_the_full_lease(registry, clock):
    """A granted lease carries every field an audit needs to replay the decision."""
    registry.set_cap(LeaseKind.BUDGET, DEEPSEEK, 10.0)
    lease = registry.reserve_budget(
        ProviderClass.PER_TOKEN,
        DEEPSEEK,
        2.50,
        run_id="run-a",
        cost_source=CostSource.ESTIMATED,
        ttl_seconds=600,
    )

    assert lease.lease_id.startswith("bud_")
    assert lease.kind is LeaseKind.BUDGET
    assert lease.unit == "usd"
    assert lease.amount == 2.50
    assert lease.hard_cap == 10.0
    assert lease.cost_source is CostSource.ESTIMATED
    assert lease.granted_at == clock.now
    assert lease.expires_at == clock.now + 600
    assert lease.expires_at_iso.endswith("+00:00")

    assert registry.outstanding(LeaseKind.BUDGET, DEEPSEEK) == 2.50
    assert registry.headroom(LeaseKind.BUDGET, DEEPSEEK) == 7.50
    assert [x.lease_id for x in registry.leases(LeaseKind.BUDGET, DEEPSEEK)] == [lease.lease_id]


def test_reservations_accumulate_within_the_cap(registry):
    """Several runs share one scope's headroom; the cap is checked against the running total."""
    registry.set_cap(LeaseKind.BUDGET, DEEPSEEK, 1.0)
    for i, amount in enumerate((0.1, 0.2, 0.7)):
        registry.reserve_budget(
            ProviderClass.PER_TOKEN, DEEPSEEK, amount,
            run_id=f"run-{i}", cost_source=CostSource.METERED,
        )
    # Exactly-at-cap must be admitted: binary float noise (0.1+0.2+0.7) is not a policy decision.
    assert registry.outstanding(LeaseKind.BUDGET, DEEPSEEK) == pytest.approx(1.0)
    assert registry.headroom(LeaseKind.BUDGET, DEEPSEEK) == pytest.approx(0.0, abs=1e-9)


# ── Budget leases: refuse ────────────────────────────────────────────────────────────────────


def test_reserve_budget_refuses_over_the_cap(registry):
    registry.set_cap(LeaseKind.BUDGET, DEEPSEEK, 5.0)
    registry.reserve_budget(
        ProviderClass.PER_TOKEN, DEEPSEEK, 4.0,
        run_id="run-a", cost_source=CostSource.METERED,
    )
    with pytest.raises(LeaseDeniedError, match="hard cap"):
        registry.reserve_budget(
            ProviderClass.PER_TOKEN, DEEPSEEK, 1.5,
            run_id="run-b", cost_source=CostSource.METERED,
        )
    # The refused reservation left no trace — a denial must not consume headroom.
    assert registry.outstanding(LeaseKind.BUDGET, DEEPSEEK) == 4.0


def test_unknown_cost_is_denied_on_a_per_token_lease(registry):
    """The audit's rule, enforced before the money moves rather than after."""
    registry.set_cap(LeaseKind.BUDGET, DEEPSEEK, 100.0)
    with pytest.raises(LeaseDeniedError, match="never free"):
        registry.reserve_budget(
            ProviderClass.PER_TOKEN, DEEPSEEK, 1.0,
            run_id="run-a", cost_source=CostSource.UNKNOWN,
        )
    assert registry.outstanding(LeaseKind.BUDGET, DEEPSEEK) == 0.0


def test_absent_cost_source_on_a_per_token_lease_is_a_loud_error(registry):
    """Omitting provenance is not the same as declaring it zero — it is a missing field."""
    registry.set_cap(LeaseKind.BUDGET, DEEPSEEK, 100.0)
    with pytest.raises(LeaseFieldError, match="cost_source"):
        registry.reserve_budget(ProviderClass.PER_TOKEN, DEEPSEEK, 1.0, run_id="run-a")


def test_subscription_lease_refuses_a_dollar_cap(registry):
    """A cap above 100 means someone handed dollars to a window lease — a boundary violation."""
    anthropic = LeaseScope(ScopeKind.PROVIDER, "anthropic")
    registry.set_cap(LeaseKind.BUDGET, anthropic, 250.0)  # dollars, mistakenly
    with pytest.raises(LeaseDeniedError, match="provider-class boundary"):
        registry.reserve_budget(
            ProviderClass.SUBSCRIPTION, anthropic, 5.0, run_id="run-a",
        )


def test_subscription_lease_refuses_an_amount_beyond_the_window(registry):
    anthropic = LeaseScope(ScopeKind.PROVIDER, "anthropic")
    registry.set_cap(LeaseKind.BUDGET, anthropic, WINDOW_PERCENT_MAX)
    with pytest.raises(LeaseDeniedError, match="window percentage points"):
        registry.reserve_budget(
            ProviderClass.SUBSCRIPTION, anthropic, 120.0, run_id="run-a",
        )


def test_subscription_lease_grants_window_percentage_points(registry):
    """The positive direction of the same boundary: percent in, percent out, no dollar cap."""
    anthropic = LeaseScope(ScopeKind.PROVIDER, "anthropic")
    lease = registry.reserve_budget(
        ProviderClass.SUBSCRIPTION, anthropic, 12.0, run_id="run-a", hard_cap=80.0,
    )
    assert lease.unit == "window_percent"
    assert lease.cost_source is None
    assert registry.headroom(LeaseKind.BUDGET, anthropic, 80.0) == pytest.approx(68.0)


def test_an_uncapped_scope_admits_nothing(registry):
    """No cap installed and none passed ⇒ refusal. 'Unconfigured' never means 'unlimited'."""
    with pytest.raises(LeaseFieldError, match="no hard cap"):
        registry.reserve_budget(
            ProviderClass.PER_TOKEN, DEEPSEEK, 1.0,
            run_id="run-a", cost_source=CostSource.METERED,
        )


@pytest.mark.parametrize("amount", [None, 0, 0.0, -1.0, float("nan"), float("inf"), True, "1.0"])
def test_a_missing_or_bogus_amount_is_loud_never_a_silent_zero(registry, amount):
    """Every non-number and non-positive amount raises. Nothing is coerced to 0.0."""
    registry.set_cap(LeaseKind.BUDGET, DEEPSEEK, 10.0)
    with pytest.raises(LeaseFieldError):
        registry.reserve_budget(
            ProviderClass.PER_TOKEN, DEEPSEEK, amount,
            run_id="run-a", cost_source=CostSource.METERED,
        )


def test_a_missing_run_id_or_ttl_is_loud(registry):
    registry.set_cap(LeaseKind.BUDGET, DEEPSEEK, 10.0)
    with pytest.raises(LeaseFieldError, match="run_id"):
        registry.reserve_budget(
            ProviderClass.PER_TOKEN, DEEPSEEK, 1.0, run_id="",
            cost_source=CostSource.METERED,
        )
    with pytest.raises(LeaseFieldError, match="ttl_seconds"):
        registry.reserve_budget(
            ProviderClass.PER_TOKEN, DEEPSEEK, 1.0, run_id="run-a",
            cost_source=CostSource.METERED, ttl_seconds=0,
        )


# ── Concurrency leases ───────────────────────────────────────────────────────────────────────


def test_reserve_concurrency_grants_slots_up_to_the_scope_cap(registry):
    """Sized with the β recommendation: six slots on the fleet scope, then refusal."""
    width = recommended_concurrency()
    registry.set_cap(LeaseKind.CONCURRENCY, FLEET, width)
    held = [
        registry.reserve_concurrency(FLEET, 1, run_id=f"cell-{i}") for i in range(width)
    ]
    assert len(held) == width
    assert registry.outstanding(LeaseKind.CONCURRENCY, FLEET) == float(width)
    assert all(lease.unit == "slots" for lease in held)

    with pytest.raises(LeaseDeniedError, match="concurrency lease denied"):
        registry.reserve_concurrency(FLEET, 1, run_id="cell-overflow")


def test_concurrency_scopes_are_independent_counters(registry):
    """Per-scope, not a global invariant: filling the fleet does not close the campaign."""
    registry.set_cap(LeaseKind.CONCURRENCY, FLEET, 1)
    registry.set_cap(LeaseKind.CONCURRENCY, CAMPAIGN, 4)
    registry.reserve_concurrency(FLEET, 1, run_id="cell-a")
    with pytest.raises(LeaseDeniedError):
        registry.reserve_concurrency(FLEET, 1, run_id="cell-b")
    # A different scope has its own headroom.
    assert registry.reserve_concurrency(CAMPAIGN, 3, run_id="cell-b").amount == 3.0


def test_concurrency_count_must_be_a_whole_number_of_slots(registry):
    registry.set_cap(LeaseKind.CONCURRENCY, FLEET, 8)
    for bad in (0, -1, 1.5, True, None, "2"):
        with pytest.raises(LeaseFieldError):
            registry.reserve_concurrency(FLEET, bad, run_id="cell-a")


# ── Release ──────────────────────────────────────────────────────────────────────────────────


def test_release_returns_the_headroom_and_is_idempotent(registry):
    registry.set_cap(LeaseKind.BUDGET, DEEPSEEK, 5.0)
    lease = registry.reserve_budget(
        ProviderClass.PER_TOKEN, DEEPSEEK, 5.0,
        run_id="run-a", cost_source=CostSource.METERED,
    )
    with pytest.raises(LeaseDeniedError):
        registry.reserve_budget(
            ProviderClass.PER_TOKEN, DEEPSEEK, 0.5,
            run_id="run-b", cost_source=CostSource.METERED,
        )

    released = registry.release(lease.lease_id)
    assert released is not None and released.lease_id == lease.lease_id
    assert registry.outstanding(LeaseKind.BUDGET, DEEPSEEK) == 0.0

    # The freed headroom is immediately reusable, and a second release is a no-op, not an error.
    registry.reserve_budget(
        ProviderClass.PER_TOKEN, DEEPSEEK, 0.5,
        run_id="run-b", cost_source=CostSource.METERED,
    )
    assert registry.release(lease.lease_id) is None
    assert registry.release("bud_never-existed") is None


def test_release_requires_a_lease_id(registry):
    with pytest.raises(LeaseFieldError):
        registry.release("")


# ── TTL expiry ───────────────────────────────────────────────────────────────────────────────


def test_an_expired_lease_stops_counting_against_the_cap(registry, clock):
    """Expiry is enforced on read by every writer — no sweeper required for correctness."""
    registry.set_cap(LeaseKind.BUDGET, DEEPSEEK, 3.0)
    registry.reserve_budget(
        ProviderClass.PER_TOKEN, DEEPSEEK, 3.0,
        run_id="run-a", cost_source=CostSource.METERED, ttl_seconds=60,
    )
    assert registry.outstanding(LeaseKind.BUDGET, DEEPSEEK) == 3.0
    with pytest.raises(LeaseDeniedError):
        registry.reserve_budget(
            ProviderClass.PER_TOKEN, DEEPSEEK, 1.0,
            run_id="run-b", cost_source=CostSource.METERED,
        )

    clock.advance(60)  # expiry is inclusive: at exactly expires_at the claim is gone
    assert registry.outstanding(LeaseKind.BUDGET, DEEPSEEK) == 0.0
    fresh = registry.reserve_budget(
        ProviderClass.PER_TOKEN, DEEPSEEK, 3.0,
        run_id="run-b", cost_source=CostSource.METERED,
    )
    assert fresh.run_id == "run-b"


def test_expire_leases_reclaims_and_reports_what_it_swept(registry, clock, server):
    """The sweep's return value is phase 4's quarantine input, so it must be the real leases."""
    registry.set_cap(LeaseKind.BUDGET, DEEPSEEK, 10.0)
    registry.set_cap(LeaseKind.CONCURRENCY, FLEET, 4)
    short = registry.reserve_budget(
        ProviderClass.PER_TOKEN, DEEPSEEK, 1.0,
        run_id="run-short", cost_source=CostSource.METERED, ttl_seconds=30,
    )
    slot = registry.reserve_concurrency(FLEET, 1, run_id="run-short", ttl_seconds=45)
    survivor = registry.reserve_budget(
        ProviderClass.PER_TOKEN, DEEPSEEK, 1.0,
        run_id="run-long", cost_source=CostSource.METERED, ttl_seconds=9000,
    )

    assert registry.expire_leases() == []  # nothing has expired yet

    clock.advance(60)
    swept = registry.expire_leases()
    assert [lease.lease_id for lease in swept] == [short.lease_id, slot.lease_id]
    assert [lease.run_id for lease in swept] == ["run-short", "run-short"]

    # The survivor is untouched, and the index no longer references the reclaimed ids.
    assert [x.lease_id for x in registry.leases(LeaseKind.BUDGET, DEEPSEEK)] == [
        survivor.lease_id
    ]
    index = server.hgetall("finops:lease:index")
    assert set(index) == {survivor.lease_id}


def test_expire_leases_can_be_narrowed_to_named_scopes(registry, clock):
    registry.set_cap(LeaseKind.BUDGET, DEEPSEEK, 10.0)
    registry.set_cap(LeaseKind.CONCURRENCY, FLEET, 4)
    registry.reserve_budget(
        ProviderClass.PER_TOKEN, DEEPSEEK, 1.0,
        run_id="run-a", cost_source=CostSource.METERED, ttl_seconds=30,
    )
    registry.reserve_concurrency(FLEET, 1, run_id="run-a", ttl_seconds=30)
    clock.advance(60)

    swept = registry.expire_leases(scopes=[(LeaseKind.CONCURRENCY, FLEET)])
    assert [lease.kind for lease in swept] == [LeaseKind.CONCURRENCY]
    # The budget scope was out of the sweep's scope list, so its record is still on disk.
    assert registry.expire_leases()  # the untouched expired budget lease is still reclaimable


# ── Atomicity ────────────────────────────────────────────────────────────────────────────────


def test_a_concurrent_writer_forces_a_retry_and_cannot_double_spend(registry, server):
    """The core guarantee: two runs cannot both admit against the same pre-state.

    The hook plays the racer — it commits a competing $6 lease *inside* the watch window of a
    $6 reservation against a $10 cap. Redis invalidates the watch, the registry re-reads, and the
    second reservation is refused. Without the compare-and-set both would have been granted and
    the scope would sit at $12 against a $10 cap.
    """
    registry.set_cap(LeaseKind.BUDGET, DEEPSEEK, 10.0)
    racer_lease: dict[str, Lease] = {}

    def racer() -> None:
        racer_lease["lease"] = registry.reserve_budget(
            ProviderClass.PER_TOKEN, DEEPSEEK, 6.0,
            run_id="racer", cost_source=CostSource.METERED,
        )

    server.before_execute = racer
    with pytest.raises(LeaseDeniedError, match="hard cap"):
        registry.reserve_budget(
            ProviderClass.PER_TOKEN, DEEPSEEK, 6.0,
            run_id="loser", cost_source=CostSource.METERED,
        )

    assert registry.outstanding(LeaseKind.BUDGET, DEEPSEEK) == 6.0
    assert [x.lease_id for x in registry.leases(LeaseKind.BUDGET, DEEPSEEK)] == [
        racer_lease["lease"].lease_id
    ]


def test_a_retry_succeeds_when_the_scope_still_fits(registry, server):
    """The other direction: a lost race that still fits is retried and granted, not refused."""
    registry.set_cap(LeaseKind.BUDGET, DEEPSEEK, 10.0)

    def racer() -> None:
        registry.reserve_budget(
            ProviderClass.PER_TOKEN, DEEPSEEK, 1.0,
            run_id="racer", cost_source=CostSource.METERED,
        )

    server.before_execute = racer
    granted = registry.reserve_budget(
        ProviderClass.PER_TOKEN, DEEPSEEK, 2.0,
        run_id="winner", cost_source=CostSource.METERED,
    )
    assert granted.run_id == "winner"
    assert registry.outstanding(LeaseKind.BUDGET, DEEPSEEK) == 3.0


def test_unbounded_contention_denies_rather_than_admitting_on_stale_state(registry, server):
    """Retry exhaustion is a refusal. The gate closes under pathological contention."""
    registry.set_cap(LeaseKind.BUDGET, DEEPSEEK, 1000.0)
    attempts = {"n": 0}

    def always_race() -> None:
        # Re-arm on every window so the reservation never gets a clean EXEC.
        attempts["n"] += 1
        server.versions["finops:lease:budget:provider:deepseek"] = attempts["n"] * 1000
        server.before_execute = always_race

    server.before_execute = always_race
    with pytest.raises(LeaseDeniedError, match="contention"):
        registry.reserve_budget(
            ProviderClass.PER_TOKEN, DEEPSEEK, 1.0,
            run_id="run-a", cost_source=CostSource.METERED,
        )
    assert attempts["n"] == DEFAULT_MAX_RETRIES


# ── Fail-closed on infrastructure failure ────────────────────────────────────────────────────


def test_a_redis_failure_denies_rather_than_degrading(registry, server):
    """Unlike ``control.live``, the gate never no-ops: a broken registry admits nothing."""
    registry.set_cap(LeaseKind.BUDGET, DEEPSEEK, 10.0)
    server.fail_with = ConnectionError("connection reset by peer")

    with pytest.raises(LeaseUnavailableError):
        registry.reserve_budget(
            ProviderClass.PER_TOKEN, DEEPSEEK, 1.0,
            run_id="run-a", cost_source=CostSource.METERED,
        )
    with pytest.raises(LeaseUnavailableError):
        registry.reserve_concurrency(FLEET, 1, run_id="run-a", hard_cap=4)
    with pytest.raises(LeaseUnavailableError):
        registry.release("bud_0001")
    with pytest.raises(LeaseUnavailableError):
        registry.expire_leases()
    with pytest.raises(LeaseUnavailableError):
        registry.outstanding(LeaseKind.BUDGET, DEEPSEEK)


def test_every_refusal_shares_one_catchable_base(registry):
    """A caller that wants 'any refusal' catches ``AdmissionError`` and gets all three."""
    from agentic_dynamics.control.lease_registry import AdmissionError

    assert issubclass(LeaseDeniedError, AdmissionError)
    assert issubclass(LeaseUnavailableError, AdmissionError)
    assert issubclass(LeaseFieldError, AdmissionError)


# ── Corrupt state ────────────────────────────────────────────────────────────────────────────


def test_a_corrupt_stored_lease_is_loud_not_skipped(registry, server):
    """Skipping an unparseable record would under-count the scope and admit an over-cap run."""
    registry.set_cap(LeaseKind.BUDGET, DEEPSEEK, 10.0)
    lease = registry.reserve_budget(
        ProviderClass.PER_TOKEN, DEEPSEEK, 9.0,
        run_id="run-a", cost_source=CostSource.METERED,
    )
    key = "finops:lease:budget:provider:deepseek"

    server.hashes[key][lease.lease_id] = "{not json"
    with pytest.raises(LeaseFieldError, match="unparseable JSON"):
        registry.outstanding(LeaseKind.BUDGET, DEEPSEEK)

    payload = json.loads(json.dumps(lease.to_dict()))
    payload.pop("amount")
    server.hashes[key][lease.lease_id] = json.dumps(payload)
    with pytest.raises(LeaseFieldError, match="missing required field"):
        registry.outstanding(LeaseKind.BUDGET, DEEPSEEK)


def test_a_corrupt_cap_is_loud(registry, server):
    server.strings["finops:lease:budget:provider:deepseek".replace(":budget", ":cap:budget")] = "n/a"
    with pytest.raises(LeaseFieldError, match="not a number"):
        registry.get_cap(LeaseKind.BUDGET, DEEPSEEK)


def test_lease_roundtrips_through_its_stored_payload(registry):
    registry.set_cap(LeaseKind.BUDGET, DEEPSEEK, 10.0)
    lease = registry.reserve_budget(
        ProviderClass.PER_TOKEN, DEEPSEEK, 1.25,
        run_id="run-a", cost_source=CostSource.RECONCILED,
        metadata={"beta_source": "lab_beta_from_corpus"},
    )
    assert Lease.from_dict(lease.to_dict()) == lease


# ── The admission record (the audit's shape) ─────────────────────────────────────────────────


def _per_token_record(**overrides) -> AdmissionRecord:
    """A valid per-token admission record; keyword overrides break one field at a time."""
    base = dict(
        run_id="run-a",
        lease_ids=("bud_0001", "con_0002"),
        reserved_cost_usd=2.5,
        hard_cap_usd=10.0,
        cost_source=CostSource.ESTIMATED,
        provider="deepseek",
        model="deepseek/deepseek-v4-flash",
        expires_at=1_000_600.0,
        worktree_identity="wt_admission_leases",
        result_namespace="experiments/results/stories/wt_admission_leases",
    )
    base.update(overrides)
    return AdmissionRecord(**base)


def test_a_complete_per_token_record_validates_and_projects(registry):
    record = _per_token_record()
    record.validate()
    payload = record.to_dict()
    assert payload["provider_class"] == "per_token"
    assert payload["lease_ids"] == ["bud_0001", "con_0002"]
    assert payload["cost_source"] == "estimated"
    assert payload["expires_at_iso"].startswith("1970-01-12")  # epoch 1,000,600s
    assert payload["worktree_identity"] == "wt_admission_leases"


@pytest.mark.parametrize(
    "field_name",
    ["run_id", "provider", "model", "worktree_identity", "result_namespace"],
)
def test_a_missing_string_field_is_a_loud_error(field_name):
    with pytest.raises(LeaseFieldError, match=field_name):
        _per_token_record(**{field_name: ""}).validate()


def test_a_record_with_no_leases_is_not_an_admission():
    with pytest.raises(LeaseFieldError, match="lease_ids"):
        _per_token_record(lease_ids=()).validate()


@pytest.mark.parametrize("bad", [None, "2.5", float("nan"), True])
def test_a_missing_reserved_cost_is_an_error_never_zero(bad):
    """The exact bug the audit found: absent cost must not read as free."""
    with pytest.raises(LeaseFieldError, match="never 0.0"):
        _per_token_record(reserved_cost_usd=bad).validate()


def test_a_per_token_record_needs_a_positive_cap_and_reservation():
    with pytest.raises(LeaseFieldError, match="hard_cap_usd"):
        _per_token_record(hard_cap_usd=None).validate()
    with pytest.raises(LeaseFieldError, match="unbudgeted run"):
        _per_token_record(reserved_cost_usd=0.0).validate()
    with pytest.raises(LeaseDeniedError, match="exceeds hard_cap_usd"):
        _per_token_record(reserved_cost_usd=25.0).validate()


def test_a_per_token_record_with_unknown_cost_is_denied():
    with pytest.raises(LeaseDeniedError, match="never free"):
        _per_token_record(cost_source=CostSource.UNKNOWN).validate()


def test_a_missing_cost_source_is_a_loud_error():
    with pytest.raises(LeaseFieldError, match="cost_source"):
        _per_token_record(cost_source=None).validate()
    with pytest.raises(LeaseFieldError, match="cost_source"):
        _per_token_record(cost_source="metered").validate()


def test_a_subscription_record_has_no_dollar_cap():
    """Positive: zero dollars, no cap. Negative: any dollar figure crosses the class boundary."""
    ok = _per_token_record(
        provider="anthropic",
        model="anthropic/claude-opus-5",
        reserved_cost_usd=0.0,
        hard_cap_usd=None,
        cost_source=CostSource.METERED,
    )
    ok.validate()
    assert ok.provider_class is ProviderClass.SUBSCRIPTION

    with pytest.raises(LeaseDeniedError, match="NO dollar cap"):
        _per_token_record(
            provider="anthropic", model="anthropic/claude-opus-5",
            reserved_cost_usd=0.0, hard_cap_usd=500.0, cost_source=CostSource.METERED,
        ).validate()
    with pytest.raises(LeaseDeniedError, match="must be 0.0"):
        _per_token_record(
            provider="anthropic", model="anthropic/claude-opus-5",
            reserved_cost_usd=3.0, hard_cap_usd=None, cost_source=CostSource.METERED,
        ).validate()


def test_an_unclassified_provider_record_is_refused():
    with pytest.raises(LeaseFieldError, match="no declared cost class"):
        _per_token_record(provider="mystery-corp").validate()


# ── Live framework Redis (skipped when the instance is down) ─────────────────────────────────


def _framework_redis_target() -> tuple[str, int] | None:
    """The reachable framework instance, from whichever side of the container boundary we are on.

    Tries the host publish (``127.0.0.1:6380``) then the in-network service
    (``finops-queue:6379``). Never probes the sandbox: both candidates are checked against
    :func:`assert_not_sandbox` first, so a misconfiguration cannot point this test at 6379 on the
    host loopback.
    """
    for host, port in (("127.0.0.1", FRAMEWORK_HOST_PORT), (FRAMEWORK_SERVICE_HOST, SANDBOX_HOST_PORT)):
        assert_not_sandbox(host, port)
        try:
            socket.create_connection((host, port), timeout=2).close()
            return host, port
        except OSError:
            continue
    return None


_LIVE_TARGET = _framework_redis_target()


@pytest.mark.skipif(
    _LIVE_TARGET is None,
    reason="framework Redis (finops-queue) not reachable on 127.0.0.1:6380 or finops-queue:6379",
)
def test_end_to_end_against_the_real_framework_redis():
    """Same flows, real WATCH/MULTI/EXEC — proves the transport, not just the policy.

    Runs in a throwaway namespace and deletes every key it created, so it cannot disturb the
    live queue's keyspace.
    """
    host, port = _LIVE_TARGET
    namespace = f"finops:lease:test:{uuid.uuid4().hex[:8]}"
    registry = LeaseRegistry.from_env(host=host, port=port, namespace=namespace)
    scope = LeaseScope(ScopeKind.CAMPAIGN, "pytest")
    client = registry._r  # the connected client, for cleanup only
    try:
        registry.set_cap(LeaseKind.BUDGET, scope, 2.0)
        first = registry.reserve_budget(
            ProviderClass.PER_TOKEN, scope, 1.5,
            run_id="pytest-a", cost_source=CostSource.ESTIMATED, ttl_seconds=60,
        )
        assert registry.outstanding(LeaseKind.BUDGET, scope) == 1.5
        with pytest.raises(LeaseDeniedError):
            registry.reserve_budget(
                ProviderClass.PER_TOKEN, scope, 1.0,
                run_id="pytest-b", cost_source=CostSource.ESTIMATED, ttl_seconds=60,
            )
        assert registry.release(first.lease_id) is not None
        assert registry.outstanding(LeaseKind.BUDGET, scope) == 0.0
    finally:
        keys = list(client.scan_iter(match=f"{namespace}*"))
        if keys:
            client.delete(*keys)
