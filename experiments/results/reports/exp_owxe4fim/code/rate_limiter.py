import time
import threading

class RateLimitExceeded(Exception):
    pass

class RateLimiter:
    def __init__(self, limit=10, window=60):
        self.limit = limit
        self.window = window
        self.counters = {}  # key -> (window_start, count)
        self._lock = threading.Lock()

    def allow_request(self, key):
        now = int(time.time())
        window_start = now - (now % self.window)
        with self._lock:
            start, count = self.counters.get(key, (window_start, 0))
            if start != window_start:
                # reset for new window
                start, count = window_start, 0
            if count >= self.limit:
                self.counters[key] = (start, count)
                return False
            self.counters[key] = (start, count + 1)
            return True
