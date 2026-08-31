"""Lease-watchdog tests — the expiry/kill rail, driven in both directions.

The work order's phase-4 verification names three claims, and each gets a positive and a negative
test here (plus an end-to-end pass through the *real* registry and admission controller, because
the interesting failure mode of this rail is not a logic bug — it is the quarantine handles
failing to travel from the admission request onto the lease the watchdog actually sees):

1. **An expired lease produces a flag within the watchdog window.**
   Positive: a lease expired one second ago is flagged on the next pass. Negative: a *live*
   lease produces nothing — a watchdog that flags healthy work is one operators learn to ignore.

2. **A quarantined worktree is excluded from the analyze/data chain.**
   Positive: the identity marked by a budget expiry is excluded by the consult filter the
   analyze and inventory scripts call. Negative: a *concurrency* expiry quarantines nothing, and
   a clean worktree survives.

3. **The flag is advisory (no automatic steering).**
   Asserted structurally (``steering_actions == 0``, every flag says so) and behaviourally: the
   pass is given a registry whose only mutating capability is the lease sweep, and the module
   imports nothing that could kill, retry, or reschedule.

Transport is faked; policy is real. ``FakeRedis`` is the same WATCH/MULTI/EXEC-faithful double
``tests/test_lease_registry.py`` uses, imported from there rather than re-implemented, so the
registry's real compare-and-set loop runs underneath these tests.
"""

from __future__ import annotations

import json

import pytest

from agentic_dynamics.control.admission import AdmissionController, AdmissionRequest
from agentic_dynamics.control.lease_registry import (
    CostSource,
    Lease,
    LeaseKind,
    LeaseRegistry,
    LeaseScope,
    LeaseUnavailableError,
    ProviderClass,
    ScopeKind,
)
from agentic_dynamics.control.lease_watchdog import (
    FLAG_STATUS_BUDGET,
    FLAG_STATUS_CONCURRENCY,
    WATCHDOG_SOURCE,
    LeaseObservation,
    build_flag,
    format_report,
    observe,
    report_json,
    sweep_once,
)
from agentic_dynamics.control.quarantine import (
    QuarantineKind,
    QuarantineReason,
    QuarantineRegistry,
    filter_quarantined_paths,
)
from agentic_dynamics.control.supervisor import SUPERVISOR_FLAGS_KEY, normalize_flag

# The registry's own transport double — reused so these tests exercise the real lock loop.
from tests.test_lease_registry import FakeRedis as RegistryFakeRedis

#: A fixed "now" so overdue arithmetic is exact rather than approximately-a-second.
NOW = 2_000_000.0


class FakeRedis(RegistryFakeRedis):
    """The registry's double plus the two list commands the flag hot path uses.

    Subclassed rather than added to ``tests/test_lease_registry.py``: that double documents an
    exact command surface ("anything else is intentionally absent so a future command has to be
    added deliberately"), and the flag push is a *different* module's surface. Extending here
    keeps each double describing the commands its own subject actually issues.
    """

    def __init__(self) -> None:
        super().__init__()
        self.lists: dict[str, list[str]] = {}

    def lpush(self, key: str, value: str) -> int:
        self._check()
        self.lists.setdefault(key, []).insert(0, value)
        return len(self.lists[key])

    def ltrim(self, key: str, start: int, end: int) -> bool:
        self._check()
        self.lists[key] = self.lists.get(key, [])[start:end + 1]
        return True


# ── Fixtures ─────────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def rig(tmp_path):
    """A lease registry + quarantine ledger + flags file, all on a frozen clock.

    Returns a small namespace rather than a tuple because the tests read four things out of it
    and positional unpacking of four values is where test-fixture bugs live.
    """

    class Rig:
        def __init__(self) -> None:
            self.clock = {"now": NOW}
            self.redis = FakeRedis()
            self.registry = LeaseRegistry(self.redis, now_fn=lambda: self.clock["now"])
            self.flags_path = tmp_path / "flags.jsonl"
            self.quarantine = QuarantineRegistry(
                ledger_path=tmp_path / "quarantine.jsonl",
                now_fn=lambda: self.clock["now"],
            )

        def sweep(self):
            """One watchdog pass on the frozen clock."""
            return sweep_once(
                self.registry,
                self.quarantine,
                redis_client=self.redis,
                flags_path=self.flags_path,
                now=self.clock["now"],
            )

        def flag_lines(self) -> list[dict]:
            """The durable flags written so far."""
            if not self.flags_path.exists():
                return []
            return [
                json.loads(line)
                for line in self.flags_path.read_text().splitlines()
                if line.strip()
            ]

    return Rig()


