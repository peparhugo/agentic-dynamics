"""Community detection for the social graph.

Two complementary algorithms are provided:

* ``connected_components`` — exact, using union-find. Cheap to maintain
  incrementally and answers "are these users in the same component?".

* ``label_propagation`` — approximate, near-linear, embarrassingly parallel.
  This is the practical choice for overlapping/loose communities on graphs
  with trillions of edges where exact methods (e.g. modularity maximization)
  are intractable.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Set

from .graph import SocialGraph
from .union_find import UnionFind


def connected_components(graph: SocialGraph) -> List[Set[str]]:
    uf = UnionFind(graph.connections_view_keys())
    for u in graph.connections_view_keys():
        for v in graph.connections(u):
            uf.union(u, v)
    return uf.components()


def component_of(graph: SocialGraph, user_id: str) -> Set[str]:
    uf = UnionFind([user_id])
    _seed_uf(graph, user_id, uf)
    return set(uf.components()[0]) if uf.num_components() else set()


def _seed_uf(graph: SocialGraph, root: str, uf: UnionFind) -> None:
    stack = [root]
    while stack:
        cur = stack.pop()
        for nxt in graph.connections(cur):
            if nxt in uf._parent:
                continue
            uf.union(cur, nxt)
            stack.append(nxt)


def label_propagation(
    graph: SocialGraph,
    iterations: int = 5,
    seed: Optional[int] = None,
) -> Dict[str, str]:
    """Label propagation community detection.

    Each node starts with its own id as its label and repeatedly adopts the
    most frequent label among its neighbours. Runs in O(iterations * edges).
    """
    rng = random.Random(seed)
    nodes = list(graph.connections_view_keys())
    labels: Dict[str, str] = {n: n for n in nodes}

    for _ in range(iterations):
        rng.shuffle(nodes)
        changed = False
        for node in nodes:
            counter: Dict[str, int] = {}
            for nxt in graph.connections(node):
                l = labels[nxt]
                counter[l] = counter.get(l, 0) + 1
            if not counter:
                continue
            best = max(counter.values())
            candidates = [l for l, c in counter.items() if c == best]
            new_label = candidates[0] if len(candidates) == 1 else rng.choice(candidates)
            if new_label != labels[node]:
                labels[node] = new_label
                changed = True
        if not changed:
            break
    return labels


def communities_from_labels(labels: Dict[str, str]) -> List[Set[str]]:
    groups: Dict[str, Set[str]] = {}
    for node, l in labels.items():
        groups.setdefault(l, set()).add(node)
    return list(groups.values())
