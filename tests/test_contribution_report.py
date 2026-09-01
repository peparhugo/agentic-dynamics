"""Contribution-derived contract guard (measurement-contribution closure, m3).

``docs/reviews/measurement_contribution_review.md`` P1: record-scope contracts were
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
    refs_digest,
)
from agentic_dynamics.reporting.lab_manifest import load_lab_manifest

pytestmark = pytest.mark.fast

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
        _cells, used_refs = mod._collect_cells(tables.stories)
        return ContributionReport.of(used_record_refs=used_refs)
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
    assert len(contribution.used_record_refs) == contribution.used
    assert len(contribution.excluded_record_refs) == contribution.excluded
    assert contribution.used_contributions == contribution.used
    assert contribution.used_unique_records <= contribution.used_contributions

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

    # f2 exact contributor attestation: the contract's ref digests equal the recomputed ref
    # set, and the unique/contribution counts match the deduplicated set.
    assert contract["used_record_refs_sha256"] == refs_digest(contribution.used_record_refs), (
        f"{script}: used_record_refs_sha256 does not match the recomputed contributor set"
    )
    assert contract["excluded_record_refs_sha256"] == refs_digest(
        contribution.excluded_record_refs
    ), f"{script}: excluded_record_refs_sha256 does not match the recomputed excluded set"
    assert contract["used_unique_records"] == contribution.used_unique_records, script
    assert contract["used_contributions"] == contribution.used_contributions, script


def test_contribution_report_derives_resolved_from_buckets():
    """``ContributionReport.of`` forces full accounting of every resolved record."""
    c = ContributionReport.of(
        used_record_refs=["a", "b", "c"],
        excluded_record_refs=["d", "e"],
        unused_eligible=2,
        exclusion_reasons={"review_without_current_story": 2},
    )
    assert c.used == 3
    assert c.used_unique_records == 3
    assert c.used_contributions == 3
    assert c.eligible == 5
    assert c.excluded == 2
    assert c.resolved == 7
    assert c.unused_eligible == 2
    assert c.used_record_refs == ("a", "b", "c")
    assert c.excluded_record_refs == ("d", "e")


def test_contribution_report_drops_zero_reasons():
    """A zero-count exclusion reason is omitted from ``exclusion_reasons``."""
    c = ContributionReport.of(
        used_record_refs=["x"],
        exclusion_reasons={"missing_required_field": 0},
    )
    assert c.exclusion_reasons == {}
    assert c.excluded == 0
    assert c.resolved == 1


# ---------------------------------------------------------------------------
# f2 — exact contributor attestation guards
# ---------------------------------------------------------------------------


def test_refs_digest_is_deterministic_and_order_independent():
    """The digest is a pure function of the ref SET, not the iteration order."""
    assert refs_digest(["b", "a"]) == refs_digest(["a", "b"])
    assert refs_digest(["a"]) != refs_digest([])
    assert len(refs_digest([])) == 64


def test_altered_contributor_set_changes_the_digest():
    """Mutation: changing (adding/removing) one contributor changes the digest."""
    refs = ["story:e1:k1", "story:e2:k2", "review:e3:k3"]
    digest = refs_digest(refs)
    assert refs_digest(refs + ["finding:e4:k4"]) != digest, (
        "an added contributor must move the digest"
    )
    assert refs_digest(refs[:2]) != digest, "a removed contributor must move the digest"
    assert refs_digest(["story:e1:k1", "story:e2:k2", "review:e3:kX"]) != digest, (
        "a renamed contributor must move the digest"
    )


def test_duplicate_ref_is_rejected():
    """Mutation: a duplicate ref is rejected unless multiplicity is explicitly permitted."""
    with pytest.raises(ValueError, match="duplicate"):
        ContributionReport.of(used_record_refs=["story:e1:k1", "story:e1:k1"])


def test_duplicate_ref_permitted_with_multiplicity():
    """``allow_multiplicity=True`` permits a record contributing more than once."""
    c = ContributionReport.of(used_record_refs=["a", "a"], allow_multiplicity=True)
    assert c.used == 2
    assert c.used_contributions == 2
    assert c.used_unique_records == 1


def test_empty_ref_is_rejected():
    """An empty (identity-less) ref cannot be attested."""
    with pytest.raises(ValueError, match="empty"):
        ContributionReport.of(used_record_refs=["story:e1:k1", ""])


def test_negative_exclusion_count_is_rejected():
    """A negative exclusion count is a defect, not a correction."""
    with pytest.raises(ValueError, match="negative"):
        ContributionReport.of(
            used_record_refs=["a"],
            exclusion_reasons={"missing_required_field": -1},
        )


def test_unknown_exclusion_reason_is_rejected():
    """An exclusion reason outside the vocabulary cannot be smuggled through."""
    with pytest.raises(ValueError, match="unknown exclusion reason"):
        ContributionReport.of(
            used_record_refs=["a"],
            exclusion_reasons={"mystery_drop": 1},
        )


def test_excluded_ref_count_must_match_exclusion_reasons():
    """The excluded ref ledger must itemise exactly the declared exclusion count."""
    with pytest.raises(ValueError, match="itemised"):
        ContributionReport.of(
            used_record_refs=["a"],
            excluded_record_refs=["x", "y"],
            exclusion_reasons={"missing_required_field": 1},
        )


def test_record_id_qualifies_story_against_its_analysis():
    """Mutation (the review's P1 case): a story and its analysis no longer collide."""
    story = {"_table": "story", "_registry": {"entity_id": "e1", "knowledge_id": "k1"}}
    analysis = {
        "_table": "analysis",
        "_registry": {"entity_id": "e1", "knowledge_id": "k1"},
        "payload": {"deep": {"solution": {"lines_of_code": 5}}},
    }
    from agentic_dynamics.reporting.lab_contract import record_id

    assert record_id(story) != record_id(analysis)
    assert record_id(story).startswith("story:e1:k1")
    assert record_id(analysis).startswith("analysis:e1:")
