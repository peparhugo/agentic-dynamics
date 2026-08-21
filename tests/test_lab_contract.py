"""Canonical-lab-contract guard (semantic-integrity release, phase s2).

``docs/review/semantic_integrity_review.md`` P0, required correction:

    A publication-eligible lab must carry ``input_dataset_id``,
    ``input_manifest_sha256``, ``registry_version``, ``metric_definition_version``,
    ``data_integrity_policy``, ``requires_external_service``. Enforce: a publication lab
    may consume only a canonical exported table or the registry resolver — not
    ``_results_summary.json``, arbitrary result globs, or unfiltered raw story files;
    ``build_data.py`` rejects lab JSON whose embedded manifest hash does not match the
    current manifest.

Phase s1 answered *which* labs may publish. This module guards *the contract*: the six
required fields, the rejection of a stale artifact, the impossibility of a summary-reading
lab being publication-eligible, and the source-level rule that a publication lab reaches
its data through the registry resolver rather than a glob.

The two tests the phase brief names explicitly are
:func:`test_stale_manifest_lab_json_is_rejected` and
:func:`test_summary_reading_lab_cannot_be_publication_eligible`.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from agentic_dynamics.reporting import canonical_corpus as cc
from agentic_dynamics.reporting.lab_contract import (
    CONTRACT_KEY,
    CONTRACT_VERSION,
    REQUIRED_FIELDS,
    build_contract,
    validate_contract,
)
from agentic_dynamics.reporting.lab_manifest import (
    LabEntry,
    load_lab_manifest,
    publication_labs,
)

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
MANIFEST_PATH = SCRIPTS_DIR / "lab_manifest.json"


# ---------------------------------------------------------------------------
# Fixtures — a synthetic manifest so the tests never depend on the real corpus
# ---------------------------------------------------------------------------


def _fake_manifest(rows: list[dict], *, schema_version: str = "1.0") -> dict:
    return {"schema_version": schema_version, "registry": rows}


def _row(locator: str, source_type: str = "story", state: str = "current") -> dict:
    return {
        "entity_id": f"e-{locator}",
        "knowledge_id": f"k-{locator}",
        "source_type": source_type,
        "logical_locator": locator,
        "source_uri": f"{source_type}:{locator}",
        "lifecycle_state": state,
    }


@pytest.fixture()
def tables_factory(tmp_path):
    """Build a :class:`CanonicalTables` over a synthetic manifest written to ``tmp_path``."""

    def _make(rows: list[dict]) -> cc.CanonicalTables:
        path = tmp_path / "data_manifest.json"
        path.write_text(json.dumps(_fake_manifest(rows)), encoding="utf-8")
        return cc.load_canonical_tables("story", manifest_path=path)

    return _make


@pytest.fixture()
def manifest_entry() -> LabEntry:
    """The real :class:`LabEntry` for ``lab_story_arc.py`` — the classification source of
    truth that :func:`validate_contract` compares the contract's semantic fields against."""
    entry = load_lab_manifest().get("lab_story_arc.py")
    assert entry is not None
    return entry


def _build(tables: cc.CanonicalTables, *, n_eligible: int = 0, n_used: int = 0, **kwargs) -> dict:
    """Build a ``lab_story_arc.py`` contract with explicit record counts.

    ``build_contract`` requires ``n_eligible_records``/``n_used_records`` explicitly
    (public-truth P1 removed the permissive defaults); the synthetic fixtures resolve to an
    empty story slice, so both default to 0 unless a test overrides them.
    """
    return build_contract(
        "lab_story_arc.py",
        tables,
        n_eligible_records=n_eligible,
        n_used_records=n_used,
        **kwargs,
    )


def _contract_payload(tables: cc.CanonicalTables, *, entry: LabEntry | None = None) -> dict:
    """A payload carrying a freshly built contract for ``lab_story_arc.py``."""
    return {CONTRACT_KEY: _build(tables)}


# ---------------------------------------------------------------------------
# 1. The six required fields
# ---------------------------------------------------------------------------


