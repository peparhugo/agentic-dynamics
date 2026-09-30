"""Tests for the execute runner — run_workflow drives agent_task phases in a worktree."""

import json
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from agentic_dynamics.experiment import spec_status
from agentic_dynamics.experiment.experiment_spec import (
    ExperimentSpec,
    Factor,
    Workflow,
    load_spec,
    validate_spec,
)
from agentic_dynamics.experiment.spec_status import SpecStatusEntry
from agentic_dynamics.knowledge.augment import default_retrieve_fn
from agentic_dynamics.runtime import workflow_runner
from agentic_dynamics.runtime.workflow_runner import (
    PLAN_UNIT_CAP_DEFAULT,
    PhaseWatchdog,
    ResumeState,
    _build_phase_prompt,
    _completed_phases_from_index,
    _expand_plan_phases,
    _load_plan_units,
    _order_plan_units,
    _resolve_test_targets,
    cell_scope,
    run_workflow,
)

SPEC = (
    Path(__file__).resolve().parent.parent / "workflows" / "repository" / "control_room_portal.yaml"
)


def _fake_agent(**overrides):
    base = dict(
        prompt_tokens=10,
        completion_tokens=20,
        reasoning_tokens=5,
        total_tokens=35,
        estimated_cost_usd=0.001,
        files_created=["docs/scope.md"],
        files_modified=[],
        final_response="done",
        ok=True,
        exit_code=0,
        error="",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_spec_loads_and_validates():
    spec = load_spec(SPEC)
    assert spec.name == "control_room_portal"
    assert spec.workflow.kind == "agent_task"
    assert [p["name"] for p in spec.workflow.params["phases"]] == [
        "scope",
        "ux_design",
        "implement",
        "verify",
    ]
    assert validate_spec(spec) == []


def test_phase_prompt_templating():
    phase = {"name": "scope", "prompt": "Write a scope for {goal}. Prior: {prior_phases}"}
    out = _build_phase_prompt(phase, "the portal", ["scope (ok)"])
    assert "the portal" in out
    assert "scope (ok)" in out
    assert "{goal}" not in out


# ── The plan→phases bridge helpers (the loop's open extension) ────────────────────────────────


def _write_units(tmp_path, payload):
    (tmp_path / "notes").mkdir(exist_ok=True)
    path = tmp_path / "notes" / "plan.units.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _unit(uid, *, depends_on=None, goal="do it", tests=None, budget=0.1):
    return {
        "id": uid,
        "goal": goal,
        "files": [f"{uid}.py"],
        "tests": tests or [],
        "acceptance": f"{uid} accepted",
        "budget_usd": budget,
        "depends_on": depends_on or [],
    }


def test_load_plan_units_returns_declaration_order(tmp_path):
    _write_units(tmp_path, {"units": [_unit("b"), _unit("a")]})
    units = _load_plan_units("notes/plan.units.json", tmp_path)
    assert [u["id"] for u in units] == ["b", "a"]


def test_order_plan_units_is_topological_by_dependency(tmp_path):
    # 'second' is DECLARED first but depends on 'first' — order must flip.
    _write_units(tmp_path, {"units": [_unit("second", depends_on=["first"]), _unit("first")]})
    units = _load_plan_units("notes/plan.units.json", tmp_path)
    assert [u["id"] for u in _order_plan_units(units)] == ["first", "second"]


def test_load_plan_units_refuses_a_duplicate_id(tmp_path):
    _write_units(tmp_path, {"units": [_unit("u1"), _unit("u1")]})
    with pytest.raises(ValueError, match="duplicate plan unit id"):
        _load_plan_units("notes/plan.units.json", tmp_path)


def test_load_plan_units_refuses_an_unknown_dependency(tmp_path):
    _write_units(tmp_path, {"units": [_unit("u1", depends_on=["ghost"])]})
    with pytest.raises(ValueError, match="unknown unit"):
        _load_plan_units("notes/plan.units.json", tmp_path)


def test_load_plan_units_refuses_a_missing_artifact(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        _load_plan_units("notes/plan.units.json", tmp_path)


def test_order_plan_units_refuses_a_cycle(tmp_path):
    _write_units(tmp_path, {"units": [_unit("a", depends_on=["b"]), _unit("b", depends_on=["a"])]})
    units = _load_plan_units("notes/plan.units.json", tmp_path)
    with pytest.raises(ValueError, match="cycle"):
        _order_plan_units(units)


def test_expand_plan_phases_renders_unit_placeholders_and_splices_gates(tmp_path):
    _write_units(tmp_path, {"units": [_unit("u1", goal="build the thing")]})
    phases = [
        {"name": "prior", "kind": "agent", "prompt": "p"},
        {
            "name": "execute",
            "kind": "agent",
            "scope": "implementation",
            "timeout": 90,
            "requires_files": ["notes/plan.units.json"],
            "expand_from_plan": "notes/plan.units.json",
            "prompt": "unit {unit_id} goal {unit_goal} files {unit_files} acc {unit_acceptance}",
        },
        {"name": "posterior", "kind": "agent", "prompt": "post"},
    ]
    expanded, record = _expand_plan_phases(phases, tmp_path, run_budget_usd=1.0)
    assert [p["name"] for p in expanded] == [
        "prior",
        "execute__u1",
        "g_u1_test_gate",
        "posterior",
    ]
    slice_def = expanded[1]
    assert slice_def["prompt"] == "unit u1 goal build the thing files u1.py acc u1 accepted"
    assert slice_def["requires_deliverable"] is True
    assert slice_def["scope"] == "implementation"
    assert slice_def["timeout"] == 90
    assert slice_def["requires_files"] == ["notes/plan.units.json"]
    gate_def = expanded[2]
    assert gate_def["kind"] == "test"
    assert gate_def["tests"] == []
    assert record is not None and record["units"] == 1
    # The original list is not mutated in place.
    assert phases[1]["name"] == "execute"


def test_expand_plan_phases_refuses_above_the_unit_cap(tmp_path):
    _write_units(tmp_path, {"units": [_unit("u1"), _unit("u2")]})
    phases = [
        {
            "name": "execute",
            "kind": "agent",
            "expand_from_plan": "notes/plan.units.json",
            "prompt": "x",
        }
    ]
    with pytest.raises(ValueError, match="unit cap"):
        _expand_plan_phases(phases, tmp_path, unit_cap=1)
    # the default cap is a real bound
    assert PLAN_UNIT_CAP_DEFAULT > 1


def test_expand_plan_phases_is_a_noop_without_the_key():
    phases = [{"name": "p1", "kind": "agent", "prompt": "x"}]
    expanded, record = _expand_plan_phases(phases, Path("/nonexistent"))
    assert expanded is phases  # byte-identical path: the SAME list object
    assert record is None


def test_expand_plan_phases_refuses_two_declaring_phases(tmp_path):
    _write_units(tmp_path, {"units": [_unit("u1")]})
    phases = [
        {"name": "a", "kind": "agent", "expand_from_plan": "notes/plan.units.json", "prompt": "x"},
        {"name": "b", "kind": "agent", "expand_from_plan": "notes/plan.units.json", "prompt": "x"},
    ]
    with pytest.raises(ValueError, match="only one phase"):
        _expand_plan_phases(phases, tmp_path)


def test_resolve_test_targets_explicit_empty_list_is_an_explicit_skip(tmp_path):
    # The expansion emits ``tests: []`` for a unit that names no tests — an explicit skip.
    assert _resolve_test_targets({"kind": "test", "tests": []}, tmp_path) == (None, True)
    # Absent keeps the historical whole-tree default; a declared list is targeted exactly.
    assert _resolve_test_targets({"kind": "test"}, tmp_path) == (None, False)
    declared, skipped = _resolve_test_targets(
        {"kind": "test", "tests": ["tests/test_x.py"]}, tmp_path
    )
    assert declared == ["tests/test_x.py"] and skipped is False


def test_run_workflow_phases_in_order(tmp_path):
    spec = load_spec(SPEC)
    seen = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        seen.append(prompt.splitlines()[1][:12])  # capture the "Goal: ..." line tail
        return _fake_agent()

    result = run_workflow(
        spec,
        goal="the goal",
        model="openai/gpt-5.6-sol",
        workdir=tmp_path,
        commit=False,
        run_agentic_fn=agent,
    )
    assert [p.phase for p in result.phases] == ["scope", "ux_design", "implement", "verify"]
    assert len(seen) == 3  # scope, ux, implement are agent phases; verify is test
    assert result.phases[0].tokens["total"] == 35
    assert result.phases[0].cost_usd == 0.001


def test_phase_result_carries_change_detection_availability(tmp_path):
    """Finding 8b: the adapter's changed-set provenance + availability reach the ledger.

    A snapshot-skipped git-status observation is partial; an empty changed set with that
    provenance must be legible as partial on the serialized phase, not as measured "no
    changes".
    """
    spec = load_spec(SPEC)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        return _fake_agent(
            files_modified=[],
            change_detection="git_status",
            change_observation_partial=True,
        )

    result = run_workflow(
        spec, goal="g", model="m", workdir=tmp_path, commit=False, run_agentic_fn=agent
    )

    assert result.phases[0].change_detection == "git_status"
    assert result.phases[0].change_observation_partial is True
    ledger = result.to_dict()["phases"][0]
    assert ledger["change_detection"] == "git_status"
    assert ledger["change_observation_partial"] is True


def test_phase_result_carries_the_prepared_step_reference(tmp_path):
    """Run-inspection slice: the executor's prepared-step reference reaches the phase ledger.

    The parent (the Docker executor) is the only actor that writes the transport, so the
    clone-relative path + prompt hash ride the StepResult and are copied onto the PhaseResult.
    The engine never re-derives either value from the spec.
    """
    from agentic_dynamics.runtime.executor import StepResult

    class _PreparedExecutor:
        def execute(self, request):
            return StepResult(
                ok=True,
                state="ok",
                exit_code=0,
                prepared_step_path=".fleet/prepared_steps/scope.a1.json",
                prepared_step_prompt_sha256="b" * 64,
            )

    spec = load_spec(SPEC)
    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        run_agentic_fn=lambda *a, **k: _fake_agent(),
        step_executor=_PreparedExecutor(),
    )

    phase = result.phases[0]
    assert phase.prepared_step_path == ".fleet/prepared_steps/scope.a1.json"
    assert phase.prepared_step_prompt_sha256 == "b" * 64
    ledger = result.to_dict()["phases"][0]
    assert ledger["prepared_step_path"] == ".fleet/prepared_steps/scope.a1.json"
    assert ledger["prepared_step_prompt_sha256"] == "b" * 64
    # A locally-executed phase (the default executor) records the named absence, not a guess.
    local = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )
    assert local.phases[0].prepared_step_path == ""
    assert local.phases[0].prepared_step_prompt_sha256 == ""


def test_run_workflow_publishes_phase_per_phase(tmp_path, monkeypatch):
    """Each phase start publishes {name, index, total} to the live publisher."""
    published = []

    class FakePublisher:
        def __init__(self, cell_id):
            self.cell_id = cell_id
            self.enabled = True

        def set_status(self, status):
            pass

        def set_phase(self, phase):
            published.append(phase)

        def publish_event(self, event):
            pass

    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)

    spec = load_spec(SPEC)
    run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        run_agentic_fn=lambda *a, **k: _fake_agent(),
        publisher_factory=FakePublisher,
    )

    assert [p["name"] for p in published] == ["scope", "ux_design", "implement", "verify"]
    assert all(p["total"] == 4 for p in published)
    assert [p["index"] for p in published] == [1, 2, 3, 4]


def test_run_workflow_publishes_phase_before_agent_runs(tmp_path, monkeypatch):
    """The phase badge is set at phase *start*, before the agent is invoked."""
    order = []

    class FakePublisher:
        def __init__(self, cell_id):
            self.enabled = True

        def set_status(self, status):
            pass

        def set_phase(self, phase):
            order.append(("phase", phase["name"]))

        def publish_event(self, event):
            pass

    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)

    spec = load_spec(SPEC)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        order.append(("agent",))
        return _fake_agent()

    run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        run_agentic_fn=agent,
        publisher_factory=FakePublisher,
    )

    # scope, ux_design, implement are agent phases (phase-before-agent); verify is
    # a test phase and emits a phase start with no agent invocation.
    assert order == [
        ("phase", "scope"),
        ("agent",),
        ("phase", "ux_design"),
        ("agent",),
        ("phase", "implement"),
        ("agent",),
        ("phase", "verify"),
    ]


def test_run_workflow_resume_publishes_original_phase_index(tmp_path, monkeypatch):
    """On resume, the badge keeps the 1-based absolute index, not a re-based one."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    captured = []

    class FakePublisher:
        def __init__(self, cell_id):
            self.enabled = True

        def set_status(self, status):
            pass

        def set_phase(self, phase):
            captured.append(phase)

        def publish_event(self, event):
            pass

    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)

    spec = load_spec(SPEC)
    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        calls.append(prompt)
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "x.md").write_text(str(len(calls)))  # unique -> commits
        return _fake_agent(ok=len(calls) < 3, error="boom")

    run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        run_agentic_fn=agent,
        publisher_factory=FakePublisher,
    )
    # implement (3rd agent call) failed -> only scope + ux_design committed.

    captured.clear()
    calls.clear()

    def agent2(prompt, *, model, backend, workdir, **kwargs):
        calls.append(prompt)
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "x.md").write_text(str(len(calls)))
        return _fake_agent()

    run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        resume=True,
        run_agentic_fn=agent2,
        publisher_factory=FakePublisher,
    )

    assert [p["name"] for p in captured] == ["implement", "verify"]
    assert [p["index"] for p in captured] == [3, 4]
    assert all(p["total"] == 4 for p in captured)


def test_run_workflow_fails_fast(tmp_path):
    spec = load_spec(SPEC)
    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        calls.append(prompt)
        return _fake_agent(ok=False, error="boom") if len(calls) == 1 else _fake_agent()

    result = run_workflow(
        spec, goal="g", model="m", workdir=tmp_path, commit=False, run_agentic_fn=agent
    )
    assert len(result.phases) == 1  # stopped after first failure
    assert result.phases[0].status == "failed"
    assert result.phases[0].error == "boom"
    assert result.ok is False


def test_run_workflow_verify_phase_runs_tests(tmp_path):
    spec = load_spec(SPEC)
    (tmp_path / "test_ok.py").write_text("def test_passes():\n    assert True\n")

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )
    verify = result.phases[-1]
    assert verify.phase == "verify"
    assert verify.test_executed_success is True
    assert verify.tests_passed >= 1


def test_run_workflow_commits_per_phase(tmp_path):
    spec = load_spec(SPEC)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "scope.md").write_text("scope content")
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    assert result.phases[0].commit_hash  # scope phase produced a commit
    log = subprocess.run(["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True)
    assert "[workflow] scope" in log.stdout


def test_run_workflow_change_analysis_seam(tmp_path, monkeypatch):
    """Review F3: an injected ChangeAnalyzer runs over each committed phase, best-effort,
    and the analysis lands on the phase result — the seam is inert without injection."""
    from agentic_dynamics.runtime.change_analyzer import ChangeAnalysis

    # The sonar/lsp legs are covered by their own unit tests; here they are stubbed to their
    # measured unavailable status so the seam test never reaches the real scanner/mypy.
    monkeypatch.setattr(
        workflow_runner,
        "_sonar_evidence",
        lambda *a, **k: {
            "status": "unavailable",
            "revision_matches": None,
            "new_critical_count": None,
            "analyzed_sha": "",
        },
    )
    monkeypatch.setattr(
        workflow_runner,
        "_lsp_evidence",
        lambda *a, **k: {"status": "unavailable", "new_error_count": None, "tool": "mypy"},
    )

    class RecordingAnalyzer:
        def __init__(self):
            self.changes = []

        def analyze(self, change):
            self.changes.append(change)
            return ChangeAnalysis(
                facts=(
                    {
                        "predicate": "changed_symbol_count",
                        "value": "1",
                        "value_type": "int",
                        "evidence_ids": (),
                    },
                ),
                neighborhood=("f",),
            )

    spec = load_spec(SPEC)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        n = len(calls)
        calls.append(n)
        (Path(workdir) / "app.py").write_text(f"def f{n}():\n    return {n}\n")
        return _fake_agent(files_created=["app.py"])

    analyzer = RecordingAnalyzer()
    result = run_workflow(
        spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent, change_analyzer=analyzer
    )

    # The FIRST phase's commit is the worktree's root commit — no parent to diff, so the
    # seam degrades to None. The SECOND committed phase has a parent: it gets analyzed.
    assert result.phases[0].commit_hash
    assert result.phases[0].change_analysis is None  # root commit: no parent to diff
    assert result.phases[1].commit_hash
    assert analyzer.changes  # the analyzer saw the second phase's change
    change = analyzer.changes[0]
    assert change.delta is not None
    assert {s.qualified_name for s in change.delta.added_symbols} == {"f1"}
    assert {s.qualified_name for s in change.delta.removed_symbols} == {"f0"}
    assert result.phases[1].change_analysis["neighborhood"] == ["f"]
    assert result.phases[1].change_analysis["facts"][0]["predicate"] == "changed_symbol_count"
    assert result.phases[1].change_analysis["graph_updated"] is False


def test_run_workflow_change_analysis_inert_without_injection(tmp_path):
    """Without an injected analyzer the seam is inert: change_analysis stays None, the phase
    result is byte-identical to a plain run (review F3's no-op default), and NO evidence block
    reaches any phase prompt."""
    spec = load_spec(SPEC)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    prompts = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        prompts.append(prompt)
        (Path(workdir) / "app.py").write_text("def f():\n    return 1\n")
        return _fake_agent(files_created=["app.py"])

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    assert result.phases[0].commit_hash
    assert result.phases[0].change_analysis is None
    assert all(p.change_analysis is None for p in result.phases)
    assert all("EVIDENCE" not in p for p in prompts)  # prompts byte-identical without injection


def test_run_workflow_change_analysis_full_sha_and_next_phase_evidence(tmp_path, monkeypatch):
    """cap_2a p1 (design §5.7): the ChangeInput revisions are FULL commit SHAs (provenance,
    the short hash stays display-only), and the NEXT phase's prompt receives a bounded,
    machine-readable evidence context (graph status, full revision, neighborhood, facts)."""
    import re

    from agentic_dynamics.runtime.change_analyzer import ChangeAnalysis

    monkeypatch.setattr(
        workflow_runner,
        "_sonar_evidence",
        lambda *a, **k: {
            "status": "unavailable",
            "revision_matches": None,
            "new_critical_count": None,
            "analyzed_sha": "",
        },
    )
    monkeypatch.setattr(
        workflow_runner,
        "_lsp_evidence",
        lambda *a, **k: {"status": "unavailable", "new_error_count": None, "tool": "mypy"},
    )

    class RecordingAnalyzer:
        def __init__(self):
            self.changes = []

        def analyze(self, change):
            self.changes.append(change)
            return ChangeAnalysis(
                facts=(
                    {
                        "predicate": "changed_symbol_count",
                        "value": "1",
                        "value_type": "int",
                        "evidence_ids": (),
                    },
                ),
                neighborhood=("f",),
                graph_status="available",
                revision=change.revision,
            )

    spec = load_spec(SPEC)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    prompts = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        prompts.append(prompt)
        n = len(prompts)
        (Path(workdir) / "app.py").write_text(f"def f{n}():\n    return {n}\n")
        return _fake_agent(files_created=["app.py"])

    analyzer = RecordingAnalyzer()
    result = run_workflow(
        spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent, change_analyzer=analyzer
    )

    # The FIRST phase's commit is the root commit (no parent to diff) -> not analyzed; the
    # SECOND committed phase is analyzed with FULL-SHA revisions.
    assert result.phases[0].change_analysis is None
    assert len(analyzer.changes) >= 1
    change = analyzer.changes[0]
    assert re.fullmatch(r"[0-9a-f]{40}", change.revision) is not None  # full SHA, not short
    assert change.after.revision == change.revision
    assert re.fullmatch(r"[0-9a-f]{40}", change.before.revision) is not None  # parent full SHA
    # The displayed commit_hash stays the SHORT form.
    assert re.fullmatch(r"[0-9a-f]{7,}", result.phases[1].commit_hash) is not None
    assert len(result.phases[1].commit_hash) < len(change.revision)

    # The NEXT agent phase's prompt (implement, after ux_design was analyzed) carries the
    # bounded evidence block with graph status, revision, neighborhood, and facts.
    evidence_prompts = [p for p in prompts if "EVIDENCE" in p]
    assert evidence_prompts, "the next-phase prompt must receive the evidence context"
    line = next(
        ln for ln in evidence_prompts[0].splitlines() if ln.strip().startswith("- EVIDENCE")
    )
    payload = json.loads(line.split("EVIDENCE ", 1)[1])
    assert payload["graph_status"] == "available"
    assert payload["revision"] == change.revision
    assert payload["neighborhood"] == ["f"]
    assert payload["facts"][0]["predicate"] == "changed_symbol_count"
    assert payload["phase"] == "ux_design"  # the analyzed phase whose evidence rode forward


def test_run_workflow_change_analysis_root_commit_never_fails(tmp_path):
    """A phase whose commit has NO parent (root commit in the worktree) cannot be diffed —
    the seam degrades to None instead of failing the phase.

    The sonar/lsp external legs are scoped off (``change_analysis_legs=False`` — the
    test_suite_speed p2 seam): the root-commit degradation the test proves lives in the
    snapshots/delta/analyzer core, which still runs; the real sonar-scanner subprocess
    windows (the p1 profile's 113-135s) are orthogonal to this assertion and covered by
    ``test_sonar_evidence_*``/``test_lsp_evidence_*``. A weakened assertion would be a
    violation; this is a scoped invocation, the proof is unchanged."""
    from agentic_dynamics.runtime.change_analyzer import ChangeAnalysis

    class Analyzer:
        def analyze(self, change):
            return ChangeAnalysis()

    spec = load_spec(SPEC)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    # Commit the FIRST phase's change directly (no parent), then let the runner commit a
    # second phase whose analysis targets commit^ — the runner's own first commit is root.
    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        n = len(calls)
        calls.append(n)
        (Path(workdir) / "app.py").write_text(f"def f{n}():\n    return {n}\n")
        return _fake_agent(files_created=["app.py"])

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        run_agentic_fn=agent,
        change_analyzer=Analyzer(),
        change_analysis_legs=False,
    )
    assert result.ok
    # Root-commit phases degrade gracefully (change_analysis may be None), never a failure.
    assert all(p.status == "ok" for p in result.phases)


def test_run_workflow_excludes_instrument_from_commit(tmp_path):
    """The runner's own ``.instrument/`` transcripts never enter history (item 5.1)."""
    spec = load_spec(SPEC)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / ".instrument").mkdir(exist_ok=True)
        (Path(workdir) / ".instrument" / "session.jsonl").write_text("transcript")
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "scope.md").write_text("---\nstatus: accepted\n---\n\nscope")
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    assert result.phases[0].commit_hash
    tracked = subprocess.run(["git", "ls-files"], cwd=tmp_path, capture_output=True, text=True)
    assert ".instrument" not in tracked.stdout
    assert "docs/scope.md" in tracked.stdout


