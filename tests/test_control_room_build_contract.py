"""The control_room_instrument_build executable contract (AIO remediation 2026-09-14).

The handoff's step-2 "done when": a deterministic test drives the ACTUAL authored workflow
(``workflows/repository/control_room_instrument_build.yaml``) through the REAL runner with
controlled executors, and observes —

* the intended context transport: the spec's ``context.domain_context`` block reaches the
  phase prompt the parent prepares (the bytes that cross the executor boundary);
* the intended retrieval scope: ``workflow.params.rag`` (the key the runner actually
  reads) resolves to the CELL scope — never the org-wide scope that would expose the
  AIO's private decision/session records to workers;
* the refusal of unsupported checkpoint combinations at validation (``checkpoint: true``
  on ``kind: test``) and the authored spec's own compliance (p1c is an agent phase with
  ``checkpoint: true`` + ``test_gate: true``);
* the missing-verification refusal: every implementation phase either declares
  ``test_gate: true`` with a test target or is a ``kind: test`` gate itself;
* the checkpoint stop: the run STOPS awaiting at p1c and p2a_timings_route CANNOT
  dispatch until a correctly bound approval exists, and a resume refuses without one;
* the bounded correction attempt (``gate_retry``): a failed verification returns to the
  producer for one bounded correction, then the independent check re-runs — and an
  infrastructure refusal (VERIFIER_*) never triggers a correction.

Deterministic: fake executors, a real temp git worktree, no Redis, no model calls, no
browser. NOT ``fast``-marked (real git worktrees).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from agentic_dynamics.experiment.experiment_spec import load_spec, validate_spec
from agentic_dynamics.runtime.executor import StepRequest, StepResult
from agentic_dynamics.runtime.workflow_runner import (
    _build_phase_prompt,
    _resolve_rag_params,
    run_workflow,
)

REPO = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO / "workflows" / "repository" / "control_room_instrument_build.yaml"
GOAL = "Build the Scroll-Synthesized Instrument Control Room"
MODEL = "deepseek/deepseek-v4-flash"

#: The phases every implementation slice must gate (every agent phase except the final
#: acceptance-assembly checkpoint phase, whose verification is the controller's ratification).
AGENT_PHASES_WITHOUT_TEST_GATE = {"p6g_acceptance"}


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def _git_init(workdir: Path) -> None:
    _git("init", "-q", cwd=workdir)
    _git("config", "user.email", "t@t", cwd=workdir)
    _git("config", "user.name", "t", cwd=workdir)


def _deterministic_retrieve_fn(seen: dict[str, str] | None = None):
    """A retrieve_fn that records the scope the augmentation seam received and refuses —
    deterministic, no stores, no paid constructor call (the runner's own fallback contract)."""
    def retrieve_fn(**kwargs):
        if seen is not None:
            seen["repository_id"] = str(kwargs.get("repository_id", ""))
            seen["acl_scope"] = str(kwargs.get("acl_scope", ""))
        raise RuntimeError("deterministic: retrieval is off in this test")
    return retrieve_fn


class _FakeAgentExecutor:
    """A controlled agent executor: writes one file per phase (so the runner commits real
    work) and records every prompt it received — the bytes that cross the boundary."""

    def __init__(self, fail: str | None = None):
        self.calls: list[str] = []  # phase names, in order
        self.prompts: dict[str, str] = {}
        self.fail = fail

    def execute(self, request: StepRequest) -> StepResult:
        self.calls.append(request.phase_name)
        self.prompts[request.phase_name] = request.prompt
        if self.fail and request.phase_name in self.fail.split(","):
            return StepResult(ok=False, state="failed", error="agent failed", exit_code=1)
        target = Path(request.workdir) / "work" / f"{request.phase_name}.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(request.prompt[:120])
        return StepResult(
            ok=True, state="ok", exit_code=0,
            prompt_tokens=10, completion_tokens=20, total_tokens=30,
            estimated_cost_usd=0.001,
        )


class _FakeVerifierExecutor:
    """A controlled verifier: passing by default; scriptable per-phase verdicts."""

    def __init__(self, fail: str | None = None, infra_error: bool = False):
        self.calls: list[str] = []
        self.fail = set((fail or "").split(",")) if fail else set()
        self.infra_error = infra_error

    def execute(self, request: StepRequest) -> StepResult:
        self.calls.append(request.phase_name)
        if request.phase_name in self.fail:
            if self.infra_error:
                return StepResult(
                    ok=False, state="failed", error="VERIFIER_ERROR: spawn refused",
                )
            return StepResult(
                ok=False, state="failed", error="suite failed (1/3 passed)",
                tests_passed=1, tests_total=3, test_executed_success=False,
            )
        return StepResult(
            ok=True, state="ok", exit_code=0,
            tests_passed=3, tests_total=3, test_executed_success=True,
        )


@pytest.fixture
def build_spec():
    return load_spec(SPEC_PATH)


# ── The authored spec's declared contract ─────────────────────────────────────


def test_authored_spec_validates_and_declares_the_supported_contract(build_spec):
    spec = build_spec
    assert validate_spec(spec) == []
    phases = spec.workflow.params["phases"]
    by_name = {p["name"]: p for p in phases}

    # p1c: the supported checkpoint shape — an AGENT phase with checkpoint + an independent
    # native test gate (the old kind: test + checkpoint: true combination is gone).
    p1c = by_name["p1c_contract_gate"]
    assert p1c["kind"] == "agent"
    assert p1c.get("checkpoint") is True
    assert p1c.get("test_gate") is True
    assert p1c.get("tests") == [
        "tests/test_doc_lifecycle.py",
        "tests/test_render_gate_captures.py",
        "tests/test_control_room_parity.py",
    ]

    # no phase may declare the unsupported combination
    for p in phases:
        assert not (p.get("checkpoint") and p.get("kind") == "test"), p["name"]

    # every implementation slice gates: each agent phase (except the final acceptance
    # assembly, whose check is the controller's ratification) declares an independent
    # test_gate with a test target, or is itself a kind:test gate.
    for p in phases:
        if p.get("kind") == "agent" and p["name"] not in AGENT_PHASES_WITHOUT_TEST_GATE:
            assert p.get("test_gate") is True, f"{p['name']} lacks test_gate"
            assert p.get("tests"), f"{p['name']} declares test_gate but no tests"

    # the final gate is an independent kind:test phase and the acceptance assembly is the
    # checkpoint AFTER it — producing the report never establishes acceptance.
    names = [p["name"] for p in phases]
    assert names.index("p6f_final_gate") < names.index("p6g_acceptance")
    p6f = by_name["p6f_final_gate"]
    assert p6f["kind"] == "test"
    p6g = by_name["p6g_acceptance"]
    assert p6g.get("checkpoint") is True

    # retrieval config: the runner's key (rag) is used, and the scope is deliberate —
    # no repository_id means cell scope (private by construction), never the org-wide
    # shared scope that would expose AIO decision/session records to workers.
    params = spec.workflow.params
    assert params.get("rag") == {}, "the runner reads workflow.params.rag (empty = cell scope)"
    assert "rag_params" not in params, "the ignored key must not reappear"
    assert params.get("rag_augment") is True
    assert (params.get("context") or {}).get("domain_context")


def test_checkpoint_on_test_kind_is_rejected_during_validation(build_spec, tmp_path):
    import copy

    spec = build_spec
    phases = copy.deepcopy(spec.workflow.params["phases"])
    for p in phases:
        if p["name"] == "p0b_parity_gate":
            p["checkpoint"] = True
    spec.workflow.params["phases"] = phases
    errors = validate_spec(spec)
    assert any("checkpoint: true on kind: test" in e for e in errors)

    # and gate_retry type-safety
    spec2 = build_spec
    phases2 = copy.deepcopy(spec2.workflow.params["phases"])
    phases2[0]["gate_retry"] = "yes"
    spec2.workflow.params["phases"] = phases2
    errors2 = validate_spec(spec2)
    assert any("gate_retry must be a non-negative integer" in e for e in errors2)


# ── Context transport + retrieval scope ───────────────────────────────────────


def test_domain_context_is_transported_into_the_prepared_prompt(build_spec):
    """The spec's domain_context reaches the assembled phase prompt — the constraints and
    canonical-source identities the phases promise to obey are actually supplied."""
    spec = build_spec
    ctx = (spec.workflow.params.get("context") or {}).get("domain_context", "")
    phase = next(p for p in spec.workflow.params["phases"] if p["name"] == "p0a_reanchor_parity")
    prompt = _build_phase_prompt(phase, GOAL, ["none"], domain_context=ctx)
    assert "canonical_sources" in prompt
    assert "design_determination.md" in prompt
    assert "NO build step" in prompt
    assert GOAL in prompt
    # a phase that references the placeholder gets the block substituted, not appended
    phase2 = dict(phase, prompt="{goal}\n{domain_context}")
    prompt2 = _build_phase_prompt(phase2, GOAL, [], domain_context=ctx)
    assert prompt2.count("SPEC CONTEXT") == 0
    assert "canonical_sources" in prompt2


def test_domain_context_crosses_the_executor_boundary(build_spec, tmp_path, monkeypatch):
    """The final prompt the executor receives (the bytes that cross the container boundary
    in production) carries the domain context — not merely the template. The deterministic
    retrieve_fn records the retrieval scope the augmentation seam actually receives (the
    cell scope — never the org-wide scope) and refuses, exercising the runner's own
    fallback contract (a retrieval failure reverts to the assembled base prompt, never
    blocks the phase, never makes a paid constructor call)."""
    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
    spec = build_spec
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)
    agent = _FakeAgentExecutor()
    seen: dict[str, str] = {}

    result = run_workflow(
        spec, goal=GOAL, model=MODEL, workdir=wd,
        step_executor=agent, verifier_executor=_FakeVerifierExecutor(),
        retrieve_fn=_deterministic_retrieve_fn(seen), publish=False, commit=True,
    )
    assert result.awaiting is True  # stops at p1c
    # the retrieval scope crossing the augmentation seam IS the cell scope
    assert seen["repository_id"] == "self-wd"
    assert seen["acl_scope"] == "self-wd"
    # the assembled prompt (what the executor received) carries the domain context
    assert "canonical_sources" in agent.prompts["p0a_reanchor_parity"]
    assert "design_determination.md" in agent.prompts["p0a_reanchor_parity"]
    assert "NO build step" in agent.prompts["p1b_gate_first_viewport"]


