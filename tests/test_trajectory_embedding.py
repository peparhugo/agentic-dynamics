"""Tests for trajectory embedding integration with EmbeddingClient.

Verifies that the trajectory.py module correctly uses the new
EmbeddingClient for semantic distance computation instead of
the old dreamlab/recall fallback.
"""

import socket

import pytest

from agentic_dynamics.legacy.trajectory import (
    ReasoningTrajectory,
    TrajectoryStep,
    _content_distance,
    _embedding_distance,
    compute_trajectory_distance,
)

try:
    socket.create_connection(("localhost", 11434), timeout=2).close()
    _OLLAMA_OK = True
except Exception:
    _OLLAMA_OK = False

pytestmark = [
    pytest.mark.external,
    pytest.mark.skipif(not _OLLAMA_OK, reason="Ollama not available on localhost:11434"),
]


def make_trajectory(run_id, actions):
    traj = ReasoningTrajectory(run_id=run_id, model="test-model")
    for i, action in enumerate(actions):
        traj.add_step(TrajectoryStep(step_index=i, action=action))
    return traj


class TestEmbeddingDistance:
    def test_returns_float_with_embeddings(self):
        baseline = make_trajectory("b", [
            "Build a static site generator in TypeScript",
            "Add WebSocket live reload support",
        ])
        perturbed = make_trajectory("p", [
            "Construct a passive web compilation engine in ECMAScript derivative",
            "Implement bidirectional connection reinitialization protocol",
        ])
        dist = _embedding_distance(baseline, perturbed, 2)
        assert dist is not None
        assert 0.0 <= dist <= 1.0

    def test_semantically_identical_is_low(self):
        baseline = make_trajectory("b", [
            "Create a REST API with Flask and JWT authentication",
        ])
        perturbed = make_trajectory("p", [
            "Build a RESTful web service using Flask framework with JWT-based auth",
        ])
        dist = _embedding_distance(baseline, perturbed, 1)
        assert dist is not None
        assert dist < 0.3

    def test_semantically_different_is_higher(self):
        baseline = make_trajectory("b", [
            "Implement a Python web scraper",
        ])
        perturbed = make_trajectory("p", [
            "Write a quantum computing simulation in Rust",
        ])
        dist = _embedding_distance(baseline, perturbed, 1)
        assert dist is not None
        assert dist > 0.2

    def test_empty_trajectories_returns_zero(self):
        baseline = ReasoningTrajectory(run_id="empty1")
        perturbed = ReasoningTrajectory(run_id="empty2")
        dist = _embedding_distance(baseline, perturbed, 0)
        assert dist == 0.0

    def test_single_step_comparison(self):
        baseline = make_trajectory("b", ["write a python function"])
        perturbed = make_trajectory("p", ["implement a python method"])
        dist = _embedding_distance(baseline, perturbed, 1)
        assert dist is not None
        assert 0.0 <= dist <= 1.0

    def test_multi_step_averaging(self):
        baseline = make_trajectory("b", [
            "read the requirements",
            "plan the architecture",
            "write the implementation",
        ])
        perturbed = make_trajectory("p", [
            "review the specification",
            "design the system",
            "code the solution",
        ])
        dist = _embedding_distance(baseline, perturbed, 3)
        assert dist is not None
        assert 0.0 <= dist <= 1.0


class TestContentDistance:
    def test_upgraded_to_use_embeddings(self):
        baseline = make_trajectory("b", [
            "create a web framework",
        ])
        perturbed = make_trajectory("p", [
            "build a web library",
        ])
        dist = _content_distance(baseline, perturbed)
        assert 0.0 <= dist <= 1.0

    def test_falls_back_when_no_actions(self):
        baseline = make_trajectory("b", [""])
        perturbed = make_trajectory("p", [""])
        dist = _content_distance(baseline, perturbed)
        assert dist == 0.0


class TestComputeTrajectoryDistance:
    def test_full_pipeline_with_embeddings(self):
        baseline = make_trajectory("b", [
            "Build a distributed web crawler in Python",
            "Add rate limiting and retry logic",
            "Implement URL frontier with priority queues",
        ])
        perturbed = make_trajectory("p", [
            "Construct a distributed web spider application in Python",
            "Integrate throttling and retry mechanisms",
            "Develop URL frontier using heap-based priority queues",
        ])
        dist = compute_trajectory_distance(baseline, perturbed)
        assert 0.0 <= dist <= 1.0

    def test_empty_trajectories_returns_zero(self):
        a = ReasoningTrajectory(run_id="a")
        b = ReasoningTrajectory(run_id="b")
        dist = compute_trajectory_distance(a, b)
        assert dist == 0.0

    def test_identical_trajectories_are_close(self):
        actions = ["build an API", "add tests", "refactor"]
        a = make_trajectory("a", actions)
        b = make_trajectory("b", actions)
        dist = compute_trajectory_distance(a, b)
        assert dist < 0.3

    def test_tool_sequence_included(self):
        a = make_trajectory("a", ["step1", "step2", "step3"])
        for i, tool in enumerate(["read", "write", "bash"]):
            a.steps[i].tool_name = tool

        b = make_trajectory("b", ["step1", "step2", "step3"])
        for i, tool in enumerate(["write", "bash", "grep"]):
            b.steps[i].tool_name = tool

        dist = compute_trajectory_distance(a, b)
        assert 0.0 <= dist <= 1.0


class TestTrajectoryClasses:
    def test_step_to_dict_truncates(self):
        long_text = "x" * 1000
        step = TrajectoryStep(step_index=0, thought=long_text, action=long_text)
        d = step.to_dict()
        assert len(d["thought"]) <= 500
        assert len(d["action"]) <= 500

    def test_trajectory_tool_call_sequence(self):
        traj = ReasoningTrajectory(run_id="test")
        traj.add_step(TrajectoryStep(step_index=0, tool_name="read"))
        traj.add_step(TrajectoryStep(step_index=1, tool_name="write"))
        traj.add_step(TrajectoryStep(step_index=2))
        assert traj.tool_call_sequence() == ["read", "write"]

    def test_trajectory_step_count(self):
        traj = ReasoningTrajectory(run_id="test")
        assert traj.step_count() == 0
        traj.add_step(TrajectoryStep(step_index=0))
        traj.add_step(TrajectoryStep(step_index=1))
        assert traj.step_count() == 2
