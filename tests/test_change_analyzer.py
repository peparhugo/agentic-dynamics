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
    # The DECLARED semantics (graph-family Part A p4): the healthy graph produced the count and
    # the pinned definition is recorded — queryable, auditable, never implicit.
    assert out.impacted_source == "graph"
    assert out.impacted_semantics == "structural"

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
    """No graph: the in-process AST walk is the seam's default posture (graph-family Part A p4
    — additive, never a gate). The impacted computation still happens; its provenance is
    declared (``in_process_walk``), and the semantics stay pinned (``structural``)."""
    change, _ = _change()
    analyzer = EvidenceChangeAnalyzer(graph_client=None)  # no graph: hermetic, still facts
    out = analyzer.analyze(change)
    assert out.graph_updated is False
    # The fixture's only caller of a changed symbol (top calls add) is ITSELF a seed — so the
    # in-process walk honestly computes 0 non-seed dependants (a computed 0, not an unknown).
    assert out.impacted_count == 0
    assert out.impacted_semantics == "structural"
    assert out.impacted_source == "in_process_walk"
    assert out.graph_status == "not_requested"  # explicit: the graph leg was never asked for
    by = {f["predicate"]: f for f in out.facts}
    assert "changed_symbol_count" in by
    assert by["impacted_symbol_count"]["value"] == "0"


def test_graph_down_preserves_delta_facts_and_exposes_status():
    """cap_2a p1: a graph client whose populate_versioned_graph raises must NOT escape — the
    analysis rolls back to the IN-PROCESS AST WALK (graph-family Part A p4) with an explicit
    unavailable status + declared provenance, no fabricated zero and no gate on the run. The
    reducer errors untouched (they still propagate)."""
    class RaisingGraphClient:
        def populate_versioned_graph(self, snapshot, *, revision, repository_id, acl_scope):
            raise RuntimeError("neo4j connection refused")

        def expand_candidates(self, *args, **kwargs):
            raise AssertionError("must not be called after populate failed")

    change, _ = _change()
    out = EvidenceChangeAnalyzer(graph_client=RaisingGraphClient()).analyze(change)
    assert out.graph_status == "unavailable"
    assert out.graph_updated is False
    # The rollback walk computed the impacted set from the AST (0 non-seed dependants in this
    # fixture) — declared provenance, never a silent omission.
    assert out.impacted_count == 0
    assert out.impacted_source == "in_process_walk"
    assert out.neighborhood == ("add", "top")
    by = {f["predicate"] for f in out.facts}
    assert "changed_symbol_count" in by  # delta facts preserved
    assert "impacted_symbol_count" in by  # computed in-process, provenance declared


def test_requested_but_unavailable_graph_is_not_mislabeled():
    """A requested graph whose client could not be constructed remains visibly unavailable;
    the in-process walk still supplies the impacted computation (additive, never a gate)."""
    change, _ = _change()
    out = EvidenceChangeAnalyzer(graph_client=None, graph_requested=True).analyze(change)
    assert out.graph_status == "unavailable"
    assert out.impacted_count == 0
    assert out.impacted_source == "in_process_walk"
    assert "impacted_symbol_count" in {f["predicate"] for f in out.facts}
    assert out.to_dict()["graph_status"] == "unavailable"


def test_expand_failure_degrades_to_unavailable():
    """The impact leg failing after a successful populate also flags the cell — the seam rolls
    back to the in-process walk (provenance declared), never a fabricated unknown."""
    class ExpandRaisingClient:
        def populate_versioned_graph(self, snapshot, *, revision, repository_id, acl_scope):
            return {"symbol_versions": 2, "module_versions": 1}

        def expand_candidates(self, *args, **kwargs):
            raise RuntimeError("bounded expansion timed out")

    change, _ = _change()
    out = EvidenceChangeAnalyzer(graph_client=ExpandRaisingClient()).analyze(change)
    assert out.graph_status == "unavailable"
    assert out.graph_updated is True  # populate DID succeed — the flag is about the impact leg
    assert out.impacted_count == 0
    assert out.impacted_source == "in_process_walk"
    by = {f["predicate"] for f in out.facts}
    assert "changed_symbol_count" in by
    assert "impacted_symbol_count" in by


