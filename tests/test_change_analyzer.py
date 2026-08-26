"""Runtime-loop smoke tests (design §5.7 — e6 of cap_evidence_integrity).

Proves the injected phase-boundary analyzer loop END TO END with a fixture: a synthetic change
produces a typed CodeSnapshot/CodeDelta, updates the versioned graph, emits the code-change
facts, and supplies the executor neighborhood — hermetically (fixture + store double, no live
analyzers) and, when Neo4j is present, through the REAL composition-root data flow.
"""

import socket

import pytest

from agentic_dynamics.control.evidence_analyzer import EvidenceChangeAnalyzer
from agentic_dynamics.core.language import (
    _PROFILES,
    build_code_snapshot,
    compute_code_delta,
)
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
        self.revisions: list[str] = []

    def populate_versioned_graph(self, snapshot, *, revision, repository_id, acl_scope):
        self.updated = True
        self.revisions.append(revision)
        assert acl_scope == "public"
        return {"symbol_versions": len(snapshot.all_symbols), "module_versions": 1}

    def expand_candidates(self, seed_ids, *, max_depth, max_neighbors, max_nodes, timeout_ms,
                          repository_id, acl_scope, rels=None):
        assert repository_id == REPO and acl_scope == "public"  # the ACL must be threaded
        from agentic_dynamics.knowledge.graph import IMPACT_EXPANSION_RELS
        assert rels == IMPACT_EXPANSION_RELS  # version history is never an impact edge
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
    assert fake.revisions == ["rev-1", REV]  # removed-symbol seeds need the parent revision too
    assert out.graph_status == "available"
    assert out.revision == REV  # full-revision provenance on the analysis

    # Executor neighborhood: the change's OWN symbols (add changed, top added) UNION the
    # ACL-scoped expansion — the cap_2a_rerun2 scope-miss fix (a rework proposal's scope must
    # contain the changed symbols, or the fixed hit rule can never score a rework leg).
    assert out.neighborhood == ("Calc", "add", "top")
    assert out.impacted_count == 1  # impacted = the dependents only, not the seeds

    # Facts: the typed delta + analyzer statuses -> the measurable code-change facts.
    by = {f["predicate"]: f for f in out.facts}
    assert by["changed_symbol_count"]["value"] == "2"
    assert by["sonar_analysis_status"]["value"] == "available"
    assert by["new_sonar_critical_count"]["value"] == "2"
    assert by["impacted_symbol_count"]["value"] == "1"
    # risk = 0.35*.2 + 0.25*.1 + 0.20*(1-1.0) + 0.20*.1 = 0.115 (tests_ratio = 2/2 = 1.0)
    assert abs(float(by["code_change_risk"]["value"]) - 0.115) < 1e-3

    # The ledger-shaped dict carries the explicit graph status + revision (JSON-safe).
    d = out.to_dict()
    assert d["graph_status"] == "available" and d["revision"] == REV
    assert all(
        f"{REPO}:phase:{REV}" in evidence_id
        for fact in out.facts
        for evidence_id in fact["evidence_ids"]
    )


def test_no_graph_client_still_emits_delta_facts():
    change, _ = _change()
    analyzer = EvidenceChangeAnalyzer(graph_client=None)  # no graph: hermetic, still facts
    out = analyzer.analyze(change)
    assert out.graph_updated is False
    assert out.impacted_count is None  # graph unknown -> impacted OMITTED, never zero
    assert out.graph_status == "not_requested"  # explicit: the graph leg was never asked for
    by = {f["predicate"] for f in out.facts}
    assert "changed_symbol_count" in by
    assert "impacted_symbol_count" not in by


def test_graph_down_preserves_delta_facts_and_exposes_status():
    """cap_2a p1: a graph client whose populate_versioned_graph raises must NOT escape — the
    analysis degrades to delta-only facts with an explicit unavailable status, no fabricated
    zero impacted count, and the reducer errors untouched (they still propagate)."""
    class RaisingGraphClient:
        def populate_versioned_graph(self, snapshot, *, revision, repository_id, acl_scope):
            raise RuntimeError("neo4j connection refused")

        def expand_candidates(self, *args, **kwargs):
            raise AssertionError("must not be called after populate failed")

    change, _ = _change()
    out = EvidenceChangeAnalyzer(graph_client=RaisingGraphClient()).analyze(change)
    assert out.graph_status == "unavailable"
    assert out.graph_updated is False
    assert out.impacted_count is None  # unknown, never 0
    assert out.neighborhood == ()
    by = {f["predicate"] for f in out.facts}
    assert "changed_symbol_count" in by  # delta facts preserved
    assert "impacted_symbol_count" not in by  # graph term omitted


