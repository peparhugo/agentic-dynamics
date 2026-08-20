from agentic_dynamics.legacy.recovery import SegmentClass, classify_trajectory_segments
from agentic_dynamics.legacy.trajectory import ReasoningTrajectory, TrajectoryStep


def _make_step(i, thought="", action="", tool_name=""):
    return TrajectoryStep(step_index=i, thought=thought, action=action, tool_name=tool_name, tokens_used=10)


class _CountingTrajectory(ReasoningTrajectory):
    """A trajectory that counts how many times its tool sequence is materialized."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tool_call_sequence_calls = 0

    def tool_call_sequence(self):
        self.tool_call_sequence_calls += 1
        return super().tool_call_sequence()


def test_identical_trajectories_not_recovery():
    steps = [
        _make_step(0, thought="designing", action="code", tool_name="write"),
        _make_step(1, thought="testing", action="tests", tool_name="bash"),
        _make_step(2, thought="fixing", action="fix", tool_name="edit"),
    ]

    baseline = ReasoningTrajectory(run_id="baseline", steps=steps)
    perturbed = ReasoningTrajectory(run_id="perturbed", steps=[_make_step(i, thought=s.thought, action=s.action, tool_name=s.tool_name) for i, s in enumerate(steps)])

    classifications = classify_trajectory_segments(baseline, perturbed)
    recovery_count = sum(1 for c in classifications if c.classification == SegmentClass.RECOVERY)

    assert recovery_count == 0, (
        f"Identical trajectories should NOT be classified as RECOVERY, got {recovery_count} recovery steps"
    )


def test_different_tool_sequence_is_recovery():
    baseline_steps = [
        _make_step(0, thought="designing", action="code", tool_name="write"),
        _make_step(1, thought="testing", action="tests", tool_name="bash"),
    ]
    perturbed_steps = [
        _make_step(0, thought="designing", action="code", tool_name="write"),
        _make_step(1, thought="wrong tool", action="wrong", tool_name="grep"),
    ]

    baseline = ReasoningTrajectory(run_id="baseline", steps=baseline_steps)
    perturbed = ReasoningTrajectory(run_id="perturbed", steps=perturbed_steps)

    classifications = classify_trajectory_segments(baseline, perturbed)
    assert len(classifications) == 2


def test_explicit_recovery_markers_detected():
    baseline_steps = [
        _make_step(0, thought="baseline", action="design", tool_name="write"),
    ]
    perturbed_steps = [
        _make_step(0, thought="me", action="let me explain why this works", tool_name="write"),
    ]

    baseline = ReasoningTrajectory(run_id="baseline", steps=baseline_steps)
    perturbed = ReasoningTrajectory(run_id="perturbed", steps=perturbed_steps)

    classifications = classify_trajectory_segments(baseline, perturbed)
    has_recovery = any(c.classification == SegmentClass.RECOVERY for c in classifications)
    assert has_recovery, "Explicit recovery markers should be detected"


def test_baseline_tool_sequence_materialized_once():
    """BUG-6: the baseline tool sequence must be materialized exactly once."""
    baseline_steps = [
        _make_step(0, thought="designing", action="code", tool_name="write"),
        _make_step(1, thought="testing", action="tests", tool_name="bash"),
    ]
    baseline = _CountingTrajectory(run_id="baseline", steps=baseline_steps)
    perturbed = ReasoningTrajectory(run_id="perturbed", steps=[
        _make_step(0, thought="designing", action="code", tool_name="write"),
        _make_step(1, thought="wrong tool", action="wrong", tool_name="grep"),
    ])

    classify_trajectory_segments(baseline, perturbed)
    assert baseline.tool_call_sequence_calls == 1
