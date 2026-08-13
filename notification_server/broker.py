"""Redis pub/sub broker: the message backbone between server instances.

The server publishes every outgoing message to a Redis channel; a background
worker task (started via `start()`) pattern-subscribes to that channel
namespace and hands each message to a callback that delivers it to the
locally-connected WebSocket clients. Multiple `NotificationServer` instances
pointed at the same Redis backend therefore share one message backbone: a
message published by any instance is delivered by every instance's worker.
"""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

import redis.asyncio as redis_asyncio

from .config import redis_url as default_redis_url

MessageHandler = Callable[[str, str], Awaitable[None]]


class RedisBroker:
    def __init__(self, url: str | None = None, client: Any = None) -> None:
        """`client` may be injected (e.g. a fakeredis FakeAsyncRedis) for
        tests; otherwise a real redis.asyncio client is built from `url`."""
        self._owns_client = client is None
        self.client = (
            client
            if client is not None
            else redis_asyncio.from_url(url or default_redis_url(), decode_responses=True)
        )
        self._pubsub = None
        self._listen_task: asyncio.Task | None = None

    async def publish(self, channel: str, data: str) -> None:
        await self.client.publish(channel, data)

    async def start(self, pattern: str, handler: MessageHandler) -> None:
        """Start the worker: pattern-subscribe and dispatch messages to `handler`."""
        if self._listen_task is not None:
            return
        self._pubsub = self.client.pubsub()
        await self._pubsub.psubscribe(pattern)
        self._listen_task = asyncio.create_task(self._listen(handler))

    async def _listen(self, handler: MessageHandler) -> None:
        assert self._pubsub is not None
        async for message in self._pubsub.listen():
            if message.get("type") != "pmessage":
                continue
            await handler(message["channel"], message["data"])

    async def stop(self) -> None:
        if self._listen_task is not None:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None
        if self._pubsub is not None:
            await self._pubsub.aclose()
            self._pubsub = None
        if self._owns_client:
            await self.client.aclose()
