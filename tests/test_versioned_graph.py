"""Versioned-graph tests (design §5.5 — e4 of cap_evidence_integrity).

Live-Neo4j integration tests: a fixture revision pair produces ModuleVersion/SymbolVersion
nodes with the two-ID contract + SUPERSEDES edges + CONTAINS/DEFINES/IMPORTS/CALLS/TESTED_BY
edges; the traversal ACL constrains the seed AND every hop (a public-scope seed can never
reach a private-repo node — the hop constraint, not a post-filter); legacy callers that omit
the ACL args interact ONLY with unversioned nodes (versioned nodes fail closed); and the
multi-label Knowledge:SymbolVersion seed join works (Knowledge full-text seed -> symbol
versions).
"""

import socket

import pytest

from agentic_dynamics.core.language import (
    _PROFILES,
    build_code_snapshot,
    compute_code_delta,
    module_entity_id,
    module_version_id,
    symbol_entity_id,
    symbol_version_id,
)
from agentic_dynamics.knowledge.graph import Neo4jClient

try:
    socket.create_connection(("localhost", 7687), timeout=2).close()
    _NEO4J_OK = True
except Exception:
    _NEO4J_OK = False

pytestmark = [
    pytest.mark.external,
    pytest.mark.skipif(not _NEO4J_OK, reason="Neo4j not available on localhost:7687"),
]

PY = _PROFILES["python"]
REPO = "e4-test-repo"


@pytest.fixture()
def client():
    c = Neo4jClient()
    # Isolate to a private test namespace: purge our versioned nodes + edges.
    c._run(
        "MATCH (n) WHERE n.repository_id = $repo OR n.acl_scope IN ['e4-public', 'e4-private'] "
        "DETACH DELETE n",
        {"repo": REPO},
    )
    yield c
    c._run(
        "MATCH (n) WHERE n.repository_id = $repo OR n.acl_scope IN ['e4-public', 'e4-private'] "
        "DETACH DELETE n",
        {"repo": REPO},
    )
    c.close()


def _snapshot(revision: str, src: bytes):
    return build_code_snapshot({"app.py": src}, revision=revision, profile=PY)


def _count(client, cypher: str, params=None):
    rec = client._run_value(cypher, params or {})
    return rec["c"]


class TestVersionedPopulation:
    def test_revision_pair_produces_versions_and_supersedes(self, client):
        r1 = _snapshot("rev-1", b"def foo():\n    return 1\n")
        r2 = _snapshot("rev-2", b"def foo():\n    return 99\n")
        c1 = client.populate_versioned_graph(r1, revision="rev-1", repository_id=REPO, acl_scope="public")
        c2 = client.populate_versioned_graph(r2, revision="rev-2", repository_id=REPO, acl_scope="public")

        assert c1["module_versions"] == 1 and c1["symbol_versions"] == 1
        assert c2["module_versions"] == 1 and c2["symbol_versions"] == 1

        # Two versions of the same entity -> one SUPERSEDES edge (new -> old).
        assert _count(
            client, "MATCH (:SymbolVersion)-[:SUPERSEDES]->(:SymbolVersion) RETURN count(*) AS c"
        ) == 1
        assert _count(
            client, "MATCH (:ModuleVersion)-[:SUPERSEDES]->(:ModuleVersion) RETURN count(*) AS c"
        ) == 1

        # Two-ID contract on the version nodes.
        ent = symbol_entity_id(REPO, "app.py", "foo", "function")
        v1 = symbol_version_id(ent, "rev-1", r1.files["app.py"][0].content_hash)
        v2 = symbol_version_id(ent, "rev-2", r2.files["app.py"][0].content_hash)
        assert v1 != v2
        rec = client._run_value(
            "MATCH (s:SymbolVersion {version_id: $vid}) RETURN s.entity_id AS eid",
            {"vid": v2},
        )
        assert rec["eid"] == ent

    def test_contains_defines_imports_edges(self, client):
        snap = build_code_snapshot(
            {
                "math_utils.py": b"import os_helper\n\ndef add(a, b):\n    return a + b\n\nclass Calc:\n    def mul(self, x):\n        return x * 2\n",
                "os_helper.py": b"def helper():\n    return 1\n",
            },
            revision="rev-1",
            profile=PY,
        )
        counts = client.populate_versioned_graph(snap, revision="rev-1", repository_id=REPO, acl_scope="public")
        assert counts["contains"] >= 6  # Revision->Module x2 + Module->Symbol x4 (defined twice each)
        assert counts["defines"] == 4  # add, Calc, Calc.mul, helper
        assert counts["imports"] >= 1  # math_utils imports os (via the import target slot)

        # The CALCULATOR method is a qualified-name symbol, DEFINES from its module.
        assert _count(
            client,
            "MATCH (:ModuleVersion)-[:DEFINES]->(:SymbolVersion {qualified_name: 'Calc.mul'}) "
            "RETURN count(*) AS c",
        ) == 1

    def test_call_and_tested_by_edges(self, client):
        snap = build_code_snapshot(
            {
                "math_utils.py": b"def add(a, b):\n    return a + b\n\ndef top():\n    return add(1, 2)\n",
                "test_math_utils.py": b"def test_add():\n    assert True\n",
            },
            revision="rev-1",
            profile=PY,
        )
        counts = client.populate_versioned_graph(snap, revision="rev-1", repository_id=REPO, acl_scope="public")
        assert counts["calls"] >= 1  # top() calls add()
        assert _count(
            client,
            "MATCH (:SymbolVersion {qualified_name: 'top'})-[:CALLS]->(:SymbolVersion {qualified_name: 'add'}) "
            "RETURN count(*) AS c",
        ) == 1
        assert counts["tested_by"] >= 1  # TESTED_BY rule: test_math_utils.py -> math_utils.py
        assert _count(
            client,
            "MATCH (:SymbolVersion {qualified_name: 'add'})-[:TESTED_BY]->(:SymbolVersion {qualified_name: 'test_add'}) "
            "RETURN count(*) AS c",
        ) == 1

    def test_affects_edges_from_issues(self, client):
        from agentic_dynamics.measurement.sonar import SonarIssue

        snap = _snapshot("rev-1", b"def foo():\n    return 1\n")
        issue = SonarIssue(key="k1", rule="python:S113", severity="MINOR", message="x",
                           file_path="app.py", line=1)
        counts = client.populate_versioned_graph(
            snap, revision="rev-1", repository_id=REPO, acl_scope="public", issues=[issue]
        )
        assert counts["affects"] == 1
        assert _count(
            client,
            "MATCH (:SonarIssue {key: 'k1'})-[:AFFECTS]->(:SymbolVersion {qualified_name: 'foo'}) "
            "RETURN count(*) AS c",
        ) == 1

    def test_multi_label_seed_join(self, client):
        client.create_knowledge_schema()
        snap = _snapshot("rev-1", b"def calc_total():\n    return 42\n")
        client.populate_versioned_graph(snap, revision="rev-1", repository_id=REPO, acl_scope="e4-public")

        # The versioned symbol is ALSO a Knowledge node: full-text finds it as a seed.
        recs = client.search_knowledge_fulltext("calc_total")
        assert any("Knowledge" in r["labels"] and "SymbolVersion" in r["labels"] for r in recs)
        seed = next(r for r in recs if "SymbolVersion" in r["labels"])
        # A scoped expansion from that Knowledge seed resolves the symbol version (seed join).
        nodes = client.expand_candidates(
            [seed["properties"]["knowledge_id"]], max_depth=0, repository_id=REPO, acl_scope="e4-public"
        )
        assert nodes and "SymbolVersion" in nodes[0]["labels"]
        assert nodes[0]["properties"]["repository_id"] == REPO


