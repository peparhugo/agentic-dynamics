import hashlib
import heapq
import time
import math
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Set, Tuple
from collections import defaultdict


@dataclass(order=True)
class FrontierItem:
    priority: int
    url: str = field(compare=False)
    domain: str = field(compare=False)
    added_at: float = field(default_factory=time.time, compare=False)
    depth: int = field(default=0, compare=False)


class URLFrontier:
    def __init__(self, politeness_manager=None, max_size: int = 100_000_000):
        self._heap: List[FrontierItem] = []
        self._url_set: Set[str] = set()
        self._domain_locks: Dict[str, bool] = defaultdict(bool)
        self._domain_queues: Dict[str, List[FrontierItem]] = defaultdict(list)
        self._politeness_manager = politeness_manager
        self._max_size = max_size
        self._crawled_count: int = 0
        self._failed_count: int = 0

    def push(self, url: str, priority: int = 0, depth: int = 0, domain: Optional[str] = None) -> bool:
        if len(self._url_set) >= self._max_size:
            return False
        if url in self._url_set:
            return False

        if domain is None:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower() or "unknown"

        item = FrontierItem(priority=priority, url=url, domain=domain, depth=depth)
        self._url_set.add(url)
        heapq.heappush(self._heap, item)
        self._domain_queues[domain].append(item)
        return True

    def pop(self) -> Optional[FrontierItem]:
        while self._heap:
            item = heapq.heappop(self._heap)
            if item.url not in self._url_set:
                continue
            if self._politeness_manager and not self._politeness_manager.can_request(item.domain):
                heapq.heappush(self._heap, item)
                continue
            self._url_set.discard(item.url)
            return item
        return None

    def pop_batch(self, max_count: int = 10) -> List[FrontierItem]:
        seen_domains: Set[str] = set()
        batch: List[FrontierItem] = []
        temp: List[FrontierItem] = []

        while self._heap and len(batch) < max_count:
            item = heapq.heappop(self._heap)
            if item.url not in self._url_set:
                continue
            if item.domain in seen_domains:
                temp.append(item)
                continue
            if self._politeness_manager and not self._politeness_manager.can_request(item.domain):
                temp.append(item)
                continue
            self._url_set.discard(item.url)
            seen_domains.add(item.domain)
            batch.append(item)

        for item in temp:
            heapq.heappush(self._heap, item)

        return batch

    def mark_crawled(self, url: str):
        self._crawled_count += 1

    def mark_failed(self, url: str):
        self._failed_count += 1

    def __len__(self) -> int:
        return len(self._url_set)

    def __bool__(self) -> bool:
        return len(self._url_set) > 0

    def size(self) -> int:
        return len(self._url_set)

    def empty(self) -> bool:
        return len(self._url_set) == 0

    def peek_domain_distribution(self) -> Dict[str, int]:
        return {d: len(q) for d, q in self._domain_queues.items()}

    @property
    def crawled_count(self) -> int:
        return self._crawled_count

    @property
    def failed_count(self) -> int:
        return self._failed_count


class DistributedFrontier(URLFrontier):
    def __init__(self, redis_client=None, shard_count: int = 16, **kwargs):
        super().__init__(**kwargs)
        self._redis = redis_client
        self._shard_count = shard_count

    def _get_shard(self, url: str) -> int:
        h = hashlib.md5(url.encode()).digest()
        return int.from_bytes(h[:4], "big") % self._shard_count

    def push(self, url: str, priority: int = 0, depth: int = 0, domain: Optional[str] = None) -> bool:
        if self._redis:
            shard = self._get_shard(url)
            key = f"frontier:shard:{shard}"
            self._redis.zadd(key, {url: priority})
            return True
        return super().push(url, priority, depth, domain)

    def pop(self) -> Optional[FrontierItem]:
        if self._redis:
            for shard in range(self._shard_count):
                key = f"frontier:shard:{shard}"
                results = self._redis.zpopmin(key, 1)
                if results:
                    url, priority = results[0]
                    return FrontierItem(priority=priority, url=url, domain="")
            return None
        return super().pop()
