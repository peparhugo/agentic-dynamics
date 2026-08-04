"Individual node in the distributed KV cluster.

Manages a local StorageEngine, optional write-ahead log,
replication to peer nodes, and health status.
"""

import json
import os
import threading
import time
from typing import Any, List, Optional, Tuple

from .engine import StorageEngine


class WALEntry:
    __slots__ = ("op", "key", "value", "timestamp")

    def __init__(self, op: str, key: str, value: Any = None):
        self.op = op
        self.key = key
        self.value = value
        self.timestamp = time.time()


class Node:
    def __init__(
        self,
        node_id: str,
        wal_path: Optional[str] = None,
        engine: Optional[StorageEngine] = None,
    ):
        self.node_id = node_id
        self.engine = engine or StorageEngine()
        self._wal_path = wal_path
        self._wal_lock = threading.Lock()
        self._healthy = True
        self._replicas: List["Node"] = []
        self._stats = {"gets": 0, "puts": 0, "errors": 0, "replicated": 0}
        self._stats_lock = threading.Lock()

    def put(self, key: str, value: Any, replicate: bool = True) -> bool:
        try:
            self.engine.put(key, value)
            self._wal_append("put", key, value)
            with self._stats_lock:
                self._stats["puts"] += 1
            if replicate and self._replicas:
                self._replicate("put", key, value)
            return True
        except Exception:
            with self._stats_lock:
                self._stats["errors"] += 1
            return False

    def get(self, key: str) -> Optional[List[Any]]:
        try:
            result = self.engine.get(key)
            with self._stats_lock:
                self._stats["gets"] += 1
            return result
        except Exception:
            with self._stats_lock:
                self._stats["errors"] += 1
            return None

    def range_query(
        self, start: str, end: str, inclusive: bool = True
    ) -> List[Tuple[str, List[Any]]]:
        try:
            return self.engine.range_query(start, end, inclusive)
        except Exception:
            with self._stats_lock:
                self._stats["errors"] += 1
            return []

    def prefix_scan(self, prefix: str) -> List[Tuple[str, List[Any]]]:
        try:
            return self.engine.prefix_scan(prefix)
        except Exception:
            with self._stats_lock:
                self._stats["errors"] += 1
            return []

    def batch_put(
        self, entries: List[Tuple[str, Any]], replicate: bool = True
    ) -> bool:
        try:
            self.engine.batch_put(entries)
            for key, value in entries:
                self._wal_append("put", key, value)
            with self._stats_lock:
                self._stats["puts"] += len(entries)
            if replicate and self._replicas:
                for key, value in entries:
                    self._replicate("put", key, value)
            return True
        except Exception:
            with self._stats_lock:
                self._stats["errors"] += 1
            return False

    def remove(self, key: str) -> bool:
        try:
            result = self.engine.remove(key)
            if result:
                self._wal_append("remove", key)
            return result
        except Exception:
            with self._stats_lock:
                self._stats["errors"] += 1
            return False

    def contains(self, key: str) -> bool:
        return self.engine.contains(key)

    def add_replica(self, replica: "Node"):
        if replica not in self._replicas and replica != self:
            self._replicas.append(replica)

    def remove_replica(self, replica: "Node"):
        if replica in self._replicas:
            self._replicas.remove(replica)

    def get_replicas(self) -> List["Node"]:
        return list(self._replicas)

    def get_snapshot(self) -> dict:
        return {
            "node_id": self.node_id,
            "key_count": self.engine.key_count(),
            "total_values": self.engine.total_values(),
            "keys": self.engine.get_all_keys(),
            "data": self.engine.get_snapshot(),
            "hot_keys": self.engine.get_hot_keys(),
            "stats": self.get_stats(),
            "healthy": self._healthy,
            "replicas": [r.node_id for r in self._replicas],
        }

    def get_data_snapshot(self) -> dict:
        return self.engine.get_snapshot()

    def get_stats(self) -> dict:
        with self._stats_lock:
            return dict(self._stats)

    def set_healthy(self, healthy: bool):
        self._healthy = healthy

    def is_healthy(self) -> bool:
        return self._healthy

    def key_count(self) -> int:
        return self.engine.key_count()

    def _replicate(self, op: str, key: str, value: Any):
        for replica in self._replicas:
            if replica.is_healthy():
                try:
                    if op == "put":
                        replica.put(key, value, replicate=False)
                    elif op == "remove":
                        replica.remove(key)
                    with self._stats_lock:
                        self._stats["replicated"] += 1
                except Exception:
                    pass

    def _wal_append(self, op: str, key: str, value: Any = None):
        if not self._wal_path:
            return
        with self._wal_lock:
            os.makedirs(os.path.dirname(self._wal_path), exist_ok=True)
            entry = {"op": op, "key": key, "value": value, "ts": time.time()}
            with open(self._wal_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