def test_contract_carries_all_required_fields(tables_factory):
    """Every required field (with the P2 rename/addition and the p3 record-scope fields),
    verbatim, on a fresh contract."""
    tables = tables_factory([_row("aaaaaaaaaaaa")])
    contract = _build(tables)

    for field_name in REQUIRED_FIELDS:
        assert field_name in contract, f"contract is missing {field_name}"
    assert contract["contract_version"] == CONTRACT_VERSION
    assert contract["lab"] == "lab_story_arc.py"
    # metric_definition_version comes from the manifest, not invented by the lab.
    assert contract["metric_definition_version"] == "story_arc/v1"
    assert contract["data_integrity_policy"] == "docs/data_integrity_findings.md"
    # Both identities are embedded (P2): the selection hash and the content hash.
    assert len(contract["registry_identity_sha256"]) == 64
    assert len(contract["resolved_input_sha256"]) == 64
    # The record-scope fields default to an honest "nothing resolved" for the empty slice.
    assert contract["n_resolved_records"] == 0
    assert contract["n_unused_eligible_records"] == 0


def test_contract_identity_tracks_the_manifest_it_was_built_from(tables_factory):
    """Two different registries must produce two different identities."""
    a = _build(tables_factory([_row("aaaaaaaaaaaa")]))
    b = _build(tables_factory([_row("bbbbbbbbbbbb")]))
    assert a["registry_identity_sha256"] != b["registry_identity_sha256"]

    # …and the same registry the same identity (the hash is a pure function of content).
    c = _build(tables_factory([_row("aaaaaaaaaaaa")]))
    assert a["registry_identity_sha256"] == c["registry_identity_sha256"]


def test_resolved_input_sha256_varies_with_the_table_slice(tables_factory):
    """The content hash is a function of *which* payloads resolved, not just the registry.

    The synthetic manifest names a story row with no payload file, so ``story`` resolves to
    an empty sequence; the hash is still a well-formed 64-hex digest, and the same slice
    over a different row hashes identically (both empty).
    """
    a = tables_factory([_row("aaaaaaaaaaaa")])
    empty = a.resolved_input_sha256
    assert len(empty) == 64

    # Same slice, different row → same (empty) content sequence.
    b = tables_factory([_row("bbbbbbbbbbbb")])
    assert b.resolved_input_sha256 == empty


def test_resolved_input_sha256_sensitive_to_payload_content(tmp_path, monkeypatch):
    """A payload whose measured content changes moves ``resolved_input_sha256`` (review P2).

    This is the gap P2 closes: the registry-identity hash is identical across the two
    resolutions (same registry, same row), but the content hash must change.
    """
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()
    payload_path = stories_dir / "note_service_aaa.json"
    manifest_path = tmp_path / "data_manifest.json"
    manifest_path.write_text(json.dumps(_fake_manifest([_row("aaa")])))
    monkeypatch.setattr(cc, "STORIES_DIR", stories_dir)

    payload_path.write_text(
        json.dumps({"story_id": "aaa", "model": "m", "summary": {"total_cost": 1.0}})
    )
    first = cc.load_canonical_tables("story", manifest_path=manifest_path)
    before = first.resolved_input_sha256
    before_registry = first.identity.registry_identity_sha256

    payload_path.write_text(
        json.dumps({"story_id": "aaa", "model": "m", "summary": {"total_cost": 2.0}})
    )
    second = cc.load_canonical_tables("story", manifest_path=manifest_path)

    assert second.resolved_input_sha256 != before
    assert second.identity.registry_identity_sha256 == before_registry


def test_identity_ignores_volatile_manifest_fields(tmp_path):
    """``generated_at``/``git_commit``/``files`` must not move the hash.

    The manifest records the sha256 of ``data.js`` — which publishing the labs produces.
    If the identity covered it, every publish would invalidate every lab it just
    published. The hash therefore covers the canonical-state registry only.
    """
    rows = [_row("aaaaaaaaaaaa")]
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "generated_at": "2026-01-01T00:00:00Z",
                "git_commit": "aaaa",
                "files": {"data.js": {"sha256": "1" * 64}},
                "registry": rows,
            }
        )
    )
    b.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "generated_at": "2026-12-31T00:00:00Z",
                "git_commit": "bbbb",
                "files": {"data.js": {"sha256": "2" * 64}},
                "registry": rows,
            }
        )
    )
    assert (
        cc.manifest_identity(manifest_path=a).registry_identity_sha256
        == cc.manifest_identity(manifest_path=b).registry_identity_sha256
    )


