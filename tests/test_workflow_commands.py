"""The workflow authoring command surface (Wave-3 a3) — new / lint / plan.

``a3_command_surface`` lands the three authoring commands and their backing logic:

* ``workflow new <name>`` — scaffold a minimal valid workflow-v1 definition from the
  minimal-agent example into ``workflows/repository/<name>.yaml``, validated against
  the schema + the a1 linter AS IT IS WRITTEN.
* ``workflow lint <file>`` — the CI-able surface of the a1 linter: named violations on
  a bad file, silence + exit 0 on a good one, exit 2 on a non-workflow document.
* ``workflow plan <file> --json`` — render the step DAG (needs/candidateFrom edges),
  the gates and their bindings, and the promotion contract as ``workflow-plan/v1``.

The run/discard-tree/promote verbs are untouched; the new verbs resolve through the
CLI's longest-prefix table (guarded in ``test_cli_resolution.py`` and asserted here).

VERIFY (both directions): (a) ``workflow new`` produces a schema-valid, linter-clean
file (asserted via an independent Draft202012Validator AND the linter); (b) ``workflow
lint`` reports the named semantic violations on a bad file and is silent on a good one;
(c) ``workflow plan --json`` renders the DAG edges + gates + promotion contract across
the four canonical shapes; (d) the CLI resolution guard resolves the three new verbs to
their backing scripts.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from workflows import lint_workflow as lw
from workflows import plan_workflow as plan
from workflows import scaffold_workflow as scaffold
from workflows.scaffold_workflow import ScaffoldError

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "workflows" / "examples"
SCHEMA_PATH = ROOT / "workflows" / "schema" / "workflow-v1.schema.json"
MINIMAL = EXAMPLES / "minimal-agent-workflow.yaml"
APPROVAL = EXAMPLES / "approval-workflow.yaml"
RESEARCH = EXAMPLES / "research-workflow.yaml"
PUBLICATION = EXAMPLES / "publication-workflow.yaml"
CORPUS = ROOT / "workflows" / "repository" / "authoring_product_aio.yaml"

#: A workflow-v1 definition that violates three of the a1 semantic rules by name:
#: authored operational status (metadata.status), a mutating step with no downstream
#: verification (refactor), and a required gate whose only evidence is an LLM executor
#: (verify) rather than a machine executor.
BAD_WORKFLOW = """\
apiVersion: agentic-dynamics.io/v1
kind: Workflow
metadata:
  name: bad-wf
  revision: "1"
  status: completed
spec:
  baseRef: main
  workspace:
    mode: isolated
  concurrency:
    group: bad-wf
    policy: serial
  steps:
    - id: implement
      kind: agent
      executor: agent
      scope: implementation
      prompt: do the thing
    - id: refactor
      kind: agent
      executor: agent
      scope: implementation
      needs: [implement]
      prompt: refactor it
    - id: verify
      kind: gate
      executor: agent
      needs: [implement]
      candidateFrom: implement
  promotion:
    candidateFrom: implement
    strategy: squash-merge
    requiredGates: [verify]