def test_run_workflow_excludes_fleet_transport_from_commit(tmp_path):
    """The prepared-step transport (``.fleet/``) never enters history.

    The 2026-09-19 leak: the engine's post-phase ``git add -A`` committed
    ``.fleet/prepared_steps/<phase>.aN.json`` into the candidate (two such files already sit
    on main from earlier merges). The commit pathspec excludes it explicitly, mirroring
    ``.instrument/``.
    """
    spec = load_spec(SPEC)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / ".fleet" / "prepared_steps").mkdir(parents=True, exist_ok=True)
        (Path(workdir) / ".fleet" / "prepared_steps" / "p1.a1.json").write_text("{}")
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "scope.md").write_text("---\nstatus: accepted\n---\n\nscope")
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    assert result.phases[0].commit_hash
    tracked = subprocess.run(["git", "ls-files"], cwd=tmp_path, capture_output=True, text=True)
    assert ".fleet" not in tracked.stdout
    assert "docs/scope.md" in tracked.stdout


def test_run_workflow_resume_skips_committed_phases(tmp_path):
    spec = load_spec(SPEC)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        calls.append(prompt.splitlines()[1])
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "x.md").write_text(str(len(calls)))  # unique → commits
        return _fake_agent(ok=len(calls) < 3, error="boom")

    run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    # implement (3rd agent call) failed → only scope + ux committed

    calls.clear()

    def agent2(prompt, *, model, backend, workdir, **kwargs):
        calls.append(prompt.splitlines()[1])
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "x.md").write_text(str(len(calls)))
        return _fake_agent()

    result = run_workflow(
        spec, goal="g", model="m", workdir=tmp_path, resume=True, run_agentic_fn=agent2
    )
    assert [p.phase for p in result.phases] == ["implement", "verify"]
    assert len(calls) == 1  # only implement re-runs; scope/ux skipped


# ── Wave F7: the selected parent's snapshot IS the resume input ──


def test_resume_state_is_the_completion_input_without_git_or_index(tmp_path, monkeypatch):
    """An explicit ResumeState skips exactly its completed_phases: no ``[workflow]`` commit
    is required in the worktree and the spec index is never consulted. The provenance is
    stamped onto the result ledger."""
    consulted = []
    monkeypatch.setattr(spec_status, "index_entry", lambda name, **kw: consulted.append(name))
    executed = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        executed.append(prompt.splitlines()[1])
        return _fake_agent()

    spec = load_spec(SPEC)
    state = ResumeState(
        parent_run_id="run-parent",
        ledger_path="/ledgers/20260912T000000Z_run-parent.json",
        completed_phases=frozenset({"scope", "ux_design"}),
    )
    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        resume_state=state,
        run_agentic_fn=agent,
    )

    assert [p.phase for p in result.phases] == ["implement", "verify"]
    assert len(executed) == 1  # only implement re-runs; the parent's ok phases are skipped
    assert consulted == []  # the spec-index fallback was never reached
    assert result.resumed_from_run_id == "run-parent"
    assert result.resumed_from_ledger == state.ledger_path
    assert result.to_dict()["resumed_from_run_id"] == "run-parent"
    assert result.to_dict()["resumed_from_ledger"] == state.ledger_path


def test_resume_state_overrides_git_history_completion(tmp_path):
    """The explicit parent snapshot wins over the worktree's git log: a phase committed
    here but NOT ok in the selected parent re-runs. Correct family linkage alone must not
    let goal-prefix history decide what the parent completed."""
    spec = load_spec(SPEC)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        calls.append(prompt.splitlines()[1])
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "x.md").write_text(str(len(calls)))
        return _fake_agent()

    # First run commits scope + ux_design + implement, so the worktree's git log would let
    # the INFERENCE path skip all three.
    run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    calls.clear()

    # The selected parent completed ONLY scope; ux_design's commit here must not skip it.
    state = ResumeState(
        parent_run_id="run-parent",
        ledger_path="/ledgers/run-parent.json",
        completed_phases=frozenset({"scope"}),
    )
    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        resume_state=state,
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )

    assert [p.phase for p in result.phases] == ["ux_design", "implement", "verify"]
    assert result.resumed_from_run_id == "run-parent"


# ── RAG augmentation seam ───────────────────────────────────────


class _FakeEvidence:
    def __init__(self, cid, text, authority="source"):
        self.id = cid
        self.text = text
        self.authority = authority
        self.content_hash = f"ch:{cid}"
        self.token_count = len(text.split())

    def citation(self):
        return f"[K:{self.id}@abc:loc]"


class _FakeAttempt:
    def __init__(self, evidence, fallback_mode="full"):
        self.selected_evidence = evidence
        self.fallback_mode = fallback_mode
        self.retrieval_attempt_id = "ra:test"


class _FakeAugmented:
    def __init__(self, prompt):
        self.prompt = prompt
        self.fallback = False
        self.evidence_ids = ["k1"]
        self.versions = {"schema": "prompt-plan/v1"}
        self.token_counts = {"in": 10}
        self.cost_usd = 0.0
        self.constructor_attempt_id = "ca:test"


def test_explicit_no_rag_is_byte_identical(tmp_path):
    """The rollback path (2026-09-24): ``rag_augment=False`` — the previously implicit
    default, now the explicit opt-out — is byte-for-byte identical to a plain run."""
    spec = load_spec(SPEC)
    prompts = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        prompts.append(prompt)
        return _fake_agent()

    run_workflow(
        spec,
        goal="the goal",
        model="m",
        workdir=tmp_path,
        commit=False,
        run_agentic_fn=agent,
        rag_augment=False,
    )

    prior = []
    expected = []
    for p in spec.workflow.params["phases"]:
        if p.get("kind", "agent") == "agent":
            expected.append(_build_phase_prompt(p, "the goal", prior))
        prior.append(f"{p['name']} (ok)")
    assert prompts == expected


def test_rag_default_is_on(tmp_path, monkeypatch):
    """2026-09-24 (the controller's on-by-default directive): with NO spec flag and NO
    injection, the seam resolves ON — retrieve -> construct -> render actually run. A store
    that is absent degrades to a NAMED fallback, never a silent skip; here the stubbed
    constructor raising proves the fallback absorbs failure while the seam itself ran."""
    import agentic_dynamics.runtime.workflow_runner as wr

    spec = load_spec(SPEC)
    calls: list[str] = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        return _fake_agent()

    def fake_retrieve_fn():
        calls.append("retrieve_fn")

        def _retrieve(**kwargs):
            calls.append("retrieve")
            return _FakeAttempt([_FakeEvidence("k1", "cached evidence")])

        return _retrieve

    def fake_construct_fn(rag_params, run_agent):
        calls.append("construct_fn")

        def _construct(request):
            calls.append("construct")
            raise RuntimeError("stub constructor — the fallback must absorb this")

        return _construct

    monkeypatch.setattr(wr, "default_retrieve_fn", fake_retrieve_fn)
    monkeypatch.setattr(wr, "default_construct_fn", fake_construct_fn)

    run_workflow(
        spec, goal="the goal", model="m", workdir=tmp_path, commit=False, run_agentic_fn=agent
    )

    # The seam ran WITHOUT any flag or injection — the default resolved ON.
    assert "retrieve_fn" in calls and "retrieve" in calls
    assert "construct_fn" in calls and "construct" in calls


def test_rag_hook_ordering_between_route_and_agent(tmp_path):
    spec = load_spec(SPEC)
    order = []

    def retrieve_fn(**kwargs):
        order.append("retrieve")
        return _FakeAttempt([_FakeEvidence("k1", "cached evidence")])

    def construct_fn(request):
        order.append("construct")
        return _FakeAugmented("AUGMENTED: " + request.raw_work_item)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        order.append("agent")
        return _fake_agent()

    run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        rag_augment=True,
        retrieve_fn=retrieve_fn,
        construct_fn=construct_fn,
        run_agentic_fn=agent,
    )

    # scope, ux_design, implement are agent phases (retrieve -> construct -> agent);
    # verify is a test phase and is bypassed entirely.
    assert order == ["retrieve", "construct", "agent"] * 3


def test_rag_bypasses_test_phases(tmp_path):
    spec = load_spec(SPEC)
    retrieve_calls = []

    def retrieve_fn(**kwargs):
        retrieve_calls.append(kwargs["raw_work_item"])
        return _FakeAttempt([_FakeEvidence("k1", "x")])

    def construct_fn(request):
        return _FakeAugmented("AUG")

    run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        rag_augment=True,
        retrieve_fn=retrieve_fn,
        construct_fn=construct_fn,
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )

    assert len(retrieve_calls) == 3  # verify (kind == test) is never augmented


def test_rag_prompt_is_augmented_and_provenance_serialized(tmp_path):
    spec = load_spec(SPEC)
    captured = []

    def retrieve_fn(**kwargs):
        return _FakeAttempt([_FakeEvidence("k1", "cached evidence")])

    def construct_fn(request):
        return _FakeAugmented("AUGMENTED: " + request.raw_work_item)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        captured.append(prompt)
        return _fake_agent()

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        rag_augment=True,
        retrieve_fn=retrieve_fn,
        construct_fn=construct_fn,
        run_agentic_fn=agent,
    )

    assert captured[0].startswith("AUGMENTED: ")
    d = result.phases[0].to_dict()
    assert d["raw_prompt_hash"]
    assert d["retrieval_attempt_id"] == "ra:test"
    assert d["constructor_attempt_id"] == "ca:test"
    assert d["selected_evidence_ids"] == ["k1"]
    assert d["fallback_mode"] == "full"
    assert "pre_phase_commit" in d
    assert "augmentation_versions" in d
    assert "augmentation_tokens" in d
    assert "augmentation_cost_usd" in d
    assert "augmentation_latency_ms" in d


def test_rag_fallback_on_retrieve_failure(tmp_path):
    spec = load_spec(SPEC)
    captured = []

    def retrieve_fn(**kwargs):
        raise RuntimeError("chroma down")

    def construct_fn(request):
        raise AssertionError("must not be called")

    def agent(prompt, *, model, backend, workdir, **kwargs):
        captured.append(prompt)
        return _fake_agent()

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        rag_augment=True,
        retrieve_fn=retrieve_fn,
        construct_fn=construct_fn,
        run_agentic_fn=agent,
    )

    assert result.phases[0].fallback_mode == "no_rag"
    assert result.phases[0].status == "ok"  # never blocked the phase
    expected = _build_phase_prompt(spec.workflow.params["phases"][0], "g", [])
    assert captured[0] == expected


def test_rag_fallback_on_construct_failure(tmp_path):
    spec = load_spec(SPEC)

    def retrieve_fn(**kwargs):
        return _FakeAttempt([_FakeEvidence("k1", "x")])

    def construct_fn(request):
        raise RuntimeError("constructor model down")

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        rag_augment=True,
        retrieve_fn=retrieve_fn,
        construct_fn=construct_fn,
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )

    assert result.phases[0].fallback_mode == "no_rag"
    assert result.phases[0].status == "ok"


def test_default_retrieve_fn_binds_dense_and_graph_stores(monkeypatch):
    """The default retrieval builds ONE Neo4j client and binds both legs to it.

    2026-09-19 (review: perf): the dense store receives the SAME client the lexical leg
    uses — one client per factory call, one connection pool; the vector store does not mint
    its own.
    """
    import agentic_dynamics.knowledge.graph as graph
    import agentic_dynamics.knowledge.neo4j_vectors as vectors

    constructed: dict = {"neo4j_calls": []}

    class _FakeNeo4j:
        def __init__(self, **kwargs):
            constructed["neo4j_calls"].append(kwargs)

    class _FakeVector:
        def __init__(self, client=None, **kwargs):
            constructed["vector_client"] = client

    monkeypatch.setattr(graph, "Neo4jClient", _FakeNeo4j)
    monkeypatch.setattr(vectors, "Neo4jVectorStore", _FakeVector)

    fn = default_retrieve_fn()

    assert isinstance(fn.keywords["dense_store"], _FakeVector)
    assert isinstance(fn.keywords["graph_client"], _FakeNeo4j)
    assert len(constructed["neo4j_calls"]) == 1, "one client for both legs"
    assert constructed["vector_client"] is fn.keywords["graph_client"]


def test_default_retrieve_fn_degrades_to_no_rag_when_stores_down(tmp_path, monkeypatch):
    """A store that cannot connect degrades to ``no_rag`` without raising.

    Both store classes are swapped for fakes that construct fine but raise at query
    time (a lazy driver whose infra is down). ``retrieve``'s per-leg try/except marks
    each leg down, so the phase falls back to the base prompt and stays ``ok``.
    """
    import agentic_dynamics.knowledge.embeddings as embeddings
    import agentic_dynamics.knowledge.graph as graph

    class _DownChroma:
        def __init__(self, **kwargs):
            pass

        def search(self, *args, **kwargs):
            raise RuntimeError("chroma unreachable")

    class _DownNeo4j:
        def __init__(self, **kwargs):
            pass

        def search_knowledge_fulltext(self, *args, **kwargs):
            raise RuntimeError("neo4j unreachable")

    monkeypatch.setattr(embeddings, "ChromaStore", _DownChroma)
    monkeypatch.setattr(graph, "Neo4jClient", _DownNeo4j)

    spec = load_spec(SPEC)

    def construct_fn(request):
        return _FakeAugmented("AUGMENTED: " + request.raw_work_item)

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        rag_augment=True,
        construct_fn=construct_fn,
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )

    assert result.phases[0].fallback_mode == "no_rag"
    assert result.phases[0].status == "ok"


# ── Per-cell retrieval scope threading ──────────────────────────


def test_cell_scope_uses_worktree_basename(tmp_path, monkeypatch):
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)
    assert cell_scope(tmp_path) == f"self-{tmp_path.name}"


def test_cell_scope_overridden_by_finops_cell_id(tmp_path, monkeypatch):
    monkeypatch.setenv("FINOPS_CELL_ID", "wf_override")
    assert cell_scope(tmp_path) == "self-wf_override"


def test_rag_empty_repository_id_defaults_to_cell_scope(tmp_path, monkeypatch):
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)
    spec = load_spec(SPEC)
    captured = {}

    def retrieve_fn(**kwargs):
        captured["repository_id"] = kwargs.get("repository_id")
        captured["acl_scope"] = kwargs.get("acl_scope")
        return _FakeAttempt([_FakeEvidence("k1", "x")])

    run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        rag_augment=True,
        retrieve_fn=retrieve_fn,
        construct_fn=lambda request: _FakeAugmented("AUG"),
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )

    # The empty scope resolves to the per-cell scope, not the global store.
    expected = f"self-{tmp_path.name}"
    assert captured["repository_id"] == expected
    assert captured["acl_scope"] == expected


def test_rag_explicit_repository_id_is_preserved(tmp_path, monkeypatch):
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)
    spec = load_spec(SPEC)
    captured = {}

    def retrieve_fn(**kwargs):
        captured["repository_id"] = kwargs.get("repository_id")
        captured["acl_scope"] = kwargs.get("acl_scope")
        return _FakeAttempt([_FakeEvidence("k1", "x")])

    run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        rag_augment=True,
        rag_params={"repository_id": "shared-scope"},
        retrieve_fn=retrieve_fn,
        construct_fn=lambda request: _FakeAugmented("AUG"),
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )

    # The shared-scope override is preserved unchanged — never overwritten by the
    # per-cell default.
    assert captured["repository_id"] == "shared-scope"


def test_retrieve_construct_render_path_never_writes():
    """The augmentation seam is read-only; the sole KB writer is the emit_self path.

    ``retrieve -> construct -> render`` must reference ``publish_event`` ZERO times — the
    seam reads (dense + lexical retrieval) and constructs (one flash-model call), but it can
    never write the knowledge plane. The only write is the self-build producer
    (``emit_phase_finding``), reached exclusively through ``_emit_self_finding`` (gated by
    ``_finding_emit_enabled`` — default ON since kb_finding_layer k1).
    """
    import inspect

    import agentic_dynamics.knowledge.augment as augment
    import agentic_dynamics.knowledge.prompt_constructor as pc
    import agentic_dynamics.knowledge.retrieval as retrieval_mod
    from agentic_dynamics.runtime import workflow_runner as wr

    # The two read-side modules never reference publish_event.
    for mod in (retrieval_mod, pc):
        assert "publish_event" not in inspect.getsource(mod)

    # The seam's retrieve/construct/render functions never reference publish_event either.
    for fn in (augment.augment_prompt, augment.default_retrieve_fn, augment.default_construct_fn):
        assert "publish_event" not in inspect.getsource(fn)

    # The write is funneled through emit_phase_finding (not publish_event) and lives only in
    # the emit_self helper — so an augmented phase can never write except through emit_self.
    assert "emit_phase_finding" in inspect.getsource(wr._emit_self_finding)
    assert "publish_event" not in inspect.getsource(wr._emit_self_finding)


# ── finding emit: default ON (kb_finding_layer k1) ─────────────


def _git_init(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)


def _emit_synth_spec(phase_defs: list[dict]) -> ExperimentSpec:
    """A minimal agent_task spec whose agent phases write a file, so each one commits."""
    return ExperimentSpec(
        name="k1_emit_synth",
        question="q",
        version="1",
        workflow=Workflow(
            kind="agent_task",
            params={"language": "python", "phases": phase_defs},
        ),
        factors=[Factor("model", ["m"])],
        design="factorial",
    )


def _agent_writes_marker(counter: list) -> Callable:
    """A fake agent that rewrites ``work.txt`` per call so every phase commits."""

    def agent(prompt, *, model, backend, workdir, **kwargs):
        counter.append(prompt)
        (Path(workdir) / "work.txt").write_text(str(len(counter)))
        return _fake_agent()

    return agent


class _CloneCommitExecutor:
    """A containerized-cell stub: writes + commits in the run clone, never the host worktree."""

    def __init__(self, clone: Path) -> None:
        self.clone = Path(clone)

    def execute(self, request):  # noqa: ANN001 — the StepRequest surface is not under test
        (self.clone / "deliverable.txt").write_text("delivered\n")
        subprocess.run(["git", "add", "-A"], cwd=self.clone, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", f"[workflow] {request.phase_name} — g"],
            cwd=self.clone,
            check=True,
            capture_output=True,
        )
        return _fake_agent()


def test_run_clone_bookkeeping_reads_the_run_clone(tmp_path, monkeypatch):
    """The containerized regression (run-c931259949ee p4_verify): a phase commits INTO the
    run's private clone while the host worktree is only its source. The post-phase gates
    (NO_CHANGES), the runner's commit, and the ledger candidate sha must read the CLONE —
    before the fix, ``_git_head(workdir)`` read "" and every ``requires_deliverable`` phase
    failed NO_CHANGES even when the cell delivered.
    """
    wt = tmp_path / "wt"
    wt.mkdir()
    _git_init(wt)
    (wt / "base.txt").write_text("base\n")
    subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=wt, check=True)

    clone = tmp_path / "runs" / "run-x" / "repo"
    clone.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(wt), str(clone)], check=True)
    for key, value in (("user.email", "t@t"), ("user.name", "t")):
        subprocess.run(["git", "config", key, value], cwd=clone, check=True)

    monkeypatch.setenv("FINOPS_RUN_CLONE", str(clone))
    monkeypatch.setattr(workflow_runner, "_emit_self_finding", lambda pr, *, goal, scope: None)

    spec = _emit_synth_spec(
        [{"name": "p1", "kind": "agent", "prompt": "do p1", "requires_deliverable": True}]
    )
    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=wt,
        step_executor=_CloneCommitExecutor(clone),
    )
    ph = result.phases[0]
    clone_head = subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"], cwd=clone, text=True
    ).strip()
    assert ph.status == "ok", ph.error
    assert ph.commit_gate is None
    assert ph.commit_hash == clone_head
    assert result.git_sha == clone_head
    # The worktree itself was never touched by the phase.
    assert not (wt / "deliverable.txt").exists()


