"""World-model loop v1 gates: the phase artifact gate + the committed-phase report emit.

Covers the two runner additions of 2026-09-21:

* ``requires_files`` — a phase REFUSES before spend when a declared artifact is absent
  (the world-model loop's plan gate: execute cannot run without ``notes/plan.md``);
* ``rag.emit_report`` — a committed phase ALSO emits the full report-variant record, so a
  loop's notes become retrievable knowledge, not only git files.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from agentic_dynamics.core.paths import PROJECT_ROOT
from agentic_dynamics.experiment.experiment_spec import load_spec
from agentic_dynamics.runtime import workflow_runner as wr
from agentic_dynamics.runtime.executor import StepResult


@pytest.fixture(autouse=True)
def _stub_emit_write_path(monkeypatch, tmp_path_factory):
    """No test in this module may reach the live KB/report tree (2026-09-21 leak).

    ``SPEC`` / ``SHAPE_SPEC`` opt in with ``rag.emit_self`` / ``rag.emit_report: true``, which
    outranks the suite-wide ``FINFOPS_EMIT_SELF=0`` disarm
    (``workflow_runner._finding_emit_enabled``). Left unguarded, the four tests that commit an
    agent phase therefore reach the real durable write on every run and litter the canonical KB
    with ``self-test_*`` findings.

    The guard is MODULE-LOCAL (not ``tests/conftest.py``): the suite-wide install would also
    intercept ``tests/test_workflow_runner.py``'s
    ``test_finding_emit_default_run_writes_enriched_records``, which intentionally exercises the
    real write path against a tmp tree. Intercept the single durable write + publish entry
    (``knowledge_ingestion.emit_phase_finding``) — both ``_emit_self_finding`` and
    ``_emit_research_report`` import it *inside* the function, so patching the module attribute
    is honored — and point the durable results tree at tmp, containing
    ``_emit_research_report``'s direct ``path.write_text`` (which happens BEFORE the emit call).

    Tests that exercise the real write path stub these themselves and override this fixture;
    because fixtures share one function-scoped ``monkeypatch``, the test-body setter wins at call
    time and LIFO undo restores cleanly. Yields the recorder so the regression can request it.
    """
    import agentic_dynamics.knowledge.knowledge_ingestion as ki

    results = tmp_path_factory.mktemp("live_kb_guard")
    monkeypatch.setenv("FINOPS_RESULTS_DIR", str(results))
    emitted: list[tuple[str, dict]] = []
    monkeypatch.setattr(ki, "emit_phase_finding", lambda pr, **kw: emitted.append((pr.phase, kw)))
    yield emitted


SPEC = """name: t_wml
question: q
version: "0.1"
artifact_kind: workflow
intent: measure
side_effects: {repository: true, external_services: false}
repeatable: true
factors: [{name: model, levels: [m]}]
design: factorial
rules: []
metrics: []
comparison: null
writeup: {format: lab_book, sections: [question]}
stop: {budget_usd: 1.0, max_attempts: 1}
adapt: {strategy: manual, selection: highest_uncertainty}
workflow:
  kind: agent_task
  params:
    language: python
    fork: false
    rag_augment: false
    rag:
      emit_self: true
      emit_report: true
      emit_scope: agentic-dynamics
    context:
      domain_context: TEST
    phases:
      - name: prior
        kind: agent
        timeout: 60
        prompt: |
          prior {goal}
      - name: execute
        kind: agent
        timeout: 60
        requires_files: [notes/plan.md]
        prompt: |
          execute {goal}
