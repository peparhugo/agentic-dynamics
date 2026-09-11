"""workflow-v1 -> ExperimentSpec compilation tests (step 1: authoring connects to execution).

``workflows/compile_workflow.py`` is the bridge between the Wave-3 authoring contract
(workflow-v1, validated by ``workflows/lint_workflow.py``) and the engine's executable
ExperimentSpec. These tests pin the two halves that matter:

* the SUPPORTED subset compiles faithfully — the minimal example's agent step + test gate
  become one ``agent_task`` phase whose native ``test_gate: true`` runs the independent
  test_runner verdict; the compiled spec passes ``validate_spec`` and carries the
  definition identity (digest + provenance) a run must certify;
* everything the engine cannot execute 1:1 REFUSES with a named ``refused-*`` code — the
  four canonical examples are the refusal fixtures (approval node, command executor,
  readonly workspace), plus targeted mutations for the rest of the vocabulary.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentic_dynamics.experiment import experiment_spec as es
from workflows import compile_workflow as cw
from workflows import lint_workflow as lw

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "workflows" / "examples"


def _load(name: str) -> dict:
    return yaml.safe_load((EXAMPLES / name).read_text(encoding="utf-8"))


def _minimal() -> dict:
    return _load("minimal-agent-workflow.yaml")


def _refusal_errors(document: dict) -> list[str]:
    with pytest.raises(cw.CompilationRefusedError) as exc:
        cw.compile_workflow(document)
    return exc.value.errors


# --------------------------------------------------------------------------- #
# The supported subset compiles faithfully
# --------------------------------------------------------------------------- #
def test_minimal_compiles_to_one_agent_task_phase_with_test_gate():
    compiled = cw.compile_workflow(_minimal(), source="minimal-agent-workflow.yaml")
    spec = compiled.spec

    assert spec.name == "minimal-agent-workflow"
    assert spec.version == "1"
    assert spec.artifact_kind == "workflow"
    assert spec.intent == "mutate"
    assert spec.repeatable is False
    assert spec.sandboxed is True
    assert spec.workflow.kind == "agent_task"

    phases = spec.workflow.params["phases"]
    # the gate MERGES into its producer: one phase, carrying the native test_gate seam.
    assert [p["name"] for p in phases] == ["implement"]
    assert phases[0]["kind"] == "agent"
    assert phases[0]["scope"] == "implementation"
    assert phases[0]["test_gate"] is True

    # the compiled spec must satisfy the experiment layer's own validator.
    assert es.validate_spec(spec) == []

    assert compiled.source_digest and len(compiled.source_digest) == 64
    assert compiled.step_map == {"implement": "implement", "verify": "implement"}


def test_compiled_provenance_binds_the_definition_identity():
    compiled = cw.compile_workflow(_minimal(), source="minimal-agent-workflow.yaml")
    prov = compiled.spec.workflow.params["workflow_v1"]

    assert prov["schema"] == "workflow-v1"
    assert prov["digest"] == compiled.source_digest
    assert prov["name"] == "minimal-agent-workflow"
    assert prov["revision"] == "1"
    assert prov["baseRef"] == "main"
    assert prov["concurrency"]["policy"] == "serial"
    assert prov["promotion"]["strategy"] == "squash-merge"
    assert prov["promotion"]["requiredGates"] == ["verify"]
    assert prov["step_map"]["verify"] == "implement"


def test_plan_render_is_carried_with_the_compiled_definition():
    compiled = cw.compile_workflow(_minimal())
    assert compiled.plan["schema"] == "workflow-plan/v1"
    assert [s["id"] for s in compiled.plan["steps"]] == ["implement", "verify"]
    assert compiled.plan["validation"]["ok"] is True


# --------------------------------------------------------------------------- #
# Refusals: lint findings first (never warnings)
# --------------------------------------------------------------------------- #
def test_lint_violations_refuse_with_their_codes():
    document = _minimal()
    document["spec"]["steps"] = [document["spec"]["steps"][0]]  # drop the verify gate
    errors = _refusal_errors(document)
    assert any(
        cw.REFUSED_LINT in e and lw.MUTATING_WITHOUT_VERIFICATION in e for e in errors
    ), errors


# --------------------------------------------------------------------------- #
# Refusals: the canonical examples the engine cannot execute 1:1
# --------------------------------------------------------------------------- #
def test_approval_node_refuses():
    errors = _refusal_errors(_load("approval-workflow.yaml"))
    assert any(cw.REFUSED_STEP_KIND in e and "approval" in e for e in errors), errors


def test_task_and_command_steps_refuse():
    errors = _refusal_errors(_load("publication-workflow.yaml"))
    assert any(cw.REFUSED_STEP_KIND in e for e in errors), errors


def test_readonly_workspace_refuses():
    errors = _refusal_errors(_load("research-workflow.yaml"))
    assert any(cw.REFUSED_WORKSPACE_MODE in e for e in errors), errors


# --------------------------------------------------------------------------- #
# Refusals: targeted mutations of the minimal definition
# --------------------------------------------------------------------------- #
def test_non_squash_promotion_strategy_refuses():
    document = _minimal()
    document["spec"]["promotion"]["strategy"] = "merge-commit"
    errors = _refusal_errors(document)
    assert any(cw.REFUSED_PROMOTION_STRATEGY in e for e in errors), errors


def test_join_step_refuses():
    document = _minimal()
    steps = document["spec"]["steps"]
    steps.append(
        {
            "id": "extend",
            "kind": "agent",
            "executor": "agent",
            "scope": "implementation",
            "needs": ["implement"],
            "prompt": "Extend the change.",
        }
    )
    steps.append(
        {
            "id": "verify-extend",
            "kind": "gate",
            "executor": "test",
            "needs": ["extend"],
            "candidateFrom": "extend",
        }
    )
    steps.append(
        {
            "id": "join",
            "kind": "agent",
            "executor": "agent",
            "scope": "implementation",
            "needs": ["verify", "verify-extend"],
            "prompt": "Join both branches.",
        }
    )
    steps.append(
        {
            "id": "verify-join",
            "kind": "gate",
            "executor": "test",
            "needs": ["join"],
            "candidateFrom": "join",
        }
    )
    document["spec"]["promotion"]["requiredGates"] = ["verify", "verify-extend", "verify-join"]
    errors = _refusal_errors(document)
    assert any(cw.REFUSED_NEEDS_JOIN in e for e in errors), errors


def test_non_blocking_inline_gate_refuses():
    document = _minimal()
    document["spec"]["steps"][0]["gate"] = {"executor": "test", "blocking": False}
    errors = _refusal_errors(document)
    assert any(cw.REFUSED_INLINE_GATE in e for e in errors), errors


def test_missing_prompt_refuses():
    document = _minimal()
    del document["spec"]["steps"][0]["prompt"]
    errors = _refusal_errors(document)
    assert any(cw.REFUSED_MISSING_PROMPT in e for e in errors), errors


def test_workspace_image_refuses():
    document = _minimal()
    document["spec"]["workspace"]["image"] = "fleet/base"
    errors = _refusal_errors(document)
    assert any(cw.REFUSED_WORKSPACE_IMAGE in e for e in errors), errors


def test_bounded_concurrency_refuses():
    document = _minimal()
    document["spec"]["concurrency"] = {"group": "minimal-agent-workflow", "policy": "bounded",
                                       "maxRuns": 2}
    errors = _refusal_errors(document)
    assert any(cw.REFUSED_CONCURRENCY_BOUNDED in e for e in errors), errors


# --------------------------------------------------------------------------- #
# The execution seam
# --------------------------------------------------------------------------- #
def test_wrong_document_kind_is_a_caller_error():
    with pytest.raises(ValueError):
        cw.compile_workflow({"name": "not-a-workflow", "version": "1"})


def test_load_spec_any_routes_workflow_v1_through_the_compiler():
    spec = cw.load_spec_any(EXAMPLES / "minimal-agent-workflow.yaml")
    assert isinstance(spec, es.ExperimentSpec)
    assert spec.name == "minimal-agent-workflow"
    assert spec.workflow.params["workflow_v1"]["digest"]


def test_load_spec_any_leaves_experiment_specs_untouched():
    path = ROOT / "workflows" / "repository" / "beta_lab_execution.yaml"
    assert cw.load_spec_any(path).to_dict() == es.load_spec(path).to_dict()