def test_finding_emit_defaults_on_for_committed_phases(tmp_path, monkeypatch):
    """(k1 a) DEFAULT settings emit a finding per committed phase — no opt-in flag.

    With ``FINOPS_EMIT_SELF`` unset (the production default), no ``rag_params.emit_self``, and
    no phase marker, every successful committed phase fires the emit path. The write seam is
    stubbed to a recorder so the assertion targets the GATE (the default-on flip), not the
    live KB.
    """
    _git_init(tmp_path)
    monkeypatch.delenv("FINOPS_EMIT_SELF", raising=False)
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)
    spec = _emit_synth_spec(
        [
            {"name": "p1", "kind": "agent", "prompt": "do p1"},
            {"name": "p2", "kind": "agent", "prompt": "do p2"},
        ]
    )
    emitted: list[tuple] = []

    def _recorder(pr, *, goal, scope):
        emitted.append((pr.phase, pr.status, pr.commit_hash, scope))

    monkeypatch.setattr(workflow_runner, "_emit_self_finding", _recorder)

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        run_agentic_fn=_agent_writes_marker([]),
    )
    assert [p.phase for p in result.phases] == ["p1", "p2"]
    assert all(p.status == "ok" and p.commit_hash for p in result.phases)
    # One finding per committed phase, scoped to the cell — without any opt-in flag.
    assert [(e[0], e[1]) for e in emitted] == [("p1", "ok"), ("p2", "ok")]
    assert all(e[2] for e in emitted)
    assert all(e[3] == f"self-{tmp_path.name}" for e in emitted)


def test_finding_emit_no_emit_marker_suppresses_phase(tmp_path, monkeypatch):
    """(k1 c) a phase with the explicit no-emit marker does not emit — but still commits."""
    _git_init(tmp_path)
    monkeypatch.delenv("FINOPS_EMIT_SELF", raising=False)
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)
    spec = _emit_synth_spec(
        [
            {"name": "p1", "kind": "agent", "prompt": "do p1", "no_emit": True},
            {"name": "p2", "kind": "agent", "prompt": "do p2"},
        ]
    )
    emitted: list[str] = []
    monkeypatch.setattr(
        workflow_runner,
        "_emit_self_finding",
        lambda pr, *, goal, scope: emitted.append(pr.phase),
    )

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        run_agentic_fn=_agent_writes_marker([]),
    )
    assert [p.phase for p in result.phases] == ["p1", "p2"]
    # p1 still committed (the marker suppresses only the finding, never the commit).
    assert all(p.commit_hash for p in result.phases)
    assert emitted == ["p2"]


def test_finding_emit_explicit_true_outranks_env_disarm(tmp_path, monkeypatch):
    """(k1 e) the emit_self flag still works when set: True re-enables under the env disarm."""
    _git_init(tmp_path)
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)
    # conftest sets FINOPS_EMIT_SELF=0; an explicit rag_params.emit_self=True must win.
    spec = _emit_synth_spec([{"name": "p1", "kind": "agent", "prompt": "do p1"}])
    emitted: list[str] = []
    monkeypatch.setattr(
        workflow_runner,
        "_emit_self_finding",
        lambda pr, *, goal, scope: emitted.append(pr.phase),
    )
    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        run_agentic_fn=_agent_writes_marker([]),
        rag_params={"emit_self": True},
    )
    assert result.phases[0].status == "ok" and result.phases[0].commit_hash
    assert emitted == ["p1"]


def test_finding_emit_explicit_false_outranks_default_on(tmp_path, monkeypatch):
    """(k1 e) the emit_self flag still works when set: False opts a run out of the default."""
    _git_init(tmp_path)
    monkeypatch.delenv("FINOPS_EMIT_SELF", raising=False)
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)
    spec = _emit_synth_spec([{"name": "p1", "kind": "agent", "prompt": "do p1"}])
    emitted: list[str] = []
    monkeypatch.setattr(
        workflow_runner,
        "_emit_self_finding",
        lambda pr, *, goal, scope: emitted.append(pr.phase),
    )
    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        run_agentic_fn=_agent_writes_marker([]),
        rag_params={"emit_self": False},
    )
    assert result.phases[0].status == "ok" and result.phases[0].commit_hash
    assert emitted == []


def test_finding_emit_fires_when_agent_self_commits(tmp_path, monkeypatch):
    """(k6 witness gap) a phase whose agent commits its OWN conforming work still emits.

    ``_git_commit`` stages + commits the phase's uncommitted work and returns its short sha,
    but a phase whose agent ALREADY committed (the orchestration norm this wave runs under —
    every k0-k5 phase committed its own work) leaves a tree clean of staged changes, so
    ``_git_commit`` returns ``""`` and the k1 default-on gate (``and pr.commit_hash``) never
    fires — the finding silently never lands for exactly the phases the runner produces. The
    commit block now adopts the phase's own HEAD when the tree is clean and the HEAD advanced
    past the pre-phase baseline, so the self-committed phase's finding still emits.
    """
    _git_init(tmp_path)
    monkeypatch.delenv("FINOPS_EMIT_SELF", raising=False)
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)
    spec = _emit_synth_spec([{"name": "p1", "kind": "agent", "prompt": "do p1"}])

    def _agent_self_commits(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "work.txt").write_text("agent's own committed work")
        subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "[workflow] p1 — g"],
            cwd=workdir,
            check=True,
        )
        return _fake_agent()

    emitted: list[tuple] = []
    monkeypatch.setattr(
        workflow_runner,
        "_emit_self_finding",
        lambda pr, *, goal, scope: emitted.append((pr.phase, pr.commit_hash, scope)),
    )

    result = run_workflow(
        spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=_agent_self_commits
    )
    phase = result.phases[0]
    assert phase.status == "ok"
    # The agent's own commit was ADOPTED as the phase commit — not left "" (the pre-fix gap).
    assert phase.commit_hash
    assert emitted == [("p1", phase.commit_hash, f"self-{tmp_path.name}")]


def test_finding_emit_default_run_writes_enriched_records(tmp_path, monkeypatch):
    """(k1 a+b) a DEFAULT run emits one enriched finding per committed phase, end to end.

    The full self-build chain (``run_workflow`` -> ``_emit_self_finding`` ->
    ``emit_phase_finding`` -> durable artifact) is exercised with the KB seam pointed at tmp
    (PROJECT_ROOT) and the stream publish captured, so the assertion covers the default-on
    gate AND the enriched finding text without touching the live KB.
    """
    import agentic_dynamics.knowledge.knowledge_ingestion as ki
    import agentic_dynamics.knowledge.knowledge_stream as ks

    _git_init(tmp_path)
    monkeypatch.delenv("FINOPS_EMIT_SELF", raising=False)
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)
    spec = _emit_synth_spec(
        [
            {"name": "p1", "kind": "agent", "prompt": "do p1"},
            {"name": "p2", "kind": "agent", "prompt": "do p2"},
        ]
    )
    monkeypatch.setattr(ki, "PROJECT_ROOT", tmp_path)
    published: list = []
    monkeypatch.setattr(ks, "connect", lambda: object())
    monkeypatch.setattr(ks, "publish_event", lambda r, e, **kw: published.append(e) or "0-1")

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        run_agentic_fn=_agent_writes_marker([]),
    )
    assert [p.phase for p in result.phases] == ["p1", "p2"]
    assert all(p.status == "ok" and p.commit_hash for p in result.phases)

    # One durable artifact per committed phase, published to the (stubbed) stream.
    artifact_paths = sorted((tmp_path / "experiments" / "results" / "kb").glob("*.json"))
    assert len(artifact_paths) == 2
    assert len(published) == 2

    records = [json.loads(p.read_text()) for p in artifact_paths]
    by_phase = {
        "p1": next(r for r in records if r["text"].startswith("g phase p1 ->")),
        "p2": next(r for r in records if r["text"].startswith("g phase p2 ->")),
    }
    for phase in ("p1", "p2"):
        rec = by_phase[phase]
        # The canonical head is preserved and the k1 tail rides after it: status + commit.
        # No independent test suite ran in this synthetic run, so the verdict stays None ->
        # ADVISORY (never MEASURED) and no tests split is fabricated.
        assert rec["text"].startswith(f"g phase {phase} -> test_executed_success None")
        assert "status ok" in rec["text"]
        assert "commit " in rec["text"]
        assert "tests " not in rec["text"]
        assert rec["authority"] == "ADVISORY"
        assert rec["evidence_class"] == "[H]"
        assert rec["source_type"] == "finding"


# ── spec_id on the ledger records ───────────────────────────────


def test_ledger_records_carry_spec_id(tmp_path):
    """``spec_id`` is a declared LEDGER_FIELD; job *and* attempt records must emit it.

    Without it a run ledger identifies only the spec *name*, so two runs across a version
    bump are indistinguishable in the ledger.
    """
    spec = load_spec(SPEC)
    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )

    expected = f"{spec.name}@{spec.version}"
    assert result.spec_id == expected  # job record
    assert all(p.spec_id == expected for p in result.phases)  # attempt records

    serialized = result.to_dict()
    assert serialized["spec_id"] == expected
    assert all(ph["spec_id"] == expected for ph in serialized["phases"])


def test_result_to_dict_carries_the_split_run_family_link():
    """The engine result is the ledger's serialization source; g1's family link (stamped by the
    CLI composition root after run_workflow returns) must survive to_dict so spec_status can
    read it off the ledger. Pre-g1 results (all three fields empty) serialize unchanged."""
    from agentic_dynamics.runtime.workflow_runner import WorkflowRunResult

    plain = WorkflowRunResult(spec_name="g1", model="m", workdir="/tmp/x", goal="g")
    payload = plain.to_dict()
    assert payload["run_id"] == ""
    assert payload["parent_run_id"] == ""
    assert payload["family_id"] == ""

    child = WorkflowRunResult(spec_name="g1", model="m", workdir="/tmp/x", goal="g")
    # The CLI stamps these after the engine returns (Debt-2: the engine never knows the
    # control-plane id); to_dict must then carry them into the ledger.
    child.run_id = "run-child"
    child.parent_run_id = "run-parent"
    child.family_id = "run-parent"
    payload = child.to_dict()
    assert payload["run_id"] == "run-child"
    assert payload["parent_run_id"] == "run-parent"
    assert payload["family_id"] == "run-parent"


# ── --resume: git log first, the derived index as the fallback ──


def _index_ledger(tmp_path: Path, goal: str, phases: list[dict]) -> SpecStatusEntry:
    """Write a fixture run ledger under ``tmp_path`` and return an entry pointing at it."""
    rel = "experiments/results/workflows/control_room_portal/20260819T000000Z.json"
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"spec_name": "control_room_portal", "goal": goal, "phases": phases})
    )
    return SpecStatusEntry(
        name="control_room_portal",
        version="0.2",
        status="runnable",
        spec_path="workflows/repository/control_room_portal.yaml",
        last_run_at="2026-08-19T00:00:00+00:00",
        results_pointer=rel,
        n_runs=1,
    )


def test_resume_falls_back_to_the_index_without_workflow_commits(tmp_path, monkeypatch):
    # tmp_path is not a git repo, so the git-log path finds nothing — exactly the case
    # the index fallback exists for.
    entry = _index_ledger(
        tmp_path,
        "g",
        [
            {"phase": "scope", "status": "ok"},
            {"phase": "ux_design", "status": "ok"},
            {"phase": "implement", "status": "failed"},
        ],
    )
    monkeypatch.setattr(workflow_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(spec_status, "index_entry", lambda name, **kw: entry)

    spec = load_spec(SPEC)
    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        resume=True,
        commit=False,
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )
    # scope/ux_design were ok in the ledger and are skipped; the failed implement re-runs.
    assert [p.phase for p in result.phases] == ["implement", "verify"]


def test_index_fallback_is_not_consulted_when_commits_exist(tmp_path, monkeypatch):
    """The git-log path stays primary — the pre-existing behaviour must not regress."""
    consulted = []
    monkeypatch.setattr(spec_status, "index_entry", lambda name, **kw: consulted.append(name))
    spec = load_spec(SPEC)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)

    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        calls.append(prompt)
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "x.md").write_text(str(len(calls)))
        return _fake_agent(ok=len(calls) < 2, error="boom")

    run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        resume=True,
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )
    assert [p.phase for p in result.phases][0] == "ux_design"  # scope skipped via git log
    assert consulted == []  # ... and the index untouched


def test_index_fallback_requires_a_matching_goal(tmp_path, monkeypatch):
    # Phase names collide across workflows (scope/verify), so a ledger written for a
    # different goal must not let a resume skip work that was never done for this one.
    entry = _index_ledger(
        tmp_path, "a completely different goal", [{"phase": "scope", "status": "ok"}]
    )
    monkeypatch.setattr(workflow_runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(spec_status, "index_entry", lambda name, **kw: entry)

    spec = load_spec(SPEC)
    phase_names = [p["name"] for p in spec.workflow.params["phases"]]
    assert _completed_phases_from_index(spec, phase_names, "g") == set()


def test_index_fallback_degrades_to_empty_on_any_failure(tmp_path, monkeypatch):
    """No index, a dangling results_pointer, or a raising lookup all mean "start over"."""
    spec = load_spec(SPEC)
    phase_names = [p["name"] for p in spec.workflow.params["phases"]]
    monkeypatch.setattr(workflow_runner, "PROJECT_ROOT", tmp_path)

    monkeypatch.setattr(spec_status, "index_entry", lambda name, **kw: None)
    assert _completed_phases_from_index(spec, phase_names, "g") == set()

    dangling = SpecStatusEntry(
        name="control_room_portal",
        version="0.2",
        status="runnable",
        spec_path="x.yaml",
        results_pointer="does/not/exist.json",
    )
    monkeypatch.setattr(spec_status, "index_entry", lambda name, **kw: dangling)
    assert _completed_phases_from_index(spec, phase_names, "g") == set()

    def boom(name, **kw):
        raise RuntimeError("index exploded")

    monkeypatch.setattr(spec_status, "index_entry", boom)
    assert _completed_phases_from_index(spec, phase_names, "g") == set()


# ── v2 analyzer legs: severity filter + novelty + deadline (cap_2a rerun2 p1) ──


def _avail_metrics():
    from agentic_dynamics.measurement.sonar import SONAR_STATUS_AVAILABLE, SonarMetrics

    return SonarMetrics(
        project_key="exp_wt", analyzed=True, status=SONAR_STATUS_AVAILABLE, analyzed_sha="c" * 40
    )


def _issue(rule, severity, file_path, line):
    from agentic_dynamics.measurement.sonar import SonarIssue

    return SonarIssue(rule=rule, severity=severity, file_path=file_path, line=line)


def test_call_with_deadline_returns_false_on_timeout():
    """(c) A non-returning analyzer leg is bounded by the client-side deadline — it degrades to
    ``(False, None)`` instead of hanging the phase."""
    import time

    from agentic_dynamics.runtime import workflow_runner as wr

    def slow():
        time.sleep(1.0)
        return "never"

    returned, result = wr._call_with_deadline(slow, timeout=0.05)
    assert returned is False
    assert result is None


def test_sonar_evidence_no_parent_checkout_is_unavailable(tmp_path):
    """A failed parent materialization degrades the sonar leg to its measured unavailable
    status (count omitted — null-not-zero, never a fabricated 0)."""
    from agentic_dynamics.runtime import workflow_runner as wr

    payload = wr._sonar_evidence(tmp_path, None, "0" * 40, "1" * 40)
    assert payload["status"] == "unavailable"
    assert payload["new_critical_count"] is None


def test_sonar_evidence_novelty_introduced_blocker_counts_one(monkeypatch, tmp_path):
    """(b) Novelty rule: a change-introduced BLOCKER (present only in the after-analysis) counts
    exactly 1, and the leg requests the server-side BLOCKER,CRITICAL severity filter."""
    from agentic_dynamics.runtime import workflow_runner as wr

    monkeypatch.setattr(wr, "run_sonar_analysis", lambda *a, **k: _avail_metrics())
    seen = {}

    def fake_fetch(key, severities="", ps=500):
        seen["severities"] = severities
        if key.endswith("0" * 12):  # the parent revision: no criticals
            return []
        return [_issue("python:S1000", "BLOCKER", "calc.py", 10)]

    monkeypatch.setattr(wr, "fetch_sonar_issues", fake_fetch)
    payload = wr._sonar_evidence(tmp_path, tmp_path, "0" * 40, "1" * 40)
    assert payload["status"] == "available"
    assert payload["new_critical_count"] == 1
    assert seen["severities"] == "BLOCKER,CRITICAL"


def test_sonar_evidence_preexisting_blocker_counts_zero(monkeypatch, tmp_path):
    """(b) Novelty rule: a pre-existing BLOCKER (same identity in BOTH revisions, untouched by
    the change) counts 0."""
    from agentic_dynamics.runtime import workflow_runner as wr

    monkeypatch.setattr(wr, "run_sonar_analysis", lambda *a, **k: _avail_metrics())
    blocker = _issue("python:S1000", "BLOCKER", "calc.py", 5)
    monkeypatch.setattr(wr, "fetch_sonar_issues", lambda key, severities="", ps=500: [blocker])

    payload = wr._sonar_evidence(tmp_path, tmp_path, "0" * 40, "1" * 40)
    assert payload["status"] == "available"
    assert payload["new_critical_count"] == 0


def test_lsp_evidence_novelty_introduced_error_counts_one(monkeypatch, tmp_path):
    """The LSP leg counts only change-introduced ERROR diagnostics by (file, line, code)."""
    from agentic_dynamics.measurement.lsp_diagnostics import LSPDiagnostic, LSPReport
    from agentic_dynamics.runtime import workflow_runner as wr

    calls = []

    def fake_diag(path, profile, tool_name=None):
        n = len(calls)
        calls.append(path)
        if n == 0:  # parent revision: clean
            return LSPReport(tool="mypy", language="python", available=True)
        return LSPReport(
            tool="mypy",
            language="python",
            available=True,
            diagnostics=[LSPDiagnostic("error", "bad", "calc.py", 10, 5, "return-value")],
        )

    monkeypatch.setattr(wr, "run_diagnostics", fake_diag)
    payload = wr._lsp_evidence(tmp_path, tmp_path, "0" * 40, "1" * 40, None)
    assert payload["status"] == "available"
    assert payload["new_error_count"] == 1
    assert payload["tool"] == "mypy"


# ── Phase watchdog (cap_runner_hardening p1) ─────────────────────


def _watchdog_transcript(workdir):
    return Path(workdir) / ".instrument" / "session.jsonl"


def _watchdog_stalled_agent(killed, release):
    """A fake agent that writes one step, registers a SIGTERM-recording kill, then goes quiet.

    The watchdog must SIGTERM it (recording the kill) and fail the phase with STALLED while
    the agent itself keeps waiting until the kill releases it.
    """

    def agent(prompt, *, model, backend, workdir, watchdog=None, **kwargs):
        transcript = _watchdog_transcript(workdir)
        transcript.parent.mkdir(parents=True, exist_ok=True)
        watchdog["kill"] = lambda: (killed.append("SIGTERM"), release.set())
        with transcript.open("a") as fh:
            fh.write(json.dumps({"type": "step_start"}) + "\n")
        release.wait(timeout=5)  # no further steps — the transcript goes stale past the threshold
        return _fake_agent()

    return agent


def test_watchdog_sigterms_a_stalled_agent_and_fails_the_phase(tmp_path):
    """(a) A fake agent that stops writing steps for > threshold is SIGTERM'd and the phase
    fails with STALLED + evidence (last-step timestamp, stale age, transcript tail), and the
    evidence rides the phase's ledger record."""
    spec = load_spec(SPEC)
    killed: list[str] = []
    release = threading.Event()

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        phase_watchdog_min=0.03,  # 1.8s — the test's whole runtime budget
        run_agentic_fn=_watchdog_stalled_agent(killed, release),
    )
    p = result.phases[0]
    assert p.status == "failed"
    assert p.stall_evidence is not None
    assert p.stall_evidence["reason"] == "STALLED"
    assert p.stall_evidence["stale_age_s"] >= p.stall_evidence["threshold_min"] * 60
    assert p.stall_evidence["last_step_at"]
    assert "step_start" in p.stall_evidence["transcript_tail"]
    assert "STALLED" in p.error
    assert killed == ["SIGTERM"]  # the watchdog actually killed the agent
    assert result.ok is False

    # The ledger carries the evidence, not just the error string.
    ledger = result.to_dict()["phases"][0]
    assert ledger["stall_evidence"]["reason"] == "STALLED"
    assert ledger["status"] == "failed"


def test_watchdog_never_kills_a_compliant_agent(tmp_path):
    """(b) A fake agent that keeps stepping — even slowly — is never killed; the phase stays ok."""
    spec = load_spec(SPEC)
    killed: list[str] = []
    release = threading.Event()

    def agent(prompt, *, model, backend, workdir, watchdog=None, **kwargs):
        transcript = _watchdog_transcript(workdir)
        transcript.parent.mkdir(parents=True, exist_ok=True)
        watchdog["kill"] = lambda: (killed.append("SIGTERM"), release.set())
        for i in range(4):
            with transcript.open("a") as fh:
                fh.write(json.dumps({"type": "step_start", "n": i}) + "\n")
            release.wait(timeout=0.15)  # continuous slow steps: max gap 0.15s < 1.8s threshold
        return _fake_agent()

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        phase_watchdog_min=0.03,
        run_agentic_fn=agent,
    )
    assert result.phases[0].status == "ok"
    assert result.phases[0].stall_evidence is None
    assert killed == []


def test_watchdog_threshold_env_override(tmp_path, monkeypatch):
    """(c) FINOPS_PHASE_WATCHDOG_MIN overrides the default threshold; the stall fires under it."""
    monkeypatch.setenv("FINOPS_PHASE_WATCHDOG_MIN", "0.03")
    spec = load_spec(SPEC)
    killed: list[str] = []
    release = threading.Event()

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,  # no explicit arg → env wins
        run_agentic_fn=_watchdog_stalled_agent(killed, release),
    )
    assert result.phases[0].status == "failed"
    assert result.phases[0].stall_evidence["reason"] == "STALLED"
    assert result.phases[0].stall_evidence["threshold_min"] == 0.03


