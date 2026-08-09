from __future__ import annotations

import bisect
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Set, Tuple

from social_graph.types import NodeID, Edge, User


class SocialGraph:
    def __init__(self, directed: bool = False) -> None:
        self._adj: Dict[NodeID, List[NodeID]] = {}
        self._users: Dict[NodeID, User] = {}
        self._directed = directed
        self._edge_count: int = 0

    @property
    def node_count(self) -> int:
        return len(self._adj)

    @property
    def edge_count(self) -> int:
        return self._edge_count

    @property
    def directed(self) -> bool:
        return self._directed

    @property
    def nodes(self) -> List[NodeID]:
        return list(self._adj.keys())

    def has_node(self, node_id: NodeID) -> bool:
        return node_id in self._adj

    def add_node(self, user: Optional[User] = None, node_id: Optional[NodeID] = None) -> NodeID:
        if user is not None:
            nid = user.user_id
        elif node_id is not None:
            nid = node_id
            user = User(user_id=nid)
        else:
            raise ValueError("Either user or node_id must be provided")

        if nid not in self._adj:
            self._adj[nid] = []
        self._users[nid] = user
        return nid

    def add_edge(self, u: NodeID, v: NodeID) -> None:
        if u == v:
            return
        if u not in self._adj:
            self.add_node(node_id=u)
        if v not in self._adj:
            self.add_node(node_id=v)

        if not self._directed:
            if v not in self._adj[u]:
                self._adj[u].append(v)
                self._adj[u].sort()
            if u not in self._adj[v]:
                self._adj[v].append(u)
                self._adj[v].sort()
            self._edge_count += 1
        else:
            if v not in self._adj[u]:
                self._adj[u].append(v)
                self._adj[u].sort()
                self._edge_count += 1

    def remove_edge(self, u: NodeID, v: NodeID) -> None:
        if u not in self._adj or v not in self._adj:
            return

        def _remove(lst: List[NodeID], target: NodeID) -> bool:
            try:
                lst.remove(target)
                return True
            except ValueError:
                return False

        if not self._directed:
            removed_u = _remove(self._adj[u], v)
            removed_v = _remove(self._adj[v], u)
            if removed_u and removed_v:
                self._edge_count -= 1
        else:
            if _remove(self._adj[u], v):
                self._edge_count -= 1

    def remove_node(self, node_id: NodeID) -> None:
        if node_id not in self._adj:
            return
        neighbors = list(self._adj[node_id])
        for neighbor in neighbors:
            self.remove_edge(node_id, neighbor)
        del self._adj[node_id]
        self._users.pop(node_id, None)

    def get_neighbors(self, node_id: NodeID) -> List[NodeID]:
        return self._adj.get(node_id, [])

    def get_degree(self, node_id: NodeID) -> int:
        return len(self._adj.get(node_id, []))

    def has_edge(self, u: NodeID, v: NodeID) -> bool:
        if u not in self._adj:
            return False
        idx = bisect.bisect_left(self._adj[u], v)
        return idx < len(self._adj[u]) and self._adj[u][idx] == v

    def get_user(self, node_id: NodeID) -> Optional[User]:
        return self._users.get(node_id)

    def edges(self) -> List[Edge]:
        seen: Set[Tuple[NodeID, NodeID]] = set()
        result = []
        for u in self._adj:
            for v in self._adj[u]:
                if not self._directed:
                    key = (min(u, v), max(u, v))
                else:
                    key = (u, v)
                if key not in seen:
                    seen.add(key)
                    result.append((u, v))
        return result

    def clear(self) -> None:
        self._adj.clear()
        self._users.clear()
        self._edge_count = 0

    def subgraph(self, node_ids: Set[NodeID]) -> SocialGraph:
        sub = SocialGraph(directed=self._directed)
        for nid in node_ids:
            if nid in self._adj:
                sub.add_node(user=self._users.get(nid))
        for nid in node_ids:
            if nid in self._adj:
                for neighbor in self._adj[nid]:
                    if neighbor in node_ids:
                        if not self._directed and nid > neighbor:
                            continue
                        sub.add_edge(nid, neighbor)
        return sub

    def __contains__(self, node_id: NodeID) -> bool:
        return node_id in self._adj

    def __len__(self) -> int:
        return self.node_count
