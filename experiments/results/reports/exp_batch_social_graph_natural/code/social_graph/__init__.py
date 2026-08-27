"""Social network graph data structures and infrastructure.

A horizontally sharded, read-optimized social graph supporting users,
connections, friend-of-friend suggestions, path finding, and community
detection, designed for billion-node / trillion-edge scale.
"""

from .cache import CachedGraph, LRUCache
from .community import (
    communities_from_labels,
    connected_components,
    component_of,
    label_propagation,
)
from .graph import SocialGraph
from .models import Connection, FriendSuggestion, PathResult, User
from .pathfinding import (
    bfs_path,
    bidirectional_bfs_path,
    shortest_path,
)
from .sharding import ConsistentHash, ShardedGraph
from .storage import ConnectionStore, Mutation, WriteAheadLog
from .union_find import UnionFind

__all__ = [
    "SocialGraph",
    "ShardedGraph",
    "ConsistentHash",
    "User",
    "Connection",
    "FriendSuggestion",
    "PathResult",
    "UnionFind",
    "connected_components",
    "component_of",
    "label_propagation",
    "communities_from_labels",
    "bfs_path",
    "bidirectional_bfs_path",
    "shortest_path",
    "LRUCache",
    "CachedGraph",
    "WriteAheadLog",
    "ConnectionStore",
    "Mutation",
]