"""


def _init_repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "seed.txt").write_text("seed")
    subprocess.run(["git", "add", "seed.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=tmp_path, check=True)


class _R:
    ok = True
    error = ""
    session_id = "ses_child"
    total_tokens = 10
    estimated_cost_usd = 0.0
    final_response = "ok"


def test_artifact_gate_refuses_without_the_declared_plan(tmp_path):
    _init_repo(tmp_path)
    spec = load_spec(_write_spec(tmp_path))
    calls = []

    def fake(prompt, **kwargs):
        calls.append(prompt)
        (tmp_path / "phase_1_marker.txt").write_text("prior ran")  # no notes/plan.md
        return _R()

    result = wr.run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=fake)
    phases = {p.phase: p for p in result.phases}
    assert phases["execute"].status == "failed"
    assert "ARTIFACT_MISSING" in phases["execute"].error
    assert "notes/plan.md" in phases["execute"].error
    # the gate refuses BEFORE the agent runs: exactly one invocation (the prior phase)
    assert len(calls) == 1


def test_artifact_gate_passes_when_the_prior_wrote_the_plan(tmp_path):
    _init_repo(tmp_path)
    spec = load_spec(_write_spec(tmp_path))
    calls = []

    def fake(prompt, **kwargs):
        calls.append(prompt)
        (tmp_path / "notes").mkdir(exist_ok=True)
        (tmp_path / "notes" / "plan.md").write_text("the plan")
        return _R()

    result = wr.run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=fake)
    phases = {p.phase: p for p in result.phases}
    assert phases["execute"].status == "ok"
    assert len(calls) == 2  # prior AND execute ran


def test_emit_report_opts_in_for_committed_phases(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    spec = load_spec(_write_spec(tmp_path))
    emitted = []

    def fake(prompt, **kwargs):
        (tmp_path / "notes").mkdir(exist_ok=True)
        (tmp_path / "notes" / "plan.md").write_text("the plan")
        (tmp_path / "work.txt").write_text("work")
        return _R()

    monkeypatch.setattr(
        wr, "_emit_self_finding", lambda pr, goal, scope: emitted.append(("self", pr.phase))
    )
    monkeypatch.setattr(
        wr, "_emit_research_report", lambda pr, **kw: emitted.append(("report", pr.phase))
    )
    wr.run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=fake)
    # a committed phase emits BOTH the metadata finding and (opted in) the report record
    assert ("self", "prior") in emitted
    assert ("report", "prior") in emitted


def _write_spec(tmp_path):
    path = tmp_path / "spec.yaml"
    path.write_text(SPEC, encoding="utf-8")
    return path


def test_artifact_path_honors_the_results_dir_contract(tmp_path, monkeypatch):
    import agentic_dynamics.knowledge.knowledge_ingestion as ki

    results = tmp_path / "durable" / "experiments" / "results"
    monkeypatch.setenv("FINOPS_RESULTS_DIR", str(results))
    assert ki._artifact_path("abc") == results / "kb" / "abc.json"


SHAPE_SPEC = SPEC.replace(
    "        requires_files: [notes/plan.md]",
    "        requires_files: [notes/plan.md]\n"
    "        requires_content:\n"
    '          notes/plan.md: ["## Files", "## Tests", "## Acceptance"]',
)


def test_shape_gate_refuses_an_unsectioned_plan(tmp_path):
    _init_repo(tmp_path)
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(SHAPE_SPEC, encoding="utf-8")
    spec = load_spec(spec_path)
    calls = []

    def fake(prompt, **kwargs):
        calls.append(prompt)
        (tmp_path / "notes").mkdir(exist_ok=True)
        (tmp_path / "notes" / "plan.md").write_text("a plan with no required sections")
        return _R()

    result = wr.run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=fake)
    phases = {p.phase: p for p in result.phases}
    assert phases["execute"].status == "failed"
    assert "ARTIFACT_SHAPE" in phases["execute"].error
    assert len(calls) == 1  # refused before the execute agent ran


def test_shape_gate_passes_when_the_plan_carries_its_sections(tmp_path):
    _init_repo(tmp_path)
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(SHAPE_SPEC, encoding="utf-8")
    spec = load_spec(spec_path)
    calls = []

    def fake(prompt, **kwargs):
        calls.append(prompt)
        (tmp_path / "notes").mkdir(exist_ok=True)
        (tmp_path / "notes" / "plan.md").write_text("## Files\nx\n## Tests\ny\n## Acceptance\nz")
        return _R()

    result = wr.run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=fake)
    phases = {p.phase: p for p in result.phases}
    assert phases["execute"].status == "ok"
    assert len(calls) == 2


def test_report_path_honors_the_results_dir_contract(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import agentic_dynamics.knowledge.knowledge_ingestion as ki

    results = tmp_path / "durable" / "experiments" / "results"
    monkeypatch.setenv("FINOPS_RESULTS_DIR", str(results))
    captured = {}
    monkeypatch.setattr(ki, "emit_phase_finding", lambda pr, **kw: captured.update(kw))
    monkeypatch.setattr(wr, "_capture_session_report", lambda sid: "the report body")
    pr = SimpleNamespace(
        phase="prior",
        session_id="ses_x",
        final_response="the report body",
        status="ok",
        cost_usd=0.0,
        tokens={},
        test_executed_success=None,
        commit_hash="x",
    )
    wr._emit_research_report(
        pr, goal="g", spec_name="t_wml", wd=tmp_path, rag_params={"emit_scope": "s"}
    )
    path = str(captured.get("report_path", ""))
    assert str(results) in path and path.endswith("_prior.md")
    assert Path(path).is_file()


def test_no_emission_escapes_the_module_under_the_suite_disarm(
    tmp_path, monkeypatch, _stub_emit_write_path
):
    """Regression for the 2026-09-21 live-KB leak: the disarm is powerless against an opt-in.

    The exact leak precondition is that ``FINFOPS_EMIT_SELF=0`` is active AND the shared ``SPEC``
    still opts in (``rag.emit_self: true``), because ``_finding_emit_enabled`` returns the
    explicit value before consulting the env. Drive the REAL ``wr._emit_self_finding`` /
    ``wr._emit_research_report`` routing — no per-test stubbing of those functions — so the only
    thing standing between the run and the live tree is the module fixture. Assert both halves
    the plan calls the contract points: (i) the emission FIRED and was seen by the guard (it was
    intercepted, not silently skipped), and (ii) the live durable directories are byte-identical
    before/after. Assertion (ii) alone would pass even without the stub (the redirect contains
    the report), so both are required.
    """
    _init_repo(tmp_path)
    # The leak precondition, asserted rather than assumed.
    assert os.environ.get("FINOPS_EMIT_SELF") == "0"
    assert wr._finding_emit_enabled({"emit_self": True}, {}) is True

    kb_dir = PROJECT_ROOT / "experiments" / "results" / "kb"
    reports_dir = PROJECT_ROOT / "experiments" / "results" / "workflows" / "t_wml"
    before_kb = set(kb_dir.glob("*")) if kb_dir.is_dir() else set()
    before_reports = set(reports_dir.rglob("*")) if reports_dir.is_dir() else set()

    spec = load_spec(_write_spec(tmp_path))

    def fake(prompt, **kwargs):
        (tmp_path / "notes").mkdir(exist_ok=True)
        (tmp_path / "notes" / "plan.md").write_text("## Files\nx\n## Tests\ny\n## Acceptance\nz")
        return _R()

    wr.run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=fake)

    # (i) the route fired and was intercepted by the module guard ...
    assert any(phase == "prior" for phase, _kw in _stub_emit_write_path)
    # (ii) ... and nothing escaped to the live durable tree.
    assert (set(kb_dir.glob("*")) if kb_dir.is_dir() else set()) == before_kb
    assert (set(reports_dir.rglob("*")) if reports_dir.is_dir() else set()) == before_reports


# ── v1.3: the plan-driven test gate (tests_from_plan + the explicit skip) ─────────────────────

PLAN_GATE_SPEC = """name: t_wml_plan_gate
question: q
version: "0.1"
artifact_kind: workflow
intent: measure
side_effects: {repository: true, external_services: false}
repeatable: true
factors: [{name: model, levels: [m]}]
design: factorial
rules: []
metrics: []
comparison: null
writeup: {format: lab_book, sections: [question]}
stop: {budget_usd: 1.0, max_attempts: 1}
adapt: {strategy: manual, selection: highest_uncertainty}
workflow:
  kind: agent_task
  params:
    language: python
    fork: false
    rag_augment: false
    rag: {emit_self: false, emit_report: false}
    context:
      domain_context: TEST
    phases:
      - name: prior
        kind: agent
        timeout: 60
        prompt: |
          prior {goal}
      - name: g_test_gate
        kind: test
        scope: implementation
        timeout: 60
        tests_from_plan: notes/plan.md
        prompt: |
          The declared target verifies the worktree.