def test_retrieval_scope_is_cell_scoped_by_default_and_explicit_override_is_preserved(build_spec):
    spec = build_spec
    wd = Path("/tmp/wt_build_cell")
    # the authored spec: rag={} → the deliberate cell scope, never the org-wide scope
    resolved = _resolve_rag_params(spec, None, wd=wd, rag_augment=True)
    assert resolved["repository_id"] == "self-wt_build_cell"
    assert resolved["acl_scope"] == "self-wt_build_cell"
    assert resolved["repository_id"] != "agentic-dynamics", (
        "the org-wide scope would expose the AIO's private decision/session records"
    )
    # the explicit shared-scope override still works for coordinated parallel workstreams
    explicit = _resolve_rag_params(
        spec, {"repository_id": "wave-a-shared"}, wd=wd, rag_augment=True
    )
    assert explicit["repository_id"] == "wave-a-shared"
    # the runner's read key is `rag` — a spec authoring `rag_params` gets nothing
    import copy

    spec2 = copy.deepcopy(spec)
    spec2.workflow.params["rag_params"] = {"repository_id": "agentic-dynamics"}
    resolved2 = _resolve_rag_params(spec2, None, wd=wd, rag_augment=True)
    assert resolved2["repository_id"] == "self-wt_build_cell", (
        "workflow.params.rag_params is NOT read by the runner — only workflow.params.rag"
    )


