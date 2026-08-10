"""Tests for Neo4j graph module — Neo4jClient, _BufferedResult."""

import pytest
from pathlib import Path
from instrument.graph import Neo4jClient, _BufferedResult


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
