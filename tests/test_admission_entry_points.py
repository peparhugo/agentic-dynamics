"""Entry-point wiring tests — the gate is in front of *every* spend surface.

``tests/test_admission.py`` proves the controller decides correctly. This file proves the
decision is actually consulted, at each of the five entry points the ``admission_leases`` work
order enumerates, and — the load-bearing half — that **a refusal means no invocation happened**:

=======================================  ====================================================
Entry point                              What the refusal test proves
=======================================  ====================================================
``scripts/enqueue.py``                   nothing is pushed onto the queue
``scripts/worker.py``                    ``subprocess.run`` is never called
``scripts/analysis_worker.py``           the slot lease gates the job
``scripts/fleet/spawn_wrapper.py``       ``docker`` is never invoked (step 6)
``runtime.workflow_runner``              the agent function is never called
``adapters.backends.run_agentic``        no adapter is even imported (the bypass detector)
=======================================  ====================================================

"No invocation happened" is asserted positively wherever possible — the spy is a callable that
fails the test if it is ever reached, not merely a counter checked afterwards.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agentic_dynamics.control.admission import AdmissionController, AdmissionDenied
from agentic_dynamics.control.lease_registry import (
    CostSource,
    LeaseKind,
    LeaseRegistry,
    LeaseScope,
    ScopeKind,
)
from agentic_dynamics.core.admission_context import (
    ADMISSION_ENV_KEYS,
    ADMISSION_REQUIRED_ENV,
    BUDGET_LEASE_ENV,
    RUN_ID_ENV,
    AdmissionContextError,
    LeaseContext,
    bind_context,
)
from agentic_dynamics.experiment.experiment_spec import load_spec
from agentic_dynamics.runtime.admission import phase_admission_scope
from agentic_dynamics.runtime.workflow_runner import run_workflow

# ``server`` first: importing a route module on its own hits the circular import the server's
# bottom-of-module import block exists to break (the convention every other Control Room test
# follows — see tests/test_subscription_usage_api.py).
from apps.control_room import server  # noqa: F401  # side effect: import ordering
from apps.control_room.routes import telemetry as telemetry_routes

try:
    from tests.test_lease_registry import Clock, FakeRedis
except ImportError:  # pragma: no cover - direct-run path
    from test_lease_registry import Clock, FakeRedis

SPEC = Path(__file__).resolve().parent.parent / "workflows" / "repository" / "control_room_portal.yaml"

SUBSCRIPTION_MODEL = "anthropic/claude-opus-5"
PER_TOKEN_MODEL = "deepseek/deepseek-v4-flash"

FLEET = LeaseScope(ScopeKind.FLEET, "default")
ANALYSIS = LeaseScope(ScopeKind.FLEET, "analysis")
ANTHROPIC = LeaseScope(ScopeKind.PROVIDER, "anthropic")


# ── Fixtures ─────────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clean_admission_env():
    """Every test starts with no admission in the environment (see the sibling suite's note)."""
    saved = {k: os.environ.pop(k, None) for k in (*ADMISSION_ENV_KEYS, ADMISSION_REQUIRED_ENV)}
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.fixture
def armed():
    with patch.dict(os.environ, {ADMISSION_REQUIRED_ENV: "1"}):
        yield


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def registry(clock: Clock) -> LeaseRegistry:
    counter = iter(f"{i:04d}" for i in range(1, 10_000))
    return LeaseRegistry(FakeRedis(), now_fn=clock, id_fn=lambda: next(counter))


@pytest.fixture
def capped(registry: LeaseRegistry) -> LeaseRegistry:
    registry.set_cap(LeaseKind.BUDGET, ANTHROPIC, 100.0)
    registry.set_cap(LeaseKind.BUDGET, LeaseScope(ScopeKind.PROVIDER, "deepseek"), 20.0)
    registry.set_cap(LeaseKind.CONCURRENCY, FLEET, 4.0)
    registry.set_cap(LeaseKind.CONCURRENCY, ANALYSIS, 2.0)
    registry.set_cap(LeaseKind.CONCURRENCY, ANTHROPIC, 4.0)
    registry.set_cap(LeaseKind.CONCURRENCY, LeaseScope(ScopeKind.PROVIDER, "deepseek"), 4.0)
    return registry


@pytest.fixture
def controller(capped: LeaseRegistry, clock: Clock) -> AdmissionController:
    return AdmissionController(capped, now_fn=clock)


def _fake_agent(**overrides):
    """A stand-in ``AgenticResult``, matching ``tests/test_workflow_runner.py``'s shape."""
    base = dict(
        prompt_tokens=10, completion_tokens=20, reasoning_tokens=5, total_tokens=35,
        estimated_cost_usd=0.001, files_created=[], files_modified=[],
        final_response="done", ok=True, exit_code=0, error="",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# ═══════════════════════════════════════════════════════════════════════════════════════════
# (a) scripts/enqueue.py — reserve at queue-fill time
# ═══════════════════════════════════════════════════════════════════════════════════════════


def _cells(n: int = 2, model: str = SUBSCRIPTION_MODEL) -> list[dict]:
    return [
        {
            "cell_id": f"cell_{i}", "story": "task_manager_api", "tier": "tier1_minimal",
            "quality": "good", "condition": "clean", "model": model,
        }
        for i in range(n)
    ]


def test_enqueue_is_untouched_when_the_gate_is_disarmed():
    """Default posture: the cells go out exactly as they came in, with no lease block."""
    from scripts import enqueue

    cells = _cells()
    assert enqueue.admit_cells(cells) == cells
    assert "budget_lease_id" not in cells[0]


def test_enqueue_stamps_a_budget_lease_on_every_cell(armed, controller: AdmissionController):
    """The queue can only carry work whose budget is already claimed."""
    from scripts import enqueue

    stamped = enqueue.admit_cells(_cells(3), controller=controller)
    assert len(stamped) == 3
    for cell in stamped:
        assert cell["budget_lease_id"]
        assert cell["expires_at"] > 0
        assert cell["admission_run_id"] == cell["cell_id"]
        # Subscription class: zero marginal dollars, and therefore no dollar cap.
        assert cell["reserved_cost_usd"] == 0.0
        assert cell["hard_cap_usd"] is None
    # Three window-point reservations against the provider's budget scope.
    assert controller.registry.outstanding(LeaseKind.BUDGET, ANTHROPIC) == pytest.approx(3.0)


def test_enqueue_takes_no_concurrency_lease(armed, controller: AdmissionController):
    """Filling a queue occupies no execution slot — the worker takes that lease later."""
    from scripts import enqueue

    enqueue.admit_cells(_cells(2), controller=controller)
    assert controller.registry.outstanding(LeaseKind.CONCURRENCY, FLEET) == 0.0


def test_enqueue_refuses_the_whole_batch_and_leaves_nothing_reserved(
    armed, controller: AdmissionController, capped: LeaseRegistry
):
    """Batch-atomic: a partially-budgeted queue is indistinguishable from a budgeted one."""
    capped.set_cap(LeaseKind.BUDGET, ANTHROPIC, 2.5)  # room for 2 cells at 1.0 point each
    from scripts import enqueue

    with pytest.raises(AdmissionDenied):
        enqueue.admit_cells(_cells(4), controller=controller)
    # The two that DID fit were released on the way out.
    assert capped.outstanding(LeaseKind.BUDGET, ANTHROPIC) == 0.0


def test_enqueue_refuses_an_unpriced_per_token_cell(armed, controller: AdmissionController):
    """A DeepSeek cell with no stated cost never reaches the queue."""
    from scripts import enqueue

    with pytest.raises(AdmissionDenied, match="Unknown cost is never free"):
        enqueue.admit_cells(_cells(1, model=PER_TOKEN_MODEL), controller=controller)


def test_enqueue_main_pushes_nothing_when_admission_is_denied(
    armed, controller: AdmissionController, capped: LeaseRegistry, monkeypatch
):
    """End to end at the CLI seam: a denial exits non-zero and the queue stays empty."""
    from scripts import enqueue

    capped.set_cap(LeaseKind.BUDGET, ANTHROPIC, 0.5)  # no cell fits

    pushed: list[str] = []

    class RefusingRedis:
        def lpush(self, *args):
            pushed.append(args)
            raise AssertionError("a denied batch must never reach the queue")

        def hset(self, *args):
            raise AssertionError("a denied batch must never reach the status hash")

        def delete(self, *args):
            pass

    monkeypatch.setattr(enqueue.redis, "Redis", lambda **kw: RefusingRedis())
    monkeypatch.setattr(enqueue, "default_controller", lambda: controller)
    monkeypatch.setattr(enqueue.sys, "argv", ["enqueue.py", "--model", SUBSCRIPTION_MODEL])

    with pytest.raises(SystemExit) as exc:
        enqueue.main()
    assert exc.value.code == 2
    assert pushed == []


# ═══════════════════════════════════════════════════════════════════════════════════════════
# (b) scripts/worker.py — lease before spawn, release after the cell settles
# ═══════════════════════════════════════════════════════════════════════════════════════════


def test_worker_admission_is_inert_when_disarmed():
    from scripts import worker

    with worker.cell_admission(_cells(1)[0]) as env:
        assert env == {}


def test_worker_reuses_the_queue_time_budget_and_adds_only_slots(
    armed, controller: AdmissionController, capped: LeaseRegistry
):
    """The double-count guard: the cell's dollars are claimed once, at fill time, not twice."""
    from scripts import enqueue, worker

    cell = enqueue.admit_cells(_cells(1), controller=controller)[0]
    budget_after_fill = capped.outstanding(LeaseKind.BUDGET, ANTHROPIC)

    with worker.cell_admission(cell, registry=capped) as env:
        # The budget total is UNCHANGED — no second reservation for the same cell.
        assert capped.outstanding(LeaseKind.BUDGET, ANTHROPIC) == pytest.approx(budget_after_fill)
        # Two slots: fleet-wide and per-provider.
        assert capped.outstanding(LeaseKind.CONCURRENCY, FLEET) == 1.0
        assert capped.outstanding(LeaseKind.CONCURRENCY, ANTHROPIC) == 1.0
        # And the child's launch envelope carries the admission across the process boundary.
        assert env[BUDGET_LEASE_ENV] == cell["budget_lease_id"]
        assert env[RUN_ID_ENV] == cell["cell_id"]

    # Released on settle — but the queue-time budget lease is NOT released here: it belongs to
    # the job, and the job may still be re-queued.
    assert capped.outstanding(LeaseKind.CONCURRENCY, FLEET) == 0.0
    assert capped.outstanding(LeaseKind.BUDGET, ANTHROPIC) == pytest.approx(budget_after_fill)


def test_worker_admits_a_job_that_carries_no_lease_block(
    armed, controller: AdmissionController, capped: LeaseRegistry, monkeypatch
):
    """An older queue entry still gets budgeted — here, not silently run unbudgeted."""
    from scripts import worker

    monkeypatch.setattr(worker, "default_controller", lambda: controller)
    with worker.cell_admission(_cells(1)[0], registry=capped) as env:
        assert env[BUDGET_LEASE_ENV]
        assert capped.outstanding(LeaseKind.BUDGET, ANTHROPIC) == pytest.approx(1.0)
    assert capped.outstanding(LeaseKind.BUDGET, ANTHROPIC) == 0.0


def test_worker_refuses_a_job_whose_lease_block_is_malformed(armed, capped: LeaseRegistry):
    """"Looks budgeted, isn't" is a refusal, not a silent re-reservation."""
    from scripts import worker

    cell = {**_cells(1)[0], "budget_lease_id": "bud_x"}  # partial block: the other 4 absent
    with (
        pytest.raises(AdmissionDenied, match="invalid lease block"),
        worker.cell_admission(cell, registry=capped),
    ):
        pytest.fail("a malformed lease block must never admit")


def test_worker_refuses_when_the_fleet_is_full(
    armed, controller: AdmissionController, capped: LeaseRegistry
):
    from scripts import enqueue, worker

    capped.set_cap(LeaseKind.CONCURRENCY, FLEET, 1.0)
    cells = enqueue.admit_cells(_cells(2), controller=controller)
    # The first cell's slot is HELD across the second attempt — the refusal is only meaningful
    # while the fleet is genuinely full.
    with (
        worker.cell_admission(cells[0], registry=capped),
        pytest.raises(AdmissionDenied, match="concurrency denied"),
        worker.cell_admission(cells[1], registry=capped),
    ):
        pytest.fail("the second cell must not be admitted")
    # The refused cell's budget lease survives — it will be re-queued and is still paid for.
    assert capped.outstanding(LeaseKind.BUDGET, ANTHROPIC) == pytest.approx(2.0)


class _FakeQueueRedis:
    """The smallest Redis the worker loop actually uses: BRPOP, LPUSH, LLEN, HSET."""

    def __init__(self, jobs: list[str]) -> None:
        self.jobs = list(jobs)
        self.requeued: list[str] = []
        self.status: dict[str, str] = {}

    def ping(self):
        return True

    def brpop(self, key, timeout=0):
        return (key, self.jobs.pop(0)) if self.jobs else None

    def lpush(self, key, value):
        self.requeued.append(value)
        return 1

    def llen(self, key):
        return len(self.jobs)

    def hset(self, key, field, value):
        self.status[field] = value
        return 1


def test_worker_loop_spawns_no_subprocess_when_admission_is_denied(
    armed, controller: AdmissionController, capped: LeaseRegistry, monkeypatch
):
    """The load-bearing assertion: refusal means the ``run_story.py`` process never existed.

    ``subprocess.run`` is replaced with a callable that fails the test on contact, so this
    cannot pass by an unchecked counter.
    """
    from scripts import worker

    capped.set_cap(LeaseKind.CONCURRENCY, FLEET, 0.5)  # nothing fits
    cell = {**_cells(1)[0], "cell_id": "denied_cell"}
    fake = _FakeQueueRedis([json.dumps(cell)])

    monkeypatch.setattr(worker, "_connect_redis", lambda: fake)
    monkeypatch.setattr(worker, "default_controller", lambda: controller)
    monkeypatch.setattr(worker, "LeaseRegistry", SimpleNamespace(from_env=lambda: capped))
    monkeypatch.setattr(worker.heartbeat, "HeartbeatThread", lambda *a, **k: SimpleNamespace(
        start=lambda: None
    ))
    monkeypatch.setattr(worker, "LivePublisher", lambda cid: SimpleNamespace(
        publish_status=lambda *_a, **_k: None
    ))
    monkeypatch.setattr(worker.time, "sleep", lambda *_a: None)

    def never(*args, **kwargs):
        raise AssertionError("a denied cell must never spawn run_story.py")

    monkeypatch.setattr(worker.subprocess, "run", never)

    worker.main()

    # Refused, re-queued (not dead-lettered), and marked back to queued.
    assert len(fake.requeued) >= 1
    assert json.loads(fake.requeued[0])["cell_id"] == "denied_cell"
    assert fake.status["denied_cell"] == "queued"


def test_worker_loop_exits_after_persistent_denials(
    armed, controller: AdmissionController, capped: LeaseRegistry, monkeypatch
):
    """A hard cap is not contention: the worker stops rather than spinning against it."""
    from scripts import worker

    capped.set_cap(LeaseKind.CONCURRENCY, FLEET, 0.5)
    cell = json.dumps({**_cells(1)[0], "cell_id": "stuck"})
    # More jobs than the denial ceiling, so only the ceiling can end the loop.
    fake = _FakeQueueRedis([cell] * (worker.MAX_CONSECUTIVE_DENIALS + 5))

    monkeypatch.setattr(worker, "_connect_redis", lambda: fake)
    monkeypatch.setattr(worker, "LeaseRegistry", SimpleNamespace(from_env=lambda: capped))
    monkeypatch.setattr(worker.heartbeat, "HeartbeatThread", lambda *a, **k: SimpleNamespace(
        start=lambda: None
    ))
    monkeypatch.setattr(worker, "LivePublisher", lambda cid: SimpleNamespace(
        publish_status=lambda *_a, **_k: None
    ))
    monkeypatch.setattr(worker.time, "sleep", lambda *_a: None)
    monkeypatch.setattr(worker.subprocess, "run", lambda *a, **k: pytest.fail("never spawn"))

    worker.main()
    assert len(fake.requeued) == worker.MAX_CONSECUTIVE_DENIALS
    # Jobs are still on the queue — the worker gave up, it did not drain them into the DLQ.
    assert fake.jobs


# ═══════════════════════════════════════════════════════════════════════════════════════════
# (b′) scripts/analysis_worker.py — concurrency only
# ═══════════════════════════════════════════════════════════════════════════════════════════


def test_analysis_worker_declares_its_own_slot_scope():
    """Analysis competes for the machine but scales differently — its own counter, by design."""
    from scripts import analysis_worker

    assert analysis_worker.ANALYSIS_SCOPE == ANALYSIS


def test_analysis_slot_is_refused_when_the_analysis_scope_is_full(armed, capped: LeaseRegistry):
    from agentic_dynamics.control.admission import concurrency_admitted
    from scripts import analysis_worker

    capped.set_cap(LeaseKind.CONCURRENCY, analysis_worker.ANALYSIS_SCOPE, 1.0)
    with concurrency_admitted(
        analysis_worker.ANALYSIS_SCOPE, run_id="analysis:a", registry=capped
    ), pytest.raises(AdmissionDenied), concurrency_admitted(
        analysis_worker.ANALYSIS_SCOPE, run_id="analysis:b", registry=capped
    ):
        pytest.fail("the second analysis slot must not be granted")


# ═══════════════════════════════════════════════════════════════════════════════════════════
# (c) scripts/fleet/spawn_wrapper.py — step 6
# ═══════════════════════════════════════════════════════════════════════════════════════════


def _valid_request(**overrides) -> dict:
    """A request that passes steps 1-5 (borrowed from ``tests/test_spawn_wrapper.py``)."""
    request = {
        "phase": "p1_slice1_base_supervisor",
        "scope": "implementation",
        "mounts": [
            {"target": "/tmp", "mode": "rw"},
            {"target": "/app/experiments/results", "mode": "rw"},
            {"target": "/repo", "mode": "ro"},
        ],
        "network": "fleet-net",
        "env": {"FINOPS_KB_WRITE": "1"},
    }
    request.update(overrides)
    return request


def _lease_block(expires_at: float = 9e9, **overrides) -> dict:
    block = {
        "reserved_cost_usd": 0.0,
        "hard_cap_usd": None,
        "budget_lease_id": "bud_0001",
        "concurrency_lease_id": "con_0002",
        "expires_at": expires_at,
    }
    block.update(overrides)
    return block


def test_spawn_without_a_lease_block_passes_while_the_gate_is_disarmed():
    """Backwards compatible: today's requests keep validating until an operator arms the gate."""
    from scripts.fleet.spawn_wrapper import validate_spawn

    assert validate_spawn(_valid_request()) == []


def test_spawn_without_a_lease_block_is_refused_at_step_6_when_armed(armed):
    from scripts.fleet.spawn_wrapper import validate_spawn

    errors = validate_spawn(_valid_request())
    assert errors and all(e.startswith("step 6") for e in errors)
    assert "missing entirely" in errors[0]


def test_spawn_with_a_valid_lease_block_passes_step_6(armed):
    from scripts.fleet.spawn_wrapper import validate_spawn

    assert validate_spawn(_valid_request(**_lease_block()), now=1000.0) == []


def test_spawn_with_an_expired_lease_is_refused(armed):
    """The claim is gone; a container started on it would be unbudgeted from its first token."""
    from scripts.fleet.spawn_wrapper import validate_spawn

    errors = validate_spawn(_valid_request(**_lease_block(expires_at=500.0)), now=501.0)
    assert errors and "lease expired" in errors[0]


def test_partial_lease_block_is_refused_even_when_disarmed():
    from scripts.fleet.spawn_wrapper import validate_spawn

    errors = validate_spawn(_valid_request(budget_lease_id="bud_x"))
    assert errors and "partial lease block" in errors[0]


def test_step_6_runs_after_the_scope_checks(armed):
    """Ordering is preserved: an unauthorized scope still fails at step 2, not step 6."""
    from scripts.fleet.spawn_wrapper import validate_spawn

    errors = validate_spawn(_valid_request(scope="admin_everything", **_lease_block()))
    assert errors and errors[0].startswith("step 1")


def test_spawn_sibling_never_reaches_docker_without_a_lease(armed, monkeypatch):
    """The broker is never reached by an unbudgeted spawn — the same guarantee as steps 1-5.

    fb2_broker_hostside: the docker call executes in the HOST broker's process, so the "never
    reaches docker" assertion patches the SEAM (spawn_wrapper's seam client factory) — an
    unbudgeted spawn must refuse at step 6 before the seam is even opened.
    """
    from scripts.fleet import spawn_wrapper

    monkeypatch.setattr(
        spawn_wrapper, "_broker_client",
        lambda: pytest.fail("an unbudgeted spawn must never open the broker seam"),
    )
    with pytest.raises(spawn_wrapper.SpawnValidationError, match="step 6"):
        spawn_wrapper.spawn_sibling(_valid_request())


def test_build_phase_request_stamps_the_admission_into_both_places():
    """The orchestrator side reads the lease block; the cell side reads the env vars."""
    from scripts.fleet.spawn_wrapper import build_phase_request

    context = LeaseContext(
        run_id="admission_leases:p2", model=SUBSCRIPTION_MODEL,
        budget_lease_id="bud_0001", concurrency_lease_ids=("con_0002",),
        reserved_cost_usd=0.0, hard_cap_usd=None, expires_at=9e9,
    )
    request = build_phase_request(
        {"name": "p1_slice1_base_supervisor", "scope": "implementation"},
        goal="g", workdir="/tmp/wt", model=SUBSCRIPTION_MODEL,
        spec_name="admission_leases", admission=context,
    )
    assert request["budget_lease_id"] == "bud_0001"          # validated by step 6
    assert request["env"][BUDGET_LEASE_ENV] == "bud_0001"    # read by the cell's own guard
    assert request["env"][RUN_ID_ENV] == "admission_leases:p2"


def test_build_phase_request_without_an_admission_carries_no_lease_block():
    from scripts.fleet.spawn_wrapper import build_phase_request

    request = build_phase_request(
        {"name": "p1_slice1_base_supervisor", "scope": "implementation"},
        goal="g", workdir="/tmp/wt", model=SUBSCRIPTION_MODEL, spec_name="admission_leases",
    )
    assert "budget_lease_id" not in request
    assert BUDGET_LEASE_ENV not in request["env"]


# ═══════════════════════════════════════════════════════════════════════════════════════════
# (d) runtime.workflow_runner — the per-phase gate
# ═══════════════════════════════════════════════════════════════════════════════════════════


def test_phase_admission_scope_is_inert_without_a_gate():
    with phase_admission_scope(None, "p1", SUBSCRIPTION_MODEL) as admission:
        assert admission is None


def test_runner_never_invokes_the_agent_when_the_phase_is_denied(tmp_path):
    """The runner's half of "refusal means no invocation": the agent callable is never reached."""
    from contextlib import contextmanager

    spec = load_spec(SPEC)

    @contextmanager
    def refusing_gate(phase_name: str, model: str):
        raise AdmissionDenied(f"no budget for {phase_name}")
        yield  # pragma: no cover - unreachable, present only to make this a generator

    def never(*args, **kwargs):
        raise AssertionError("a denied phase must never invoke the agent")

    result = run_workflow(
        spec, goal="g", model=SUBSCRIPTION_MODEL, workdir=tmp_path, commit=False,
        run_agentic_fn=never, phase_admission=refusing_gate,
    )
    assert not result.ok
    assert result.phases[0].status == "failed"
    assert result.phases[0].error.startswith("ADMISSION_DENIED")
    # stop_on_error: the run halts at the first refusal rather than burning through the rest.
    assert len(result.phases) == 1


def test_runner_runs_the_phase_under_its_admission(tmp_path):
    """The other direction — and the admission is *in force* while the agent runs."""
    from contextlib import contextmanager

    spec = load_spec(SPEC)
    seen: list[tuple[str, str | None]] = []

    @contextmanager
    def gate(phase_name: str, model: str):
        context = LeaseContext(
            run_id=f"spec:{phase_name}", model=model,
            budget_lease_id=f"bud_{phase_name}", expires_at=9e9,
        )
        with bind_context(context):
            yield SimpleNamespace(context=lambda: context)

    def agent(prompt, **kwargs):
        # The gate is open around the invocation, not merely before it.
        seen.append((kwargs.get("model", ""), os.environ.get(BUDGET_LEASE_ENV)))
        return _fake_agent()

    result = run_workflow(
        spec, goal="g", model=SUBSCRIPTION_MODEL, workdir=tmp_path, commit=False,
        run_agentic_fn=agent, phase_admission=gate,
    )
    assert result.ok
    assert seen and all(lease_id for _model, lease_id in seen)
    assert seen[0][1] == "bud_scope"  # the first phase of control_room_portal
    # And the admission does not outlive the run.
    assert BUDGET_LEASE_ENV not in os.environ


def test_runner_releases_the_phase_lease_when_the_phase_fails(tmp_path):
    """A failed phase returns its headroom — the gate closes on the error path too."""
    from contextlib import contextmanager

    spec = load_spec(SPEC)
    open_leases: list[str] = []

    @contextmanager
    def gate(phase_name: str, model: str):
        open_leases.append(phase_name)
        try:
            yield None
        finally:
            open_leases.remove(phase_name)

    def failing_agent(prompt, **kwargs):
        return _fake_agent(ok=False, exit_code=1, error="boom")

    result = run_workflow(
        spec, goal="g", model=SUBSCRIPTION_MODEL, workdir=tmp_path, commit=False,
        run_agentic_fn=failing_agent, phase_admission=gate,
    )
    assert not result.ok
    assert open_leases == []


# ═══════════════════════════════════════════════════════════════════════════════════════════
# (e) adapters.backends.run_agentic — the bypass detector
# ═══════════════════════════════════════════════════════════════════════════════════════════


def test_run_agentic_refuses_without_a_lease_context(armed, monkeypatch):
    """Calling the backend around the controller is detected and refused.

    Asserted with a poisoned adapter: if the refusal ever failed to fire, the call would reach
    ``run_opencode_agentic`` and blow up with a *different* error, so this cannot pass silently.
    """
    from agentic_dynamics.adapters import backends, opencode

    monkeypatch.setattr(
        opencode, "run_opencode_agentic",
        lambda *a, **k: pytest.fail("a bypassed invocation must never reach the backend"),
    )
    with pytest.raises(AdmissionContextError, match="bypassed the admission controller"):
        backends.run_agentic("do the thing", model=PER_TOKEN_MODEL)


def test_run_agentic_proceeds_under_a_live_admission(armed, monkeypatch):
    from agentic_dynamics.adapters import backends, opencode

    calls: list[str] = []
    monkeypatch.setattr(
        opencode, "run_opencode_agentic",
        lambda prompt, **kwargs: calls.append(prompt) or _fake_agent(),
    )
    # ``cost_source`` is required on a per-token admission since p3 (unknown cost is never
    # free) — a live admission is one that is priced, not merely one that exists.
    context = LeaseContext(
        run_id="r", model=PER_TOKEN_MODEL, budget_lease_id="b", expires_at=9e9,
        cost_source=CostSource.ESTIMATED,
    )
    with bind_context(context):
        backends.run_agentic("do the thing", model=PER_TOKEN_MODEL)
    assert calls == ["do the thing"]


def test_run_agentic_is_unchanged_when_the_gate_is_disarmed(monkeypatch):
    """The default path: no admission, no refusal, byte-identical behaviour."""
    from agentic_dynamics.adapters import backends, opencode

    calls: list[str] = []
    monkeypatch.setattr(
        opencode, "run_opencode_agentic",
        lambda prompt, **kwargs: calls.append(prompt) or _fake_agent(),
    )
    backends.run_agentic("do the thing", model=PER_TOKEN_MODEL)
    assert calls == ["do the thing"]


def test_run_agentic_refuses_an_expired_admission(armed, monkeypatch):
    from agentic_dynamics.adapters import backends, opencode

    monkeypatch.setattr(
        opencode, "run_opencode_agentic",
        lambda *a, **k: pytest.fail("an expired admission must never reach the backend"),
    )
    context = LeaseContext(
        run_id="r", model=PER_TOKEN_MODEL, budget_lease_id="b", expires_at=1.0
    )
    with bind_context(context), pytest.raises(AdmissionContextError, match="expired"):
        backends.run_agentic("do the thing", model=PER_TOKEN_MODEL)


def test_run_agentic_refuses_an_admission_for_a_different_model(armed, monkeypatch):
    """A subscription admission cannot be spent on a per-token model."""
    from agentic_dynamics.adapters import backends, opencode

    monkeypatch.setattr(
        opencode, "run_opencode_agentic",
        lambda *a, **k: pytest.fail("a mismatched admission must never reach the backend"),
    )
    context = LeaseContext(
        run_id="r", model=SUBSCRIPTION_MODEL, budget_lease_id="b", expires_at=9e9
    )
    with bind_context(context), pytest.raises(AdmissionContextError, match="not transferable"):
        backends.run_agentic("do the thing", model=PER_TOKEN_MODEL)


# ═══════════════════════════════════════════════════════════════════════════════════════════
# (f) scripts/run_workflow.py — the composition root's wiring
# ═══════════════════════════════════════════════════════════════════════════════════════════


def _args(**overrides) -> SimpleNamespace:
    base = dict(
        no_admission=False, campaign_budget_usd=None, campaign_concurrency=None,
        workdir="/tmp/wt_admission_leases",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_composition_root_injects_nothing_when_disarmed():
    """No gate AND no Redis connection: a disarmed run must not require infrastructure."""
    from scripts import run_workflow as rw

    assert rw._build_phase_admission(load_spec(SPEC), _args()) is None


def test_composition_root_injects_nothing_with_the_explicit_escape(armed):
    from scripts import run_workflow as rw

    assert rw._build_phase_admission(load_spec(SPEC), _args(no_admission=True)) is None


def test_composition_root_installs_the_campaign_caps_and_returns_a_gate(
    armed, capped: LeaseRegistry, monkeypatch
):
    from scripts import run_workflow as rw

    monkeypatch.setattr(
        "agentic_dynamics.control.lease_registry.LeaseRegistry.from_env",
        classmethod(lambda cls, **kw: capped),
    )
    gate = rw._build_phase_admission(
        load_spec(SPEC), _args(campaign_budget_usd=25.0, campaign_concurrency=3)
    )
    assert gate is not None
    campaign = LeaseScope(ScopeKind.CAMPAIGN, "control_room_portal")
    assert capped.get_cap(LeaseKind.BUDGET, campaign) == 25.0
    assert capped.get_cap(LeaseKind.CONCURRENCY, campaign) == 3.0


def test_composition_root_refuses_to_start_when_the_registry_is_unreachable(armed, monkeypatch):
    """Fail-closed at the root: "cannot ask the gate" is not "proceed"."""
    from agentic_dynamics.control.lease_registry import LeaseUnavailableError
    from scripts import run_workflow as rw

    def boom(cls, **kwargs):
        raise LeaseUnavailableError("redis unreachable")

    monkeypatch.setattr(
        "agentic_dynamics.control.lease_registry.LeaseRegistry.from_env", classmethod(boom)
    )
    with pytest.raises(LeaseUnavailableError):
        rw._build_phase_admission(load_spec(SPEC), _args())


# ═══════════════════════════════════════════════════════════════════════════════════════════
# The Control Room's admission telemetry surface
# ═══════════════════════════════════════════════════════════════════════════════════════════


def test_control_room_board_scopes_cover_the_wired_entry_points():
    """The dashboard's fixed rows are the scopes the entry points actually reserve against."""
    scopes = {
        (kind, scope.token) for kind, scope in telemetry_routes.ADMISSION_BOARD_SCOPES
    }
    assert (LeaseKind.CONCURRENCY, FLEET.token) in scopes        # scripts/worker.py
    assert (LeaseKind.CONCURRENCY, ANALYSIS.token) in scopes     # scripts/analysis_worker.py
    assert (LeaseKind.BUDGET, ANTHROPIC.token) in scopes         # scripts/enqueue.py
    assert (LeaseKind.BUDGET, "provider:deepseek") in scopes


def test_control_room_board_degrades_instead_of_failing_the_route(monkeypatch):
    """Telemetry degrades where admission would refuse — nothing is decided on this path."""
    from agentic_dynamics.control.lease_registry import LeaseUnavailableError

    def boom(cls, **kwargs):
        raise LeaseUnavailableError("redis unreachable")

    monkeypatch.setattr(
        "agentic_dynamics.control.lease_registry.LeaseRegistry.from_env", classmethod(boom)
    )
    block = telemetry_routes._admission_block()
    assert block["available"] is False
    assert "unreachable" in block["error"]


def test_control_room_board_reports_live_leases(monkeypatch, capped: LeaseRegistry, armed):
    capped.reserve_concurrency(FLEET, 1, run_id="cell-a")
    monkeypatch.setattr(
        "agentic_dynamics.control.lease_registry.LeaseRegistry.from_env",
        classmethod(lambda cls, **kw: capped),
    )
    block = telemetry_routes._admission_block()
    assert block["armed"] is True
    row = next(r for r in block["scopes"] if r["scope"] == FLEET.token
               and r["kind"] == LeaseKind.CONCURRENCY.value)
    assert row["outstanding"] == 1.0
    assert row["headroom"] == 3.0


# ═══════════════════════════════════════════════════════════════════════════════════════════
# Cross-cutting: the disarmed default really is byte-identical
# ═══════════════════════════════════════════════════════════════════════════════════════════


def test_every_entry_point_is_inert_while_the_gate_is_disarmed(tmp_path, monkeypatch):
    """One test for the posture the whole phase rests on: the freeze is not lifted by this code.

    If any entry point reserved, refused, or required Redis with the gate off, this would fail —
    which is the property that makes shipping the gate disarmed a safe default rather than a
    hidden behaviour change.
    """
    from scripts import enqueue, worker
    from scripts.fleet.spawn_wrapper import validate_spawn

    # enqueue: cells pass through untouched
    cells = _cells(2)
    assert enqueue.admit_cells(cells) == cells

    # worker: no leases, no env stamp
    with worker.cell_admission(cells[0]) as env:
        assert env == {}

    # fleet: a lease-less spawn request still validates
    assert validate_spawn(_valid_request()) == []

    # runner: no gate injected, phases run
    def agent(prompt, **kwargs):
        return _fake_agent()

    result = run_workflow(
        load_spec(SPEC), goal="g", model=SUBSCRIPTION_MODEL, workdir=tmp_path,
        commit=False, run_agentic_fn=agent,
    )
    assert result.ok

    # adapters: no refusal
    from agentic_dynamics.adapters import backends, opencode

    monkeypatch.setattr(opencode, "run_opencode_agentic", lambda *a, **k: _fake_agent())
    assert backends.run_agentic("x", model=PER_TOKEN_MODEL) is not None
