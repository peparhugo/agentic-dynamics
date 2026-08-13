"""Redis pub/sub broker for cross-instance message delivery.

A server instance that accepts a broadcast or direct message doesn't deliver
it straight to its own locally-connected clients; it publishes a routed
envelope to a shared Redis channel instead. Every server instance (including
the publisher) runs a worker task that subscribes to that same channel and
hands each envelope to a delivery callback, which matches it against that
instance's own local client registry. This is what lets several server
processes share one message backbone: a message accepted by any instance
reaches clients connected to any other instance too.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

DEFAULT_CHANNEL = "notification-server:messages"

EnvelopeHandler = Callable[[dict[str, Any]], Awaitable[None]]


class RedisBroker:
    def __init__(self, redis_client: Any, channel: str = DEFAULT_CHANNEL) -> None:
        self._redis = redis_client
        self.channel = channel
        self._pubsub = None
        self._worker_task: asyncio.Task | None = None

    async def publish(self, envelope: dict[str, Any]) -> None:
        await self._redis.publish(self.channel, json.dumps(envelope))

    async def start(self, on_envelope: EnvelopeHandler) -> None:
        """Subscribe to the shared channel and start delivering envelopes."""
        if self._worker_task is not None:
            return
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(self.channel)
        self._worker_task = asyncio.create_task(self._listen(on_envelope))

    async def _listen(self, on_envelope: EnvelopeHandler) -> None:
        pubsub = self._pubsub
        assert pubsub is not None
        async for raw in pubsub.listen():
            if raw.get("type") != "message":
                continue
            try:
                envelope = json.loads(raw["data"])
            except (TypeError, ValueError):
                logger.warning("dropping malformed envelope from redis: %r", raw.get("data"))
                continue
            try:
                await on_envelope(envelope)
            except Exception:
                logger.exception("error delivering envelope from redis")

    async def stop(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
            self._worker_task = None
        if self._pubsub is not None:
            await self._pubsub.unsubscribe(self.channel)
            await self._pubsub.aclose()
            self._pubsub = None