"""


def test_plan_test_targets_resolve_existing_files_in_the_tests_section_only(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_in_section.py").write_text("x")
    (tmp_path / "tests" / "test_outside_section.py").write_text("x")
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "plan.md").write_text(
        "# Plan\n\n"
        "## Files\n- `tests/test_outside_section.py`\n- `src/not_a_test.py`\n\n"
        "## Tests\n- `tests/test_in_section.py`\n- `tests/test_missing.py`\n"
        "- `tests/test_in_section.py`\n\n"
        "## Acceptance\n- done\n"
    )
    # Only the ## Tests section; only files that exist; deduplicated.
    assert wr._test_targets_from_plan(notes / "plan.md", tmp_path) == ["tests/test_in_section.py"]


def test_plan_driven_test_gate_skips_explicitly_when_the_plan_names_no_targets(tmp_path):
    _init_repo(tmp_path)
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(PLAN_GATE_SPEC, encoding="utf-8")
    spec = load_spec(spec_path)

    def fake(prompt, **kwargs):
        (tmp_path / "notes").mkdir(exist_ok=True)
        (tmp_path / "notes" / "plan.md").write_text(
            "## Tests\nNo suites are named for this analysis-only run.\n"
        )
        return _R()

    result = wr.run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=fake)
    gate = {p.phase: p for p in result.phases}["g_test_gate"]
    assert gate.status == "ok"
    assert "SKIPPED" in gate.test_gate_note  # explicit, visible — never a silent pass
    assert gate.test_executed_success is None  # never ran — never a fabricated verdict


# ── v1.3: the artifact gate is clone-aware (the fleet clone is the candidate) ──────────────────


def _clone_with_plan(parent: Path, *, with_plan: bool) -> Path:
    """A minimal run-clone-shaped git repo beside the host worktree."""
    clone = parent / "runclone"
    clone.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=clone, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=clone, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=clone, check=True)
    if with_plan:
        (clone / "notes").mkdir()
        (clone / "notes" / "plan.md").write_text("## Files\nx\n## Tests\ny\n## Acceptance\nz\n")
    else:
        (clone / "seed.txt").write_text("seed")
    subprocess.run(["git", "add", "-A"], cwd=clone, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=clone, check=True)
    return clone


class _OkExecutor:
    """The containerized path's step executor, scripted: every phase returns ok."""

    def __init__(self) -> None:
        self.executed: list[str] = []

    def execute(self, request):
        self.executed.append(request.phase_name)
        return StepResult(ok=True, state="ok")


