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

from agentic_dynamics.experiment.experiment_spec import load_spec
from agentic_dynamics.runtime import workflow_runner as wr
from agentic_dynamics.runtime.executor import StepResult

#: The checkout root — the LIVE durable tree lives at ``<root>/experiments/results``. Resolved
#: from this file, never from the process cwd, so the regression's before/after snapshot always
#: names the same tree the runner would otherwise write into.
_REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _stub_emit_write_path(tmp_path_factory, monkeypatch):
    """No test in this module may reach the real GB/emit write path.

    The module's fixture spec opts in with ``rag.emit_self`` / ``rag.emit_report: true``, which
    ``_finding_emit_enabled`` returns BEFORE the suite-wide ``FINFOPS_EMIT_SELF=0`` disarm
    (``tests/conftest.py``). Without this guard four tests write real findings + report files
    into the live durable tree on every run. Two layers are required:

    (1) stub ``knowledge_ingestion.emit_phase_finding`` — the one durable write+publish entry
        both emit paths import IN-FUNCTION (so the call-time module attribute is intercepted);
    (2) point ``FINOPS_RESULTS_DIR`` at a tmp tree — ``_emit_research_report`` writes its report
        file DIRECTLY (``path.write_text``) before calling ``emit_phase_finding``, so the stub
        alone would still leak the report file.

    The returned recording list lets the regression prove the gate actually opened (non-vacuous)
    and was intercepted. Tests that exercise the real ``_emit_research_report`` override this
    fixture afterwards (their ``monkeypatch`` calls apply later), so their coverage is intact.
    """
    from agentic_dynamics.knowledge import knowledge_ingestion as ki

    emitted = []
    monkeypatch.setattr(ki, "emit_phase_finding", lambda pr, **kw: emitted.append((pr.phase, kw)))
    monkeypatch.setenv("FINOPS_RESULTS_DIR", str(tmp_path_factory.mktemp("results")))
    return emitted


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


# ── v1.3.1: F1 (run_model outranks the router) + F2 (unique report stamps) ────────────────────

RUN_MODEL_SPEC = """name: t_wml_run_model
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
        run_model: openai/gpt-5.6-terra
        prompt: |
          prior {goal}
"""


def test_declared_run_model_outranks_the_router(tmp_path):
    """F1 (live run-0fad6c313dcd): the production root always injects route_step and that
    router never reads phase_def, so a spec's ``run_model:`` was silently ignored — the loop's
    "DIFFERENT model" adversarial phase ran on the run model. The declared override must win.

    Exercised on the CONTAINERIZED shape (an injected step executor receives the
    runner-resolved model): the in-process LocalAgentExecutor re-applies ``run_model`` late
    (executor.py:386), which masks the runner-level bug — the prepared fleet step carries the
    runner's choice, so that is where the override must resolve.
    """
    _init_repo(tmp_path)
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(RUN_MODEL_SPEC, encoding="utf-8")
    spec = load_spec(spec_path)

    class _RecordingExecutor:
        def __init__(self) -> None:
            self.models: list[str] = []

        def execute(self, request):
            self.models.append(str(request.model))
            return StepResult(ok=True, state="ok")

    executor = _RecordingExecutor()
    result = wr.run_workflow(
        spec,
        goal="g",
        model="deepseek/deepseek-v4-flash",
        workdir=tmp_path,
        commit=False,
        step_executor=executor,
        router=lambda phase_def, state, preferences, signals=None: "router/picked-model",
    )
    assert result.ok
    assert executor.models == ["openai/gpt-5.6-terra"]


