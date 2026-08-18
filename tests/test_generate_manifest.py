"""Tests for scripts/generate_manifest.py — canonical-state round 2, plan step 15's
registry-array compaction (``_compact_registry_index``), plus a backward-compatibility
check that ``manifest["files"]`` stays byte-for-byte the same shape it always was
(design §11).

New file — no test previously covered ``generate_manifest.py`` at all (confirmed by
search at implementation time).
"""

from __future__ import annotations

import json

from scripts import generate_manifest as gm


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _row(**overrides) -> dict:
    base = {
        "knowledge_id": "kid_0001",
        "entity_id": "eid_0001",
        "source_type": "story",
        "logical_locator": "story_abc",
        "source_uri": "story:story_abc",
        "lifecycle_state": "current",
        "observed_at": "2026-08-15T00:00:00+00:00",
        "indexed_at": "2026-08-15T00:00:01+00:00",
        "supersedes": None,
        "causes": None,
    }
    base.update(overrides)
    return base


# ── _compact_registry_index ───────────────────────────────────────


def test_compact_registry_index_missing_file_returns_empty_list(tmp_path):
    assert gm._compact_registry_index(tmp_path / "does_not_exist.jsonl") == []


def test_compact_registry_index_keeps_newest_row_per_entity_id(tmp_path):
    path = tmp_path / "registry_index.jsonl"
    _write_jsonl(path, [
        _row(knowledge_id="kid_v1", entity_id="eid_1", indexed_at="2026-08-15T00:00:01+00:00"),
        _row(knowledge_id="kid_v2", entity_id="eid_1", indexed_at="2026-08-15T00:10:00+00:00"),
        _row(knowledge_id="kid_v1_old", entity_id="eid_1", indexed_at="2026-08-14T00:00:00+00:00"),
    ])
    compacted = gm._compact_registry_index(path)
    assert len(compacted) == 1
    assert compacted[0]["knowledge_id"] == "kid_v2"  # the newest indexed_at wins


def test_compact_registry_index_returns_one_row_per_distinct_entity(tmp_path):
    path = tmp_path / "registry_index.jsonl"
    _write_jsonl(path, [
        _row(knowledge_id="kid_a", entity_id="eid_a"),
        _row(knowledge_id="kid_b", entity_id="eid_b"),
        _row(knowledge_id="kid_c", entity_id="eid_c"),
    ])
    compacted = gm._compact_registry_index(path)
    assert {r["entity_id"] for r in compacted} == {"eid_a", "eid_b", "eid_c"}


def test_compact_registry_index_output_is_sorted_by_entity_id(tmp_path):
    path = tmp_path / "registry_index.jsonl"
    _write_jsonl(path, [
        _row(knowledge_id="kid_z", entity_id="eid_z"),
        _row(knowledge_id="kid_a", entity_id="eid_a"),
        _row(knowledge_id="kid_m", entity_id="eid_m"),
    ])
    compacted = gm._compact_registry_index(path)
    assert [r["entity_id"] for r in compacted] == ["eid_a", "eid_m", "eid_z"]


def test_compact_registry_index_skips_malformed_lines(tmp_path):
    path = tmp_path / "registry_index.jsonl"
    path.write_text(
        json.dumps(_row(knowledge_id="kid_good", entity_id="eid_good")) + "\n"
        "{not valid json\n"
        "\n"  # a blank line, also tolerated
        + json.dumps({"entity_id": "", "knowledge_id": "kid_no_entity"}) + "\n"  # no entity_id
    )
    compacted = gm._compact_registry_index(path)
    assert len(compacted) == 1
    assert compacted[0]["knowledge_id"] == "kid_good"