# ── The checkpoint stop on the REAL workflow ──────────────────────────────────


def _approval_text(*, operator: str = "jane@example.com", date: str = "2026-09-14",
                   binding: dict | None = None) -> str:
    lines = ["# Operator approval\n\n", f"- operator: {operator}\n", f"- date: {date}\n"]
    for key, value in (binding or {}).items():
        lines.append(f"- {key}: {value}\n")
    return "".join(lines)


def _commit_approval(wd: Path, spec_name: str, phase: str) -> None:
    """Commit the approval the OFFICIAL way (approve_workflow.py's shape): an ``[approval]``
    subject — which the runner's phase-prefix commit-msg hook exempts — descending from the
    checkpoint commit. A raw `git commit -m "operator approval"` would be REWRITTEN by the
    hook into a second ``[workflow] <phase>`` commit and the resume would misread it as the
    checkpoint commit itself (the defect this test reproduces)."""
    ck = _git("rev-parse", "HEAD", cwd=wd).stdout.strip()
    tree = _git("rev-parse", "HEAD^{tree}", cwd=wd).stdout.strip()
    ap = wd / "approvals" / spec_name
    ap.mkdir(parents=True, exist_ok=True)
    (ap / f"{phase}_approval.md").write_text(
        _approval_text(binding={"spec": spec_name, "phase": phase,
                                "candidate": ck, "tree": tree})
    )
    _git("add", "-Af", cwd=wd)
    _git("commit", "-qm", f"[approval] {spec_name}/{phase} — approved by jane@example.com",
         cwd=wd)


