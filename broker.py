"""Message broker and shared client-state implementations."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from redis.asyncio import Redis

DeliveryHandler = Callable[[dict[str, Any]], Awaitable[None]]


class Broker(Protocol):
    async def start(self, handler: DeliveryHandler) -> None: ...

    async def close(self) -> None: ...

    async def publish(self, delivery: dict[str, Any]) -> None: ...

    async def add_client(self, client_id: str) -> None: ...

    async def remove_client(self, client_id: str) -> None: ...

    async def subscribe_client(self, client_id: str, channel: str) -> None: ...

    async def unsubscribe_client(self, client_id: str, channel: str) -> None: ...

    async def client_exists(self, client_id: str) -> bool: ...

    async def is_subscribed(self, client_id: str, channel: str) -> bool: ...

    async def connected_count(self) -> int: ...

    async def channels(self) -> dict[str, int]: ...

    async def subscribers(self, channel: str) -> list[str]: ...


class LocalBroker:
    """In-process fallback used when Redis isn't configured."""

    def __init__(self) -> None:
        self._handler: DeliveryHandler | None = None
        self._clients: set[str] = set()
        self._channels: dict[str, set[str]] = {}

    async def start(self, handler: DeliveryHandler) -> None:
        self._handler = handler

    async def close(self) -> None:
        self._handler = None

    async def publish(self, delivery: dict[str, Any]) -> None:
        if self._handler is not None:
            await self._handler(delivery)

    async def add_client(self, client_id: str) -> None:
        self._clients.add(client_id)

    async def remove_client(self, client_id: str) -> None:
        self._clients.discard(client_id)
        for channel in list(self._channels):
            self._channels[channel].discard(client_id)
            if not self._channels[channel]:
                del self._channels[channel]

    async def subscribe_client(self, client_id: str, channel: str) -> None:
        if client_id in self._clients:
            self._channels.setdefault(channel, set()).add(client_id)

    async def unsubscribe_client(self, client_id: str, channel: str) -> None:
        subscribers = self._channels.get(channel)
        if subscribers is not None:
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    async def client_exists(self, client_id: str) -> bool:
        return client_id in self._clients

    async def is_subscribed(self, client_id: str, channel: str) -> bool:
        return client_id in self._channels.get(channel, set())

    async def connected_count(self) -> int:
        return len(self._clients)

    async def channels(self) -> dict[str, int]:
        return {
            channel: len(subscribers)
            for channel, subscribers in sorted(self._channels.items())
        }

    async def subscribers(self, channel: str) -> list[str]:
        return sorted(self._channels.get(channel, set()))


class RedisBroker:
    """Redis pub/sub transport with Redis-backed connection metadata."""

    PUBSUB_CHANNEL = "notifications:messages"
    CLIENTS_KEY = "notifications:clients"
    CHANNELS_KEY = "notifications:channels"

    def __init__(self, url: str | None = None, client: Redis | None = None) -> None:
        if client is None and url is None:
            raise ValueError("a Redis URL or client is required")
        self._redis = client or Redis.from_url(url, decode_responses=True)
        self._owns_client = client is None
        self._pubsub: Any = None
        self._listener: asyncio.Task[None] | None = None

    @staticmethod
    def _channel_key(channel: str) -> str:
        return f"notifications:channel:{channel}"

    @staticmethod
    def _client_channels_key(client_id: str) -> str:
        return f"notifications:client:{client_id}:channels"

    async def start(self, handler: DeliveryHandler) -> None:
        if self._listener is not None and not self._listener.done():
            return
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(self.PUBSUB_CHANNEL)
        self._listener = asyncio.create_task(self._listen(handler))

    async def _listen(self, handler: DeliveryHandler) -> None:
        assert self._pubsub is not None
        try:
            async for item in self._pubsub.listen():
                if item["type"] != "message":
                    continue
                data = item["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                await handler(json.loads(data))
        except asyncio.CancelledError:
            raise

    async def close(self) -> None:
        if self._listener is not None:
            self._listener.cancel()
            await asyncio.gather(self._listener, return_exceptions=True)
            self._listener = None
        if self._pubsub is not None:
            await self._pubsub.aclose()
            self._pubsub = None
        if self._owns_client:
            await self._redis.aclose()

    async def publish(self, delivery: dict[str, Any]) -> None:
        await self._redis.publish(
            self.PUBSUB_CHANNEL, json.dumps(delivery, separators=(",", ":"))
        )

    async def add_client(self, client_id: str) -> None:
        await self._redis.hset(self.CLIENTS_KEY, client_id, "connected")

    async def remove_client(self, client_id: str) -> None:
        client_channels_key = self._client_channels_key(client_id)
        channels = await self._redis.smembers(client_channels_key)
        async with self._redis.pipeline(transaction=True) as pipeline:
            pipeline.hdel(self.CLIENTS_KEY, client_id)
            for channel in channels:
                pipeline.srem(self._channel_key(channel), client_id)
            pipeline.delete(client_channels_key)
            await pipeline.execute()
        await self._remove_empty_channels(channels)

    async def subscribe_client(self, client_id: str, channel: str) -> None:
        async with self._redis.pipeline(transaction=True) as pipeline:
            pipeline.sadd(self._channel_key(channel), client_id)
            pipeline.sadd(self._client_channels_key(client_id), channel)
            pipeline.sadd(self.CHANNELS_KEY, channel)
            await pipeline.execute()

    async def unsubscribe_client(self, client_id: str, channel: str) -> None:
        async with self._redis.pipeline(transaction=True) as pipeline:
            pipeline.srem(self._channel_key(channel), client_id)
            pipeline.srem(self._client_channels_key(client_id), channel)
            await pipeline.execute()
        await self._remove_empty_channels({channel})

    async def _remove_empty_channels(self, channels: set[str]) -> None:
        for channel in channels:
            if not await self._redis.exists(self._channel_key(channel)):
                await self._redis.srem(self.CHANNELS_KEY, channel)

    async def client_exists(self, client_id: str) -> bool:
        return bool(await self._redis.hexists(self.CLIENTS_KEY, client_id))

    async def is_subscribed(self, client_id: str, channel: str) -> bool:
        return bool(await self._redis.sismember(self._channel_key(channel), client_id))

    async def connected_count(self) -> int:
        return int(await self._redis.hlen(self.CLIENTS_KEY))

    async def channels(self) -> dict[str, int]:
        channels = sorted(await self._redis.smembers(self.CHANNELS_KEY))
        counts: dict[str, int] = {}
        for channel in channels:
            count = int(await self._redis.scard(self._channel_key(channel)))
            if count:
                counts[channel] = count
        return counts

    async def subscribers(self, channel: str) -> list[str]:
        return sorted(await self._redis.smembers(self._channel_key(channel)))
