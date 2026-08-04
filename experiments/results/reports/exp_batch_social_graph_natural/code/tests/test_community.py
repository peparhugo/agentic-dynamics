from __future__ import annotations

import pytest
from social_graph.graph import SocialGraph
from social_graph.community import CommunityDetector


class TestCommunityDetector:
    def make_simple_graph(self) -> tuple[SocialGraph, CommunityDetector]:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(2, 3)
        g.add_edge(4, 5)
        g.add_edge(5, 6)
        return g, CommunityDetector(g)

    def test_connected_components_basic(self) -> None:
        g, cd = self.make_simple_graph()
        comps = cd.connected_components()
        assert len(comps) == 2
        sizes = sorted([len(v) for v in comps.values()])
        assert sizes == [3, 3]

    def test_connected_components_empty(self) -> None:
        g = SocialGraph()
        cd = CommunityDetector(g)
        comps = cd.connected_components()
        assert comps == {}

    def test_connected_components_single(self) -> None:
        g = SocialGraph()
        g.add_node(node_id=1)
        cd = CommunityDetector(g)
        comps = cd.connected_components()
        assert len(comps) == 1
        assert list(comps.values())[0] == [1]

    def test_label_propagation(self) -> None:
        g, cd = self.make_simple_graph()
        labels = cd.label_propagation()
        assert len(set(labels.values())) == 2
        assert labels[1] == labels[2] == labels[3]
        assert labels[4] == labels[5] == labels[6]
        assert labels[1] != labels[4]

    def test_label_propagation_empty(self) -> None:
        g = SocialGraph()
        cd = CommunityDetector(g)
        labels = cd.label_propagation()
        assert labels == {}

    def test_communities_connected_components(self) -> None:
        g, cd = self.make_simple_graph()
        comps = cd.communities(method="connected_components")
        assert len(comps) == 2

    def test_communities_label_propagation(self) -> None:
        g, cd = self.make_simple_graph()
        comps = cd.communities(method="label_propagation")
        assert len(comps) == 2

    def test_communities_invalid_method(self) -> None:
        g = SocialGraph()
        cd = CommunityDetector(g)
        with pytest.raises(ValueError):
            cd.communities(method="nonexistent")

    def test_modularity_accurate_clusters(self) -> None:
        g = SocialGraph()
        for i in range(3):
            for j in range(3):
                if i != j:
                    g.add_edge(i, j)
        for i in range(3, 6):
            for j in range(3, 6):
                if i != j:
                    g.add_edge(i, j)
        g.add_edge(2, 3)
        cd = CommunityDetector(g)
        comps = cd.connected_components()
        q = cd.modularity(comps)
        assert -1.0 <= q <= 1.0
        assert q > 0.0

    def test_modularity_empty(self) -> None:
        g = SocialGraph()
        cd = CommunityDetector(g)
        assert cd.modularity({}) == 0.0

    def test_community_sizes(self) -> None:
        g, cd = self.make_simple_graph()
        comps = cd.connected_components()
        sizes = cd.community_sizes(comps)
        assert set(sizes.values()) == {3, 3}

    def test_giant_component_fraction(self) -> None:
        g, cd = self.make_simple_graph()
        frac = cd.giant_component_fraction()
        assert frac == 0.5

    def test_giant_component_fraction_empty(self) -> None:
        g = SocialGraph()
        cd = CommunityDetector(g)
        assert cd.giant_component_fraction() == 0.0

    def test_num_connected_components(self) -> None:
        g, cd = self.make_simple_graph()
        assert cd.num_connected_components() == 2

    def test_triangle_community(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(2, 3)
        g.add_edge(3, 1)
        cd = CommunityDetector(g)
        comps = cd.connected_components()
        assert len(comps) == 1
        assert cd.num_connected_components() == 1

    def test_modularity_accurate_clusters_high(self) -> None:
        g = SocialGraph()
        cluster1 = list(range(5))
        cluster2 = list(range(5, 10))
        for i in cluster1:
            for j in cluster1:
                if i < j:
                    g.add_edge(i, j)
        for i in cluster2:
            for j in cluster2:
                if i < j:
                    g.add_edge(i, j)
        g.add_edge(cluster1[-1], cluster2[0])
        cd = CommunityDetector(g)
        comps = cd.connected_components()
        q = cd.modularity(comps)
        assert -1.0 <= q <= 1.0
