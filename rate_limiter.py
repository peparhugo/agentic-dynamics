"""Per-client message rate limiting.

Limits are enforced per client ID. When a Redis client is available the
counter lives in Redis as a fixed-window counter (shared across every server
instance); otherwise a local in-memory sliding window is used as a fallback so
limiting still works for single-process deployments.

The limit is configured through the ``RATE_LIMIT`` environment variable
(default: 100 messages per minute). A value of ``0`` disables limiting.
"""

import logging
import time

log = logging.getLogger(__name__)

DEFAULT_RATE_LIMIT = 100
WINDOW_SECONDS = 60
KEY_PREFIX = "notif:rl:"


class RateLimiter:
    """Fixed-window rate limiter keyed by client ID.

    ``limit`` is the maximum number of messages a client may send within a
    window of ``window_seconds`` seconds. A ``limit`` <= 0 disables limiting.
    """

    def __init__(self, limit: int = DEFAULT_RATE_LIMIT,
                 window_seconds: int = WINDOW_SECONDS,
                 redis_client=None) -> None:
        self.limit = max(0, int(limit))
        self.window_seconds = max(1, int(window_seconds))
        self._redis = redis_client
        self._memory: dict[str, list[float]] = {}

    def set_redis(self, redis_client) -> None:
        """Point the limiter at a Redis client once it is connected."""
        self._redis = redis_client

    def _key(self, client_id: str, bucket: int) -> str:
        return f"{KEY_PREFIX}{client_id}:{bucket}"

    async def allow(self, client_id: str) -> bool:
        """Return True when a client may send another message."""
        if self.limit <= 0:
            return True
        if self._redis is not None:
            return await self._allow_redis(client_id)
        return self._allow_memory(client_id)

    async def _allow_redis(self, client_id: str) -> bool:
        """Increment a fixed-window Redis counter for the client."""
        bucket = int(time.time()) // self.window_seconds
        key = self._key(client_id, bucket)
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, self.window_seconds)
        return count <= self.limit

    def _allow_memory(self, client_id: str) -> bool:
        """In-memory sliding-window fallback for the same semantics."""
        now = time.time()
        cutoff = now - self.window_seconds
        stamps = [t for t in self._memory.get(client_id, []) if t > cutoff]
        if len(stamps) >= self.limit:
            self._memory[client_id] = stamps
            return False
        stamps.append(now)
        self._memory[client_id] = stamps
        return True
