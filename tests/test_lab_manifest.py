"""Lab-quarantine guard (semantic-integrity release, phase s1).

``docs/review/semantic_integrity_review.md`` P0: the lab-book path bypassed the canonical
data-integrity boundary — ten labs read the retired ``experiments/results/_results_summary.json``
while ``reproduce.sh`` still ran them and ``build_data.py`` still published their JSON with zero
provenance checks (a split publication path: canonical main metrics, legacy lab metrics).

Release item 1 quarantines those labs. This module is the guard that keeps the quarantine true.
It parses ``scripts/lab_manifest.json`` and asserts, at source level and with no external
dependencies:

1.  **Coverage** — every ``scripts/lab_*.py`` on disk is classified exactly once, and the
    manifest names no lab that does not exist.
2.  **Vocabulary** — ``lab_status`` is one of canonical/historical/quarantined and every entry
    carries the fields the review requires (``lab_status`` + ``publication_eligible``).
3.  **Quarantine is absolute** — a quarantined lab is in neither the reproduce default set nor
    the publication set.
4.  **Classification matches reality** — any lab whose source reaches ``_results_summary.json``
    (directly or through a known transitive loader) is quarantined. This is the check that
    catches a *future* lab quietly reintroducing the retired corpus.
5.  **Consumers agree with the manifest** — ``reproduce.sh`` derives its lab set from the
    manifest instead of hard-coding one, and ``build_data.py`` gates publication on it. Two
    hand-kept lists drifting apart is precisely how the original defect survived.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
MANIFEST_PATH = SCRIPTS_DIR / "lab_manifest.json"

#: The retired corpus the quarantine exists to keep out of reproduction + publication.
RETIRED_SUMMARY = "_results_summary.json"

#: Modules that read the retired summary on a lab's behalf. A lab importing one of these is
#: transitively summary-derived even though its own source never names the file. Keyed by the
#: import symbol that appears in lab source; the value is the evidence for the reader.
TRANSITIVE_SUMMARY_READERS = {
    # opencode_analyzer._load_summary reads _results_summary.json (reporting/opencode_analyzer.py).
    "opencode_analyzer": "reporting/opencode_analyzer.py::_load_summary",
    # Neo4jClient.load_runs populates ExperimentRun nodes from _results_summary.json
    # (knowledge/graph.py::load_runs), so every Cypher query over them is summary-derived.
    "Neo4jClient": "knowledge/graph.py::Neo4jClient.load_runs",
}

LAB_STATUSES = {"canonical", "historical", "quarantined"}


def _lab_scripts() -> set[str]:
    """Every lab book on disk, by file name."""
    return {p.name for p in SCRIPTS_DIR.glob("lab_*.py")}


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _labs() -> dict[str, dict]:
    return _manifest()["labs"]


# ---------------------------------------------------------------------------
# 1. Coverage — every lab classified, exactly once, no phantom entries
# ---------------------------------------------------------------------------


def test_manifest_exists_and_is_valid_json():
    assert MANIFEST_PATH.exists(), "scripts/lab_manifest.json is the lab classification manifest"
    assert _manifest().get("schema_version", "").startswith("lab-manifest/")


def test_every_lab_script_is_classified_with_zero_orphans():
    on_disk = _lab_scripts()
    classified = set(_labs())
    assert classified == on_disk, (
        f"unclassified labs on disk: {sorted(on_disk - classified)}; "
        f"manifest entries with no file: {sorted(classified - on_disk)}"
    )


# ---------------------------------------------------------------------------
# 2. Vocabulary — the review's required fields, with legal values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("script", sorted(_labs()))
def test_entry_carries_required_fields(script: str):
    entry = _labs()[script]
    assert entry["lab_status"] in LAB_STATUSES, f"{script}: illegal lab_status"
    assert isinstance(entry["publication_eligible"], bool), (
        f"{script}: publication_eligible must be a boolean, not a hedge"
    )
    assert isinstance(entry["reproduce_default"], bool)
    assert entry.get("rationale", "").strip(), (
        f"{script}: a classification without a rationale is an opinion, not evidence"
    )


# ---------------------------------------------------------------------------
# 3. Quarantine is absolute — out of reproduction AND out of publication
# ---------------------------------------------------------------------------


def test_quarantined_labs_are_not_published_and_not_reproduced():
    for script, entry in _labs().items():
        if entry["lab_status"] != "quarantined":
            continue
        assert not entry["publication_eligible"], f"{script}: quarantined but publication_eligible"
        assert not entry["reproduce_default"], f"{script}: quarantined but in the reproduce set"


def test_at_least_one_lab_is_quarantined():
    """Regression fuse: a manifest that quarantines nothing has silently lost the P0 fix."""
    quarantined = [s for s, e in _labs().items() if e["lab_status"] == "quarantined"]
    assert quarantined, "no labs quarantined — the P0 correction has been undone"


# ---------------------------------------------------------------------------
# 4. Classification matches the source — no lab may read the retired corpus and stay canonical
# ---------------------------------------------------------------------------


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """``id()`` of every docstring Constant node in the tree.

    Needed because the scan below must distinguish *using* the retired corpus from
    *documenting that we do not*: a contract-bearing lab's docstring legitimately says
    "no ``_results_summary.json``", and a naive substring scan would quarantine it for
    saying so.
    """
    out: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            out.add(id(first.value))
    return out


def _imported_names(tree: ast.AST) -> set[str]:
    """Every module path and bound name introduced by an import in this file."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
            names.update(a.asname for a in node.names if a.asname)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
            names.update(a.name for a in node.names)
            names.update(a.asname for a in node.names if a.asname)
    return names


