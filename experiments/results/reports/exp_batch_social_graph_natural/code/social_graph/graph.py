"""In-memory adjacency store for a single shard of the social graph.

The full graph is partitioned (see ``sharding.py``); each partition is one
``SocialGraph`` instance holding a compact adjacency index keyed by user id.
Edges are stored in both directions for O(1) neighbour enumeration, the
dominant operation for read-heavy workloads (connection views, suggestions,
feed fan-out).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .models import Connection, FriendSuggestion, User


class SocialGraph:
    """Adjacency-list graph with user + connection storage.

    Not thread-safe; shard instances are owned by a single worker. Concurrency
    is handled one layer up by the shard router / storage layer.
    """

    def __init__(self) -> None:
        self._users: Dict[str, User] = {}
        # adjacency[u] -> {v: weight}
        self._adj: Dict[str, Dict[str, float]] = {}
        self._edge_meta: Dict[Tuple[str, str], Connection] = {}

    # ------------------------------------------------------------------ users
    def add_user(self, user: User) -> None:
        if user.id in self._users:
            raise ValueError(f"user {user.id} already exists")
        self._users[user.id] = user
        self._adj.setdefault(user.id, {})

    def remove_user(self, user_id: str) -> None:
        if user_id not in self._users:
            raise KeyError(user_id)
        for neighbour in list(self._adj.get(user_id, {})):
            self._adj[neighbour].pop(user_id, None)
            self._edge_meta.pop((neighbour, user_id), None)
        self._adj.pop(user_id, None)
        self._users.pop(user_id, None)

    def get_user(self, user_id: str) -> Optional[User]:
        return self._users.get(user_id)

    def has_user(self, user_id: str) -> bool:
        return user_id in self._users

    def user_count(self) -> int:
        return len(self._users)

    # ------------------------------------------------------------ connections
    def add_connection(
        self, src: str, dst: str, weight: float = 1.0, **meta
    ) -> None:
        if src not in self._users:
            raise KeyError(f"unknown user {src}")
        if dst not in self._users:
            raise KeyError(f"unknown user {dst}")
        if src == dst:
            raise ValueError("self connections are not allowed")

        self._adj[src][dst] = weight
        self._adj[dst][src] = weight
        conn = Connection(src=src, dst=dst, weight=weight, metadata=meta)
        self._edge_meta[(src, dst)] = conn
        self._edge_meta[(dst, src)] = conn

    def remove_connection(self, src: str, dst: str) -> None:
        self._adj.get(src, {}).pop(dst, None)
        self._adj.get(dst, {}).pop(src, None)
        self._edge_meta.pop((src, dst), None)
        self._edge_meta.pop((dst, src), None)

    def are_connected(self, a: str, b: str) -> bool:
        return b in self._adj.get(a, {})

    def connection_weight(self, a: str, b: str) -> Optional[float]:
        return self._adj.get(a, {}).get(b)

    def connections(self, user_id: str) -> Set[str]:
        """Direct neighbours (friends/connections) of a user."""
        return set(self._adj.get(user_id, {}))

    def degree(self, user_id: str) -> int:
        return len(self._adj.get(user_id, {}))

    def edge_count(self) -> int:
        return len(self._edge_meta) // 2

    def connections_view_keys(self) -> List[str]:
        """All node ids present in the adjacency index (used for iteration)."""
        return list(self._adj.keys())

    def all_edges(self) -> Iterable[Connection]:
        seen = set()
        for conn in self._edge_meta.values():
            key = frozenset((conn.src, conn.dst))
            if key not in seen:
                seen.add(key)
                yield conn

    # ------------------------------------------------- friend-of-friend / 2hop
    def mutual_friends(self, a: str, b: str) -> int:
        na = self._adj.get(a, {})
        nb = self._adj.get(b, {})
        if len(na) > len(nb):
            na, nb = nb, na
        return sum(1 for n in na if n in nb)

    def friends_of_friends(
        self, user_id: str, limit: Optional[int] = None, exclude_direct: bool = True
    ) -> List[FriendSuggestion]:
        """Suggest connections via the friend-of-friend (2-hop) heuristic.

        Candidates are ranked by number of mutual friends, a cheap and
        effective proxy for affinity that also feeds the recommendation index.
        """
        direct = self._adj.get(user_id, {})
        counts: Dict[str, int] = defaultdict(int)

        for friend in direct:
            for second_hop in self._adj.get(friend, {}):
                if second_hop == user_id:
                    continue
                if exclude_direct and second_hop in direct:
                    continue
                counts[second_hop] += 1

        suggestions = [
            FriendSuggestion(user_id=uid, mutual_friends=c)
            for uid, c in counts.items()
        ]
        suggestions.sort(key=lambda s: (-s.mutual_friends, s.user_id))
        if limit is not None:
            suggestions = suggestions[:limit]
        return suggestions
