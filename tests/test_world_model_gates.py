"""World-model loop v1 gates: the phase artifact gate + the committed-phase report emit.

Covers the two runner additions of 2026-09-21:

* ``requires_files`` — a phase REFUSES before spend when a declared artifact is absent
  (the world-model loop's plan gate: execute cannot run without ``notes/plan.md``);
* ``rag.emit_report`` — a committed phase ALSO emits the full report-variant record, so a
  loop's notes become retrievable knowledge, not only git files.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from agentic_dynamics.experiment.experiment_spec import load_spec
from agentic_dynamics.runtime import workflow_runner as wr

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
