"""A polite, priority-aware URL frontier.

The frontier is the crawler's scheduler.  Its job is to decide *what* to
crawl next while honouring three constraints:

* **Seen-set / loop avoidance** -- a Bloom filter rejects any URL we have
  already enqueued, so link cycles cannot loop forever.
* **Host politeness** -- at most one URL per host is "in flight" at a time,
  and a host is not revisited until a minimum delay has elapsed.
* **Priority** -- within a host, higher-priority URLs are dequeued first.

This is the classic two-level (host + URL) frontier.  It scales to billions
of URLs because it stores only O(1) state per host and the seen-set is a
compact probabilistic filter.
"""

from __future__ import annotations

import heapq
import threading
import time
from collections import defaultdict
from typing import Callable, Dict, List, Optional, Tuple

from webcrawler.dedup import BloomFilter
from webcrawler.url_utils import hostname_of, is_http_url, normalize_url


class Frontier:
    def __init__(
        self,
        default_delay: float = 1.0,
        capacity: int = 1_000_000,
        error_rate: float = 0.01,
        clock: Callable[[], float] = time.monotonic,
        track_seen: bool = True,
    ):
        self.default_delay = default_delay
        self._clock = clock
        self.track_seen = track_seen
        self._seen = BloomFilter(capacity=capacity, error_rate=error_rate)
        # host -> heap of (-priority, seq, url)
        self._queues: Dict[str, List[Tuple[float, int, str]]] = defaultdict(list)
        # heap of (ready_time, host) hosts waiting to be polled
        self._available: List[Tuple[float, str]] = []
        self._in_flight: set = set()
        self._seq = 0
        self._lock = threading.Lock()

    def has_seen(self, url: str) -> bool:
        if not self.track_seen:
            return False
        return normalize_url(url) in self._seen

    def add(self, url: str, priority: float = 0.0) -> bool:
        """Enqueue a URL.  Returns True if newly added, False if a dup."""
        if not is_http_url(url):
            return False
        url = normalize_url(url)
        with self._lock:
            if self.track_seen:
                if url in self._seen:
                    return False
                self._seen.add(url)
            return self._enqueue(url, priority)

    def requeue(self, url: str, priority: float = 0.0) -> bool:
        """Enqueue a URL that was already seen (used for scheduled
        recrawls).  Bypasses the seen filter."""
        if not is_http_url(url):
            return False
        url = normalize_url(url)
        with self._lock:
            return self._enqueue(url, priority)

    def _enqueue(self, url: str, priority: float) -> bool:
        host = hostname_of(url)
        self._seq += 1
        queue = self._queues[host]
        if not queue and host not in self._in_flight:
            heapq.heappush(self._available, (self._clock(), host))
        heapq.heappush(queue, (-priority, self._seq, url))
        return True

    def add_many(self, urls, priority: float = 0.0) -> int:
        added = 0
        for u in urls:
            if self.add(u, priority):
                added += 1
        return added

    def next(self) -> Optional[str]:
        """Return the next URL to crawl, or None if no host is due yet.

        ``next_ready_time`` tells the caller how long to sleep.
        """
        with self._lock:
            now = self._clock()
            while self._available:
                ready_time, host = self._available[0]
                if host not in self._queues or not self._queues[host]:
                    heapq.heappop(self._available)
                    continue
                if host in self._in_flight:
                    heapq.heappop(self._available)
                    continue
                if ready_time > now:
                    return None
                heapq.heappop(self._available)
                queue = self._queues[host]
                _, _, url = heapq.heappop(queue)
                if not queue:
                    del self._queues[host]
                self._in_flight.add(host)
                return url
            return None

    def next_ready_time(self) -> Optional[float]:
        with self._lock:
            if not self._available:
                return None
            return self._available[0][0]

    def complete(self, host: str, delay: Optional[float] = None) -> None:
        """Signal that ``host`` finished its current fetch and may be
        scheduled again after ``delay`` seconds."""
        with self._lock:
            self._in_flight.discard(host)
            if host in self._queues and self._queues[host]:
                d = delay if delay is not None else self.default_delay
                heapq.heappush(self._available, (self._clock() + d, host))

    def pending(self) -> int:
        with self._lock:
            return sum(len(q) for q in self._queues.values())

    def in_flight(self) -> int:
        with self._lock:
            return len(self._in_flight)

    def __bool__(self) -> bool:
        return self.pending() > 0 or self.in_flight() > 0

    def __len__(self) -> int:
        return self.pending()


__all__ = ["Frontier"]
