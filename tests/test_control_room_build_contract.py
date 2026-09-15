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

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

from agentic_dynamics.experiment.experiment_spec import load_spec, validate_spec
from agentic_dynamics.runtime import workflow_runner as runner_module
from agentic_dynamics.runtime.executor import StepRequest, StepResult
from agentic_dynamics.runtime.workflow_runner import (
    ResumeState,
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


def _commit_approval(wd: Path, spec_name: str, phase: str, *, run_id: str | None = None,
                     gate_id: str | None = None, text: str | None = None) -> None:
    """Commit the approval the OFFICIAL way (approve_workflow.py's shape): an ``[approval]``
    subject — which the runner's phase-prefix commit-msg hook exempts — descending from the
    checkpoint commit. A raw `git commit -m "operator approval"` would be REWRITTEN by the
    hook into a second ``[workflow] <phase>`` commit and the resume would misread it as the
    checkpoint commit itself (the defect this test reproduces).

    ``run_id``/``gate_id`` add the durable binding fields the fleet resume supplies; ``text``
    overrides the whole artifact (the wrong-binding reproductions)."""
    ck = _git("rev-parse", "HEAD", cwd=wd).stdout.strip()
    tree = _git("rev-parse", "HEAD^{tree}", cwd=wd).stdout.strip()
    binding = {"spec": spec_name, "phase": phase, "candidate": ck, "tree": tree}
    if run_id is not None:
        binding["run"] = run_id
    if gate_id is not None:
        binding["gate"] = gate_id
    ap = wd / "approvals" / spec_name
    ap.mkdir(parents=True, exist_ok=True)
    (ap / f"{phase}_approval.md").write_text(
        text if text is not None else _approval_text(binding=binding)
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


# ── The explicit (selected-parent) checkpoint continuation ────────────────────
# The fleet defect (reviewer reproduction 2026-09-14): the explicit resume path takes its
# completion set from the selected parent's ledger — which recorded ``ok`` phases only — so
# a REACHED-but-awaiting checkpoint was never validated through the completed-checkpoint
# path, re-ran, and stopped there again. These tests drive the REAL ``_load_resume_state``
# (the loader the fleet's ``--resume --parent-run-id`` path uses) and the authored workflow
# through the runner.


def _load_run_workflow_module(name: str = "run_workflow_under_test_continuation"):
    """Load ``scripts/run_workflow.py`` (not a package) so the tests call the REAL selected-
    parent loader the fleet resume path performs — a hand-built ``ResumeState`` would miss
    the loader defect entirely."""
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / "run_workflow.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_run_ledger(root: Path, spec_name: str, run_id: str, result) -> Path:
    """Write a finished run's ledger under the identity-carrying name the loader selects."""
    ledger_dir = root / "experiments" / "results" / "workflows" / spec_name
    ledger_dir.mkdir(parents=True, exist_ok=True)
    payload = result.to_dict()
    payload["run_id"] = run_id
    path = ledger_dir / f"20260914T000000000000Z_{run_id}.json"
    path.write_text(json.dumps(payload))
    return path


def _run_to_p1c(spec, wd):
    """Drive the authored workflow to its designed p1c stop with controlled executors."""
    result = run_workflow(
        spec, goal=GOAL, model=MODEL, workdir=wd,
        step_executor=_FakeAgentExecutor(), verifier_executor=_FakeVerifierExecutor(),
        retrieve_fn=_deterministic_retrieve_fn(), publish=False, commit=True,
    )
    assert result.awaiting is True
    assert result.awaiting_phase == "p1c_contract_gate"
    return result


def test_explicit_resume_validates_the_reached_checkpoint_and_refuses_without_approval(
    build_spec, tmp_path, monkeypatch
):
    """Case 1 — parent reaches p1c; no approval: the resume remains awaiting WITHOUT
    re-running the checkpoint or dispatching any producer/verifier beyond the stop."""
    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
    spec = build_spec
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)
    parent = _run_to_p1c(spec, wd)
    _write_run_ledger(tmp_path, spec.name, "run-parent-1", parent)

    module = _load_run_workflow_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    state = module._load_resume_state(spec.name, "run-parent-1")
    assert state.completed_phases == frozenset({
        "p0a_reanchor_parity", "p0b_parity_gate", "p1a_ia_amendment",
        "p1b_gate_first_viewport",
    })
    assert state.reached_checkpoints == frozenset({"p1c_contract_gate"})

    agent2 = _FakeAgentExecutor()
    verifier2 = _FakeVerifierExecutor()
    second = run_workflow(
        spec, goal=GOAL, model=MODEL, workdir=wd,
        step_executor=agent2, verifier_executor=verifier2,
        retrieve_fn=_deterministic_retrieve_fn(), publish=False, commit=True,
        resume=True, resume_state=state,
        approval_run_id="run-parent-1", approval_gate_id="gate-p1c",
    )
    assert second.awaiting is True
    assert second.awaiting_phase == "p1c_contract_gate"
    assert second.awaiting_reason == "approval_refused"
    assert agent2.calls == [], "the reached checkpoint was re-run instead of validated"
    assert verifier2.calls == [], "a verifier dispatched past the stopped checkpoint"
    # the typed decision trace records the rejected contract read (the I10 capture)
    rejected = [c for c in second.checkpoints if c.phase == "p1c_contract_gate"]
    assert rejected and rejected[-1].decision == "rejected"
    assert "no_artifact" in (rejected[-1].approval_evidence or {}).get("failed_checks", [])


def test_explicit_resume_skips_the_approved_checkpoint_and_dispatches_p2a(
    build_spec, tmp_path, monkeypatch
):
    """Case 2 — same parent, correctly bound committed approval: p1c is skipped (validated,
    never re-run) and the next dispatch is p2a_timings_route; the skipped work is recorded
    as inherited completion with provenance."""
    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
    spec = build_spec
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)
    parent = _run_to_p1c(spec, wd)
    _write_run_ledger(tmp_path, spec.name, "run-parent-2", parent)

    module = _load_run_workflow_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    state = module._load_resume_state(spec.name, "run-parent-2")
    _commit_approval(wd, spec.name, "p1c_contract_gate",
                     run_id="run-parent-2", gate_id="gate-p1c")

    agent2 = _FakeAgentExecutor()
    verifier2 = _FakeVerifierExecutor()
    second = run_workflow(
        spec, goal=GOAL, model=MODEL, workdir=wd,
        step_executor=agent2, verifier_executor=verifier2,
        retrieve_fn=_deterministic_retrieve_fn(), publish=False, commit=True,
        resume=True, resume_state=state,
        approval_run_id="run-parent-2", approval_gate_id="gate-p1c",
    )
    assert "p1c_contract_gate" not in agent2.calls, "the approved checkpoint re-ran"
    assert agent2.calls[0] == "p2a_timings_route"
    # the run continues to its final designed stop (the controller's acceptance checkpoint)
    assert second.awaiting is True
    assert second.awaiting_phase == "p6g_acceptance"
    approved = [c for c in second.checkpoints if c.phase == "p1c_contract_gate"]
    assert approved and approved[-1].decision == "approved"
    # inherited completion is recorded with provenance, not re-attributed silently
    inherited = {e["phase"]: e for e in second.inherited_phases}
    assert set(inherited) == {
        "p0a_reanchor_parity", "p0b_parity_gate", "p1a_ia_amendment",
        "p1b_gate_first_viewport", "p1c_contract_gate",
    }
    assert inherited["p1c_contract_gate"]["from_run_id"] == "run-parent-2"
    assert inherited["p1c_contract_gate"]["status"] == "checkpoint_approved"


