"""CAP test-runner wiring — `workflows/repository/cap_test_runner_wiring.yaml` (t2_wire_it).

Covers the named seam (docs/designs/current/cap_test_runner_wiring.md §1): an agent phase that
declares ``test_gate: true`` gets the independent test_runner's outcome recorded on
``PhaseResult.test_executed_success``, which ``attempt_facts/v1`` reads (kind-agnostically) to
mint ``phase_test_verified``. Guards honoured: the boolean comes ONLY from
``run_suite``/``suite_succeeded`` (never a self-report), and when the runner did not execute the
field stays ``None`` (null-not-zero — no defaulting).
"""

import subprocess
from pathlib import Path
from types import SimpleNamespace

from agentic_dynamics.control.facts import EvidenceItem, ReducerInput
from agentic_dynamics.control.reducers import attempt_facts_v1
from agentic_dynamics.experiment.experiment_spec import load_spec
from agentic_dynamics.runtime import workflow_runner
from agentic_dynamics.runtime.workflow_runner import run_workflow

SPEC = Path(__file__).resolve().parent.parent / "workflows" / "repository" / "control_room_portal.yaml"

NOW = "2026-08-25T00:00:00+00:00"

#: Hermetic test-runner fixtures (the shape ``test_runner.run_suite`` returns).
_PASSING = {"runner": "pytest", "passed": 3, "failed": 0, "errors": 0, "total": 3,
            "pass_rate": 1.0, "tail": "3 passed"}
_FAILING = {"runner": "pytest", "passed": 1, "failed": 2, "errors": 0, "total": 3,
            "pass_rate": 0.3333, "tail": "2 failed"}


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


def _spec_with_gate(gated_phase: str):
    """The real control_room_portal spec with ``test_gate`` added to one agent phase."""
    spec = load_spec(SPEC)
    spec.workflow.params["phases"] = [
        dict(p, test_gate=(p.get("name") == gated_phase))
        for p in spec.workflow.params["phases"]
    ]
    return spec


def _attempt_facts(run: dict) -> list:
    """Feed one run artifact through the REAL ``attempt_facts/v1`` reducer (the kb_produce_facts
    shape, minus the registry write)."""
    inp = ReducerInput(
        scope_path="org:test/workload:control_room_portal",
        scope_type="workload",
        scope_id="",
        repository_id="test",
        evidence=(EvidenceItem(source_type="workflow_run", evidence_id="ev:test", payload=run),),
        facts=(),
        now=NOW,
        source_revision="test",
    )
    return attempt_facts_v1(inp)


def _verified_value(facts, phase: str) -> str | None:
    for f in facts:
        if f.predicate == "phase_test_verified" and f.subject_id == phase:
            return f.value
    return None


# ── Runner-outcome present / absent → field True / False / None ──


def test_agent_phase_without_gate_keeps_test_executed_success_none(tmp_path, monkeypatch):
    """An un-gated agent phase stays ``None`` (never a default) — no phase_test_verified fact."""
    monkeypatch.setattr(workflow_runner, "run_suite", lambda *a, **k: _PASSING)
    spec = load_spec(SPEC)
    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                          run_agentic_fn=lambda *a, **k: _fake_agent())
    implement = next(p for p in result.phases if p.phase == "implement")
    assert implement.kind == "agent"
    assert implement.test_executed_success is None
    facts = _attempt_facts(result.to_dict())
    assert _verified_value(facts, "implement") is None    # agent phase: no gate → no fact
    assert _verified_value(facts, "verify") == "true"     # test-kind phase: unchanged, still bool


def test_agent_phase_with_gate_records_passing_suite(tmp_path, monkeypatch):
    """Gate + passing runner → the attempt carries ``True``; the reducer mints ``"true"``."""
    monkeypatch.setattr(workflow_runner, "run_suite", lambda *a, **k: _PASSING)
    spec = _spec_with_gate("implement")
    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                          run_agentic_fn=lambda *a, **k: _fake_agent())
    implement = next(p for p in result.phases if p.phase == "implement")
    assert implement.kind == "agent"
    assert implement.test_executed_success is True
    assert implement.tests_passed == 3
    assert implement.tests_total == 3
    assert implement.to_dict()["test_executed_success"] is True  # survives serialization
    facts = _attempt_facts(result.to_dict())
    assert _verified_value(facts, "implement") == "true"