def test_compact_registry_index_preserves_all_row_fields(tmp_path):
    # A lone, unsuperseded row: every field it carries survives compaction unchanged,
    # plus the two newly-DERIVED fields this row's own history doesn't affect —
    # valid_to stays None (still open/current — nothing supersedes it) and versions
    # is a single-entry history of itself (see the multi-version tests below for a
    # chain where versions actually has more than one entry).
    path = tmp_path / "registry_index.jsonl"
    row = _row(supersedes="kid_prev", causes="kid_obs")
    _write_jsonl(path, [row])
    compacted = gm._compact_registry_index(path)
    assert compacted[0] == {**row, "reason": None, "valid_to": None, "versions": [{
        "knowledge_id": row["knowledge_id"],
        "lifecycle_state": "current",
        "valid_to": None,
        "observed_at": row["observed_at"],
        "indexed_at": row["indexed_at"],
        "reason": None,
    }]}


# ── derived lifecycle_state / valid_to (canonical-state finalize, G2) ────
#
# These fixtures exercise multi-version entity histories the way
# scripts/kb_worker.py's kb-registry-v1 handler (G1) actually writes them: a plain
# tombstone (one row, lifecycle_state already "tombstoned"), a two-version supersede
# chain (the successor's own "current" line PLUS its "predecessor superseded" marker
# line — same entity_id, same indexed_at, distinct knowledge_id), and a three-version
# chain to prove the derivation generalizes past a single hop.


def test_compact_registry_index_delete_marker_renders_entity_tombstoned(tmp_path):
    path = tmp_path / "registry_index.jsonl"
    _write_jsonl(path, [
        _row(knowledge_id="kid_bad", entity_id="eid_1", lifecycle_state="tombstoned"),
    ])
    compacted = gm._compact_registry_index(path)
    assert len(compacted) == 1
    assert compacted[0]["lifecycle_state"] == "tombstoned"
    # No dedicated valid_to was ever recorded on the row itself, so the derivation
    # falls back to the tombstone's own indexed_at as the closest proxy this flat
    # index has to "event time" (design §6).
    assert compacted[0]["valid_to"] == compacted[0]["indexed_at"]


def test_compact_registry_index_tombstone_wins_over_an_older_current_row(tmp_path):
    # An entity that was "current" and is LATER tombstoned must render tombstoned —
    # the tombstone is the entity's most recent fact, even though an earlier row for
    # the same entity_id still says "current".
    path = tmp_path / "registry_index.jsonl"
    _write_jsonl(path, [
        _row(knowledge_id="kid_v1", entity_id="eid_1", indexed_at="2026-08-15T00:00:00+00:00",
             lifecycle_state="current"),
        _row(knowledge_id="kid_v1_tombstone", entity_id="eid_1", indexed_at="2026-08-16T00:00:00+00:00",
             lifecycle_state="tombstoned"),
    ])
    compacted = gm._compact_registry_index(path)
    assert len(compacted) == 1
    assert compacted[0]["knowledge_id"] == "kid_v1_tombstone"
    assert compacted[0]["lifecycle_state"] == "tombstoned"