def test_report_stamp_is_unique_within_a_second(tmp_path, monkeypatch):
    """F2 (live run-0fad6c313dcd): a whole-second stamp made two same-phase reports inside one
    second overwrite each other — nondeterministic counts and a lost report. The stamp now
    carries microseconds, so same-second reports are two files."""
    from types import SimpleNamespace

    import agentic_dynamics.knowledge.knowledge_ingestion as ki

    results = tmp_path / "durable"
    monkeypatch.setenv("FINOPS_RESULTS_DIR", str(results))
    monkeypatch.setattr(ki, "emit_phase_finding", lambda pr, **kw: None)
    monkeypatch.setattr(wr, "_capture_session_report", lambda sid: "the report body")
    stamps = iter(["2026-09-21T18:25:45.111111+00:00", "2026-09-21T18:25:45.222222+00:00"])
    monkeypatch.setattr(wr, "_now", lambda: next(stamps))
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
    for _ in range(2):
        wr._emit_research_report(
            pr, goal="g", spec_name="t_wml", wd=tmp_path, rag_params={"emit_scope": "s"}
        )
    reports = sorted((results / "workflows" / "t_wml" / "reports").glob("*_prior.md"))
    assert len(reports) == 2  # same wall-clock second, two files — no overwrite


# ── the live-KB test-emission leak: the module-local guard + its regression ───────────────────


def _snapshot_paths(root: Path) -> set[str]:
    """The SET of file paths under ``root`` (never a count).

    Report stamps carry microseconds but the REPORT filenames of a single phase can still land
    in nondeterministic order/counts across runs; a path SET is the stable invariant — it either
    gained a file or it did not.
    """
    if not root.exists():
        return set()
    return {str(p) for p in root.rglob("*") if p.is_file()}


def test_no_emission_escapes_the_module_under_the_suite_disarm(
    tmp_path, monkeypatch, _stub_emit_write_path
):
    """Regression: while the suite disarm is active, this module must not write to the live KB.

    The fixture spec declares ``rag.emit_self: true`` / ``emit_report: true``, and the runner
    intentionally lets an explicit opt-in outrank ``FINFOPS_EMIT_SELF=0``
    (``_finding_emit_enabled``). So the module-local autouse guard, not the suite env, is what
    keeps the live durable tree clean. This test proves BOTH halves:

    * the emit gate actually opened and was intercepted (``_stub_emit_write_path`` is
      non-empty) — otherwise the guard would be vacuous and the test would pass even if the
      real write path were reachable;
    * the live path sets under ``experiments/results/kb`` and
      ``experiments/results/workflows/t_wml`` are unchanged — the report file's direct write
      is also contained.
    """
    _init_repo(tmp_path)
    spec = load_spec(_write_spec(tmp_path))

    # Positive control: the suite disarm is set, yet the spec's explicit opt-in opens the gate.
    # (If this stops holding, the leak's premise changed — fail loudly rather than silently
    # passing with nothing to guard.)
    assert os.environ.get("FINOPS_EMIT_SELF") == "0"
    resolved = wr._resolve_rag_params(spec, None, wd=tmp_path, rag_augment=False)
    assert wr._finding_emit_enabled(resolved, {}) is True

    # Snapshot the LIVE durable tree BEFORE the run (path SETS, not counts).
    live_kb = _REPO_ROOT / "experiments" / "results" / "kb"
    live_reports = _REPO_ROOT / "experiments" / "results" / "workflows" / "t_wml"
    before = _snapshot_paths(live_kb) | _snapshot_paths(live_reports)

    def fake(prompt, **kwargs):
        (tmp_path / "notes").mkdir(exist_ok=True)
        (tmp_path / "notes" / "plan.md").write_text("the plan")
        (tmp_path / "work.txt").write_text("work")
        return _R()

    wr.run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=fake)

    # Interception proof — the runner reached the emit seam and the guard caught it. Removing
    # the stub makes this empty and this assertion fail.
    assert _stub_emit_write_path, "the emit seam was ever reached — the regression is vacuous"
    # Containment proof — nothing escaped to the live durable tree. Removing the results-dir
    # redirect lets `_emit_research_report` write its report file directly, so this assertion
    # fails.
    after = _snapshot_paths(live_kb) | _snapshot_paths(live_reports)
    assert after == before
