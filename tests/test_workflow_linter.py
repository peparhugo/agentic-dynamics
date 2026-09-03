"""Semantic-rule tests for workflows/lint_workflow.py (a1).

The authoring contract's SEMANTIC half (Wave 3, a1): the linter validates the
schema fields AND the rules a JSON Schema alone cannot express. Every mandated
violation is rejected with a STABLE NAMED error: mutating-without-verification,
promotion-without-gates, unbound-gate, prompt-as-evidence, plus authored-status,
unknown-step-kind, and missing-concurrency. A clean workflow passes with zero
errors. The historical 181-spec corpus (an ExperimentSpec document kind) is
untouched and is never linted as a workflow-v1 definition.
"""

import json
from pathlib import Path

import pytest

from workflows import lint_workflow as lw

_CORPUS_SPEC = (
    Path(__file__).resolve().parent.parent
    / "workflows"
    / "repository"
    / "authoring_product_aio.yaml"
)


def _agent_step(step_id="implement", **overrides) -> dict:
    step = {"id": step_id, "kind": "agent", "executor": "agent", "scope": "implementation"}
    step.update(overrides)
    return step


def _gate_step(step_id="verify", **overrides) -> dict:
    step = {"id": step_id, "kind": "gate", "executor": "test"}
    step.update(overrides)
    return step


def _workflow(steps, promotion=None, **spec_overrides) -> dict:
    spec = {
        "baseRef": "main",
        "workspace": {"mode": "isolated"},
        "concurrency": {"group": "wf", "policy": "serial"},
        "steps": steps,
    }
    if promotion is not None:
        spec["promotion"] = promotion
    spec.update(spec_overrides)
    return {
        "apiVersion": "agentic-dynamics.io/v1",
        "kind": "Workflow",
        "metadata": {"name": "wf", "revision": "1"},
        "spec": spec,
    }


def _canonical() -> dict:
    """The clean positive case: one mutating agent step, a test gate bound to its
    candidate, and a promotion that requires the gate."""
    return _workflow(
        steps=[_agent_step(), _gate_step("verify", needs=["implement"], candidateFrom="implement")],
        promotion={
            "candidateFrom": "implement",
            "strategy": "squash-merge",
            "requiredGates": ["verify"],
        },
    )


def test_clean_canonical_workflow_passes_with_no_errors():
    report = lw.lint(_canonical())
    assert report.ok
    assert report.findings == []


def test_clean_approval_shape_passes():
    """An approval checkpoint is a valid gate; requiredGates may name it."""
    document = _workflow(
        steps=[
            _agent_step(),
            _gate_step("verify", needs=["implement"], candidateFrom="implement"),
            {
                "id": "approve",
                "kind": "approval",
                "executor": "human",
                "needs": ["verify"],
                "candidateFrom": "implement",
            },
        ],
        promotion={
            "candidateFrom": "implement",
            "strategy": "squash-merge",
            "requiredGates": ["verify", "approve"],
        },
    )
    assert lw.lint(document).ok


def test_clean_inline_blocking_gate_counts_as_verification():
    """A mutating step with a blocking inline gate is self-verified."""
    document = _workflow(
        steps=[
            _agent_step(gate={"blocking": True, "executor": "test"}),
        ]
    )
    report = lw.lint(document)
    assert report.ok
    assert not report.has(lw.MUTATING_WITHOUT_VERIFICATION)


def test_clean_research_shape_requires_no_promotion():
    """A read-only research step is not mutating and needs no promotion."""
    document = _workflow(
        steps=[
            {"id": "survey", "kind": "agent", "executor": "agent", "scope": "research_readonly"},
        ],
        workspace={"mode": "readonly"},
    )
    assert lw.lint(document).ok


# --------------------------------------------------------------------------- #
# The seven mandated rejections
# --------------------------------------------------------------------------- #
def test_rejects_authored_operational_status():
    for location in (
        {"status": "completed"},
        {"metadata": {"name": "wf", "revision": "1", "status": "running"}},
        {
            "spec": {
                "baseRef": "main",
                "concurrency": {"group": "g", "policy": "serial"},
                "workspace": {"mode": "isolated"},
                "steps": [_agent_step()],
                "status": "ok",
            }
        },
    ):
        document = {"apiVersion": "agentic-dynamics.io/v1", "kind": "Workflow"}
        document.update(location)
        report = lw.lint(document)
        assert report.has(lw.AUTHORED_STATUS)
        finding = next(f for f in report.findings if f.code == lw.AUTHORED_STATUS)
        assert finding.path.endswith("status")