def test_compact_registry_index_supersede_marks_predecessor_superseded_with_effective_valid_to(tmp_path):
    # Mirrors exactly what kb-registry-v1's handler appends for one supersede event:
    # the successor's own full "current" line, plus a thin "predecessor superseded"
    # marker line for the OLD knowledge_id — same entity_id, same indexed_at.
    path = tmp_path / "registry_index.jsonl"
    _write_jsonl(path, [
        _row(knowledge_id="kid_v1", entity_id="eid_1", indexed_at="2026-08-15T00:00:00+00:00",
             observed_at="2026-08-15T00:00:00+00:00", lifecycle_state="current"),
        _row(knowledge_id="kid_v2", entity_id="eid_1", indexed_at="2026-08-16T00:00:00+00:00",
             observed_at="2026-08-16T00:00:00+00:00", lifecycle_state="current",
             supersedes="kid_v1"),
        {
            "knowledge_id": "kid_v1", "entity_id": "eid_1",
            "lifecycle_state": "superseded", "valid_to": "2026-08-16T00:00:00+00:00",
            "indexed_at": "2026-08-16T00:00:00+00:00",
        },
    ])
    compacted = gm._compact_registry_index(path)
    assert len(compacted) == 1  # still one row per entity_id

    entity_row = compacted[0]
    # The entity's HEAD is the successor — "current", not "superseded".
    assert entity_row["knowledge_id"] == "kid_v2"
    assert entity_row["lifecycle_state"] == "current"
    assert entity_row["valid_to"] is None
    assert entity_row["supersedes"] == "kid_v1"

    # The predecessor's derived state is exposed via the entity's version history —
    # this is the fact this compaction pass exists to compute: "a supersede renders
    # the predecessor superseded with effective valid_to = successor valid_from"
    # (here, the successor's own observed_at, the flat index's valid_from proxy).
    versions_by_kid = {v["knowledge_id"]: v for v in entity_row["versions"]}
    assert versions_by_kid["kid_v1"]["lifecycle_state"] == "superseded"
    assert versions_by_kid["kid_v1"]["valid_to"] == "2026-08-16T00:00:00+00:00"
    assert versions_by_kid["kid_v2"]["lifecycle_state"] == "current"
    assert versions_by_kid["kid_v2"]["valid_to"] is None


def test_compact_registry_index_derives_supersession_even_without_a_marker_line(tmp_path):
    # The derivation must not depend on kb-registry-v1's marker-line mechanism
    # existing — it is re-derivable from the `supersedes` chain alone (design §6: "the
    # index layers compute the effective valid_to ... purely as a derived view over
    # the supersedes chain"). Here only the successor's own line is present (its
    # `supersedes` pointer is enough); no separate marker line for kid_v1 was ever
    # appended, e.g. because it predates G1 shipping.
    path = tmp_path / "registry_index.jsonl"
    _write_jsonl(path, [
        _row(knowledge_id="kid_v1", entity_id="eid_1", indexed_at="2026-08-15T00:00:00+00:00",
             observed_at="2026-08-15T00:00:00+00:00", lifecycle_state="current"),
        _row(knowledge_id="kid_v2", entity_id="eid_1", indexed_at="2026-08-16T00:00:00+00:00",
             observed_at="2026-08-16T00:00:00+00:00", lifecycle_state="current",
             supersedes="kid_v1"),
    ])
    compacted = gm._compact_registry_index(path)
    entity_row = compacted[0]
    assert entity_row["knowledge_id"] == "kid_v2"
    versions_by_kid = {v["knowledge_id"]: v for v in entity_row["versions"]}
    assert versions_by_kid["kid_v1"]["lifecycle_state"] == "superseded"
    assert versions_by_kid["kid_v1"]["valid_to"] == "2026-08-16T00:00:00+00:00"  # kid_v2's observed_at


def test_compact_registry_index_three_version_chain(tmp_path):
    # v1 -> v2 -> v3: each predecessor's effective valid_to is its OWN direct
    # successor's valid_from, not the chain's final head's.
    path = tmp_path / "registry_index.jsonl"
    _write_jsonl(path, [
        _row(knowledge_id="kid_v1", entity_id="eid_1", indexed_at="2026-08-14T00:00:00+00:00",
             observed_at="2026-08-14T00:00:00+00:00", lifecycle_state="current"),
        _row(knowledge_id="kid_v2", entity_id="eid_1", indexed_at="2026-08-15T00:00:00+00:00",
             observed_at="2026-08-15T00:00:00+00:00", lifecycle_state="current",
             supersedes="kid_v1"),
        _row(knowledge_id="kid_v3", entity_id="eid_1", indexed_at="2026-08-16T00:00:00+00:00",
             observed_at="2026-08-16T00:00:00+00:00", lifecycle_state="current",
             supersedes="kid_v2"),
    ])
    compacted = gm._compact_registry_index(path)
    entity_row = compacted[0]
    assert entity_row["knowledge_id"] == "kid_v3"
    assert entity_row["lifecycle_state"] == "current"

    versions_by_kid = {v["knowledge_id"]: v for v in entity_row["versions"]}
    assert versions_by_kid["kid_v1"]["lifecycle_state"] == "superseded"
    assert versions_by_kid["kid_v1"]["valid_to"] == "2026-08-15T00:00:00+00:00"  # v2's observed_at
    assert versions_by_kid["kid_v2"]["lifecycle_state"] == "superseded"
    assert versions_by_kid["kid_v2"]["valid_to"] == "2026-08-16T00:00:00+00:00"  # v3's observed_at
    assert versions_by_kid["kid_v3"]["lifecycle_state"] == "current"
    assert versions_by_kid["kid_v3"]["valid_to"] is None


