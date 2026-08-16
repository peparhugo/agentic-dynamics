"""
Redis-backed message backbone for the notification server.

Delivering a message to a WebSocket client only works if that client is
connected to *this* process. Once a deployment runs more than one server
instance, a client publishing a broadcast needs a way to reach clients
connected to sibling instances too. RedisBackbone provides that hand-off:

* Every instance publishes outgoing broadcast/direct envelopes onto a single
  Redis pub/sub channel (the "bus").
* Every instance also subscribes to that same channel. Each subscriber acts
  as a worker: it receives every envelope published by any instance
  (including its own) and hands it to a local delivery callback, which is
  responsible for ignoring envelopes that originated from itself (since
  same-instance delivery already happened synchronously and directly).
* Client connection state (which client is on which instance) and channel
  subscription membership are mirrored into plain Redis keys as they change,
  so that state is visible cluster-wide and does not evaporate if a single
  instance restarts -- a fresh process can immediately see who else is
  connected across the deployment instead of starting from a blank slate.
"""

from __future__ import annotations

import json
import time
from typing import AsyncIterator, Optional

BUS_CHANNEL = "notif:bus"
CLIENTS_KEY = "notif:clients"
CHANNEL_INDEX_KEY = "notif:channels:index"
RATE_LIMIT_WINDOW_SECONDS = 60


def _channel_key(channel: str) -> str:
    return f"notif:channel:{channel}"


def _client_channels_key(client_id: str) -> str:
    return f"notif:client-channels:{client_id}"


def _rate_limit_key(client_id: str, window: int) -> str:
    return f"notif:ratelimit:{client_id}:{window}"


class RedisBackbone:
    """Wraps a redis.asyncio-compatible client with the operations the
    notification server needs: a pub/sub bus plus mirrored connection and
    subscription state. Accepts any client exposing the redis-py asyncio
    API (a real `redis.asyncio.Redis`, or a drop-in test double such as
    `fakeredis.aioredis.FakeRedis`)."""

    def __init__(self, client, instance_id: str) -> None:
        self.client = client
        self.instance_id = instance_id

    # ── Pub/sub bus ────────────────────────────────────────────────

    async def publish(self, envelope: dict) -> None:
        envelope = {**envelope, "origin_instance": self.instance_id}
        await self.client.publish(BUS_CHANNEL, json.dumps(envelope))

    async def listen(self) -> AsyncIterator[dict]:
        """Yield every envelope published on the bus, forever, including
        ones this same instance published. Callers must check
        `origin_instance` themselves if they want to skip self-originated
        envelopes they already handled synchronously."""
        pubsub = self.client.pubsub()
        await pubsub.subscribe(BUS_CHANNEL)
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    continue
        finally:
            await pubsub.unsubscribe(BUS_CHANNEL)
            await pubsub.aclose()

    # ── Client connection state ────────────────────────────────────

    async def register_client(self, client_id: str) -> None:
        await self.client.hset(CLIENTS_KEY, client_id, self.instance_id)

    async def unregister_client(self, client_id: str) -> None:
        await self.client.hdel(CLIENTS_KEY, client_id)

    async def client_instance(self, client_id: str) -> Optional[str]:
        value = await self.client.hget(CLIENTS_KEY, client_id)
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else value

    async def connected_clients(self) -> dict[str, str]:
        raw = await self.client.hgetall(CLIENTS_KEY)
        result = {}
        for key, value in raw.items():
            key = key.decode("utf-8") if isinstance(key, bytes) else key
            value = value.decode("utf-8") if isinstance(value, bytes) else value
            result[key] = value
        return result

    # ── Channel subscription state ─────────────────────────────────

    async def subscribe_channel(self, channel: str, client_id: str) -> None:
        await self.client.sadd(_channel_key(channel), client_id)
        await self.client.sadd(_client_channels_key(client_id), channel)
        await self.client.sadd(CHANNEL_INDEX_KEY, channel)

    async def unsubscribe_channel(self, channel: str, client_id: str) -> None:
        await self.client.srem(_channel_key(channel), client_id)
        await self.client.srem(_client_channels_key(client_id), channel)
        remaining = await self.client.scard(_channel_key(channel))
        if remaining == 0:
            await self.client.srem(CHANNEL_INDEX_KEY, channel)

    async def unsubscribe_all_channels(self, client_id: str) -> None:
        channels_key = _client_channels_key(client_id)
        raw_channels = await self.client.smembers(channels_key)
        for channel in raw_channels:
            channel = channel.decode("utf-8") if isinstance(channel, bytes) else channel
            await self.unsubscribe_channel(channel, client_id)
        await self.client.delete(channels_key)

    async def channel_subscribers(self, channel: str) -> list[str]:
        raw = await self.client.smembers(_channel_key(channel))
        members = [m.decode("utf-8") if isinstance(m, bytes) else m for m in raw]
        return sorted(members)

    async def channels(self) -> dict[str, int]:
        raw = await self.client.smembers(CHANNEL_INDEX_KEY)
        names = [n.decode("utf-8") if isinstance(n, bytes) else n for n in raw]
        result = {}
        for name in names:
            result[name] = await self.client.scard(_channel_key(name))
        return result

    # ── Rate limiting ───────────────────────────────────────────────

    async def check_rate_limit(
        self, client_id: str, limit: int, window_seconds: int = RATE_LIMIT_WINDOW_SECONDS
    ) -> bool:
        """Increment client_id's counter for the current fixed window and
        report whether they're still within `limit` messages for that
        window. The counter lives in Redis (not per-instance memory) so the
        limit is enforced per client ID cluster-wide, no matter which server
        instance the client's messages land on. Returns True if the message
        is allowed, False if the client has exceeded the limit."""
        window = int(time.time() // window_seconds)
        key = _rate_limit_key(client_id, window)
        count = await self.client.incr(key)
        if count == 1:
            await self.client.expire(key, window_seconds * 2)
        return count <= limit


def create_redis_client(redis_url: str):
    """Build a real redis.asyncio client for the given URL. Kept as a thin
    wrapper so callers (and tests) can swap in a fake client without
    importing redis.asyncio directly."""
    import redis.asyncio as redis_asyncio

    return redis_asyncio.from_url(redis_url)