# ---------------------------------------------------------------------------
# 2. THE NAMED TEST — a stale-manifest lab JSON is rejected
# ---------------------------------------------------------------------------


def test_stale_manifest_lab_json_is_rejected(tables_factory, manifest_entry):
    """A lab built against an older registry may not publish."""
    old = tables_factory([_row("aaaaaaaaaaaa")])
    # Same row count (so registry_version is identical) but a *different* row — only the
    # registry-identity hash can tell the two registries apart.
    new = tables_factory([_row("bbbbbbbbbbbb")])

    payload = {
        "experiment_id": "lab_story_arc",
        CONTRACT_KEY: _build(old),
    }

    reason = validate_contract(
        payload, manifest_entry=manifest_entry, current_identity=new.identity
    )
    assert reason is not None, "a stale artifact must be rejected"
    assert "stale registry_identity_sha256" in reason
    assert "lab_story_arc.py" in reason, "the rejection must name the lab"

    # …and the same payload against its own registry is accepted.
    assert (
        validate_contract(payload, manifest_entry=manifest_entry, current_identity=old.identity)
        is None
    )


def test_missing_contract_is_rejected(tables_factory, manifest_entry):
    """A pre-contract artifact is exactly as untrustworthy as a stale one."""
    current = tables_factory([_row("aaaaaaaaaaaa")]).identity
    reason = validate_contract(
        {"experiment_id": "x"}, manifest_entry=manifest_entry, current_identity=current
    )
    assert reason is not None and CONTRACT_KEY in reason


@pytest.mark.parametrize("missing", REQUIRED_FIELDS)
def test_incomplete_contract_is_rejected(tables_factory, manifest_entry, missing):
    """Dropping any one required field is a rejection, field by field."""
    tables = tables_factory([_row("aaaaaaaaaaaa")])
    contract = _build(tables)
    contract.pop(missing)
    reason = validate_contract(
        {CONTRACT_KEY: contract}, manifest_entry=manifest_entry, current_identity=tables.identity
    )
    assert reason is not None and missing in reason


def test_empty_identity_field_is_rejected(tables_factory, manifest_entry):
    """An empty (rather than absent) identity value must not slip through."""
    tables = tables_factory([_row("aaaaaaaaaaaa")])
    contract = _build(tables)
    contract["registry_version"] = "  "
    reason = validate_contract(
        {CONTRACT_KEY: contract}, manifest_entry=manifest_entry, current_identity=tables.identity
    )
    assert reason is not None and "registry_version" in reason


def test_null_requires_external_service_is_allowed(tables_factory, manifest_entry):
    """``requires_external_service: null`` is the correct value, not a missing one."""
    tables = tables_factory([_row("aaaaaaaaaaaa")])
    contract = _build(tables)
    assert contract["requires_external_service"] is None
    assert (
        validate_contract(
            {CONTRACT_KEY: contract},
            manifest_entry=manifest_entry,
            current_identity=tables.identity,
        )
        is None
    )