def test_real_workflow_stops_at_p1c_and_p2a_cannot_dispatch_without_approval(
    build_spec, tmp_path, monkeypatch
):
    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
    spec = build_spec
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)
    agent = _FakeAgentExecutor()
    verifier = _FakeVerifierExecutor()

    result = run_workflow(
        spec, goal=GOAL, model=MODEL, workdir=wd,
        step_executor=agent, verifier_executor=verifier,
        retrieve_fn=_deterministic_retrieve_fn(), publish=False, commit=True,
    )
    # the mechanical stop: awaiting at p1c, and p2a_timings_route NEVER dispatched
    assert result.awaiting is True
    assert result.awaiting_phase == "p1c_contract_gate"
    assert result.awaiting_reason == "checkpoint"
    assert [p.phase for p in result.phases] == [
        "p0a_reanchor_parity", "p0b_parity_gate", "p1a_ia_amendment",
        "p1b_gate_first_viewport", "p1c_contract_gate",
    ]
    assert result.phases[-1].status == "awaiting"
    assert "p2a_timings_route" not in agent.calls
    # the independent gate ran on the checkpoint phase (test_gate → verifier dispatch)
    assert "p1c_contract_gate__test_gate" in verifier.calls

    # resume WITHOUT the approval: refused, nothing runs
    agent2 = _FakeAgentExecutor()
    verifier2 = _FakeVerifierExecutor()
    result2 = run_workflow(
        spec, goal=GOAL, model=MODEL, workdir=wd,
        step_executor=agent2, verifier_executor=verifier2,
        retrieve_fn=_deterministic_retrieve_fn(), publish=False, commit=True, resume=True,
    )
    assert result2.awaiting is True
    assert result2.awaiting_reason == "approval_refused"
    assert agent2.calls == []

    # the operator signs + commits the approval (descendant of the checkpoint commit):
    # the resume proceeds past p1c and p2a dispatches. The run then continues the build and
    # stops at the FINAL checkpoint (p6g_acceptance) — the controller's acceptance stop.
    _commit_approval(wd, spec.name, "p1c_contract_gate")
    agent3 = _FakeAgentExecutor()
    verifier3 = _FakeVerifierExecutor()
    result3 = run_workflow(
        spec, goal=GOAL, model=MODEL, workdir=wd,
        step_executor=agent3, verifier_executor=verifier3,
        retrieve_fn=_deterministic_retrieve_fn(), publish=False, commit=True, resume=True,
    )
    assert "p2a_timings_route" in agent3.calls
    assert result3.awaiting is True
    assert result3.awaiting_phase == "p6g_acceptance"
    assert result3.awaiting_reason == "checkpoint"
    assert result3.phases[-1].phase == "p6g_acceptance"
    assert result3.phases[-1].status == "awaiting"


# ── The bounded correction attempt ────────────────────────────────────────────

