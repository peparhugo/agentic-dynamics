"""Redis pub/sub bus used to fan messages out across server instances.

Every server instance publishes routed message envelopes to a single Redis
channel and also subscribes to that same channel. Delivery to actual
WebSocket clients happens in each instance's subscription handler, so an
envelope published by instance A is received (and locally delivered) by
every instance, including A itself. That's what lets several server
processes share one notification backbone: only Redis needs to be reachable
by all of them, not the instances to each other.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger("notification_server.redis_bus")

CHANNEL = "notification_server:events"


class RedisBus:
    def __init__(self, redis_client: Any, channel: str = CHANNEL) -> None:
        self._redis = redis_client
        self._channel = channel
        self._pubsub = None
        self._listen_task: asyncio.Task | None = None

    async def start(self, handler: Callable[[dict], Awaitable[None]]) -> None:
        """Subscribe to the bus channel and start delivering messages to `handler`."""
        if self._listen_task is not None:
            return
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(self._channel)
        self._listen_task = asyncio.create_task(self._listen(handler))

    async def _listen(self, handler: Callable[[dict], Awaitable[None]]) -> None:
        assert self._pubsub is not None
        async for message in self._pubsub.listen():
            if message.get("type") != "message":
                continue
            data = message["data"]
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            try:
                envelope = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                logger.warning("dropping malformed bus message: %r", data)
                continue
            await handler(envelope)

    async def publish(self, envelope: dict) -> None:
        await self._redis.publish(self._channel, json.dumps(envelope))

    async def stop(self) -> None:
        if self._listen_task is not None:
            self._listen_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listen_task
            self._listen_task = None
        if self._pubsub is not None:
            with contextlib.suppress(Exception):
                await self._pubsub.unsubscribe(self._channel)
                await self._pubsub.aclose()
            self._pubsub = None
