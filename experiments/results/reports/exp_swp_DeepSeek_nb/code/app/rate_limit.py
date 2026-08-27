import threading
import time


class RateLimiter:
    def __init__(self, limit, window):
        self.limit = limit
        self.window = window
        self._attempts = {}
        self._lock = threading.Lock()

    def _now(self):
        return time.monotonic()

    def _key(self, identifier):
        return str(identifier)

    def reset(self, identifier=None):
        with self._lock:
            if identifier is None:
                self._attempts.clear()
            else:
                self._attempts.pop(self._key(identifier), None)

    def is_allowed(self, identifier):
        key = self._key(identifier)
        now = self._now()
        with self._lock:
            timestamps = [t for t in self._attempts.get(key, []) if now - t < self.window]
            if len(timestamps) < self.limit:
                timestamps.append(now)
                self._attempts[key] = timestamps
                return True
            self._attempts[key] = timestamps
            return False

    def remaining(self, identifier):
        key = self._key(identifier)
        now = self._now()
        with self._lock:
            timestamps = [t for t in self._attempts.get(key, []) if now - t < self.window]
            return max(0, self.limit - len(timestamps))
