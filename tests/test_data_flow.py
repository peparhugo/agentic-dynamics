"""Data-flow guards (critique rec 8) — separate from the import-graph lint.

These assert *behaviour at the data level*, not just the import graph:

* **retrieval never supplies canonical facts** — the ``retrieve → construct → render`` seam is
  a pure reader: it references the KB write path (``publish_event``) zero times, and its
  fusion gate hard-excludes ``Authority.POLICY`` candidates (pinned policy is read directly
  from the checkout, never surfaced as a retrieved fact).
* **knowledge never actuates** — no knowledge module imports or calls the candidate-instruction
  producer ``actuation_ingestion.derive_actuation_record``.

See ``tests/test_dependency_direction.py`` for the import-graph lint and
``docs/release/consolidation/design.md`` §1.4.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parent.parent
AD = ROOT / "src" / "agentic_dynamics"


def test_retrieval_never_writes_the_kb():
    """The retrieval seam references the KB write path zero times — it is a pure reader."""
    src = (AD / "knowledge" / "retrieval.py").read_text(encoding="utf-8")
    assert "publish_event" not in src, "retrieval.py references publish_event"


def test_retrieval_never_supplies_policy_candidates():
    """The fusion gate returns ``None`` (exclude) for POLICY-authority candidates.

    POLICY is deliberately absent from ``AUTHORITY_MULTIPLIER`` and its freshness gate
    returns ``None``, so a POLICY record can never survive fusion into the evidence the
    executor sees — canonical facts never come from arbitrary retrieved text (rec 8).
    """
    from agentic_dynamics.knowledge.knowledge import Authority
    from agentic_dynamics.knowledge.retrieval import AUTHORITY_MULTIPLIER, freshness_multiplier

    assert Authority.POLICY not in AUTHORITY_MULTIPLIER
    assert (
        freshness_multiplier(
            authority=Authority.POLICY,
            commit_sha="abc",
            observed_at=None,
            current_commit="abc",
        )
        is None
    )


def test_knowledge_never_actuates():
    """No knowledge module imports or calls ``derive_actuation_record`` (knowledge does not
    actuate). Docstring mentions are allowed; actual imports/calls are not."""
    for path in sorted((AD / "knowledge").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "agentic_dynamics.control.actuation_ingestion"
            ):
                names = {a.name for a in node.names}
                assert "derive_actuation_record" not in names, (
                    f"{path}: imports actuation_ingestion.derive_actuation_record"
                )
            if isinstance(node, ast.Attribute) and node.attr == "derive_actuation_record":
                # A bare attribute reference is a call site (e.g. actuation_ingestion.derive_actuation_record(...)).
                raise AssertionError(f"{path}: references derive_actuation_record")


def test_canonical_corpus_names_unavailable_input_and_preserves_provenance(tmp_path, monkeypatch):
    """The reporting door distinguishes unavailable input from a measured empty slice.

    A missing manifest and an unreadable registered payload are named ``unavailable``;
    neither is allowed to look like an empty successful measurement.  A readable payload
    still carries the registry identity and row-level provenance that tie analysis to the
    canonical corpus, rather than to an arbitrary result-file glob.
    """
    from agentic_dynamics.reporting import canonical_corpus as cc

    missing = cc.load_canonical_tables("story", manifest_path=tmp_path / "missing.json")
    assert missing.input_state == "unavailable"
    assert missing.is_empty

    empty_manifest = tmp_path / "empty.json"
    empty_manifest.write_text('{"schema_version": "test/1", "registry": []}', encoding="utf-8")
    empty = cc.load_canonical_tables("story", manifest_path=empty_manifest)
    assert empty.input_state == "empty"
    assert empty.is_empty

    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()
    bad_payload = stories_dir / "story_bad.json"
    bad_payload.write_text("not json", encoding="utf-8")
    unreadable_manifest = tmp_path / "unreadable.json"
    unreadable_manifest.write_text(
        '{"schema_version": "test/1", "registry": [{"entity_id": "e1", '
        '"knowledge_id": "k1", "source_type": "story", "logical_locator": "bad", '
        '"source_uri": "story:bad", "lifecycle_state": "current"}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(cc, "STORIES_DIR", stories_dir)
    unreadable = cc.load_canonical_tables("story", manifest_path=unreadable_manifest)
    assert unreadable.input_state == "unavailable"
    assert unreadable.resolution.unreadable == 1
    assert unreadable.stories == []

    good_payload = stories_dir / "story_good.json"
    good_payload.write_text('{"story_id": "good", "summary": {}}', encoding="utf-8")
    good_manifest = tmp_path / "good.json"
    good_manifest.write_text(
        '{"schema_version": "test/1", "registry": [{"entity_id": "e2", '
        '"knowledge_id": "k2", "source_type": "story", "logical_locator": "good", '
        '"source_uri": "story:good", "lifecycle_state": "current"}]}',
        encoding="utf-8",
    )
    good = cc.load_canonical_tables("story", manifest_path=good_manifest)
    assert good.input_state == "available"
    assert good.identity.registry_identity_sha256
    assert good.stories[0]["_registry"]["knowledge_id"] == "k2"
