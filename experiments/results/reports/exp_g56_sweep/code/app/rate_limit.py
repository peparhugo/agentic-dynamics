from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class LoginRateLimiter:
    def __init__(self, limit, window_seconds, clock=monotonic):
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self._attempts = defaultdict(deque)
        self._lock = Lock()

    def check(self, key):
        now = self.clock()
        cutoff = now - self.window_seconds
        with self._lock:
            attempts = self._attempts[key]
            while attempts and attempts[0] <= cutoff:
                attempts.popleft()
            if len(attempts) >= self.limit:
                retry_after = max(1, int(attempts[0] + self.window_seconds - now) + 1)
                return False, retry_after
            attempts.append(now)
            return True, None
