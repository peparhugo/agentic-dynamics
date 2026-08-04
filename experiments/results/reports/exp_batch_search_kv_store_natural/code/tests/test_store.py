"""Tests for distributed key-value store.

Covers storage engine, consistent hashing, node operations,
distributed store with replication/consistency, hot keys,
range queries, batch operations, and distributed joins.
"""

import pytest
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from kv_store.engine import StorageEngine
from kv_store.hash_ring import ConsistentHashRing
from kv_store.node import Node
from kv_store.store import (
    DistributedKVStore,
    ConsistencyLevel,
    WriteResult,
    HotKeyTracker,
)
from kv_store.join import JoinExecutor


class TestStorageEngine:
    def test_put_and_get(self):
        engine = StorageEngine()
        engine.put("hello", "doc1")
        engine.put("hello", "doc2")
        assert engine.get("hello") == ["doc1", "doc2"]
        assert engine.get("missing") is None

    def test_range_query(self):
        engine = StorageEngine()
        for i in range(20):
            engine.put(f"key_{i:03d}", f"doc_{i}")
        results = engine.range_query("key_005", "key_010")
        keys = [k for k, _ in results]
        assert keys == [f"key_{i:03d}" for i in range(5, 11)]

    def test_range_query_exclusive(self):
        engine = StorageEngine()
        for i in range(10):
            engine.put(f"k_{i}", f"doc_{i}")
        results = engine.range_query("k_3", "k_6", inclusive=False)
        keys = [k for k, _ in results]
        assert keys == ["k_4", "k_5"]

    def test_prefix_scan(self):
        engine = StorageEngine()
        engine.put("user:1:name", "Alice")
        engine.put("user:1:email", "alice@test.com")
        engine.put("user:2:name", "Bob")
        engine.put("order:1:total", "100")
        results = engine.prefix_scan("user:1:")
        keys = [k for k, _ in results]
        assert sorted(keys) == ["user:1:email", "user:1:name"]

    def test_batch_put(self):
        engine = StorageEngine()
        entries = [("a", 1), ("b", 2), ("c", 3), ("a", 4)]
        engine.batch_put(entries)
        assert engine.get("a") == [1, 4]
        assert engine.get("b") == [2]
        assert engine.get("c") == [3]
        assert engine.key_count() == 3

    def test_remove(self):
        engine = StorageEngine()
        engine.put("x", 1)
        assert engine.contains("x")
        assert engine.remove("x")
        assert not engine.contains("x")
        assert engine.remove("y") is False

    def test_sorted_order_maintained(self):
        engine = StorageEngine()
        engine.put("z", 1)
        engine.put("a", 1)
        engine.put("m", 1)
        keys = engine.get_all_keys()
        assert keys == sorted(keys)

    def test_hot_key_detection(self):
        engine = StorageEngine()
        for _ in range(100):
            engine.put("hot_key", "val")
        for _ in range(50):
            engine.put("warm_key", "val")
        for _ in range(10):
            engine.put("cold_key", "val")

        for _ in range(5):
            engine.get("hot_key")
        for _ in range(2):
            engine.get("warm_key")
        engine.get("cold_key")

        hot = engine.get_hot_keys(top_n=2)
        assert len(hot) >= 1
        assert hot[0][0] == "hot_key"

        write_hot = engine.get_hot_write_keys(top_n=2)
        assert write_hot[0][0] == "hot_key"

    def test_snapshot(self):
        engine = StorageEngine()
        engine.put("k1", "v1")
        engine.put("k2", "v2")
        snap = engine.get_snapshot()
        assert snap == {"k1": ["v1"], "k2": ["v2"]}
        engine.put("k1", "v1_new")
        assert engine.get("k1") == ["v1", "v1_new"]
        assert snap["k1"] == ["v1"]


