"""In-memory fixed-window rate limiter keyed by client identifier."""

import threading
import time


class RateLimiter:
    """Fixed-window counter limiter.

    Thread-safe and dependency-free. Clients are keyed by an arbitrary
    string (normally the request IP address).
    """

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        stale = [k for k, (start, _) in self._windows.items()
                 if now - start >= self.window_seconds]
        for k in stale:
            del self._windows[k]

    def allow(self, key: str) -> bool:
        """Return True if ``key`` may proceed, otherwise False."""
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            start, count = self._windows.get(key, (now, 0))
            if now - start >= self.window_seconds:
                start, count = now, 0
            if count >= self.max_requests:
                return False
            self._windows[key] = (start, count + 1)
            return True

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()
