"""Redis pub/sub backend used as the message-distribution backbone.

Each server instance publishes outgoing messages to a shared Redis channel.
A background "worker" loop in every instance (including the publisher's own
process) subscribes to that channel and relays messages to whichever clients
are connected locally. This lets multiple server processes share one
backbone: a message published by any instance reaches clients connected to
any other instance.

Client connection presence (which server a client is attached to) is stored
in a Redis hash so it survives the restart of any single server process and
is visible to every instance.

When REDIS_URL is not configured, an in-memory fake Redis (fakeredis) is used
instead of a real broker so the server keeps working standalone (e.g. local
dev, tests) without requiring a Redis deployment.
"""

import json
import os

import fakeredis.aioredis as fakeredis_asyncio
import redis.asyncio as redis_asyncio

DEFAULT_CHANNEL = "notification_server:events"
CLIENTS_KEY = "notification_server:clients"


def make_redis_client(redis_url=None):
    redis_url = redis_url or os.environ.get("REDIS_URL")
    if redis_url:
        return redis_asyncio.from_url(redis_url, decode_responses=True)
    return fakeredis_asyncio.FakeRedis(decode_responses=True)


class RedisBackend:
    """Wraps a Redis client with the pub/sub channel and presence hash used
    by NotificationServer."""

    def __init__(self, client, channel=DEFAULT_CHANNEL):
        self.client = client
        self.channel = channel
        self._pubsub = None

    # ── pub/sub ──────────────────────────────────────────────────

    async def publish(self, envelope: dict) -> None:
        await self.client.publish(self.channel, json.dumps(envelope))

    async def subscribe(self):
        self._pubsub = self.client.pubsub()
        await self._pubsub.subscribe(self.channel)
        return self._pubsub

    async def listen(self):
        """Yield decoded envelopes published on the channel. Must be called
        after subscribe()."""
        if self._pubsub is None:
            await self.subscribe()
        async for message in self._pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                yield json.loads(message["data"])
            except (TypeError, ValueError):
                continue

    async def close(self, close_client=True) -> None:
        if self._pubsub is not None:
            await self._pubsub.unsubscribe(self.channel)
            await self._pubsub.aclose()
            self._pubsub = None
        if close_client:
            await self.client.aclose()

    # ── client presence (shared across instances, survives restarts) ──

    async def register_client(self, client_id: str, server_id: str) -> None:
        await self.client.hset(CLIENTS_KEY, client_id, json.dumps({"server_id": server_id}))

    async def unregister_client(self, client_id: str) -> None:
        await self.client.hdel(CLIENTS_KEY, client_id)

    async def get_client_server(self, client_id: str):
        raw = await self.client.hget(CLIENTS_KEY, client_id)
        if raw is None:
            return None
        return json.loads(raw)["server_id"]

    async def all_clients(self) -> dict:
        raw = await self.client.hgetall(CLIENTS_KEY)
        return {client_id: json.loads(value)["server_id"] for client_id, value in raw.items()}