def _watchdog_child_db(root: Path, *, updated_ms: int) -> Path:
    """A minimal opencode-shaped SQLite store: one message row (a child session's work)."""
    import sqlite3

    db = root / "opencode" / "opencode.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.execute(
        "create table message (id text, session_id text, time_created integer, "
        "time_updated integer, data text)"
    )
    con.execute(
        "create table part (id text, message_id text, session_id text, time_created integer, "
        "time_updated integer, data text)"
    )
    con.execute(
        "insert into message values ('m1', 'ses_child', ?, ?, '{}')", (updated_ms, updated_ms)
    )
    con.commit()
    con.close()
    return db


def test_watchdog_child_session_activity_keeps_a_delegating_phase_alive(tmp_path):
    """(d) The 2026-09-22 false positive: the top-level transcript is stale for an hour while
    a delegated child session's message was updated seconds ago. With an explicit activity
    store the child's update advances the stall clock — the phase is ALIVE, not STALLED."""
    db = _watchdog_child_db(tmp_path, updated_ms=int(time.time() * 1000))
    watchdog = PhaseWatchdog(tmp_path, 0.05, activity_db=db)  # 3s threshold
    watchdog._last_activity = time.time() - 3600  # the transcript clock is cold
    assert watchdog.check_stall() is None  # the child row advanced the clock


def test_watchdog_stale_child_rows_still_stall(tmp_path):
    """(e) The probe is not a blanket exemption: a child store whose newest row is ALSO stale
    (a genuinely hung tree) fires STALLED exactly like the transcript clock."""
    db = _watchdog_child_db(tmp_path, updated_ms=int((time.time() - 3600) * 1000))
    watchdog = PhaseWatchdog(tmp_path, 0.05, activity_db=db)
    watchdog._last_activity = time.time() - 3600
    evidence = watchdog.check_stall()
    assert evidence is not None
    assert evidence["reason"] == "STALLED"


def test_watchdog_activity_probe_is_scoped_to_the_cell_namespace(tmp_path, monkeypatch):
    """(f) The probe is scoped: disabled without an explicit XDG_DATA_HOME (an in-process run
    against the operator's shared store must never be kept alive by an unrelated session),
    resolved to the cell's own store when the namespace is explicit."""
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert PhaseWatchdog(tmp_path, 20).activity_db is None

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "state"))
    resolved = PhaseWatchdog(tmp_path, 20).activity_db
    assert resolved == tmp_path / "state" / "opencode" / "opencode.db"


def test_watchdog_explicit_arg_overrides_env(tmp_path, monkeypatch):
    """The CLI/arg threshold outranks the env: a huge explicit value means no stall even with a
    hostile small env value, and the kill never fires."""
    monkeypatch.setenv("FINOPS_PHASE_WATCHDOG_MIN", "0.03")  # would stall under the env alone
    spec = load_spec(SPEC)
    killed: list[str] = []
    release = threading.Event()

    def agent(prompt, *, model, backend, workdir, watchdog=None, **kwargs):
        transcript = _watchdog_transcript(workdir)
        transcript.parent.mkdir(parents=True, exist_ok=True)
        watchdog["kill"] = lambda: (killed.append("SIGTERM"), release.set())
        with transcript.open("a") as fh:
            fh.write("step\n")
        release.wait(timeout=0.5)  # short — the explicit 60-min threshold never fires here
        return _fake_agent()

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        phase_watchdog_min=60.0,
        run_agentic_fn=agent,
    )
    assert result.phases[0].status == "ok"
    assert result.phases[0].stall_evidence is None
    assert killed == []


def test_watchdog_default_threshold_does_not_fire_for_a_quick_agent(tmp_path, monkeypatch):
    """The default (20 min) watchdog is inert for a normal quick agent — no stall, no overhead
    observable in the outcome."""
    monkeypatch.delenv("FINOPS_PHASE_WATCHDOG_MIN", raising=False)
    spec = load_spec(SPEC)
    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )
    assert result.ok
    assert all(p.stall_evidence is None for p in result.phases)


def test_watchdog_zero_disables_it(tmp_path, monkeypatch):
    """A threshold <= 0 turns the watchdog off — the phase is byte-identical to pre-hardening
    (no seam, no kill path, no stall possible)."""
    monkeypatch.setenv("FINOPS_PHASE_WATCHDOG_MIN", "0.03")
    spec = load_spec(SPEC)
    seen = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        seen.append(kwargs)
        time.sleep(0.6)  # a stall-prone agent — but the watchdog is disabled, so no seam/kill
        return _fake_agent()

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        phase_watchdog_min=0,
        run_agentic_fn=agent,
    )
    assert result.phases[0].status == "ok"
    assert all("watchdog" not in kw for kw in seen)  # no seam threaded to the agent


def test_watchdog_only_wraps_agent_phases(tmp_path):
    """The watchdog wraps the agent process only — test phases run in-process (run_suite) and
    are never given a watchdog seam or a kill path."""
    spec = load_spec(SPEC)
    watchdogs = []

    def agent(prompt, *, model, backend, workdir, watchdog=None, **kwargs):
        watchdogs.append(watchdog)
        return _fake_agent()

    result = run_workflow(
        spec, goal="g", model="m", workdir=tmp_path, commit=False, run_agentic_fn=agent
    )
    # scope/ux_design/implement are agent phases → seam present; verify (kind=test) never calls agent.
    assert len(watchdogs) == 3
    assert all(w is not None for w in watchdogs)
    assert result.phases[-1].kind == "test"
    assert result.phases[-1].stall_evidence is None


# ── Deploy gate (cap_runner_hardening p2) ───────────────────────

#: Faithful reconstruction of the revamp2 p3 session's deploy event (the bash tool_use whose
#: input deployed BOTH production hosts). The command is the one that silently overwrote the
#: site twice — the replay proof the gate must catch.
REVAMP2_DEPLOY_LINE = json.dumps(
    {
        "type": "tool_use",
        "timestamp": 1787783173755,
        "sessionID": "ses_fbfd53722ffeHBFPqC3B3fC6Se",
        "part": {
            "type": "tool",
            "tool": "bash",
            "callID": "call_revamp2_p3",
            "state": {
                "status": "completed",
                "input": {
                    "command": "firebase deploy --only hosting && firebase deploy --only hosting --project agentic-dynamics",
                    "workdir": "/tmp/wt_site_revamp2/apps/website",
                    "timeout": 120000,
                },
                "output": "=== Deploying to 'ai-finops-rulebook'...\n\u2714 Deploy complete!\n"
                "=== Deploying to 'agentic-dynamics'...\n\u2714 Deploy complete!\n",
            },
        },
    }
)


def _deploy_agent(transcript_line, *, deploy_in_all=False):
    """A fake agent that writes ``transcript_line`` into the phase's session transcript, then
    succeeds. Models the real adapter's per-phase end-write: each phase REPLACES the transcript
    (``write_text``), so a later clean phase never inherits an earlier phase's deploy line."""
    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        n = len(calls)
        calls.append(n)
        transcript = _watchdog_transcript(workdir)
        transcript.parent.mkdir(parents=True, exist_ok=True)
        if deploy_in_all or n == 0:
            transcript.write_text(transcript_line + "\n")
        else:
            transcript.write_text('{"type": "step_start"}\n')
        return _fake_agent()

    return agent


def test_deploy_gate_fails_a_non_deploy_phase_with_evidence(tmp_path):
    """(a) A fake agent session containing 'firebase deploy' in a non-deploy phase fails with
    DEPLOY_GATE + the quoted offending command, and the evidence rides the phase's ledger record."""
    spec = load_spec(SPEC)
    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        run_agentic_fn=_deploy_agent(REVAMP2_DEPLOY_LINE),
    )
    p = result.phases[0]
    assert p.status == "failed"
    assert p.deploy_gate is not None
    assert p.deploy_gate["reason"] == "DEPLOY_GATE"
    assert any("firebase deploy" in v["command"] for v in p.deploy_gate["violations"])
    assert any("--project agentic-dynamics" in v["command"] for v in p.deploy_gate["violations"])
    assert p.deploy_gate["violations"][0]["line"].startswith("{")
    assert "DEPLOY_GATE" in p.error
    assert "'firebase deploy --only hosting" in p.error  # the offending command is quoted
    assert result.ok is False
    assert result.to_dict()["phases"][0]["deploy_gate"]["reason"] == "DEPLOY_GATE"


def test_deploy_gate_passes_a_deploy_allowed_phase(tmp_path):
    """(b) The same deploy command in a phase marked ``deploy_allowed: true`` passes — the gate
    is about the marker, never a naming rule; later clean phases stay clean (per-phase transcript)."""
    spec = load_spec(SPEC)
    spec.workflow.params["phases"][0]["deploy_allowed"] = True  # scope may deploy
    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        run_agentic_fn=_deploy_agent(REVAMP2_DEPLOY_LINE),
    )
    assert result.ok
    assert result.phases[0].status == "ok"
    assert result.phases[0].deploy_gate is None
    assert all(p.deploy_gate is None for p in result.phases)


def test_deploy_gate_not_triggered_by_clean_phases_or_test_phases(tmp_path):
    """A clean agent phase (no deploy command) and the test phase never trip the gate; a bash
    command that merely mentions firebase in text (not a deploy) is not a violation."""
    spec = load_spec(SPEC)
    clean_line = json.dumps(
        {
            "type": "tool_use",
            "sessionID": "s",
            "part": {
                "type": "tool",
                "tool": "bash",
                "state": {"input": {"command": "python scripts/build_data.py"}},
            },
        }
    )

    def agent(prompt, *, model, backend, workdir, **kwargs):
        _watchdog_transcript(workdir).parent.mkdir(parents=True, exist_ok=True)
        _watchdog_transcript(workdir).write_text(clean_line + "\n")
        return _fake_agent()

    result = run_workflow(
        spec, goal="g", model="m", workdir=tmp_path, commit=False, run_agentic_fn=agent
    )
    assert result.ok
    assert all(p.deploy_gate is None for p in result.phases)
    assert result.phases[-1].kind == "test"
    assert result.phases[-1].deploy_gate is None


def test_deploy_allowed_marker_is_type_checked(tmp_path):
    """(c) The validator type-checks the marker: a non-boolean (the typo that would silently
    disable the gate) is refused; a real boolean validates; specs without the marker (the whole
    committed corpus) validate unchanged."""
    spec = load_spec(SPEC)
    assert validate_spec(spec) == []  # the existing spec has no marker — still valid

    spec.workflow.params["phases"][0]["deploy_allowed"] = "true"  # string typo
    errors = validate_spec(spec)
    assert any("deploy_allowed must be a boolean" in e for e in errors)

    spec.workflow.params["phases"][0]["deploy_allowed"] = 1  # int typo
    errors = validate_spec(spec)
    assert any("deploy_allowed must be a boolean" in e for e in errors)

    spec.workflow.params["phases"][0]["deploy_allowed"] = True  # honest marker
    assert validate_spec(spec) == []


def test_deploy_gate_replay_revamp2_p3_session(tmp_path):
    """(d) Replay proof: the revamp2 p3 deploy command (the one that overwrote production) is
    caught by the gate — against the embedded transcript event AND, when the real worktree still
    exists on disk, against the actual /tmp/wt_site_revamp2 session transcript."""
    from agentic_dynamics.runtime import workflow_runner as wr

    # (1) the embedded reconstruction of the exact production-affecting command
    spec = load_spec(SPEC)
    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        run_agentic_fn=_deploy_agent(REVAMP2_DEPLOY_LINE),
    )
    p = result.phases[0]
    assert p.status == "failed"
    assert p.deploy_gate["reason"] == "DEPLOY_GATE"
    assert p.deploy_gate["violations"][0]["command"] == (
        "firebase deploy --only hosting && firebase deploy --only hosting --project agentic-dynamics"
    )
    assert p.deploy_gate["violations"][0]["pattern"] == "firebase deploy"

    # (2) against the real revamp2 session transcript when it is still on disk — the gate would
    # have fired on the exact line the evidence measured
    real = Path("/tmp/wt_site_revamp2/.instrument/session.jsonl")
    if real.exists():
        hits = wr._scan_transcript_for_deploys(real)
        assert any("firebase deploy" in h["command"] for h in hits), (
            "the real revamp2 p3 session must be caught by the deploy gate"
        )


# ── Commit-prefix enforcement (cap_runner_hardening p3) ──────────

#: The revamp2 branch's 7 plain-message commits (feature/site-revamp2, between the phase's
#: own [workflow] commit and the pre-phase spec commit) — the exact commits that broke the
#: resume machinery and forced the re-tagging surgery. The replay proof the validator must
#: reject.
REVAMP2_GOAL = "Deliver the site's IMPLEMENTED visual system"
REVAMP2_PLAIN_COMMITS = [
    "research: cap_site_revamp editorial audit",
    "site: add editorial visual system",
    "site: rewrite public research narrative",
    "site: wire campaign evidence to data",
    "site: harden evidence publication",
    "data: refresh site publication receipt",
    "docs: record site deploy verification",
]


def _git_init(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)


def _commit_file(workdir, subject, n):
    """Write a distinct file, commit it with ``subject``, return the full commit sha."""
    (Path(workdir) / "docs").mkdir(exist_ok=True)
    (Path(workdir) / "docs" / f"f{n}.md").write_text(f"---\nstatus: accepted\n---\n\n{subject} {n}")
    subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", subject], cwd=workdir, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=workdir, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_commit_prefix_canonicalizes_a_plain_message_commit(tmp_path):
    """(a) A fake agent that commits a plain message: the default CANONICALIZE mode installs
    the commit-msg hook, which prefixes the message to the canonical pattern AT COMMIT TIME
    (the work preserved) — the phase CONTINUES ok and the message on disk is canonical, so
    resume reliability is preserved. The gate itself never sees a violation (the hook is the
    first line of defense)."""
    spec = load_spec(SPEC)
    _git_init(tmp_path)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "scope.md").write_text("---\nstatus: accepted\n---\n\nscope")
        subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "site: add things"], cwd=workdir, check=True)
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    p = result.phases[0]
    assert p.status == "ok"  # the hook fixed it at commit time — no failure
    assert p.commit_gate is None
    # the message on disk IS canonical now — resume will match it
    subjects = subprocess.run(
        ["git", "log", "--format=%s"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.splitlines()
    assert subjects[0] == "[workflow] scope — g"


def test_commit_prefix_gate_rewrites_a_plain_message_commit_with_hook_disabled(
    tmp_path, monkeypatch
):
    """(a2) With FINOPS_COMMIT_HOOK=0 (no commit-time hook) AND the explicit opt-in
    FINOPS_COMMIT_GATE=canonicalize, the gate's own rewrite path fires for a plain-message
    commit: the proper history rewrite prefixes the subject, the phase CONTINUES, and
    COMMIT_PREFIX_CANONICALIZED records the original subject + the rewritten sha — the work
    preserved (the tree hash is unchanged). P0-4: canonicalize is no longer the default."""
    monkeypatch.setenv("FINOPS_COMMIT_HOOK", "0")
    monkeypatch.setenv("FINOPS_COMMIT_GATE", "canonicalize")
    spec = load_spec(SPEC)
    _git_init(tmp_path)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "scope.md").write_text("---\nstatus: accepted\n---\n\nscope")
        subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "site: add things"], cwd=workdir, check=True)
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    p = result.phases[0]
    assert p.status == "ok"  # canonicalized, not failed
    assert p.commit_gate is not None
    assert p.commit_gate["reason"] == "COMMIT_PREFIX_CANONICALIZED"
    assert p.commit_gate["original_subjects"] == ["site: add things"]
    assert p.commit_gate["expected_prefix"] == "[workflow] scope — g"
    assert p.commit_gate["rewritten_sha"]
    subjects = subprocess.run(
        ["git", "log", "--format=%s"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.splitlines()
    assert subjects[0] == "[workflow] scope — g"


def test_commit_msg_hook_prefixes_plain_commits_at_commit_time(tmp_path):
    """The commit-msg hook itself: a non-conforming subject is rewritten to the canonical
    pattern at commit time; a conforming subject and the adapter's 'Initial' commit pass
    through untouched. This is the drawing-board fix — the agent CANNOT produce a violating
    commit."""
    from agentic_dynamics.runtime import workflow_runner as wr

    _git_init(tmp_path)
    wr._install_commit_msg_hook(tmp_path, "scope", "g")
    hook = tmp_path / ".git" / "hooks" / "commit-msg"
    assert hook.exists()
    assert hook.stat().st_mode & 0o111  # executable

    def commit(subject):
        (tmp_path / "f").write_text(subject)
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-q", "-m", subject], cwd=tmp_path, check=True)

    commit("Initial")  # the adapter's init commit — must pass through
    commit("site: add things")  # plain message — must be prefixed
    commit("[workflow] scope — g done")  # conforming — must pass through

    subjects = subprocess.run(
        ["git", "log", "--format=%s"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.splitlines()
    assert subjects == ["[workflow] scope — g done", "[workflow] scope — g", "Initial"]


def test_commit_msg_hook_installs_into_a_clone_without_a_hooks_directory(tmp_path):
    """The fleet's run clones carry no .git/hooks/ directory; the installer must CREATE it.

    Regression (2026-09-18 delivery demo, run-75e8319533fb): write_text into the missing
    directory raised FileNotFoundError, swallowed by the best-effort except — the hook never
    installed, and the strict gate then failed a plain-message commit at the finish line.
    A delivery run must not die on a missing directory.
    """
    from agentic_dynamics.runtime import workflow_runner as wr

    _git_init(tmp_path)
    shutil.rmtree(tmp_path / ".git" / "hooks", ignore_errors=True)
    assert not (tmp_path / ".git" / "hooks").exists(), "this test pins the hooks-less shape"
    wr._install_commit_msg_hook(tmp_path, "generate", "implement taskman")
    hook = tmp_path / ".git" / "hooks" / "commit-msg"
    assert hook.exists(), "the installer must create the hooks directory it writes into"
    assert hook.stat().st_mode & 0o111

    (tmp_path / "f").write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "plain message"], cwd=tmp_path, check=True)
    subject = subprocess.run(
        ["git", "log", "-1", "--format=%s"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    assert subject == "[workflow] generate — implement taskman"


def test_commit_prefix_strict_mode_fails_a_plain_message_commit(tmp_path, monkeypatch):
    """FINOPS_COMMIT_GATE=strict restores the fail-with-evidence mode: a plain-message
    commit fails the phase with COMMIT_PREFIX + the subject as evidence."""
    monkeypatch.setenv("FINOPS_COMMIT_GATE", "strict")
    spec = load_spec(SPEC)
    _git_init(tmp_path)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "scope.md").write_text("---\nstatus: accepted\n---\n\nscope")
        subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "site: add things"], cwd=workdir, check=True)
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    p = result.phases[0]
    assert p.status == "failed"
    assert p.commit_gate is not None
    assert p.commit_gate["reason"] == "COMMIT_PREFIX"
    assert p.commit_gate["subjects"] == ["site: add things"]
    assert p.commit_gate["expected_prefix"] == "[workflow] scope — g"
    assert "COMMIT_PREFIX" in p.error
    assert "site: add things" in p.error
    assert result.ok is False
    assert result.to_dict()["phases"][0]["commit_gate"]["reason"] == "COMMIT_PREFIX"


def test_commit_prefix_strict_is_the_default_no_rewrite(tmp_path, monkeypatch):
    """P0-4 (control-plane stabilization): strict is now the DEFAULT commit-gate mode — the
    ordinary autonomous path never rewrites history. A plain-message commit fails the phase
    with evidence; no FINOPS_COMMIT_GATE is set, so the historical canonicalize path (which
    changed SHAs after evidence referenced them) does NOT fire. Message normalization
    belongs to the promoter, not the executor."""
    monkeypatch.setenv("FINOPS_COMMIT_HOOK", "0")  # force the gate path (no commit-time hook)
    monkeypatch.delenv("FINOPS_COMMIT_GATE", raising=False)
    spec = load_spec(SPEC)
    _git_init(tmp_path)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "scope.md").write_text("---\nstatus: accepted\n---\n\nscope")
        subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "site: add things"], cwd=workdir, check=True)
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    p = result.phases[0]
    assert p.status == "failed"  # strict-by-default: fails with evidence, no rewrite
    assert p.commit_gate["reason"] == "COMMIT_PREFIX"
    # the bad subject is UNCHANGED on disk — no history was rewritten
    subjects = subprocess.run(
        ["git", "log", "--format=%s"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.splitlines()
    assert "site: add things" in subjects


def test_commit_prefix_passes_a_matching_commit(tmp_path):
    """(b) A fake agent whose only commit matches '[workflow] <phase> — <goal prefix>' passes
    (the enforcement only fires on the violation)."""
    spec = load_spec(SPEC)
    _git_init(tmp_path)
    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        n = len(calls)
        calls.append(n)
        if n == 0:  # only the scope phase commits — with the correct pattern
            (Path(workdir) / "docs").mkdir(exist_ok=True)
            (Path(workdir) / "docs" / "scope.md").write_text("---\nstatus: accepted\n---\n\nscope")
            subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "[workflow] scope — g done"], cwd=workdir, check=True
            )
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    assert result.ok
    assert result.phases[0].status == "ok"
    assert result.phases[0].commit_gate is None
    assert all(p.commit_gate is None for p in result.phases)


def test_commit_prefix_fires_even_when_the_phase_already_failed(tmp_path, monkeypatch):
    """The enforcement runs regardless of ok/fail (strict mode): a phase that failed for
    another reason but also made a plain commit carries BOTH reasons."""
    monkeypatch.setenv("FINOPS_COMMIT_GATE", "strict")
    spec = load_spec(SPEC)
    _git_init(tmp_path)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "scope.md").write_text("---\nstatus: accepted\n---\n\nscope")
        subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "site: add things"], cwd=workdir, check=True)
        return _fake_agent(ok=False, error="boom")

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    p = result.phases[0]
    assert p.status == "failed"
    assert "boom" in p.error  # the agent's own failure stays visible
    assert "COMMIT_PREFIX" in p.error  # ... and the commit violation is appended
    assert p.commit_gate and p.commit_gate["reason"] == "COMMIT_PREFIX"


