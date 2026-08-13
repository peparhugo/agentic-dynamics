"""
Redis pub/sub backbone for the notification server.

Responsibilities:
- Serve as the message bus.  Servers publish JSON message envelopes to a
  shared Redis pub/sub channel; every server instance runs a worker that
  subscribes to that channel and delivers the messages to its locally
  connected clients.  This lets multiple server instances share one
  backbone.
- Persist client connection state (connected client ids and channel
  memberships) in Redis so the state survives server restarts and is
  shared between instances.

Connection string comes from the ``REDIS_URL`` environment variable.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import redis.asyncio as aioredis


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RedisBackend:
    """Thin wrapper around a redis.asyncio client for pub/sub + state."""

    def __init__(self, url: str, namespace: str = "notify") -> None:
        self.url = url
        self.namespace = namespace
        self.messages_channel = f"{namespace}:messages"
        self._redis: aioredis.Redis | None = None

    # ── Connection ─────────────────────────────────────────────────

    async def connect(self) -> "RedisBackend":
        self._redis = aioredis.Redis.from_url(self.url, decode_responses=True)
        await self._redis.ping()
        return self

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.close()
            self._redis = None

    async def flush(self) -> None:
        if self._redis is None:
            return
        keys = await self._redis.keys(f"{self.namespace}:*")
        if keys:
            await self._redis.delete(*keys)

    def pubsub(self):
        if self._redis is None:
            raise RuntimeError("RedisBackend is not connected")
        return self._redis.pubsub()

    # ── Pub/sub ────────────────────────────────────────────────────

    async def publish(self, envelope: dict) -> None:
        if self._redis is None:
            raise RuntimeError("RedisBackend is not connected")
        await self._redis.publish(self.messages_channel, json.dumps(envelope))

    # ── Key helpers ────────────────────────────────────────────────

    def _client_key(self, client_id: str) -> str:
        return f"{self.namespace}:client:{client_id}"

    def _channel_key(self, channel: str) -> str:
        return f"{self.namespace}:channel:{channel}"

    def _ratelimit_key(self, client_id: str) -> str:
        return f"{self.namespace}:ratelimit:{client_id}"

    @property
    def _clients_set(self) -> str:
        return f"{self.namespace}:clients"

    @property
    def _channels_set(self) -> str:
        return f"{self.namespace}:channels"

    @property
    def _seq_key(self) -> str:
        return f"{self.namespace}:client_seq"

    # ── Client connection state ────────────────────────────────────

    async def next_client_id(self) -> str:
        """Return a globally unique client id (shared across instances)."""
        if self._redis is None:
            raise RuntimeError("RedisBackend is not connected")
        return str(await self._redis.incr(self._seq_key))

    async def register_client(self, client_id: str, server_id: str) -> None:
        pipe = self._redis.pipeline()
        pipe.sadd(self._clients_set, client_id)
        pipe.hset(
            self._client_key(client_id),
            mapping={"server_id": server_id, "connected_at": _now_iso()},
        )
        await pipe.execute()

    async def unregister_client(self, client_id: str) -> None:
        pipe = self._redis.pipeline()
        pipe.srem(self._clients_set, client_id)
        pipe.delete(self._client_key(client_id))
        await pipe.execute()

    async def client_exists(self, client_id: str) -> bool:
        return bool(await self._redis.sismember(self._clients_set, client_id))

    async def client_info(self, client_id: str) -> dict | None:
        info = await self._redis.hgetall(self._client_key(client_id))
        return info or None

    async def global_clients(self) -> set[str]:
        return set(await self._redis.smembers(self._clients_set))

    async def global_channels(self) -> set[str]:
        return set(await self._redis.smembers(self._channels_set))

    async def global_channel_members(self, channel: str) -> set[str]:
        return set(await self._redis.smembers(self._channel_key(channel)))

    async def add_channel_member(self, client_id: str, channel: str) -> None:
        pipe = self._redis.pipeline()
        pipe.sadd(self._channels_set, channel)
        pipe.sadd(self._channel_key(channel), client_id)
        await pipe.execute()

    async def remove_channel_member(self, client_id: str, channel: str) -> None:
        await self._redis.srem(self._channel_key(channel), client_id)
        if not await self._redis.scard(self._channel_key(channel)):
            pipe = self._redis.pipeline()
            pipe.delete(self._channel_key(channel))
            pipe.srem(self._channels_set, channel)
            await pipe.execute()

    # ── Rate limiting ─────────────────────────────────────────────────

    async def rate_limit_allow(
        self, client_id: str, limit: int, window: int = 60
    ) -> bool:
        """Sliding-window per-client rate limit check.

        Returns ``True`` when *client_id* has sent fewer than *limit* messages
        in the last *window* seconds.  Request timestamps are kept in a sorted
        set per client, so the counters are shared across server instances.
        A rejected request does not consume quota; once the window has rolled
        over the client is allowed again.
        """
        if self._redis is None:
            raise RuntimeError("RedisBackend is not connected")
        key = self._ratelimit_key(client_id)
        now = time.time()
        # Single round trip: prune the window, record the current request,
        # refresh the TTL and read back the resulting count.
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, int(window))
        pipe.zcard(key)
        results = await pipe.execute()
        return int(results[3]) <= limit

    async def rate_limit_record(self, client_id: str, window: int = 60) -> None:
        """Record one request from *client_id* into its Redis counter."""
        if self._redis is None:
            raise RuntimeError("RedisBackend is not connected")
        key = self._ratelimit_key(client_id)
        now = time.time()
        pipe = self._redis.pipeline()
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, int(window))
        await pipe.execute()
