import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class _Window:
    timestamps: list[float] = field(default_factory=list)


class RateLimiter:
    def __init__(self, max_requests: int = 30, window_seconds: float = 60.0):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._buckets: dict[str, _Window] = defaultdict(_Window)

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        window = self._buckets[key]
        cutoff = now - self._window_seconds

        window.timestamps = [t for t in window.timestamps if t > cutoff]

        if len(window.timestamps) >= self._max_requests:
            return False

        window.timestamps.append(now)
        return True

    def remaining(self, key: str) -> int:
        now = time.monotonic()
        window = self._buckets[key]
        cutoff = now - self._window_seconds
        window.timestamps = [t for t in window.timestamps if t > cutoff]
        return max(0, self._max_requests - len(window.timestamps))