class TestConsistentHashRing:
    def test_add_shard(self):
        ring = ConsistentHashRing(virtual_nodes_per_shard=50)
        ring.add_shard("s0")
        assert ring.shard_count() == 1
        assert ring.get_shard("any_key") == "s0"

    def test_multiple_shards(self):
        ring = ConsistentHashRing(virtual_nodes_per_shard=50)
        for i in range(5):
            ring.add_shard(f"s{i}")
        assert ring.shard_count() == 5
        seen = set()
        for i in range(1000):
            seen.add(ring.get_shard(f"key_{i}"))
        assert seen == {f"s{i}" for i in range(5)}

    def test_remove_shard(self):
        ring = ConsistentHashRing(virtual_nodes_per_shard=50)
        ring.add_shard("s0")
        ring.add_shard("s1")
        ring.remove_shard("s0")
        assert ring.shard_count() == 1
        assert ring.get_shard("any_key") == "s1"

    def test_replication_shards(self):
        ring = ConsistentHashRing(virtual_nodes_per_shard=50)
        for i in range(10):
            ring.add_shard(f"s{i}")
        shards = ring.get_shards("test_key", 3)
        assert len(shards) == 3
        assert len(set(shards)) == 3

    def test_consistent_lookup(self):
        ring = ConsistentHashRing(virtual_nodes_per_shard=100)
        for i in range(3):
            ring.add_shard(f"s{i}")
        shard1 = ring.get_shard("my_key")
        for _ in range(100):
            assert ring.get_shard("my_key") == shard1

    def test_fair_distribution(self):
        ring = ConsistentHashRing(virtual_nodes_per_shard=200)
        for i in range(5):
            ring.add_shard(f"s{i}")
        counts = {f"s{i}": 0 for i in range(5)}
        for i in range(5000):
            shard = ring.get_shard(f"key_{i}")
            counts[shard] += 1
        avg = 1000
        for count in counts.values():
            assert abs(count - avg) < avg * 0.5

    def test_keys_moving_estimate(self):
        ring = ConsistentHashRing(virtual_nodes_per_shard=50)
        for i in range(4):
            ring.add_shard(f"s{i}")
        fraction = ring.keys_moving(added=["s4"])
        assert 0.0 <= fraction <= 1.0


class TestNode:
    def test_basic_operations(self):
        node = Node("n1")
        assert node.put("k", "v1")
        assert node.get("k") == ["v1"]
        assert node.get("missing") is None

    def test_put_appends(self):
        node = Node("n1")
        node.put("k", 1)
        node.put("k", 2)
        assert node.get("k") == [1, 2]

    def test_range_query(self):
        node = Node("n1")
        for i in range(10):
            node.put(f"k_{i}", f"v_{i}")
        results = node.range_query("k_3", "k_6")
        keys = [k for k, _ in results]
        assert keys == [f"k_{i}" for i in range(3, 7)]

    def test_prefix_scan(self):
        node = Node("n1")
        node.put("apple", "fruit")
        node.put("application", "software")
        node.put("apply", "verb")
        node.put("banana", "fruit")
        results = node.prefix_scan("app")
        keys = [k for k, _ in results]
        assert sorted(keys) == ["apple", "application", "apply"]

    def test_batch_put(self):
        node = Node("n1")
        node.batch_put([("a", 1), ("b", 2), ("c", 3)])
        assert node.get("a") == [1]
        assert node.get("b") == [2]
        assert node.get("c") == [3]

    def test_replication(self):
        primary = Node("primary")
        replica = Node("replica")
        primary.add_replica(replica)
        primary.put("shared", "data")
        assert replica.get("shared") == ["data"]

    def test_replication_chain(self):
        n1 = Node("n1")
        n2 = Node("n2")
        n3 = Node("n3")
        n1.add_replica(n2)
        n2.add_replica(n3)
        n1.put("key", "val")
        assert n2.get("key") == ["val"]
        assert n3.get("key") == ["val"]

    def test_unhealthy_replica_skipped(self):
        primary = Node("primary")
        replica = Node("replica")
        replica.set_healthy(False)
        primary.add_replica(replica)
        primary.put("k", "v")
        assert replica.get("k") is None

    def test_remove_operation(self):
        node = Node("n1")
        node.put("k", "v")
        assert node.contains("k")
        node.remove("k")
        assert not node.contains("k")

    def test_get_snapshot(self):
        node = Node("n1")
        node.put("k1", "v1")
        node.put("k2", "v2")
        snap = node.get_snapshot()
        assert snap["key_count"] == 2
        assert "k1" in snap["data"]

    def test_remove_replica(self):
        n1 = Node("n1")
        n2 = Node("n2")
        n1.add_replica(n2)
        assert len(n1.get_replicas()) == 1
        n1.remove_replica(n2)
        assert len(n1.get_replicas()) == 0

    def test_stats(self):
        node = Node("n1")
        node.put("k", "v")
        node.get("k")
        node.get("missing")
        stats = node.get_stats()
        assert stats["puts"] == 1
        assert stats["gets"] == 2