GATE_RETRY_SPEC_YAML = """\
name: gate_retry_fixture
question: gate retry fixture
version: "0.1"
artifact_kind: workflow
intent: mutate
side_effects:
  repository: true
  external_services: false
workflow:
  kind: agent_task
  params:
    language: python
    phases:
      - name: build
        kind: agent
        timeout: 120
        test_gate: true
        gate_retry: 1
        tests:
          - tests/test_thing.py
        prompt: |
          {goal}
      - name: next
        kind: agent
        timeout: 120
        test_gate: true
        tests:
          - tests/test_thing.py
        prompt: |
          {goal}
factors:
  - {name: model, levels: [deepseek/deepseek-v4-flash]}
design: factorial
rules: []
metrics: []
comparison: null
"""


def _gate_retry_spec(tmp_path: Path):
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(GATE_RETRY_SPEC_YAML)
    return load_spec(spec_path)


class _OnceFailingVerifier:
    """Fails the first verification of the named phase, passes everything after."""

    def __init__(self, fail_phase: str):
        self.fail_phase = fail_phase
        self.seen: dict[str, int] = {}
        self.calls: list[str] = []

    def execute(self, request: StepRequest) -> StepResult:
        self.calls.append(request.phase_name)
        n = self.seen.get(request.phase_name, 0) + 1
        self.seen[request.phase_name] = n
        if request.phase_name == self.fail_phase and n == 1:
            return StepResult(
                ok=False, state="failed", error="suite failed (1/3 passed)",
                tests_passed=1, tests_total=3, test_executed_success=False,
            )
        return StepResult(
            ok=True, state="ok", exit_code=0,
            tests_passed=3, tests_total=3, test_executed_success=True,
        )


def test_gate_retry_returns_to_the_producer_then_reruns_the_check(tmp_path, monkeypatch):
    """A failed verification returns to the producing phase for ONE bounded correction
    (its prompt carries the failed check's evidence), then the independent check re-runs."""
    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
    spec = _gate_retry_spec(tmp_path)
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)
    agent = _FakeAgentExecutor()
    verifier = _OnceFailingVerifier("build__test_gate")

    result = run_workflow(
        spec, goal="g", model=MODEL, workdir=wd,
        step_executor=agent, verifier_executor=verifier,
        publish=False, commit=True,
    )
    assert result.ok is True
    # build ran twice (initial + correction); its own gate ran twice (fail then pass); next ran once
    assert agent.calls == ["build", "build", "next"]
    assert verifier.calls == ["build__test_gate", "build__test_gate", "next__test_gate"]
    # the correction attempt's prompt carries the failed check's evidence
    assert "CORRECTION ATTEMPT" in agent.prompts["build"]
    assert "suite failed" in agent.prompts["build"]
    # the ledger carries ONE record per phase (the failed record was replaced, not duplicated)
    assert [p.phase for p in result.phases] == ["build", "next"]
    assert result.phases[0].status == "ok"


def test_gate_retry_is_bounded_and_exhaustion_fails_the_run(tmp_path, monkeypatch):
    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
    spec = _gate_retry_spec(tmp_path)
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)
    agent = _FakeAgentExecutor()
    verifier = _FakeVerifierExecutor(fail="build__test_gate")

    result = run_workflow(
        spec, goal="g", model=MODEL, workdir=wd,
        step_executor=agent, verifier_executor=verifier,
        publish=False, commit=True,
    )
    # the correction budget is 1: build ran twice, its gate failed both times, next never ran
    assert result.ok is False
    assert agent.calls == ["build", "build"]
    assert verifier.calls == ["build__test_gate", "build__test_gate"]
    assert "next" not in agent.calls


def test_verifier_infra_failure_never_triggers_a_correction(tmp_path, monkeypatch):
    """A VERIFIER_ERROR (spawn refused etc.) is infrastructure state, not a code defect —
    the run stops without burning a correction re-run against an unchanged environment."""
    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
    spec = _gate_retry_spec(tmp_path)
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)
    agent = _FakeAgentExecutor()
    verifier = _FakeVerifierExecutor(fail="build__test_gate", infra_error=True)

    result = run_workflow(
        spec, goal="g", model=MODEL, workdir=wd,
        step_executor=agent, verifier_executor=verifier,
        publish=False, commit=True,
    )
    assert result.ok is False
    assert agent.calls == ["build"]  # exactly one attempt — no correction
    assert result.phases[0].status == "failed"
    assert result.phases[0].error.startswith("VERIFIER_ERROR:")


