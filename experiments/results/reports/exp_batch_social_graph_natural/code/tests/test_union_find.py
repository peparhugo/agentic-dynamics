from __future__ import annotations

import pytest
from social_graph.union_find import UnionFind


class TestUnionFind:
    def test_basic_operations(self) -> None:
        uf = UnionFind()
        uf.make_set(1)
        uf.make_set(2)
        assert uf.find(1) != uf.find(2)
        uf.union(1, 2)
        assert uf.find(1) == uf.find(2)
        assert uf.connected(1, 2)

    def test_transitive_union(self) -> None:
        uf = UnionFind()
        uf.union(1, 2)
        uf.union(2, 3)
        assert uf.connected(1, 3)
        assert uf.connected(2, 3)

    def test_union_idempotent(self) -> None:
        uf = UnionFind()
        uf.union(1, 2)
        root_before = uf.find(1)
        uf.union(1, 2)
        assert uf.find(1) == root_before

    def test_components(self) -> None:
        uf = UnionFind()
        uf.union(1, 2)
        uf.union(3, 4)
        uf.union(5, 6)
        uf.union(2, 3)

        comps = uf.components()
        assert len(comps) == 2
        sizes = sorted([len(v) for v in comps.values()])
        assert sizes == [2, 4]

    def test_find_auto_makeset(self) -> None:
        uf = UnionFind()
        root = uf.find(10)
        assert root == 10
        assert 10 in uf

    def test_component_size(self) -> None:
        uf = UnionFind()
        uf.union(1, 2)
        uf.union(2, 3)
        assert uf.component_size(1) == 3
        assert uf.component_size(4) == 1

    def test_num_components(self) -> None:
        uf = UnionFind()
        uf.union(1, 2)
        uf.union(3, 4)
        uf.make_set(5)
        assert uf.num_components() == 3

    def test_not_connected(self) -> None:
        uf = UnionFind()
        uf.union(1, 2)
        uf.make_set(3)
        assert not uf.connected(1, 3)

    def test_empty(self) -> None:
        uf = UnionFind()
        assert len(uf) == 0
        assert uf.num_components() == 0

    def test_path_compression(self) -> None:
        uf = UnionFind()
        uf.union(1, 2)
        uf.union(2, 3)
        uf.union(3, 4)
        uf.union(4, 5)
        root = uf.find(1)
        for i in range(1, 6):
            assert uf.find(i) == root