def test_impact_expansion_allowlist_excludes_supersedes():
    """cap_2a p1: the impact traversal narrows the retrieval allowlist — SUPERSEDES (version
    history) is never an impact edge; the retrieval allowlist itself is unchanged."""
    from agentic_dynamics.knowledge.graph import ALLOWED_EXPANSION_RELS, IMPACT_EXPANSION_RELS

    assert ALLOWED_EXPANSION_RELS - {"SUPERSEDES"} == IMPACT_EXPANSION_RELS
    assert "SUPERSEDES" not in IMPACT_EXPANSION_RELS
    assert "CALLS" in IMPACT_EXPANSION_RELS and "AFFECTS" in IMPACT_EXPANSION_RELS


# ── The graph-family Part A seam (p4) — the wall's fix: graph-first + in-process rollback ──


def _wall_fixture():
    """The 2d/2e wall in miniature: a behavior-preserving change to ``add`` plus the added
    widgets that structurally call it (the widgets-call-add dependants). The only NON-SEED
    structural dependant of the changed symbols is ``test_add``."""
    before = build_code_snapshot(
        {
            "calc.py": b"def add(a, b):\n    return a + b\n",
            "widgets.py": b"",
            "test_calc.py": (
                b"def test_add():\n    from calc import add\n"
                b"    assert add(1, 1) == 2\n"
            ),
        },
        revision="rev-1",
        profile=PY,
    )
    after = build_code_snapshot(
        {
            # add's body is split — a behavior-preserving change.
            "calc.py": b"def add(a, b):\n    result = a + b\n    return result\n",
            # the added widgets: structural dependants of add (the wall's edges).
            "widgets.py": (
                b"from calc import add\n"
                b"\ndef widget_1(x):\n    return add(x, 1)\n"
                b"\ndef widget_2(x):\n    return add(x, 2)\n"
            ),
            "test_calc.py": (
                b"def test_add():\n    from calc import add\n"
                b"    assert add(1, 1) == 2\n"
            ),
        },
        revision=REV,
        profile=PY,
    )
    return before, after, compute_code_delta(before, after)


def test_wall_style_seam_recovers_structural_dependant():
    """The 2e wall's fix, reproduced at the seam: the graph query comes back EMPTY (returns
    only the seeds — the wall's truncation/empty signature) while the in-process AST walk sees
    the structural dependant (``test_add``). The seam ROLLS BACK — impacted=1, not the wall's
    wrong 0 — and declares the provenance + the pinned semantics."""
    class EmptyGraphClient:
        def populate_versioned_graph(self, snapshot, *, revision, repository_id, acl_scope):
            return {"symbol_versions": len(snapshot.all_symbols), "module_versions": 1}

        def expand_candidates(self, seed_ids, *, max_depth, max_neighbors, max_nodes,
                              timeout_ms, repository_id, acl_scope, rels=None):
            # The empty result: only the seeds resolve, no dependants — the graph "answered"
            # but has nothing to show (truncated or unpopulated scope).
            return [
                {"properties": {"version_id": s, "qualified_name": f"seed-{i}"}, "canonical_id": s}
                for i, s in enumerate(seed_ids)
            ]

    before, after, delta = _wall_fixture()
    change = ChangeInput(
        before=before, after=after, delta=delta, revision=REV,
        repository_id=REPO, acl_scope="public",
    )
    out = EvidenceChangeAnalyzer(graph_client=EmptyGraphClient()).analyze(change)
    # The graph was reachable (status available) but its answer under-counted the AST's —
    # the empty/truncated failure — so the seam kept the in-process walk's structural answer.
    assert out.graph_status == "available"
    assert out.impacted_count == 1  # test_add — the wall's wrong 0 is NOT reproduced by the seam
    assert "test_add" in out.neighborhood
    assert out.impacted_source == "in_process_walk"
    assert out.impacted_semantics == "structural"
    by = {f["predicate"]: f for f in out.facts}
    assert by["impacted_symbol_count"]["value"] == "1"