def test_explicit_resume_refuses_wrongly_bound_approvals_before_execution(
    build_spec, tmp_path, monkeypatch
):
    """Case 3 — wrong run, gate, candidate, or invalid approval: refused BEFORE execution
    with the named failed check — never a partial dispatch."""
    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
    spec = build_spec
    module = _load_run_workflow_module()
    variants = (
        ("run_id", {"run": "run-foreign"}),
        ("gate_id", {"gate": "gate-foreign"}),
        ("candidate_sha", {"candidate": "deadbeef9"}),
        ("operator", None),
    )
    for index, (expected_failed, override) in enumerate(variants):
        wd = tmp_path / f"wd{index}"
        wd.mkdir()
        _git_init(wd)
        parent = _run_to_p1c(spec, wd)
        run_id = f"run-parent-3{index}"
        _write_run_ledger(tmp_path, spec.name, run_id, parent)
        monkeypatch.setattr(module, "ROOT", tmp_path)
        state = module._load_resume_state(spec.name, run_id)
        ck = _git("rev-parse", "HEAD", cwd=wd).stdout.strip()
        tree = _git("rev-parse", "HEAD^{tree}", cwd=wd).stdout.strip()
        binding = {"spec": spec.name, "phase": "p1c_contract_gate", "candidate": ck,
                   "tree": tree, "run": run_id, "gate": "gate-p1c"}
        if override is None:
            text = _approval_text(operator="tbd", binding=binding)
        else:
            binding.update(override)
            text = _approval_text(binding=binding)
        _commit_approval(wd, spec.name, "p1c_contract_gate", text=text)

        agent2 = _FakeAgentExecutor()
        verifier2 = _FakeVerifierExecutor()
        second = run_workflow(
            spec, goal=GOAL, model=MODEL, workdir=wd,
            step_executor=agent2, verifier_executor=verifier2,
            retrieve_fn=_deterministic_retrieve_fn(), publish=False, commit=True,
            resume=True, resume_state=state,
            approval_run_id=run_id, approval_gate_id="gate-p1c",
        )
        assert second.awaiting is True, expected_failed
        assert second.awaiting_reason == "approval_refused"
        assert agent2.calls == [], f"{expected_failed}: execution began past a refusal"
        rejected = [c for c in second.checkpoints if c.phase == "p1c_contract_gate"][-1]
        assert rejected.decision == "rejected"
        assert expected_failed in (rejected.approval_evidence or {}).get("failed_checks", [])


