"""
Redis pub/sub message broker and client-state store.

The broker is the shared backbone for the notification server:

- Outgoing application messages are published to Redis pub/sub channels.
- Every server instance runs a subscriber ("worker") that receives those
  messages and delivers them to its locally-connected WebSocket clients.
- Client connection state (unique IDs, metadata, subscriptions) is stored in
  Redis so it survives server restarts and is shared across instances.

Channel layout
--------------
- ``notify:broadcast``        — global broadcast to every connected client.
- ``notify:channel:{name}``   — a message targeting a named channel.
- ``notify:direct:{client}``  — a message targeting a single client.

Every instance subscribes to the ``notify:*`` pattern and routes incoming
messages locally.

Client state keys
-----------------
- ``notify:next_client_id``            — monotonic counter for globally unique IDs.
- ``notify:clients``                   — set of active client IDs.
- ``notify:client:{id}``               — hash: instance_id, connected_at.
- ``notify:client:{id}:channels``      — set of channel names the client joined.
- ``notify:subscriptions:{channel}``   — set of client IDs subscribed to a channel.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, List, Optional

BROADCAST_CHANNEL = "notify:broadcast"
CHANNEL_PREFIX = "notify:channel:"
DIRECT_PREFIX = "notify:direct:"
SUBSCRIBE_PATTERN = "notify:*"

CLIENT_COUNTER_KEY = "notify:next_client_id"
CLIENTS_KEY = "notify:clients"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_redis(redis_url: Optional[str] = None):
    """Return an async Redis client.

    Uses a real Redis server when ``redis_url`` is provided (the value of the
    ``REDIS_URL`` env var), otherwise falls back to an in-process fakeredis
    instance so the server works without external infrastructure.
    """
    if redis_url:
        import redis.asyncio as aioredis

        return aioredis.Redis.from_url(redis_url, decode_responses=True)

    import fakeredis.aioredis as aioredis

    return aioredis.FakeRedis(decode_responses=True)


def client_key(client_id: int) -> str:
    return f"notify:client:{client_id}"


def client_channels_key(client_id: int) -> str:
    return f"notify:client:{client_id}:channels"


def subscriptions_key(channel: str) -> str:
    return f"notify:subscriptions:{channel}"


class MessageBroker:
    """Async wrapper around Redis pub/sub plus client-state persistence."""

    def __init__(
        self,
        redis: Any = None,
        redis_url: Optional[str] = None,
    ) -> None:
        if redis is not None:
            self._redis = redis
        else:
            self._redis = create_redis(redis_url or os.environ.get("REDIS_URL"))
        self._owns_redis = redis is None

    @property
    def redis(self) -> Any:
        return self._redis

    # ── Pub/sub ───────────────────────────────────────────────

    async def publish(self, channel: str, message: str) -> None:
        await self._redis.publish(channel, message)

    def pubsub(self) -> Any:
        return self._redis.pubsub()

    # ── Client state ──────────────────────────────────────────

    async def next_client_id(self) -> int:
        return int(await self._redis.incr(CLIENT_COUNTER_KEY))

    async def register_client(self, client_id: int, instance_id: str) -> None:
        pipe = self._redis.pipeline()
        pipe.sadd(CLIENTS_KEY, str(client_id))
        pipe.hset(
            client_key(client_id),
            mapping={"instance_id": instance_id, "connected_at": utcnow()},
        )
        await pipe.execute()

    async def unregister_client(self, client_id: int) -> None:
        pipe = self._redis.pipeline()
        pipe.srem(CLIENTS_KEY, str(client_id))
        pipe.delete(client_key(client_id))
        pipe.delete(client_channels_key(client_id))
        await pipe.execute()

    async def subscribe_client(self, client_id: int, channel: str) -> None:
        pipe = self._redis.pipeline()
        pipe.sadd(subscriptions_key(channel), str(client_id))
        pipe.sadd(client_channels_key(client_id), channel)
        await pipe.execute()

    async def unsubscribe_client(self, client_id: int, channel: str) -> None:
        pipe = self._redis.pipeline()
        pipe.srem(subscriptions_key(channel), str(client_id))
        pipe.srem(client_channels_key(client_id), channel)
        await pipe.execute()

    async def client_ids(self) -> List[str]:
        return sorted(await self._redis.smembers(CLIENTS_KEY))

    async def client_info(self, client_id: int) -> dict:
        return await self._redis.hgetall(client_key(client_id))

    async def close(self) -> None:
        if self._owns_redis:
            await self._redis.aclose()


RATE_LIMIT_KEY_PREFIX = "notify:rate:"


class RateLimiter:
    """Fixed-window rate limiter backed by Redis counters.

    Each client gets a per-minute window key.  The counter is incremented
    atomically with :meth:`~redis.Redis.incr` and expires shortly after the
    window ends so stale keys do not accumulate.
    """

    def __init__(self, redis: Any, limit: int = 100) -> None:
        self._redis = redis
        self.limit = max(0, int(limit))

    async def allow(self, client_id: int) -> bool:
        """Return ``True`` if the client may send another message this minute."""
        if self.limit == 0:
            return False
        window = int(time.time() // 60)
        key = f"{RATE_LIMIT_KEY_PREFIX}{client_id}:{window}"
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, 120)
        return count <= self.limit
