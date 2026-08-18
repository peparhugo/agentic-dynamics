import hashlib

import pytest
import random
from instrument.perturb import (
    ALIEN_VOCABULARIES,
    PERTURBATION_CLASSES,
    build_operators,
    derive_seed,
    perturb_prompt,
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


def test_insert_contradiction_first_matching_domain_wins():
    """BUG-5: the first matching domain must win, not the last.

    The prompt matches both "api" (first in iteration order) and "database"
    (second). The loop must exit on the first match so the injected contradiction
    is drawn from the "api" pairs, never "database".
    """
    ops = build_operators()
    rng = random.Random(0)

    prompt = "Build an API backed by a PostgreSQL database. Use REST endpoints."
    result = ops["insert_contradiction"].apply_fn(prompt, 0.5, rng)

    api_signatures = ("stateless", "GraphQL", "versioned via URL prefix", "per-IP", "XML")
    db_signatures = ("3NF", "denormalized", "MongoDB", "eventual consistency")

    assert any(sig in result for sig in api_signatures), (
        "contradiction should be drawn from the first-matching 'api' domain"
    )
    assert not any(sig in result for sig in db_signatures), (
        "contradiction must not come from the later 'database' domain"
    )


@pytest.mark.parametrize("cls", PERTURBATION_CLASSES)
def test_basin_verdict_handles_every_class(cls):
    for escape in (0.9, 0.4, 0.0):
        m = BasinMetrics(perturbation_class=cls, escape_score=escape)
        verdict = m.get_verdict()
        assert verdict, "verdict must be non-empty"


def test_basin_verdict_unknown_class_does_not_crash():
    m = BasinMetrics(perturbation_class="", escape_score=0.9)
    assert m.get_verdict()


# ── Regression tests: operator invariants (post-fix) ──

# Parametrize over the live registry so a newly added operator is covered
# automatically by the determinism / no-op / smoke tests below.
_OPERATOR_NAMES = sorted(build_operators())

# A representative prompt that exercises every operator: tech terms
# (alien_vocab), constraint sentences (invert/remove_critical_constraint),
# and section headers (reverse_causality).
_SAMPLE_PROMPT = (
    "Build a REST API with JWT authentication.\n"
    "Requirements:\n"
    "- Must support rate limiting on all endpoints.\n"
    "- Should include input validation.\n"
    "- Must handle pagination.\n"
    "Output format: JSON responses."
)


@pytest.mark.parametrize("op_name", _OPERATOR_NAMES)
def test_determinism_same_seed_same_output(op_name):
    """The same (prompt, operator, strength, seed) must yield the same prompt."""
    out1, _ = perturb_prompt(_SAMPLE_PROMPT, op_name, strength=0.5, rng_seed=7)
    out2, _ = perturb_prompt(_SAMPLE_PROMPT, op_name, strength=0.5, rng_seed=7)
    assert out1 == out2


def test_cross_model_same_cell_same_seed():
    """A cell's seed is a pure function of (task, operator, strength, seed_variant).

    derive_seed takes no model argument, so two models running the same cell get
    the same seed. We also lock the exact formula so any accidental change to
    the seed contract fails the test.
    """
    task = "Build a REST API"
    operator = "invert_constraint"
    strength = 0.5
    variant = 0

    seed = derive_seed(task, operator, strength, variant)
    expected = int(
        hashlib.sha256(
            f"{task}|{operator}|{strength}|{variant}".encode("utf-8")
        ).hexdigest()[:8],
        16,
    )
    assert seed == expected
    assert seed == derive_seed(task, operator, strength, variant)


def test_seed_variant_deviates_starting_point():
    """A deviated starting point (new seed_variant) yields a distinct seed.

    repetition is deliberately NOT a seed input, so re-measuring a cell
    reproduces the same starting point (see test_cross_model_same_cell_same_seed
    and test_determinism_same_seed_same_output), while each seed_variant level
    yields a distinct seed — and therefore a distinct perturbed prompt for any
    seed-sensitive operator — measured against the same baseline.
    """
    task = "Build a REST API with JWT authentication."
    op = "invert_constraint"
    strength = 0.5

    variants = [derive_seed(task, op, strength, v) for v in range(4)]
    assert len(set(variants)) == 4  # every variant yields a distinct starting point


@pytest.mark.parametrize("op_name", _OPERATOR_NAMES)
def test_strength_zero_is_noop(op_name):
    """strength <= 0.0 must return the base prompt unchanged (no minimum perturb)."""
    out, rec = perturb_prompt(_SAMPLE_PROMPT, op_name, strength=0.0, rng_seed=42)
    assert out == _SAMPLE_PROMPT
    assert rec.noop_reason == "strength 0.0 (no-op)"


def test_alien_vocab_injects_cross_domain_terms():
    """The main path must substitute ALIEN_VOCABULARIES terms, not same-domain synonyms."""
    base = "Build a REST API. The api endpoint uses a database server with a cache."
    out, rec = perturb_prompt(base, "inject_alien_vocab", strength=0.5, rng_seed=42)

    assert rec.vocab_domain in ALIEN_VOCABULARIES
    alien_words = ALIEN_VOCABULARIES[rec.vocab_domain]
    assert any(word in out for word in alien_words)
    assert rec.injected_tokens
    assert all(tok in alien_words for tok in rec.injected_tokens)


def test_reverse_causality_no_duplication():
    """The task description must appear exactly once at every strength."""
    task_sentence = "Build a REST API with JWT authentication."
    base = (
        task_sentence + "\n"
        "Requirements:\n"
        "- Must support rate limiting.\n"
        "- Should include input validation.\n"
        "Output format: JSON responses."
    )
    for strength in (0.1, 0.5, 0.8, 1.0):
        out, _ = perturb_prompt(base, "reverse_causality", strength=strength, rng_seed=42)
        assert out.count(task_sentence) == 1, f"task duplicated at strength {strength}"


@pytest.mark.parametrize("op_name", _OPERATOR_NAMES)
def test_operator_smoke(op_name):
    """At strength 0.5 every operator yields non-empty output that differs from base,
    with a canonical perturbation class."""
    ops = build_operators()
    out, rec = perturb_prompt(_SAMPLE_PROMPT, op_name, strength=0.5, rng_seed=42)

    assert out, "perturbed prompt must be non-empty"
    assert out != _SAMPLE_PROMPT, "strength 0.5 must perturb the prompt"
    assert rec.perturbation_class in PERTURBATION_CLASSES
    assert rec.perturbation_class == ops[op_name].perturbation_class