def test_commit_prefix_rejects_a_different_phases_name(tmp_path):
    """A commit using ANOTHER phase's name (the resume-spoofing shape) does not count for this
    phase, and the goal prefix is enforced strictly."""
    from agentic_dynamics.runtime import workflow_runner as wr

    assert wr._commit_subject_matches("[workflow] ux_design — g", "scope", "g") is False
    assert wr._commit_subject_matches("[workflow] scope — g", "scope", "g") is True
    assert wr._commit_subject_matches("[workflow] scope — different goal", "scope", "g") is False
    assert wr._commit_subject_matches("site: add things", "scope", "g") is False


def test_commit_prefix_replay_rejects_revamp2_plain_commits(tmp_path, monkeypatch):
    monkeypatch.setenv("FINOPS_COMMIT_GATE", "strict")
    """(c) Replay proof: the revamp2 branch's 7 plain commits would each have failed the phase
    (COMMIT_PREFIX) — the validator rejects every one, accepts the phase's own [workflow]
    commit, and an end-to-end phase that made those 7 commits fails with them as evidence."""
    from agentic_dynamics.runtime import workflow_runner as wr

    goal_prefix = REVAMP2_GOAL[:40]

    # (1) the validator rejects all 7 plain commits ...
    for subject in REVAMP2_PLAIN_COMMITS:
        assert (
            wr._commit_subject_matches(subject, "p1_implement_inventory", goal_prefix) is False
        ), subject
    # ... and accepts the phase's own workflow commit (the runner's _git_commit shape)
    ok = f"[workflow] p1_implement_inventory — {REVAMP2_GOAL}:"
    assert wr._commit_subject_matches(ok, "p1_implement_inventory", goal_prefix) is True

    # (2) end-to-end: an agent that made those 7 commits during the phase fails COMMIT_PREFIX
    spec = load_spec(SPEC)
    _git_init(tmp_path)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        for i, subject in enumerate(REVAMP2_PLAIN_COMMITS):
            (Path(workdir) / "docs" / f"f{i}.md").write_text(subject)
            subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
            subprocess.run(["git", "commit", "-q", "-m", subject], cwd=workdir, check=True)
        return _fake_agent()

    result = run_workflow(
        spec, goal=REVAMP2_GOAL, model="m", workdir=tmp_path, run_agentic_fn=agent
    )
    p = result.phases[0]
    assert p.status == "failed"
    assert p.commit_gate and p.commit_gate["reason"] == "COMMIT_PREFIX"
    # git log returns newest-first — compare the subject set, not the order
    assert set(p.commit_gate["subjects"]) == set(REVAMP2_PLAIN_COMMITS)
    assert p.commit_gate["expected_prefix"] == f"[workflow] scope — {REVAMP2_GOAL[:40]}"
    assert not p.commit_hash  # the bad commit is never propagated by the commit gate
    assert result.ok is False


def test_commit_prefix_exempts_the_adapters_initial_commit(tmp_path, monkeypatch):
    monkeypatch.setenv("FINOPS_COMMIT_GATE", "strict")
    """The runner's own execution-layer commits are exempt: the adapter's fresh-worktree
    ``Initial`` commit (subject ``Initial`` + the runner's init author) never trips the gate,
    while a plain-message commit under the SAME forged identity still does — the enforcement
    targets MANUAL agent commits (the p4 integration fix the live smoke found)."""
    from agentic_dynamics.runtime import workflow_runner as wr

    spec = load_spec(SPEC)
    _git_init(tmp_path)

    # the worktree starts EMPTY of commits; the fake simulates the adapter's _init_git_workdir
    # creating its "Initial" commit DURING the phase under the runner's init identity
    def agent(prompt, *, model, backend, workdir, **kwargs):
        subprocess.run(
            ["git", "config", "user.email", wr.RUNNER_INIT_AUTHOR_EMAIL], cwd=workdir, check=True
        )
        subprocess.run(["git", "config", "user.name", "Experiment Runner"], cwd=workdir, check=True)
        (Path(workdir) / "seed.txt").write_text("seed")
        subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "Initial"], cwd=workdir, check=True)
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    assert result.phases[0].status == "ok"
    assert result.phases[0].commit_gate is None

    # same forged identity, but a plain-message commit — NOT exempt (subject != "Initial")
    def agent_bad(prompt, *, model, backend, workdir, **kwargs):
        subprocess.run(
            ["git", "config", "user.email", wr.RUNNER_INIT_AUTHOR_EMAIL], cwd=workdir, check=True
        )
        subprocess.run(["git", "config", "user.name", "Experiment Runner"], cwd=workdir, check=True)
        (Path(workdir) / "seed2.txt").write_text("changed")  # a NEW change → a real commit
        subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "site: add things"], cwd=workdir, check=True)
        return _fake_agent()

    spec2 = load_spec(SPEC)
    result2 = run_workflow(spec2, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent_bad)
    assert result2.phases[0].status == "failed"
    assert result2.phases[0].commit_gate["reason"] == "COMMIT_PREFIX"
    assert result2.phases[0].commit_gate["subjects"] == ["site: add things"]


# ── P0 fix: commit-prefix canonicalization is safe only for a single offender at HEAD ──


def test_commit_prefix_seven_commit_range_with_violations_is_rewritten_in_canonicalize_mode(
    tmp_path, monkeypatch
):
    """(Drawing-board fix) A seven-commit phase range with violations at the beginning,
    middle, and end IS self-healed in canonicalize mode: the gate rewrites EVERY offender's
    subject via the proper history rewrite (git filter-branch over the exact range — the
    P0 single-amend rule refused this shape because amend rewrites HEAD alone). The phase
    CONTINUES, every subject conforms on re-read, and the final TREE hash is unchanged (only
    messages changed — the deliverable tree is preserved). FINOPS_COMMIT_HOOK=0 forces the
    gate path (with the hook, commit-time prevention would fix the subjects before the gate
    ever sees them). P0-4: canonicalize is an explicit opt-in now, not the default."""
    monkeypatch.setenv("FINOPS_COMMIT_HOOK", "0")
    monkeypatch.setenv("FINOPS_COMMIT_GATE", "canonicalize")
    spec = load_spec(SPEC)
    _git_init(tmp_path)
    subjects = [
        "beginning bad",  # violation — the FIRST commit of the range
        "[workflow] scope — g",  # conforming
        "[workflow] scope — g",  # conforming
        "middle bad",  # violation — in the middle
        "[workflow] scope — g",  # conforming
        "[workflow] scope — g",  # conforming
        "end bad",  # violation — at HEAD
    ]
    made = []
    calls: list[int] = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        n = len(calls)
        calls.append(n)
        if n == 0:  # only the first phase makes the seven commits
            for i, subject in enumerate(subjects):
                made.append((_commit_file(workdir, subject, i), subject))
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    p = result.phases[0]
    assert p.status == "ok"  # rewritten, not failed
    assert p.commit_gate is not None
    assert p.commit_gate["reason"] == "COMMIT_PREFIX_CANONICALIZED"
    bad_subjects = ["beginning bad", "middle bad", "end bad"]
    assert set(p.commit_gate["original_subjects"]) == set(bad_subjects)
    assert p.commit_gate["expected_prefix"] == "[workflow] scope — g"
    assert p.commit_gate["rewritten_sha"]
    # every subject conforms on re-read — the range is fully canonical
    log = subprocess.run(
        ["git", "log", "--format=%H|%s"], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    got = [line.split("|", 1)[1] for line in log]
    assert got == ["[workflow] scope — g"] * 7
    assert result.ok


def test_commit_prefix_seven_commit_range_with_violations_fails_strict_in_strict_mode(
    tmp_path, monkeypatch
):
    """(P0) Same seven-commit range under FINOPS_COMMIT_GATE=strict: the strict mode never
    amends anything, so the run fails with COMMIT_PREFIX + the same full evidence."""
    monkeypatch.setenv("FINOPS_COMMIT_GATE", "strict")
    spec = load_spec(SPEC)
    _git_init(tmp_path)
    subjects = [
        "beginning bad",
        "[workflow] scope — g",
        "[workflow] scope — g",
        "middle bad",
        "[workflow] scope — g",
        "[workflow] scope — g",
        "end bad",
    ]
    made = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        for i, subject in enumerate(subjects):
            made.append((_commit_file(workdir, subject, i), subject))
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    p = result.phases[0]
    assert p.status == "failed"
    assert p.commit_gate["reason"] == "COMMIT_PREFIX"
    bad_subjects = ["beginning bad", "middle bad", "end bad"]
    assert set(p.commit_gate["subjects"]) == set(bad_subjects)
    offenders = {o["sha"]: o["subject"] for o in p.commit_gate["offenders"]}
    assert set(offenders) == {sha for sha, s in made if s in bad_subjects}
    log = subprocess.run(
        ["git", "log", "--format=%H|%s"], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    assert [line.split("|", 1)[1] for line in log] == list(reversed(subjects))
    assert [line.split("|", 1)[0] for line in log] == [sha for sha, _ in reversed(made)]
    assert result.ok is False


def test_commit_prefix_rewrites_a_single_bad_commit_with_hook_disabled(tmp_path, monkeypatch):
    """(Drawing-board fix, positive) With the commit-time hook disabled, a SINGLE bad commit
    is canonicalized by the gate's rewrite path: the offender's subject becomes canonical,
    the gate records COMMIT_PREFIX_CANONICALIZED with the original subject + the rewritten
    sha, the phase CONTINUES, and the TREE is preserved (only the message changed —
    content-addressed proof). P0-4: canonicalize is an explicit opt-in, not the default."""
    monkeypatch.setenv("FINOPS_COMMIT_HOOK", "0")
    monkeypatch.setenv("FINOPS_COMMIT_GATE", "canonicalize")
    spec = load_spec(SPEC)
    _git_init(tmp_path)
    made = []
    calls: list[int] = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        n = len(calls)
        calls.append(n)
        if n == 0:  # scope — the single bad commit
            made.append((_commit_file(workdir, "site: add things", 0), "site: add things"))
        else:  # later agent phases commit their own canonical messages (distinct files)
            phase = "ux_design" if n == 1 else "implement"
            _commit_file(workdir, f"[workflow] {phase} — g", n)
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    p = result.phases[0]
    assert p.status == "ok"  # canonicalized, not failed
    assert p.commit_gate is not None
    assert p.commit_gate["reason"] == "COMMIT_PREFIX_CANONICALIZED"
    assert p.commit_gate["original_subjects"] == ["site: add things"]
    assert p.commit_gate["expected_prefix"] == "[workflow] scope — g"
    original_sha = made[0][0]
    rewritten_sha = p.commit_gate["rewritten_sha"]
    assert rewritten_sha and rewritten_sha != original_sha  # the rewrite replaced the sha
    # the re-read shows ZERO violations — every commit now matches its own phase's pattern
    subjects = subprocess.run(
        ["git", "log", "--format=%s"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.splitlines()
    assert set(subjects) == {
        "[workflow] scope — g",
        "[workflow] ux_design — g",
        "[workflow] implement — g",
    }
    assert "site: add things" not in subjects
    # the rewrite preserved the TREE — only the message changed (content-addressed proof)
    orig_tree = subprocess.run(
        ["git", "rev-parse", f"{original_sha}^{{tree}}"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    new_tree = subprocess.run(
        ["git", "rev-parse", f"{rewritten_sha}^{{tree}}"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert orig_tree == new_tree
    assert result.ok


def test_commit_prefix_rewrites_a_single_bad_commit_not_at_head(tmp_path, monkeypatch):
    """(Drawing-board fix) A single bad commit buried under a good commit IS self-healed by
    the gate's rewrite path — the shape the P0 amend rule had to refuse (``git commit
    --amend`` would have rewritten the GOOD commit at HEAD). The filter-branch rewrite
    scopes to the phase range by exact shas: the bad subject becomes canonical, the good
    commit's subject and every TREE are untouched. P0-4: canonicalize is an explicit opt-in,
    not the default."""
    monkeypatch.setenv("FINOPS_COMMIT_HOOK", "0")
    monkeypatch.setenv("FINOPS_COMMIT_GATE", "canonicalize")
    spec = load_spec(SPEC)
    _git_init(tmp_path)
    made = []
    calls: list[int] = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        n = len(calls)
        calls.append(n)
        if n == 0:  # scope — bad commit, then a good commit on top
            made.append((_commit_file(workdir, "site: add things", 0), "site: add things"))
            made.append((_commit_file(workdir, "[workflow] scope — g", 1), "[workflow] scope — g"))
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    p = result.phases[0]
    assert p.status == "ok"  # rewritten, not failed
    assert p.commit_gate is not None
    assert p.commit_gate["reason"] == "COMMIT_PREFIX_CANONICALIZED"
    assert p.commit_gate["original_subjects"] == ["site: add things"]
    assert p.commit_gate["expected_prefix"] == "[workflow] scope — g"
    (bad_sha, _), (good_sha, good_subject) = made
    # BOTH commits now conform; the good commit's SUBJECT is untouched (only shas change
    # because the range was rewritten)
    log = subprocess.run(
        ["git", "log", "--format=%H|%s"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.splitlines()
    assert [line.split("|", 1)[1] for line in log] == ["[workflow] scope — g"] * 2
    assert good_subject == "[workflow] scope — g"
    # the good commit's TREE is preserved (messages-only rewrite)
    good_tree = subprocess.run(
        ["git", "rev-parse", f"{good_sha}^{{tree}}"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    head_tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert head_tree == good_tree
    assert result.ok


def test_commit_prefix_handles_a_goal_whose_40th_char_is_a_space(tmp_path):
    """(The i10 backfill lesson) A goal whose ``goal[:40]`` ends with a space: the hook
    writes the prefix, git strips the trailing whitespace on commit, and the gate compares
    the TRIMMED prefix (``_goal_prefix``) — otherwise the run fails COMMIT_PREFIX on its
    own prefix. The backfill goal "Verify the I10 typed-checkpoint capture implementation
    ..." hit exactly this."""
    spec = load_spec(SPEC)
    _git_init(tmp_path)
    goal = "Verify the I10 typed-checkpoint capture implementation on this branch"

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "scope.md").write_text("---\nstatus: accepted\n---\n\nscope")
        subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "plain message"], cwd=workdir, check=True)
        return _fake_agent()

    result = run_workflow(spec, goal=goal, model="m", workdir=tmp_path, run_agentic_fn=agent)
    p = result.phases[0]
    assert p.status == "ok"  # the hook prefixed, git trimmed, the gate matched the trim
    subjects = subprocess.run(
        ["git", "log", "--format=%s"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.splitlines()
    assert subjects[0].startswith("[workflow] scope — Verify the I10 typed-checkpoint capture")


def test_doc_contract_fails_a_phase_that_commits_a_doc_without_frontmatter(tmp_path):
    """(The 2e merge lesson) An agent phase that commits a docs/ file without a valid
    status frontmatter fails DOC_CONTRACT at phase time — the merge-time guard became a
    runner gate (the 2e p5 authored review docs without frontmatter and the merge went out
    red)."""
    spec = load_spec(SPEC)
    _git_init(tmp_path)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs" / "reviews").mkdir(parents=True, exist_ok=True)
        (Path(workdir) / "docs" / "reviews" / "x_adversary.md").write_text(
            "# x — adversarial review\n\nNo frontmatter here.\n"
        )
        subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "site: add things"], cwd=workdir, check=True)
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    p = result.phases[0]
    assert p.status == "failed"
    assert p.commit_gate is not None
    assert p.commit_gate["reason"] == "DOC_CONTRACT"
    assert any(path.endswith("x_adversary.md") for path in p.commit_gate["docs"])
    assert "DOC_CONTRACT" in p.error


def test_doc_contract_passes_a_doc_with_valid_status_frontmatter(tmp_path):
    """A docs/ file carrying a valid status field passes; a non-docs commit passes."""
    spec = load_spec(SPEC)
    _git_init(tmp_path)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs" / "reviews").mkdir(parents=True, exist_ok=True)
        (Path(workdir) / "docs" / "reviews" / "x_adversary.md").write_text(
            "---\nstatus: accepted\n---\n\n# x — adversarial review\n"
        )
        (Path(workdir) / "docs" / "scope.md").write_text("---\nstatus: accepted\n---\n\nscope")
        subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "[workflow] scope — g done"], cwd=workdir, check=True
        )
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    p = result.phases[0]
    assert p.status == "ok"
    assert p.commit_gate is None


def test_doc_contract_ignores_unknown_status_values(tmp_path):
    """An unknown status value is ALSO a violation (the contract vocabulary is closed)."""
    spec = load_spec(SPEC)
    _git_init(tmp_path)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs").mkdir(parents=True, exist_ok=True)
        (Path(workdir) / "docs" / "scope.md").write_text("---\nstatus: draft\n---\n\nscope")
        subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "[workflow] scope — g done"], cwd=workdir, check=True
        )
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    p = result.phases[0]
    assert p.status == "failed"
    assert p.commit_gate["reason"] == "DOC_CONTRACT"


def test_commit_msg_hook_works_in_a_worktree_shape(tmp_path):
    """(The 2d p5 lesson) Campaigns run in git WORKTREES, where ``.git`` is a file
    pointing at the shared git dir — the hook must install via ``git rev-parse --git-path``
    (shared hooks dir + per-worktree prefix file), or it silently fails and the wrapper's
    commit lands unprefixed (the exact shape that failed the 2d run's ledger)."""
    from agentic_dynamics.runtime import workflow_runner as wr

    main = tmp_path / "main"
    main.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=main, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=main, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=main, check=True)
    (main / "seed.md").write_text("seed")
    subprocess.run(["git", "add", "-A"], cwd=main, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "Initial"], cwd=main, check=True)
    wt = main / "wt"
    subprocess.run(["git", "worktree", "add", str(wt), "-b", "feature/x"], cwd=main, check=True)
    assert (wt / ".git").is_file()  # the worktree shape: .git is a FILE

    wr._install_commit_msg_hook(wt, "scope", "g")
    (wt / "f.md").write_text("f")
    subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "site: add things"], cwd=wt, check=True)
    subjects = subprocess.run(
        ["git", "log", "--format=%s"], cwd=wt, capture_output=True, text=True
    ).stdout.splitlines()
    assert subjects[0] == "[workflow] scope — g"  # the hook fired in the worktree
    # a second worktree gets its own prefix without clobbering the first
    wt2 = main / "wt2"
    subprocess.run(["git", "worktree", "add", str(wt2), "-b", "feature/y"], cwd=main, check=True)
    wr._install_commit_msg_hook(wt2, "other", "g")
    (wt2 / "g.md").write_text("g")
    subprocess.run(["git", "add", "-A"], cwd=wt2, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "plain message"], cwd=wt2, check=True)
    subjects2 = subprocess.run(
        ["git", "log", "--format=%s"], cwd=wt2, capture_output=True, text=True
    ).stdout.splitlines()
    assert subjects2[0] == "[workflow] other — g"
    # the first worktree's hook still prefixes with ITS prefix (per-worktree file)
    (wt / "h.md").write_text("h")
    subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "another plain"], cwd=wt, check=True)
    subjects1 = subprocess.run(
        ["git", "log", "--format=%s"], cwd=wt, capture_output=True, text=True
    ).stdout.splitlines()
    assert subjects1[0] == "[workflow] scope — g"


def test_commit_prefix_rewrites_in_a_worktree_shape(tmp_path, monkeypatch):
    """(The 2d p5 lesson, part 2) The gate's history rewrite must also resolve its filter
    script via ``git rev-parse --git-path`` — in a worktree ``wd/.git/`` does not exist."""
    monkeypatch.setenv("FINOPS_COMMIT_HOOK", "0")
    from agentic_dynamics.runtime import workflow_runner as wr

    main = tmp_path / "main"
    main.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=main, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=main, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=main, check=True)
    (main / "seed.md").write_text("seed")
    subprocess.run(["git", "add", "-A"], cwd=main, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "Initial"], cwd=main, check=True)
    wt = main / "wt"
    subprocess.run(["git", "worktree", "add", str(wt), "-b", "feature/x"], cwd=main, check=True)
    pre = wr._git_head(wt)  # the worktree branch's Initial commit — BEFORE the bad commits
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "bad one"], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "bad two"], cwd=wt, check=True)
    res = wr._canonicalize_commit_range(wt, pre, "[workflow] scope — g", [])
    assert res is not None
    subjects = subprocess.run(
        ["git", "log", "--format=%s"], cwd=wt, capture_output=True, text=True
    ).stdout.splitlines()
    assert subjects == ["[workflow] scope — g", "[workflow] scope — g", "Initial"]


def test_watchdog_sees_through_a_junk_heartbeat(tmp_path):
    """(p5-1) A stalled agent that touches the session file with junk heartbeats — non-JSON
    lines AND valid-JSON-but-not-a-step dicts — is STILL caught: the stall clock advances only
    on MEANINGFUL step events, never on any write."""
    spec = load_spec(SPEC)
    killed: list[str] = []
    release = threading.Event()

    def agent(prompt, *, model, backend, workdir, watchdog=None, **kwargs):
        transcript = _watchdog_transcript(workdir)
        transcript.parent.mkdir(parents=True, exist_ok=True)
        watchdog["kill"] = lambda: (killed.append("SIGTERM"), release.set())
        transcript.write_text('{"type": "step_start"}\n')  # one real step, then ...
        n = 0
        while not release.is_set():  # ... only junk heartbeats (both flavors)
            with transcript.open("a") as fh:
                fh.write("heartbeat keep-alive\n" if n % 2 else '{"foo": "bar"}\n')
            n += 1
            release.wait(timeout=0.15)
        return _fake_agent()

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        phase_watchdog_min=0.03,
        run_agentic_fn=agent,
    )
    p = result.phases[0]
    assert p.status == "failed"
    assert p.stall_evidence and p.stall_evidence["reason"] == "STALLED"
    assert killed == ["SIGTERM"]


