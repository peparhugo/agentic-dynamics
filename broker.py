"""Redis pub/sub message backbone and shared client connection state."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Awaitable, Callable, Optional

try:
    import redis.asyncio as aioredis
except ImportError:  # pragma: no cover - redis is a declared dependency
    aioredis = None

REDIS_CHANNEL_PREFIX = "notif:"
BROADCAST_CHANNEL = "notif:broadcast"
CLIENTS_SET = "notif:clients"


def _redis_channel(channel: str, message_type: str) -> str:
    if message_type == "direct":
        return f"{REDIS_CHANNEL_PREFIX}direct:{channel}"
    if channel:
        return f"{REDIS_CHANNEL_PREFIX}channel:{channel}"
    return BROADCAST_CHANNEL


Handler = Callable[[str, dict], Awaitable[None]]


class RedisBroker:
    """Publishes messages to Redis and consumes messages from other instances.

    Every instance tags outgoing messages with a unique ``instance_id`` and
    ignores messages tagged with its own id, which prevents local echo and
    double delivery while still fanning messages out across every instance
    sharing the same Redis backbone.
    """

    def __init__(self, redis_url: Optional[str] = None, client=None) -> None:
        self.redis_url = redis_url
        self.instance_id = uuid.uuid4().hex
        self._client = client
        self._pubsub = None
        self._task: Optional[asyncio.Task] = None
        self._handler: Optional[Handler] = None

    @property
    def connected(self) -> bool:
        return self._client is not None

    async def connect(self) -> "RedisBroker":
        if aioredis is None:
            raise RuntimeError("redis package is not installed")
        if self._client is None:
            if not self.redis_url:
                raise ValueError("REDIS_URL is not configured")
            self._client = aioredis.Redis.from_url(
                self.redis_url, decode_responses=True
            )
        await self._client.ping()
        return self

    async def start_listener(self, handler: Handler) -> None:
        self._handler = handler
        self._pubsub = self._client.pubsub()
        await self._pubsub.psubscribe(f"{REDIS_CHANNEL_PREFIX}*")
        self._task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        try:
            async for message in self._pubsub.listen():
                if message.get("type") != "pmessage":
                    continue
                try:
                    data = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError):
                    continue
                if data.get("origin") == self.instance_id:
                    continue
                redis_channel = message.get("channel", "")
                if self._handler is not None:
                    await self._handler(redis_channel, data)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    async def publish(
        self,
        channel: str,
        message_type: str,
        payload: Optional[dict],
        timestamp: str,
    ) -> None:
        data = json.dumps(
            {
                "origin": self.instance_id,
                "channel": channel,
                "type": message_type,
                "payload": payload if payload is not None else {},
                "timestamp": timestamp,
            }
        )
        redis_channel = _redis_channel(channel, message_type)
        await self._client.publish(redis_channel, data)

    async def register_client(self, client_id: str) -> None:
        await self._client.sadd(CLIENTS_SET, client_id)
        await self._client.set(
            f"{REDIS_CHANNEL_PREFIX}client:{client_id}:instance", self.instance_id
        )

    async def unregister_client(self, client_id: str) -> None:
        await self._client.srem(CLIENTS_SET, client_id)
        await self._client.delete(
            f"{REDIS_CHANNEL_PREFIX}client:{client_id}:instance",
            f"{REDIS_CHANNEL_PREFIX}subs:{client_id}",
        )

    async def subscribe_client(self, client_id: str, channel: str) -> None:
        await self._client.sadd(f"{REDIS_CHANNEL_PREFIX}subs:{client_id}", channel)

    async def unsubscribe_client(self, client_id: str, channel: str) -> None:
        await self._client.srem(f"{REDIS_CHANNEL_PREFIX}subs:{client_id}", channel)

    async def connected_clients(self) -> set[str]:
        return await self._client.smembers(CLIENTS_SET)

    async def client_subscriptions(self, client_id: str) -> set[str]:
        return await self._client.smembers(f"{REDIS_CHANNEL_PREFIX}subs:{client_id}")

    async def client_instance(self, client_id: str) -> Optional[str]:
        return await self._client.get(
            f"{REDIS_CHANNEL_PREFIX}client:{client_id}:instance"
        )

    async def close(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        if self._pubsub is not None:
            try:
                await self._pubsub.aclose()
            except Exception:
                pass
            self._pubsub = None
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None