def test_chained_resume_preserves_inherited_completion_across_both_parents(
    build_spec, tmp_path, monkeypatch
):
    """Case 4 — initial run → approved first checkpoint → second checkpoint → approved final
    continuation: the third continuation inherits BOTH parents' completion, replays no
    earlier producer, and reaches logical completion with zero additional producer calls
    and zero additional spend."""
    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
    spec = build_spec
    all_names = [p["name"] for p in spec.workflow.params["phases"]]
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)

    parent = _run_to_p1c(spec, wd)
    _write_run_ledger(tmp_path, spec.name, "run-root", parent)
    module = _load_run_workflow_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    state1 = module._load_resume_state(spec.name, "run-root")
    assert state1.reached_checkpoints == frozenset({"p1c_contract_gate"})

    _commit_approval(wd, spec.name, "p1c_contract_gate",
                     run_id="run-root", gate_id="gate-p1c")
    agent2 = _FakeAgentExecutor()
    second = run_workflow(
        spec, goal=GOAL, model=MODEL, workdir=wd,
        step_executor=agent2, verifier_executor=_FakeVerifierExecutor(),
        retrieve_fn=_deterministic_retrieve_fn(), publish=False, commit=True,
        resume=True, resume_state=state1,
        approval_run_id="run-root", approval_gate_id="gate-p1c",
    )
    assert second.awaiting is True
    assert second.awaiting_phase == "p6g_acceptance"
    assert agent2.calls[0] == "p2a_timings_route"
    assert "p0a_reanchor_parity" not in agent2.calls, "the second run replayed an ancestor"
    _write_run_ledger(tmp_path, spec.name, "run-mid", second)

    state2 = module._load_resume_state(spec.name, "run-mid")
    assert state2.completed_phases == frozenset(all_names) - {"p6g_acceptance"}
    assert state2.reached_checkpoints == frozenset({"p6g_acceptance"})
    carried = {e["phase"]: e for e in state2.inherited_phases}
    assert carried["p1c_contract_gate"]["from_run_id"] == "run-root", (
        "the approved checkpoint lost its original provenance"
    )
    assert carried["p0a_reanchor_parity"]["from_run_id"] == "run-root"
    assert "p2a_timings_route" not in carried  # run-mid executed it; it is run-mid's own

    _commit_approval(wd, spec.name, "p6g_acceptance",
                     run_id="run-mid", gate_id="gate-p6g")
    agent3 = _FakeAgentExecutor()
    third = run_workflow(
        spec, goal=GOAL, model=MODEL, workdir=wd,
        step_executor=agent3, verifier_executor=_FakeVerifierExecutor(),
        retrieve_fn=_deterministic_retrieve_fn(), publish=False, commit=True,
        resume=True, resume_state=state2,
        approval_run_id="run-mid", approval_gate_id="gate-p6g",
    )
    assert agent3.calls == [], "an earlier producer replayed on the final continuation"
    assert third.already_complete is True
    assert third.total_cost_usd == 0.0, "inherited invocations were charged again"
    final_decisions = {c.phase: c.decision for c in third.checkpoints}
    assert final_decisions.get("p6g_acceptance") == "approved"
    inherited3 = {e["phase"]: e for e in third.inherited_phases}
    assert inherited3["p1c_contract_gate"]["from_run_id"] == "run-root"
    assert inherited3["p2a_timings_route"]["from_run_id"] == "run-mid"


