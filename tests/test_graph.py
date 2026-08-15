"""Tests for Neo4j graph module — Neo4jClient, _BufferedResult."""

import pytest
import socket
from pathlib import Path
from instrument.graph import ALLOWED_EXPANSION_RELS, Neo4jClient, _BufferedResult
from instrument.embeddings import step_doc_id

try:
    s = socket.create_connection(("localhost", 7687), timeout=2); s.close()
    _NEO4J_OK = True
except Exception:
    _NEO4J_OK = False

pytestmark = pytest.mark.skipif(not _NEO4J_OK, reason="Neo4j not available on localhost:7687")


class _Neo4jTestBase:
    """Shared autouse fixture: one Neo4jClient per test, closed on teardown."""

    @pytest.fixture(autouse=True)
    def _setup_client(self):
        self.client = Neo4jClient(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password123",
        )
        yield
        self.client.close()


class TestBufferedResult:
    def test_single_returns_first_record(self):
        records = [{"c": 5}, {"c": 10}]
        br = _BufferedResult(records)
        assert br.single() == {"c": 5}

    def test_single_empty_returns_none(self):
        br = _BufferedResult([])
        assert br.single() is None

    def test_iter_yields_all_records(self):
        records = [{"a": 1}, {"b": 2}, {"c": 3}]
        br = _BufferedResult(records)
        result = list(br)
        assert len(result) == 3
        assert result == records

    def test_len_returns_count(self):
        br = _BufferedResult([1, 2, 3, 4])
        assert len(br) == 4


class TestNeo4jClient:
    @pytest.fixture(autouse=True)
    def setup_client(self):
        self.client = Neo4jClient(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password123",
        )
        yield
        self.client.close()

    def test_connectivity(self):
        result = self.client._run("RETURN 1 AS num")
        assert result.single()["num"] == 1

    def test_run_returns_buffered_result(self):
        result = self.client._run("RETURN 42 AS answer")
        assert result.single()["answer"] == 42

    def test_create_schema_idempotent(self):
        self.client.create_schema()
        self.client.create_schema()
        assert True

    def test_load_operators_creates_nodes(self):
        self.client.load_operators()
        result = self.client._run(
            "MATCH (o:PerturbationOperator) RETURN count(o) AS c"
        )
        assert result.single()["c"] >= 10

    def test_load_operators_creates_strategies(self):
        self.client.load_operators()
        result = self.client._run(
            "MATCH (s:StrategyArchetype) RETURN count(s) AS c"
        )
        assert result.single()["c"] == 4

    def test_load_models(self):
        self.client.load_models()
        result = self.client._run("MATCH (m:Model) RETURN count(m) AS c")
        count = result.single()["c"]
        assert count >= 1
        assert count <= 20

    def test_model_properties_set_correctly(self):
        self.client.load_models()
        result = self.client._run(
            "MATCH (m:Model {model_id: 'deepseek/deepseek-v4-pro'}) "
            "RETURN m.provider, m.count, m.avg_cost_per_session"
        )
        record = result.single()
        assert record is not None
        assert record["m.provider"] == "deepseek"
        assert record["m.count"] > 0

    def test_load_runs(self):
        self.client.load_runs()
        result = self.client._run("MATCH (r:ExperimentRun) RETURN count(r) AS c")
        assert result.single()["c"] >= 1

    def test_link_runs_creates_run_on_relationships(self):
        self.client.load_models()
        self.client.load_runs()
        self.client.link_runs()
        result = self.client._run(
            "MATCH ()-[rel:RUN_ON]->() RETURN count(rel) AS c"
        )
        assert result.single()["c"] > 0

    def test_load_basin_topology(self):
        self.client.load_basin_topology()
        result = self.client._run("MATCH (bt:BasinTopology) RETURN count(bt) AS c")
        assert result.single()["c"] >= 1

    def test_load_basin_topology_creates_profiles(self):
        self.client.load_basin_topology()
        result = self.client._run("MATCH (bp:BasinProfile) RETURN count(bp) AS c")
        assert result.single()["c"] >= 1

    def test_load_configs(self):
        self.client.load_configs()
        result = self.client._run("MATCH (c:ExperimentConfig) RETURN count(c) AS c")
        assert result.single()["c"] >= 1

    def test_build_returns_counts(self):
        counts = self.client.build()
        assert "models" in counts
        assert "runs" in counts
        assert "configs" in counts
        assert counts["models"] > 0
        assert counts["runs"] > 0
        assert counts["run_on_rels"] > 0


