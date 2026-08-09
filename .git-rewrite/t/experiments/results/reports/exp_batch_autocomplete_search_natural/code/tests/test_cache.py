import time
import pytest
from autocomplete.cache import TTLCache


class TestTTLCache:
    def test_set_and_get(self):
        cache = TTLCache()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing_key(self):
        cache = TTLCache()
        assert cache.get("missing") is None

    def test_ttl_expiry(self):
        cache = TTLCache(ttl=0.01)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        time.sleep(0.02)
        assert cache.get("key1") is None

    def test_custom_ttl(self):
        cache = TTLCache(ttl=10)
        cache.set("key1", "value1", ttl=0.01)
        assert cache.get("key1") == "value1"
        time.sleep(0.02)
        assert cache.get("key1") is None

    def test_max_size_eviction(self):
        cache = TTLCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_lru_behavior(self):
        cache = TTLCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.get("a")
        cache.set("d", 4)
        assert cache.get("a") == 1
        assert cache.get("b") is None
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_delete(self):
        cache = TTLCache()
        cache.set("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_clear(self):
        cache = TTLCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_size(self):
        cache = TTLCache()
        assert cache.size() == 0
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.size() == 2

    def test_keys(self):
        cache = TTLCache()
        cache.set("a", 1)
        cache.set("b", 2)
        keys = cache.keys()
        assert "a" in keys
        assert "b" in keys
