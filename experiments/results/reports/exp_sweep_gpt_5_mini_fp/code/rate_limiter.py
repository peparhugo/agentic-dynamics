from collections import deque
from time import time

class RateLimiter:
    def __init__(self, calls=5, period=60):
        self.calls = calls
        self.period = period
        self.store = {}

    def allow(self, key):
        now = time()
        dq = self.store.get(key)
        if not dq:
            dq = deque()
            self.store[key] = dq
        while dq and dq[0] <= now - self.period:
            dq.popleft()
        if len(dq) >= self.calls:
            return False
        dq.append(now)
        return True

rate_limiter = RateLimiter()
