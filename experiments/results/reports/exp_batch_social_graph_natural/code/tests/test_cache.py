from __future__ import annotations

import pytest
from social_graph.cache import LRUCache, CacheLayer
from social_graph.graph import SocialGraph


class TestLRUCache:
    def test_basic_operations(self) -> None:
        c = LRUCache(capacity=2)
        c.put("a", 1)
        c.put("b", 2)
        assert c.get("a") == 1
        assert c.get("b") == 2

    def test_eviction(self) -> None:
        c = LRUCache(capacity=2)
        c.put("a", 1)
        c.put("b", 2)
        c.get("a")
        c.put("c", 3)
        assert "a" in c
        assert "b" not in c
        assert c.get("b") is None

    def test_get_nonexistent(self) -> None:
        c = LRUCache(capacity=2)
        assert c.get("x") is None
        assert c.get("x", "default") == "default"

    def test_remove(self) -> None:
        c = LRUCache(capacity=2)
        c.put("a", 1)
        c.remove("a")
        assert "a" not in c

    def test_clear(self) -> None:
        c = LRUCache(capacity=2)
        c.put("a", 1)
        c.put("b", 2)
        c.clear()
        assert len(c) == 0
        assert c.hits == 0
        assert c.misses == 0

    def test_len(self) -> None:
        c = LRUCache(capacity=3)
        c.put("a", 1)
        c.put("b", 2)
        assert len(c) == 2

    def test_contains(self) -> None:
        c = LRUCache(capacity=2)
        c.put("a", 1)
        assert "a" in c
        assert "b" not in c

    def test_iteration(self) -> None:
        c = LRUCache(capacity=3)
        c.put("a", 1)
        c.put("b", 2)
        c.put("c", 3)
        assert set(iter(c)) == {"a", "b", "c"}

    def test_hit_rate(self) -> None:
        c = LRUCache(capacity=3)
        c.put("a", 1)
        c.get("a")
        c.get("a")
        c.get("b")
        assert c.hits == 2
        assert c.misses == 1
        assert c.hit_rate == 2.0 / 3.0

    def test_capacity_property(self) -> None:
        c = LRUCache(capacity=42)
        assert c.capacity == 42


class TestCacheLayer:
    def test_get_neighbors_caches(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(1, 3)
        cl = CacheLayer(g, capacity=10)
        assert len(cl.cache) == 0
        neigh = cl.get_neighbors(1)
        assert set(neigh) == {2, 3}
        assert len(cl.cache) == 1
        neigh2 = cl.get_neighbors(1)
        assert set(neigh2) == {2, 3}

    def test_invalidate(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        cl = CacheLayer(g, capacity=10)
        cl.get_neighbors(1)
        assert 1 in cl.cache
        cl.invalidate(1)
        assert 1 not in cl.cache

    def test_warm(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(2, 3)
        cl = CacheLayer(g, capacity=10)
        cl.warm([1, 2, 3])
        assert len(cl.cache) == 3
        assert 1 in cl.cache
        assert 2 in cl.cache
        assert 3 in cl.cache

    def test_clear(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        cl = CacheLayer(g, capacity=10)
        cl.get_neighbors(1)
        cl.clear()
        assert len(cl.cache) == 0
