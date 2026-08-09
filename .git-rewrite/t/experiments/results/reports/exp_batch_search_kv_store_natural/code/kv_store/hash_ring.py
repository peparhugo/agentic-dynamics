"Consistent hashing ring with virtual nodes.

Maps keys to shards using a hash ring with configurable virtual nodes
per physical node for balanced distribution.
"""

import hashlib
from bisect import bisect_right
from typing import Any, Dict, List, Optional, Set, Tuple


class ConsistentHashRing:
    def __init__(self, virtual_nodes_per_shard: int = 150):
        self._ring: List[Tuple[int, str]] = []
        self._positions: Dict[int, str] = {}
        self._nodes: Set[str] = set()
        self._shard_keys: Dict[str, List[int]] = {}
        self._virtual_nodes_per_shard = virtual_nodes_per_shard

    def add_shard(self, shard_id: str):
        if shard_id in self._nodes:
            return
        self._nodes.add(shard_id)
        self._shard_keys[shard_id] = []
        for i in range(self._virtual_nodes_per_shard):
            vn_key = f"{shard_id}:vn:{i}"
            pos = self._hash(vn_key)
            self._ring.append((pos, shard_id))
            self._shard_keys[shard_id].append(pos)
        self._ring.sort(key=lambda x: x[0])

    def remove_shard(self, shard_id: str):
        if shard_id not in self._nodes:
            return
        self._nodes.discard(shard_id)
        self._ring = [(p, n) for p, n in self._ring if n != shard_id]
        self._shard_keys.pop(shard_id, None)

    def get_shard(self, key: str) -> Optional[str]:
        if not self._ring:
            return None
        h = self._hash(key)
        pos = bisect_right([p for p, _ in self._ring], h)
        if pos == len(self._ring):
            pos = 0
        return self._ring[pos][1]

    def get_shards(self, key: str, count: int) -> List[str]:
        if not self._ring or count <= 0:
            return []
        h = self._hash(key)
        pos = bisect_right([p for p, _ in self._ring], h)
        if pos == len(self._ring):
            pos = 0
        seen: Set[str] = set()
        result = []
        for i in range(len(self._ring)):
            idx = (pos + i) % len(self._ring)
            shard = self._ring[idx][1]
            if shard not in seen:
                seen.add(shard)
                result.append(shard)
                if len(result) >= count:
                    break
        return result

    def get_all_shards(self) -> List[str]:
        return sorted(self._nodes)

    def shard_count(self) -> int:
        return len(self._nodes)

    def keys_moving(self, added: List[str] = None, removed: List[str] = None) -> float:
        added = added or []
        removed = removed or []
        temp_ring = ConsistentHashRing(self._virtual_nodes_per_shard)
        for n in self._nodes | set(added) - set(removed):
            temp_ring.add_shard(n)
        moved = 0
        sample = 10000
        for i in range(sample):
            key = f"__sample__{i}"
            orig = self.get_shard(key)
            new = temp_ring.get_shard(key)
            if orig != new:
                moved += 1
        return moved / sample

    def _hash(self, key: str) -> int:
        return int(hashlib.md5(key.encode()).hexdigest(), 16) & 0x7FFFFFFF
