"""Per-client rate limiting for inbound messages.

Uses a fixed 60-second window keyed by client ID and the window's start
minute. Mirrors the pattern used elsewhere in this codebase (`RedisBus`,
`ClientRegistry`): pass a redis(.asyncio)-compatible client to share
counters across every server instance behind the same broker, so a client's
limit is enforced cluster-wide rather than per-process. Omit it to fall back
to local in-memory counters, which keeps single-instance/test use working
with no Redis configured at all.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

DEFAULT_LIMIT = 100
WINDOW_SECONDS = 60


def _key(client_id: str, window: int) -> str:
    return f"notification_server:ratelimit:{client_id}:{window}"


class RateLimiter:
    def __init__(self, redis_client: Any = None, limit: int = DEFAULT_LIMIT) -> None:
        self._redis = redis_client
        self.limit = limit
        self._local_window = self._current_window()
        self._local_counts: dict[str, int] = defaultdict(int)

    @staticmethod
    def _current_window() -> int:
        return int(time.time()) // WINDOW_SECONDS

    async def check(self, client_id: str) -> bool:
        """Record one message from `client_id` and report whether it's still within the limit.

        Returns True if the message is allowed, False if `client_id` has
        already hit `limit` messages in the current 60-second window. Every
        call counts, including ones that return False, so a client stuck
        over the limit keeps getting rejected until the window rolls over.
        """
        window = self._current_window()
        if self._redis is not None:
            key = _key(client_id, window)
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, WINDOW_SECONDS)
            return count <= self.limit

        if window != self._local_window:
            self._local_window = window
            self._local_counts.clear()
        self._local_counts[client_id] += 1
        return self._local_counts[client_id] <= self.limit
