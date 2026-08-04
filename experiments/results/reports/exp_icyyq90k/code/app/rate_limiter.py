import time
import asyncio
from collections import defaultdict


class SlidingWindowRateLimiter:
    """Sliding-window rate limiter per key (IP address)."""

    def __init__(self, max_requests: int = 10, window_seconds: float = 60.0):
        self._max = max_requests
        self._window = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str) -> bool:
        async with self._lock:
            now = time.monotonic()
            bucket = self._buckets[key]
            cutoff = now - self._window

            while bucket and bucket[0] < cutoff:
                bucket.pop(0)

            if len(bucket) >= self._max:
                return False

            bucket.append(now)
            return True
