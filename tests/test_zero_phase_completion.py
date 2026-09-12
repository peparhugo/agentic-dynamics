"""Step 2d: a resume whose completion set covered every phase is LOGICAL COMPLETION.

The final-checkpoint defect (2026-09-11): after the last checkpoint was approved, the resumed
invocation executed zero phases — every phase was already complete — which mapped to
``cancelled``, and the spec-status family union then read the family as ``failed``. A zero-phase
resume whose completion set covers every declared phase now reports ``already_complete`` and
``succeeded`` (the work WAS performed, by the parent); an aborted launch that ran nothing and
completed nothing still reads ``cancelled``.
"""

from __future__ import annotations

from agentic_dynamics.runtime.workflow_runner import WorkflowRunResult


def _result(**kwargs) -> WorkflowRunResult:
    return WorkflowRunResult(
        spec_name="s",
        spec_id="s@1",
        model="m",
        workdir="/tmp",
        goal="g",
        started_at="t",
        **kwargs,
    )


def test_already_complete_reads_succeeded_not_cancelled():
    result = _result(already_complete=True)
    assert result.ok is True
    assert result.state == "succeeded"
    assert result.to_dict()["already_complete"] is True


def test_aborted_launch_without_completion_stays_cancelled():
    result = _result()
    assert result.ok is False
    assert result.state == "cancelled"
    assert result.to_dict()["already_complete"] is False