def test_refused_resume_preserves_inherited_completion_and_the_unresolved_checkpoint(
    build_spec, tmp_path, monkeypatch
):
    """Reviewer reproduction (Astra, 2026-09-15): reach p1c → an unsigned resume REFUSES →
    approve that refused child → resume it. A refusal executes nothing, so its ledger must
    still carry (a) the completion it inherited and (b) the checkpoint it left unresolved —
    otherwise the next continuation forgets both, replays producers, and stops at p1c again."""
    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
    spec = build_spec
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)

    parent = _run_to_p1c(spec, wd)
    _write_run_ledger(tmp_path, spec.name, "run-root", parent)
    module = _load_run_workflow_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    state1 = module._load_resume_state(spec.name, "run-root")
    assert state1.reached_checkpoints == frozenset({"p1c_contract_gate"})

    # Run 2: the unsigned resume refuses — no approval artifact exists.
    refusing_agent = _FakeAgentExecutor()
    refused = run_workflow(
        spec, goal=GOAL, model=MODEL, workdir=wd,
        step_executor=refusing_agent, verifier_executor=_FakeVerifierExecutor(),
        retrieve_fn=_deterministic_retrieve_fn(), publish=False, commit=True,
        resume=True, resume_state=state1,
        approval_run_id="run-root", approval_gate_id="gate-p1c",
    )
    assert refused.awaiting is True and refused.awaiting_reason == "approval_refused"
    assert refusing_agent.calls == []
    _write_run_ledger(tmp_path, spec.name, "run-refused", refused)

    # The refused child's ledger still carries the family's continuation state...
    state2 = module._load_resume_state(spec.name, "run-refused")
    assert state2.completed_phases == frozenset({
        "p0a_reanchor_parity", "p0b_parity_gate", "p1a_ia_amendment",
        "p1b_gate_first_viewport",
    }), "the refusal dropped the completion it inherited"
    assert state2.reached_checkpoints == frozenset({"p1c_contract_gate"}), (
        "the refusal dropped the unresolved checkpoint identity"
    )

    # ...so approving THAT CHILD and resuming it proceeds past p1c without replay.
    _commit_approval(wd, spec.name, "p1c_contract_gate",
                     run_id="run-refused", gate_id="gate-p1c")
    agent3 = _FakeAgentExecutor()
    third = run_workflow(
        spec, goal=GOAL, model=MODEL, workdir=wd,
        step_executor=agent3, verifier_executor=_FakeVerifierExecutor(),
        retrieve_fn=_deterministic_retrieve_fn(), publish=False, commit=True,
        resume=True, resume_state=state2,
        approval_run_id="run-refused", approval_gate_id="gate-p1c",
    )
    assert "p1c_contract_gate" not in agent3.calls, "the approved checkpoint re-ran"
    assert agent3.calls[0] == "p2a_timings_route"
    assert "p0a_reanchor_parity" not in agent3.calls, (
        "the refusal's child replayed producers the family already paid for"
    )
    # the continuation reached its own designed stop — the final acceptance checkpoint
    assert third.awaiting is True and third.awaiting_phase == "p6g_acceptance"
    approved = [c for c in third.checkpoints if c.phase == "p1c_contract_gate"]
    assert approved and approved[-1].decision == "approved"