# ── Reviewer reproductions (2026-09-14): the correction history + resume inference ──────────

GATE_RETRY_TEST_PHASE_YAML = """\
name: gate_retry_test_phase_fixture
question: gate retry via a separate test phase
version: "0.1"
artifact_kind: workflow
intent: mutate
side_effects:
  repository: true
  external_services: false
workflow:
  kind: agent_task
  params:
    language: python
    phases:
      - name: build
        kind: agent
        timeout: 120
        test_gate: true
        tests:
          - tests/test_thing.py
        prompt: |
          {goal}
      - name: verify
        kind: test
        timeout: 120
        gate_retry: 1
        tests:
          - tests/test_thing.py
        prompt: |
          {goal}
factors:
  - {name: model, levels: [deepseek/deepseek-v4-flash]}
design: factorial
rules: []
metrics: []
comparison: null
"""

THREE_PHASE_YAML = """\
name: three_phase_fixture
question: resume inference fixture
version: "0.1"
artifact_kind: workflow
intent: mutate
side_effects:
  repository: true
  external_services: false
workflow:
  kind: agent_task
  params:
    language: python
    phases:
      - name: alpha
        kind: agent
        timeout: 120
        test_gate: true
        tests:
          - tests/test_thing.py
        prompt: |
          {goal}
      - name: beta
        kind: agent
        timeout: 120
        test_gate: true
        tests:
          - tests/test_thing.py
        prompt: |
          {goal}
      - name: gamma
        kind: agent
        timeout: 120
        test_gate: true
        tests:
          - tests/test_thing.py
        prompt: |
          {goal}
factors:
  - {name: model, levels: [deepseek/deepseek-v4-flash]}
design: factorial
rules: []
metrics: []
comparison: null
"""


class _CostingAgentExecutor:
    """A fake executor that returns a fixed per-call cost and records each request's ordinal."""

    def __init__(self, cost: float = 0.001):
        self.calls: list[str] = []
        self.attempts: list[int] = []
        self.cost = cost

    def execute(self, request: StepRequest) -> StepResult:
        self.calls.append(request.phase_name)
        self.attempts.append(request.attempt)
        target = Path(request.workdir) / "work" / f"{request.phase_name}_{request.attempt}.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x")
        return StepResult(
            ok=True, state="ok", exit_code=0,
            prompt_tokens=10, completion_tokens=20, total_tokens=30,
            estimated_cost_usd=self.cost,
        )


def test_correction_retains_costs_and_increments_attempt_identity(tmp_path, monkeypatch):
    """The reviewer reproduction: three calls cost $0.003 but the ledger showed $0.002 and the
    repaired phase read as a first-pass success; the container also received attempt 1 again.
    Now: the failed invocation's cost/tokens/verdict survive as attempt rows, attempt identity
    increments, and ONE final phase outcome carries the history."""
    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(GATE_RETRY_SPEC_YAML)
    spec = load_spec(spec_path)
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)
    agent = _CostingAgentExecutor(cost=0.001)
    verifier = _OnceFailingVerifier("build__test_gate")

    result = run_workflow(
        spec, goal="g", model=MODEL, workdir=wd,
        step_executor=agent, verifier_executor=verifier,
        publish=False, commit=True,
    )
    assert result.ok is True
    # the executor's attempt ordinal continued past the retained execution (never reused)
    assert agent.calls == ["build", "build", "next"]
    assert agent.attempts[:2] == [1, 2], "the correction re-run reused attempt identity 1"
    # ONE final phase outcome per phase (no duplicates), with the paid calls retained
    assert [p.phase for p in result.phases] == ["build", "next"]
    build = result.phases[0]
    assert build.status == "ok"
    assert len(build.attempts) == 2, "the failed invocation's history was discarded"
    # phase-level cost includes BOTH paid calls (the old shape recorded only the last)
    assert round(build.cost_usd, 6) == 0.002
    # the ledger's attempt records: a1 = the failed invocation (cost + verdict retained),
    # a2 = the final attempt; the repaired phase is NOT a first-pass success.
    records = [r for r in result.attempts if r.phase == "build"]
    assert [r.attempt_number for r in records] == [1, 2]
    assert len({r.attempt_id for r in records}) == 2
    assert records[0].status == "failed" and records[0].cost_usd == 0.001
    assert records[0].first_pass is False and records[0].retry_reason.startswith("correction")
    assert records[1].accepted is True and records[1].first_pass is None
    assert records[1].cost_usd == 0.001


