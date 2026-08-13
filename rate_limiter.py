"""Rate limiting for message handling using Redis."""

import logging
import os
from typing import Optional
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter for messages per client using Redis counters."""

    def __init__(self, redis_url: Optional[str] = None, limit: int = 100):
        self.redis_url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379")
        self.limit = int(os.environ.get("RATE_LIMIT", str(limit)))
        self.redis: Optional[redis.Redis] = None
        self.window_seconds = 60

    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            self.redis = await redis.from_url(self.redis_url)
            await self.redis.ping()
            logger.info(f"Rate limiter connected to Redis")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis for rate limiter: {e}")
            self.redis = None

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.aclose()

    async def check_rate_limit(self, client_id: str) -> tuple[bool, int]:
        """
        Check if client has exceeded rate limit.

        Returns:
            (is_allowed, remaining_messages)
        """
        if not self.redis:
            return True, self.limit

        try:
            key = f"rate_limit:{client_id}"
            current = await self.redis.incr(key)

            if current == 1:
                await self.redis.expire(key, self.window_seconds)

            remaining = max(0, self.limit - current)
            is_allowed = current <= self.limit

            return is_allowed, remaining
        except Exception as e:
            logger.error(f"Error checking rate limit for {client_id}: {e}")
            return True, self.limit

    async def reset_client(self, client_id: str) -> None:
        """Reset rate limit counter for a client."""
        if not self.redis:
            return

        try:
            key = f"rate_limit:{client_id}"
            await self.redis.delete(key)
        except Exception as e:
            logger.error(f"Error resetting rate limit for {client_id}: {e}")
