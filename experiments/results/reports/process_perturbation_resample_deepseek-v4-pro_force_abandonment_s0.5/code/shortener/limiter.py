import time


class TokenBucket:
    def __init__(self, capacity, rate, now=None):
        self.capacity = float(capacity)
        self.rate = float(rate)
        self.tokens = self.capacity
        self._now = now or time.monotonic
        self.last = self._now()

    def allow(self, n=1):
        now = self._now()
        elapsed = now - self.last
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last = now
        if self.tokens >= n:
            self.tokens -= n
            return True, 0.0
        retry = (n - self.tokens) / self.rate if self.rate > 0 else float("inf")
        return False, retry


class Limiter:
    def __init__(self, now=None):
        self._now = now
        self._buckets = {}

    def hit(self, key, capacity, rate, n=1):
        bucket = self._buckets.get(key)
        if bucket is None or bucket.capacity != capacity or bucket.rate != rate:
            bucket = TokenBucket(capacity, rate, now=self._now)
            self._buckets[key] = bucket
        return bucket.allow(n)

    def reset(self):
        self._buckets.clear()
