"Distributed key-value store client.

Coordinates reads/writes across sharded nodes with:
- Consistent hashing for key placement
- Configurable replication factor
- Consistency levels: ONE, QUORUM, ALL
- Hot key detection and load shedding
- Batch operations and range queries
- Request coalescing for hot keys
"""

import threading
import time
from collections import defaultdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .hash_ring import ConsistentHashRing
from .node import Node


class ConsistencyLevel(Enum):
    ONE = "ONE"
    QUORUM = "QUORUM"
    ALL = "ALL"


class HotKeyTracker:
    def __init__(self, threshold: int = 100, window_sec: float = 10.0):
        self.threshold = threshold
        self.window_sec = window_sec
        self._counts: Dict[str, int] = defaultdict(int)
        self._hot_keys: Set[str] = set()
        self._lock = threading.Lock()
        self._last_prune = time.monotonic()

    def record(self, key: str):
        with self._lock:
            self._counts[key] += 1
            if self._counts[key] >= self.threshold:
                self._hot_keys.add(key)
            self._maybe_prune()

    def is_hot(self, key: str) -> bool:
        with self._lock:
            self._maybe_prune()
            return key in self._hot_keys

    def get_hot_keys(self) -> Set[str]:
        with self._lock:
            self._maybe_prune()
            return set(self._hot_keys)

    def _maybe_prune(self):
        now = time.monotonic()
        if now - self._last_prune > self.window_sec:
            self._counts.clear()
            self._hot_keys.clear()
            self._last_prune = now


class WriteResult:
    def __init__(self, success: bool, ack_count: int, required: int, errors: List[str] = None):
        self.success = success
        self.ack_count = ack_count
        self.required = required
        self.errors = errors or []


class DistributedKVStore:
    def __init__(
        self,
        nodes: Optional[List[Node]] = None,
        shard_ids: Optional[List[str]] = None,
        replication_factor: int = 3,
        default_consistency: ConsistencyLevel = ConsistencyLevel.QUORUM,
        virtual_nodes: int = 150,
    ):
        self._nodes: Dict[str, Node] = {}
        self._ring = ConsistentHashRing(virtual_nodes)
        self._replication_factor = min(replication_factor, 1)
        self._default_consistency = default_consistency
        self._hot_tracker = HotKeyTracker()
        self._read_coalesce_locks: Dict[str, threading.Lock] = {}
        self._read_coalesce_lock = threading.Lock()
        self._read_coalesce_results: Dict[str, Any] = {}
        self._stats_lock = threading.Lock()
        self._stats = {"gets": 0, "puts": 0, "hot_key_hits": 0, "errors": 0}

        if nodes and shard_ids:
            for node, sid in zip(nodes, shard_ids):
                self.add_node(node, sid)

    def add_node(self, node: Node, shard_id: str):
        self._nodes[shard_id] = node
        self._ring.add_shard(shard_id)
        self._replication_factor = min(
            max(self._replication_factor, 1),
            len(self._nodes),
        )

    def remove_node(self, shard_id: str):
        if shard_id in self._nodes:
            del self._nodes[shard_id]
            self._ring.remove_shard(shard_id)

    def setup_replication(self, shard_id: str, replica_count: int):
        replicas = self._ring.get_shards(shard_id, replica_count + 1)
        primary = self._nodes.get(shard_id)
        if primary:
            for r_shard in replicas[1:]:
                replica_node = self._nodes.get(r_shard)
                if replica_node:
                    primary.add_replica(replica_node)

    def setup_full_replication(self, replica_count: int):
        for shard_id in self._ring.get_all_shards():
            self.setup_replication(shard_id, replica_count)

    def put(
        self,
        key: str,
        value: Any,
        consistency: Optional[ConsistencyLevel] = None,
    ) -> WriteResult:
        consistency = consistency or self._default_consistency
        shards = self._ring.get_shards(key, self._replication_factor)
        nodes = [self._nodes[s] for s in shards if s in self._nodes and self._nodes[s].is_healthy()]

        required = self._required_acks(consistency, len(nodes))
        ack_count = 0
        errors = []

        for node in nodes:
            try:
                if node.put(key, value, replicate=False):
                    ack_count += 1
                else:
                    errors.append(f"put failed on {node.node_id}")
            except Exception as e:
                errors.append(str(e))

        success = ack_count >= required
        with self._stats_lock:
            self._stats["puts"] += 1
            if not success:
                self._stats["errors"] += 1

        return WriteResult(success, ack_count, required, errors)

    def get(self, key: str, consistency: Optional[ConsistencyLevel] = None) -> Optional[List[Any]]:
        consistency = consistency or self._default_consistency
        self._hot_tracker.record(key)

        if self._hot_tracker.is_hot(key):
            with self._stats_lock:
                self._stats["hot_key_hits"] += 1
            return self._coalesced_get(key)

        return self._direct_get(key, consistency)

    def _direct_get(self, key: str, consistency: ConsistencyLevel) -> Optional[List[Any]]:
        shards = self._ring.get_shards(key, self._replication_factor)
        nodes = [self._nodes[s] for s in shards if s in self._nodes and self._nodes[s].is_healthy()]

        required = self._required_acks(consistency, len(nodes))
        results = []
        for node in nodes:
            try:
                r = node.get(key)
                if r is not None:
                    results.append(r)
            except Exception:
                pass

        with self._stats_lock:
            self._stats["gets"] += 1

        if len(results) >= required:
            return self._resolve_reads(results)
        return None

    def _coalesced_get(self, key: str) -> Optional[List[Any]]:
        lock = self._get_coalesce_lock(key)
        with lock:
            if key in self._read_coalesce_results:
                return self._read_coalesce_results[key]
            result = self._direct_get(key, self._default_consistency)
            self._read_coalesce_results[key] = result
            return result

    def _get_coalesce_lock(self, key: str) -> threading.Lock:
        with self._read_coalesce_lock:
            if key not in self._read_coalesce_locks:
                self._read_coalesce_locks[key] = threading.Lock()
            return self._read_coalesce_locks[key]

    def range_query(
        self,
        start: str,
        end: str,
        inclusive: bool = True,
    ) -> List[Tuple[str, List[Any]]]:
        all_results: Dict[str, List[Any]] = {}
        for node in self._nodes.values():
            if node.is_healthy():
                results = node.range_query(start, end, inclusive)
                for k, v in results:
                    if k not in all_results:
                        all_results[k] = []
                    all_results[k].extend(v)
        return sorted(all_results.items(), key=lambda x: x[0])

    def prefix_scan(self, prefix: str) -> List[Tuple[str, List[Any]]]:
        all_results: Dict[str, List[Any]] = {}
        for node in self._nodes.values():
            if node.is_healthy():
                results = node.prefix_scan(prefix)
                for k, v in results:
                    if k not in all_results:
                        all_results[k] = []
                    all_results[k].extend(v)
        return sorted(all_results.items(), key=lambda x: x[0])

    def batch_put(
        self,
        entries: List[Tuple[str, Any]],
        consistency: Optional[ConsistencyLevel] = None,
    ) -> WriteResult:
        consistency = consistency or self._default_consistency
        by_shard: Dict[str, List[Tuple[str, Any]]] = defaultdict(list)
        for key, value in entries:
            shard = self._ring.get_shard(key)
            if shard:
                by_shard[shard].append((key, value))

        total_acks = 0
        total_required = 0
        all_errors = []

        for shard_id, shard_entries in by_shard.items():
            shards = self._ring.get_shards(shard_id, self._replication_factor)
            nodes = [self._nodes[s] for s in shards if s in self._nodes and self._nodes[s].is_healthy()]
            required = self._required_acks(consistency, len(nodes))

            for node in nodes:
                try:
                    if node.batch_put(shard_entries, replicate=False):
                        total_acks += 1
                    else:
                        all_errors.append(f"batch_put failed on {node.node_id}")
                except Exception as e:
                    all_errors.append(str(e))

            total_required += required

        success = total_acks >= total_required if total_required > 0 else False
        with self._stats_lock:
            self._stats["puts"] += 1
            if not success:
                self._stats["errors"] += 1

        return WriteResult(success, total_acks, total_required, all_errors)

    def multi_get(
        self, keys: List[str], consistency: Optional[ConsistencyLevel] = None
    ) -> Dict[str, Optional[List[Any]]]:
        results = {}
        for key in keys:
            results[key] = self.get(key, consistency)
        return results

    def get_hot_keys(self, top_n: int = 10) -> List[str]:
        all_hot: Dict[str, int] = defaultdict(int)
        for node in self._nodes.values():
            if node.is_healthy():
                for k, count in node.engine.get_hot_keys(top_n):
                    all_hot[k] += count
        sorted_keys = sorted(all_hot.items(), key=lambda x: x[1], reverse=True)
        return [k for k, _ in sorted_keys[:top_n]]

    def get_stats(self) -> dict:
        with self._stats_lock:
            return dict(self._stats)

    def get_cluster_health(self) -> Dict[str, dict]:
        return {
            shard_id: {
                "node_id": node.node_id,
                "healthy": node.is_healthy(),
                "key_count": node.key_count(),
                "replicas": [r.node_id for r in node.get_replicas()],
                "stats": node.get_stats(),
            }
            for shard_id, node in self._nodes.items()
        }

    def _required_acks(self, consistency: ConsistencyLevel, total_nodes: int) -> int:
        if total_nodes == 0:
            return 0
        if consistency == ConsistencyLevel.ONE:
            return 1
        elif consistency == ConsistencyLevel.QUORUM:
            return (total_nodes // 2) + 1
        elif consistency == ConsistencyLevel.ALL:
            return total_nodes
        return 1

    def _resolve_reads(self, results: List[List[Any]]) -> List[Any]:
        if not results:
            return []
        longest = max(results, key=len)
        return longest

    def node_for_key(self, key: str) -> Optional[Node]:
        shard = self._ring.get_shard(key)
        if shard:
            return self._nodes.get(shard)
        return None

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def replication_factor(self) -> int:
        return self._replication_factor
