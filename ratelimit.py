"""
Per-client message rate limiting for the notification server.

Limits are enforced per client-ID using Redis counters (``INCR`` on a key
that holds the message count for the current fixed time window), so counters
are shared by every server instance connected to the same Redis. When no
``REDIS_URL`` is configured, an in-process counter map is used so the server
keeps working out of the box (matching the LocalBroker fallback).

Configuration:

- ``RATE_LIMIT`` - maximum messages per client per window (default: 100).
"""

from __future__ import annotations

import os
import time

KEY_PREFIX = "notifications:"
DEFAULT_RATE_LIMIT = 100
DEFAULT_WINDOW_SECONDS = 60


def default_rate_limit() -> int:
    """Read the per-client message limit from the ``RATE_LIMIT`` env var."""
    raw = (os.environ.get("RATE_LIMIT") or "").strip()
    if not raw:
        return DEFAULT_RATE_LIMIT
    try:
        return max(int(raw), 1)
    except ValueError:
        return DEFAULT_RATE_LIMIT


class RateLimiter:
    """Per-client fixed-window rate limiter.

    When a Redis client is supplied the counters live in Redis
    (``{prefix}rl:{client_id}:{window}``); otherwise an in-process map of
    ``client_id -> (window, count)`` is used.
    """

    def __init__(
        self,
        limit: int | None = None,
        window: int = DEFAULT_WINDOW_SECONDS,
        redis=None,
        prefix: str | None = None,
    ) -> None:
        self.limit = limit if limit is not None else default_rate_limit()
        self.window = window
        self._redis = redis
        self._prefix = prefix or KEY_PREFIX
        # client_id -> (window_start, count) for the in-process fallback.
        self._mem: dict[str, tuple[int, int]] = {}

    def _key(self, client_id: str) -> str:
        window = int(time.time() // self.window)
        return f"{self._prefix}rl:{client_id}:{window}"

    async def allow(self, client_id: str) -> bool:
        """Register one message attempt; False when the limit is exceeded."""
        if self._redis is not None:
            key = self._key(client_id)
            current = await self._redis.incr(key)
            if current == 1:
                await self._redis.expire(key, self.window)
            return current <= self.limit

        now = int(time.monotonic() // self.window)
        window, count = self._mem.get(client_id, (now, 0))
        if window != now:
            window, count = now, 0
        count += 1
        self._mem[client_id] = (window, count)
        if len(self._mem) > 1024:
            self._prune(now)
        return count <= self.limit

    def _prune(self, now: int) -> None:
        stale = [cid for cid, (w, _) in self._mem.items() if now - w > 2]
        for cid in stale:
            del self._mem[cid]

    async def reset(self, client_id: str | None = None) -> None:
        """Delete counters; used mostly by tests."""
        if self._redis is not None:
            pattern = (
                f"{self._prefix}rl:{client_id}:*"
                if client_id is not None
                else f"{self._prefix}rl:*"
            )
            async for key in self._redis.scan_iter(match=pattern):
                await self._redis.delete(key)
            return
        if client_id is None:
            self._mem.clear()
        else:
            self._mem.pop(client_id, None)

    async def close(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass


def default_rate_limiter() -> RateLimiter:
    """Build the limiter configured by the ``RATE_LIMIT``/``REDIS_URL`` env vars."""
    limit = default_rate_limit()
    url = (os.environ.get("REDIS_URL") or "").strip()
    if url:
        from redis.asyncio import Redis

        redis = Redis.from_url(url, decode_responses=True)
        return RateLimiter(limit=limit, redis=redis)
    return RateLimiter(limit=limit)