def test_absent_registry_rejects_everything(tmp_path, manifest_entry):
    """With no manifest there is nothing to prove lineage against — publish nothing.

    The contract's semantic fields are all *correct* (so the semantic check passes); the
    rejection must come from the missing-registry identity, not from a field mismatch.
    """
    empty = cc.manifest_identity(manifest_path=tmp_path / "nope.json")
    assert empty.registry_identity_sha256 == ""
    contract = {
        "lab": "lab_story_arc.py",
        "input_dataset_id": "canonical_registry/story",
        "registry_identity_sha256": "a" * 64,
        "resolved_input_sha256": "a" * 64,
        "registry_version": "absent",
        "metric_definition_version": "story_arc/v1",
        "data_integrity_policy": "docs/data_integrity_findings.md",
        "requires_external_service": None,
        "contract_version": CONTRACT_VERSION,
        "n_resolved_records": 1,
        "n_eligible_records": 1,
        "n_used_records": 1,
        "n_excluded_records": 0,
        "n_unused_eligible_records": 0,
        "review_without_current_story": 0,
        "story_without_review": 0,
        "missing_required_field": 0,
        "outside_analysis_population": 0,
    }
    reason = validate_contract(
        {CONTRACT_KEY: contract}, manifest_entry=manifest_entry, current_identity=empty
    )
    assert reason is not None and "generate_manifest" in reason


# ---------------------------------------------------------------------------
# 2b. Semantic identity — every manifest-authored field is compared exactly
# ---------------------------------------------------------------------------

#: The seven fields validate_contract compares for exact equality, mapped to a mutated
#: (wrong) value that must trigger rejection. Each is the concrete drift class the review
#: named (the grit/v0-vs-v1 mismatch being the headline one).
SEMANTIC_MUTATIONS = (
    ("lab", "lab_story_review.py"),
    ("input_dataset_id", "canonical_registry/review"),
    ("registry_version", "data-manifest/9.9+0rows"),
    ("metric_definition_version", "story_arc/v0"),
    ("data_integrity_policy", "docs/some_other_policy.md"),
    ("requires_external_service", "sonar"),
    ("contract_version", "lab-contract/v1"),
)


@pytest.mark.parametrize("field,wrong", SEMANTIC_MUTATIONS)
def test_semantic_field_mismatch_is_rejected(tables_factory, manifest_entry, field, wrong):
    """Altering any one semantic field independently rejects publication (review P1).

    The registry-identity hash is left untouched, so only the semantic comparison can
    catch the mutation — exactly the gap the review found (a grit/v0 artifact accepted
    because its *hash* matched while its metric version did not).
    """
    tables = tables_factory([_row("aaaaaaaaaaaa")])
    contract = _build(tables)
    assert contract[field] != wrong, "the mutation value must actually differ"

    contract[field] = wrong
    reason = validate_contract(
        {CONTRACT_KEY: contract}, manifest_entry=manifest_entry, current_identity=tables.identity
    )
    assert reason is not None, f"mutation of {field} must be rejected"
    assert field in reason


def test_build_contract_requires_a_classified_lab(tables_factory):
    """Building a contract for a lab absent from the manifest raises (no /v0 fallback)."""
    tables = tables_factory([_row("aaaaaaaaaaaa")])
    with pytest.raises(ValueError, match="not classified"):
        build_contract("lab_does_not_exist.py", tables)


#: Record-count mutations that break the self-consistency invariant (review P2, c4;
#: extended in public-truth P1/p3) — each must be rejected by the consistency check.
#: (The exclusion-reason sum has its own message, covered by a dedicated test below.)
RECORD_COUNT_MUTATIONS = (
    ("n_excluded_records", lambda c: c["n_resolved_records"] - c["n_eligible_records"] + 1),
    ("n_used_records", lambda c: c["n_eligible_records"] + 1),
    ("n_unused_eligible_records", lambda c: c["n_eligible_records"] - c["n_used_records"] + 1),
)


@pytest.mark.parametrize("field,mutator", RECORD_COUNT_MUTATIONS)
def test_inconsistent_record_counts_are_rejected(tables_factory, manifest_entry, field, mutator):
    """A contract whose record counts do not sum is rejected (the ``n_input_records``
    defect the review named: a count that does not mean what it says)."""
    tables = tables_factory([_row("aaaaaaaaaaaa")])
    contract = _build(tables)
    contract[field] = mutator(contract)

    reason = validate_contract(
        {CONTRACT_KEY: contract}, manifest_entry=manifest_entry, current_identity=tables.identity
    )
    assert reason is not None
    assert "record counts inconsistent" in reason


