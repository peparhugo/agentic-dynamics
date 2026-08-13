"""Per-client message rate limiting backed by Redis counters.

Each client gets a fixed-window counter keyed by client id: the first message
in a window sets the key's TTL to the window length, every message after
that increments it, and once the count exceeds the configured limit further
messages in that window are rejected. The window resets automatically when
the Redis key expires, so no separate cleanup is needed.
"""
from __future__ import annotations

import os
from typing import Any

DEFAULT_LIMIT = 100
DEFAULT_WINDOW_SECONDS = 60


class RateLimiter:
    def __init__(
        self,
        redis_client: Any,
        limit: int = DEFAULT_LIMIT,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        self._redis = redis_client
        self.limit = limit
        self.window_seconds = window_seconds

    @classmethod
    def from_env(cls, redis_client: Any) -> "RateLimiter":
        limit = int(os.environ.get("RATE_LIMIT", DEFAULT_LIMIT))
        return cls(redis_client, limit=limit)

    def _key(self, client_id: str) -> str:
        return f"ratelimit:{client_id}"

    async def allow(self, client_id: str) -> bool:
        """Record one message from `client_id`; return False once the limit is exceeded."""
        key = self._key(client_id)
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, self.window_seconds)
        return count <= self.limit