class TestKnowledgeSchema(_Neo4jTestBase):
    """Knowledge constraints/indexes + native full-text index."""

    def test_create_knowledge_schema_idempotent(self):
        self.client.create_knowledge_schema()
        self.client.create_knowledge_schema()  # IF NOT EXISTS — safe to re-run

    def test_knowledge_constraints_exist(self):
        self.client.create_knowledge_schema()
        recs = self.client._run(
            "SHOW CONSTRAINTS YIELD name RETURN name"
        )
        names = {r["name"] for r in recs}
        assert "knowledge_id_unique" in names
        assert "step_id_unique" in names
        assert "code_module_path_unique" in names

    def test_knowledge_indexes_exist(self):
        self.client.create_knowledge_schema()
        recs = self.client._run("SHOW INDEXES YIELD name RETURN name")
        names = {r["name"] for r in recs}
        assert "knowledge_entity_id" in names
        assert "step_doc_id" in names
        assert "code_module_name" in names

    def test_fulltext_index_exists(self):
        self.client.create_knowledge_schema()
        recs = self.client._run("SHOW FULLTEXT INDEXES YIELD name RETURN name")
        names = {r["name"] for r in recs}
        assert "step_text_ft" in names

    def test_knowledge_id_uniqueness_enforced(self):
        self.client.create_knowledge_schema()
        self.client._run(
            "MERGE (k:Knowledge {knowledge_id: 'ks_dup'}) SET k.entity_id = 'ent_x'"
        )
        # A second insert with the same knowledge_id must fail on the constraint.
        with pytest.raises(Exception):
            self.client._run(
                "CREATE (k:Knowledge {knowledge_id: 'ks_dup', entity_id: 'ent_y'})"
            )
        self.client._run("MATCH (k:Knowledge {knowledge_id: 'ks_dup'}) DETACH DELETE k")


class TestBuildStepGraph(_Neo4jTestBase):
    """doc_id/text regression — the dense↔graph join repair."""

    def test_step_doc_id_matches_embeddings_scheme(self):
        # The canonical id formatter is shared by embeddings and graph.
        assert step_doc_id("sess_1", 0) == "sess_1_step_0000"
        assert step_doc_id("sess_1", 12) == "sess_1_step_0012"

    def test_build_step_graph_populates_doc_id_and_text(self):
        counts = self.client.build_step_graph(max_steps=5)
        assert counts["steps"] > 0
        recs = self.client._run(
            "MATCH (s:Step) WHERE s.doc_id IS NOT NULL AND s.doc_id <> '' "
            "RETURN s.session_id AS session_id, s.step_index AS step_index, "
            "s.doc_id AS doc_id, s.text AS text LIMIT 10"
        )
        rows = list(recs)
        assert len(rows) > 0
        for row in rows:
            # The graph doc_id MUST equal the canonical Chroma id for the same
            # (session, step) — the cross-store join both indexes share.
            assert row["doc_id"] == step_doc_id(row["session_id"], row["step_index"])
            assert row["text"]  # text is now populated (previously never set)