def test_rejects_unknown_step_kind_with_named_error():
    document = _workflow(steps=[_agent_step(kind="telepath")])
    report = lw.lint(document)
    assert report.has(lw.UNKNOWN_STEP_KIND)
    assert any(f.code == lw.UNKNOWN_STEP_KIND for f in report.findings)


def test_rejects_missing_concurrency_policy_with_named_error():
    document = _workflow(steps=[_agent_step()])
    del document["spec"]["concurrency"]
    assert lw.lint(document).has(lw.MISSING_CONCURRENCY)
    document = _workflow(steps=[_agent_step()], concurrency={"group": "wf"})
    assert lw.lint(document).has(lw.MISSING_CONCURRENCY)


def test_rejects_mutating_step_without_downstream_verification():
    document = _workflow(steps=[_agent_step()])
    report = lw.lint(document)
    assert report.has(lw.MUTATING_WITHOUT_VERIFICATION)
    finding = next(f for f in report.findings if f.code == lw.MUTATING_WITHOUT_VERIFICATION)
    assert "implement" in finding.message


def test_mutating_steps_are_all_covered_by_one_terminal_gate():
    """A linear multi-step wave (like the corpus shape) is verified by a gate on
    the final candidate, which builds on every upstream step."""
    document = _workflow(
        steps=[
            _agent_step("setup"),
            _agent_step("build", needs=["setup"]),
            _gate_step("verify", needs=["setup", "build"], candidateFrom="build"),
        ],
        promotion={
            "candidateFrom": "build",
            "strategy": "squash-merge",
            "requiredGates": ["verify"],
        },
    )
    assert lw.lint(document).ok


def test_parallel_mutation_branch_without_gate_is_rejected():
    """A second mutating branch a terminal gate does not cover is flagged."""
    document = _workflow(
        steps=[
            _agent_step("left"),
            _agent_step("right"),
            _gate_step("verify", candidateFrom="left", needs=["left"]),
        ],
        promotion={
            "candidateFrom": "left",
            "strategy": "squash-merge",
            "requiredGates": ["verify"],
        },
    )
    report = lw.lint(document)
    assert report.has(lw.MUTATING_WITHOUT_VERIFICATION)
    assert any(
        "right" in f.message for f in report.findings if f.code == lw.MUTATING_WITHOUT_VERIFICATION
    )


def test_non_blocking_inline_gate_does_not_verify():
    document = _workflow(steps=[_agent_step(gate={"blocking": False, "executor": "test"})])
    assert lw.lint(document).has(lw.MUTATING_WITHOUT_VERIFICATION)


def test_rejects_promotion_without_required_gates():
    document = _workflow(
        steps=[_agent_step(), _gate_step("verify", needs=["implement"], candidateFrom="implement")],
        promotion={
            "candidateFrom": "implement",
            "strategy": "squash-merge",
            "requiredGates": ["implement"],
        },
    )
    report = lw.lint(document)
    assert report.has(lw.PROMOTION_WITHOUT_GATES)
    assert any(f.code == lw.PROMOTION_WITHOUT_GATES for f in report.findings)


def test_rejects_gate_not_bound_to_a_candidate():
    """A gate step that resolves no candidate sha is an unbound gate."""
    document = _workflow(
        steps=[_agent_step("research", scope="research_readonly"), _gate_step("judge")]
    )
    report = lw.lint(document)
    assert report.has(lw.UNBOUND_GATE)
    assert any("judge" in f.message for f in report.findings if f.code == lw.UNBOUND_GATE)


def test_rejects_ambiguous_gate_without_candidate_from():
    """A gate whose needs-closure reaches multiple mutating steps must name the
    candidate it gates via candidateFrom."""
    document = _workflow(
        steps=[
            _agent_step("a"),
            _agent_step("b"),
            _gate_step("verify", needs=["a", "b"]),
        ]
    )
    report = lw.lint(document)
    assert report.has(lw.UNBOUND_GATE)
    assert any("candidateFrom" in f.message for f in report.findings if f.code == lw.UNBOUND_GATE)