def test_fully_bound_final_continuation_validates_from_recorded_lineage_not_the_index(
    build_spec, tmp_path, monkeypatch
):
    """Reviewer reproduction (Astra, 2026-09-15): with identical parent ledgers and correctly
    bound approvals, the final continuation must validate p1c from its RECORDED ORIGIN — not
    from whichever run the global spec index currently points at. Pre-fix, the same chain
    succeeded with a current index entry and refused with a stale/unrelated one."""
    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
    spec = build_spec
    module = _load_run_workflow_module()

    index_variants = {
        # the index points at the selected parent (the pre-fix happy path)
        "current": {"p1c_contract_gate": {
            "decision": "approved", "reached_at": "2026-09-14T00:00:00+00:00",
        }},
        # no usable index record (the pre-fix refusal path)
        "stale": {},
        # an unrelated run's decision (the pre-fix refusal path)
        "unrelated": {"p1c_contract_gate": {"decision": "rejected"}},
    }
    for variant, records in index_variants.items():
        wd = tmp_path / variant
        wd.mkdir()
        _git_init(wd)
        parent = _run_to_p1c(spec, wd)
        run_root = f"run-root-{variant}"
        _write_run_ledger(tmp_path, spec.name, run_root, parent)
        monkeypatch.setattr(module, "ROOT", tmp_path)
        state1 = module._load_resume_state(spec.name, run_root)

        _commit_approval(wd, spec.name, "p1c_contract_gate",
                         run_id=run_root, gate_id="gate-p1c")
        agent2 = _FakeAgentExecutor()
        second = run_workflow(
            spec, goal=GOAL, model=MODEL, workdir=wd,
            step_executor=agent2, verifier_executor=_FakeVerifierExecutor(),
            retrieve_fn=_deterministic_retrieve_fn(), publish=False, commit=True,
            resume=True, resume_state=state1,
            approval_run_id=run_root, approval_gate_id="gate-p1c",
        )
        assert second.awaiting is True and second.awaiting_phase == "p6g_acceptance", variant
        run_mid = f"run-mid-{variant}"
        _write_run_ledger(tmp_path, spec.name, run_mid, second)
        state2 = module._load_resume_state(spec.name, run_mid)

        # The global index now points wherever the variant says; validation must not care.
        monkeypatch.setattr(
            runner_module,
            "_previous_checkpoint_state",
            lambda spec, phase, _records=records: _records.get(phase),
        )
        _commit_approval(wd, spec.name, "p6g_acceptance",
                         run_id=run_mid, gate_id="gate-p6g")
        agent3 = _FakeAgentExecutor()
        third = run_workflow(
            spec, goal=GOAL, model=MODEL, workdir=wd,
            step_executor=agent3, verifier_executor=_FakeVerifierExecutor(),
            retrieve_fn=_deterministic_retrieve_fn(), publish=False, commit=True,
            resume=True, resume_state=state2,
            approval_run_id=run_mid, approval_gate_id="gate-p6g",
        )
        assert third.awaiting is False, f"{variant}: the final continuation refused"
        assert third.already_complete is True, variant
        assert agent3.calls == [], variant
        decisions = {c.phase: c.decision for c in third.checkpoints}
        assert decisions.get("p1c_contract_gate") == "approved", variant
        assert decisions.get("p6g_acceptance") == "approved", variant