def _reaches_retired_summary(script: str) -> tuple[bool, str]:
    """Does this lab reach ``_results_summary.json`` directly or transitively?

    An **AST** scan, not a substring scan: only real string literals (excluding
    docstrings) and real imports/identifiers count. Comments and prose can therefore
    discuss the retired corpus without tripping the guard, while any actual use — a path
    literal, or an import of a module known to read it — is caught.
    """
    tree = ast.parse((SCRIPTS_DIR / script).read_text(encoding="utf-8"), filename=script)
    docstrings = _docstring_nodes(tree)

    # 1. A non-docstring string literal naming the retired file = direct use.
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
            and RETIRED_SUMMARY in node.value
        ):
            return True, f"{script} names {RETIRED_SUMMARY} in a code literal"

    # 2. Importing (or referencing) a module/class known to read it = transitive use.
    imported = _imported_names(tree)
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    for symbol, evidence in TRANSITIVE_SUMMARY_READERS.items():
        hit = any(symbol in name for name in imported) or symbol in referenced
        if hit:
            return True, f"{script} uses {symbol} -> {evidence}"
    return False, ""


@pytest.mark.parametrize("script", sorted(_labs()))
def test_summary_reading_labs_are_quarantined(script: str):
    """The core invariant: touching the retired corpus forces quarantine.

    Written as a source scan rather than a hard-coded list so a NEW lab that reintroduces
    ``_results_summary.json`` fails here instead of quietly publishing.
    """
    reaches, evidence = _reaches_retired_summary(script)
    entry = _labs()[script]
    if reaches:
        assert entry["lab_status"] == "quarantined", (
            f"{script} reaches the retired corpus ({evidence}) but is "
            f"lab_status={entry['lab_status']!r} — it must be quarantined"
        )
        assert entry["reads_retired_summary"] is True, (
            f"{script}: reads_retired_summary must be true"
        )
    else:
        assert entry["reads_retired_summary"] is False, (
            f"{script}: flagged reads_retired_summary but no source evidence found"
        )


# ---------------------------------------------------------------------------
# 5. Consumers are driven by the manifest — no second, drifting list
# ---------------------------------------------------------------------------


def test_reproduce_sh_derives_its_lab_set_from_the_manifest():
    """``reproduce.sh`` must not hard-code lab names again."""
    src = (SCRIPTS_DIR / "reproduce.sh").read_text(encoding="utf-8")
    assert "reproduce_lab_scripts" in src, "reproduce.sh must query the manifest loader"
    # The old failure mode: a literal array of lab scripts. Quarantined names must not appear.
    for script, entry in _labs().items():
        if entry["lab_status"] == "quarantined":
            assert script not in src, f"reproduce.sh still names the quarantined lab {script}"


def test_build_data_gates_publication_on_the_manifest():
    """``build_data.py`` must consult the manifest, not a hand-kept lab_names list."""
    src = (SCRIPTS_DIR / "build_data.py").read_text(encoding="utf-8")
    assert "publication_labs" in src, "build_data must load the publication set from the manifest"
    assert "rejection_reason" in src, "build_data must log rejections by name"
    # The pre-quarantine hard-coded list is gone.
    assert "lab_names = [" not in src, "build_data still hard-codes a lab list"


def test_loader_agrees_with_the_raw_manifest():
    """The typed loader and the JSON must describe the same world (no parser drift)."""
    from agentic_dynamics.reporting.lab_manifest import (
        load_lab_manifest,
        publication_labs,
        quarantined_labs,
        reproduce_lab_scripts,
    )

    manifest = load_lab_manifest()
    raw = _labs()

    assert len(manifest) == len(raw)
    assert set(reproduce_lab_scripts(manifest)) == {
        s for s, e in raw.items() if e["reproduce_default"]
    }
    assert {e.script for e in quarantined_labs(manifest)} == {
        s for s, e in raw.items() if e["lab_status"] == "quarantined"
    }
    # Nothing quarantined can appear in the publication mapping.
    published = {e.script for e in publication_labs(manifest).values()}
    assert published.isdisjoint({s for s, e in raw.items() if e["lab_status"] == "quarantined"})


def test_published_data_js_carries_no_quarantined_lab_output():
    """End of the chain: the committed ``data.js`` must not still publish a quarantined lab.

    ``grit_matrix`` is the one quarantined lab that had a top-level website key; the guard is
    written generically so any future quarantined lab with a ``website_key`` is covered too.
    """
    data_js = ROOT / "apps" / "website" / "data.js"
    if not data_js.exists():  # pragma: no cover - data.js is generated, may be absent
        pytest.skip("apps/website/data.js not present")
    text = data_js.read_text(encoding="utf-8")
    payload = json.loads(text[text.index("{") : text.rindex("}") + 1])

    for script, entry in _labs().items():
        key = entry.get("website_key")
        if not key or entry["lab_status"] != "quarantined":
            continue
        section = payload.get(key)
        assert not section, (
            f"data.js still publishes '{key}' from the quarantined lab {script} "
            f"({len(section)} entries) — rebuild with build_data.py"
        )

    # And the publication-eligible labs are the only ones under `labs`.
    eligible_keys = {
        e["website_key"] for e in _labs().values() if e["publication_eligible"] and e["website_key"]
    }
    assert set(payload.get("labs", {})) <= eligible_keys
