"""Regression tests for the four instrumented ledger fields.

Covers the instrumentation gap closure (remediation step 3):
  - ``answer``/``explanation`` token split (opencode._parse_session_output)
  - ``confidence`` [H] execution-confidence signal (opencode.AgenticResult)
  - ``perturbation_strength`` + ``test_executed_success`` on story results
  - wiring of the independent test runner into the single-task path (run.py)
"""

import json
from pathlib import Path

from instrument.opencode import AgenticResult, _parse_session_output
from instrument.story import SessionResult, StoryResult
from instrument.workflow_runner import PhaseResult

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
