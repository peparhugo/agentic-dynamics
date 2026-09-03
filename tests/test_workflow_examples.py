"""The four canonical workflow-v1 examples (Wave 3, a2) — the POSITIVE cases for a1.

The examples under ``workflows/examples/`` ARE the authoring product's positive cases:
every one must validate against ``workflows/schema/workflow-v1.schema.json`` (draft
2020-12) AND pass ``workflows/lint_workflow.py`` with zero findings. The four documented
shapes are:

* ``minimal-agent-workflow.yaml`` — the smallest valid workflow: one agent step + one
  test gate; promotion requires exactly that one gate.
* ``approval-workflow.yaml`` — an agent step + a verifier gate + an approval checkpoint;
  promotion requires the gate AND the approval (the only example with a human
  ``kind: approval`` step).
* ``research-workflow.yaml`` — a measurement/research shape: ``readonly`` workspace, no
  mutating step, no gate and no promotion — repeatable and runnable by construction.
* ``publication-workflow.yaml`` — build + HTML-consistency + receipt + deploy gates; no
  agent step at all (fully deterministic command pipeline); promotion requires all three
  gates.

VERIFY (both directions): (a) all four validate against the a1 schema; (b) all four pass
the a1 linter with zero errors; (c) the four shapes are structurally distinct exactly as
documented in ``workflows/examples/README.md``; (d) the historical ExperimentSpec corpus
(``workflows/repository|operations|research``) is untouched — the examples are NEW
workflow-v1 documents, a different document kind the ExperimentSpec corpus scans exclude
via ``experiment_spec.committed_spec_paths``.
"""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from agentic_dynamics.experiment.experiment_spec import committed_spec_paths
from workflows import lint_workflow as lw

_ROOT = Path(__file__).resolve().parent.parent
_EXAMPLE_DIR = _ROOT / "workflows" / "examples"
_SCHEMA_PATH = _ROOT / "workflows" / "schema" / "workflow-v1.schema.json"
_CORPUS_DIRS = ("repository", "operations", "research")

# The four canonical example files (a2's deliverable).
EXAMPLE_FILES = (
    "minimal-agent-workflow.yaml",
    "approval-workflow.yaml",
    "research-workflow.yaml",
    "publication-workflow.yaml",
)

# The DOCUMENTED structural signature of each shape (workflows/examples/README.md). The
# tests below assert the committed file matches its documented signature AND that no two
# signatures collide — the "four shapes differ as documented" proof.
DOCUMENTED_SIGNATURES: dict[str, dict] = {
    "minimal-agent-workflow.yaml": {
        "n_steps": 2,
        "kinds": ["agent", "gate"],
        "executors": ["agent", "test"],
        "workspace_mode": "isolated",
        "promotion": True,
        "required_gates": ["verify"],
    },
    "approval-workflow.yaml": {
        "n_steps": 3,
        "kinds": ["agent", "gate", "approval"],
        "executors": ["agent", "test", "human"],
        "workspace_mode": "isolated",
        "promotion": True,
        "required_gates": ["verify", "approve"],
    },
    "research-workflow.yaml": {
        "n_steps": 3,
        "kinds": ["task", "agent", "agent"],
        "executors": ["command", "agent", "agent"],
        "workspace_mode": "readonly",
        "promotion": False,
        "required_gates": [],
    },
    "publication-workflow.yaml": {
        "n_steps": 4,
        "kinds": ["task", "gate", "gate", "gate"],
        "executors": ["command", "command", "command", "command"],
        "workspace_mode": "isolated",
        "promotion": True,
        "required_gates": ["html-consistency", "receipt", "deploy"],
    },
}


def _schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator() -> Draft202012Validator:
    return Draft202012Validator(_schema())


def _load_document(filename: str) -> dict:
    return lw.load_document((_EXAMPLE_DIR / filename).read_text(encoding="utf-8"))


def _corpus_paths() -> list[Path]:
    paths: list[Path] = []
    for subdir in _CORPUS_DIRS:
        paths.extend(sorted((_ROOT / "workflows" / subdir).glob("*.yaml")))
    return paths


# --------------------------------------------------------------------------- #
# (a) all four examples validate against workflow-v1.schema.json
# --------------------------------------------------------------------------- #
def test_four_example_files_exist():
    for filename in EXAMPLE_FILES:
        assert (_EXAMPLE_DIR / filename).is_file(), filename


def test_each_example_is_a_workflow_v1_document():
    for filename in EXAMPLE_FILES:
        assert lw.is_workflow_v1_document(_load_document(filename)), filename


def test_each_example_validates_against_the_schema():
    validator = _validator()
    for filename in EXAMPLE_FILES:
        assert validator.is_valid(_load_document(filename)), filename


def test_each_example_has_no_authored_operational_status():
    for filename in EXAMPLE_FILES:
        document = _load_document(filename)
        assert "status" not in document
        assert "status" not in document["metadata"]
        assert "status" not in document["spec"]
        for step in document["spec"]["steps"]:
            assert "status" not in step


