"""Executable guardrails for the ``world_model_loop`` workflow spec.

Two minted ``pattern/v1`` records are landed onto the loop spec and pinned here so a later
edit cannot silently weaken the contract:

* ``explicit-empty-note`` — the execute phase writes ``notes/deviations.md``
  UNCONDITIONALLY (an explicit-empty ``no deviations`` record when nothing deviated) and the
  posterior GATES on that file through ``requires_files``. The gate is the enforcement: the
  runner's ``_missing_required_files`` (``workflow_runner.py:865``) refuses to spend on the
  posterior when execute skipped the note, instead of letting the posterior trust a stale
  document from a prior task.
* ``note-provenance`` — the posterior checks each inherited note's last commit
  (``git log -1 -- notes/<file>``) before trusting it; an untouched note is a stale note.

The assertions pin short, stable contract tokens (paths + the phrase), never prose: the same
shape ``tests/test_cap_2a_spec.py`` uses for a workflow spec's load-bearing prompt lines.
"""

from pathlib import Path

import pytest

from agentic_dynamics.experiment.experiment_spec import load_spec

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = ROOT / "workflows" / "repository" / "world_model_loop.yaml"


def _phases(spec) -> dict[str, dict]:
    """The spec's phase definitions keyed by name (the runner's own lookup shape)."""
    return {str(phase["name"]): phase for phase in spec.workflow.params["phases"]}


def test_posterior_requires_the_deviations_note():
    """The explicit-empty fix is ENFORCED: the posterior refuses to run without the note.

    Without this ``requires_files`` entry the convention is prompt-only; the artifact gate is
    what turns "the execute phase should write ``notes/deviations.md``" into a refusal.
    """
    posterior = _phases(load_spec(SPEC_PATH))["posterior"]
    assert "notes/deviations.md" in (posterior.get("requires_files") or [])


def test_execute_prompt_orders_an_explicit_empty_deviations_note():
    """Execute always writes the note, explicit-empty when nothing deviated."""
    prompt = str(_phases(load_spec(SPEC_PATH))["execute"].get("prompt", ""))
    assert "notes/deviations.md" in prompt
    assert "no deviations" in prompt


def test_posterior_prompt_requires_note_provenance():
    """The posterior must check a note's last commit before trusting it."""
    prompt = str(_phases(load_spec(SPEC_PATH))["posterior"].get("prompt", ""))
    assert "git log -1 -- notes/" in prompt
