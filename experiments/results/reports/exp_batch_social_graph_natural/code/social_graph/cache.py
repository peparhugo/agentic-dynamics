"""Read-path caching layer.

The graph is read-heavy: users constantly open their connections list, degree
counts, and friend suggestions. We front each shard with an LRU cache holding
hot adjacency sets so those reads never touch the (remote) shard store.

For correctness under heavy writes the cache is best-effort: entries are
invalidated on mutation via a version tag, so a stale read is possible only
within the tiny window before a write flushes — an acceptable trade-off for a
social graph (eventual consistency), and the exact behaviour is exposed for
tests via ``invalidate``.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Callable, Hashable, Optional


class LRUCache:
    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._data: OrderedDict = OrderedDict()

    def get(self, key: Hashable) -> Optional[Any]:
        if key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def put(self, key: Hashable, value: Any) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = value
        if len(self._data) > self.capacity:
            self._data.popitem(last=False)

    def has(self, key: Hashable) -> bool:
        return key in self._data

    def invalidate(self, key: Hashable) -> None:
        self._data.pop(key, None)

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)


class CachedGraph:
    """Decorates a SocialGraph with a read-through LRU cache."""

    def __init__(self, graph, cache_capacity: int = 10_000) -> None:
        self._graph = graph
        self._cache = LRUCache(cache_capacity)
        self._version = 0

    def _key(self, prefix: str, user_id: str) -> tuple:
        return (prefix, user_id)

    def connections(self, user_id: str):
        key = self._key("conn", user_id)
        hit = self._cache.get(key)
        if hit is None:
            hit = frozenset(self._graph.connections(user_id))
            self._cache.put(key, hit)
        return hit

    def degree(self, user_id: str) -> int:
        key = self._key("deg", user_id)
        hit = self._cache.get(key)
        if hit is None:
            hit = self._graph.degree(user_id)
            self._cache.put(key, hit)
        return hit

    def add_connection(self, src: str, dst: str, weight: float = 1.0) -> None:
        self._graph.add_connection(src, dst, weight)
        self._invalidate_user(src)
        self._invalidate_user(dst)

    def remove_connection(self, src: str, dst: str) -> None:
        self._graph.remove_connection(src, dst)
        self._invalidate_user(src)
        self._invalidate_user(dst)

    def _invalidate_user(self, user_id: str) -> None:
        self._cache.invalidate(self._key("conn", user_id))
        self._cache.invalidate(self._key("deg", user_id))
        self._version += 1

    @property
    def graph(self):
        return self._graph

    def cache_stats(self) -> dict:
        return {"size": len(self._cache), "version": self._version}