def test_test_phase_correction_does_not_duplicate_producer_records(tmp_path, monkeypatch):
    """The duplicate-attempt-id reproduction: a separate test phase failing must re-run its
    producer ONCE — the producer's stale record is retired into history, not duplicated."""
    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(GATE_RETRY_TEST_PHASE_YAML)
    spec = load_spec(spec_path)
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)
    agent = _CostingAgentExecutor(cost=0.001)
    verifier = _OnceFailingVerifier("verify")

    result = run_workflow(
        spec, goal="g", model=MODEL, workdir=wd,
        step_executor=agent, verifier_executor=verifier,
        publish=False, commit=True,
    )
    assert result.ok is True
    assert agent.calls == ["build", "build"]  # producer re-ran exactly once
    assert [p.phase for p in result.phases] == ["build", "verify"], "duplicate producer record"
    build = result.phases[0]
    assert len(build.attempts) == 2  # both paid invocations retained
    assert round(build.cost_usd, 6) == 0.002
    records = [r for r in result.attempts if r.phase == "build"]
    assert len({r.attempt_id for r in records}) == 2, "duplicate attempt ids"
    assert agent.attempts[:2] == [1, 2]


def _commit_phase_marker(wd: Path, phase: str, goal: str) -> str:
    """Commit a marker whose subject matches the runner's phase-commit contract exactly."""
    path = wd / "work" / f"{phase}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(phase)
    _git("add", "-A", cwd=wd)
    _git("commit", "-qm", f"[workflow] {phase} — {goal[:40]}", cwd=wd)
    return _git("rev-parse", "HEAD", cwd=wd).stdout.strip()


def test_resume_never_infers_unexecuted_phases_from_a_later_commit(tmp_path, monkeypatch):
    """The reviewer reproduction: a worktree whose ONLY commit belongs to the third phase
    resumed with phases 1-2 declared complete and succeeded without running them. A later
    commit cannot establish that earlier work ran: without its own evidence each phase
    executes (or re-verifies) on resume."""
    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(THREE_PHASE_YAML)
    spec = load_spec(spec_path)
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)
    goal = "g"
    _commit_phase_marker(wd, "gamma", goal)  # ONLY the third phase's commit exists

    agent = _FakeAgentExecutor()
    verifier = _FakeVerifierExecutor()
    result = run_workflow(
        spec, goal=goal, model=MODEL, workdir=wd,
        step_executor=agent, verifier_executor=verifier,
        publish=False, commit=True, resume=True,
    )
    assert result.ok is True
    # the unexecuted phases RAN (their own evidence was required); gamma had its own commit
    assert agent.calls == ["alpha", "beta"]
    assert result.already_complete is False, (
        "resume declared unexecuted work complete from a later commit"
    )


def test_resume_all_phases_with_their_own_commits_skips_everything(tmp_path, monkeypatch):
    """The legitimate logical-completion case stays: every phase has its OWN commit → the
    resume executes nothing and records already_complete (never a manufactured failure)."""
    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(THREE_PHASE_YAML)
    spec = load_spec(spec_path)
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)
    goal = "g"
    for phase in ("alpha", "beta", "gamma"):
        _commit_phase_marker(wd, phase, goal)

    agent = _FakeAgentExecutor()
    result = run_workflow(
        spec, goal=goal, model=MODEL, workdir=wd,
        step_executor=agent, verifier_executor=_FakeVerifierExecutor(),
        publish=False, commit=True, resume=True,
    )
    assert agent.calls == []
    assert result.already_complete is True
    assert result.phases == []
