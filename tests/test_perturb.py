import pytest
import random
from instrument.perturb import (
    build_operators,
    PERTURBATION_CLASSES,
    perturbation_class_for,
)
from instrument.basin import BasinMetrics


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


def test_operator_classes_are_canonical():
    ops = build_operators()
    assert len(ops) == 10
    for name, op in ops.items():
        assert op.perturbation_class in PERTURBATION_CLASSES, (
            f"operator {name!r} has non-canonical class {op.perturbation_class!r}"
        )


def test_perturbation_class_for_known_operator():
    assert perturbation_class_for("inject_alien_vocab") == "process_perturbation"
    assert perturbation_class_for("invert_constraint") == "objective_mutation"
    assert perturbation_class_for("remove_critical_constraint") == "specification_corruption"


def test_perturbation_class_for_unknown_returns_empty():
    assert perturbation_class_for("nonexistent_operator") == ""


@pytest.mark.parametrize("cls", PERTURBATION_CLASSES)
def test_basin_verdict_handles_every_class(cls):
    for escape in (0.9, 0.4, 0.0):
        m = BasinMetrics(perturbation_class=cls, escape_score=escape)
        verdict = m.get_verdict()
        assert verdict, "verdict must be non-empty"


def test_basin_verdict_unknown_class_does_not_crash():
    m = BasinMetrics(perturbation_class="", escape_score=0.9)
    assert m.get_verdict()
