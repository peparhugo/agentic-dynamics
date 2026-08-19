import threading
import time


class RateLimiter:
    """Fixed-window rate limiter keyed by arbitrary identifiers."""

    def __init__(self, limit, window_seconds):
        self.limit = limit
        self.window = window_seconds
        self._counts = {}
        self._lock = threading.Lock()

    def allow(self, key):
        now = time.time()
        window_start = now - (now % self.window)
        with self._lock:
            entry = self._counts.get(key)
            if entry is None or entry[0] != window_start:
                self._counts[key] = (window_start, 1)
                return True, 1, self.limit, 0
            count = entry[1]
            if count >= self.limit:
                retry_after = max(1, int(self.window - (now - window_start)))
                return False, count, self.limit, retry_after
            self._counts[key] = (window_start, count + 1)
            return True, count + 1, self.limit, 0