# --------------------------------------------------------------------------- #
# (b) all four pass the a1 linter with zero errors
# --------------------------------------------------------------------------- #
def test_each_example_passes_the_linter_with_zero_errors():
    for filename in EXAMPLE_FILES:
        report = lw.lint_path(_EXAMPLE_DIR / filename)
        assert report.ok, f"{filename}: {report.codes}"
        assert report.findings == [], filename


def test_none_of_the_seven_mandated_rejections_fires_on_an_example():
    mandated = (
        lw.AUTHORED_STATUS,
        lw.UNKNOWN_STEP_KIND,
        lw.MISSING_CONCURRENCY,
        lw.MUTATING_WITHOUT_VERIFICATION,
        lw.PROMOTION_WITHOUT_GATES,
        lw.UNBOUND_GATE,
        lw.PROMPT_AS_EVIDENCE,
    )
    for filename in EXAMPLE_FILES:
        report = lw.lint_path(_EXAMPLE_DIR / filename)
        assert not any(report.has(code) for code in mandated), filename


# --------------------------------------------------------------------------- #
# (c) the four shapes are structurally distinct AS DOCUMENTED
# --------------------------------------------------------------------------- #
def _actual_signature(document: dict) -> dict:
    steps = document["spec"]["steps"]
    promotion = document["spec"].get("promotion")
    return {
        "n_steps": len(steps),
        "kinds": [step["kind"] for step in steps],
        "executors": [step.get("executor") for step in steps],
        "workspace_mode": document["spec"]["workspace"]["mode"],
        "promotion": promotion is not None,
        "required_gates": (promotion.get("requiredGates", []) if promotion is not None else []),
    }


def test_each_example_matches_its_documented_signature():
    for filename, expected in DOCUMENTED_SIGNATURES.items():
        assert _actual_signature(_load_document(filename)) == expected, filename


def test_the_four_shapes_are_pairwise_distinct():
    signatures = [_actual_signature(_load_document(f)) for f in EXAMPLE_FILES]
    keys = ("workspace_mode", "kinds", "executors", "required_gates")
    fingerprints = {
        f: tuple(
            tuple(signature[k]) if isinstance(signature[k], list) else signature[k] for k in keys
        )
        for f, signature in zip(EXAMPLE_FILES, signatures, strict=True)
    }
    assert len(set(fingerprints.values())) == len(EXAMPLE_FILES), fingerprints


def test_distinctive_markers_land_exactly_once_each():
    """The four documented differentiators appear in exactly the intended examples."""
    signatures = {f: _actual_signature(_load_document(f)) for f in EXAMPLE_FILES}
    approval = signatures["approval-workflow.yaml"]
    research = signatures["research-workflow.yaml"]
    publication = signatures["publication-workflow.yaml"]
    minimal = signatures["minimal-agent-workflow.yaml"]

    assert "approval" in approval["kinds"] and "human" in approval["executors"]
    assert "approval" not in research["kinds"] and "approval" not in publication["kinds"]
    assert research["workspace_mode"] == "readonly" and research["promotion"] is False
    assert "agent" not in publication["kinds"] and "agent" not in publication["executors"]
    assert len(minimal["required_gates"]) == 1  # the smallest valid workflow


# --------------------------------------------------------------------------- #
# (d) the historical corpus is untouched (the examples are a different doc kind)
# --------------------------------------------------------------------------- #
def test_examples_are_new_files_never_corpus_copies():
    """No example shadows a historical corpus YAML: the examples are new files under
    workflows/examples/, none of which lives in or reuses an identity from
    workflows/repository|operations|research."""
    corpus_names = {path.stem for path in _corpus_paths()}
    corpus_dirs = {path.parent for path in _corpus_paths()}
    for filename in EXAMPLE_FILES:
        example_path = _EXAMPLE_DIR / filename
        assert example_path.is_file()
        assert example_path.parent not in corpus_dirs
        assert filename not in corpus_names, f"{filename} collides with a corpus file"


def test_corpus_yamls_are_experiment_specs_not_workflow_v1_documents():
    """The corpus (the lab) is a different document kind — none of its YAMLs is a
    workflow-v1 definition, and none was touched into one by these examples."""
    corpus = _corpus_paths()
    assert len(corpus) > 0
    for path in corpus:
        document = lw.load_document(path.read_text(encoding="utf-8"))
        assert not lw.is_workflow_v1_document(document), path


def test_committed_spec_discovery_excludes_the_examples():
    """The ExperimentSpec corpus scan (experiment_spec.committed_spec_paths) excludes the
    workflow-v1 examples — they are not ExperimentSpecs and never enter the lifecycle
    index."""
    discovered = {p.resolve() for p in committed_spec_paths(_ROOT)}
    for filename in EXAMPLE_FILES:
        assert (_EXAMPLE_DIR / filename).resolve() not in discovered, filename
    # And nothing loadable was dropped: every corpus + definitions spec is still discovered.
    assert all(path.resolve() in discovered for path in _corpus_paths())
