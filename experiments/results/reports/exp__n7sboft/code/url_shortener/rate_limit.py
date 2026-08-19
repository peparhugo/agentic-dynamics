from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class Window:
    started_at: float
    requests: int


class FixedWindowLimiter:
    """A process-local limiter; durable URL and analytics data remain in SQLite."""

    def __init__(self) -> None:
        self._windows: dict[str, Window] = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, duration: int) -> tuple[bool, int, int]:
        now = time.monotonic()
        with self._lock:
            window = self._windows.get(key)
            if window is None or now - window.started_at >= duration:
                window = Window(now, 0)
                self._windows[key] = window

            retry_after = max(1, int(duration - (now - window.started_at) + 0.999))
            if window.requests >= limit:
                return False, 0, retry_after

            window.requests += 1
            return True, limit - window.requests, retry_after