def test_reason_counts_must_sum_to_excluded(tables_factory, manifest_entry):
    """An exclusion-reason breakdown that does not itemise ``n_excluded_records`` is
    rejected — a lab cannot drop records without saying which named reason dropped them."""
    tables = tables_factory([_row("aaaaaaaaaaaa")])
    # One resolved record, one excluded — but no reason count accounts for it.
    contract = _build(tables, n_resolved_records=1, n_eligible=0, n_used=0)
    reason = validate_contract(
        {CONTRACT_KEY: contract}, manifest_entry=manifest_entry, current_identity=tables.identity
    )
    assert reason is not None
    assert "exclusion reasons sum" in reason


def test_build_contract_requires_explicit_eligibility_and_usage(tables_factory):
    """The permissive ``eligible=resolved``/``used=eligible`` defaults are gone (P1)."""
    tables = tables_factory([_row("aaaaaaaaaaaa")])
    with pytest.raises(ValueError, match="n_eligible_records is required"):
        build_contract("lab_story_arc.py", tables, n_used_records=0)
    with pytest.raises(ValueError, match="n_used_records is required"):
        build_contract("lab_story_arc.py", tables, n_eligible_records=0)


# ---------------------------------------------------------------------------
# 3. THE NAMED TEST — a summary-reading lab cannot be publication-eligible
# ---------------------------------------------------------------------------


def test_summary_reading_lab_cannot_be_publication_eligible(tmp_path):
    """The manifest loader refuses the combination outright.

    Enforced at load time rather than only in a test, so the impossible state cannot
    exist even briefly in a pipeline run.
    """
    bad = {
        "schema_version": "lab-manifest/v1",
        "labs": {
            "lab_evil.py": {
                "lab_status": "historical",  # deliberately NOT quarantined
                "publication_eligible": True,
                "website_key": "evil",
                "reproduce_default": False,
                "output": "experiments/results/lab_evil.json",
                "input_sources": ["experiments/results/_results_summary.json"],
                "reads_retired_summary": True,
                "requires_external_service": None,
                "contract_status": "pending",
                "metric_definition_version": "evil/v1",
                "rationale": "smuggling the retired corpus onto the website",
            }
        },
    }
    path = tmp_path / "lab_manifest.json"
    path.write_text(json.dumps(bad), encoding="utf-8")

    with pytest.raises(ValueError, match="cannot be publication_eligible"):
        load_lab_manifest(path)


def test_publication_eligible_lab_must_declare_a_metric_definition_version(tmp_path):
    """An unnamed metric cannot be versioned, so it cannot be published."""
    bad = {
        "schema_version": "lab-manifest/v1",
        "labs": {
            "lab_x.py": {
                "lab_status": "canonical",
                "publication_eligible": True,
                "website_key": "x",
                "reproduce_default": True,
                "output": "experiments/results/lab_x.json",
                "input_sources": ["registry"],
                "reads_retired_summary": False,
                "requires_external_service": None,
                "contract_status": "enforced",
                "metric_definition_version": "",
                "rationale": "no metric version declared",
            }
        },
    }
    path = tmp_path / "lab_manifest.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="metric_definition_version"):
        load_lab_manifest(path)


# ---------------------------------------------------------------------------
# 4. Source-level rule — publication labs consume the resolver, never a glob
# ---------------------------------------------------------------------------


#: Result directories a publication-eligible lab may not walk on its own. Reading these
#: by glob is what "unfiltered raw story files" means in the review.
FORBIDDEN_GLOB_ROOTS = (
    "experiments/results/stories",
    "experiments/results/reviews",
    "experiments/results/analysis",
)


def _publication_scripts() -> list[LabEntry]:
    manifest = load_lab_manifest()
    return sorted((e for e in manifest if e.publication_eligible), key=lambda e: e.script)


