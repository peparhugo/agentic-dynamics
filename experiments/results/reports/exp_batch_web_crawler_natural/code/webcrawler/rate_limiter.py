"""Rate limiting and per-host crawl politeness.

A crawler that hammers a single host will be blocked and is impolite.
Two complementary mechanisms are provided:

* :class:`TokenBucket` -- a token-bucket limiter with a configurable refill
  rate and burst capacity, usable both as a *global* limiter (aggregate
  requests per second across the whole crawl) and per-host.

* :class:`HostPoliteness` -- enforces a minimum interval between requests to
  each host (honouring ``Crawl-delay`` from robots.txt or a default).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Callable, Dict, Optional


class TokenBucket:
    """A token-bucket rate limiter.

    ``rate`` is the sustainable rate in tokens/sec; ``capacity`` is the
    burst size.  ``acquire`` returns the number of seconds to wait (0.0 if
    a token is immediately available).
    """

    def __init__(self, rate: float, capacity: Optional[float] = None):
        if rate <= 0:
            raise ValueError("rate must be > 0")
        self.rate = float(rate)
        self.capacity = float(capacity if capacity is not None else rate)
        self._tokens = self.capacity
        self._updated = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self, now: float) -> None:
        elapsed = now - self._updated
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._updated = now

    def acquire(self) -> float:
        with self._lock:
            now = time.monotonic()
            self._refill(now)
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return 0.0
            needed = 1.0 - self._tokens
            wait = needed / self.rate
            # Advance the virtual clock so a burst of waiters queue up
            # rather than all firing at once.
            self._tokens = 0.0
            self._updated = now + wait
            return wait

    def try_acquire(self) -> bool:
        with self._lock:
            now = time.monotonic()
            self._refill(now)
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False


class HostPoliteness:
    """Enforces a minimum delay between requests to each host.

    ``delay_provider`` is an optional callable ``host -> seconds`` used to
    look up the polite delay (e.g. robots.txt ``Crawl-delay``).  When absent,
    ``default_delay`` applies to every host.
    """

    def __init__(
        self,
        default_delay: float = 1.0,
        delay_provider: Optional[Callable[[str], Optional[float]]] = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.default_delay = default_delay
        self.delay_provider = delay_provider
        self._clock = clock
        self._last: Dict[str, float] = defaultdict(lambda: float("-inf"))
        self._lock = threading.Lock()

    def delay_for(self, host: str) -> float:
        if self.delay_provider is not None:
            d = self.delay_provider(host)
            if d is not None:
                return float(d)
        return self.default_delay

    def wait_time(self, host: str) -> float:
        """Return seconds to sleep before fetching ``host`` (non-mutating)."""
        delay = self.delay_for(host)
        with self._lock:
            now = self._clock()
            return max(0.0, self._last[host] + delay - now)

    def acquire(self, host: str) -> float:
        """Record the current request to ``host`` and return the number of
        seconds the caller should sleep first (0.0 if none)."""
        delay = self.delay_for(host)
        with self._lock:
            now = self._clock()
            wait = max(0.0, self._last[host] + delay - now)
            self._last[host] = now + wait
            return wait


__all__ = ["TokenBucket", "HostPoliteness"]
