from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, Iterator, Optional


class LRUCache:
    def __init__(self, capacity: int = 1024) -> None:
        self._capacity = max(1, capacity)
        self._store: OrderedDict = OrderedDict()
        self._hits: int = 0
        self._misses: int = 0

    def get(self, key: Any, default: Any = None) -> Any:
        if key in self._store:
            self._store.move_to_end(key)
            self._hits += 1
            return self._store[key]
        self._misses += 1
        return default

    def put(self, key: Any, value: Any) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = value
        if len(self._store) > self._capacity:
            self._store.popitem(last=False)

    def remove(self, key: Any) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()
        self._hits = 0
        self._misses = 0

    def __contains__(self, key: Any) -> bool:
        return key in self._store

    def __len__(self) -> int:
        return len(self._store)

    def __iter__(self) -> Iterator:
        return iter(self._store)

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0


class CacheLayer:
    def __init__(self, graph: Any, cache: Optional[LRUCache] = None, capacity: int = 1024) -> None:
        self._graph = graph
        self._cache = cache if cache is not None else LRUCache(capacity)

    def get_neighbors(self, node_id: int) -> list[int]:
        cached = self._cache.get(node_id)
        if cached is not None:
            return cached
        neighbors = self._graph.get_neighbors(node_id)
        self._cache.put(node_id, neighbors)
        return neighbors

    def invalidate(self, node_id: int) -> None:
        self._cache.remove(node_id)

    def warm(self, node_ids: list[int]) -> None:
        for nid in node_ids:
            if nid not in self._cache:
                self._cache.put(nid, self._graph.get_neighbors(nid))

    @property
    def cache(self) -> LRUCache:
        return self._cache

    def clear(self) -> None:
        self._cache.clear()
