import time
import threading
from collections import defaultdict


class RateLimiter:
    def __init__(self, window_seconds=60, max_requests=10):
        self.window = window_seconds
        self.max = max_requests
        self._buckets = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, key):
        now = time.time()
        with self._lock:
            bucket = self._buckets[key]
            cutoff = now - self.window
            while bucket and bucket[0] < cutoff:
                bucket.pop(0)
            if len(bucket) >= self.max:
                return False
            bucket.append(now)
            return True

    def remaining(self, key):
        now = time.time()
        with self._lock:
            bucket = self._buckets[key]
            cutoff = now - self.window
            while bucket and bucket[0] < cutoff:
                bucket.pop(0)
            return max(0, self.max - len(bucket))

    def reset(self):
        with self._lock:
            self._buckets.clear()


_rate_limiter = RateLimiter(window_seconds=60, max_requests=30)


def limit_shorten(ip):
    return _rate_limiter.is_allowed(f"shorten:{ip}")


def get_shorten_remaining(ip):
    return _rate_limiter.remaining(f"shorten:{ip}")
