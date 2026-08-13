"""Redis-backed per-client rate limiting for inbound messages.

Each client gets a fixed 60-second window counter in Redis (INCR, with
EXPIRE set only on the first increment of a window) so the limit is
enforced consistently across every NotificationServer instance sharing the
same Redis backbone, not just whichever process instance a given client
happens to be connected to.
"""

from __future__ import annotations


class RateLimiter:
    WINDOW_SECONDS = 60

    def __init__(self, redis, limit: int, namespace: str = "ns") -> None:
        self.redis = redis
        self.limit = limit
        self.ns = namespace

    def _key(self, client_id: str) -> str:
        return f"{self.ns}:ratelimit:{client_id}"

    async def allow(self, client_id: str) -> bool:
        """Increment the client's counter for the current window and report
        whether this message is within the configured per-minute limit."""
        key = self._key(client_id)
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, self.WINDOW_SECONDS)
        return count <= self.limit