def test_watchdog_cannot_distinguish_a_forged_valid_step(tmp_path):
    """(p5-1, accepted limitation) A heartbeat forged to LOOK like a real step event keeps the
    watchdog alive — the transcript is the model's own output channel and the two are
    indistinguishable at the transcript level. The measured disease was total silence; this is
    documented, not fixed. The test pins the boundary."""
    spec = load_spec(SPEC)
    killed: list[str] = []
    release = threading.Event()

    def agent(prompt, *, model, backend, workdir, watchdog=None, **kwargs):
        transcript = _watchdog_transcript(workdir)
        transcript.parent.mkdir(parents=True, exist_ok=True)
        watchdog["kill"] = lambda: (killed.append("SIGTERM"), release.set())
        with transcript.open("a") as fh:
            fh.write('{"type": "step_start"}\n')
        for _ in range(4):  # keep emitting REAL-looking step boundaries, slowly
            release.wait(timeout=0.15)
            if release.is_set():
                break
            with transcript.open("a") as fh:
                fh.write('{"type": "step_finish"}\n')
        return _fake_agent()

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        phase_watchdog_min=0.03,
        run_agentic_fn=agent,
    )
    assert result.phases[0].status == "ok"
    assert killed == []


# ── Deploy-gate evasion (p5-2) ──────────────────────────────────

DEPLOY_EVASION_COMMANDS = [
    ("firebase deploy --only hosting", {"workdir": "/somewhere/else"}),  # different cwd
    ("firebase --help > /dev/null && firebase deploy", {}),  # pre-command obfuscation
    ("npx firebase-tools deploy --only hosting", {}),  # npx form
    ("true; firebase deploy --only hosting", {}),  # chained
    ("firebase deploy --only hosting --project agentic-dynamics", {}),  # mirror host explicit
]


def test_deploy_gate_evasion_attempts_that_are_caught(tmp_path):
    """(p5-2) Evasion attempts that still expose the firebase command are caught: a different
    working directory, a benign pre-command, the ``npx firebase-tools`` form, chaining, and the
    explicit mirror-host flag. Each fails a non-deploy phase with DEPLOY_GATE."""
    from agentic_dynamics.runtime import workflow_runner as wr

    for command, extra in DEPLOY_EVASION_COMMANDS:
        line = json.dumps(
            {
                "type": "tool_use",
                "sessionID": "s",
                "part": {
                    "type": "tool",
                    "tool": "bash",
                    "state": {
                        "status": "completed",
                        "input": {"command": command, "workdir": extra.get("workdir", "/tmp/w")},
                        "output": "",
                    },
                },
            }
        )
        assert wr._deploy_pattern_match(command) is not None, command
        spec = load_spec(SPEC)
        result = run_workflow(
            spec,
            goal="g",
            model="m",
            workdir=tmp_path,
            commit=False,
            run_agentic_fn=_deploy_agent(line),
        )
        p = result.phases[0]
        assert p.status == "failed", command
        assert p.deploy_gate and p.deploy_gate["reason"] == "DEPLOY_GATE", command
        assert any(command == v["command"] for v in p.deploy_gate["violations"]), command


def test_deploy_gate_catches_a_deploy_script_by_its_output(tmp_path):
    """(p5-2) Indirection caught by the OUTPUT tier: a script file (``./deploy.sh``) whose bash
    input contains no 'firebase' literal but whose captured output shows the production deploy
    banner is still caught — a real firebase deploy prints the banner however it is invoked."""
    line = json.dumps(
        {
            "type": "tool_use",
            "sessionID": "s",
            "part": {
                "type": "tool",
                "tool": "bash",
                "state": {
                    "status": "completed",
                    "input": {
                        "command": "./deploy.sh",
                        "workdir": "/tmp/wt_site_revamp2/apps/website",
                    },
                    "output": "\n=== Deploying to 'ai-finops-rulebook'...\n\u2714 Deploy complete!\n"
                    "Hosting URL: https://ai-finops-rulebook.web.app\n",
                },
            },
        }
    )
    spec = load_spec(SPEC)
    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        run_agentic_fn=_deploy_agent(line),
    )
    p = result.phases[0]
    assert p.status == "failed"
    assert p.deploy_gate and p.deploy_gate["reason"] == "DEPLOY_GATE"
    assert p.deploy_gate["violations"][0]["command"] == "./deploy.sh"
    assert "Deploy complete!" in p.deploy_gate["violations"][0]["pattern"]


def test_deploy_gate_variable_indirection_without_a_banner_is_a_limitation(tmp_path):
    """(p5-2, accepted limitation) Indirection that never surfaces the literal 'firebase'
    command NOR the deploy banner in this phase's transcript — e.g. an alias/variable defined in
    an EARLIER phase, or a wrapper that suppresses firebase's output — is not catchable by a
    deterministic transcript scan (shell state across phases is unresolvable). Documented, not
    fixed. The test pins the boundary so a future hardening knows where it stands."""
    from agentic_dynamics.runtime import workflow_runner as wr

    line = json.dumps(
        {
            "type": "tool_use",
            "sessionID": "s",
            "part": {
                "type": "tool",
                "tool": "bash",
                "state": {
                    "status": "completed",
                    "input": {
                        "command": "$DEPLOY --only hosting --project agentic-dynamics",
                        "workdir": "/tmp/apps/website",
                    },
                    "output": "ok",  # a wrapper that swallows the deploy banner
                },
            },
        }
    )
    transcript = Path(tmp_path) / "lim.jsonl"
    transcript.write_text(line + "\n")
    assert wr._scan_transcript_for_deploys(transcript) == []


# ── Commit-enforcement evasion (p5-3) ───────────────────────────


def test_commit_prefix_evasion_attempts_that_are_caught(tmp_path):
    """(p5-3) Commit-message evasion: a DIFFERENT phase's name, a hyphen instead of the literal
    em-dash, a double em-dash, and a missing space after the em-dash are all rejected — the
    validator enforces the phase's OWN name + the exact pattern the resume machinery matches."""
    from agentic_dynamics.runtime import workflow_runner as wr

    goal_prefix = "g"
    assert (
        wr._commit_subject_matches("[workflow] p3_dom_verification — g", "scope", goal_prefix)
        is False
    )
    assert wr._commit_subject_matches("[workflow] scope - g", "scope", goal_prefix) is False
    assert wr._commit_subject_matches("[workflow] scope -- g", "scope", goal_prefix) is False
    assert wr._commit_subject_matches("[workflow] scope —— g", "scope", goal_prefix) is False
    assert wr._commit_subject_matches("[workflow] scope —g", "scope", goal_prefix) is False
    assert wr._commit_subject_matches("[workflow] scope — g", "scope", goal_prefix) is True
    # a WRONG goal prefix is rejected (already covered, kept for the attack matrix)
    assert (
        wr._commit_subject_matches("[workflow] scope — different goal", "scope", goal_prefix)
        is False
    )


def test_commit_prefix_trailing_content_after_a_valid_prefix_matches(tmp_path):
    """(p5-3, known-safe) Trailing content AFTER a valid '[workflow] <phase> — <goal prefix>'
    prefix still matches — the SAME startswith leniency the resume machinery has. The
    enforcement is deliberately not stricter than the pattern it guards: a commit that resumes
    as this phase's IS this phase's. Not a bypass of the contract; documented."""
    from agentic_dynamics.runtime import workflow_runner as wr

    assert wr._commit_subject_matches("[workflow] scope — g; rm -rf /", "scope", "g") is True
    assert wr._commit_subject_matches("[workflow] scope — g (done, extra)", "scope", "g") is True


def _spec_with_requires_deliverable():
    """The control_room_portal spec with the first phase's requires_deliverable on."""
    spec = load_spec(SPEC)
    for p in spec.workflow.params["phases"]:
        if p.get("name") == "scope":
            p["requires_deliverable"] = True
    return spec


def test_agent_phase_with_no_tree_change_fails_no_changes(tmp_path):
    """The vacuous-pass post-mortem: a phase that DECLARES requires_deliverable and
    delivers no tree change certifies itself ok while producing no deliverable (revamp3
    p3-p6). The runner's own _git_commit may still make an EMPTY commit — the working
    tree identity is what proves the phase produced nothing."""
    spec = _spec_with_requires_deliverable()
    _git_init(tmp_path)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        return _fake_agent()  # no file writes — the phase's tree never changes

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    p = result.phases[0]
    assert p.status == "failed"
    assert p.commit_gate is not None
    assert p.commit_gate["reason"] == "NO_CHANGES"
    assert "NO_CHANGES" in p.error


def test_agent_phase_without_the_flag_tolerates_no_change(tmp_path):
    """The opt-in default: a phase without requires_deliverable may legitimately conclude
    with no tree change (analysis-only phases) — the vacuous-pass gate must not break
    the general case."""
    spec = load_spec(SPEC)
    _git_init(tmp_path)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        return _fake_agent()  # no file writes

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    assert all(p.status == "ok" for p in result.phases)


# ── I10 — typed checkpoint capture (the session-routing v2 prerequisite) ─────────
#
# Every checkpoint event must be a TYPED, LEDGERED record, not just a status string: the
# mechanical stop (a ``checkpoint: true`` phase completing → awaiting_operator_approval) and
# the resume-decided contract reads (approved/rejected) both append a CheckpointRecord to
# ``WorkflowRunResult.checkpoints`` BEFORE the run exits, carrying phase + index, reason,
# the approval contract path, the decision, reached/decided timestamps, and the stop-point
# cost/token summary. The fixture mirrors test_checkpoint_mechanism.py's harness (the
# checkpoint stop semantics live there); these tests pin the typed capture itself.

CHECKPOINT_SPEC_YAML = """\
name: checkpoint_test
question: checkpoint fixture
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
      - name: design
        kind: agent
        checkpoint: true
        timeout: 120
        prompt: |
          {goal}
      - name: implement
        kind: agent
        timeout: 120
        prompt: |
          {goal}
factors:
  - {name: model, levels: [deepseek/deepseek-v4-flash]}
design: factorial
rules: []
metrics: []
comparison: null
"""


def _checkpoint_spec(tmp_path):
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(CHECKPOINT_SPEC_YAML)
    return load_spec(spec_path)


def _completed_checkpoint_wd(workdir):
    """A worktree whose checkpoint phase (``design``) is already committed — the state a
    resume sees after the first run stopped awaiting."""
    Path(workdir).mkdir(parents=True)
    _git_init(workdir)
    _commit_file(workdir, "[workflow] design — g", 1)
    return workdir


def test_checkpoint_phase_records_a_typed_checkpoint_record(tmp_path, monkeypatch):
    """(a) A ``checkpoint: true`` phase that completes successfully stops the run awaiting
    AND appends a typed CheckpointRecord to the run ledger BEFORE the run exits: phase +
    1-based index, reason ``checkpoint_reached``, the approval contract path, decision
    ``awaiting``, reached/decided timestamps, and the phase's cost/token summary at the
    stop point. The record rides the ledger JSON (additive ``checkpoints`` key) and the
    telemetry event log."""
    published = []

    class FakePublisher:
        def __init__(self, cell_id):
            self.cell_id = cell_id
            self.enabled = True

        def set_status(self, status):
            pass

        def set_phase(self, phase):
            pass

        def publish_event(self, event):
            published.append(event)

    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)

    spec = _checkpoint_spec(tmp_path)
    _git_init(tmp_path)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "design.md").write_text("delta preview")
        return _fake_agent()

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        run_agentic_fn=agent,
        publisher_factory=FakePublisher,
    )
    assert result.awaiting is True
    assert result.awaiting_phase == "design"
    assert result.awaiting_reason == "checkpoint"
    assert len(result.phases) == 1  # implement did NOT run
    p = result.phases[0]
    assert p.status == "awaiting"
    assert p.commit_hash

    # the typed record — one, for the design phase, at its designed stop
    assert len(result.checkpoints) == 1
    rec = result.checkpoints[0]
    assert isinstance(rec, workflow_runner.CheckpointRecord)
    assert rec.phase == "design"
    assert rec.phase_index == 1
    assert rec.reason == workflow_runner.CHECKPOINT_REASON_REACHED
    assert rec.approval_path.endswith("approvals/checkpoint_test/design_approval.md")
    assert rec.decision == workflow_runner.CHECKPOINT_DECISION_AWAITING
    assert rec.commit_hash == p.commit_hash
    # timestamps present and parseable
    from datetime import datetime

    assert datetime.fromisoformat(rec.reached_at.replace("Z", "+00:00"))
    assert datetime.fromisoformat(rec.decided_at.replace("Z", "+00:00"))
    # the phase's token/cost summary at the stop point
    assert rec.cost_usd == p.cost_usd == 0.001
    assert rec.tokens["total"] == p.tokens["total"] == 35

    # the record rides the ledger JSON (additive key) — round-trips byte-for-byte
    payload = result.to_dict()
    assert payload["awaiting"] is True
    assert len(payload["checkpoints"]) == 1
    cp = payload["checkpoints"][0]
    assert cp["phase"] == "design" and cp["phase_index"] == 1
    assert cp["reason"] == "checkpoint_reached"
    assert cp["decision"] == "awaiting"
    assert cp["approval_path"] == rec.approval_path
    assert cp["reached_at"] == rec.reached_at and cp["decided_at"] == rec.decided_at
    assert cp["cost_usd"] == 0.001 and cp["tokens"]["total"] == 35
    assert cp["commit_hash"] == p.commit_hash

    # the telemetry event log carries the same typed payload
    checkpoint_events = [e for e in published if e.get("type") == "checkpoint"]
    assert len(checkpoint_events) == 1
    assert checkpoint_events[0]["part"] == cp


def test_resume_refusal_records_rejected_checkpoint_decision(tmp_path, monkeypatch):
    """(b) A resume that refuses past an unsatisfied checkpoint (no approval artifact)
    appends an ``approval_required``/``rejected`` record with the contract-read evidence —
    the resume machinery can read the last checkpoint state even when the run stops again."""
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)
    spec = _checkpoint_spec(tmp_path)
    wd = _completed_checkpoint_wd(tmp_path / "wd")
    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        calls.append(1)
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=wd, run_agentic_fn=agent, resume=True)
    assert calls == []  # nothing ran
    assert result.awaiting is True
    assert result.awaiting_reason == "approval_refused"
    assert result.phases == []

    assert len(result.checkpoints) == 1
    rec = result.checkpoints[0]
    assert rec.phase == "design"
    assert rec.reason == workflow_runner.CHECKPOINT_REASON_APPROVAL_REQUIRED
    assert rec.decision == workflow_runner.CHECKPOINT_DECISION_REJECTED
    assert rec.approval_path.endswith("approvals/checkpoint_test/design_approval.md")
    assert rec.commit_hash  # the checkpoint phase's own commit resolved from git
    from datetime import datetime

    assert datetime.fromisoformat(rec.reached_at.replace("Z", "+00:00"))
    assert datetime.fromisoformat(rec.decided_at.replace("Z", "+00:00"))
    # the contract-read evidence names the refusal reason
    assert rec.approval_evidence is not None
    assert rec.approval_evidence["valid"] is False
    assert "no_artifact" in rec.approval_evidence["failed_checks"]


def test_resume_with_approval_records_approved_checkpoint_decision(tmp_path, monkeypatch):
    """(c) A resume that PROCEEDS past a validly-approved checkpoint (signed artifact
    committed after the checkpoint commit) appends an ``approved`` record carrying the
    contract evidence — the run keeps going, and the ledger shows why it could."""
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)
    spec = _checkpoint_spec(tmp_path)
    wd = _completed_checkpoint_wd(tmp_path / "wd")
    import subprocess as _sp

    ck = _sp.run(
        ["git", "rev-parse", "HEAD"], cwd=wd, capture_output=True, text=True
    ).stdout.strip()
    tree = _sp.run(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=wd, capture_output=True, text=True
    ).stdout.strip()
    ap = wd / "approvals" / spec.name
    ap.mkdir(parents=True)
    (ap / "design_approval.md").write_text(
        "# Operator approval\n\n- operator: jane@example.com\n- date: 2026-08-27\n"
        f"- spec: {spec.name}\n- phase: design\n- candidate: {ck}\n- tree: {tree}\n"
    )
    _commit_file(wd, "operator approval (descendant of the checkpoint)", 2)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "impl.md").write_text("implemented")
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=wd, run_agentic_fn=agent, resume=True)
    assert result.awaiting is False
    assert [p.phase for p in result.phases] == ["implement"]
    assert result.ok is True

    assert len(result.checkpoints) == 1
    rec = result.checkpoints[0]
    assert rec.phase == "design"
    assert rec.reason == workflow_runner.CHECKPOINT_REASON_APPROVAL_REQUIRED
    assert rec.decision == workflow_runner.CHECKPOINT_DECISION_APPROVED
    assert rec.approval_evidence is not None
    assert rec.approval_evidence["valid"] is True
    assert rec.approval_evidence["operator"] == "jane@example.com"
    assert rec.approval_evidence["date"] == "2026-08-27"


def test_checkpoint_ledger_round_trips_spec_status_style(tmp_path):
    """The ledger round-trip: a spec_status-style loader reads the NEW ``checkpoints`` key
    without breaking OLD ledgers (the 2d/2c era — no such key), and the
    retro_session_routing-style phase consumption is unaffected. A run with no checkpoint
    events emits an empty array, never a missing/renamed key."""
    spec_dir = tmp_path / "cap_site_revamp3"
    spec_dir.mkdir()

    # legacy 2d/2c-era ledger — no checkpoints key at all
    legacy = {
        "spec_name": "cap_site_revamp3",
        "model": "m",
        "ok": False,
        "awaiting": True,
        "total_cost_usd": 0.012,
        "started_at": "2026-08-19T14:25:30.123456+00:00",
        "ended_at": "2026-08-19T14:26:30.123456+00:00",
        "phases": [
            {
                "phase": "design",
                "status": "awaiting",
                "cost_usd": 0.012,
                "tokens": {"in": 1, "out": 2},
            },
        ],
    }
    (spec_dir / "legacy.json").write_text(json.dumps(legacy))

    # new I10 ledger — checkpoints present (one typed record)
    new = dict(legacy)
    new["ended_at"] = "2026-08-19T14:27:30.123456+00:00"
    new["checkpoints"] = [
        {
            "phase": "design",
            "phase_index": 1,
            "reason": "checkpoint_reached",
            "approval_path": str(
                spec_dir / "approvals" / "cap_site_revamp3" / "design_approval.md"
            ),
            "decision": "awaiting",
            "reached_at": "2026-08-19T14:26:30.123456+00:00",
            "decided_at": "2026-08-19T14:26:30.123456+00:00",
            "cost_usd": 0.012,
            "tokens": {"in": 1, "out": 2},
            "commit_hash": "abc123",
            "approval_evidence": None,
        }
    ]
    (spec_dir / "new.json").write_text(json.dumps(new))

    # spec_status-style loader: both ledgers project; the new key never changes the projection
    runs = spec_status.load_runs("cap_site_revamp3", results_dir=tmp_path, root=tmp_path)
    assert len(runs) == 2
    assert runs[-1].awaiting is True  # the latest (new) run still reads the awaiting flag
    assert runs[-1].ok is False
    assert runs[0].path.endswith("legacy.json")
    assert runs[1].path.endswith("new.json")

    # retro_session_routing-style consumption (the phases list) unaffected by the new key
    payload = json.loads((spec_dir / "legacy.json").read_text())
    assert "checkpoints" not in payload
    assert [p["phase"] for p in payload.get("phases", [])] == ["design"]
    payload = json.loads((spec_dir / "new.json").read_text())
    cp = payload["checkpoints"][0]
    assert cp["phase"] == "design" and cp["reason"] == "checkpoint_reached"
    assert cp["decision"] == "awaiting" and cp["cost_usd"] == 0.012
    assert [p["phase"] for p in payload.get("phases", [])] == ["design"]

    # a run with no checkpoint events emits an empty array — additive, never a missing key
    plain_yaml = CHECKPOINT_SPEC_YAML.replace("        checkpoint: true\n", "")
    plain_path = tmp_path / "plain.yaml"
    plain_path.write_text(plain_yaml)
    plain = run_workflow(
        load_spec(plain_path),
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )
    assert plain.checkpoints == []
    assert plain.to_dict()["checkpoints"] == []


def test_deploy_gate_ignores_argument_position_firebase_mentions(tmp_path):
    """The a2/a4 false-positive fix (2026-09-03): the deploy gate fires only when firebase
    is the EXECUTED command, never when the string appears inside an argument — a commit
    message quoting 'firebase deploy', a grep pattern, or a doc write are not deploys.
    The OUTPUT tier still catches real indirection (a script that reaches firebase prints
    the deploy banner)."""
    spec = load_spec(SPEC)
    mention = json.dumps(
        {
            "type": "tool_use",
            "sessionID": "s",
            "part": {
                "type": "tool",
                "tool": "bash",
                "state": {
                    "input": {
                        "command": 'git commit -m "[workflow] a4 — the AIO definition states: firebase deploy *: ask"'
                    }
                },
            },
        }
    )

    def agent(prompt, *, model, backend, workdir, **kwargs):
        _watchdog_transcript(workdir).parent.mkdir(parents=True, exist_ok=True)
        _watchdog_transcript(workdir).write_text(mention + "\n")
        return _fake_agent()

    result = run_workflow(
        spec, goal="g", model="m", workdir=tmp_path, commit=False, run_agentic_fn=agent
    )
    assert result.ok
    assert all(p.deploy_gate is None for p in result.phases)


