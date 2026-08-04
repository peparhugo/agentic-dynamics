from __future__ import annotations

import heapq
from collections import defaultdict, deque
from typing import Dict, Iterator, List, Optional, Set, Tuple, Union

from social_graph.types import NodeID, Edge
from social_graph.graph import SocialGraph
from social_graph.shard import ShardedGraph


GraphLike = Union[SocialGraph, ShardedGraph]


class QueryEngine:
    def __init__(self, graph: GraphLike) -> None:
        self._graph = graph

    def friends_of_friends(self, node_id: NodeID) -> Set[NodeID]:
        direct = set(self._graph.get_neighbors(node_id))
        result: Set[NodeID] = set()
        for friend in direct:
            for fof in self._graph.get_neighbors(friend):
                if fof != node_id and fof not in direct:
                    result.add(fof)
        return result

    def mutual_friends(self, a: NodeID, b: NodeID) -> Set[NodeID]:
        neigh_a = set(self._graph.get_neighbors(a))
        neigh_b = set(self._graph.get_neighbors(b))
        return neigh_a & neigh_b

    def are_connected(self, a: NodeID, b: NodeID) -> bool:
        return b in set(self._graph.get_neighbors(a))

    def shortest_path(self, start: NodeID, end: NodeID) -> List[NodeID]:
        if start == end:
            return [start]
        if start not in self._graph or end not in self._graph:
            return []

        f_visited: Dict[NodeID, Optional[NodeID]] = {start: None}
        b_visited: Dict[NodeID, Optional[NodeID]] = {end: None}
        f_queue = deque([start])
        b_queue = deque([end])
        f_dist: Dict[NodeID, int] = {start: 0}
        b_dist: Dict[NodeID, int] = {end: 0}
        meeting_node: Optional[NodeID] = None

        while f_queue and b_queue:
            for queue, visited, other_visited, dist, other_dist in [
                (f_queue, f_visited, b_visited, f_dist, b_dist),
                (b_queue, b_visited, f_visited, b_dist, f_dist),
            ]:
                if not queue:
                    continue
                current = queue.popleft()
                if current in other_visited:
                    meeting_node = current
                    break

                for neighbor in self._graph.get_neighbors(current):
                    if neighbor not in visited:
                        visited[neighbor] = current
                        dist[neighbor] = dist[current] + 1
                        queue.append(neighbor)
                        if neighbor in other_visited:
                            meeting_node = neighbor
                            break
                if meeting_node is not None:
                    break
            if meeting_node is not None:
                break

        if meeting_node is None:
            return []

        path: List[NodeID] = []
        node: Optional[NodeID] = meeting_node
        while node is not None:
            path.append(node)
            node = f_visited.get(node)
        path.reverse()

        node = b_visited.get(meeting_node)
        while node is not None:
            path.append(node)
            node = b_visited.get(node)

        return path

    def shortest_path_length(self, start: NodeID, end: NodeID) -> int:
        path = self.shortest_path(start, end)
        if not path:
            return -1
        return len(path) - 1

    def suggest_friends(self, node_id: NodeID, limit: int = 10) -> List[Tuple[NodeID, int]]:
        direct = set(self._graph.get_neighbors(node_id))
        scores: Dict[NodeID, int] = defaultdict(int)

        for friend in direct:
            for fof in self._graph.get_neighbors(friend):
                if fof != node_id and fof not in direct:
                    scores[fof] += 1

        heap: List[Tuple[int, NodeID]] = []
        for candidate, count in scores.items():
            if len(heap) < limit:
                heapq.heappush(heap, (count, candidate))
            elif count > heap[0][0]:
                heapq.heapreplace(heap, (count, candidate))

        result = [(candidate, count) for count, candidate in sorted(heap, reverse=True, key=lambda x: (-x[0], x[1]))]
        return result

    def degree_centrality(self) -> Dict[NodeID, float]:
        if self._graph.node_count == 0:
            return {}
        n = self._graph.node_count - 1
        if n == 0:
            return {node: 0.0 for node in self._graph.nodes}
        return {node: self._graph.get_degree(node) / n for node in self._graph.nodes}

    def common_neighbors(self, a: NodeID, b: NodeID) -> int:
        return len(self.mutual_friends(a, b))

    def jaccard_similarity(self, a: NodeID, b: NodeID) -> float:
        neigh_a = set(self._graph.get_neighbors(a))
        neigh_b = set(self._graph.get_neighbors(b))
        union = neigh_a | neigh_b
        intersection = neigh_a & neigh_b
        if not union:
            return 0.0
        return len(intersection) / len(union)