def test_requested_but_unavailable_graph_is_not_mislabeled():
    """A requested graph whose client could not be constructed remains visibly unavailable."""
    change, _ = _change()
    out = EvidenceChangeAnalyzer(graph_client=None, graph_requested=True).analyze(change)
    assert out.graph_status == "unavailable"
    assert out.impacted_count is None
    assert "impacted_symbol_count" not in {f["predicate"] for f in out.facts}
    assert out.to_dict()["graph_status"] == "unavailable"


def test_expand_failure_degrades_to_unavailable():
    """The impact leg failing after a successful populate also flags the cell — delta-only
    facts survive and the impacted count is omitted, never a fabricated zero."""
    class ExpandRaisingClient:
        def populate_versioned_graph(self, snapshot, *, revision, repository_id, acl_scope):
            return {"symbol_versions": 2, "module_versions": 1}

        def expand_candidates(self, *args, **kwargs):
            raise RuntimeError("bounded expansion timed out")

    change, _ = _change()
    out = EvidenceChangeAnalyzer(graph_client=ExpandRaisingClient()).analyze(change)
    assert out.graph_status == "unavailable"
    assert out.graph_updated is True  # populate DID succeed — the flag is about the impact leg
    assert out.impacted_count is None
    by = {f["predicate"] for f in out.facts}
    assert "changed_symbol_count" in by
    assert "impacted_symbol_count" not in by


def test_impact_expansion_allowlist_excludes_supersedes():
    """cap_2a p1: the impact traversal narrows the retrieval allowlist — SUPERSEDES (version
    history) is never an impact edge; the retrieval allowlist itself is unchanged."""
    from agentic_dynamics.knowledge.graph import ALLOWED_EXPANSION_RELS, IMPACT_EXPANSION_RELS

    assert ALLOWED_EXPANSION_RELS - {"SUPERSEDES"} == IMPACT_EXPANSION_RELS
    assert "SUPERSEDES" not in IMPACT_EXPANSION_RELS
    assert "CALLS" in IMPACT_EXPANSION_RELS and "AFFECTS" in IMPACT_EXPANSION_RELS


def test_scope_contains_changed_symbols_even_without_graph():
    """cap_2a_rerun2 scope-miss regression (the verdict's prescription, made structural):
    the executor scope must contain the changed symbols themselves — the rerun2 rework
    proposal's scope was the reachable dependents only, so the hit rule could never score
    a rework leg. Without a graph the delta's own symbols still form a usable scope."""
    change, _ = _change()
    analyzer = EvidenceChangeAnalyzer(graph_client=None)  # no graph: delta-only
    out = analyzer.analyze(change)
    assert out.graph_status == "not_requested"
    assert out.neighborhood == ("add", "top")  # the changed symbols, no expansion
    assert out.impacted_count is None  # unknown, never 0


def test_stalled_graph_degrades_within_deadline_never_hangs():
    """cap_2a p1 (found live during p2): a STALLED graph — a Bolt peer that never answers, a
    hung connection-acquisition retry — must degrade within the client-side deadline, never
    hang the phase. The analyzer's hard deadline turns a non-returning driver into an
    unavailable status with delta-only facts, exactly like a raised error."""
    import time

    class StalledGraphClient:
        def populate_versioned_graph(self, snapshot, *, revision, repository_id, acl_scope):
            time.sleep(60)  # simulate a driver stuck in a retry loop

        def expand_candidates(self, *args, **kwargs):
            time.sleep(60)

    change, _ = _change()
    analyzer = EvidenceChangeAnalyzer(graph_client=StalledGraphClient())
    analyzer.GRAPH_LEG_TIMEOUT_SECONDS = 1.0  # shrink the deadline for the test
    t0 = time.monotonic()
    out = analyzer.analyze(change)
    elapsed = time.monotonic() - t0

    assert elapsed < 10.0  # returned despite the stalled client
    assert out.graph_status == "unavailable"
    assert out.impacted_count is None
    assert out.neighborhood == ()
    by = {f["predicate"] for f in out.facts}
    assert "changed_symbol_count" in by  # delta facts survived the stalled graph leg
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
