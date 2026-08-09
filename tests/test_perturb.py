import pytest
import random
from instrument.perturb import build_operators


def test_remove_critical_constraint_removes_constraint():
    ops = build_operators()
    rng = random.Random(42)

    prompt = (
        "Build a REST API with JWT authentication.\n"
        "Requirements:\n"
        "- Must support rate limiting on all endpoints\n"
        "- Should include input validation\n"
        "- Must handle pagination\n"
    )
    result = ops["remove_critical_constraint"].apply_fn(prompt, 0.8, rng)

    assert result != prompt, "Constraint removal should modify the prompt"
    assert len(result) < len(prompt), f"Expected shorter result, got same length: {len(result)} == {len(prompt)}"
    assert "Build a REST API" in result, "Non-constraint text should be preserved"


def test_remove_critical_constraint_preserves_structure():
    ops = build_operators()
    rng = random.Random(100)

    prompt = (
        "Build a task management API.\n"
        "The API must use JWT authentication.\n"
        "All endpoints shall enforce input validation.\n"
        "The system should use PostgreSQL."
    )
    result = ops["remove_critical_constraint"].apply_fn(prompt, 0.5, rng)

    assert "Build a task management API" in result
    constraint_keywords = ["must", "shall", "should"]
    orig_count = sum(1 for kw in constraint_keywords if kw in prompt)
    result_count = sum(1 for kw in constraint_keywords if kw in result)
    assert result_count <= orig_count, (
        f"Expected fewer or equal constraints, got {result_count} vs {orig_count} original"
    )


def test_remove_critical_constraint_no_constraints_returns_same():
    ops = build_operators()
    rng = random.Random(42)

    prompt = "Build something simple."
    result = ops["remove_critical_constraint"].apply_fn(prompt, 0.8, rng)
    assert result == prompt or abs(len(result) - len(prompt)) < 10
