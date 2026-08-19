import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    """In-memory sliding-window-log rate limiter, keyed per client identifier."""

    def __init__(self, max_requests, window_seconds):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key):
        now = time.time()
        with self._lock:
            hits = self._hits[key]
            cutoff = now - self.window_seconds
            while hits and hits[0] < cutoff:
                hits.popleft()

            if len(hits) >= self.max_requests:
                retry_after = self.window_seconds - (now - hits[0])
                return False, max(retry_after, 0)

            hits.append(now)
            return True, 0

    def reset(self):
        with self._lock:
            self._hits.clear()