def _reserve_budget(rig, *, ttl: int, worktree: str = "wt_x", namespace: str = "ns_x") -> Lease:
    """Take a per-token budget lease carrying the quarantine handles the controller stamps."""
    rig.registry.set_cap(LeaseKind.BUDGET, LeaseScope(ScopeKind.PROVIDER, "deepseek"), 100.0)
    return rig.registry.reserve_budget(
        ProviderClass.PER_TOKEN,
        LeaseScope(ScopeKind.PROVIDER, "deepseek"),
        1.50,
        run_id="run-1",
        cost_source=CostSource.ESTIMATED,
        ttl_seconds=ttl,
        metadata={
            "model": "deepseek/deepseek-v4-flash",
            "worktree_identity": worktree,
            "result_namespace": namespace,
        },
    )


def _reserve_concurrency(rig, *, ttl: int, worktree: str = "wt_slot") -> Lease:
    """Take a concurrency lease — the class that flags but never quarantines."""
    rig.registry.set_cap(LeaseKind.CONCURRENCY, LeaseScope(ScopeKind.FLEET, "default"), 8)
    return rig.registry.reserve_concurrency(
        LeaseScope(ScopeKind.FLEET, "default"),
        1,
        run_id="run-2",
        ttl_seconds=ttl,
        metadata={
            "model": "anthropic/claude-sonnet-5",
            "worktree_identity": worktree,
            "result_namespace": "ns_slot",
        },
    )


# ── 1. An expired lease produces a flag within the watchdog window ──────────────────────────


def test_an_expired_budget_lease_is_flagged(rig):
    """GRANT direction: the pass after expiry produces exactly one advisory flag."""
    _reserve_budget(rig, ttl=60)
    rig.clock["now"] += 61.0  # one second past the TTL — inside the next watchdog window

    result = rig.sweep()

    assert len(result.observations) == 1
    assert len(result.flags) == 1
    flag = result.flags[0]
    assert flag["status"] == FLAG_STATUS_BUDGET
    assert flag["session_id"] == "run-1"
    assert "Advisory only" in flag["why"]
    # …and it landed durably as well as in memory.
    assert len(rig.flag_lines()) == 1


def test_an_expired_concurrency_lease_is_flagged_with_its_own_status(rig):
    """Both classes are observed; the status distinguishes them for the board's filter."""
    _reserve_concurrency(rig, ttl=30)
    rig.clock["now"] += 31.0

    result = rig.sweep()

    assert len(result.flags) == 1
    assert result.flags[0]["status"] == FLAG_STATUS_CONCURRENCY
    assert "outlived its execution slot" in result.flags[0]["why"]


def test_a_live_lease_produces_no_flag(rig):
    """REFUSE direction — the load-bearing negative: healthy work is never flagged."""
    _reserve_budget(rig, ttl=3600)
    rig.clock["now"] += 60.0  # well inside the TTL

    result = rig.sweep()

    assert result.observations == []
    assert result.flags == []
    assert result.quarantines == []
    assert rig.flag_lines() == []


def test_the_sweep_is_total_so_an_old_expiry_is_still_caught(rig):
    """The "within one window" bound: an expiry from hours ago is flagged on the next pass.

    The guarantee is not "flagged promptly after expiring" but "flagged on the first pass that
    follows", which only holds because the sweep walks every scope in the registry index rather
    than a recent-changes queue.
    """
    _reserve_budget(rig, ttl=60)
    rig.clock["now"] += 10_000.0  # nearly three hours late

    result = rig.sweep()

    assert len(result.flags) == 1
    assert result.observations[0].overdue_seconds == pytest.approx(9_940.0)


