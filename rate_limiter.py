"""
Rate limiter for per-client message rate limiting using Redis.
"""

import redis
import os
from datetime import datetime, timedelta, timezone


class RateLimiter:
    """Rate limiter using Redis counters."""

    def __init__(self, redis_url: str = "redis://localhost:6379", rate_limit: int | None = None):
        self.redis_url = redis_url
        self.rate_limit = rate_limit or int(os.getenv("RATE_LIMIT", "100"))
        self.client = redis.from_url(redis_url)
        self.window_seconds = 60

    def _get_key(self, client_id: str) -> str:
        """Generate Redis key for client rate limit counter."""
        now = datetime.now(timezone.utc)
        minute = now.strftime("%Y-%m-%d-%H-%M")
        return f"ratelimit:{client_id}:{minute}"

    def is_allowed(self, client_id: str) -> bool:
        """Check if client is allowed to send a message."""
        key = self._get_key(client_id)
        count = self.client.get(key)

        if count is None:
            self.client.setex(key, self.window_seconds, 1)
            return True

        count = int(count)
        if count < self.rate_limit:
            self.client.incr(key)
            return True

        return False

    def get_remaining(self, client_id: str) -> int:
        """Get remaining messages for client in current minute."""
        key = self._get_key(client_id)
        count = self.client.get(key)

        if count is None:
            return self.rate_limit

        count = int(count)
        return max(0, self.rate_limit - count)

    def close(self) -> None:
        """Close the Redis connection."""
        self.client.close()
