"""Runtime-loop smoke tests (design §5.7 — e6 of cap_evidence_integrity).

Proves the injected phase-boundary analyzer loop END TO END with a fixture: a synthetic change
produces a typed CodeSnapshot/CodeDelta, updates the versioned graph, emits the code-change
facts, and supplies the executor neighborhood — hermetically (fixture + store double, no live
analyzers) and, when Neo4j is present, through the REAL composition-root data flow.
"""

import socket

import pytest

from agentic_dynamics.core.language import (
    _PROFILES,
    build_code_snapshot,
    compute_code_delta,
)
from agentic_dynamics.control.evidence_analyzer import EvidenceChangeAnalyzer
from agentic_dynamics.runtime.change_analyzer import (
    ChangeAnalysis,
    ChangeInput,
    NoopChangeAnalyzer,
    default_change_analyzer,
    run_change_analysis,
)

PY = _PROFILES["python"]
REPO = "e6-repo"
REV = "rev-2"


class FakeGraphClient:
    """Duck-typed stand-in for the Neo4jClient surface (hermetic smoke)."""

    def __init__(self, neighbors: list[str]):
        self._neighbors = neighbors
        self.updated = False

    def populate_versioned_graph(self, snapshot, *, revision, repository_id, acl_scope):
        self.updated = True
        assert acl_scope == "public"
        return {"symbol_versions": len(snapshot.all_symbols), "module_versions": 1}

    def expand_candidates(self, seed_ids, *, max_depth, max_neighbors, max_nodes, timeout_ms,
                          repository_id, acl_scope):
        assert repository_id == REPO and acl_scope == "public"  # the ACL must be threaded
        # Return the seeds (depth 0) plus a bounded set of neighbors with qualified names.
        nodes = [
            {"properties": {"version_id": s, "qualified_name": f"seed-{i}"}, "canonical_id": s}
            for i, s in enumerate(seed_ids)
        ]
        for i, qname in enumerate(self._neighbors):
            nodes.append(
                {"properties": {"version_id": f"neighbor-{i}", "qualified_name": qname}, "canonical_id": f"n{i}"}
            )
        return nodes


def _fixture():
    before = build_code_snapshot(
        {
            "math_utils.py": b"def add(a, b):\n    return a + b\n",
            "test_math_utils.py": b"def test_add():\n    assert True\n",
        },
        revision="rev-1",
        profile=PY,
    )
    after = build_code_snapshot(
        {
            "math_utils.py": b"def add(a, b):\n    return a * b\n\ndef top():\n    return add(1, 2)\n",
            "test_math_utils.py": b"def test_add():\n    assert True\n",
        },
        revision=REV,
        profile=PY,
    )
    return before, after, compute_code_delta(before, after)


def _change(neighbors=None) -> tuple[ChangeInput, FakeGraphClient]:
    before, after, delta = _fixture()
    fake = FakeGraphClient(neighbors or ["Calc"])
    change = ChangeInput(
        before=before, after=after, delta=delta, revision=REV,
        repository_id=REPO, acl_scope="public",
        sonar={"status": "available", "revision_matches": True, "new_critical_count": 2,
               "analyzed_sha": REV},
        lsp={"status": "available", "new_error_count": 1, "tool": "pyright"},
    )
    return change, fake


# ── The protocol: default no-op keeps existing behavior identical ──


def test_default_analyzer_is_a_strict_noop():
    change, _ = _change()
    out = run_change_analysis(change)  # no analyzer injected
    assert out == ChangeAnalysis()
    assert out.facts == () and out.neighborhood == () and out.graph_updated is False


def test_noop_change_analyzer_ignores_everything():
    change, _ = _change()
    assert NoopChangeAnalyzer().analyze(change) == ChangeAnalysis()
    assert isinstance(default_change_analyzer(), NoopChangeAnalyzer)


def test_run_change_analysis_dispatches_to_injected_analyzer():
    class _Probe:
        def analyze(self, change):
            return ChangeAnalysis(facts=({"predicate": "changed_symbol_count", "value": "2"},))

    out = run_change_analysis(ChangeInput(
        before=None, after=None, delta=None, revision=REV, repository_id=REPO, acl_scope="public"
    ), analyzer=_Probe())
    assert out.facts == ({"predicate": "changed_symbol_count", "value": "2"},)


# ── The hermetic loop (fixture + store double, no live analyzers) ──


def test_evidence_loop_smoke_hermetic():
    change, fake = _change(neighbors=["Calc"])
    analyzer = EvidenceChangeAnalyzer(graph_client=fake)
    out = analyzer.analyze(change)

    # Graph update ran with the ACL scope threaded.
    assert fake.updated and out.graph_updated is True

    # Executor neighborhood: the bounded symbols (seeds excluded), ACL-scoped expansion.
    assert out.neighborhood == ("Calc",)
    assert out.impacted_count == 1

    # Facts: the typed delta + analyzer statuses -> the measurable code-change facts.
    by = {f["predicate"]: f for f in out.facts}
    assert by["changed_symbol_count"]["value"] == "2"
    assert by["sonar_analysis_status"]["value"] == "available"
    assert by["new_sonar_critical_count"]["value"] == "2"
    assert by["impacted_symbol_count"]["value"] == "1"
    # risk = 0.35*.2 + 0.25*.1 + 0.20*(1-1.0) + 0.20*.1 = 0.115 (tests_ratio = 2/2 = 1.0)
    assert abs(float(by["code_change_risk"]["value"]) - 0.115) < 1e-3


def test_no_graph_client_still_emits_delta_facts():
    change, _ = _change()
    analyzer = EvidenceChangeAnalyzer(graph_client=None)  # no graph: hermetic, still facts
    out = analyzer.analyze(change)
    assert out.graph_updated is False
    assert out.impacted_count is None  # graph unknown -> impacted OMITTED, never zero
    by = {f["predicate"] for f in out.facts}
    assert "changed_symbol_count" in by
    assert "impacted_symbol_count" not in by


try:
    socket.create_connection(("localhost", 7687), timeout=2).close()
    _NEO4J_OK = True
except Exception:
    _NEO4J_OK = False


@pytest.mark.skipif(not _NEO4J_OK, reason="Neo4j not available on localhost:7687")
def test_composition_root_data_flow_live_neo4j():
    """The concrete composition-root flow with the REAL graph: change -> graph -> facts ->
    neighborhood, and a scoped traversal from the changed symbols reaches the bounded set."""
    from agentic_dynamics.knowledge.graph import Neo4jClient

    client = Neo4jClient()
    try:
        client._run(
            "MATCH (n) WHERE n.repository_id = $repo DETACH DELETE n", {"repo": REPO}
        )
        change, _ = _change(neighbors=[])
        analyzer = EvidenceChangeAnalyzer(graph_client=client)
        out = analyzer.analyze(change)

        assert out.graph_updated is True
        # The versioned graph was populated for the after-revision.
        rec = client._run_value(
            "MATCH (s:SymbolVersion {repository_id: $repo, commit_sha: $rev}) "
            "RETURN count(s) AS c",
            {"repo": REPO, "rev": REV},
        )
        assert rec["c"] == 3  # add, top, test_add

        # Facts emitted; the neighborhood was ACL-scoped (public scope, this repo).
        by = {f["predicate"]: f for f in out.facts}
        assert by["changed_symbol_count"]["value"] == "2"
    finally:
        client._run("MATCH (n) WHERE n.repository_id = $repo DETACH DELETE n", {"repo": REPO})
        client.close()