class TestDistributedKVStore:
    def _make_cluster(self, n_shards: int = 3, rf: int = 3) -> DistributedKVStore:
        nodes = [Node(f"node_{i}") for i in range(n_shards)]
        shard_ids = [f"shard_{i}" for i in range(n_shards)]
        store = DistributedKVStore(nodes, shard_ids, replication_factor=rf)
        store.setup_full_replication(rf)
        return store

    def test_put_get_one_shard(self):
        store = self._make_cluster(n_shards=3)
        result = store.put("hello", "world")
        assert result.success
        val = store.get("hello")
        assert val == ["world"]

    def test_put_get_multiple_values(self):
        store = self._make_cluster(n_shards=3)
        store.put("k", "v1")
        store.put("k", "v2")
        store.put("k", "v3")
        assert store.get("k") == ["v1", "v2", "v3"]

    def test_missing_key(self):
        store = self._make_cluster(n_shards=3)
        assert store.get("nonexistent") is None

    def test_consistency_one(self):
        store = self._make_cluster(n_shards=3, rf=3)
        result = store.put("fast", "data", consistency=ConsistencyLevel.ONE)
        assert result.success
        assert result.ack_count >= 1

    def test_consistency_quorum(self):
        store = self._make_cluster(n_shards=3, rf=3)
        result = store.put("safe", "data", consistency=ConsistencyLevel.QUORUM)
        assert result.success
        assert result.ack_count >= 2

    def test_consistency_all(self):
        store = self._make_cluster(n_shards=3, rf=3)
        result = store.put("strict", "data", consistency=ConsistencyLevel.ALL)
        assert result.success
        assert result.ack_count >= 3

    def test_range_query_distributed(self):
        store = self._make_cluster(n_shards=3, rf=3)
        store.put("key_a", "doc1")
        store.put("key_b", "doc2")
        store.put("key_c", "doc3")
        store.put("key_d", "doc4")
        store.put("key_e", "doc5")
        results = store.range_query("key_b", "key_d")
        keys = [k for k, _ in results]
        assert "key_b" in keys
        assert "key_c" in keys
        assert "key_d" in keys

    def test_prefix_scan_distributed(self):
        store = self._make_cluster(n_shards=3, rf=3)
        store.put("doc:1:title", "Title1")
        store.put("doc:1:body", "Body1")
        store.put("doc:2:title", "Title2")
        store.put("meta:1:author", "Author1")
        results = store.prefix_scan("doc:")
        keys = [k for k, _ in results]
        assert len(keys) == 3
        assert all(k.startswith("doc:") for k in keys)

    def test_batch_put(self):
        store = self._make_cluster(n_shards=3, rf=3)
        entries = [("a", 1), ("b", 2), ("c", 3), ("d", 4)]
        result = store.batch_put(entries)
        assert result.success
        assert store.get("a") == [1]
        assert store.get("b") == [2]

    def test_multi_get(self):
        store = self._make_cluster(n_shards=3, rf=3)
        store.put("x", 1)
        store.put("y", 2)
        store.put("z", 3)
        results = store.multi_get(["x", "y", "missing"])
        assert results["x"] == [1]
        assert results["y"] == [2]
        assert results["missing"] is None

    def test_hot_key_detection_and_coalescing(self):
        store = self._make_cluster(n_shards=3, rf=3)
        store.put("hot", "data")

        for _ in range(200):
            store._hot_tracker.record("hot")
        assert store._hot_tracker.is_hot("hot")
        result = store.get("hot")
        assert result == ["data"]

    def test_concurrent_gets(self):
        store = self._make_cluster(n_shards=3, rf=3)
        store.put("shared", "val")

        def read_key(_):
            return store.get("shared")

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_key, i) for i in range(50)]
            results = [f.result() for f in as_completed(futures)]

        assert all(r == ["val"] for r in results)

    def test_cluster_health(self):
        store = self._make_cluster(n_shards=3, rf=3)
        health = store.get_cluster_health()
        assert len(health) == 3
        for info in health.values():
            assert info["healthy"]

    def test_node_failure_handling(self):
        store = self._make_cluster(n_shards=3, rf=3)
        store.put("surviving", "data")

        nodes = list(store._nodes.values())
        nodes[0].set_healthy(False)

        result = store.put("after_failure", "data2", consistency=ConsistencyLevel.ONE)
        assert result.success

        val = store.get("surviving")
        assert val is not None

    def test_write_result_structure(self):
        store = self._make_cluster(n_shards=3, rf=3)
        result = store.put("k", "v", consistency=ConsistencyLevel.ALL)
        assert isinstance(result, WriteResult)
        assert result.success
        assert result.ack_count >= 1

    def test_node_for_key(self):
        store = self._make_cluster(n_shards=5, rf=3)
        node = store.node_for_key("some_key")
        assert node is not None
        same_node = store.node_for_key("some_key")
        assert node == same_node

    def test_add_remove_node(self):
        store = self._make_cluster(n_shards=3, rf=3)
        new_node = Node("node_new")
        store.add_node(new_node, "shard_new")
        assert store.node_count == 4
        store.remove_node("shard_new")
        assert store.node_count == 3

    def test_stats_tracking(self):
        store = self._make_cluster(n_shards=3, rf=3)
        store.put("k1", "v1")
        store.put("k2", "v2")
        store.get("k1")
        stats = store.get_stats()
        assert stats["puts"] >= 2
        assert stats["gets"] >= 1


