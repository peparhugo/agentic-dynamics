from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set, Tuple

from social_graph.types import NodeID, Edge, User
from social_graph.graph import SocialGraph


class ShardingStrategy:
    def __init__(self, num_shards: int = 8) -> None:
        self._num_shards = num_shards

    @property
    def num_shards(self) -> int:
        return self._num_shards

    def shard_for(self, node_id: NodeID) -> int:
        return abs(hash(node_id)) % self._num_shards

    def shards_for_edge(self, u: NodeID, v: NodeID) -> Tuple[int, int]:
        return self.shard_for(u), self.shard_for(v)


class Shard:
    def __init__(self, shard_id: int) -> None:
        self.shard_id = shard_id
        self._graph = SocialGraph()

    def add_node(self, node_id: NodeID, user: Optional[User] = None) -> None:
        self._graph.add_node(user=user, node_id=node_id)

    def add_edge(self, u: NodeID, v: NodeID) -> None:
        self._graph.add_edge(u, v)

    def get_neighbors(self, node_id: NodeID) -> List[NodeID]:
        return self._graph.get_neighbors(node_id)

    @property
    def node_count(self) -> int:
        return self._graph.node_count

    @property
    def edge_count(self) -> int:
        return self._graph.edge_count

    def has_node(self, node_id: NodeID) -> bool:
        return self._graph.has_node(node_id)


class ShardedGraph:
    def __init__(self, num_shards: int = 8, directed: bool = False) -> None:
        self._strategy = ShardingStrategy(num_shards)
        self._shards: List[Shard] = [Shard(i) for i in range(num_shards)]
        self._directed = directed
        self._node_count = 0
        self._edge_count = 0
        self._node_shard_map: Dict[NodeID, int] = {}

    @property
    def num_shards(self) -> int:
        return self._strategy.num_shards

    @property
    def node_count(self) -> int:
        return self._node_count

    @property
    def edge_count(self) -> int:
        return self._edge_count

    def add_node(self, user: Optional[User] = None, node_id: Optional[NodeID] = None) -> NodeID:
        if user is not None:
            nid = user.user_id
        elif node_id is not None:
            nid = node_id
            user = User(user_id=nid)
        else:
            raise ValueError("Either user or node_id must be provided")

        s = self._strategy.shard_for(nid)
        self._shards[s].add_node(nid, user)
        self._node_shard_map[nid] = s
        self._node_count += 1
        return nid

    def add_edge(self, u: NodeID, v: NodeID) -> None:
        if u == v:
            return
        s_u, s_v = self._strategy.shards_for_edge(u, v)
        if u not in self._node_shard_map:
            self.add_node(node_id=u)
        if v not in self._node_shard_map:
            self.add_node(node_id=v)
        self._shards[s_u].add_edge(u, v)
        if not self._directed:
            self._shards[s_v].add_edge(u, v)
        self._edge_count += 1

    def get_neighbors(self, node_id: NodeID) -> List[NodeID]:
        if node_id not in self._node_shard_map:
            return []
        s = self._node_shard_map[node_id]
        return self._shards[s].get_neighbors(node_id)

    def shard_for(self, node_id: NodeID) -> int:
        return self._strategy.shard_for(node_id)

    def has_node(self, node_id: NodeID) -> bool:
        return node_id in self._node_shard_map

    @property
    def nodes(self) -> List[NodeID]:
        return list(self._node_shard_map.keys())

    def edges(self) -> List[Edge]:
        seen: Set[Tuple[int, int]] = set()
        result = []
        for nid in self._node_shard_map:
            s = self._node_shard_map[nid]
            for nb in self._shards[s].get_neighbors(nid):
                key = (min(nid, nb), max(nid, nb)) if not self._directed else (nid, nb)
                if key not in seen:
                    seen.add(key)
                    result.append((nid, nb))
        return result
