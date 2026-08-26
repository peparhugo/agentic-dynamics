"""Tests for scripts/registry.py — the read-only CLI surface over the canonical-state
registry (docs/canonical_state_r2_plan.md step 16).

One test per subcommand against a fixture manifest (never the real
experiments/data_manifest.json — every test monkeypatches ``registry.DATA_MANIFEST_PATH``
or calls ``registry.load_registry(fixture_path)``/passes rows directly), plus
``test_show_actuation_follows_causes_to_observation`` (the one behavior specific to round
2's Delta 3).
"""

from __future__ import annotations

import json

from scripts import registry


def _row(**overrides) -> dict:
    base = {
        "knowledge_id": "kid_0001",
        "entity_id": "eid_0001",
        "source_type": "story",
        "logical_locator": "story_abc123",
        "source_uri": "story:story_abc123",
        "lifecycle_state": "current",
        "observed_at": "2026-08-15T00:00:00+00:00",
        "indexed_at": "2026-08-15T00:00:01+00:00",
        "supersedes": None,
        "causes": None,
    }
    base.update(overrides)
    return base


def _write_manifest(path, registry_rows):
    path.write_text(json.dumps({"schema_version": "1.0", "registry": registry_rows}))


# ── load_registry ─────────────────────────────────────────────────


def test_load_registry_returns_empty_list_when_manifest_missing(tmp_path):
    assert registry.load_registry(tmp_path / "does_not_exist.json") == []


def test_load_registry_returns_empty_list_on_corrupt_json(tmp_path):
    path = tmp_path / "data_manifest.json"
    path.write_text("{not valid json")
    assert registry.load_registry(path) == []


def test_load_registry_reads_the_registry_array(tmp_path):
    path = tmp_path / "data_manifest.json"
    _write_manifest(path, [_row()])
    rows = registry.load_registry(path)
    assert len(rows) == 1
    assert rows[0]["knowledge_id"] == "kid_0001"


# ── show ─────────────────────────────────────────────────────────


def test_resolve_show_matches_by_logical_locator_first():
    rows = [
        _row(knowledge_id="kid_a", entity_id="eid_a", logical_locator="story_a"),
        _row(knowledge_id="kid_b", entity_id="story_a", logical_locator="not_it"),  # entity_id collision bait
    ]
    stage, candidates = registry.resolve_show(rows, "story_a")
    assert stage == "logical_locator"
    assert [c["knowledge_id"] for c in candidates] == ["kid_a"]


def test_resolve_show_falls_back_to_entity_id():
    rows = [_row(knowledge_id="kid_a", entity_id="eid_a", logical_locator="story_a")]
    stage, candidates = registry.resolve_show(rows, "eid_a")
    assert stage == "entity_id"
    assert candidates[0]["knowledge_id"] == "kid_a"


def test_resolve_show_falls_back_to_knowledge_id_prefix():
    rows = [_row(knowledge_id="kid_abcdef123456", entity_id="eid_a", logical_locator="story_a")]
    stage, candidates = registry.resolve_show(rows, "kid_abcdef")
    assert stage == "knowledge_id_prefix"
    assert candidates[0]["knowledge_id"] == "kid_abcdef123456"


def test_resolve_show_reports_no_match():
    rows = [_row()]
    stage, candidates = registry.resolve_show(rows, "nothing_matches_this")
    assert stage == "none"
    assert candidates == []


def test_resolve_show_reports_ambiguous_candidates():
    rows = [
        _row(knowledge_id="kid_a", logical_locator="shared_id"),
        _row(knowledge_id="kid_b", logical_locator="shared_id"),
    ]
    stage, candidates = registry.resolve_show(rows, "shared_id")
    assert stage == "logical_locator"
    assert len(candidates) == 2


def test_cmd_show_prints_ambiguous_candidates(capsys):
    rows = [
        _row(knowledge_id="kid_a", logical_locator="shared_id"),
        _row(knowledge_id="kid_b", logical_locator="shared_id"),
    ]
    exit_code = registry.cmd_show(_ns(id="shared_id"), rows)
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "ambiguous" in out
    assert "kid_a" in out and "kid_b" in out


