from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterator, List, Optional, Set, Tuple, Union

from social_graph.types import NodeID
from social_graph.graph import SocialGraph
from social_graph.shard import ShardedGraph
from social_graph.union_find import UnionFind

GraphLike = Union[SocialGraph, ShardedGraph]


class CommunityDetector:
    def __init__(self, graph: GraphLike) -> None:
        self._graph = graph

    def connected_components(self) -> Dict[int, List[NodeID]]:
        uf = UnionFind()
        for node in self._graph.nodes:
            uf.make_set(node)
        for node in self._graph.nodes:
            for neighbor in self._graph.get_neighbors(node):
                uf.union(node, neighbor)
        return uf.components()

    def label_propagation(self, max_iterations: int = 50) -> Dict[NodeID, int]:
        labels: Dict[NodeID, int] = {}
        for i, node in enumerate(self._graph.nodes):
            labels[node] = node

        import random
        rng = random.Random(42)

        for iteration in range(max_iterations):
            changed = False
            nodes = list(self._graph.nodes)
            rng.shuffle(nodes)

            for node in nodes:
                if not self._graph.get_neighbors(node):
                    continue

                label_counts: Dict[int, int] = defaultdict(int)
                for neighbor in self._graph.get_neighbors(node):
                    label_counts[labels[neighbor]] += 1

                if not label_counts:
                    continue

                max_count = max(label_counts.values())
                best_labels = [l for l, c in label_counts.items() if c == max_count]
                best_label = best_labels[0]

                if labels[node] != best_label:
                    labels[node] = best_label
                    changed = True

            if not changed:
                break

        label_map: Dict[int, int] = {}
        next_id = 0
        remapped: Dict[NodeID, int] = {}
        for node in self._graph.nodes:
            raw = labels[node]
            if raw not in label_map:
                label_map[raw] = next_id
                next_id += 1
            remapped[node] = label_map[raw]

        return remapped

    def communities(self, method: str = "connected_components") -> Dict[int, List[NodeID]]:
        if method == "connected_components":
            return self.connected_components()
        elif method == "label_propagation":
            node_labels = self.label_propagation()
            groups: Dict[int, List[NodeID]] = defaultdict(list)
            for node, label in node_labels.items():
                groups[label].append(node)
            return dict(groups)
        else:
            raise ValueError(f"Unknown method: {method}")

    def modularity(self, communities: Dict[int, List[NodeID]]) -> float:
        node_to_community: Dict[NodeID, int] = {}
        for comm_id, members in communities.items():
            for node in members:
                node_to_community[node] = comm_id

        m = self._graph.edge_count
        if m == 0:
            return 0.0

        degrees = {node: self._graph.get_degree(node) for node in self._graph.nodes}
        q = 0.0

        for node in self._graph.nodes:
            ci = node_to_community.get(node)
            if ci is None:
                continue
            for neighbor in self._graph.get_neighbors(node):
                cj = node_to_community.get(neighbor)
                if cj is None:
                    continue
                if ci == cj:
                    q += 1.0 - (degrees[node] * degrees[neighbor]) / (2.0 * m)

        q /= (2.0 * m)
        return q

    def community_sizes(self, communities: Dict[int, List[NodeID]]) -> Dict[int, int]:
        return {cid: len(members) for cid, members in communities.items()}

    def giant_component_fraction(self) -> float:
        if self._graph.node_count == 0:
            return 0.0
        comps = self.connected_components()
        if not comps:
            return 0.0
        largest = max(len(members) for members in comps.values())
        return largest / self._graph.node_count

    def num_connected_components(self) -> int:
        comps = self.connected_components()
        return len(comps)
