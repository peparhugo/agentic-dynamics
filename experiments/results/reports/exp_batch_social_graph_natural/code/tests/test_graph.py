from __future__ import annotations

import pytest
from social_graph.graph import SocialGraph
from social_graph.types import User


class TestSocialGraph:
    def test_add_node(self) -> None:
        g = SocialGraph()
        nid = g.add_node(node_id=1)
        assert nid == 1
        assert g.has_node(1)
        assert g.node_count == 1

    def test_add_node_with_user(self) -> None:
        g = SocialGraph()
        u = User(user_id=42, name="Test")
        nid = g.add_node(user=u)
        assert nid == 42
        user = g.get_user(42)
        assert user is not None
        assert user.name == "Test"

    def test_add_edge_undirected(self) -> None:
        g = SocialGraph(directed=False)
        g.add_edge(1, 2)
        assert g.has_node(1)
        assert g.has_node(2)
        assert g.has_edge(1, 2)
        assert g.has_edge(2, 1)
        assert g.edge_count == 1

    def test_add_edge_directed(self) -> None:
        g = SocialGraph(directed=True)
        g.add_edge(1, 2)
        assert g.has_edge(1, 2)
        assert not g.has_edge(2, 1)
        assert g.edge_count == 1

    def test_self_loop_ignored(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 1)
        assert g.edge_count == 0
        assert g.get_neighbors(1) == []

    def test_duplicate_edge_ignored(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(1, 2)
        g.add_edge(2, 1)
        assert g.edge_count == 1

    def test_remove_edge(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(1, 3)
        g.remove_edge(1, 2)
        assert not g.has_edge(1, 2)
        assert g.has_edge(1, 3)
        assert g.edge_count == 1

    def test_remove_nonexistent_edge(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.remove_edge(1, 3)
        assert g.edge_count == 1

    def test_remove_node(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(1, 3)
        g.remove_node(1)
        assert not g.has_node(1)
        assert g.has_node(2)
        assert g.has_node(3)
        assert g.edge_count == 0

    def test_get_neighbors(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(1, 3)
        g.add_edge(1, 4)
        neigh = g.get_neighbors(1)
        assert set(neigh) == {2, 3, 4}

    def test_get_neighbors_nonexistent(self) -> None:
        g = SocialGraph()
        assert g.get_neighbors(999) == []

    def test_get_degree(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(1, 3)
        assert g.get_degree(1) == 2
        assert g.get_degree(2) == 1
        assert g.get_degree(999) == 0

    def test_has_edge(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        assert g.has_edge(1, 2)
        assert g.has_edge(2, 1)
        assert not g.has_edge(1, 3)

    def test_edges(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(2, 3)
        g.add_edge(3, 1)
        edges = g.edges()
        assert len(edges) == 3
        assert (1, 2) in edges or (2, 1) in edges

    def test_nodes(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(2, 3)
        nodes = g.nodes
        assert set(nodes) == {1, 2, 3}

    def test_subgraph(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(2, 3)
        g.add_edge(3, 4)
        g.add_edge(4, 1)
        sub = g.subgraph({1, 2, 3})
        assert sub.node_count == 3
        assert sub.edge_count == 2
        assert sub.has_edge(1, 2)
        assert sub.has_edge(2, 3)
        assert not sub.has_edge(3, 4)

    def test_contains(self) -> None:
        g = SocialGraph()
        g.add_node(node_id=1)
        assert 1 in g
        assert 2 not in g

    def test_len(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(2, 3)
        assert len(g) == 3

    def test_clear(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(2, 3)
        g.clear()
        assert g.node_count == 0
        assert g.edge_count == 0
        assert g.nodes == []

    def test_large_graph(self) -> None:
        g = SocialGraph()
        n = 200
        for i in range(n - 1):
            g.add_edge(i, i + 1)
        assert g.node_count == n
        assert g.edge_count == n - 1
        path = []
        cur = 0
        while cur < n:
            path.append(cur)
            neighbors = [nb for nb in g.get_neighbors(cur) if nb > cur]
            if not neighbors:
                break
            cur = neighbors[0]
        assert len(path) == n

    def test_star_graph(self) -> None:
        g = SocialGraph()
        center = 0
        for i in range(1, 11):
            g.add_edge(center, i)
        assert g.get_degree(center) == 10
        for i in range(1, 11):
            assert g.get_degree(i) == 1
