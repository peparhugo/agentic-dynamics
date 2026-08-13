"""Redis-backed per-client rate limiter.

Each client gets a counter key namespaced by client id and the current fixed
60-second window (`floor(time / 60)`); the key is set to expire 60 seconds
after its first increment, so stale windows clean themselves up without a
separate sweep. Because the counter lives in Redis rather than an in-process
dict, the limit is enforced cluster-wide across every `NotificationServer`
instance sharing the same Redis backend, consistent with `RedisClientState`.
"""
from __future__ import annotations

import time
from typing import Any

WINDOW_SECONDS = 60
KEY_PREFIX = "ns:ratelimit:"


class RateLimiter:
    def __init__(self, client: Any, limit: int) -> None:
        self.client = client
        self.limit = limit

    async def allow(self, client_id: str) -> bool:
        """Record one message from `client_id` and report whether it's
        within the limit for the current window."""
        window = int(time.time() // WINDOW_SECONDS)
        key = f"{KEY_PREFIX}{client_id}:{window}"
        count = await self.client.incr(key)
        if count == 1:
            await self.client.expire(key, WINDOW_SECONDS)
        return count <= self.limit