@pytest.mark.parametrize("entry", _publication_scripts(), ids=lambda e: e.script)
def test_publication_lab_uses_the_canonical_resolver(entry: LabEntry):
    """Every publication-eligible lab imports the resolver + the contract emitter."""
    src = (SCRIPTS_DIR / entry.script).read_text(encoding="utf-8")
    assert "canonical_corpus" in src, (
        f"{entry.script} must consume agentic_dynamics.reporting.canonical_corpus"
    )
    assert "load_canonical_tables" in src, f"{entry.script} must call load_canonical_tables"
    assert "attach_contract" in src or "build_contract" in src, (
        f"{entry.script} must embed a lab_contract block in its output"
    )


@pytest.mark.parametrize("entry", _publication_scripts(), ids=lambda e: e.script)
def test_publication_lab_does_not_glob_raw_result_dirs(entry: LabEntry):
    """No publication lab may construct its own path into the raw result directories.

    AST-based (string literals only, docstrings excluded) so the prose explaining the rule
    does not trip it.
    """
    tree = ast.parse(
        (SCRIPTS_DIR / entry.script).read_text(encoding="utf-8"), filename=entry.script
    )

    docstrings: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and body
        ):
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                docstrings.add(id(first.value))

    offenders = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
        and any(root in node.value for root in FORBIDDEN_GLOB_ROOTS)
    ]
    assert not offenders, (
        f"{entry.script} builds its own path into a raw result directory {offenders} — "
        f"publication labs must resolve inputs through the registry"
    )


# ---------------------------------------------------------------------------
# 5. End-to-end — the artifacts on disk satisfy their own contract
# ---------------------------------------------------------------------------


def test_published_lab_artifacts_carry_a_valid_contract():
    """Every lab JSON build_data would publish validates against the current manifest.

    This is the integration check: manifest + resolver + emitter + validator agreeing on
    the real corpus. Skipped only when a lab has not been run yet (a gap, not a failure).
    The payload-content hash is recomputed from the lab's own resolved tables, so a drift in
    any resolved payload is caught here, not just a registry change.
    """
    from agentic_dynamics.reporting.lab_contract import expected_tables

    manifest = load_lab_manifest()
    identity = cc.current_manifest_identity()
    if not identity.registry_identity_sha256:  # pragma: no cover - manifest always present
        pytest.skip("no data_manifest.json registry in this checkout")

    checked = 0
    for _key, entry in sorted(publication_labs(manifest).items()):
        if not entry.output:
            continue
        artifact = ROOT / entry.output
        if not artifact.exists():
            continue
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        expected_content = cc.load_canonical_tables(*expected_tables(entry)).resolved_input_sha256
        reason = validate_contract(
            payload,
            manifest_entry=entry,
            current_identity=identity,
            expected_resolved_input_sha256=expected_content,
        )
        assert reason is None, reason
        checked += 1

    assert checked, "no publication-eligible lab artifacts found to validate"


# ---------------------------------------------------------------------------
# 6. Grit has exactly one meaning (semantic-integrity release, phase s4)
# ---------------------------------------------------------------------------

#: The one definition, as stated in README.md, the glossary, and scripts/lab_grit.py.
GRIT_DEFINITION = "G(s) = P(test_executed_success | perturbation_strength = s)"

#: Files that may mention the *history* of the collision (they explain the rename) — a
#: historical explanation is not a second meaning.
_COLLISION_HISTORY_ALLOWED = {
    "scripts/lab_correctness_escape_quadrants.py",
    "scripts/lab_manifest.json",
    "scripts/CONTEXT.md",
    "tests/test_lab_contract.py",
    "tests/test_lab_manifest.py",
    "tests/test_lab_outputs_canonical.py",
}


def test_the_formal_grit_lab_exists_and_is_canonical():
    """The definition the README publishes now has an implementation behind it."""
    entry = load_lab_manifest().get("lab_grit.py")
    assert entry is not None, "lab_grit.py must be classified"
    assert entry.lab_status == "canonical"
    assert entry.publication_eligible and entry.website_key == "grit"
    assert entry.reproduce_default, "the formal metric belongs in the core reproduction set"
    assert entry.metric_definition_version == "grit/v1"