def test_rejects_candidate_from_naming_a_non_producing_step():
    document = _workflow(
        steps=[
            _agent_step("a"),
            _gate_step("verify", candidateFrom="a"),
            _gate_step("judge", candidateFrom="verify", needs=["verify"]),
        ]
    )
    report = lw.lint(document)
    assert report.has(lw.UNBOUND_GATE)
    assert any("verify" in f.message for f in report.findings if f.code == lw.UNBOUND_GATE)


def test_rejects_inline_gate_on_a_step_that_produces_no_candidate():
    document = _workflow(
        steps=[
            {
                "id": "survey",
                "kind": "agent",
                "scope": "research_readonly",
                "gate": {"executor": "test"},
            }
        ]
    )
    assert lw.lint(document).has(lw.UNBOUND_GATE)


def test_rejects_prompt_text_as_sole_gate_evidence():
    """A required gate whose only 'evidence' is prompt text (no machine executor)
    is prompt-as-evidence."""
    document = _workflow(
        steps=[
            _agent_step(),
            {
                "id": "review",
                "kind": "gate",
                "needs": ["implement"],
                "candidateFrom": "implement",
                "prompt": "Read the diff carefully and judge whether it is correct.",
            },
        ],
        promotion={
            "candidateFrom": "implement",
            "strategy": "squash-merge",
            "requiredGates": ["review"],
        },
    )
    report = lw.lint(document)
    assert report.has(lw.PROMPT_AS_EVIDENCE)
    assert all(f.code == lw.PROMPT_AS_EVIDENCE for f in report.findings)


def test_rejects_llm_executor_gate_as_prompt_evidence():
    """A bound gate run by an agent executor produces prose, not evidence."""
    document = _workflow(
        steps=[
            _agent_step(),
            _gate_step("review", executor="agent", needs=["implement"], candidateFrom="implement"),
        ],
        promotion={
            "candidateFrom": "implement",
            "strategy": "squash-merge",
            "requiredGates": ["review"],
        },
    )
    assert lw.lint(document).has(lw.PROMPT_AS_EVIDENCE)


def test_machine_executor_gate_is_not_prompt_evidence():
    document = _workflow(
        steps=[
            _agent_step(),
            _gate_step(
                "review", executor="command", needs=["implement"], candidateFrom="implement"
            ),
        ],
        promotion={
            "candidateFrom": "implement",
            "strategy": "squash-merge",
            "requiredGates": ["review"],
        },
    )
    assert not lw.lint(document).has(lw.PROMPT_AS_EVIDENCE)


def test_approval_step_is_legitimate_human_gate_evidence():
    document = _workflow(
        steps=[
            _agent_step(),
            {
                "id": "approve",
                "kind": "approval",
                "executor": "human",
                "needs": ["implement"],
                "candidateFrom": "implement",
            },
        ],
        promotion={
            "candidateFrom": "implement",
            "strategy": "squash-merge",
            "requiredGates": ["approve"],
        },
    )
    assert lw.lint(document).ok


# --------------------------------------------------------------------------- #
# Additional structural rules the linter enforces
# --------------------------------------------------------------------------- #
def test_rejects_duplicate_step_ids():
    document = _workflow(steps=[_agent_step("dup"), _agent_step("dup")])
    assert lw.lint(document).has(lw.DUPLICATE_STEP_ID)


def test_rejects_unknown_step_references():
    document = _workflow(
        steps=[_agent_step(), _gate_step("verify", needs=["ghost"], candidateFrom="missing")]
    )
    report = lw.lint(document)
    assert report.has(lw.UNKNOWN_STEP_REFERENCE)


def test_rejects_dependency_cycle():
    document = _workflow(
        steps=[
            _agent_step("a", needs=["b"]),
            _agent_step("b", needs=["a"]),
        ]
    )
    assert lw.lint(document).has(lw.STEP_DEPENDENCY_CYCLE)


def test_rejects_promotion_candidate_that_produces_no_candidate():
    document = _workflow(
        steps=[_agent_step(), _gate_step("verify", needs=["implement"], candidateFrom="implement")],
        promotion={
            "candidateFrom": "verify",
            "strategy": "squash-merge",
            "requiredGates": ["verify"],
        },
    )
    assert lw.lint(document).has(lw.PROMOTION_CANDIDATE_NOT_PRODUCING)


