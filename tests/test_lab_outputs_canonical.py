"""Canonical-output guard (semantic-integrity release, phase s3).

``docs/reviews/semantic_integrity_review.md`` recommended release item 3:

    Rebuild derived outputs — every active lab + website dataset from current canonical
    records only. […] Verify zero lab outputs carry the retired summary's lineage; the
    site's lab sections draw only from contract-bearing JSONs.

s1 decided which labs may publish, s2 gave the survivors a contract. This module makes
item 3's *verification* permanent rather than a one-time observation, asserting four
things that together mean "the published derivation path is canonical end to end":

1. ``experiments/results/lab_*.json`` contains **only** manifest-declared, non-quarantined
   outputs, and every publication-eligible one is present. Quarantined artifacts live in
   ``legacy_labs/`` and undeclared files are rejected outright, so a stale file can no
   longer be mistaken for a current measurement.
2. No live lab output carries the retired summary's lineage — checked structurally
   (a valid contract naming the canonical resolver) rather than by keyword.
3. Every published artifact is **current**: its ``n_input_records`` matches what the
   resolver returns from today's registry, so "regenerated from current canonical
   records" is a checkable claim, not a changelog entry.
4. Every ``D.labs.<key>`` the website reads exists in ``data.js`` and came from a
   publication-eligible lab — and the quarantined Grit section publishes nothing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from agentic_dynamics.reporting import canonical_corpus as cc
from agentic_dynamics.reporting.lab_contract import (
    CONTRACT_KEY,
    EXCLUSION_REASONS,
    validate_contract,
)
from agentic_dynamics.reporting.lab_manifest import load_lab_manifest, publication_labs

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "experiments" / "results"
LEGACY_DIR = RESULTS_DIR / "legacy_labs"
DATA_JS = ROOT / "apps" / "website" / "data.js"
WEBSITE_DIR = ROOT / "apps" / "website"

#: The retired corpus. Its name must not appear in any live lab artifact's lineage.
RETIRED_SUMMARY = "_results_summary.json"


def _data_js_payload() -> dict | None:
    """Parse ``window.DYNAMICS_DATA`` out of the generated ``data.js``."""
    if not DATA_JS.exists():  # pragma: no cover - generated file, present in CI
        return None
    text = DATA_JS.read_text(encoding="utf-8")
    return json.loads(text[text.index("{") : text.rindex("}") + 1])


# ---------------------------------------------------------------------------
# 1. The live results directory holds only contract-bearing outputs
# ---------------------------------------------------------------------------


def test_live_results_dir_holds_only_declared_non_quarantined_lab_outputs():
    """Every ``experiments/results/lab_*.json`` is a manifest-DECLARED, non-quarantined output.

    The teeth are unchanged in both directions that matter: a file no manifest entry claims
    still fails (the stale-artifact case this guard exists for), and a quarantined lab's
    output still may not sit here (``test_quarantined_labs_write_into_legacy_labs`` pins the
    declaration; this pins the directory).

    What changed: the manifest has THREE statuses (``lab_manifest.LAB_STATUSES``) and this
    check only ever knew two. ``historical`` — "kept for provenance and still runnable by
    hand, but its question or corpus belongs to a superseded measurement era; not published"
    — is neither publication-eligible nor quarantined. Keying the expected set off
    ``publication_eligible`` alone therefore declared the manifest's own ``output`` path
    illegal the moment the first historical lab landed (``lab_beta_from_corpus``, whose
    output is a live input to ``control.lease_registry``'s β lease sizing, not a stale
    measurement). A historical lab reads canonical sources, so relocating it to
    ``legacy_labs/`` would also misfile it — that directory's README scopes it to
    retired-summary lineage.

    The publication path itself is unaffected: invariants 2-4 below still key off
    ``_published_artifacts()`` / ``publication_labs()``, so nothing non-eligible can reach
    ``data.js`` or claim a lineage contract.
    """
    manifest = load_lab_manifest()
    declared = {Path(e.output).name: e for e in manifest if e.output and not e.quarantined}
    on_disk = {p.name for p in RESULTS_DIR.glob("lab_*.json")}

    undeclared = sorted(on_disk - set(declared))
    assert not undeclared, (
        f"unexpected lab artifacts in the canonical results dir: {undeclared} — no manifest "
        f"entry declares them (move non-canonical outputs to legacy_labs/)"
    )
    missing = sorted({n for n, e in declared.items() if e.publication_eligible} - on_disk)
    assert not missing, (
        f"publication-eligible lab outputs missing from the canonical results dir: {missing} "
        f"— re-run the core lab set"
    )


def test_quarantined_labs_write_into_legacy_labs():
    """A quarantined lab's declared output path is inside ``legacy_labs/``.

    Without this, running a quarantined lab by hand would drop a non-canonical artifact
    back into the canonical directory and quietly break invariant 1.
    """
    for entry in load_lab_manifest():
        if not entry.quarantined or not entry.output:
            continue
        assert "legacy_labs/" in entry.output, (
            f"{entry.script} writes to {entry.output} — a quarantined lab must write into "
            f"experiments/results/legacy_labs/"
        )


def test_quarantined_lab_scripts_point_at_the_legacy_dir():
    """Source-level check: the script's own output constant matches the manifest.

    The manifest could say ``legacy_labs/`` while the script still wrote to the canonical
    directory; this closes that gap.
    """
    for entry in load_lab_manifest():
        if not entry.quarantined or not entry.output:
            continue
        src = (ROOT / "scripts" / entry.script).read_text(encoding="utf-8")
        assert '"legacy_labs"' in src, (
            f"{entry.script} does not build its output path through legacy_labs/"
        )


def test_legacy_dir_documents_itself():
    """``legacy_labs/`` carries a README explaining why its contents are not canonical."""
    readme = LEGACY_DIR / "README.md"
    assert readme.exists(), "legacy_labs/ must explain itself"
    text = readme.read_text(encoding="utf-8")
    assert RETIRED_SUMMARY in text
    assert "lab_contract" in text


# ---------------------------------------------------------------------------
# 2 + 3. Zero retired lineage; every published artifact is current
# ---------------------------------------------------------------------------


def _published_artifacts() -> list[tuple[str, Path, dict]]:
    """``(lab_script, path, payload)`` for every publication-eligible artifact on disk."""
    out = []
    for _key, entry in sorted(publication_labs(load_lab_manifest()).items()):
        if not entry.output:
            continue
        path = ROOT / entry.output
        if path.exists():
            out.append((entry.script, path, json.loads(path.read_text(encoding="utf-8"))))
    return out


def test_no_live_lab_output_carries_retired_summary_lineage():
    """Item 3's headline claim, checked directly.

    Structural, not keyword-based: a live artifact must carry a contract whose
    ``input_dataset_id`` names the canonical registry resolver. A lab derived from the
    retired summary cannot produce one — it has no registry identity to embed.
    """
    artifacts = _published_artifacts()
    assert artifacts, "no publication-eligible lab artifacts found — run the core lab set"

    for lab, path, payload in artifacts:
        contract = payload.get(CONTRACT_KEY)
        assert isinstance(contract, dict), f"{lab}: {path.name} has no contract"
        assert contract["input_dataset_id"].startswith("canonical_registry/"), (
            f"{lab}: input_dataset_id {contract['input_dataset_id']!r} is not the registry resolver"
        )
        assert RETIRED_SUMMARY not in json.dumps(contract), (
            f"{lab}: contract references the retired corpus"
        )


def test_published_artifacts_match_the_current_registry():
    """ "Regenerated from current canonical records" is verified, not asserted.

    Each artifact's contract must validate against today's manifest identity, its
    ``n_resolved_records`` must equal what the resolver returns now, and the record-count
    scope must be self-consistent (``resolved = eligible + excluded`` with the exclusions
    breakdown accounting for every excluded record). A lab re-run before the corpus changed
    passes; one left behind fails.
    """
    identity = cc.current_manifest_identity()
    if not identity.registry_identity_sha256:  # pragma: no cover - manifest present in CI
        pytest.skip("no data_manifest.json registry in this checkout")

    # Derived from the resolver's own table registry, so a newly added table (s4 added
    # ``finding`` for the Grit lab) is covered automatically instead of KeyError-ing here.
    everything = cc.load_canonical_tables(*cc.TABLES)
    resolved = {name: len(everything.rows(name)) for name in cc.TABLES}
    manifest = load_lab_manifest()

    for lab, _path, payload in _published_artifacts():
        entry = manifest.get(lab)
        assert entry is not None
        contract = payload[CONTRACT_KEY]
        reason = validate_contract(payload, manifest_entry=entry, current_identity=identity)
        assert reason is None, reason

        # input_dataset_id is "canonical_registry/story+review" — recompute its size.
        slice_name = contract["input_dataset_id"].split("/", 1)[1]
        expected = sum(resolved[t] for t in slice_name.split("+"))
        assert contract["n_resolved_records"] == expected, (
            f"{lab}: contract claims {contract['n_resolved_records']} resolved records but "
            f"the current registry resolves {expected} for '{slice_name}' — re-run the lab"
        )
        # The scope must be self-consistent and honest (review P2; tightened in P1).
        assert (
            contract["n_eligible_records"] + contract["n_excluded_records"]
            == contract["n_resolved_records"]
        ), f"{lab}: eligible + excluded != resolved"
        assert (
            contract["n_used_records"] + contract["n_unused_eligible_records"]
            == contract["n_eligible_records"]
        ), f"{lab}: used + unused_eligible != eligible"
        reason_total = sum(contract[r] for r in EXCLUSION_REASONS)
        assert reason_total == contract["n_excluded_records"], (
            f"{lab}: exclusion reasons sum to {reason_total}, not {contract['n_excluded_records']}"
        )


def test_condition_effects_contract_reconciles_with_output():
    """The contract's record scope matches what the output actually consumed (review P1).

    ``lab_condition_effects`` resolves 215 stories + 242 reviews, but its rows consume only
    the 155 reviews whose story is still current. The contract must say so — ``n_used`` must
    equal ``stories + joined_reviews``, not "everything resolved", and the per-condition rows
    must actually carry those joined reviews.
    """
    path = RESULTS_DIR / "lab_condition_effects.json"
    if not path.exists():  # pragma: no cover
        pytest.skip("lab_condition_effects not run")
    payload = json.loads(path.read_text(encoding="utf-8"))
    contract = payload[CONTRACT_KEY]
    summary = payload["summary"]

    assert contract["n_resolved_records"] == summary["stories"] + summary["reviews"]
    assert contract["n_used_records"] == summary["stories"] + summary["joined_reviews"], (
        f"declared n_used={contract['n_used_records']} != "
        f"stories({summary['stories']}) + joined_reviews({summary['joined_reviews']})"
    )
    assert contract["review_without_current_story"] == summary["reviews_without_current_story"]
    # The per-condition rows actually carry the joined reviews the contract claims.
    assert sum(c["reviews"] for c in payload["conditions"]) == summary["joined_reviews"]


def test_verification_value_join_publishes_no_placeholder_identity():
    """The story→review join fails explicitly — no ``model: "?"`` row survives (m1).

    ``docs/reviews/measurement_contribution_review.md`` P0: ``lab_verification_value``
    converted unmatched reviews into ``stories.get(sid, ("?", 0))`` placeholder rows (432
    commit-review observations driving a −0.154 correlation) while its contract declared
    457/457/457/0. The m1 fix makes the join fail explicitly: a review whose ``_story_id``
    names no current resolved story is counted as ``review_without_current_story`` and
    excluded, a current story no review joined is counted as ``story_without_review``, and
    the contract declares the joined populations. This test recomputes the join from the
    resolver and reconciles the artifact against it, so a reintroduced placeholder breaks
    here before any artifact is regenerated.
    """
    from scripts import lab_verification_value as lvv

    path = RESULTS_DIR / "lab_verification_value.json"
    if not path.exists():  # pragma: no cover
        pytest.skip("lab_verification_value not run")
    payload = json.loads(path.read_text(encoding="utf-8"))
    contract = payload[CONTRACT_KEY]
    summary = payload["summary"]

    tables = cc.load_canonical_tables("story", "review")
    recomputed, recomputed_contribution = lvv.compute(tables.stories, tables.reviews)
    rs = recomputed["summary"]

    # (1) No recomputed — and no published — row carries a placeholder identity.
    assert recomputed["rows"], "the recomputed join produced no rows"
    assert all(r["model"] != "?" for r in recomputed["rows"]), (
        "the join still emits a placeholder model '?' row"
    )
    assert all(r["model"] for r in payload["rows"]), "a published row has an empty model"
    assert all(r["model"] != "?" for r in payload["rows"]), (
        "a published row still carries model '?' — regenerate the artifact"
    )

    # (2) Every review contributing to the correlation has a joined current story: the
    # recomputed join counts and rows must equal what the artifact declared.
    assert summary["review_without_current_story"] == rs["review_without_current_story"]
    assert summary["story_without_review"] == rs["story_without_review"]
    assert payload["rows"] == recomputed["rows"], (
        "the published rows do not match the recomputed join — regenerate the artifact"
    )

    # (3) The contract counts reconcile with the join, not "everything resolved".
    n_resolved = len(tables.stories) + len(tables.reviews)
    n_excluded = rs["review_without_current_story"] + rs["story_without_review"]
    assert contract["n_resolved_records"] == n_resolved
    assert contract["n_excluded_records"] == n_excluded
    assert contract["review_without_current_story"] == rs["review_without_current_story"]
    assert contract["story_without_review"] == rs["story_without_review"]
    assert contract["n_eligible_records"] == n_resolved - n_excluded
    assert contract["n_used_records"] == contract["n_eligible_records"]
    assert contract["n_unused_eligible_records"] == 0
    # The correlation in the artifact must be the one the recomputed join produces.
    assert summary["correlation_tests_vs_worse_rate"] == rs["correlation_tests_vs_worse_rate"]


# ---------------------------------------------------------------------------
# 4. The site's lab sections draw only from contract-bearing JSONs
# ---------------------------------------------------------------------------


def test_site_lab_keys_are_all_contract_bearing():
    """Every ``D.labs.<key>`` referenced by the site resolves to an eligible lab in data.js."""
    payload = _data_js_payload()
    if payload is None:  # pragma: no cover
        pytest.skip("apps/website/data.js not generated")

    published = set(payload.get("labs", {}))
    eligible = {
        e.website_key for e in load_lab_manifest() if e.publication_eligible and e.website_key
    }
    assert published <= eligible, (
        f"data.js publishes lab keys that are not publication-eligible: {sorted(published - eligible)}"
    )

    # Every key the HTML/JS reads must actually be present, or the section renders blank.
    referenced: set[str] = set()
    for page in WEBSITE_DIR.glob("*.html"):
        referenced |= set(
            re.findall(r"\bD\.labs\.([A-Za-z_][A-Za-z0-9_]*)", page.read_text(encoding="utf-8"))
        )
    for page in WEBSITE_DIR.glob("*.js"):
        if page.name == "data.js":
            continue
        referenced |= set(
            re.findall(r"\bD\.labs\.([A-Za-z_][A-Za-z0-9_]*)", page.read_text(encoding="utf-8"))
        )

    missing = referenced - published
    assert not missing, f"the site reads D.labs.{sorted(missing)} but data.js does not publish it"


def test_every_published_lab_section_carries_its_contract_into_data_js():
    """The lineage travels with the numbers: contracts survive into ``data.js``."""
    payload = _data_js_payload()
    if payload is None:  # pragma: no cover
        pytest.skip("apps/website/data.js not generated")

    labs = payload.get("labs", {})
    assert labs, "data.js publishes no lab sections at all"
    for key, section in labs.items():
        assert CONTRACT_KEY in section, (
            f"data.js labs.{key} has no {CONTRACT_KEY} — it was published without lineage"
        )


def test_quarantined_quadrant_section_publishes_nothing():
    """The one quarantined lab with a top-level website key stays empty.

    Renamed in s4 with its lab: ``grit_matrix`` -> ``correctness_escape_quadrants``. The old
    key must be gone entirely, or the site could read a stale section that nothing maintains.
    """
    payload = _data_js_payload()
    if payload is None:  # pragma: no cover
        pytest.skip("apps/website/data.js not generated")
    assert "grit_matrix" not in payload, (
        "the retired data.js key 'grit_matrix' is back — s4 renamed it to "
        "'correctness_escape_quadrants'"
    )
    assert payload.get("correctness_escape_quadrants") == [], (
        "correctness_escape_quadrants is quarantined (its lab reads the retired summary) and "
        "must publish no points"
    )


def test_site_does_not_hard_code_lab_table_rows():
    """The arc + condition tables must render from data.js, not from transcribed HTML.

    They previously carried hand-typed figures from an older corpus — the drift that made
    item 3 necessary. The tbodies are now populated by JS from ``D.labs``.
    """
    evidence = (WEBSITE_DIR / "evidence.html").read_text(encoding="utf-8")
    for tbody_id in ("arc-session-tbody", "condition-tbody"):
        assert f'id="{tbody_id}"' in evidence, f"{tbody_id} placeholder missing"
    # The JS that fills them must reference the contract-bearing labs.
    assert "labs.story_arc" in evidence
    assert "labs.condition_effects" in evidence


# ---------------------------------------------------------------------------
# 5. No unmeasured value is published as a measurement
# ---------------------------------------------------------------------------


def test_lsp_signal_is_null_when_the_language_server_never_ran():
    """An absent signal must be ``null``, never an averaged-in zero.

    Every ``analysis_*.json`` carries ``deep.lsp = {"available": false, "errors": 0}``, so
    averaging the raw ``errors`` field published "0.0 LSP errors per story" — read on the
    site as *clean code* when the truth is *no diagnostics tool ran*. The lab now counts
    only cells where ``available`` is true (``docs/data_integrity_findings.md``: an
    unmeasured value is null).
    """
    path = ROOT / "experiments" / "results" / "lab_quality_frontier.json"
    if not path.exists():  # pragma: no cover
        pytest.skip("quality frontier lab not run")
    payload = json.loads(path.read_text(encoding="utf-8"))

    available = payload["summary"].get("lsp_available_cells", 0)
    for model in payload["models"]:
        if model["lsp_cells"] == 0:
            assert model["lsp_errors_per_cell"] is None, (
                f"{model['model']}: publishes a fabricated 0.0 LSP rate with no available cells"
            )
    if available == 0:
        assert all(m["lsp_errors_per_cell"] is None for m in payload["models"])


def test_site_does_not_hard_code_quality_frontier_figures():
    """The quality-frontier claim renders from the lab, not from transcribed numbers."""
    evidence = (WEBSITE_DIR / "evidence.html").read_text(encoding="utf-8")
    assert 'id="qf-cheapest"' in evidence and 'id="qf-best-quality"' in evidence
    assert "labs.quality_frontier" in evidence
    # The superseded transcriptions must not come back.
    for stale in ("13.5/story", "0.167 on code quality", "cleanest LSP (5.1)"):
        assert stale not in evidence, f"stale transcribed figure returned: {stale}"
