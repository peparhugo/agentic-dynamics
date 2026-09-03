"""JSON-Schema assertions for workflows/schema/workflow-v1.schema.json (a1).

The authoring contract's STRUCTURAL half (Wave 3, a1): the schema (JSON Schema,
draft 2020-12) must accept a canonical workflow and reject an authored operational
status, an unknown step kind, a missing concurrency policy, and the other
structural violations a workflow definition can carry. The SEMANTIC half — the
rules a schema alone cannot express — lives in workflows/lint_workflow.py and is
covered by tests/test_workflow_linter.py.
"""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "workflows" / "schema" / "workflow-v1.schema.json"
)


def _schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator() -> Draft202012Validator:
    return Draft202012Validator(_schema())


def _canonical() -> dict:
    """The canonical workflow every positive assertion starts from: an agent step
    (mutating) whose candidate a test gate verifies, then a gated promotion."""
    return {
        "apiVersion": "agentic-dynamics.io/v1",
        "kind": "Workflow",
        "metadata": {"name": "minimal-agent-workflow", "revision": "1", "lifecycle": "development"},
        "spec": {
            "baseRef": "main",
            "workspace": {"mode": "isolated"},
            "concurrency": {"group": "minimal-agent", "policy": "serial"},
            "steps": [
                {
                    "id": "implement",
                    "kind": "agent",
                    "executor": "agent",
                    "scope": "implementation",
                    "prompt": "Implement the requested change and commit it.",
                },
                {
                    "id": "verify",
                    "kind": "gate",
                    "executor": "test",
                    "scope": "research_readonly",
                    "needs": ["implement"],
                    "candidateFrom": "implement",
                },
            ],
            "promotion": {
                "candidateFrom": "implement",
                "strategy": "squash-merge",
                "requiredGates": ["verify"],
            },
        },
    }


def test_schema_is_draft_2020_12():
    assert _schema()["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_canonical_workflow_validates():
    assert _validator().is_valid(_canonical())


def test_canonical_workflow_has_no_operational_status_field():
    document = _canonical()
    assert "status" not in document
    assert "status" not in document["metadata"]
    assert "status" not in document["spec"]
    for step in document["spec"]["steps"]:
        assert "status" not in step


def test_rejects_authored_status_at_root():
    document = _canonical()
    document["status"] = "completed"
    assert not _validator().is_valid(document)


def test_rejects_authored_operational_status_in_metadata():
    document = _canonical()
    document["metadata"]["status"] = "running"
    assert not _validator().is_valid(document)


def test_rejects_authored_status_on_a_step():
    document = _canonical()
    document["spec"]["steps"][0]["status"] = "succeeded"
    assert not _validator().is_valid(document)


def test_rejects_authored_status_on_promotion():
    document = _canonical()
    document["spec"]["promotion"]["status"] = "promoted"
    assert not _validator().is_valid(document)


def test_rejects_unknown_step_kind():
    document = _canonical()
    document["spec"]["steps"][0]["kind"] = "robot"
    errors = list(_validator().iter_errors(document))
    assert errors
    assert any("steps" in [str(p) for p in e.absolute_path] for e in errors)


def test_rejects_missing_concurrency_block():
    document = _canonical()
    del document["spec"]["concurrency"]
    assert not _validator().is_valid(document)


def test_rejects_concurrency_without_policy():
    document = _canonical()
    document["spec"]["concurrency"] = {"group": "minimal-agent"}
    assert not _validator().is_valid(document)


def test_rejects_concurrency_with_unknown_policy():
    document = _canonical()
    document["spec"]["concurrency"] = {"group": "minimal-agent", "policy": "whenever"}
    assert not _validator().is_valid(document)


def test_rejects_concurrency_without_group():
    document = _canonical()
    document["spec"]["concurrency"] = {"policy": "serial"}
    assert not _validator().is_valid(document)


def test_rejects_bounded_policy_without_max_runs():
    document = _canonical()
    document["spec"]["concurrency"] = {"group": "minimal-agent", "policy": "bounded"}
    assert not _validator().is_valid(document)


def test_accepts_bounded_policy_with_max_runs():
    document = _canonical()
    document["spec"]["concurrency"] = {"group": "minimal-agent", "policy": "bounded", "maxRuns": 3}
    assert _validator().is_valid(document)


def test_rejects_unknown_step_kind_field_and_unknown_root_kind():
    document = _canonical()
    document["kind"] = "Experiment"
    assert not _validator().is_valid(document)
    document = _canonical()
    document["spec"]["steps"][0]["executor"] = "mind-meld"
    assert not _validator().is_valid(document)


def test_rejects_unknown_workspace_mode_and_scope():
    document = _canonical()
    document["spec"]["workspace"] = {"mode": "enterprise"}
    assert not _validator().is_valid(document)
    document = _canonical()
    document["spec"]["steps"][0]["scope"] = "everywhere"
    assert not _validator().is_valid(document)


def test_rejects_promotion_without_required_gates():
    document = _canonical()
    document["spec"]["promotion"] = {
        "candidateFrom": "implement",
        "strategy": "squash-merge",
        "requiredGates": [],
    }
    assert not _validator().is_valid(document)


def test_rejects_empty_steps():
    document = _canonical()
    document["spec"]["steps"] = []
    assert not _validator().is_valid(document)
