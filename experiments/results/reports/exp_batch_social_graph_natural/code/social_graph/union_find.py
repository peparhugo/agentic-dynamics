"""Disjoint-set (union-find) structure used for community detection.

Weighted union by rank/size with path halving keeps the amortized cost of a
single operation at the inverse-Ackermann bound, which is effectively O(1)
even at billion-node scale.
"""

from __future__ import annotations

from typing import Dict, Hashable, Iterable, List, Set


class UnionFind:
    def __init__(self, elements: Iterable[Hashable] = ()) -> None:
        self._parent: Dict[Hashable, Hashable] = {}
        self._size: Dict[Hashable, int] = {}
        for e in elements:
            self.add(e)

    def add(self, x: Hashable) -> None:
        if x not in self._parent:
            self._parent[x] = x
            self._size[x] = 1

    def find(self, x: Hashable) -> Hashable:
        # Path halving: no recursion, so no stack overflow on deep trees.
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[x] != x:
            nxt = self._parent[x]
            self._parent[x] = root
            x = nxt
        return root

    def union(self, a: Hashable, b: Hashable) -> None:
        self.add(a)
        self.add(b)
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        # Attach the smaller component to the larger to bound tree depth.
        if self._size[ra] < self._size[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        self._size[ra] += self._size[rb]

    def connected(self, a: Hashable, b: Hashable) -> bool:
        if a not in self._parent or b not in self._parent:
            return False
        return self.find(a) == self.find(b)

    def component_size(self, x: Hashable) -> int:
        if x not in self._parent:
            return 0
        return self._size[self.find(x)]

    def components(self) -> List[Set[Hashable]]:
        groups: Dict[Hashable, Set[Hashable]] = {}
        for x in self._parent:
            groups.setdefault(self.find(x), set()).add(x)
        return list(groups.values())

    def num_components(self) -> int:
        return sum(1 for x in self._parent if self._parent[x] == x)