def test_explicit_resume_never_relaxes_run_gate_binding_to_the_global_index(
    build_spec, tmp_path, monkeypatch
):
    """Reviewer reproduction (Astra, 2026-09-15): a checkpoint's FIRST explicit continuation
    has no inherited origin yet — the empty origin map is NOT legacy. The expected run/gate
    binding must stand, so an approval naming the correct candidate but a FOREIGN run/gate is
    refused with ZERO dispatch even when the global index currently reports an approved entry
    (pre-fix, that combination executed p2a)."""
    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
    spec = build_spec
    module = _load_run_workflow_module()
    for index_state, records in {
        # the pre-fix bypass: an unrelated approved entry stripped the binding
        "approved": {"p1c_contract_gate": {
            "decision": "approved", "reached_at": "2026-09-14T00:00:00+00:00",
        }},
        "rejected": {"p1c_contract_gate": {"decision": "rejected"}},
        "absent": {},
    }.items():
        wd = tmp_path / f"wd-{index_state}"
        wd.mkdir()
        _git_init(wd)
        parent = _run_to_p1c(spec, wd)
        run_id = f"run-parent-{index_state}"
        _write_run_ledger(tmp_path, spec.name, run_id, parent)
        monkeypatch.setattr(module, "ROOT", tmp_path)
        state = module._load_resume_state(spec.name, run_id)
        assert state.inherited_phases == (), "the first explicit continuation has no origins"
        assert state.reached_checkpoints == frozenset({"p1c_contract_gate"})

        # The approval names the correct candidate/tree, but a FOREIGN run and gate.
        ck = _git("rev-parse", "HEAD", cwd=wd).stdout.strip()
        tree = _git("rev-parse", "HEAD^{tree}", cwd=wd).stdout.strip()
        _commit_approval(wd, spec.name, "p1c_contract_gate", text=_approval_text(binding={
            "spec": spec.name, "phase": "p1c_contract_gate", "candidate": ck, "tree": tree,
            "run": "run-foreign", "gate": "gate-foreign",
        }))

        monkeypatch.setattr(
            runner_module,
            "_previous_checkpoint_state",
            lambda spec, phase, _records=records: _records.get(phase),
        )
        agent2 = _FakeAgentExecutor()
        verifier2 = _FakeVerifierExecutor()
        second = run_workflow(
            spec, goal=GOAL, model=MODEL, workdir=wd,
            step_executor=agent2, verifier_executor=verifier2,
            retrieve_fn=_deterministic_retrieve_fn(), publish=False, commit=True,
            resume=True, resume_state=state,
            approval_run_id=run_id, approval_gate_id="gate-p1c",
        )
        assert second.awaiting is True, index_state
        assert second.awaiting_phase == "p1c_contract_gate", index_state
        assert second.awaiting_reason == "approval_refused", index_state
        assert agent2.calls == [], f"{index_state}: execution began past a foreign approval"
        assert verifier2.calls == [], index_state
        rejected = [c for c in second.checkpoints if c.phase == "p1c_contract_gate"][-1]
        assert rejected.decision == "rejected", index_state
        failed = (rejected.approval_evidence or {}).get("failed_checks", [])
        assert "run_id" in failed and "gate_id" in failed, (index_state, failed)


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
        self.prompts: dict[str, str] = {}
        self.cost = cost

    def execute(self, request: StepRequest) -> StepResult:
        self.calls.append(request.phase_name)
        self.attempts.append(request.attempt)
        self.prompts[request.phase_name] = request.prompt
        target = Path(request.workdir) / "work" / f"{request.phase_name}_{request.attempt}.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x")
        return StepResult(
            ok=True, state="ok", exit_code=0,
            prompt_tokens=10, completion_tokens=20, total_tokens=30,
            estimated_cost_usd=self.cost,
        )


class _FailOnceThenOkExecutor(_CostingAgentExecutor):
    """Fails the named phase's FIRST attempt (escalation fires), then succeeds with cost."""

    def __init__(self, fail_first: str, cost: float = 0.001):
        super().__init__(cost=cost)
        self.fail_first = fail_first
        self.failures = 0

    def execute(self, request: StepRequest) -> StepResult:
        if request.phase_name == self.fail_first and self.failures == 0:
            self.failures += 1
            self.calls.append(request.phase_name)
            self.attempts.append(request.attempt)
            self.prompts[request.phase_name] = request.prompt
            # A FAILED attempt is still a PAID invocation — the fake reports its cost so the
            # cumulative-spend assertions are meaningful.
            return StepResult(
                ok=False, state="failed", error="agent failed", exit_code=1,
                prompt_tokens=10, completion_tokens=20, total_tokens=30,
                estimated_cost_usd=self.cost,
            )
        return super().execute(request)


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


TWO_CORRECTION_YAML = """\
name: two_correction_fixture
question: a native gate failure followed by a downstream test failure
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

ESCALATION_CORRECTION_YAML = """\
name: escalation_correction_fixture
question: an escalating agent followed by a bounded correction
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
    escalation:
      ladder:
        - deepseek/deepseek-v4-flash
        - deepseek/deepseek-v4-pro
      max_attempts: 2
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


class _ScriptedFailures:
    """Fails each named verification a scripted number of times, then passes."""

    def __init__(self, failures: dict[str, int]):
        self.remaining = dict(failures)
        self.calls: list[str] = []

    def execute(self, request: StepRequest) -> StepResult:
        self.calls.append(request.phase_name)
        remaining = self.remaining.get(request.phase_name, 0)
        if remaining > 0:
            self.remaining[request.phase_name] = remaining - 1
            return StepResult(
                ok=False, state="failed", error="suite failed (1/3 passed)",
                tests_passed=1, tests_total=3, test_executed_success=False,
            )
        return StepResult(
            ok=True, state="ok", exit_code=0,
            tests_passed=3, tests_total=3, test_executed_success=True,
        )