class TestJoinExecutor:
    def _make_store(self) -> DistributedKVStore:
        nodes = [Node(f"n{i}") for i in range(3)]
        shards = [f"s{i}" for i in range(3)]
        store = DistributedKVStore(nodes, shards, replication_factor=3)
        store.setup_full_replication(3)
        return store

    def test_hash_join(self):
        store = self._make_store()
        store.put("term:python", "doc_1")
        store.put("term:python", "doc_2")
        store.put("term:rust", "doc_1")
        store.put("term:rust", "doc_3")
        store.put("doc:doc_1", {"title": "Python Guide"})
        store.put("doc:doc_1", {"author": "Alice"})
        store.put("doc:doc_2", {"title": "Advanced Python"})
        store.put("doc:doc_3", {"title": "Rust Book"})

        joiner = JoinExecutor(store)
        results = joiner.hash_join(["term:python", "term:rust"], right_prefix="doc:")

        doc_ids_for_python = set()
        doc_ids_for_rust = set()
        metadata_for_python = []
        metadata_for_rust = []

        for key, docs, meta in results:
            if key == "term:python":
                doc_ids_for_python = set(docs)
                metadata_for_python = meta
            elif key == "term:rust":
                doc_ids_for_rust = set(docs)
                metadata_for_rust = meta

        assert doc_ids_for_python == {"doc_1", "doc_2"}
        assert doc_ids_for_rust == {"doc_1", "doc_3"}
        assert len(metadata_for_python) >= 2
        assert len(metadata_for_rust) >= 1

    def test_nested_loop_join(self):
        store = self._make_store()
        store.put("user:1", "order_10")
        store.put("user:1", "order_11")
        store.put("user:2", "order_20")
        store.put("order:order_10", {"total": 100})
        store.put("order:order_11", {"total": 200})
        store.put("order:order_20", {"total": 50})

        joiner = JoinExecutor(store)
        results = joiner.nested_loop_join(["user:1", "user:2"], right_prefix="order:")

        assert len(results) >= 3
        totals = []
        for _, right_val in results:
            if isinstance(right_val, list):
                for item in right_val:
                    if isinstance(item, dict) and "total" in item:
                        totals.append(item["total"])
            elif isinstance(right_val, dict) and "total" in right_val:
                totals.append(right_val["total"])
        assert sorted(totals) == [50, 100, 200]

    def test_index_merge_join(self):
        store = self._make_store()
        store.put("cat:python", "doc_1")
        store.put("cat:python", "doc_2")
        store.put("cat:rust", "doc_3")
        store.put("doc:doc_1", "Python Basics")
        store.put("doc:doc_2", "Python Advanced")
        store.put("doc:doc_3", "Rust Programming")

        joiner = JoinExecutor(store)
        results = joiner.index_merge_join("cat:", "doc:")

        assert len(results) >= 2