def test_compact_registry_index_supersede_then_tombstone(tmp_path):
    # A chain where the CURRENT head is itself later tombstoned: the entity renders
    # tombstoned (not "current"), and the earlier, already-superseded predecessor
    # keeps its own derived state regardless.
    path = tmp_path / "registry_index.jsonl"
    _write_jsonl(path, [
        _row(knowledge_id="kid_v1", entity_id="eid_1", indexed_at="2026-08-14T00:00:00+00:00",
             observed_at="2026-08-14T00:00:00+00:00", lifecycle_state="current"),
        _row(knowledge_id="kid_v2", entity_id="eid_1", indexed_at="2026-08-15T00:00:00+00:00",
             observed_at="2026-08-15T00:00:00+00:00", lifecycle_state="current",
             supersedes="kid_v1"),
        _row(knowledge_id="kid_v2_tombstone", entity_id="eid_1", indexed_at="2026-08-16T00:00:00+00:00",
             lifecycle_state="tombstoned"),
    ])
    compacted = gm._compact_registry_index(path)
    entity_row = compacted[0]
    assert entity_row["knowledge_id"] == "kid_v2_tombstone"
    assert entity_row["lifecycle_state"] == "tombstoned"

    versions_by_kid = {v["knowledge_id"]: v for v in entity_row["versions"]}
    assert versions_by_kid["kid_v1"]["lifecycle_state"] == "superseded"


def test_compact_registry_index_independent_entities_do_not_interfere(tmp_path):
    # A supersede chain under one entity_id must not affect an unrelated entity_id's
    # own, independent version.
    path = tmp_path / "registry_index.jsonl"
    _write_jsonl(path, [
        _row(knowledge_id="kid_v1", entity_id="eid_1", lifecycle_state="current"),
        _row(knowledge_id="kid_v2", entity_id="eid_1", lifecycle_state="current", supersedes="kid_v1"),
        _row(knowledge_id="kid_other", entity_id="eid_2", lifecycle_state="current"),
    ])
    compacted = gm._compact_registry_index(path)
    by_entity = {r["entity_id"]: r for r in compacted}
    assert len(compacted) == 2
    assert by_entity["eid_2"]["knowledge_id"] == "kid_other"
    assert by_entity["eid_2"]["lifecycle_state"] == "current"
    assert len(by_entity["eid_2"]["versions"]) == 1


# ── main() integration: registry is additive, files{} stays unchanged ────


