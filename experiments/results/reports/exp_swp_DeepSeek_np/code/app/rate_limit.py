import threading
import time


class RateLimiter:
    """A simple thread-safe, in-memory fixed-window rate limiter."""

    def __init__(self, max_attempts=5, window=60):
        self.max_attempts = max_attempts
        self.window = window
        self._lock = threading.Lock()
        self._store = {}

    def allow(self, key):
        now = time.monotonic()
        with self._lock:
            window_start, count = self._store.get(key, (now, 0))
            if now - window_start >= self.window:
                window_start, count = now, 0
            if count >= self.max_attempts:
                retry_after = self.window - (now - window_start)
                self._store[key] = (window_start, count)
                return False, max(0.0, retry_after)
            count += 1
            self._store[key] = (window_start, count)
            return True, 0.0

    def reset(self):
        with self._lock:
            self._store.clear()

    def reset_key(self, key):
        with self._lock:
            self._store.pop(key, None)