def test_artifact_gate_reads_the_run_clone_in_the_containerized_path(tmp_path, monkeypatch):
    """Live regression (run-037d7d760bd6): the first fleet (clone-world) submission of the
    loop died ARTIFACT_MISSING because the gate checked the host worktree while the prior
    phase had committed the plan INTO the run's clone. The gate must read the candidate —
    ``git_wd`` (the clone) when one is bound, the worktree otherwise."""
    _init_repo(tmp_path)  # host worktree: deliberately NO notes/plan.md
    clone = _clone_with_plan(tmp_path, with_plan=True)
    monkeypatch.setenv("FINOPS_RUN_CLONE", str(clone))
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(SHAPE_SPEC, encoding="utf-8")
    spec = load_spec(spec_path)

    executor = _OkExecutor()
    result = wr.run_workflow(
        spec, goal="g", model="m", workdir=tmp_path, commit=False, step_executor=executor
    )
    phases = {p.phase: p for p in result.phases}
    assert phases["execute"].status == "ok"  # the clone's plan satisfies the gate
    assert executor.executed == ["prior", "execute"]


def test_artifact_gate_still_refuses_when_the_clone_lacks_the_plan(tmp_path, monkeypatch):
    """The negative control: a clone WITHOUT the plan still refuses, before the step runs."""
    _init_repo(tmp_path)
    clone = _clone_with_plan(tmp_path, with_plan=False)
    monkeypatch.setenv("FINOPS_RUN_CLONE", str(clone))
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(SHAPE_SPEC, encoding="utf-8")
    spec = load_spec(spec_path)

    executor = _OkExecutor()
    result = wr.run_workflow(
        spec, goal="g", model="m", workdir=tmp_path, commit=False, step_executor=executor
    )
    phases = {p.phase: p for p in result.phases}
    assert phases["execute"].status == "failed"
    assert "ARTIFACT_MISSING" in phases["execute"].error
    assert executor.executed == ["prior"]  # refused BEFORE the execute step ran
