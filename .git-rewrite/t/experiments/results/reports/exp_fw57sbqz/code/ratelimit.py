import threading
import time
from collections import defaultdict


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _decay(self, key: str, now: float) -> None:
        cutoff = now - self.window_seconds
        self._buckets[key] = [t for t in self._buckets[key] if t > cutoff]

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            self._decay(key, now)
            if len(self._buckets[key]) >= self.max_requests:
                return False
            self._buckets[key].append(now)
            return True

    def remaining(self, key: str) -> int:
        now = time.monotonic()
        with self._lock:
            self._decay(key, now)
            used = len(self._buckets[key])
            return max(0, self.max_requests - used)

    def reset(self, key: str) -> None:
        with self._lock:
            self._buckets.pop(key, None)

    def cleanup(self, max_age_seconds: float = 300) -> None:
        now = time.monotonic()
        with self._lock:
            stale = [
                k for k, ts_list in self._buckets.items()
                if not ts_list or max(ts_list) < now - max_age_seconds
            ]
            for k in stale:
                del self._buckets[k]
