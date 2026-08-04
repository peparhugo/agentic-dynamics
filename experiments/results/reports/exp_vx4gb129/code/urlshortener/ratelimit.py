import time
import threading
from collections import defaultdict


class TokenBucket:
    def __init__(self, rate: float, burst: int):
        self.rate = rate
        self.burst = burst
        self.tokens: defaultdict[str, float] = defaultdict(lambda: float(burst))
        self.last_refill: defaultdict[str, float] = defaultdict(time.monotonic)
        self.lock = threading.Lock()

    def consume(self, key: str, cost: int = 1) -> bool:
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill[key]
            self.tokens[key] = min(
                self.burst, self.tokens[key] + elapsed * self.rate
            )
            self.last_refill[key] = now

            if self.tokens[key] >= cost:
                self.tokens[key] -= cost
                return True
            return False

    def prune(self, ttl: float = 300.0):
        now = time.monotonic()
        with self.lock:
            stale = [
                k
                for k, t in self.last_refill.items()
                if now - t > ttl and self.tokens[k] >= self.burst
            ]
            for k in stale:
                del self.tokens[k]
                del self.last_refill[k]


bucket = TokenBucket(rate=10.0, burst=20)


def check_rate_limit(ip: str) -> bool:
    return bucket.consume(ip)