class TestCodeModuleGraph(_Neo4jTestBase):
    """CodeModule nodes + IMPORTS/IMPORTED_BY/TOUCHED edges."""

    _A = "codemodule_test_a.py"
    _B = "codemodule_test_b.py"
    _WT = "wt_codemodule_test"

    @pytest.fixture(autouse=True)
    def _cleanup(self, _setup_client):
        yield
        self.client._run(
            "MATCH (n:CodeModule) WHERE n.module_path IN [$a, $b] DETACH DELETE n",
            {"a": self._A, "b": self._B},
        )
        self.client._run(
            "MATCH (r:ExperimentRun {worktree_name: $wt}) DETACH DELETE r",
            {"wt": self._WT},
        )

    def test_load_codebase_graph_writes_nodes_and_edges(self):
        from instrument.codebase_graph import CodebaseGraph, ModuleNode

        graph = CodebaseGraph(language="python")
        graph.modules = {
            self._A: ModuleNode(path=self._A, loc=10, imports_from=[self._B]),
            self._B: ModuleNode(path=self._B, loc=5, imports_from=[]),
        }

        counts = self.client.load_codebase_graph(graph, self._WT)
        assert counts["modules"] == 2
        assert counts["imports"] == 1
        assert counts["imported_by"] == 1
        assert counts["touched"] == 2

        # TOUCHED: the run links every module it touched.
        recs = self.client._run(
            "MATCH (r:ExperimentRun {worktree_name: $wt})-[:TOUCHED]->(c:CodeModule) "
            "RETURN count(c) AS c",
            {"wt": self._WT},
        )
        assert recs.single()["c"] == 2

        # IMPORTS: a -> b, IMPORTED_BY: b -> a.
        recs = self.client._run(
            "MATCH (a:CodeModule {module_path: $a})-[:IMPORTS]->(b:CodeModule {module_path: $b}) "
            "RETURN count(*) AS c",
            {"a": self._A, "b": self._B},
        )
        assert recs.single()["c"] == 1
        recs = self.client._run(
            "MATCH (b:CodeModule {module_path: $b})-[:IMPORTED_BY]->(a:CodeModule {module_path: $a}) "
            "RETURN count(*) AS c",
            {"a": self._A, "b": self._B},
        )
        assert recs.single()["c"] == 1


class TestExpandCandidates(_Neo4jTestBase):
    """Bounded, allowlisted graph expansion."""

    @pytest.fixture(autouse=True)
    def _cleanup(self, _setup_client):
        self.client._run("MATCH (n:__TestExpand) DETACH DELETE n")
        yield
        self.client._run("MATCH (n:__TestExpand) DETACH DELETE n")

    def _seed_element_id(self, name: str) -> str:
        rec = self.client._run_value(
            "MATCH (n:__TestExpand {name: $name}) RETURN elementId(n) AS eid",
            {"name": name},
        )
        assert rec is not None
        return rec["eid"]

    def _build_star(self):
        self.client._run(
            "CREATE (a:__TestExpand {name: 'a'}) "
            "CREATE (b:__TestExpand {name: 'b'}) "
            "CREATE (c:__TestExpand {name: 'c'}) "
            "CREATE (d:__TestExpand {name: 'd'}) "
            "CREATE (e:__TestExpand {name: 'e'}) "
            "MERGE (a)-[:DEFINES]->(b) "
            "MERGE (a)-[:DEFINES]->(c) "
            "MERGE (a)-[:MENTIONS]->(d) "
            "MERGE (c)-[:DEFINES]->(e)"
        )

    def test_expand_respects_allowlist(self):
        self._build_star()
        seed = self._seed_element_id("a")
        nodes = self.client.expand_candidates([seed], max_depth=2)
        names = {n["properties"].get("name") for n in nodes}
        assert {"a", "b", "c", "e"} <= names
        assert "d" not in names  # MENTIONS is not on the allowlist

    def test_expand_respects_depth(self):
        self._build_star()
        seed = self._seed_element_id("a")
        nodes = self.client.expand_candidates([seed], max_depth=1)
        names = {n["properties"].get("name") for n in nodes}
        assert {"a", "b", "c"} <= names
        assert "e" not in names  # two hops away, excluded at max_depth=1

    def test_expand_respects_neighbor_and_node_bounds(self):
        self.client._run(
            "CREATE (a:__TestExpand {name: 'hub'}) "
            "WITH a UNWIND range(1, 10) AS i "
            "CREATE (n:__TestExpand {name: 'leaf_' + toString(i)}) "
            "MERGE (a)-[:DEFINES]->(n)"
        )
        seed = self._seed_element_id("hub")
        nodes = self.client.expand_candidates(
            [seed], max_depth=1, max_neighbors=3, max_nodes=4
        )
        # hub + up to 3 neighbors, capped at 4 total nodes.
        assert len(nodes) == 4
        names = {n["properties"].get("name") for n in nodes}
        assert "hub" in names

    def test_allowlisted_relationships_are_fixed(self):
        assert ALLOWED_EXPANSION_RELS == {
            "DEFINES", "IMPORTS", "CALLS", "TESTED_BY",
            "PRODUCED_BY", "PRECEDES", "SUPERSEDES", "CONTRADICTS",
        }