def test_the_flag_survives_supervisor_normalization(rig):
    """The flag rides the SAME ``supervisor_flags`` list as a session flag, so it must normalize.

    If ``normalize_flag`` dropped it, the Control Room would render nothing and the rail would be
    silently inert — the failure mode a watchdog can least afford.
    """
    _reserve_budget(rig, ttl=60)
    rig.clock["now"] += 61.0
    result = rig.sweep()

    normalized = normalize_flag(result.flags[0])
    assert normalized is not None
    assert normalized["lease"]["lease_id"] == result.observations[0].lease_id
    assert "flag_id" in normalized


def test_the_flag_reaches_the_redis_hot_path(rig):
    """The bounded hot list is what the Control Room reads; the JSONL is what survives a restart."""
    _reserve_budget(rig, ttl=60)
    rig.clock["now"] += 61.0
    rig.sweep()

    pushed = rig.redis.lists.get(SUPERVISOR_FLAGS_KEY, [])
    assert len(pushed) == 1
    assert json.loads(pushed[0])["status"] == FLAG_STATUS_BUDGET


def test_a_down_hot_path_never_costs_the_durable_flag(rig, tmp_path):
    """Durable first, Redis second — an outage degrades the board, not the record."""
    _reserve_budget(rig, ttl=60)
    rig.clock["now"] += 61.0

    # Sweep with a Redis that fails only on the flag push (the registry read already happened).
    result = sweep_once(
        rig.registry,
        rig.quarantine,
        redis_client=_ExplodingPush(),
        flags_path=rig.flags_path,
        now=rig.clock["now"],
    )
    assert len(result.flags) == 1
    assert len(rig.flag_lines()) == 1


class _ExplodingPush:
    """A Redis double whose only behaviour is to fail the flag push."""

    def lpush(self, *_args, **_kwargs):
        raise ConnectionError("redis is down")

    def ltrim(self, *_args, **_kwargs):
        raise ConnectionError("redis is down")


# ── 2. A quarantined worktree is excluded from the analyze/data chain ───────────────────────


def test_an_expired_budget_lease_quarantines_both_output_surfaces(rig):
    """A run writes code to a worktree and data to a namespace; marking one leaves a path back."""
    _reserve_budget(rig, ttl=60, worktree="wt_contaminated", namespace="ns_contaminated")
    rig.clock["now"] += 61.0

    result = rig.sweep()

    kinds = {(r.kind, r.identity) for r in result.quarantines}
    assert kinds == {
        (QuarantineKind.WORKTREE, "wt_contaminated"),
        (QuarantineKind.RESULT_NAMESPACE, "ns_contaminated"),
    }
    assert all(r.reason is QuarantineReason.BUDGET_LEASE_EXPIRED for r in result.quarantines)
    assert all(r.source == WATCHDOG_SOURCE for r in result.quarantines)


def test_the_quarantined_worktree_is_excluded_by_the_analyze_consult(rig):
    """The end of the chain: what the watchdog marks, ``discover_worktrees`` drops.

    This calls the exact helper ``scripts/analyze_worktrees.py`` and ``scripts/inventory.py``
    call, so the exclusion is verified through the real consult path rather than by re-asserting
    the registry's own bookkeeping.
    """
    _reserve_budget(rig, ttl=60, worktree="exp_contaminated")
    rig.clock["now"] += 61.0
    rig.sweep()

    kept, excluded = filter_quarantined_paths(
        ["/tmp/exp_clean", "/tmp/exp_contaminated"], registry=rig.quarantine
    )
    assert kept == ["/tmp/exp_clean"]
    assert excluded == ["/tmp/exp_contaminated"]


