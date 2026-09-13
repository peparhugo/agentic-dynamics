"""Regression tests for the four instrumented ledger fields.

Covers the instrumentation gap closure (remediation step 3):
  - ``answer``/``explanation`` token split (opencode._parse_session_output)
  - ``confidence`` [H] execution-confidence signal (opencode.AgenticResult)
  - ``perturbation_strength`` + ``test_executed_success`` on story results
  - wiring of the independent test runner into the single-task path (run.py)
"""

import json
from pathlib import Path

import pytest

from agentic_dynamics.adapters.opencode import AgenticResult, _parse_session_output
from agentic_dynamics.measurement.efficiency import split_cost
from agentic_dynamics.runtime.queue_timings import timing_row
from agentic_dynamics.runtime.story import SessionResult, StoryResult
from agentic_dynamics.runtime.workflow_runner import AttemptRecord, PhaseResult

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parent.parent


# ── answer / explanation token split ──────────────────────────────────────────


def _synthetic_stdout() -> str:
    """A minimal two-step v2 opencode stream: one tool step, one prose step."""
    lines = [
        {"type": "step_start", "sessionID": "s", "part": {"type": "step-start"}},
        {"type": "tool_use", "part": {
            "type": "tool", "tool": "write",
            "state": {"status": "completed", "input": {}, "output": ""},
        }},
        {"type": "step_finish", "part": {
            "tokens": {"input": 100, "output": 50, "reasoning": 10}, "cost": 0.01,
        }},
        {"type": "step_start", "sessionID": "s", "part": {"type": "step-start"}},
        {"type": "text", "part": {"type": "text", "text": "Here is an explanation."}},
        {"type": "step_finish", "part": {
            "tokens": {"input": 20, "output": 30, "reasoning": 5}, "cost": 0.005,
        }},
    ]
    return "\n".join(json.dumps(line) for line in lines)


def test_answer_explanation_token_split():
    # Tool-call steps are the "answer" (deliverable); prose-only steps are the
    # "explanation". The split must partition the completion/output tokens.
    result = AgenticResult()
    _parse_session_output(_synthetic_stdout(), result)

    assert result.completion_tokens == 80
    assert result.answer_tokens == 50
    assert result.explanation_tokens == 30
    # Invariant: the two buckets are a partition of the output stream.
    assert result.answer_tokens + result.explanation_tokens == result.completion_tokens
    # Reasoning stays in its own channel — never folded into answer/explanation.
    assert result.reasoning_tokens == 15


def test_answer_explanation_split_zero_when_no_tool_calls():
    # A prose-only session attributes everything to explanation.
    lines = [
        {"type": "step_start", "sessionID": "s", "part": {"type": "step-start"}},
        {"type": "text", "part": {"type": "text", "text": "Just prose."}},
        {"type": "step_finish", "part": {
            "tokens": {"input": 20, "output": 30, "reasoning": 5}, "cost": 0.005,
        }},
    ]
    result = AgenticResult()
    _parse_session_output("\n".join(json.dumps(line) for line in lines), result)
    assert result.answer_tokens == 0
    assert result.explanation_tokens == 30


# ── confidence [H] derivation ────────────────────────────────────────────────


def test_confidence_zero_on_error():
    r = AgenticResult(error="Timeout after 300s")
    assert r.confidence == 0.0


def test_confidence_from_measured_tests():
    r = AgenticResult(tests_passed=3, tests_total=4)
    assert r.confidence == 0.75


def test_confidence_from_tool_success_fraction():
    r = AgenticResult(total_tool_calls=10, error_count=2)
    assert r.confidence == 0.8


def test_confidence_none_without_signal():
    r = AgenticResult()
    assert r.confidence is None


# ── story / workflow record wiring ───────────────────────────────────────────


def test_story_result_records_ledger_fields():
    sr = SessionResult(
        session_number=1,
        task_type="x",
        prompt="p",
        confidence=0.9,
        answer_tokens=100,
        explanation_tokens=40,
    )
    story = StoryResult(
        story_name="s",
        perturbation_condition="clean",
        perturbation_strength=0.0,
        test_executed_success=True,
        sessions=[sr],
    )
    d = story.to_dict()
    assert d["perturbation_strength"] == 0.0
    assert d["test_executed_success"] is True
    s0 = d["sessions"][0]
    assert s0["confidence"] == 0.9
    assert s0["answer_tokens"] == 100
    assert s0["explanation_tokens"] == 40


def test_phase_result_records_confidence_and_token_split():
    pr = PhaseResult(
        phase="build",
        kind="agent",
        status="ok",
        tokens={"in": 100, "out": 80, "reasoning": 15, "answer": 50, "explanation": 30, "total": 195},
        confidence=0.75,
    )
    d = pr.to_dict()
    assert d["confidence"] == 0.75
    assert d["tokens"]["answer"] == 50
    assert d["tokens"]["explanation"] == 30


# ── single-task path (run.py) ────────────────────────────────────────────────


