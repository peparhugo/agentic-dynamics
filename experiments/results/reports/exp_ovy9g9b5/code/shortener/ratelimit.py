"""Simple in-memory sliding-window rate limiter keyed by client identity."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    """Allow at most ``max_requests`` per ``window_seconds`` per key."""

    def __init__(self, max_requests: int = 10, window_seconds: float = 60.0) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        """Record a hit for ``key`` and return True if it is within limits."""
        ts = time.monotonic() if now is None else now
        cutoff = ts - self.window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return False
            hits.append(ts)
            return True

    def remaining(self, key: str, now: float | None = None) -> int:
        ts = time.monotonic() if now is None else now
        cutoff = ts - self.window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            return max(0, self.max_requests - len(hits))

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)