def test_main_adds_registry_without_disturbing_the_files_block(tmp_path, monkeypatch):
    # Redirect every path main() touches into an isolated tmp_path tree — this must
    # never write to the real repo's experiments/data_manifest.json.
    project_root = tmp_path
    results_dir = project_root / "experiments" / "results"
    results_dir.mkdir(parents=True)
    (project_root / "firebase" / "public").mkdir(parents=True)

    monkeypatch.setattr(gm, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(gm, "RESULTS_DIR", results_dir)
    monkeypatch.setattr(gm, "REGISTRY_INDEX_PATH", results_dir / "registry_index.jsonl")
    _write_jsonl(results_dir / "registry_index.jsonl", [_row(knowledge_id="kid_only")])

    # None of the four files_to_hash sources exist in this isolated tree — main() must
    # still complete and mark each as MISSING (unchanged pre-existing behavior).
    gm.main()

    manifest = json.loads((project_root / "experiments" / "data_manifest.json").read_text())

    # files{} shape is byte-for-byte unchanged: same 4 keys, MISSING (None) when absent.
    assert set(manifest["files"].keys()) == {
        "inventory.json", "_results_summary.json", "_trajectory_aggregate.json", "data.js",
    }
    assert all(v is None for v in manifest["files"].values())

    # registry{} is additive and reflects the compacted index.
    assert len(manifest["registry"]) == 1
    assert manifest["registry"][0]["knowledge_id"] == "kid_only"


def test_main_registry_is_empty_list_when_no_index_file_exists(tmp_path, monkeypatch):
    project_root = tmp_path
    results_dir = project_root / "experiments" / "results"
    results_dir.mkdir(parents=True)
    (project_root / "firebase" / "public").mkdir(parents=True)

    monkeypatch.setattr(gm, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(gm, "RESULTS_DIR", results_dir)
    monkeypatch.setattr(gm, "REGISTRY_INDEX_PATH", results_dir / "registry_index.jsonl")

    gm.main()

    manifest = json.loads((project_root / "experiments" / "data_manifest.json").read_text())
    assert manifest["registry"] == []


def test_compact_registry_index_merges_marker_line_without_losing_observed_at(tmp_path):
    # A supersede event appends (a) the successor's full "current" line, (b) a thin
    # "predecessor superseded" marker line that shares the predecessor's knowledge_id. The
    # marker must NOT clobber the predecessor's full registration line — its observed_at
    # must survive into the versions projection (merge, not replace).
    path = tmp_path / "registry_index.jsonl"
    _write_jsonl(path, [
        _row(knowledge_id="kid_v1", entity_id="eid_1",
             observed_at="2026-08-14T00:00:00+00:00", indexed_at="2026-08-14T00:00:01+00:00"),
        _row(knowledge_id="kid_v2", entity_id="eid_1",
             observed_at="2026-08-15T00:00:00+00:00", indexed_at="2026-08-15T00:00:01+00:00",
             supersedes="kid_v1"),
        {
            "knowledge_id": "kid_v1", "entity_id": "eid_1",
            "lifecycle_state": "superseded", "valid_to": "2026-08-15T00:00:00+00:00",
            "indexed_at": "2026-08-15T00:00:01+00:00",
        },
    ])
    compacted = gm._compact_registry_index(path)
    entity_row = compacted[0]
    versions_by_kid = {v["knowledge_id"]: v for v in entity_row["versions"]}

    # The marker's derived lifecycle_state/valid_to still win ...
    assert versions_by_kid["kid_v1"]["lifecycle_state"] == "superseded"
    assert versions_by_kid["kid_v1"]["valid_to"] == "2026-08-15T00:00:00+00:00"
    # ... but the predecessor's original observed_at survives the merge.
    assert versions_by_kid["kid_v1"]["observed_at"] == "2026-08-14T00:00:00+00:00"


def test_compact_registry_index_carries_reason_through(tmp_path):
    # A tombstoned record's `reason` (why it was retracted) must surface in both the head
    # row and the versions list, not be dropped at the registry_index.jsonl boundary.
    path = tmp_path / "registry_index.jsonl"
    _write_jsonl(path, [
        _row(knowledge_id="kid_t", entity_id="eid_1", lifecycle_state="tombstoned",
             reason="contaminated: ran as clean (P0-7)"),
    ])
    compacted = gm._compact_registry_index(path)
    entity_row = compacted[0]
    assert entity_row["reason"] == "contaminated: ran as clean (P0-7)"
    assert entity_row["versions"][0]["reason"] == "contaminated: ran as clean (P0-7)"
