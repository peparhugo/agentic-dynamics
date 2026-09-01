"""Experiment-vs-workflow placement guard (critique rec 3, refactor-repair P1-3 placement).

Rec 3: ``experiments/specs/`` used to hold genuine experimental definitions beside
implementation projects and repo-development workflows, making it impossible to tell an
experiment that studies a hypothesis from a work order that changes the repository.

The Stage-2 fix re-homed the corpus, but it decided placement with a *substring heuristic* over
question text — which let real misplacements survive (``posthoc_pipeline`` — operational — and
``workflow_step_routing`` — source-modifying — both lived in ``experiments/definitions/``).

This guard now decides placement from the spec's EXPLICIT ``artifact_kind`` metadata
(``experiment`` | ``workflow``), never from text: the declared kind must match the directory the
spec lives in, and a mismatch fails. Until the P1-3 backfill writes ``artifact_kind`` into every
one of the 77 specs, an *unset* kind is treated as "not yet classified" (no assertion) — the
backfill makes the guard strict over the whole corpus.
"""

from __future__ import annotations

from pathlib import Path

import yaml

import pytest
pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parent.parent
SPECS_FLAT = ROOT / "experiments" / "specs"
DEFINITIONS = ROOT / "experiments" / "definitions"
WORKFLOWS = ROOT / "workflows"

#: The two specs the placement task re-homed out of ``experiments/definitions/``.
REHOMED = ("operations/posthoc_pipeline.yaml", "repository/workflow_step_routing.yaml")


def _load_spec(path: Path) -> dict:
    """Load a spec YAML into a plain dict (placement check, not full validation)."""
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _spec_files(directory: Path, *, recursive: bool) -> list[Path]:
    """Every ``*.yaml`` under ``directory``.

    ``definitions/`` is scanned at the top level only — its ``configs/`` subdirectory holds
    measurement *configs* (not ExperimentSpecs), out of scope for the guard. ``workflows/`` is
    scanned recursively (repository/operations/research/examples).
    """
    if not directory.exists():
        return []
    return sorted(directory.rglob("*.yaml") if recursive else directory.glob("*.yaml"))


def _declared_kind(spec: dict) -> str | None:
    """The authored ``artifact_kind``, or ``None`` when not yet backfilled (pre-P1-3-backfill)."""
    kind = spec.get("artifact_kind")
    return kind if isinstance(kind, str) and kind in ("experiment", "workflow") else None


def test_experiments_specs_flat_dir_is_drained():
    """``experiments/specs/`` must hold no ``*.yaml`` — only the generated STATUS.md/index.json."""
    leftovers = sorted(SPECS_FLAT.glob("*.yaml"))
    assert not leftovers, (
        "experiments/specs/ still holds un-split specs: " + ", ".join(p.name for p in leftovers)
    )


def test_misplaced_specs_are_rehomed():
    """The two previously-misplaced specs now live under workflows/ and declare ``workflow``."""
    for rel in REHOMED:
        path = WORKFLOWS / rel
        assert path.exists(), f"{rel} was not re-homed"
        assert _declared_kind(_load_spec(path)) == "workflow", (
            f"{rel} must declare artifact_kind: workflow"
        )


def test_definitions_declare_experiment_kind():
    """No spec in ``experiments/definitions/`` declares ``artifact_kind: workflow``."""
    misplaced = []
    for path in _spec_files(DEFINITIONS, recursive=False):
        if _declared_kind(_load_spec(path)) == "workflow":
            misplaced.append(f"{path.name} (artifact_kind=workflow)")
    assert not misplaced, (
        "workflow specs misplaced in experiments/definitions/ (re-home under workflows/): "
        + ", ".join(misplaced)
    )


def test_workflows_declare_workflow_kind():
    """No spec under ``workflows/`` declares ``artifact_kind: experiment``."""
    misplaced = []
    for path in _spec_files(WORKFLOWS, recursive=True):
        if _declared_kind(_load_spec(path)) == "experiment":
            misplaced.append(f"{path.relative_to(WORKFLOWS)} (artifact_kind=experiment)")
    assert not misplaced, (
        "experiment specs misplaced under workflows/ (re-home under experiments/definitions/): "
        + ", ".join(misplaced)
    )
