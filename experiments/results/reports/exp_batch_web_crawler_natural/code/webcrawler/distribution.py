"""Distributed crawling: consistent-hash sharding of the URL space.

To crawl billions of pages, the crawl is spread over many machines.  Each URL
is assigned to exactly one worker via a consistent hash ring keyed on its
hostname.  This gives three properties essential at scale:

* **Deterministic assignment** -- any node can compute which worker owns a
  URL without a central directory (no single point of failure).
* **Host locality** -- all URLs of a host land on the same worker, so
  per-host politeness (robots.txt, crawl-delay, rate limiting) is enforced
  naturally by a single process.
* **Minimal reshuffling** -- adding/removing a worker only moves ~1/N of the
  URL space (``replicas`` virtual nodes smooth the distribution).

The :class:`Distributor` layers a small work-queue abstraction over the ring
for coordinator/worker communication.
"""

from __future__ import annotations

import bisect
import hashlib
from typing import Iterable, List, Optional, Sequence


def _hash(key: str) -> int:
    return int.from_bytes(hashlib.md5(key.encode("utf-8")).digest()[:8], "big")


class HashRing:
    def __init__(self, nodes: Sequence[str], replicas: int = 100):
        if not nodes:
            raise ValueError("HashRing requires at least one node")
        self.replicas = replicas
        self._ring: List[int] = []
        self._node_for_pos: dict = {}
        self._nodes = set(nodes)
        for node in nodes:
            self._add_node(node)

    def _add_node(self, node: str) -> None:
        for i in range(self.replicas):
            key = _hash(f"{node}:{i}")
            self._ring.append(key)
            self._node_for_pos[key] = node
        self._ring.sort()

    def add_node(self, node: str) -> None:
        if node in self._nodes:
            return
        self._nodes.add(node)
        self._add_node(node)

    def remove_node(self, node: str) -> None:
        if node not in self._nodes:
            return
        self._nodes.discard(node)
        self._ring = [p for p in self._ring if self._node_for_pos[p] != node]
        for p in list(self._node_for_pos):
            if self._node_for_pos[p] == node:
                del self._node_for_pos[p]

    def get_node(self, key: str) -> str:
        h = _hash(key)
        idx = bisect.bisect_right(self._ring, h)
        if idx == len(self._ring):
            idx = 0
        return self._node_for_pos[self._ring[idx]]

    @property
    def nodes(self) -> set:
        return set(self._nodes)


class Distributor:
    """Assigns URLs to workers and tracks which URLs a given worker owns."""

    def __init__(self, workers: Sequence[str], replicas: int = 100):
        self.ring = HashRing(workers, replicas=replicas)

    def worker_for(self, url: str) -> str:
        from webcrawler.url_utils import hostname_of

        host = hostname_of(url) or url
        return self.ring.get_node(host)

    def assign(self, urls: Iterable[str]) -> dict:
        """Partition ``urls`` into per-worker batches."""
        batches: dict = {}
        for url in urls:
            worker = self.worker_for(url)
            batches.setdefault(worker, []).append(url)
        return batches

    def worker_count(self) -> int:
        return len(self.ring.nodes)


__all__ = ["HashRing", "Distributor"]
