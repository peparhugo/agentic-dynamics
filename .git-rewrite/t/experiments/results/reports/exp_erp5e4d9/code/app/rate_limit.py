from time import time
from threading import Lock

# Simple in-memory fixed-window rate limiter per key (IP).
class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max = max_requests
        self.window = window_seconds
        self.storage = {}  # key -> (window_start, count)
        self.lock = Lock()

    def allow(self, key: str) -> bool:
        now = int(time())
        window_start = now - (now % self.window)
        with self.lock:
            start, count = self.storage.get(key, (window_start, 0))
            if start != window_start:
                # new window
                self.storage[key] = (window_start, 1)
                return True
            if count < self.max:
                self.storage[key] = (start, count + 1)
                return True
            return False