def test_a_concurrency_expiry_quarantines_nothing(rig):
    """REFUSE direction: a slot overrun is a throughput problem, not a contamination one.

    The distinction is the module's central judgement — quarantining fully-paid-for work whose
    only sin was running one slot wide would make the ledger noise.
    """
    _reserve_concurrency(rig, ttl=30, worktree="wt_slot")
    rig.clock["now"] += 31.0

    result = rig.sweep()

    assert len(result.flags) == 1, "it is still observed…"
    assert result.quarantines == [], "…but its output is not contaminated"
    kept, excluded = filter_quarantined_paths(["/tmp/wt_slot"], registry=rig.quarantine)
    assert kept == ["/tmp/wt_slot"] and excluded == []


def test_a_live_lease_quarantines_nothing(rig):
    """The other negative: nothing expired, so the corpus is untouched."""
    _reserve_budget(rig, ttl=3600, worktree="wt_healthy")
    rig.clock["now"] += 60.0
    rig.sweep()

    kept, excluded = filter_quarantined_paths(["/tmp/wt_healthy"], registry=rig.quarantine)
    assert kept == ["/tmp/wt_healthy"] and excluded == []


def test_re_sweeping_the_same_expiry_does_not_re_quarantine(rig):
    """Idempotence across passes — the watchdog runs on a cadence, the ledger must not grow.

    (The second pass observes nothing because ``expire_leases`` already reclaimed the lease; the
    assertion that matters is that the *ledger* is unchanged either way.)
    """
    _reserve_budget(rig, ttl=60)
    rig.clock["now"] += 61.0
    first = rig.sweep()
    rig.clock["now"] += 300.0
    second = rig.sweep()

    assert len(first.quarantines) == 2
    assert second.quarantines == []
    assert len(rig.quarantine.entries()) == 2


def test_a_budget_expiry_without_identity_is_reported_not_dropped(rig):
    """An unattributable expiry is the worst state — so it must be the loudest, not the quietest.

    A lease taken outside the controller (or by an older code path) carries no quarantine handle.
    There is nothing to mark, but the expiry still happened and still needs a human, so it lands
    in ``unattributable`` *and* in ``errors`` rather than being silently skipped.
    """
    rig.registry.set_cap(LeaseKind.BUDGET, LeaseScope(ScopeKind.PROVIDER, "deepseek"), 100.0)
    rig.registry.reserve_budget(
        ProviderClass.PER_TOKEN,
        LeaseScope(ScopeKind.PROVIDER, "deepseek"),
        1.0,
        run_id="run-orphan",
        cost_source=CostSource.ESTIMATED,
        ttl_seconds=60,
        metadata={"model": "deepseek/deepseek-v4-flash"},  # no identity fields
    )
    rig.clock["now"] += 61.0

    result = rig.sweep()

    assert len(result.flags) == 1, "still flagged"
    assert result.quarantines == [], "nothing to mark"
    assert len(result.unattributable) == 1
    assert any("cannot be quarantined by identity" in e for e in result.errors)


def test_a_partial_identity_still_quarantines_the_surface_it_has(rig):
    """Half a handle is better than none: mark what we can name, don't discard the whole expiry."""
    _reserve_budget(rig, ttl=60, worktree="wt_only", namespace="")
    rig.clock["now"] += 61.0

    result = rig.sweep()

    assert [(r.kind, r.identity) for r in result.quarantines] == [
        (QuarantineKind.WORKTREE, "wt_only")
    ]
    assert result.unattributable == []


# ── 3. The flag is advisory (no automatic steering) ─────────────────────────────────────────


def test_a_pass_takes_zero_steering_actions(rig):
    """The observe-only contract, made assertable rather than merely documented."""
    _reserve_budget(rig, ttl=60)
    _reserve_concurrency(rig, ttl=60)
    rig.clock["now"] += 61.0

    result = rig.sweep()

    assert result.steering_actions == 0
    assert result.to_dict()["advisory"] is True
    assert len(result.observations) == 2


