import time
from collections import defaultdict, deque

from flask import request


def get_client_ip():
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


class RateLimiter:
    def __init__(self, max_attempts=5, window_seconds=60):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits = defaultdict(deque)

    def _prune(self, key, now):
        q = self._hits[key]
        cutoff = now - self.window_seconds
        while q and q[0] <= cutoff:
            q.popleft()

    def hit(self, key):
        now = time.monotonic()
        self._prune(key, now)
        self._hits[key].append(now)

    def is_limited(self, key):
        now = time.monotonic()
        self._prune(key, now)
        return len(self._hits[key]) >= self.max_attempts

    def retry_after(self, key):
        q = self._hits[key]
        if not q:
            return 0
        now = time.monotonic()
        return max(1, int(q[0] + self.window_seconds - now) + 1)

    def reset(self):
        self._hits.clear()
