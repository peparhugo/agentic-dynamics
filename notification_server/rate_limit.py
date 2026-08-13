"""Per-client rate limiting, enforced via Redis fixed-window counters so the
limit is shared correctly across every server instance a client's messages
might land on.

Each client gets `limit` messages per WINDOW_SECONDS-second window. The first
message in a window creates a counter key with a matching TTL; every message
after that increments it. Once the counter exceeds the limit, further
messages in that window are rejected (the caller is expected to send the
client an error reply rather than silently dropping the message).
"""

import os

DEFAULT_RATE_LIMIT = 100
WINDOW_SECONDS = 60
KEY_PREFIX = "notification_server:ratelimit"


def resolve_rate_limit(rate_limit=None) -> int:
    if rate_limit is not None:
        return int(rate_limit)
    env_value = os.environ.get("RATE_LIMIT")
    if env_value:
        return int(env_value)
    return DEFAULT_RATE_LIMIT


class RateLimiter:
    def __init__(self, client, limit=None, window_seconds=WINDOW_SECONDS):
        self.client = client
        self.limit = resolve_rate_limit(limit)
        self.window_seconds = window_seconds

    async def allow(self, client_id: str) -> bool:
        """Record one message from `client_id` and report whether it is
        within the limit for the current window."""
        key = f"{KEY_PREFIX}:{client_id}"
        count = await self.client.incr(key)
        if count == 1:
            await self.client.expire(key, self.window_seconds)
        return count <= self.limit