def test_the_watchdog_imports_nothing_that_could_steer():
    """A structural guard: the rail must not acquire a kill/retry capability by accident.

    ``control.orphan_sweep`` reaps processes and ``runtime`` can start them; importing either
    here would be the first step toward a watchdog that acts. The supervisor rail is observe-only
    and this test is what notices when that stops being true.
    """
    import inspect

    from agentic_dynamics.control import lease_watchdog

    source = inspect.getsource(lease_watchdog)
    for forbidden in ("subprocess", "os.kill", "SIGTERM", "SIGKILL", "psutil"):
        assert forbidden not in source, (
            f"the lease watchdog must not be able to steer, but references {forbidden!r}"
        )


def test_the_watchdog_never_releases_or_reissues_a_lease(rig):
    """Observing an expiry must not hand the work a fresh claim — that would be steering.

    The registry's sweep reclaims the *headroom* (that is bookkeeping). What must not happen is a
    new lease appearing for the same run, which would silently re-admit unadmitted work.
    """
    _reserve_budget(rig, ttl=60)
    rig.clock["now"] += 61.0
    rig.sweep()

    live = rig.registry.leases(LeaseKind.BUDGET, LeaseScope(ScopeKind.PROVIDER, "deepseek"))
    assert live == [], "the expired claim is reclaimed and NOT replaced"


# ── Robustness: one bad thing must not silence the pass ─────────────────────────────────────


def test_a_registry_that_cannot_be_swept_reports_rather_than_faking_a_clean_pass(rig):
    """An unreachable registry yields an error, never an empty "all clear"."""
    rig.redis.fail_with = ConnectionError("redis is down")

    result = rig.sweep()

    assert result.observations == []
    assert result.flags == []
    assert len(result.errors) == 1
    assert "no expiries could be observed" in result.errors[0]


