from __future__ import annotations

import pytest
from social_graph.graph import SocialGraph
from social_graph.query import QueryEngine


class TestQueryEngineFriends:
    def make_graph(self) -> tuple[SocialGraph, QueryEngine]:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(1, 3)
        g.add_edge(2, 4)
        g.add_edge(3, 4)
        g.add_edge(4, 5)
        g.add_edge(5, 6)
        return g, QueryEngine(g)

    def test_friends_of_friends(self) -> None:
        g, qe = self.make_graph()
        fof = qe.friends_of_friends(1)
        assert fof == {4}

    def test_friends_of_friends_no_indirect(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(2, 3)
        qe = QueryEngine(g)
        fof = qe.friends_of_friends(2)
        assert fof == set()

    def test_mutual_friends(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(1, 3)
        g.add_edge(1, 4)
        g.add_edge(2, 3)
        g.add_edge(2, 4)
        qe = QueryEngine(g)
        mutual = qe.mutual_friends(1, 2)
        assert mutual == {3, 4}

    def test_mutual_friends_none(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(3, 4)
        qe = QueryEngine(g)
        mutual = qe.mutual_friends(1, 3)
        assert mutual == set()

    def test_are_connected(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        qe = QueryEngine(g)
        assert qe.are_connected(1, 2)
        assert qe.are_connected(2, 1)
        assert not qe.are_connected(1, 3)

    def test_shortest_path_simple(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(2, 3)
        g.add_edge(3, 4)
        qe = QueryEngine(g)
        path = qe.shortest_path(1, 4)
        assert path == [1, 2, 3, 4]

    def test_shortest_path_same_node(self) -> None:
        g = SocialGraph()
        g.add_node(node_id=1)
        qe = QueryEngine(g)
        path = qe.shortest_path(1, 1)
        assert path == [1]

    def test_shortest_path_unreachable(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(3, 4)
        qe = QueryEngine(g)
        path = qe.shortest_path(1, 3)
        assert path == []

    def test_shortest_path_nonexistent(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        qe = QueryEngine(g)
        assert qe.shortest_path(1, 999) == []
        assert qe.shortest_path(999, 1) == []

    def test_shortest_path_length(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(2, 3)
        qe = QueryEngine(g)
        assert qe.shortest_path_length(1, 3) == 2
        assert qe.shortest_path_length(1, 1) == 0
        assert qe.shortest_path_length(1, 999) == -1

    def test_shortest_path_bidirectional(self) -> None:
        g = SocialGraph()
        n = 10
        for i in range(n - 1):
            g.add_edge(i, i + 1)
        qe = QueryEngine(g)
        path = qe.shortest_path(0, n - 1)
        assert path == list(range(n))
        assert len(path) == n


class TestQueryEngineSuggestions:
    def make_graph(self) -> tuple[SocialGraph, QueryEngine]:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(1, 3)
        g.add_edge(2, 4)
        g.add_edge(3, 4)
        g.add_edge(2, 5)
        g.add_edge(3, 5)
        g.add_edge(4, 6)
        g.add_edge(5, 6)
        return g, QueryEngine(g)

    def test_suggest_friends_basic(self) -> None:
        g, qe = self.make_graph()
        suggestions = qe.suggest_friends(1, limit=5)
        candidates = {c for c, _ in suggestions}
        assert 4 in candidates
        assert 5 in candidates
        assert 1 not in candidates
        assert 2 not in candidates
        assert 3 not in candidates

    def test_suggest_friends_limit(self) -> None:
        g = SocialGraph()
        g.add_edge(0, 1)
        g.add_edge(0, 2)
        g.add_edge(0, 3)
        for i in range(1, 4):
            for j in range(10, 20):
                g.add_edge(i, j)
        qe = QueryEngine(g)
        s = qe.suggest_friends(0, limit=3)
        assert len(s) <= 3

    def test_suggest_friends_ranked(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(1, 3)
        g.add_edge(2, 10)
        g.add_edge(2, 11)
        g.add_edge(3, 10)
        g.add_edge(3, 11)
        g.add_edge(3, 12)
        qe = QueryEngine(g)
        s = qe.suggest_friends(1)
        assert s  # should have suggestions
        counts = dict(s)
        assert counts[10] == 2
        assert counts[11] == 2

    def test_suggest_friends_no_suggestions(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        qe = QueryEngine(g)
        s = qe.suggest_friends(1, limit=5)
        assert s == []

    def test_degree_centrality(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(1, 3)
        g.add_edge(1, 4)
        qe = QueryEngine(g)
        cent = qe.degree_centrality()
        assert cent[1] == 1.0
        assert cent[2] == 1.0 / 3.0

    def test_degree_centrality_empty(self) -> None:
        g = SocialGraph()
        qe = QueryEngine(g)
        assert qe.degree_centrality() == {}

    def test_jaccard_similarity(self) -> None:
        g = SocialGraph()
        g.add_edge(1, 2)
        g.add_edge(1, 3)
        g.add_edge(1, 4)
        g.add_edge(2, 3)
        g.add_edge(2, 4)
        g.add_edge(2, 5)
        qe = QueryEngine(g)
        js = qe.jaccard_similarity(1, 2)
        assert js == 2.0 / 4.0  # {3,4} / {3,4,5,1?} no wait: {3,4} / {1,2,3,4,5} = 2/5? Let me think
        # neigh(1) = {2,3,4}, neigh(2) = {1,3,4,5}
        # intersection = {3,4} = 2, union = {1,2,3,4,5} = 5
        # jaccard = 2/5
        assert js == pytest.approx(2.0 / 5.0)

    def test_jaccard_zero(self) -> None:
        g = SocialGraph()
        g.add_node(node_id=1)
        g.add_node(node_id=2)
        qe = QueryEngine(g)
        assert qe.jaccard_similarity(1, 2) == 0.0