def test_the_quadrant_lab_no_longer_claims_the_name():
    """``lab_grit_matrix.py`` is gone; its successor does not use 'grit' as a metric name."""
    assert not (SCRIPTS_DIR / "lab_grit_matrix.py").exists(), "the colliding name must be retired"
    quad = SCRIPTS_DIR / "lab_correctness_escape_quadrants.py"
    assert quad.exists()

    tree = ast.parse(quad.read_text(encoding="utf-8"), filename=quad.name)
    docstrings = _docstring_ids(tree)
    offenders = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
        and "grit" in node.value.lower()
    ]
    assert not offenders, (
        f"the quadrant lab still uses 'grit' in code/output strings: {offenders} "
        f"(the docstring may explain the rename; the metric may not carry the name)"
    )


def test_no_high_grit_key_survives_anywhere():
    """The colliding quadrant key ``high_grit`` is gone from live code and artifacts.

    Docstrings and comments are exempt: the rename has to be *explainable*, and a sentence
    saying "the quadrant formerly called ``high_grit`` is now ``robust``" is documentation,
    not a second meaning. What must not survive is the key itself — in code, in emitted
    JSON, or on the site.
    """
    hits: list[str] = []

    for path in list(ROOT.glob("scripts/*.py")) + list(ROOT.glob("src/agentic_dynamics/**/*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        docstrings = _docstring_ids(tree)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
                and "high_grit" in node.value
            ):
                hits.append(str(path.relative_to(ROOT)))
                break

    for pattern in ("apps/website/*.html", "apps/website/*.js", "experiments/results/**/*.json"):
        for path in ROOT.glob(pattern):
            if path.name == "lab_manifest.json":
                continue  # records the rename decision in prose
            try:
                if "high_grit" in path.read_text(encoding="utf-8"):
                    hits.append(str(path.relative_to(ROOT)))
            except (OSError, UnicodeDecodeError):  # pragma: no cover - binary/unreadable
                continue

    assert not hits, f"the retired quadrant key 'high_grit' still appears in {sorted(set(hits))}"


def test_readme_glossary_and_lab_state_the_same_definition():
    """One definition, three places — README, the site glossary, and the lab itself."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    glossary = (ROOT / "apps" / "website" / "glossary.html").read_text(encoding="utf-8")
    lab = (SCRIPTS_DIR / "lab_grit.py").read_text(encoding="utf-8")

    # README/lab use the exact spelling; the glossary renders it in HTML with &nbsp;.
    assert (
        "P(test_executed_success \\| perturbation_strength=s)" in readme
        or "P(test_executed_success | perturbation_strength=s)" in readme
    )
    assert GRIT_DEFINITION in lab
    assert "P(test-executed&nbsp;success | perturbation&nbsp;strength=s)" in glossary


def test_grit_output_reports_the_definition_and_its_caveats():
    """The artifact carries its own definition and states its limits.

    A two-point G(s) presented without the "only two strength levels" and "the levels come
    from different corpora" caveats would be a stronger claim than the data supports.
    """
    path = ROOT / "experiments" / "results" / "lab_grit.json"
    if not path.exists():  # pragma: no cover
        pytest.skip("lab_grit not run")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["metric_definition"] == GRIT_DEFINITION
    assert payload["by_strength"], "no strength levels computed"
    assert payload["by_strength_finding_corpus"], "the design-controlled comparison is missing"
    caveats = " ".join(payload["caveats"]).lower()
    assert "two" in caveats and "strength" in caveats
    assert "corpus" in caveats
    # Every reported rate either has a value with an interval, or is explicitly unsupported.
    for section in ("by_strength", "by_model_perturbed", "by_perturbation_class_perturbed"):
        for row in payload[section]:
            if row["grit"] is None:
                assert row["insufficient_support"] is True
            else:
                assert row["ci95_lo"] is not None and row["ci95_hi"] is not None


def _docstring_ids(tree: ast.AST) -> set[int]:
    """``id()`` of every docstring Constant (so prose can discuss what code may not do)."""
    out: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and body
        ):
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                out.add(id(first.value))
    return out