def test_one_unwritable_quarantine_does_not_abort_the_pass(rig, monkeypatch):
    """A failed mark is collected, and the remaining surfaces are still attempted."""
    _reserve_budget(rig, ttl=60, worktree="wt_a", namespace="ns_a")
    rig.clock["now"] += 61.0

    real = rig.quarantine.quarantine
    calls = {"n": 0}

    def flaky(kind, identity, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("disk full")
        return real(kind, identity, **kwargs)

    monkeypatch.setattr(rig.quarantine, "quarantine", flaky)
    result = rig.sweep()

    assert len(result.quarantines) == 1, "the second surface was still marked"
    assert any("disk full" in e for e in result.errors)


def test_a_registry_on_the_story_agent_sandbox_is_refused():
    """Defence in depth: a lease registry on a DB story agents ``flushall()`` is not a registry."""
    with pytest.raises(LeaseUnavailableError):
        LeaseRegistry.from_env(host="127.0.0.1", port=6379)


# ── Projections ──────────────────────────────────────────────────────────────────────────────


def test_observe_reads_the_handles_defensively():
    """A lease with no metadata at all must project cleanly, not raise."""
    lease = Lease(
        lease_id="l1",
        kind=LeaseKind.BUDGET,
        scope=LeaseScope(ScopeKind.PROVIDER, "deepseek"),
        provider_class=ProviderClass.PER_TOKEN,
        amount=1.0,
        unit="usd",
        hard_cap=10.0,
        expires_at=NOW - 5.0,
        granted_at=NOW - 65.0,
        run_id="run-x",
        metadata={},
    )
    observation = observe(lease, now=NOW)
    assert observation.overdue_seconds == pytest.approx(5.0)
    assert observation.attributable is False
    assert observation.worktree_identity == ""


def test_the_report_names_the_advisory_contract(rig):
    """The operator-facing line says what was NOT done, because that is the surprising part."""
    _reserve_budget(rig, ttl=60)
    rig.clock["now"] += 61.0
    text = format_report(rig.sweep())
    assert "ADVISORY" in text
    assert "0 steering actions taken" in text


def test_an_empty_pass_reports_quietly(rig):
    """Nothing expired is the normal case and must not look like an incident."""
    assert "no expired leases" in format_report(rig.sweep())


def test_the_json_report_is_stable_keyed(rig):
    """``--json`` output must diff cleanly across passes, so keys are sorted."""
    _reserve_budget(rig, ttl=60)
    rig.clock["now"] += 61.0
    payload = json.loads(report_json(rig.sweep()))
    assert payload["advisory"] is True
    assert payload["steering_actions"] == 0
    assert list(payload) == sorted(payload)


def test_build_flag_truncates_an_overlong_title():
    """``normalize_flag`` requires strings; the title budget is 80 chars, like supervise.py's."""
    observation = LeaseObservation(
        lease_id="l" * 200,
        kind=LeaseKind.BUDGET.value,
        scope="provider/deepseek",
        run_id="run-1",
        model="deepseek/deepseek-v4-flash",
        provider_class="per_token",
        amount=1.0,
        unit="usd",
        expires_at=NOW,
        overdue_seconds=1.0,
    )
    assert len(build_flag(observation)["title"]) <= 80


# ── End to end: the handles must actually travel from admission to quarantine ───────────────


def test_admission_stamps_the_handles_so_the_watchdog_can_quarantine(rig):
    """The integration that the whole rail depends on, through the real controller.

    Every other test in this file constructs leases with the handles already present. This one
    proves the *controller* puts them there — the seam where a rename or a dropped kwarg would
    turn every budget expiry into an unattributable one without failing a single unit test.
    """
    rig.registry.set_cap(LeaseKind.BUDGET, LeaseScope(ScopeKind.PROVIDER, "deepseek"), 100.0)
    rig.registry.set_cap(LeaseKind.CONCURRENCY, LeaseScope(ScopeKind.FLEET, "default"), 8)
    controller = AdmissionController(registry=rig.registry)

    admission = controller.admit(
        AdmissionRequest(
            run_id="run-e2e",
            model="deepseek/deepseek-v4-flash",
            worktree_identity="wt_e2e",
            result_namespace="ns_e2e",
            amount=2.0,
            cost_source=CostSource.ESTIMATED,
            hard_cap_usd=50.0,
            ttl_seconds=60,
        )
    )
    # Both lease kinds carry the handles — the concurrency one too, so a future policy change
    # could quarantine on slot overruns without another round of plumbing.
    assert admission.budget_lease.metadata["worktree_identity"] == "wt_e2e"
    assert admission.concurrency_leases[0].metadata["result_namespace"] == "ns_e2e"

    rig.clock["now"] += 61.0
    result = rig.sweep()

    assert {(r.kind, r.identity) for r in result.quarantines} == {
        (QuarantineKind.WORKTREE, "wt_e2e"),
        (QuarantineKind.RESULT_NAMESPACE, "ns_e2e"),
    }
    kept, excluded = filter_quarantined_paths(["/tmp/wt_e2e"], registry=rig.quarantine)
    assert kept == [] and excluded == ["/tmp/wt_e2e"]


def test_a_released_admission_never_reaches_the_watchdog(rig):
    """The happy path: work that settles inside its lease produces no flag and no quarantine.

    Without this, "the watchdog flags expiries" would be indistinguishable from "the watchdog
    flags everything", and the rail's whole value is the distinction.
    """
    rig.registry.set_cap(LeaseKind.BUDGET, LeaseScope(ScopeKind.PROVIDER, "deepseek"), 100.0)
    rig.registry.set_cap(LeaseKind.CONCURRENCY, LeaseScope(ScopeKind.FLEET, "default"), 8)
    controller = AdmissionController(registry=rig.registry)

    admission = controller.admit(
        AdmissionRequest(
            run_id="run-clean",
            model="deepseek/deepseek-v4-flash",
            worktree_identity="wt_clean",
            result_namespace="ns_clean",
            amount=2.0,
            cost_source=CostSource.ESTIMATED,
            hard_cap_usd=50.0,
            ttl_seconds=3600,
        )
    )
    rig.clock["now"] += 60.0
    controller.release(admission)  # the work settled well inside its claim
    rig.clock["now"] += 10_000.0  # …and now long past when the lease WOULD have expired

    result = rig.sweep()

    assert result.observations == [], "a released lease cannot expire"
    assert result.quarantines == []
    kept, _excluded = filter_quarantined_paths(["/tmp/wt_clean"], registry=rig.quarantine)
    assert kept == ["/tmp/wt_clean"]
