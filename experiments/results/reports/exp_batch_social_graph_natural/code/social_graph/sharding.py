"""Horizontal sharding of the social graph.

Billions of nodes / trillions of edges cannot live in one machine's memory, so
we partition the graph into shards. Users are assigned to shards by consistent
hashing on their id, which spreads load evenly and minimizes reshuffling when
the shard count changes.

Because a connection touches two users it is stored in *both* endpoint shards
(edge replication), so every neighbour query is served from a single shard with
no cross-shard reads on the hot path. Cross-shard operations (path finding,
community detection) fan out and aggregate at the router.
"""

from __future__ import annotations

import hashlib
import heapq
from bisect import bisect
from typing import Dict, Iterable, List, Optional

from .graph import SocialGraph
from .models import FriendSuggestion, PathResult, User
from .pathfinding import shortest_path


class ConsistentHash:
    """Consistent hash ring mapping keys to a fixed set of shards."""

    def __init__(self, shard_ids: Iterable[str], virtual_nodes: int = 150) -> None:
        self.shard_ids = list(shard_ids)
        self.virtual_nodes = virtual_nodes
        self._ring: List[tuple] = []
        self._build()

    def _build(self) -> None:
        self._ring = []
        for sid in self.shard_ids:
            for i in range(self.virtual_nodes):
                h = self._hash(f"{sid}:{i}")
                self._ring.append((h, sid))
        self._ring.sort()
        self._hashes = [h for h, _ in self._ring]

    @staticmethod
    def _hash(key: str) -> int:
        return int.from_bytes(hashlib.md5(key.encode("utf-8")).digest(), "big")

    def shard_for(self, key: str) -> str:
        if not self._ring:
            raise RuntimeError("consistent hash ring is empty")
        h = self._hash(key)
        idx = bisect(self._hashes, h)
        if idx == len(self._ring):
            idx = 0
        return self._ring[idx][1]


class ShardedGraph:
    """Router over multiple SocialGraph shards keyed by user id."""

    def __init__(self, shard_ids: Iterable[str]) -> None:
        self._shards: Dict[str, SocialGraph] = {
            sid: SocialGraph() for sid in shard_ids
        }
        self._ring = ConsistentHash(self._shards.keys())

    # -------------------------------------------------------------- routing
    def _shard(self, user_id: str) -> SocialGraph:
        return self._shards[self._ring.shard_for(user_id)]

    def _all_shards(self) -> List[SocialGraph]:
        return list(self._shards.values())

    def shard_for(self, user_id: str) -> str:
        return self._ring.shard_for(user_id)

    @property
    def shard_count(self) -> int:
        return len(self._shards)

    # ---------------------------------------------------------------- users
    def add_user(self, user: User) -> None:
        self._shard(user.id).add_user(user)

    def remove_user(self, user_id: str) -> None:
        # A user's edges also live in their neighbours' shards; clean them up.
        graph = self._shard(user_id)
        for neighbour in list(graph.connections(user_id)):
            self._shard(neighbour).remove_connection(neighbour, user_id)
        graph.remove_user(user_id)

    def get_user(self, user_id: str) -> Optional[User]:
        return self._shard(user_id).get_user(user_id)

    def total_users(self) -> int:
        return sum(s.user_count() for s in self._all_shards())

    # --------------------------------------------------------- connections
    def add_connection(self, src: str, dst: str, weight: float = 1.0) -> None:
        s_src, s_dst = self._shard(src), self._shard(dst)
        if s_src is s_dst:
            s_src.add_connection(src, dst, weight)
            return
        s_src.add_connection(src, dst, weight)
        s_dst.add_connection(dst, src, weight)

    def remove_connection(self, src: str, dst: str) -> None:
        s_src, s_dst = self._shard(src), self._shard(dst)
        if s_src is s_dst:
            s_src.remove_connection(src, dst)
            return
        s_src.remove_connection(src, dst)
        s_dst.remove_connection(dst, src)

    def connections(self, user_id: str) -> set:
        return self._shard(user_id).connections(user_id)

    def degree(self, user_id: str) -> int:
        return self._shard(user_id).degree(user_id)

    def are_connected(self, a: str, b: str) -> bool:
        return self._shard(a).are_connected(a, b)

    def total_edges(self) -> int:
        return sum(s.edge_count() for s in self._all_shards())

    # ------------------------------------------------- friend-of-friend
    def friends_of_friends(
        self, user_id: str, limit: Optional[int] = None
    ) -> List[FriendSuggestion]:
        return self._shard(user_id).friends_of_friends(user_id, limit=limit)

    # ------------------------------------------------------ cross-shard
    def shortest_path(self, src: str, dst: str) -> PathResult:
        """BFS across shards, fetching neighbour sets lazily from each shard."""
        from collections import deque

        if src == dst:
            return PathResult(path=[src], distance=0)
        if self.get_user(src) is None or self.get_user(dst) is None:
            return PathResult(path=None, distance=-1)

        prev = {src: None}
        queue = deque([src])
        while queue:
            cur = queue.popleft()
            for nxt in self._shard(cur).connections(cur):
                if nxt in prev:
                    continue
                prev[nxt] = cur
                if nxt == dst:
                    path = [dst]
                    while path[-1] != src:
                        path.append(prev[path[-1]])
                    path.reverse()
                    return PathResult(path=path, distance=len(path) - 1)
                queue.append(nxt)
        return PathResult(path=None, distance=-1)
