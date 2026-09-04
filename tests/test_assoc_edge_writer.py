"""Tests for the associative first-family writer's producer-side wiring (graph_leg c2).

Covers the best-effort seam in ``scripts/kb_backfill_findings.py``:
``write_wave_finding_edge`` (the per-record producer-side edge write) and its call inside
``emit_record``. The graph write itself (``Neo4jClient.merge_wave_finding_produced_by``) is
tested live in ``tests/test_graph.py::TestAssocEdgeWriter``; here the client is faked so a
graph outage, a success, and the family gate are all deterministic with NO live Neo4j.
"""

import types

from scripts import kb_backfill_findings as kbf


def _record(source_type="finding", logical_locator="wave:c2spec"):
    """A record stand-in with the fields the producer seam reads."""
    return types.SimpleNamespace(
        knowledge_id="kid-c2-assoc",
        source_type=source_type,
        logical_locator=logical_locator,
    )


class _BoomClient:
    """A graph client whose write raises — models a graph outage at emit time."""

    def __init__(self):
        self.closed = False

    def merge_wave_finding_produced_by(self, record):
        raise ConnectionError("neo4j unreachable")

    def close(self):
        self.closed = True


class _OkClient:
    """A graph client whose write succeeds."""

    def __init__(self):
        self.closed = False
        self.seen = []

    def merge_wave_finding_produced_by(self, record):
        self.seen.append(record.knowledge_id)
        return "edge_merged"

    def close(self):
        self.closed = True


def _patch_client(monkeypatch, client):
    monkeypatch.setattr("agentic_dynamics.knowledge.graph.Neo4jClient", lambda *a, **k: client)


def test_graph_outage_degrades_to_skipped_logged_not_silent(monkeypatch, capsys):
    """A graph outage must not raise out of the producer — the emit succeeds, logged."""
    client = _BoomClient()
    _patch_client(monkeypatch, client)

    status = kbf.write_wave_finding_edge(_record())

    assert status == "skipped"
    assert client.closed is True  # the client is always closed, even on failure
    out = capsys.readouterr().out
    assert "assoc edge skipped" in out  # logged, never silent


def test_success_path_reports_merged(monkeypatch, capsys):
    client = _OkClient()
    _patch_client(monkeypatch, client)

    status = kbf.write_wave_finding_edge(_record())

    assert status == "edge_merged"
    assert client.seen == ["kid-c2-assoc"]
    assert client.closed is True
    out = capsys.readouterr().out
    assert "PRODUCED_BY" in out and "edge_merged" in out


def test_non_wave_record_never_touches_the_graph(monkeypatch, capsys):
    """The family gate: only wave-conclusion findings reach the writer; anything else is a
    no-op that never constructs a graph client (a non-wave record must not open a driver)."""
    client = _BoomClient()
    _patch_client(monkeypatch, client)

    status = kbf.write_wave_finding_edge(_record(logical_locator="exp_some_worktree"))

    assert status == "not_family"
    assert client.closed is False  # never opened, never used


def test_emit_record_succeeds_when_the_graph_is_down(tmp_path, monkeypatch, capsys):
    """DONE_WHEN (c): a graph outage degrades to the record emit succeeding WITHOUT edges.

    The REAL seam: ``emit_record`` calls ``write_wave_finding_edge``, whose internal
    try/except converts a graph failure into a logged ``"skipped"`` — so the durable artifact +
    registry row still land and ``emit_record`` reports ``"new"``. Hermetic: no live Redis (the
    event publish is also best-effort) and a fake Neo4j client that raises.
    """
    import json

    from agentic_dynamics.knowledge.knowledge import Authority, KnowledgeRecord

    def _connect_boom(*a, **k):
        raise RuntimeError("redis down")

    monkeypatch.setattr(kbf.ks, "connect", _connect_boom)
    _patch_client(monkeypatch, _BoomClient())

    root = tmp_path
    record = KnowledgeRecord(
        knowledge_id="kid-c2-emit",
        entity_id="ent-c2-emit",
        source_uri="file://docs/reviews/x_adversarial.md",
        source_type="finding",
        logical_locator="wave:c2emit",
        repository_id="wave:c2emit",
        branch="",
        worktree_id="",
        commit_sha="abc123",
        content_hash="h",
        extractor_version="wave-backfill/v1",
        embedding_version="",
        authority=Authority.DERIVED,
        valid_from="",
        valid_to=None,
        observed_at="",
        indexed_at="",
        acl_scope="wave:c2emit",
        contains_sensitive_data=False,
        text="wave c2emit -> verdict clean",
        token_count=0,
        language="",
        symbols=[],
        outcome_id="c2emit",
        test_executed_success=None,
        evidence_class="[C]",
    )

    outcome = kbf.emit_record(record, root=root)

    assert outcome == "new"  # the emit succeeded despite the graph + redis failures
    artifact = root / "experiments" / "results" / "kb" / "kid-c2-emit.json"
    assert artifact.exists()
    rows = (root / "experiments" / "results" / "registry_index.jsonl").read_text().splitlines()
    assert any(json.loads(line)["knowledge_id"] == "kid-c2-emit" for line in rows)
    out = capsys.readouterr().out
    assert "assoc edge skipped" in out  # the graph failure was logged, not silent