def test_healthy_graph_preferred_when_richer():
    """A healthy graph (a result at least as rich as the in-process walk) is preferred — the
    seam is graph-first, the in-process walk is only the rollback."""
    before, after, delta = _wall_fixture()
    change = ChangeInput(
        before=before, after=after, delta=delta, revision=REV,
        repository_id=REPO, acl_scope="public",
    )
    class RichGraphClient:
        def populate_versioned_graph(self, snapshot, *, revision, repository_id, acl_scope):
            return {"symbol_versions": len(snapshot.all_symbols), "module_versions": 1}

        def expand_candidates(self, seed_ids, *, max_depth, max_neighbors, max_nodes,
                              timeout_ms, repository_id, acl_scope, rels=None):
            nodes = [
                {"properties": {"version_id": s, "qualified_name": f"seed-{i}"}, "canonical_id": s}
                for i, s in enumerate(seed_ids)
            ]
            # The graph sees test_add AND the two-hop module-reach (subtract) — richer than the
            # in-process call walk (which only sees test_add).
            for qname in ("test_add", "subtract"):
                nodes.append({"properties": {"version_id": f"n-{qname}", "qualified_name": qname},
                              "canonical_id": f"n-{qname}"})
            return nodes

    out = EvidenceChangeAnalyzer(graph_client=RichGraphClient()).analyze(change)
    assert out.graph_status == "available"
    assert out.impacted_count == 2  # the graph's richer result wins (2 >= 1)
    assert out.impacted_source == "graph"
    assert out.impacted_semantics == "structural"


def test_semantics_declared_queryable_on_the_record():
    """The semantics are queryable + auditable: the ChangeAnalysis record carries the pinned
    definition and the evidence payload carries it too (the fact's evidence_ids link back)."""
    from agentic_dynamics.control.reducers.code_change_facts import (
        IMPACTED_SEMANTICS,
        IMPACTED_SOURCES,
    )

    # The declaration is a recorded constant — never an implicit definition.
    assert IMPACTED_SEMANTICS["definition"] == "structural"
    assert "behavioral" in IMPACTED_SEMANTICS["contrast"]
    assert set(IMPACTED_SOURCES) == {"graph", "in_process_walk"}

    change, fake = _change(neighbors=["Calc"])
    out = EvidenceChangeAnalyzer(graph_client=fake).analyze(change)
    assert out.impacted_semantics == IMPACTED_SEMANTICS["definition"]
    assert out.impacted_source == "graph"
    # The evidence payload that backs the impacted fact carries the same declaration.
    evidence = EvidenceChangeAnalyzer._reducer_input(change, out.impacted_count, out.impacted_source)
    imp = next(e for e in evidence.evidence if e.source_type == "impacted_symbols")
    assert imp.payload["semantics"] == "structural"
    assert imp.payload["source"] == "graph"


def test_in_process_walk_is_pure_and_deterministic():
    """The rollback walk is a pure function: no I/O, deterministic, and it reproduces the
    wall's structural dependant (test_add) that the 300ms graph query missed."""
    from agentic_dynamics.control.evidence_analyzer import _in_process_impacted

    before, after, delta = _wall_fixture()
    change = ChangeInput(
        before=before, after=after, delta=delta, revision=REV,
        repository_id=REPO, acl_scope="public",
    )
    scope, impacted = _in_process_impacted(change)
    assert impacted == 1  # test_add — the widgets are seeds, excluded by the wall's rule
    assert set(scope) == {"add", "test_add", "widget_1", "widget_2"}
    # Deterministic.
    assert _in_process_impacted(change) == (scope, impacted)


def test_scope_contains_changed_symbols_even_without_graph():
    """cap_2a_rerun2 scope-miss regression (the verdict's prescription, made structural):
    the executor scope must contain the changed symbols themselves — the rerun2 rework
    proposal's scope was the reachable dependents only, so the hit rule could never score
    a rework leg. Without a graph the delta's own symbols still form a usable scope."""
    change, _ = _change()
    analyzer = EvidenceChangeAnalyzer(graph_client=None)  # no graph: in-process walk
    out = analyzer.analyze(change)
    assert out.graph_status == "not_requested"
    assert out.neighborhood == ("add", "top")  # the changed symbols, no graph expansion
    assert out.impacted_count == 0  # computed by the in-process walk, provenance declared
    assert out.impacted_source == "in_process_walk"


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
    assert out.impacted_count == 0  # the in-process rollback computed it within the deadline
    assert out.impacted_source == "in_process_walk"
    # The executor scope still carries the change's own symbols (the cap_2a scope-miss fix)
    # even when the graph leg stalls — the impacted expansion is the in-process walk's.
    assert out.neighborhood == ("add", "top")
    by = {f["predicate"] for f in out.facts}
    assert "changed_symbol_count" in by  # delta facts survived the stalled graph leg
    assert "impacted_symbol_count" in by  # computed in-process, never gated by the graph


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