def test_cmd_show_reports_not_found(capsys):
    exit_code = registry.cmd_show(_ns(id="nope"), [_row()])
    assert exit_code == 1
    assert "no registry entry matches" in capsys.readouterr().out


def test_cmd_show_prints_the_matched_row(capsys):
    rows = [_row(knowledge_id="kid_a", logical_locator="story_a")]
    exit_code = registry.cmd_show(_ns(id="story_a"), rows)
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "matched via logical_locator" in out
    assert "kid_a" in out


def test_show_actuation_follows_causes_to_observation(capsys):
    # design §10 / §5a: the one behavior specific to round 2 — an actuation record's
    # `show` output additionally resolves and prints its justifying observation.
    observation = _row(
        knowledge_id="kid_observation_1", entity_id="eid_observation_1",
        source_type="observation", logical_locator="assessment_xyz",
    )
    actuation = _row(
        knowledge_id="kid_actuation_1", entity_id="eid_actuation_1",
        source_type="actuation", logical_locator="actuation_xyz",
        causes="kid_observation_1",
    )
    rows = [observation, actuation]

    exit_code = registry.cmd_show(_ns(id="actuation_xyz"), rows)
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "matched via logical_locator" in out
    assert "causes (the justifying observation):" in out
    assert "kid_observation_1" in out


def test_show_actuation_with_unresolvable_causes_reports_it(capsys):
    actuation = _row(
        knowledge_id="kid_actuation_2", logical_locator="actuation_orphan",
        source_type="actuation", causes="kid_never_registered",
    )
    exit_code = registry.cmd_show(_ns(id="actuation_orphan"), [actuation])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "not found in the registry (unresolved citation)" in out


# ── query ────────────────────────────────────────────────────────


def test_cmd_query_filters_by_record_type(capsys):
    rows = [
        _row(knowledge_id="kid_a", source_type="story"),
        _row(knowledge_id="kid_b", source_type="review"),
    ]
    registry.cmd_query(_ns(record_type="story", lifecycle=None, since=None), rows)
    out = capsys.readouterr().out
    assert "kid_a" in out
    assert "kid_b" not in out
    assert "1 record(s)" in out


def test_cmd_query_filters_by_lifecycle(capsys):
    rows = [
        _row(knowledge_id="kid_a", lifecycle_state="current"),
        _row(knowledge_id="kid_b", lifecycle_state="tombstoned"),
    ]
    registry.cmd_query(_ns(record_type=None, lifecycle="tombstoned", since=None), rows)
    out = capsys.readouterr().out
    assert "kid_b" in out
    assert "kid_a" not in out


def test_cmd_query_filters_by_since(capsys):
    rows = [
        _row(knowledge_id="kid_old", observed_at="2026-01-01T00:00:00+00:00"),
        _row(knowledge_id="kid_new", observed_at="2026-08-15T00:00:00+00:00"),
    ]
    registry.cmd_query(_ns(record_type=None, lifecycle=None, since="2026-06-01"), rows)
    out = capsys.readouterr().out
    assert "kid_new" in out
    assert "kid_old" not in out


def test_cmd_query_with_no_filters_lists_everything(capsys):
    rows = [_row(knowledge_id="kid_a"), _row(knowledge_id="kid_b", entity_id="eid_2")]
    registry.cmd_query(_ns(record_type=None, lifecycle=None, since=None), rows)
    out = capsys.readouterr().out
    assert "2 record(s)" in out


def test_cmd_query_combines_filters():
    rows = [
        _row(knowledge_id="kid_a", source_type="story", lifecycle_state="current"),
        _row(knowledge_id="kid_b", source_type="story", lifecycle_state="tombstoned"),
        _row(knowledge_id="kid_c", source_type="review", lifecycle_state="current"),
    ]
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        registry.cmd_query(_ns(record_type="story", lifecycle="current", since=None), rows)
    out = buf.getvalue()
    assert "kid_a" in out
    assert "kid_b" not in out
    assert "kid_c" not in out


# ── lineage ──────────────────────────────────────────────────────


def test_cmd_lineage_reports_missing_entity(capsys):
    exit_code = registry.cmd_lineage(_ns(entity_id="nope", live=False), [_row()])
    assert exit_code == 1
    assert "no registry entry for entity_id" in capsys.readouterr().out