class TestSearchHelpers(_Neo4jTestBase):
    """Exact-property + full-text search (typed, no hand-written Cypher)."""

    @pytest.fixture(autouse=True)
    def _cleanup(self, _setup_client):
        yield
        self.client._run("MATCH (k:Knowledge {knowledge_id: 'kf_001'}) DETACH DELETE k")
        self.client._run("MATCH (s:Step {step_id: 'ft_1'}) DETACH DELETE s")
        self.client._run(
            "MATCH (s:Step) WHERE s.step_id IN ['ft_c1', 'ft_c2', 'ft_c3'] DETACH DELETE s"
        )

    def test_find_exact_returns_matching_node(self):
        self.client._run(
            "MERGE (k:Knowledge {knowledge_id: 'kf_001'}) SET k.entity_id = 'ent_1'"
        )
        res = self.client.find_exact("Knowledge", "knowledge_id", "kf_001")
        assert len(res) == 1
        assert res[0]["properties"]["knowledge_id"] == "kf_001"
        assert "Knowledge" in res[0]["labels"]

    def test_find_exact_rejects_non_identifier(self):
        with pytest.raises(ValueError):
            self.client.find_exact("Knowledge; DROP", "knowledge_id", "x")

    def test_search_fulltext_returns_matching_step(self):
        self.client.create_knowledge_schema()
        self.client._run(
            "MERGE (s:Step {step_id: 'ft_1'}) SET s.text = 'websocket live reload protocol'"
        )
        res = self.client.search_fulltext("step_text_ft", "websocket")
        assert len(res) >= 1
        assert any(r["properties"].get("step_id") == "ft_1" for r in res)

    def test_search_fulltext_commit_filter_excludes_stale_commit(self):
        self.client.create_knowledge_schema()
        # Three matches on the same text: one on the current commit, one on a stale
        # commit, and one with no commit_sha at all (absent → IS NULL → eligible).
        self.client._run(
            "MERGE (s:Step {step_id: 'ft_c1'}) "
            "SET s.text = 'websocket live reload protocol', s.commit_sha = 'abc'"
        )
        self.client._run(
            "MERGE (s:Step {step_id: 'ft_c2'}) "
            "SET s.text = 'websocket live reload protocol', s.commit_sha = 'xyz'"
        )
        self.client._run(
            "MERGE (s:Step {step_id: 'ft_c3'}) "
            "SET s.text = 'websocket live reload protocol'"
        )

        res = self.client.search_fulltext("step_text_ft", "websocket", commit="abc")
        ids = {r["properties"].get("step_id") for r in res}
        assert "ft_c1" in ids          # current commit passes
        assert "ft_c3" in ids          # absent commit_sha passes (IS NULL)
        assert "ft_c2" not in ids      # stale commit is pre-filtered out

    def test_search_fulltext_no_commit_is_back_compatible(self):
        self.client.create_knowledge_schema()
        self.client._run(
            "MERGE (s:Step {step_id: 'ft_c2'}) "
            "SET s.text = 'websocket live reload protocol', s.commit_sha = 'xyz'"
        )
        # Omitting commit keeps the historical no-filter behavior: the stale-commit
        # node is still returned.
        res = self.client.search_fulltext("step_text_ft", "websocket")
        assert any(r["properties"].get("step_id") == "ft_c2" for r in res)
