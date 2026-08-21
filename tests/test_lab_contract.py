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


# ---------------------------------------------------------------------------
# 1. The six required fields
# ---------------------------------------------------------------------------


def test_contract_carries_exactly_the_six_required_fields(tables_factory):
    """The review's field list, verbatim, on a freshly built contract."""
    tables = tables_factory([_row("aaaaaaaaaaaa")])
    contract = build_contract("lab_story_arc.py", tables)

    for field_name in REQUIRED_FIELDS:
        assert field_name in contract, f"contract is missing {field_name}"
    assert contract["contract_version"] == CONTRACT_VERSION
    assert contract["lab"] == "lab_story_arc.py"
    # metric_definition_version comes from the manifest, not invented by the lab.
    assert contract["metric_definition_version"] == "story_arc/v1"
    assert contract["data_integrity_policy"] == "docs/data_integrity_findings.md"


def test_contract_identity_tracks_the_manifest_it_was_built_from(tables_factory):
    """Two different registries must produce two different identities."""
    a = build_contract("lab_story_arc.py", tables_factory([_row("aaaaaaaaaaaa")]))
    b = build_contract("lab_story_arc.py", tables_factory([_row("bbbbbbbbbbbb")]))
    assert a["input_manifest_sha256"] != b["input_manifest_sha256"]

    # …and the same registry the same identity (the hash is a pure function of content).
    c = build_contract("lab_story_arc.py", tables_factory([_row("aaaaaaaaaaaa")]))
    assert a["input_manifest_sha256"] == c["input_manifest_sha256"]


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
        cc.manifest_identity(manifest_path=a).input_manifest_sha256
        == cc.manifest_identity(manifest_path=b).input_manifest_sha256
    )


# ---------------------------------------------------------------------------
# 2. THE NAMED TEST — a stale-manifest lab JSON is rejected
# ---------------------------------------------------------------------------


def test_stale_manifest_lab_json_is_rejected(tables_factory):
    """A lab built against an older registry may not publish."""
    old = tables_factory([_row("aaaaaaaaaaaa")])
    new = tables_factory([_row("aaaaaaaaaaaa"), _row("bbbbbbbbbbbb")])

    payload = {
        "experiment_id": "lab_story_arc",
        CONTRACT_KEY: build_contract("lab_story_arc.py", old),
    }

    reason = validate_contract(payload, lab_script="lab_story_arc.py", current=new.identity)
    assert reason is not None, "a stale artifact must be rejected"
    assert "stale input_manifest_sha256" in reason
    assert "lab_story_arc.py" in reason, "the rejection must name the lab"

    # …and the same payload against its own registry is accepted.
    assert validate_contract(payload, lab_script="lab_story_arc.py", current=old.identity) is None


def test_missing_contract_is_rejected(tables_factory):
    """A pre-contract artifact is exactly as untrustworthy as a stale one."""
    current = tables_factory([_row("aaaaaaaaaaaa")]).identity
    reason = validate_contract(
        {"experiment_id": "x"}, lab_script="lab_story_arc.py", current=current
    )
    assert reason is not None and CONTRACT_KEY in reason


@pytest.mark.parametrize("missing", REQUIRED_FIELDS)
def test_incomplete_contract_is_rejected(tables_factory, missing):
    """Dropping any one required field is a rejection, field by field."""
    tables = tables_factory([_row("aaaaaaaaaaaa")])
    contract = build_contract("lab_story_arc.py", tables)
    contract.pop(missing)
    reason = validate_contract(
        {CONTRACT_KEY: contract}, lab_script="lab_story_arc.py", current=tables.identity
    )
    assert reason is not None and missing in reason


def test_empty_identity_field_is_rejected(tables_factory):
    """An empty (rather than absent) identity value must not slip through."""
    tables = tables_factory([_row("aaaaaaaaaaaa")])
    contract = build_contract("lab_story_arc.py", tables)
    contract["registry_version"] = "  "
    reason = validate_contract(
        {CONTRACT_KEY: contract}, lab_script="lab_story_arc.py", current=tables.identity
    )
    assert reason is not None and "registry_version" in reason


def test_null_requires_external_service_is_allowed(tables_factory):
    """``requires_external_service: null`` is the correct value, not a missing one."""
    tables = tables_factory([_row("aaaaaaaaaaaa")])
    contract = build_contract("lab_story_arc.py", tables)
    assert contract["requires_external_service"] is None
    assert (
        validate_contract(
            {CONTRACT_KEY: contract}, lab_script="lab_story_arc.py", current=tables.identity
        )
        is None
    )


def test_absent_registry_rejects_everything(tmp_path):
    """With no manifest there is nothing to prove lineage against — publish nothing."""
    empty = cc.manifest_identity(manifest_path=tmp_path / "nope.json")
    assert empty.input_manifest_sha256 == ""
    reason = validate_contract(
        {CONTRACT_KEY: {f: "x" for f in REQUIRED_FIELDS}},
        lab_script="lab_story_arc.py",
        current=empty,
    )
    assert reason is not None and "generate_manifest" in reason


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
    """
    manifest = load_lab_manifest()
    identity = cc.current_manifest_identity()
    if not identity.input_manifest_sha256:  # pragma: no cover - manifest always present in CI
        pytest.skip("no data_manifest.json registry in this checkout")

    checked = 0
    for _key, entry in sorted(publication_labs(manifest).items()):
        if not entry.output:
            continue
        artifact = ROOT / entry.output
        if not artifact.exists():
            continue
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        reason = validate_contract(payload, lab_script=entry.script, current=identity)
        assert reason is None, reason
        checked += 1

    assert checked, "no publication-eligible lab artifacts found to validate"