# --------------------------------------------------------------------------- #
# Loading surfaces
# --------------------------------------------------------------------------- #
def test_lint_text_parses_yaml(tmp_path):
    document = _canonical()
    import yaml

    text = yaml.safe_dump(document)
    assert lw.lint_text(text).ok


def test_lint_path_reads_a_yaml_file(tmp_path):
    import yaml

    path = tmp_path / "minimal.yaml"
    path.write_text(yaml.safe_dump(_canonical()), encoding="utf-8")
    assert lw.lint_path(path).ok


def test_schema_file_loads_and_matches_module():
    schema = json.loads(lw.SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema == lw.load_schema()


def test_semantic_error_codes_are_stable():
    codes = list(lw.semantic_error_codes())
    for code in (
        lw.AUTHORED_STATUS,
        lw.UNKNOWN_STEP_KIND,
        lw.MISSING_CONCURRENCY,
        lw.MUTATING_WITHOUT_VERIFICATION,
        lw.PROMOTION_WITHOUT_GATES,
        lw.UNBOUND_GATE,
        lw.PROMPT_AS_EVIDENCE,
    ):
        assert code in codes


# --------------------------------------------------------------------------- #
# The historical corpus is a different document kind (the lab, not the template)
# --------------------------------------------------------------------------- #
def test_corpus_experiment_spec_is_not_a_workflow_v1_document():
    import yaml

    corpus_document = yaml.safe_load(_CORPUS_SPEC.read_text(encoding="utf-8"))
    assert not lw.is_workflow_v1_document(corpus_document)


def test_linting_a_corpus_experiment_spec_does_not_pass_and_does_not_crash():
    """The linter targets NEW and touched workflow-v1 documents. A historical
    ExperimentSpec is never required to lint clean — running it must not crash
    and must not report a workflow-v1 pass."""
    import yaml

    corpus_document = yaml.safe_load(_CORPUS_SPEC.read_text(encoding="utf-8"))
    report = lw.lint(corpus_document)
    assert not report.ok
    assert any(f.code == lw.SCHEMA_INVALID for f in report.findings)
    assert not report.has(lw.MUTATING_WITHOUT_VERIFICATION)


@pytest.mark.parametrize(
    "document",
    [
        {"name": "admission_leases", "question": "q", "version": "0.1"},
        {"name": "x", "phases": [], "factors": []},
        {"kind": "Workflow"},
        {"metadata": {"name": "w"}, "spec": {}},
    ],
)
def test_is_workflow_v1_document_is_strict(document):
    assert lw.is_workflow_v1_document(document) is False


def test_approval_with_agent_executor_is_rejected_prompt_as_evidence():
    """A1 (authoring_product_aio adversarial, 2026-09-03): an approval step carrying an
    LLM executor (agent/task) is NOT legitimate human evidence — it is an LLM
    self-approval. An author must not be able to make a model judge its own work the
    candidate's ONLY required gate. Only a human/controller executor (or a machine
    gate executor, which makes it a gate not an approval) is legitimate on an approval."""
    document = _workflow(
        steps=[
            _agent_step(),
            {
                "id": "approve",
                "kind": "approval",
                "executor": "agent",  # the A1 anti-pattern: an LLM self-approval
                "needs": ["implement"],
                "candidateFrom": "implement",
            },
        ],
        promotion={
            "candidateFrom": "implement",
            "strategy": "squash-merge",
            "requiredGates": ["approve"],
        },
    )
    findings = lw.lint(document)
    assert not findings.ok
    assert findings.has(lw.PROMPT_AS_EVIDENCE)


def test_approval_with_human_executor_still_passes_after_a1():
    """The A1 tightening must not reject the legitimate shape: a human/controller
    approval as the required gate stays clean."""
    document = _workflow(
        steps=[
            _agent_step(),
            {
                "id": "approve",
                "kind": "approval",
                "executor": "human",
                "needs": ["implement"],
                "candidateFrom": "implement",
            },
        ],
        promotion={
            "candidateFrom": "implement",
            "strategy": "squash-merge",
            "requiredGates": ["approve"],
        },
    )
    assert lw.lint(document).ok
