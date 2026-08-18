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
    path = tmp_path / "registry_index.jsonl"
    row = _row(supersedes="kid_prev", causes="kid_obs")
    _write_jsonl(path, [row])
    compacted = gm._compact_registry_index(path)
    assert compacted[0] == row


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