def test_cmd_lineage_without_live_prints_one_hop_view(capsys):
    rows = [_row(entity_id="eid_target", supersedes="kid_prev", causes=None)]
    exit_code = registry.cmd_lineage(_ns(entity_id="eid_target", live=False), rows)
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "one-hop view only" in out
    assert "kid_prev" in out


class _FakeNeo4jResultRow(dict):
    """A dict already satisfies ``dict(row)`` in resolve_lineage_live — this alias just
    documents the shape expected from a Neo4j record: knowledge_id/entity_id/source_type/
    supersedes/causes columns, one row per node in the SUPERSEDES chain."""


class _FakeNeo4jClient:
    """Store-double for instrument.graph.Neo4jClient — records the query it was asked
    and returns a canned SUPERSEDES chain, mirroring tests/test_kb_worker.py's pattern."""

    def __init__(self, chain):
        self._chain = chain
        self.closed = False
        self.calls = []

    def _run(self, query, params=None):
        self.calls.append((query, params or {}))
        return [_FakeNeo4jResultRow(row) for row in self._chain]

    def close(self):
        self.closed = True


def test_resolve_lineage_live_walks_the_supersedes_chain():
    chain = [
        {"knowledge_id": "kid_v2", "entity_id": "eid_x", "source_type": "story", "supersedes": "kid_v1", "causes": None},
        {"knowledge_id": "kid_v1", "entity_id": "eid_x", "source_type": "story", "supersedes": None, "causes": None},
    ]
    client = _FakeNeo4jClient(chain)
    result = registry.resolve_lineage_live(client, "eid_x")
    assert [r["knowledge_id"] for r in result] == ["kid_v2", "kid_v1"]
    query, params = client.calls[0]
    assert params == {"eid": "eid_x"}
    assert "SUPERSEDES" in query


def test_cmd_lineage_with_live_queries_neo4j_and_closes(monkeypatch, capsys):
    chain = [
        {"knowledge_id": "kid_v2", "entity_id": "eid_x", "source_type": "story", "supersedes": "kid_v1", "causes": None},
    ]
    fake_client = _FakeNeo4jClient(chain)

    import agentic_dynamics.knowledge.graph as graph_module

    monkeypatch.setattr(graph_module, "Neo4jClient", lambda: fake_client)

    rows = [_row(entity_id="eid_x")]
    exit_code = registry.cmd_lineage(_ns(entity_id="eid_x", live=True), rows)
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "SUPERSEDES chain for entity_id eid_x" in out
    assert "kid_v2" in out
    assert fake_client.closed is True


# ── CLI wiring (argparse -> cmd_*) ────────────────────────────────


def test_main_show_reads_from_the_manifest_path(tmp_path, monkeypatch, capsys):
    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [_row(knowledge_id="kid_x", logical_locator="story_x")])
    monkeypatch.setattr(registry, "DATA_MANIFEST_PATH", manifest_path)

    exit_code = registry.main(["show", "story_x"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "kid_x" in out


def test_main_query_reads_from_the_manifest_path(tmp_path, monkeypatch, capsys):
    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [_row(source_type="flag")])
    monkeypatch.setattr(registry, "DATA_MANIFEST_PATH", manifest_path)

    exit_code = registry.main(["query", "--record-type", "flag"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "1 record(s)" in out


def test_main_lineage_reads_from_the_manifest_path(tmp_path, monkeypatch, capsys):
    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [_row(entity_id="eid_y")])
    monkeypatch.setattr(registry, "DATA_MANIFEST_PATH", manifest_path)

    exit_code = registry.main(["lineage", "eid_y"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "one-hop view only" in out


def test_main_with_no_manifest_degrades_to_empty(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(registry, "DATA_MANIFEST_PATH", tmp_path / "does_not_exist.json")
    exit_code = registry.main(["show", "anything"])
    assert exit_code == 1
    assert "no registry entry matches" in capsys.readouterr().out


# ── argparse.Namespace helper ─────────────────────────────────────


def _ns(**kwargs):
    """A minimal stand-in for argparse.Namespace — cmd_show/cmd_query/cmd_lineage only
    ever read specific attributes off ``args``, never call argparse-specific methods."""
    import argparse

    return argparse.Namespace(**kwargs)