def test_resume_correction_reruns_the_producer_marked_complete(tmp_path, monkeypatch):
    """Corrective resume: the producer sits in the parent's completion set, but a failing
    verification invalidates its result — the correction must make the producer ELIGIBLE to
    execute again, not merely re-run the verifier against the unchanged candidate."""
    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(GATE_RETRY_TEST_PHASE_YAML)
    spec = load_spec(spec_path)
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)
    agent = _CostingAgentExecutor(cost=0.001)
    verifier = _OnceFailingVerifier("verify")
    state = ResumeState(
        parent_run_id="run-parent",
        ledger_path="/ledgers/run-parent.json",
        completed_phases=frozenset({"build"}),
    )

    result = run_workflow(
        spec, goal="g", model=MODEL, workdir=wd,
        step_executor=agent, verifier_executor=verifier,
        publish=False, commit=True, resume=True, resume_state=state,
    )
    assert result.ok is True
    assert agent.calls == ["build"], "the producer was skipped and only the verifier re-ran"
    assert "CORRECTION ATTEMPT" in agent.prompts["build"]
    assert [p.phase for p in result.phases] == ["build", "verify"]


def test_repeated_correction_retains_each_paid_invocation_once(tmp_path, monkeypatch):
    """A native gate failure followed by a downstream test failure: three paid $0.001
    invocations must read as exactly $0.003, with three unique attempt identities and ONE
    cumulative sequence — the old helper re-appended history the record already seeded."""
    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(TWO_CORRECTION_YAML)
    spec = load_spec(spec_path)
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)
    agent = _CostingAgentExecutor(cost=0.001)
    verifier = _ScriptedFailures({"build__test_gate": 1, "verify": 1})

    result = run_workflow(
        spec, goal="g", model=MODEL, workdir=wd,
        step_executor=agent, verifier_executor=verifier,
        publish=False, commit=True,
    )
    assert result.ok is True
    assert agent.calls == ["build", "build", "build"]
    assert agent.attempts == [1, 2, 3]
    build = next(p for p in result.phases if p.phase == "build")
    assert len(build.attempts) == 3, "a paid invocation was duplicated or discarded"
    assert [row["attempt_number"] for row in build.attempts] == [1, 2, 3]
    assert round(build.cost_usd, 6) == 0.003, "duplicated history overcounted the spend"
    records = [r for r in result.attempts if r.phase == "build"]
    assert len(records) == 3
    assert len({r.attempt_id for r in records}) == 3, "duplicate attempt ids"
    assert records[0].status == "failed" and records[0].first_pass is False
    assert records[0].retry_reason.startswith("correction")
    assert records[2].accepted is True


def test_escalation_then_correction_advances_past_all_prior_invocations(tmp_path, monkeypatch):
    """An escalation (two paid invocations in ONE phase execution) followed by a correction:
    the next executor identity must advance past ALL prior invocations — both ladder rows —
    not merely count phase-loop rewinds (which would collide at ordinal 2)."""
    monkeypatch.setenv("FINOPS_EMIT_SELF", "0")
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(ESCALATION_CORRECTION_YAML)
    spec = load_spec(spec_path)
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)
    agent = _FailOnceThenOkExecutor("build", cost=0.001)
    verifier = _OnceFailingVerifier("verify")

    result = run_workflow(
        spec, goal="g", model=MODEL, workdir=wd,
        step_executor=agent, verifier_executor=verifier,
        publish=False, commit=True,
    )
    assert result.ok is True
    assert agent.calls == ["build", "build", "build"]
    assert agent.attempts == [1, 2, 3], "the correction reused an escalated attempt ordinal"
    build = next(p for p in result.phases if p.phase == "build")
    assert [row["attempt_number"] for row in build.attempts] == [1, 2, 3]
    assert len(build.attempts) == 3
    assert round(build.cost_usd, 6) == 0.003
    records = [r for r in result.attempts if r.phase == "build"]
    assert len({r.attempt_id for r in records}) == 3
    assert records[1].escalation_from == MODEL
    assert records[0].escalation_to is None


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
