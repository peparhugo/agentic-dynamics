"""Contribution-derived contract guard (measurement-contribution closure, m3).

``docs/review/measurement_contribution_review.md`` P1: record-scope contracts were
explicit, but not *proven against computation* — the validator checked the counts added
up, not that they described the records that actually contributed. m3 closes that gap:

* every canonical lab's ``compute()`` returns ``(result, contribution)``, a typed
  :class:`ContributionReport` the computation builds itself;
* the contract is DERIVED from that report (:func:`attach_contribution`), never
  hand-authored in ``main`` afterwards.

This module reconciles, for **every** canonical lab, the artifact's contract against a
*recomputed* contribution: it re-runs the lab's own ``compute()`` over the current
resolver tables and asserts the published ``n_resolved`` / ``n_eligible`` / ``n_used`` /
``n_excluded`` / ``n_unused_eligible`` and the four exclusion-reason counts all equal the
recomputed values. That is stronger than arithmetic self-consistency: a lab that declared
the wrong population fails here even though its contract still sums correctly.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from agentic_dynamics.reporting import canonical_corpus as cc
from agentic_dynamics.reporting.lab_contract import (
    CONTRACT_KEY,
    EXCLUSION_REASONS,
    ContributionReport,
)
from agentic_dynamics.reporting.lab_manifest import load_lab_manifest

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "experiments" / "results"


# ---------------------------------------------------------------------------
# The recompute surface: lab script -> (input tables, recompute callable)
# ---------------------------------------------------------------------------


def _module(script: str):
    """Import ``scripts.<name>`` by its manifest script name (``lab_foo.py``)."""
    return importlib.import_module(f"scripts.{script[:-3]}")


def _recompute(script: str, tables: cc.CanonicalTables) -> ContributionReport:
    """Re-run the lab's computation and return its self-reported contribution.

    The result payload is discarded — the contract only needs the contribution. Each lab's
    ``compute()`` returns ``(result, contribution)``; ``lab_story_review`` (no ``compute``)
    rebuilds its contribution from ``_collect_cells``.
    """
    mod = _module(script)
    if script == "lab_story_review.py":
        _cells, used_ids = mod._collect_cells(tables.stories)
        return ContributionReport.of(used_record_ids=used_ids)
    if script == "lab_cache_economics.py":
        return mod.compute(tables.stories)[1]
    if script == "lab_story_arc.py":
        return mod.compute(tables.stories)[1]
    if script == "lab_verification_frontier.py":
        return mod.compute(tables.stories)[1]
    if script == "lab_condition_effects.py":
        return mod.compute(tables.stories, tables.reviews)[1]
    if script == "lab_verification_value.py":
        return mod.compute(tables.stories, tables.reviews)[1]
    if script == "lab_quality_frontier.py":
        return mod.compute(tables.stories, tables.analysis)[1]
    if script == "lab_grit.py":
        return mod.compute(tables.findings, tables.stories)[1]
    raise AssertionError(f"no recompute mapping for {script}")


def _input_tables(script: str) -> tuple[str, ...]:
    """The resolver tables a lab reads, hard-coded here to match the lab's ``compute``."""
    return {
        "lab_cache_economics.py": ("story",),
        "lab_story_arc.py": ("story",),
        "lab_story_review.py": ("story",),
        "lab_verification_frontier.py": ("story",),
        "lab_condition_effects.py": ("story", "review"),
        "lab_verification_value.py": ("story", "review"),
        "lab_quality_frontier.py": ("story", "analysis"),
        "lab_grit.py": ("finding", "story"),
    }[script]


def _canonical_labs() -> list[str]:
    return sorted(e.script for e in load_lab_manifest() if e.publication_eligible)


# ---------------------------------------------------------------------------
# The reconciliation guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("script", _canonical_labs())
def test_contract_reconciles_with_recomputed_contribution(script: str):
    """The published contract equals the computation's own ContributionReport (m3).

    Recomputes the join with the lab's own ``compute()`` over the current resolver tables
    and asserts the artifact's contract records exactly that population — not just that
    the counts are self-consistent.
    """
    entry = load_lab_manifest().get(script)
    assert entry is not None and entry.output is not None
    path = ROOT / entry.output
    if not path.exists():  # pragma: no cover
        pytest.skip(f"{script} not run")
    payload = json.loads(path.read_text(encoding="utf-8"))
    contract = payload[CONTRACT_KEY]

    tables = cc.load_canonical_tables(*_input_tables(script))
    contribution = _recompute(script, tables)

    # The computation's own invariants (defence in depth).
    assert contribution.eligible + contribution.excluded == contribution.resolved
    assert contribution.used + contribution.unused_eligible == contribution.eligible
    assert len(contribution.used_record_ids) == contribution.used

    # The contract carries the recomputed population, field for field.
    assert contract["n_resolved_records"] == contribution.resolved, (
        f"{script}: declared {contract['n_resolved_records']} resolved, computed "
        f"{contribution.resolved}"
    )
    assert contract["n_eligible_records"] == contribution.eligible, script
    assert contract["n_used_records"] == contribution.used, script
    assert contract["n_excluded_records"] == contribution.excluded, script
    assert contract["n_unused_eligible_records"] == contribution.unused_eligible, script
    for reason in EXCLUSION_REASONS:
        assert contract[reason] == contribution.exclusion_reasons.get(reason, 0), (
            f"{script}: contract.{reason}={contract[reason]!r} but the computation "
            f"reported {contribution.exclusion_reasons.get(reason, 0)!r}"
        )


def test_contribution_report_derives_resolved_from_buckets():
    """``ContributionReport.of`` forces full accounting of every resolved record."""
    c = ContributionReport.of(
        used_record_ids=["a", "b", "c"],
        unused_eligible=2,
        exclusion_reasons={"review_without_current_story": 3, "story_without_review": 2},
    )
    assert c.used == 3
    assert c.eligible == 5
    assert c.excluded == 5
    assert c.resolved == 10
    assert c.unused_eligible == 2
    assert c.used_record_ids == ("a", "b", "c")


def test_contribution_report_drops_zero_reasons():
    """A zero-count exclusion reason is omitted from ``exclusion_reasons``."""
    c = ContributionReport.of(
        used_record_ids=["x"],
        exclusion_reasons={"missing_required_field": 0},
    )
    assert c.exclusion_reasons == {}
    assert c.excluded == 0
    assert c.resolved == 1