"""


def _load_script(name: str):
    """Load a ``scripts/<name>.py`` shell by file path (the run_workflow_graph_cli shape)."""
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema_validator() -> Draft202012Validator:
    with SCHEMA_PATH.open("r", encoding="utf-8") as fh:
        return Draft202012Validator(json.load(fh))


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    return _schema_validator()


def _assert_workflow_v1_clean(path: Path, validator: Draft202012Validator) -> dict:
    text = path.read_text(encoding="utf-8")
    document = lw.load_document(text)
    assert lw.is_workflow_v1_document(document)
    errors = sorted(validator.iter_errors(document), key=lambda e: list(e.path))
    assert not errors, [e.message for e in errors]
    report = lw.lint_text(text)
    assert report.ok, report.findings
    return document


# --------------------------------------------------------------------------- #
# (a) workflow new — scaffold + validate as it is written
# --------------------------------------------------------------------------- #
def test_workflow_new_creates_schema_valid_linter_clean_workflow(tmp_path, validator):
    path = scaffold.scaffold("a3_probe_wf", output_dir=tmp_path)
    assert path == tmp_path / "a3_probe_wf.yaml"
    assert path.is_file()
    document = _assert_workflow_v1_clean(path, validator)
    assert document["metadata"]["name"] == "a3_probe_wf"
    assert document["metadata"]["revision"] == "1"
    assert document["spec"]["concurrency"]["group"] == "a3_probe_wf"
    steps = {step["id"] for step in document["spec"]["steps"]}
    assert steps == {"implement", "verify"}


def test_workflow_new_default_target_is_repository_dir(tmp_path):
    path = scaffold.scaffold("a3_default_target", root=tmp_path)
    assert path == tmp_path / "workflows" / "repository" / "a3_default_target.yaml"
    assert path.is_file()


def test_workflow_new_rejects_invalid_name(tmp_path):
    for bad in ("Bad Name", "9starts-with-digit", "UPPER", "has space", ""):
        with pytest.raises(ScaffoldError):
            scaffold.scaffold(bad, output_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_workflow_new_refuses_to_overwrite(tmp_path):
    target = tmp_path / "a3_existing.yaml"
    target.write_text("keep me", encoding="utf-8")
    with pytest.raises(ScaffoldError, match="overwrite"):
        scaffold.scaffold("a3_existing", output_dir=tmp_path)
    assert target.read_text(encoding="utf-8") == "keep me"


def test_workflow_new_invalid_template_refuses_and_writes_nothing(tmp_path):
    bad_template = tmp_path / "bad_template.yaml"
    bad_template.write_text(BAD_WORKFLOW, encoding="utf-8")
    out = tmp_path / "out"
    with pytest.raises(ScaffoldError, match="linter-clean"):
        scaffold.scaffold("a3_from_bad", output_dir=out, template_path=bad_template)
    assert not out.exists() or list(out.iterdir()) == []


def test_workflow_new_cli_writes_validated_file(tmp_path, capsys):
    workflow_new = _load_script("workflow_new")
    rc = workflow_new.run(["a3_cli_probe", "--output-dir", str(tmp_path)])
    assert rc == 0
    target = tmp_path / "a3_cli_probe.yaml"
    assert target.is_file()
    assert str(target) in capsys.readouterr().out
    assert lw.lint_path(target).ok


# --------------------------------------------------------------------------- #
# (b) workflow lint — named violations / silence / non-workflow documents
# --------------------------------------------------------------------------- #
def test_workflow_lint_reports_named_semantic_violations(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text(BAD_WORKFLOW, encoding="utf-8")
    workflow_lint = _load_script("workflow_lint")

    rc = workflow_lint.run([str(bad), "--json"])
    report = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert report["ok"] is False
    assert report["schema"] == "workflow-lint/v1"
    codes = {finding["code"] for finding in report["findings"]}
    for named in (
        "authored-status",
        "mutating-without-verification",
        "prompt-as-evidence",
    ):
        assert named in codes, f"missing named violation {named}: {sorted(codes)}"
    for finding in report["findings"]:
        assert {"code", "message", "path"} <= set(finding)

    capsys.readouterr()
    rc = workflow_lint.run([str(bad)])
    assert rc == 1
    human = capsys.readouterr().out
    assert "authored-status:" in human
    assert "mutating-without-verification:" in human
    assert "prompt-as-evidence:" in human


def test_workflow_lint_is_silent_on_good_workflow(tmp_path, capsys):
    good = tmp_path / "good.yaml"
    good.write_text(MINIMAL.read_text(encoding="utf-8"), encoding="utf-8")
    workflow_lint = _load_script("workflow_lint")
    rc = workflow_lint.run([str(good)])
    assert rc == 0
    assert capsys.readouterr().out == ""  # silence IS the pass signal


def test_workflow_lint_rejects_missing_file_and_corpus_document(capsys):
    workflow_lint = _load_script("workflow_lint")
    rc = workflow_lint.run(["does-not-exist.yaml"])
    assert rc == 2

    rc = workflow_lint.run([str(CORPUS)])  # an ExperimentSpec is NOT a workflow-v1 doc
    assert rc == 2
    assert "not a workflow-v1 definition" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# (c) workflow plan --json — DAG edges + gates + promotion contract
# --------------------------------------------------------------------------- #
def test_workflow_plan_json_renders_dag_edges_gates_promotion(capsys):
    workflow_plan = _load_script("workflow_plan")
    rc = workflow_plan.run([str(MINIMAL), "--json"])
    assert rc == 0
    doc = json.loads(capsys.readouterr().out)

    assert doc["schema"] == "workflow-plan/v1"
    assert doc["document_kind"] == "workflow-v1"
    assert doc["metadata"]["name"] == "minimal-agent-workflow"
    assert doc["spec"]["baseRef"] == "main"
    assert doc["spec"]["concurrency"] == {"group": "minimal-agent-workflow", "policy": "serial"}

    by_id = {step["id"]: step for step in doc["steps"]}
    assert list(by_id) == ["implement", "verify"]
    assert by_id["implement"]["mutating"] is True
    assert by_id["implement"]["needs"] == []
    assert by_id["verify"]["mutating"] is False
    assert by_id["verify"]["needs"] == ["implement"]
    assert by_id["verify"]["candidateFrom"] == "implement"

    edge_pairs = {(e["from"], e["to"], e["via"]) for e in doc["edges"]}
    assert ("implement", "verify", "needs") in edge_pairs
    assert ("implement", "verify", "candidateFrom") in edge_pairs
    assert doc["topological_order"] == ["implement", "verify"]

    assert doc["gates"] == [
        {
            "id": "verify",
            "kind": "gate",
            "executor": "test",
            "scope": "research_readonly",
            "candidateFrom": "implement",
            "binds": "implement",
            "binding": "declared",
            "required_by_promotion": True,
        }
    ]
    assert doc["promotion"] == {
        "candidateFrom": "implement",
        "strategy": "squash-merge",
        "requiredGates": ["verify"],
    }
    assert doc["validation"] == {"ok": True, "findings": []}


def test_workflow_plan_text_is_a_human_plan(capsys):
    workflow_plan = _load_script("workflow_plan")
    rc = workflow_plan.run([str(MINIMAL)])
    assert rc == 0
    text = capsys.readouterr().out
    assert "minimal-agent-workflow" in text
    assert "steps (2)" in text
    assert "verify <- implement" in text
    assert "validation: OK" in text


def test_workflow_plan_json_research_shape_has_no_gates_or_promotion(capsys):
    workflow_plan = _load_script("workflow_plan")
    rc = workflow_plan.run([str(RESEARCH), "--json"])
    assert rc == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["promotion"] is None
    assert doc["gates"] == []
    assert all(not step["mutating"] for step in doc["steps"])
    assert doc["topological_order"] == ["harvest", "measure", "report"]
    assert doc["validation"]["ok"] is True


def test_workflow_plan_json_approval_shape_binds_both_checkpoints(capsys):
    workflow_plan = _load_script("workflow_plan")
    rc = workflow_plan.run([str(APPROVAL), "--json"])
    assert rc == 0
    doc = json.loads(capsys.readouterr().out)
    gate_ids = {gate["id"]: gate for gate in doc["gates"]}
    assert set(gate_ids) == {"verify", "approve"}
    for gate in doc["gates"]:
        assert gate["binds"] == "implement"
        assert gate["binding"] == "declared"
        assert gate["required_by_promotion"] is True
    assert doc["promotion"]["requiredGates"] == ["verify", "approve"]


def test_workflow_plan_json_publication_shape_tasks_produce_candidate(capsys):
    workflow_plan = _load_script("workflow_plan")
    rc = workflow_plan.run([str(PUBLICATION), "--json"])
    assert rc == 0
    doc = json.loads(capsys.readouterr().out)
    by_id = {step["id"]: step for step in doc["steps"]}
    assert by_id["build"]["kind"] == "task"
    assert by_id["build"]["mutating"] is True
    assert doc["promotion"]["candidateFrom"] == "build"
    assert set(doc["promotion"]["requiredGates"]) == {"html-consistency", "receipt", "deploy"}
    assert all(g["binds"] == "build" for g in doc["gates"])


def test_workflow_plan_embeds_validation_findings_for_violating_workflow(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text(BAD_WORKFLOW, encoding="utf-8")
    workflow_plan = _load_script("workflow_plan")
    rc = workflow_plan.run([str(bad), "--json"])
    assert rc == 0  # a violating workflow still renders so its problems are visible
    doc = json.loads(capsys.readouterr().out)
    assert doc["validation"]["ok"] is False
    codes = {f["code"] for f in doc["validation"]["findings"]}
    assert "authored-status" in codes
    assert "mutating-without-verification" in codes


def test_workflow_plan_rejects_non_workflow_document(capsys):
    workflow_plan = _load_script("workflow_plan")
    rc = workflow_plan.run([str(CORPUS)])
    assert rc == 2
    assert "not a workflow-v1 definition" in capsys.readouterr().err
    assert workflow_plan.run(["no-such-file.yaml"]) == 2


def test_build_plan_path_matches_cli_rendering(tmp_path):
    plan_doc = plan.build_plan_path(MINIMAL)
    assert plan_doc["metadata"]["name"] == "minimal-agent-workflow"
    assert plan_doc["validation"]["ok"] is True


# --------------------------------------------------------------------------- #
# (d) the CLI resolution guard resolves the new verbs
# --------------------------------------------------------------------------- #
def test_authoring_subcommands_resolve_to_backing_scripts():
    from agentic_dynamics import cli

    for argv, script in (
        (["workflow", "new"], "workflow_new.py"),
        (["workflow", "lint"], "workflow_lint.py"),
        (["workflow", "plan"], "workflow_plan.py"),
    ):
        resolved_script, rest = cli._resolve(argv)
        assert resolved_script == script
        assert rest == []
        assert (cli._SCRIPTS_DIR / script).exists()
    # The authoring verbs must not shadow the pre-existing workflow verbs.
    assert cli._resolve(["workflow", "run"]) == ("run_workflow.py", [])
    assert cli._resolve(["workflow", "promote"]) == ("promote.py", [])