def test_test_phase_with_phantom_target_is_a_false_green_guard(tmp_path):
    """The b5 phantom-target lesson (fleet_launch_boundary F5, ported to the wave3 branch):
    a kind:test phase whose tests: target resolves to NO collected tests (a nonexistent
    file) must FAIL the phase — a zero-test run is never a pass. The old check failed the
    phase only on suite failed/errors, so total 0 / failed 0 / errors 0 read ok while
    test_executed_success was False: the phase record contradicted itself."""
    spec = load_spec(SPEC)
    for p in spec.workflow.params["phases"]:
        if p.get("kind") == "test":
            p["tests"] = ["tests/this_file_does_not_exist.py"]
            break
    else:
        raise AssertionError("SPEC has no test phase")

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )
    test_phase = [p for p in result.phases if p.kind == "test"][0]
    assert test_phase.status == "failed"  # zero tests is a failure, never ok
    assert test_phase.test_executed_success is False
    assert test_phase.tests_total == 0
    assert "TEST_GATE" in test_phase.error or "no tests" in test_phase.error
    assert result.ok is False  # the run must not report success


# ── wave C follow-up: runner/fleet honesty ───────────────────────────────────


def _init_repo(path) -> None:
    import subprocess as sp

    sp.run(["git", "init", "-q"], cwd=path, check=True, capture_output=True)
    sp.run(["git", "config", "user.email", "t@t"], cwd=path, check=True, capture_output=True)
    sp.run(["git", "config", "user.name", "t"], cwd=path, check=True, capture_output=True)


def test_git_commit_verbose_names_the_reason(tmp_path):
    """Wave C follow-up: every non-commit outcome carries a NAME (this used to be a bare "")."""
    from agentic_dynamics.runtime.workflow_runner import _git_commit_verbose

    _init_repo(tmp_path)
    # clean tree → nothing to commit
    h, reason = _git_commit_verbose(tmp_path, "p1", "goal")
    assert (h, reason) == ("", "nothing_to_commit")
    # staged work → committed
    (tmp_path / "a.txt").write_text("x")
    h, reason = _git_commit_verbose(tmp_path, "p1", "goal")
    assert h and reason == ""
    # a git REFUSAL is named with its detail, never a bare ""
    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    # Git templates can be empty (this host's are): create the directory the hook lands in.
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    (tmp_path / "b.txt").write_text("y")
    h, reason = _git_commit_verbose(tmp_path, "p1", "goal")
    assert h == "" and reason.startswith("commit_failed:")


def test_an_ok_phase_with_uncommitted_work_fails_loudly(tmp_path, monkeypatch):
    """An ok phase whose commit cannot land must fail with COMMIT_SKIPPED + the reason —
    never a green phase over work nobody can commit (the three-run loss, 2026-09-12)."""
    import agentic_dynamics.runtime.workflow_runner as wr

    spec = load_spec(SPEC)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        d = Path(workdir) / "docs"
        d.mkdir(parents=True, exist_ok=True)
        (d / "scope.md").write_text("scope")
        return _fake_agent()

    monkeypatch.setattr(
        wr, "_git_commit_verbose", lambda *a, **k: ("", "commit_failed: deliberate")
    )
    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)

    phase = result.phases[0]
    assert phase.status == "failed"
    assert phase.commit_status == "commit_failed: deliberate"
    assert "COMMIT_SKIPPED" in phase.error
    assert result.ok is False


def test_partial_self_commit_with_failed_final_commit_is_not_adopted(tmp_path, monkeypatch):
    """(Astra ae212a0 finding 4) a phase that self-commits PART of its work and then has the
    runner's final commit rejected must NOT adopt the earlier partial HEAD as its outcome.

    Real temp-git probe: the agent commits an initial part, writes the final deliverable, and
    a pre-commit hook rejects the runner's final commit. The partial commit advances HEAD, so
    the pre-fix commit block adopted it and skipped the dirty-tree check — reporting
    ``ok=true`` over a still-uncommitted deliverable, the same loss class PR #49 set out to
    eliminate. The fix verifies the intended final worktree state is clean BEFORE adopting:
    here the deliverable remains, so the phase fails with the failed-commit reason preserved
    and the earlier HEAD is not recorded.
    """
    monkeypatch.delenv("FINOPS_EMIT_SELF", raising=False)
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)
    _git_init(tmp_path)
    spec = _emit_synth_spec([{"name": "p1", "kind": "agent", "prompt": "do p1"}])

    def agent(prompt, *, model, backend, workdir, **kwargs):
        wd = Path(workdir)
        # (1) the agent self-commits an initial part of the work
        (wd / "partial.txt").write_text("partial")
        subprocess.run(["git", "add", "-A"], cwd=wd, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "[workflow] p1 — g"], cwd=wd, check=True)
        # (2) the agent writes the final deliverable, committed only by the runner
        (wd / "deliverable.txt").write_text("final deliverable")
        # (3) a pre-commit hook rejects the runner's final commit
        hook = wd / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        return _fake_agent(files_created=["deliverable.txt"])

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    phase = result.phases[0]

    # not green over an uncommitted deliverable
    assert phase.status == "failed"
    assert result.ok is False
    # the failed-commit reason is preserved, never a silent success
    assert phase.commit_status.startswith("commit_failed:")
    assert "COMMIT_SKIPPED" in phase.error
    # the earlier partial HEAD is NOT adopted as the phase outcome
    assert phase.commit_hash == ""
    # the final deliverable is still present and still needs committing
    assert (tmp_path / "deliverable.txt").exists()
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=tmp_path, capture_output=True, text=True
    ).stdout
    assert "deliverable.txt" in status


def test_clean_self_commit_is_adopted(tmp_path, monkeypatch):
    """(Astra ae212a0 finding 4, direction b) the happy path still works: an agent that
    commits ALL of its work leaves a clean tree, so its own HEAD IS adopted — adoption is
    gated on the clean-tree verification, not removed."""
    monkeypatch.delenv("FINOPS_EMIT_SELF", raising=False)
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)
    _git_init(tmp_path)
    spec = _emit_synth_spec([{"name": "p1", "kind": "agent", "prompt": "do p1"}])
    monkeypatch.setattr(workflow_runner, "_emit_self_finding", lambda *a, **k: None)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        wd = Path(workdir)
        (wd / "work.txt").write_text("agent's own committed work")
        subprocess.run(["git", "add", "-A"], cwd=wd, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "[workflow] p1 — g"], cwd=wd, check=True)
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    phase = result.phases[0]
    assert phase.status == "ok"
    assert phase.commit_hash  # the agent's own clean commit was adopted
    assert phase.commit_status == ""
    assert phase.error == ""
    # the worktree is genuinely clean and represented by the adopted candidate
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=tmp_path, capture_output=True, text=True
    ).stdout
    assert status.strip() == ""


def test_commit_prefix_gate_is_merge_aware(tmp_path, monkeypatch):
    """Wave C follow-up: a phase that MERGES a branch is not charged with the merged
    lineage's commits (first-parent view); a direct nonconforming commit still fails."""
    import subprocess as sp

    from agentic_dynamics.runtime.workflow_runner import PhaseResult, _enforce_commit_prefix

    monkeypatch.delenv("FINOPS_COMMIT_GATE", raising=False)

    def git(repo, *args):
        return sp.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)

    repo = tmp_path / "r"
    repo.mkdir()
    _init_repo(repo)
    (repo / "a").write_text("1")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    base = git(repo, "rev-parse", "HEAD").stdout.strip()
    # a side branch with a NON-conforming commit, merged with the canonical subject
    git(repo, "checkout", "-q", "-b", "side")
    (repo / "b").write_text("2")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "plain side commit")
    git(repo, "checkout", "-q", "-")
    git(repo, "merge", "--no-ff", "side", "-m", "[workflow] p1 — goal")

    pr = PhaseResult(phase="p1", kind="agent", status="ok")
    _enforce_commit_prefix(pr, repo, "p1", "goal", base)
    assert pr.status == "ok" and not pr.commit_gate  # the merge is the phase's work

    # negative control: a DIRECT nonconforming commit after the baseline still fails
    (repo / "c").write_text("3")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "plain direct commit")
    pr2 = PhaseResult(phase="p1", kind="agent", status="ok")
    _enforce_commit_prefix(pr2, repo, "p1", "goal", base)
    assert pr2.status == "failed"
    assert pr2.commit_gate and pr2.commit_gate.get("reason") == "COMMIT_PREFIX"


def test_wall_burned_phase_without_a_deliverable_fails(tmp_path):
    """A phase killed at its timeout wall with NOTHING committed must FAIL, never read ok
    (2026-09-22, the L33 g_adversarial: status ok + timed_out=True + commit "" made a run
    read 'succeeded' and only promote's commit check refused it)."""
    spec = load_spec(SPEC)

    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)

    def agent(prompt, *, model, backend, workdir, watchdog=None, **kwargs):
        time.sleep(1.2)  # burn past the 1s wall; write nothing, commit nothing
        return _fake_agent()

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=True,
        phase_watchdog_min=0,
        timeout=1,
        run_agentic_fn=agent,
    )
    phase = result.phases[0]
    assert phase.timed_out is True
    assert phase.status == "failed"
    assert "TIMEOUT" in (phase.error or "")
    assert result.ok is False


# ── Context-route ledger contract (world models L60, unit 5) ─────────────────────────────────


def test_phase_result_context_route_is_named_absence_when_unrouted():
    """u5 (L60/F5): ``to_dict`` ALWAYS carries ``context_route``.

    A phase that computed no route must serialize an explicit NAMED ABSENCE — never a dropped
    key (indistinguishable from an old ledger) and never a fabricated empty success (an empty
    record with ``route_status == "resolved"``, which reads as a clean retrieval that matched
    nothing). The structural boundary F5 records: the run that introduced the recorder is
    executed by the pre-recorder runner, so its agent phases serialize exactly this absence.
    """
    from agentic_dynamics.knowledge.context_layers import CONTEXT_ROUTE_RECORD_KEYS
    from agentic_dynamics.runtime.workflow_runner import PhaseResult

    phase = PhaseResult(phase="implement", kind="agent", status="ok")
    assert phase.context_route is None  # nothing computed yet — this unit only serializes

    ledger = phase.to_dict()
    assert "context_route" in ledger  # never a dropped key
    absence = ledger["context_route"]
    assert set(absence) == set(CONTEXT_ROUTE_RECORD_KEYS)  # the schema's stable keys, exactly
    assert absence["schema"] == "context-route/v1"
    assert absence["route_status"] == "unknown"  # NOT "resolved" — no fabricated clean pass
    assert absence["fallback_reason"] == "context_route_not_computed"
    assert absence["layers"] == []  # nothing was resolved
    assert absence["served_count"] == 0

    # Round-trip: the named absence survives reconstruction — the key is part of the dataclass,
    # not an in-memory-only view.
    rebuilt = PhaseResult(**ledger)
    assert rebuilt.context_route == absence


def test_phase_result_context_route_record_round_trips_layer_statuses():
    """u5 (L60): a computed record round-trips through JSON with its layer statuses intact."""
    from agentic_dynamics.knowledge.context_layers import (
        build_context_route_record,
        resolve_phase_layers,
    )
    from agentic_dynamics.runtime.workflow_runner import PhaseResult

    # A resolved implementation route: L1 structure + L2 history, with L4 self prohibited.
    route = resolve_phase_layers("implement", "agent")
    record = build_context_route_record("implement", route, None, None, shared_scopes=[])
    statuses = {layer["layer"]: layer["status"] for layer in record["layers"]}
    assert statuses["L1"] == "named_absent"
    assert statuses["L2"] == "named_absent"
    assert statuses["L4"] == "excluded"

    phase = PhaseResult(phase="implement", kind="agent", status="ok")
    phase.context_route = record

    ledger = phase.to_dict()
    assert ledger["context_route"] == record  # emitted verbatim, never re-derived

    # JSON is how the run ledger is persisted; the record must survive it byte-for-byte.
    reloaded = json.loads(json.dumps(ledger))
    rebuilt = PhaseResult(**reloaded)
    assert rebuilt.context_route == record
    rebuilt_statuses = {
        layer["layer"]: layer["status"] for layer in rebuilt.context_route["layers"]
    }
    assert rebuilt_statuses == statuses


def test_phase_result_context_route_legacy_ledger_parses_and_upgrades_to_named_absence():
    """u5 (L60/F5): an OLD ledger row (no ``context_route`` key) parses unchanged.

    The field was ADDED without renaming or removing any existing key, so a consumer reading a
    pre-field on-disk ledger must still find the row usable: ``.get("context_route")`` yields a
    clean absence (``None``), never a ``KeyError`` — the row "parses unchanged". Re-serializing
    that legacy row through the CURRENT dataclass materializes the explicit named absence, which
    is what makes a missing record AUDITABLE rather than silently dropped. This is the F5
    structural boundary: the recorder run serializes the absence, the follow-up run (on the
    promoted tree) is the first live evidence of a populated record.
    """
    from agentic_dynamics.runtime.workflow_runner import (
        CONTEXT_ROUTE_ABSENCE_REASON,
        PhaseResult,
    )

    # A hand-written pre-field ledger row: the stable columns an old on-disk ledger carried,
    # and conspicuously NOT ``context_route``.
    legacy_row = {
        "phase": "implement",
        "kind": "agent",
        "status": "ok",
        "model": "deepseek/deepseek-flash",
        "duration_s": 1.5,
    }
    # The run ledger is JSONL on disk: it must parse without the new key and without error.
    parsed = json.loads(json.dumps(legacy_row))
    assert "context_route" not in parsed  # the old shape genuinely lacks the key
    assert parsed.get("context_route") is None  # a consumer reads absence, not a KeyError

    rebuilt = PhaseResult(**parsed)
    assert rebuilt.context_route is None  # the absent field defaults; nothing is fabricated

    # Re-serializing UPGRADES the legacy row to the current contract: the key is present and
    # names the absence — never omitted (indistinguishable from an old ledger) and never a
    # fabricated empty success (an empty record with ``route_status == "resolved"``).
    upgraded = rebuilt.to_dict()
    assert "context_route" in upgraded
    absence = upgraded["context_route"]
    assert absence["fallback_reason"] == CONTEXT_ROUTE_ABSENCE_REASON
    assert absence["route_status"] == "unknown"
    assert absence["layers"] == []


# ── Context-route end-to-end wiring (world models L60, unit 6 — F1/F5) ───────────────────────


def test_real_phase_route_reaches_retrieval_and_ledger(tmp_path):
    """u6 (L60/F1/F5): the runner resolves the REAL phase route END-TO-END, no injected route.

    The att6 defect was that ``LayerRoute`` was built but never threaded into
    ``augment_prompt``/``retrieve`` — the route gate asserted a helper, not the route. This
    test drives a REAL phase (``implement``) through ``run_workflow`` with NO route injected:

    * the captured ``retrieve_fn`` kwargs prove the resolved layer material reached the ONE
      retrieval path — the ``implement`` call carried a nonempty ``source_types`` prefilter
      including ``code`` (L1 structure), while the unrecognised ``scope`` phase's call did NOT
      (the route is per-phase, not a fixed label); and
    * ``PhaseResult.to_dict()['context_route']`` is nonempty, ``route_status == "resolved"``,
      with one disposition per resolved layer (L1 ``served``, L4 ``excluded``); and
    * the LEDGER record and the RETRIEVAL shape are bound to the SAME route for EACH phase:
      the implementation record's L1 ``source_types`` are exactly the structure term the
      dense leg was handed, and the unknown-role ``scope`` record carries no L1 disposition
      while the code candidate the fake leg still returned is recorded ``unclassified``
      (never served) — three views of one routing decision.

    A cosmetic route label, an assertion on a helper rather than the route, or a record that
    disagrees with the retrieval it drove, all fail here.
    """
    from agentic_dynamics.knowledge.context_layers import LAYER_STATUSES

    spec = load_spec(SPEC)
    seen: list[dict] = []

    class _TypedEvidence:
        """A served candidate carrying its real ``source_type`` (attribution observable)."""

        def __init__(self, cid, text, source_type):
            self.id = cid
            self.text = text
            self.authority = "source"
            self.source_type = source_type
            self.content_hash = f"ch:{cid}"
            self.token_count = len(text.split())

        def citation(self):
            return f"[K:{self.id}@abc:loc]"

    def retrieve_fn(**kwargs):
        seen.append(kwargs)
        return _FakeAttempt([_TypedEvidence("k1", "code evidence", "code")])

    def construct_fn(request):
        return _FakeAugmented("AUG")

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        rag_augment=True,
        retrieve_fn=retrieve_fn,
        construct_fn=construct_fn,
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )

    # An applicable agent phase: ``implement`` classifies as role=implementation, so the real
    # deterministic route resolves L1 structure (+ the L2 history floor) for it.
    implement = next(p for p in result.phases if p.phase == "implement")
    record = implement.to_dict()["context_route"]
    assert record  # nonempty — a computed record, never a dropped/empty key
    assert record["schema"] == "context-route/v1"
    assert record["route_status"] == "resolved"  # NOT "unknown"/absence
    assert record["role"] == "implementation"
    statuses = {layer["layer"]: layer["status"] for layer in record["layers"]}
    assert {"L0", "L1", "L2", "L4"} <= set(statuses)  # one disposition per resolved layer
    assert all(status in LAYER_STATUSES for status in statuses.values())
    assert statuses["L1"] == "served"  # the code evidence was attributed to structure
    assert statuses["L4"] == "excluded"  # self layer is never served to a cell phase
    assert record["served_count"] >= 1

    # The ledger record is not merely nonzero: its L1 source types are what the ONE
    # retrieval path was actually shaped with. The implementation route named ``code`` as
    # L1 structure, and the dense leg received that same structure term — so a route
    # rendered as a label (a record present but retrieval unshaped), or a record built from
    # a different route than the one retrieval ran, cannot satisfy this binding.
    l1_entry = next(layer for layer in record["layers"] if layer["layer"] == "L1")
    assert "code" in l1_entry["source_types"]
    assert set(l1_entry["source_types"]) <= set(seen[2]["source_types"])

    # F1 falsifier: the route reached retrieval. The plain dict order is the phase order
    # (scope, ux_design, implement are the three agent phases; verify is kind=test and is
    # bypassed). ``scope`` is role=unknown -> L2 only, so it must NOT get structure; the
    # implementation phase MUST.
    assert len(seen) == 3
    assert "code" not in seen[0]["source_types"]  # unknown role: no L1 structure
    assert "code" in seen[2]["source_types"]  # implementation role: L1 structure served

    # Per-phase, not a fixed label: the unrecognised ``scope`` phase resolves the L2 history
    # floor only, and its ledger record is INDEPENDENTLY nonempty/resolved with NO L1
    # disposition. Because the fake dense leg ignores the prefilter and still returns a
    # ``code`` candidate, that candidate is un-routable to ``scope`` and must be recorded
    # ``unclassified`` at ``unknown`` status — never served, never a fabricated zero. This
    # ties route -> retrieval -> record together per phase.
    scope = next(p for p in result.phases if p.phase == "scope")
    scope_record = scope.to_dict()["context_route"]
    assert scope_record["route_status"] == "resolved"  # the L2 floor IS real material
    assert all(layer["layer"] != "L1" for layer in scope_record["layers"])
    assert scope_record["served_count"] == 0  # the code candidate is not routable here
    assert any(item["id"] == "k1" for item in scope_record["unclassified"])


# ── Shared-history scope end-to-end (world models L60, unit 7 — F1/F2) ───────────────────────


def _where_matches(metadata, where):
    """Evaluate the subset of Chroma's where grammar that ``_dense_filter`` emits (u7).

    Supports the exact clause shapes the filter produces — a bare equality, ``$or``, and
    ``$and`` — so a test can prove a shared-scope decision stays retrievable through the dense
    leg's OWN where-expression, not merely through retrieve's local hard filter.
    """
    if not where:
        return True
    if "$and" in where:
        return all(_where_matches(metadata, clause) for clause in where["$and"])
    if "$or" in where:
        return any(_where_matches(metadata, clause) for clause in where["$or"])
    return all(metadata.get(key) == value for key, value in where.items())


class _WhereAwareDenseStore:
    """Dense store that APPLIES the where-expression it is handed (Chroma-shaped, u7).

    A store that ignores ``where`` would only exercise retrieve's local filter; this one
    honours the clause, so the positive shared-retrievability assertion also exercises the
    store-side union clause and would fail if the clause regressed to a single equality.
    """

    def __init__(self, hits):
        self._hits = hits
        self.where = None

    def search(self, query, *, top_k=40, where=None):
        self.where = where
        return [h for h in self._hits if _where_matches(h.get("metadata") or {}, where)]


def _scope_dense_hit(
    cid,
    text,
    *,
    repository_id="",
    source_type="code",
    acl_scope=None,
    authority="source",
):
    """A dense hit carrying the repository scope + source type the union filter operates on.

    ``acl_scope`` is opt-in (``None`` leaves the key OFF the metadata, preserving the
    historical ACL-free probes byte-for-byte); a normal-runner probe supplies it so the
    dense where-expression's authorized-ACL clause has something real to match against.
    """
    metadata = {
        "authority": authority,
        "source_type": source_type,
        "repository_id": repository_id,
        "content_hash": f"hash:{cid}",
    }
    if acl_scope is not None:
        metadata["acl_scope"] = acl_scope
    return {"id": cid, "document": text, "metadata": metadata, "distance": 0.1}