class TestHotKeyTracker:
    def test_hot_detection(self):
        tracker = HotKeyTracker(threshold=10, window_sec=60)
        for _ in range(15):
            tracker.record("hot_key")
        assert tracker.is_hot("hot_key")
        assert not tracker.is_hot("cold_key")

    def test_get_hot_keys(self):
        tracker = HotKeyTracker(threshold=5, window_sec=60)
        for _ in range(8):
            tracker.record("k1")
        for _ in range(8):
            tracker.record("k2")
        hot = tracker.get_hot_keys()
        assert "k1" in hot
        assert "k2" in hot

    def test_window_pruning(self):
        tracker = HotKeyTracker(threshold=5, window_sec=0.1)
        for _ in range(10):
            tracker.record("k")
        assert tracker.is_hot("k")
        time.sleep(0.2)
        assert not tracker.is_hot("k")


class TestEndToEndSearchEngine:
    def test_index_and_query_documents(self):
        nodes = [Node(f"n{i}") for i in range(5)]
        shards = [f"s{i}" for i in range(5)]
        store = DistributedKVStore(nodes, shards, replication_factor=3)
        store.setup_full_replication(3)

        documents = {
            "doc_1": "python is a programming language",
            "doc_2": "rust is a systems language",
            "doc_3": "python and rust are both great",
        }

        for doc_id, text in documents.items():
            store.put(f"doc:{doc_id}", {"text": text})
            for word in text.split():
                store.put(f"idx:{word}", doc_id)

        python_docs = store.get("idx:python")
        assert python_docs is not None
        assert "doc_1" in python_docs
        assert "doc_3" in python_docs

        rust_docs = store.get("idx:rust")
        assert rust_docs is not None
        assert "doc_2" in rust_docs
        assert "doc_3" in rust_docs

        results = store.prefix_scan("idx:")
        assert len(results) > 0

    def test_bulk_indexing_performance(self):
        nodes = [Node(f"n{i}") for i in range(3)]
        shards = [f"s{i}" for i in range(3)]
        store = DistributedKVStore(nodes, shards, replication_factor=3)
        store.setup_full_replication(3)

        entries = []
        for i in range(1000):
            entries.append((f"key_{i:06d}", f"value_{i}"))

        start = time.time()
        result = store.batch_put(entries, consistency=ConsistencyLevel.ONE)
        elapsed = time.time() - start

        assert result.success
        assert elapsed < 5.0

        for i in range(0, 1000, 100):
            assert store.get(f"key_{i:06d}") is not None

    def test_hot_key_replication(self):
        nodes = [Node(f"n{i}") for i in range(3)]
        shards = [f"s{i}" for i in range(3)]
        store = DistributedKVStore(nodes, shards, replication_factor=3, virtual_nodes=200)
        store.setup_full_replication(3)

        store.put("viral_content", "data")

        for _ in range(200):
            store._hot_tracker.record("viral_content")

        assert store._hot_tracker.is_hot("viral_content")

        results = []
        for _ in range(20):
            results.append(store.get("viral_content"))
        assert all(r == ["data"] for r in results)

    def test_consistency_during_partition(self):
        nodes = [Node(f"n{i}") for i in range(5)]
        shards = [f"s{i}" for i in range(5)]
        store = DistributedKVStore(nodes, shards, replication_factor=3)
        store.setup_full_replication(3)

        store.put("critical", "value_A", consistency=ConsistencyLevel.ALL)

        for n in list(store._nodes.values())[:2]:
            n.set_healthy(False)

        result = store.put("critical", "value_B", consistency=ConsistencyLevel.ONE)
        assert result.success

        read_val = store.get("critical", consistency=ConsistencyLevel.ONE)
        assert read_val is not None

    def test_distributed_join_with_search_results(self):
        nodes = [Node(f"n{i}") for i in range(3)]
        shards = [f"s{i}" for i in range(3)]
        store = DistributedKVStore(nodes, shards, replication_factor=3)
        store.setup_full_replication(3)

        keywords = ["python", "rust", "javascript"]
        docs = {
            "d1": "python guide",
            "d2": "rust book",
            "d3": "python and rust",
        }

        for doc_id, text in docs.items():
            store.put(f"doc:{doc_id}", {"content": text, "score": len(text)})
            for word in text.split():
                store.put(f"kw:{word}", doc_id)

        joiner = JoinExecutor(store)
        results = joiner.hash_join(["kw:python", "kw:rust"], right_prefix="doc:")

        for key, docs_list, metadata in results:
            assert len(docs_list) > 0
            if key == "kw:python":
                assert "d1" in docs_list or "d3" in docs_list
            if key == "kw:rust":
                assert "d2" in docs_list or "d3" in docs_list
