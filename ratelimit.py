"""Per-client rate limiting backed by Redis counters (with a local fallback)."""

import os
import time
from collections import defaultdict, deque
from typing import Optional

WINDOW_SECONDS = 60


class RateLimiter:
    """Common interface for a per-client rate limiter."""

    async def check(self, client_id: int) -> bool:  # pragma: no cover
        raise NotImplementedError


class RedisRateLimiter(RateLimiter):
    """Fixed-window rate limiter using Redis INCR/EXPIRE counters."""

    def __init__(self, client, limit: int) -> None:
        self._client = client
        self._limit = limit

    async def check(self, client_id: int) -> bool:
        minute = int(time.time()) // 60
        key = f"ratelimit:{client_id}:{minute}"
        count = await self._client.incr(key)
        if count == 1:
            await self._client.expire(key, WINDOW_SECONDS * 2)
        return count <= self._limit


class LocalRateLimiter(RateLimiter):
    """In-process fixed-window rate limiter for standalone operation."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._events: dict[int, deque] = defaultdict(deque)

    async def check(self, client_id: int) -> bool:
        now = time.monotonic()
        events = self._events[client_id]
        while events and now - events[0] > WINDOW_SECONDS:
            events.popleft()
        if len(events) < self._limit:
            events.append(now)
            return True
        return False


def make_rate_limiter(
    redis_url: Optional[str] = None,
    client=None,
    limit: Optional[int] = None,
) -> RateLimiter:
    """Build a rate limiter from RATE_LIMIT, an injected Redis client, or local fallback."""
    if limit is None:
        limit = int(os.environ.get("RATE_LIMIT", "100"))
    if client is not None:
        return RedisRateLimiter(client, limit)
    if redis_url:
        import redis.asyncio as aioredis

        return RedisRateLimiter(aioredis.from_url(redis_url), limit)
    return LocalRateLimiter(limit)
