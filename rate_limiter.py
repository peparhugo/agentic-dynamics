"""Per-client rate limiting backed by Redis counters.

Uses a fixed-window counter keyed by client id and the current window
bucket (INCR + EXPIRE), so it works against both a real redis.asyncio
client and a fakeredis.aioredis client sharing the same async hash/set
API already used by RedisBackbone (see redis_backbone.py).
"""

from __future__ import annotations

import os
import time
from typing import Any

DEFAULT_RATE_LIMIT = 100
DEFAULT_WINDOW_SECONDS = 60


class RateLimiter:
    """Limits each client id to `limit` calls per `window_seconds`."""

    def __init__(
        self,
        client: Any,
        limit: int | None = None,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        self._client = client
        self.limit = limit if limit is not None else _limit_from_env()
        self.window_seconds = window_seconds

    @staticmethod
    def _key(client_id: str, bucket: int) -> str:
        return f"ratelimit:{client_id}:{bucket}"

    async def check(self, client_id: str) -> bool:
        """Record one call for `client_id` and report whether it's within the limit."""
        bucket = int(time.time() // self.window_seconds)
        key = self._key(client_id, bucket)
        count = await self._client.incr(key)
        if count == 1:
            await self._client.expire(key, self.window_seconds)
        return count <= self.limit


def _limit_from_env() -> int:
    return int(os.environ.get("RATE_LIMIT", DEFAULT_RATE_LIMIT))


def default_rate_limiter(limit: int | None = None) -> RateLimiter:
    """A self-contained RateLimiter backed by an in-memory fakeredis client.

    Used whenever no shared Redis client is configured, so rate limiting
    still works (per-process) without requiring a real Redis server.
    """
    from fakeredis import aioredis as fake_aioredis

    return RateLimiter(fake_aioredis.FakeRedis(), limit=limit)