def test_resolve_rag_params_carries_explicit_shared_history_scopes(tmp_path):
    """u7 (L60/F1): ``_resolve_rag_params`` carries + normalizes an EXPLICIT shared list.

    The canonical ``shared_history_scopes`` key is ALWAYS present in the resolved config: an
    explicit list is preserved (aliases collapsed onto the canonical key, wildcards and empty
    entries refused) and an absent list defaults to ``[]`` — an empty list never means global.
    This is what makes the shared scope reach the phase-route builder and retrieve at all.
    """
    from agentic_dynamics.runtime.workflow_runner import _resolve_rag_params

    spec = load_spec(SPEC)

    explicit = _resolve_rag_params(
        spec,
        {"shared_history_scopes": [" cell-shared ", "cell-shared", "*", ""]},
        wd=tmp_path,
        rag_augment=True,
    )
    assert explicit["shared_history_scopes"] == ["cell-shared"]  # normalized, wildcard refused

    # The alias form is carried onto the canonical key the route + retrieval read.
    aliased = _resolve_rag_params(
        spec, {"shared_scopes": ["cell-x"]}, wd=tmp_path, rag_augment=True
    )
    assert aliased["shared_history_scopes"] == ["cell-x"]

    # Absent -> [] (the key is present and non-global, never omitted).
    defaulted = _resolve_rag_params(spec, None, wd=tmp_path, rag_augment=True)
    assert defaulted["shared_history_scopes"] == []


def test_shared_scope_union_reaches_dense_filter_end_to_end(tmp_path):
    """u7 (L60/F1/F2): a run configured with shared scopes builds the requested ∪ shared dense
    clause, keeps the shared decision retrievable, and still excludes a foreign private scope.

    The runner resolves the REAL phase route from ``rag_params`` (no injected route) and
    threads the shared scope through ``augment_prompt`` into the ONE ``retrieve`` path. The
    where-aware store below honours the where-expression it is handed, so the positive
    assertion would fail if ``_dense_filter`` regressed to a single requested-scope equality;
    the local hard pre-filter keeps the foreign private scope out regardless of the store.
    """
    import functools

    from agentic_dynamics.knowledge.retrieval import retrieve

    spec = load_spec(SPEC)
    # The cell's own scope is the "requested" arm; ``cell-b`` is the explicit shared arm. An
    # explicit ``repository_id`` is supplied so the run does not default ``acl_scope`` to the
    # cell scope (which would add an ACL equality clause and test a different dimension); the
    # shared scope is still carried solely by ``shared_history_scopes``.
    requested_scope = cell_scope(tmp_path)
    requested_hit = _scope_dense_hit(
        "k-requested", "websocket reload protocol", repository_id=requested_scope
    )
    shared_hit = _scope_dense_hit("k-shared", "shared websocket decision", repository_id="cell-b")
    foreign_hit = _scope_dense_hit("k-foreign", "foreign websocket finding", repository_id="cell-c")
    store = _WhereAwareDenseStore([requested_hit, shared_hit, foreign_hit])

    served: list[list[str]] = []

    def construct_fn(request):
        served.append([unit.knowledge_id for unit in request.evidence])
        return _FakeAugmented("AUG")

    run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        rag_augment=True,
        retrieve_fn=functools.partial(retrieve, dense_store=store, graph_client=None),
        construct_fn=construct_fn,
        rag_params={
            "repository_id": requested_scope,
            "shared_history_scopes": ["cell-b"],
            "emit_self": False,
        },
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )

    # F2 positive-1: the dense leg received the requested ∪ shared UNION clause. A single
    # requested-scope equality here would hide the shared decision at the store boundary.
    assert store.where == {"$or": [{"repository_id": requested_scope}, {"repository_id": "cell-b"}]}

    # The implementation phase is the third agent phase (scope, ux_design, implement); the
    # real route resolved L1 structure for it, so the code candidates are eligible.
    implement_ids = served[2]
    assert "k-shared" in implement_ids  # F2 positive-2: the shared decision stayed retrievable
    assert "k-foreign" not in implement_ids  # F2 negative: a foreign private scope is excluded


def test_shared_decision_served_under_default_private_acl(tmp_path):
    """u7 (L60/F1/F2, R3): a genuine shared DECISION reaches construction under the NORMAL
    runner configuration — ``_resolve_rag_params`` defaults ``acl_scope`` to the private cell
    scope — so the shared-history gate no longer side-steps the ACL contract.

    The prior e2e probe supplied an explicit ``repository_id`` precisely to AVOID that default,
    and its "shared decision" was ``source_type="code"`` — it proved shared *structure* under an
    ACL-free config, not a shared *decision* under the normal one (the astra R3/F1-F2 finding).

    Here ONLY the explicit shared-history hint is passed. ``_resolve_rag_params`` therefore
    defaults both ``repository_id`` and ``acl_scope`` to the private cell scope, and the dense
    where-expression must carry BOTH unions: the requested ∪ shared REPOSITORY clause and the
    requested-ACL ∪ shared-ACL clause. The second is the F2/R3 repair: an explicitly shared
    repository scope authorizes that scope's own ACL namespace, so a shared decision carrying
    its own non-empty ACL is no longer hidden by an equality to the private cell ACL. A
    foreign private record (its own repository AND its own foreign ACL) is the negative
    control. The where-aware store honours the clause it is handed, so a regression of either
    union to a single equality makes the positive assertion fail at the store boundary.
    """
    import functools

    from agentic_dynamics.knowledge.retrieval import retrieve

    spec = load_spec(SPEC)
    private_scope = cell_scope(tmp_path)
    shared_scope = "cell-b"

    # A GENUINE shared decision: source_type ``decision`` (L2 history), in an explicitly shared
    # repository, carrying its OWN non-empty ACL (the shared scope's namespace).
    shared_decision = _scope_dense_hit(
        "k-shared-decision",
        "shared decision: use the websocket reload protocol",
        repository_id=shared_scope,
        acl_scope=shared_scope,
        source_type="decision",
        authority="measured",
    )
    # Negative control: a foreign private decision — its own repository AND a foreign ACL.
    foreign_decision = _scope_dense_hit(
        "k-foreign-decision",
        "foreign private decision: not for sharing",
        repository_id="cell-c",
        acl_scope="cell-c",
        source_type="decision",
        authority="measured",
    )
    # The private cell's own structure, eligible for the implementation phase's L1 layer.
    local_code = _scope_dense_hit(
        "k-local-code",
        "local code: websocket reload handler",
        repository_id=private_scope,
        acl_scope=private_scope,
        source_type="code",
    )
    store = _WhereAwareDenseStore([shared_decision, foreign_decision, local_code])

    served: list[list[str]] = []

    class _CapturingAugmented(_FakeAugmented):
        """A deterministic constructor that emits EXACTLY the evidence it received."""

        def __init__(self, prompt, evidence_ids):
            super().__init__(prompt)
            self.evidence_ids = list(evidence_ids)

    def construct_fn(request):
        ids = [unit.knowledge_id for unit in request.evidence]
        served.append(ids)
        return _CapturingAugmented("AUG", ids)

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        rag_augment=True,
        retrieve_fn=functools.partial(retrieve, dense_store=store, graph_client=None),
        construct_fn=construct_fn,
        # NO repository_id / acl_scope: the runner must default them to the private cell scope.
        rag_params={"shared_history_scopes": [shared_scope], "emit_self": False},
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )

    # Positive union (F2): the dense leg was handed the requested ∪ shared repository clause
    # AND the requested-ACL ∪ shared-ACL clause. Asserting both dimensions means a regression
    # of EITHER union to a single equality fails the gate — the exact astra R3 counterexample
    # (repository union AND acl_scope=private) is now impossible.
    where = store.where
    assert isinstance(where, dict) and "$and" in where, where
    repo_clauses = [
        clause
        for clause in where["$and"]
        if "$or" in clause and all("repository_id" in term for term in clause["$or"])
    ]
    acl_clauses = [
        clause
        for clause in where["$and"]
        if "$or" in clause and all("acl_scope" in term for term in clause["$or"])
    ]
    assert repo_clauses, where
    assert {term["repository_id"] for term in repo_clauses[0]["$or"]} == {
        private_scope,
        shared_scope,
    }
    assert acl_clauses, where
    assert {term["acl_scope"] for term in acl_clauses[0]["$or"]} == {private_scope, shared_scope}

    # The implementation phase (third agent phase) resolves the L2 history floor plus L1
    # structure, so the shared DECISION is eligible and the local code is too.
    implement_ids = served[2]
    assert "k-shared-decision" in implement_ids  # F2 positive: the shared decision was served
    assert "k-local-code" in implement_ids  # L1 structure for the implementation phase
    assert "k-foreign-decision" not in implement_ids  # foreign private ACL + repository excluded

    # The record is not merely resolved: the L2 history disposition names the served shared
    # decision, and the shared scope is recorded on the route — so the ledger shows what the
    # union actually served, not just that a union clause was built.
    implement = next(p for p in result.phases if p.phase == "implement")
    record = implement.to_dict()["context_route"]
    assert record["route_status"] == "resolved"
    assert shared_scope in record["shared_scopes"]
    l2_entry = next(layer for layer in record["layers"] if layer["layer"] == "L2")
    assert l2_entry["status"] == "served"
    assert "k-shared-decision" in l2_entry["evidence_ids"]
    assert "k-foreign-decision" not in l2_entry["evidence_ids"]


# ── Declared phase scope outranks the name/kind substring classifier (world models L60, u1 — A10-R1) ──


def test_expanded_implementation_phase_declared_scope_outranks_name(tmp_path):
    """u1 (L60/A10-R1): a phase's DECLARED ``scope`` beats the name/kind substring classifier.

    The att10 astra finding: the ``execute`` phase declares ``scope: implementation`` and expands
    via ``expand_from_plan``; the generated unit slice inherits that scope (``_unit_slice_def``),
    but the unit name ``execute__u2_projected_source_type_validated`` carries the incidental
    ``validat`` substring. ``classify_phase_role`` searches the whole name for verification
    markers BEFORE implementation markers, so on the pre-fix wiring the expanded implementation
    phase lost L1 structure (role ``verification``, no ``code`` in the retrieval prefilter).

    This gate drives the REAL ``run_workflow`` on an inline ``agent_task`` spec whose ``execute``
    phase declares ``scope: implementation`` + ``expand_from_plan``, with a captured
    ``retrieve_fn``. It would fail on the pre-fix wiring because ``classify_phase_role`` returns
    verification for the expanded unit (no ``code``) and the serialized route says
    ``verification`` — reverting the declared-scope pass fails both assertions. The genuine
    verification agent phase is the negative L1 control: even though both phases resolve L2
    history, only the declared implementation scope may pull ``code`` (L1 structure).
    """
    # A real git worktree: the expanded unit slice declares ``requires_deliverable``, so each
    # agent phase must leave a tree change (the fake agent writes one file per call).
    _git_init(tmp_path)
    # The plan names the exact unit the finding used: an implementation goal whose id carries
    # the verification-looking ``validated`` word.
    _write_units(
        tmp_path,
        {"units": [_unit("u2_projected_source_type_validated", goal="project the source type")]},
    )

    phases = [
        {
            "name": "execute",
            "kind": "agent",
            "scope": "implementation",
            "expand_from_plan": "notes/plan.units.json",
            "prompt": "unit {unit_id}: {unit_goal}",
        },
        # A genuine verification agent phase. NOTE: the per-step execution SCOPE_VOCABULARY
        # (research_readonly / implementation / review_readonly / proposal_write /
        # adversarial_readonly) is a DIFFERENT closed vocabulary from the routing ROLE values
        # (planning / implementation / verification / review / unknown); there is no
        # ``scope: verification``. The routing resolver therefore reads a declared execution
        # scope as a role hint ONLY when the string coincides with a role (``implementation``)
        # and otherwise falls through to the name classifier — which classifies this named
        # ``verify`` phase as role ``verification``. This is the negative L1 control: a genuine
        # verification phase, however expressed, must stay L1-free.
        {
            "name": "verify",
            "kind": "agent",
            "prompt": "verify the delivered work",
        },
    ]
    spec = ExperimentSpec(
        name="u1_declared_scope_synth",
        question="q",
        version="1",
        workflow=Workflow(
            kind="agent_task",
            params={"language": "python", "phases": phases},
        ),
        factors=[Factor("model", ["m"])],
        design="factorial",
    )

    seen: list[dict] = []

    class _TypedEvidence:
        """A served candidate carrying its real ``source_type`` (attribution observable)."""

        def __init__(self, cid, text, source_type):
            self.id = cid
            self.text = text
            self.authority = "source"
            self.source_type = source_type
            self.content_hash = f"ch:{cid}"
            self.token_count = len(text.split())

        def citation(self):
            return f"[K:{self.id}@abc:loc]"

    def retrieve_fn(**kwargs):
        seen.append(kwargs)
        return _FakeAttempt([_TypedEvidence("k1", "code evidence", "code")])

    def construct_fn(request):
        return _FakeAugmented("AUG")

    deliveries: list[int] = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        """A fake agent that writes a fresh file (the deliverable gate needs a tree change)."""
        deliveries.append(1)
        (Path(workdir) / f"delivered_{len(deliveries)}.txt").write_text("x\n")
        return _fake_agent()

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        rag_augment=True,
        retrieve_fn=retrieve_fn,
        construct_fn=construct_fn,
        run_agentic_fn=agent,
    )

    # The expanded agent phase is reached under its generated name (the test gate for the unit is
    # ``kind: test`` and bypasses the augmentation seam, so exactly the two agent phases call
    # retrieve_fn, in phase order: the expanded execute slice, then the verification phase).
    expanded_name = "execute__u2_projected_source_type_validated"
    expanded = next(p for p in result.phases if p.phase == expanded_name)
    assert len(seen) == 2  # the unit's test gate does not retrieve

    # (a) The declared implementation scope reached the ONE retrieval path: the expanded slice's
    # callback received ``code`` (L1 structure). On the pre-fix classifier this is verification
    # and ``code`` is absent — the finding's exact regression.
    assert "code" in seen[0]["source_types"]
    # (b) The serialized route is the phase's declared semantics, resolved (not a label, not a
    # named absence): role implementation with a real L1 disposition.
    record = expanded.to_dict()["context_route"]
    assert record["route_status"] == "resolved"
    assert record["role"] == "implementation"
    l1_entry = next(layer for layer in record["layers"] if layer["layer"] == "L1")
    assert "code" in l1_entry["source_types"]

    # Negative L1 control: the genuine verification phase (name-classified — the execution scope
    # vocabulary has no ``verification`` value) must stay L1-free: no ``code`` prefilter,
    # serialized role verification. This passes under both wirings, so it isolates the DECLARED
    # implementation scope as the thing that changed the expanded slice's route, not a blanket
    # "every agent phase gets L1".
    verify = next(p for p in result.phases if p.phase == "verify")
    verify_record = verify.to_dict()["context_route"]
    assert verify_record["route_status"] == "resolved"  # the L2 history floor is real material
    assert verify_record["role"] == "verification"
    assert "code" not in seen[1]["source_types"]
    assert all(layer["layer"] != "L1" for layer in verify_record["layers"])


# ── Declared execution scope -> routing role translation (world models L60, u1 — A11-R1) ─────


def _scope_synth_spec(phases: list[dict]) -> ExperimentSpec:
    """A minimal ``agent_task`` spec with inline agent phases (no deliverables, no gates)."""
    return ExperimentSpec(
        name="u1_scope_translation_synth",
        question="q",
        version="1",
        workflow=Workflow(kind="agent_task", params={"language": "python", "phases": phases}),
        factors=[Factor("model", ["m"])],
        design="factorial",
    )


class _ScopeTypedEvidence:
    """A retrieved candidate carrying its real ``source_type`` (attribution observable)."""

    def __init__(self, cid, text, source_type):
        self.id = cid
        self.text = text
        self.authority = "source"
        self.source_type = source_type
        self.content_hash = f"ch:{cid}"
        self.token_count = len(text.split())

    def citation(self):
        return f"[K:{self.id}@abc:loc]"


def test_declared_non_implementation_scope_translates_to_routing_role(tmp_path):
    """u1 (L60/A11-R1): a DECLARED non-implementation scope reaches the routing vocabulary.

    The att11 astra finding: the execution-scope vocabulary (``SCOPE_VOCABULARY``) and the
    routing-role vocabulary are different closed sets. ``workflow_runner`` used to pass the
    declared scope through and unconditionally DELETE the explicit ``role``/``phase_role``
    hints for every nonempty scope, so ``review_readonly`` / ``research_readonly`` /
    ``adversarial_readonly`` — which name no routing role — were silently re-classified by the
    incidental phase NAME. ``execution_scope_role`` now TRANSLATES the declared scope, and the
    names below deliberately supply no role semantics:

    (a)  ``scope=review_readonly`` + name ``collect``        -> role ``review``   (NO ``code``)
    (a2) ``scope=adversarial_readonly`` + name ``inspect``   -> role ``review``   (NO ``code``)
    (b)  ``scope=research_readonly`` + name ``gather``       -> role ``planning`` (``code``)

    Reverting the runner translation hunk name-classifies all three as ``unknown`` (no ``code``
    for any), failing (a)/(a2)/(b). The existing
    ``test_expanded_implementation_phase_declared_scope_outranks_name`` remains the
    declared-implementation positive control (declared implementation still outranks the
    incidental ``validat`` name and any run-global hint).
    """
    seen: list[dict] = []

    def retrieve_fn(**kwargs):
        seen.append(kwargs)
        return _FakeAttempt([_ScopeTypedEvidence("k1", "code evidence", "code")])

    def construct_fn(request):
        return _FakeAugmented("AUG")

    spec = _scope_synth_spec(
        [
            {"name": "collect", "kind": "agent", "scope": "review_readonly", "prompt": "collect"},
            {
                "name": "inspect",
                "kind": "agent",
                "scope": "adversarial_readonly",
                "prompt": "inspect",
            },
            {"name": "gather", "kind": "agent", "scope": "research_readonly", "prompt": "gather"},
        ]
    )

    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=tmp_path,
        commit=False,
        rag_augment=True,
        retrieve_fn=retrieve_fn,
        construct_fn=construct_fn,
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )

    assert len(seen) == 3  # one real retrieve per agent phase, in phase order
    by_phase = {p.phase: p for p in result.phases}

    # (a) review_readonly -> role review, L2 history only (no L1 structure).
    collect = by_phase["collect"].to_dict()["context_route"]
    assert collect["route_status"] == "resolved"
    assert collect["role"] == "review"
    assert "code" not in seen[0]["source_types"]

    # (a2) adversarial_readonly -> role review, L2 history only (no L1 structure).
    inspect = by_phase["inspect"].to_dict()["context_route"]
    assert inspect["route_status"] == "resolved"
    assert inspect["role"] == "review"
    assert "code" not in seen[1]["source_types"]

    # (b) research_readonly -> role planning, L1 structure IS requested.
    gather = by_phase["gather"].to_dict()["context_route"]
    assert gather["route_status"] == "resolved"
    assert gather["role"] == "planning"
    assert "code" in seen[2]["source_types"]


def test_unmapped_declared_scope_retains_explicit_role_hint(tmp_path):
    """u1 (L60/A11-R1): an UNMAPPED declared scope RETAINS an explicit role/phase_role hint.

    ``proposal_write`` is deliberately UNMAPPED in ``EXECUTION_SCOPE_ROLES``: assembling a
    proposal is an execution envelope, not an evidence-routing role. For such a scope the runner
    must NOT discard the phase's explicit semantic hint (the att11 regression) and must NOT
    inject the scope as a role. The name ``build_notes`` name-classifies as ``implementation``
    (it contains the ``build`` marker), so retention is directly observable: the serialized role
    is the HINT, never the name-derived ``implementation``.

    Both hint keys are exercised — ``role`` (run 1, ``review``) and ``phase_role`` (run 2,
    ``planning``). Pre-fix the runner deleted both keys for the nonempty ``proposal_write``
    scope, so both runs would record ``implementation`` and fail. The ``review`` run also proves
    the retained hint SHAPES retrieval (review resolves L2 only -> no ``code``), so retention is
    semantic, not a cosmetic record label.
    """
    seen: list[dict] = []

    def retrieve_fn(**kwargs):
        seen.append(kwargs)
        return _FakeAttempt([_ScopeTypedEvidence("k1", "code evidence", "code")])

    def construct_fn(request):
        return _FakeAugmented("AUG")

    def _run(rag_params: dict, workdir):
        return run_workflow(
            _scope_synth_spec(
                [
                    {
                        "name": "build_notes",
                        "kind": "agent",
                        "scope": "proposal_write",
                        "prompt": "build the notes",
                    }
                ]
            ),
            goal="g",
            model="m",
            workdir=workdir,
            commit=False,
            rag_augment=True,
            retrieve_fn=retrieve_fn,
            construct_fn=construct_fn,
            rag_params=rag_params,
            run_agentic_fn=lambda *a, **k: _fake_agent(),
        )

    # Run 1: explicit ``role`` hint. A review route is L2-only, so no ``code`` is requested.
    run1_dir = tmp_path / "run1"
    run1_dir.mkdir()
    result1 = _run({"role": "review"}, run1_dir)
    record1 = next(p for p in result1.phases if p.phase == "build_notes").to_dict()["context_route"]
    assert record1["route_status"] == "resolved"
    assert record1["role"] == "review"  # retained hint, NOT the name-derived implementation
    assert "code" not in seen[0]["source_types"]

    # Run 2: explicit ``phase_role`` hint — the other hint key resolves planning (L1 requested).
    run2_dir = tmp_path / "run2"
    run2_dir.mkdir()
    result2 = _run({"phase_role": "planning"}, run2_dir)
    record2 = next(p for p in result2.phases if p.phase == "build_notes").to_dict()["context_route"]
    assert record2["route_status"] == "resolved"
    assert record2["role"] == "planning"  # retained hint, NOT the name-derived implementation
    assert "code" in seen[1]["source_types"]
