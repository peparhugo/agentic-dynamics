import time
from collections import defaultdict
from threading import Lock


class RateLimiter:
    def __init__(self):
        self._store = defaultdict(list)
        self._lock = Lock()

    def is_rate_limited(self, key, max_requests, window_seconds):
        now = time.time()
        with self._lock:
            self._store[key] = [t for t in self._store[key] if now - t < window_seconds]
            if len(self._store[key]) >= max_requests:
                return True
            self._store[key].append(now)
            return False

    def reset(self, key=None):
        with self._lock:
            if key:
                self._store.pop(key, None)
            else:
                self._store.clear()


rate_limiter = RateLimiter()