def test_run_py_wires_independent_test_success():
    src = (ROOT / "scripts" / "run.py").read_text()
    assert "test_executed_success" in src
    assert "_verify_tests" in src
    assert "run_suite" in src
    assert "suite_succeeded" in src
    assert "answer_tokens" in src
    assert "explanation_tokens" in src
    assert "perturbation_strength" in src


# ── G-14: the independent-evaluator writer ───────────────────────────────────


def test_run_suite_stamps_independent_evaluator(monkeypatch, tmp_path):
    """``run_suite`` (the harness) is the independent evaluator → every verdict is stamped."""
    from agentic_dynamics.runtime import test_runner

    monkeypatch.setattr(
        test_runner, "_run_pytest",
        lambda *a, **k: {"runner": "pytest", "passed": 2, "failed": 0, "errors": 0,
                         "total": 2, "pass_rate": 1.0, "tail": "2 passed"},
    )
    result = test_runner.run_suite(tmp_path, "python")
    assert result["evaluator_independent"] is True
    assert test_runner.suite_succeeded(result) is True


def test_verify_cell_carries_the_evaluator_provenance(monkeypatch, tmp_path):
    """The batch verification record (verify_tests) carries G-14; a missing worktree stays unknown."""
    import importlib

    verify_tests = importlib.import_module("scripts.verify_tests")
    worktree = tmp_path / "wt"
    worktree.mkdir()
    monkeypatch.setattr(
        verify_tests, "run_suite",
        lambda *a, **k: {"runner": "pytest", "passed": 3, "failed": 0, "errors": 0,
                         "total": 3, "pass_rate": 1.0, "tail": "3 passed",
                         "evaluator_independent": True},
    )
    record = verify_tests.verify_cell(
        {"_file": "cell.json", "worktree": str(worktree), "language": "python"}, node="node"
    )
    assert record["test_executed_success"] is True
    assert record["evaluator_independent"] is True

    missing = verify_tests.verify_cell(
        {"_file": "cell.json", "worktree": "/does/not/exist", "language": "python"}, node="node"
    )
    assert missing.get("evaluator_independent") is None  # no verdict → unknown, never False


# ── G-40: first-token + lease timing writers ─────────────────────────────────


def test_first_token_at_stamped_on_the_first_streamed_event(monkeypatch, tmp_path):
    """The adapter records the wall-clock first streamed token; an empty stream stays None."""
    from agentic_dynamics.adapters import opencode

    transcript = "\n".join(json.dumps(e) for e in [
        {"type": "step_start", "part": {"type": "step-start"}},
        {"type": "text", "part": {"type": "text", "text": "the first output"}},
    ])

    class _Stream:
        stdout = transcript
        stderr = ""
        exit_code = 0
        timed_out = False

    def _fake_stream(cmd, *, workdir, timeout, on_line=None, watchdog=None):
        for line in transcript.splitlines():
            if on_line is not None:
                on_line(line)
        return _Stream()

    monkeypatch.setattr(opencode, "stream_subprocess", _fake_stream)
    monkeypatch.setattr(opencode, "_init_git_workdir", lambda *a, **k: None)

    result = opencode.run_opencode_agentic(
        "task", model="deepseek/deepseek-v4-pro", workdir=str(tmp_path), init_git=False
    )
    assert result.first_token_at is not None

    class _Empty:
        stdout = ""
        stderr = ""
        exit_code = 0
        timed_out = False

    monkeypatch.setattr(opencode, "stream_subprocess", lambda *a, **k: _Empty())
    empty = opencode.run_opencode_agentic(
        "task", model="deepseek/deepseek-v4-pro", workdir=str(tmp_path), init_git=False
    )
    assert empty.first_token_at is None


def test_timing_row_carries_leased_at_only_when_measured():
    row = timing_row({"cell_id": "c1"}, status="done", started_at=2.0, ended_at=3.0,
                     leased_at=1.5)
    assert row["leased_at"] == 1.5
    absent = timing_row({"cell_id": "c1"}, status="done", started_at=2.0, ended_at=3.0)
    assert "leased_at" not in absent  # no lease → absent, never 0


# ── G-41: the inference/orchestration split ──────────────────────────────────


def test_split_cost_is_null_preserving():
    assert split_cost(inference_usd=1.0, orchestration_usd=None) == {
        "cost_inference": 1.0, "cost_orchestration": None,
    }
    assert split_cost(inference_usd=None, orchestration_usd=0.5) == {
        "cost_inference": None, "cost_orchestration": 0.5,
    }
    assert split_cost(inference_usd=None, orchestration_usd=None) == {
        "cost_inference": None, "cost_orchestration": None,
    }


def test_attempt_record_defaults_keep_new_fields_unknown():
    d = AttemptRecord(attempt_id="a1", job_id="j", phase="scope").to_dict()
    for field in ("evaluator_independent", "leased_at", "first_token_at",
                  "cost_inference", "cost_orchestration"):
        assert d[field] is None, field