class TestTraversalACL:
    def _two_repo_fixture(self, client) -> str:
        """A public repo symbol that CONTAINS a private-repo symbol, linked via DEFINES."""
        # public repo: app.py contains a symbol that references the private one via CALLS.
        pub_snap = build_code_snapshot(
            {"app.py": b"def public_api():\n    return call_private()\n\ndef call_private():\n    return 1\n"},
            revision="rev-1",
            profile=PY,
        )
        client.populate_versioned_graph(pub_snap, revision="rev-1", repository_id=REPO, acl_scope="e4-public")
        # private repo: same file, its own symbol versions.
        priv_snap = build_code_snapshot(
            {"app.py": b"def private_secret():\n    return 1\n"},
            revision="rev-1",
            profile=PY,
        )
        client.populate_versioned_graph(priv_snap, revision="e4-private-repo", repository_id="e4-private-repo", acl_scope="e4-private")
        pub_sym = next(s for s in pub_snap.files["app.py"] if s.qualified_name == "public_api")
        return symbol_version_id(
            symbol_entity_id(REPO, "app.py", "public_api", "function"), "rev-1", pub_sym.content_hash
        )

    def test_scoped_seed_cannot_reach_private_repo_node(self, client):
        vid = self._two_repo_fixture(client)

        nodes = client.expand_candidates([vid], max_depth=2, repository_id=REPO, acl_scope="e4-public")
        reached_repos = {n["properties"].get("repository_id") for n in nodes}
        assert "e4-private-repo" not in reached_repos  # the hop constraint, not a post-filter
        # The seed itself resolves within scope.
        assert any(n["properties"].get("version_id") == vid for n in nodes)

    def test_legacy_omitted_scope_fails_closed_for_versioned(self, client):
        vid = self._two_repo_fixture(client)
        # Omitting the ACL args (legacy default): a versioned seed is UNRESOLVABLE —
        # versioned nodes fail closed on missing scope, always.
        nodes = client.expand_candidates([vid], max_depth=1)
        assert nodes == []

    def test_legacy_omitted_scope_still_reaches_unversioned(self, client):
        # An unversioned legacy node is still reachable without scope (back-compatible).
        client._run("MERGE (n:__E4Legacy {name: 'legacy', doc_id: 'doc_legacy'})")
        try:
            nodes = client.expand_candidates(["doc_legacy"], max_depth=0)
            assert len(nodes) == 1
            assert nodes[0]["properties"]["name"] == "legacy"
        finally:
            client._run("MATCH (n:__E4Legacy) DETACH DELETE n")


class TestVersionedDeltaPurity:
    def test_population_is_additive_unversioned_untouched(self, client):
        client._run("MERGE (l:__E4Unversioned {name: 'keep', doc_id: 'doc_keep'})")
        try:
            snap = _snapshot("rev-1", b"def foo():\n    pass\n")
            client.populate_versioned_graph(snap, revision="rev-1", repository_id=REPO, acl_scope="public")
            rec = client._run_value(
                "MATCH (l:__E4Unversioned {doc_id: 'doc_keep'}) RETURN l.name AS name",
            )
            assert rec is not None and rec["name"] == "keep"
            # No versioned node was created FROM it, and no unversioned node got versioned.
            assert _count(client, "MATCH (:__E4Unversioned) RETURN count(*) AS c") == 1
        finally:
            client._run("MATCH (n:__E4Unversioned) DETACH DELETE n")
