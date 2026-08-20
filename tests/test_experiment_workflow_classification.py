"""Experiment-vs-workflow classification guard (critique rec 3).

Rec 3: ``experiments/specs/`` currently holds genuine experimental definitions beside
implementation projects and repo-development workflows, making it impossible to tell an
experiment that studies a hypothesis from an automated work order that changes the repository.
This test enforces the split (``docs/consolidation/design.md`` §4) *as a test, not a
convention*: a work-order spec dropped into ``experiments/definitions/`` fails, and a
measurement spec dropped into ``workflows/`` fails the reciprocal direction.

Classification rule (design §4):

* **experiment** — studies a hypothesis about a model's behaviour/cost/quality under some
  condition and produces a *measured result*. Signature: ``workflow.kind`` in
  ``{story, task, experiment}`` (or any non-``agent_task`` measurement kind), *or* an
  ``agent_task`` whose question is a hypothesis (no repo-change deliverable).
* **workflow** — a work order that changes the repository (build/write/fix/repoint/rebrand)
  with a deliverable artifact. Signature: ``workflow.kind == agent_task`` whose
  ``context.hard_rules`` name a production-code edit, *or* whose ``question`` names a
  repo-change deliverable.

The guard is deliberately heuristic (substring markers, not a hardcoded name list) so it
catches *new* misplacements; it is verified against the re-homed corpus in the move phase.
"""

from __future__ import annotations

from pathlib import Path

import yaml
import pytest

ROOT = Path(__file__).resolve().parent.parent
SPECS_FLAT = ROOT / "experiments" / "specs"
DEFINITIONS = ROOT / "experiments" / "definitions"
WORKFLOWS = ROOT / "workflows"

# Repo-change deliverable markers that a work order's question names (design §4's
# website/control-room/kb-build/rewrite/repoint/rebrand, plus the verbs the critique's actual
# work orders use). Lowercased substring match on the question text.
WORKORDER_QUESTION_MARKERS = (
    "website", "control room", "control-room", "control_room",
    "rewrite", "repoint", "rebrand", "facelift",
    "implement", "canonicalize", "remediate", "refactor", "migrate", "unify",
    "queue", "registry",
    "consolidation", "release",
    "knowledge base", "knowledge-base",
    "supervisor", "design session", "background session",
    "context abstraction", "context-abstraction",
    "architecture review", "repo review", "code review",
    "spec lifecycle", "labbook",
    "golden circle", "data pipeline",
)

# ``context.hard_rules`` markers that declare a production-code edit (the consolidation specs
# use these; older work orders rely on the question markers above).
WORKORDER_HARDRULE_MARKERS = ("production code", "edit production", "design/implement", "implement")


def _load_spec(path: Path) -> dict:
    """Load a spec YAML into a plain dict (classification, not validation)."""
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _spec_files(directory: Path) -> list[Path]:
    """Every ``*.yaml`` spec under ``directory``, recursively."""
    if not directory.exists():
        return []
    return sorted(directory.rglob("*.yaml"))


def is_work_order(spec: dict) -> bool:
    """Return True if ``spec`` carries the work-order signature (design §4)."""
    workflow = spec.get("workflow") or {}
    if workflow.get("kind") != "agent_task":
        return False
    context = (workflow.get("params") or {}).get("context") or {}
    hard_rules = str(context.get("hard_rules") or "").lower()
    if any(m in hard_rules for m in WORKORDER_HARDRULE_MARKERS):
        return True
    question = str(spec.get("question") or "").lower()
    return any(m in question for m in WORKORDER_QUESTION_MARKERS)


@pytest.mark.xfail(
    reason="expected to fail until move_specs re-homes the specs out of experiments/specs/",
    strict=False,
)
def test_experiments_specs_flat_dir_is_drained():
    """The as-is mixing: ``experiments/specs/`` must hold no ``*.yaml`` specs once the split
    has run — the specs live under ``experiments/definitions/`` and ``workflows/**`` instead.
    This is the assertion that fails *before* the move (xfail) and passes after it (xpass)."""
    leftovers = sorted(SPECS_FLAT.glob("*.yaml"))
    assert not leftovers, (
        "experiments/specs/ still holds un-split specs (the move hasn't run): "
        + ", ".join(p.name for p in leftovers)
    )


def test_definitions_are_experiments_not_work_orders():
    """Every ``experiments/definitions/**`` spec is a measurement workflow, not a work order."""
    misplaced = []
    for path in _spec_files(DEFINITIONS):
        spec = _load_spec(path)
        if is_work_order(spec):
            misplaced.append(path.name)
    assert not misplaced, (
        "work-order specs misplaced in experiments/definitions/: " + ", ".join(misplaced)
    )


def test_workflows_carry_the_work_order_signature():
    """Reciprocal: every ``workflows/**`` spec carries the work-order signature."""
    missing = []
    for path in _spec_files(WORKFLOWS):
        spec = _load_spec(path)
        if not is_work_order(spec):
            missing.append(path.name)
    assert not missing, (
        "measurement specs misplaced in workflows/: " + ", ".join(missing)
    )
