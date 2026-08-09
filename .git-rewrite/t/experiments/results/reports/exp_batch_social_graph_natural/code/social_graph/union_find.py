from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple


class UnionFind:
    def __init__(self) -> None:
        self._parent: Dict[int, int] = {}
        self._rank: Dict[int, int] = {}

    def make_set(self, x: int) -> None:
        if x not in self._parent:
            self._parent[x] = x
            self._rank[x] = 0

    def find(self, x: int) -> int:
        if x not in self._parent:
            self.make_set(x)
        if self._parent[x] != x:
            self._parent[x] = self.find(self._parent[x])
        return self._parent[x]

    def union(self, x: int, y: int) -> None:
        rx = self.find(x)
        ry = self.find(y)
        if rx == ry:
            return
        if self._rank[rx] < self._rank[ry]:
            self._parent[rx] = ry
        elif self._rank[rx] > self._rank[ry]:
            self._parent[ry] = rx
        else:
            self._parent[ry] = rx
            self._rank[rx] += 1

    def connected(self, x: int, y: int) -> bool:
        return self.find(x) == self.find(y)

    def components(self) -> Dict[int, List[int]]:
        groups: Dict[int, List[int]] = {}
        for node in self._parent:
            root = self.find(node)
            groups.setdefault(root, []).append(node)
        return groups

    def component_size(self, x: int) -> int:
        root = self.find(x)
        return sum(1 for node in self._parent if self.find(node) == root)

    def num_components(self) -> int:
        return len({self.find(n) for n in self._parent})

    def __len__(self) -> int:
        return len(self._parent)

    def __contains__(self, x: int) -> bool:
        return x in self._parent