def test_agent_phase_with_gate_records_failing_suite(tmp_path, monkeypatch):
    """Gate + failing runner → the attempt carries ``False``, the phase fails, and the reducer
    mints ``"false"`` — the honest independent verdict, never a self-report."""
    monkeypatch.setattr(workflow_runner, "run_suite", lambda *a, **k: _FAILING)
    spec = _spec_with_gate("implement")
    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                          run_agentic_fn=lambda *a, **k: _fake_agent())
    implement = next(p for p in result.phases if p.phase == "implement")
    assert implement.test_executed_success is False
    assert implement.status == "failed"
    assert implement.error           # the suite tail is recorded, like the test-kind branch
    assert result.ok is False
    assert [p.phase for p in result.phases] == ["scope", "ux_design", "implement"]  # stopped
    facts = _attempt_facts(result.to_dict())
    assert _verified_value(facts, "implement") == "false"


def test_gate_skips_when_agent_phase_failed(tmp_path, monkeypatch):
    """A gate does not run over an already-failed agent phase — the field stays ``None``."""
    calls = []
    monkeypatch.setattr(workflow_runner, "run_suite",
                        lambda *a, **k: calls.append(1) or _PASSING)
    spec = _spec_with_gate("scope")  # gate the FIRST agent phase
    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, commit=False,
                          run_agentic_fn=lambda *a, **k: _fake_agent(ok=False, error="boom"))
    scope = result.phases[0]
    assert scope.status == "failed"
    assert scope.test_executed_success is None
    assert calls == []  # the runner never executed — null-not-zero, no fabrication
    facts = _attempt_facts(result.to_dict())
    assert _verified_value(facts, "scope") is None


# ── Commit gate interaction ────────────────────────────────────


def test_gate_failure_skips_the_phase_commit(tmp_path, monkeypatch):
    """A failing gate fails the phase → no ``[workflow] implement`` commit (same as test-kind)."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    monkeypatch.setattr(workflow_runner, "run_suite", lambda *a, **k: _FAILING)
    spec = _spec_with_gate("implement")

    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        calls.append(prompt)
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / f"{len(calls)}.md").write_text(str(len(calls)))  # unique → diff
        return _fake_agent()

    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path, run_agentic_fn=agent)
    implement = next(p for p in result.phases if p.phase == "implement")
    assert implement.status == "failed"
    assert implement.commit_hash == ""
    log = subprocess.run(["git", "log", "--oneline"], cwd=tmp_path,
                         capture_output=True, text=True)
    assert "[workflow] implement" not in log.stdout


# ── End-to-end re-derivation (spec VERIFY: one real workflow phase) ──


def test_real_re_derive_agent_phase_carries_bool(tmp_path):
    """A REAL test_runner run on a gated agent phase → the REAL reducer mints the bool.

    The re-derivation proof the spec asks for: the phase gate (real ``run_suite`` against a real
    pytest suite in a real git worktree, only the LLM stubbed) records the outcome on the
    attempt, and ``attempt_facts/v1`` now carries ``phase_test_verified`` for an agent phase
    where the pre-wiring code stamped ``None``.
    """
    (tmp_path / "app.py").write_text("def add(a, b):\n    return a + b\n")
    (tmp_path / "test_app.py").write_text("from app import add\n\ndef test_add():\n    assert add(1, 2) == 3\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=tmp_path, check=True)

    spec = _spec_with_gate("implement")
    result = run_workflow(spec, goal="g", model="m", workdir=tmp_path,
                          run_agentic_fn=lambda *a, **k: _fake_agent())

    implement = next(p for p in result.phases if p.phase == "implement")
    assert implement.kind == "agent"
    assert implement.test_executed_success is True  # the real independent verdict

    facts = _attempt_facts(result.to_dict())
    assert _verified_value(facts, "implement") == "true"
