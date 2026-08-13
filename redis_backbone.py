"""
Redis pub/sub backbone for the notification server.

Wraps a redis.asyncio-compatible client (the real thing, or a
fakeredis.aioredis client sharing a FakeServer in tests) to give the
notification server two capabilities:

  * message distribution — publish() puts an envelope on a shared Redis
    channel; every server instance that called start() with a dispatch
    callback receives it and can deliver to its own locally-connected
    clients. This is what lets multiple server processes share one
    logical notification bus.
  * client presence — set_client_state()/clear_client_state() mirror
    each client's connection bookkeeping into Redis so that presence
    information isn't lost if a given server process restarts; any
    other process sharing the same Redis instance can still see it.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

DEFAULT_CHANNEL = "notifications:backbone"
CLIENT_STATE_TTL_SECONDS = 3600

DispatchCallback = Callable[[dict], Awaitable[None]]


class RedisBackbone:
    """Publishes/subscribes notification envelopes and tracks client state in Redis."""

    def __init__(
        self,
        client: Any,
        server_id: str,
        channel: str = DEFAULT_CHANNEL,
    ) -> None:
        self._client = client
        self.server_id = server_id
        self._channel = channel
        self._pubsub: Any | None = None
        self._listen_task: asyncio.Task | None = None

    async def publish(self, envelope: dict) -> None:
        await self._client.publish(self._channel, json.dumps(envelope))

    async def start(self, on_message: DispatchCallback) -> None:
        """Subscribe to the shared channel and begin dispatching messages in the background."""
        self._pubsub = self._client.pubsub()
        await self._pubsub.subscribe(self._channel)
        self._listen_task = asyncio.create_task(self._listen(on_message))

    async def _listen(self, on_message: DispatchCallback) -> None:
        assert self._pubsub is not None
        async for raw in self._pubsub.listen():
            if raw.get("type") != "message":
                continue
            try:
                envelope = json.loads(raw["data"])
            except (json.JSONDecodeError, TypeError):
                logger.warning("dropping malformed redis backbone message: %r", raw.get("data"))
                continue
            try:
                await on_message(envelope)
            except Exception:
                logger.exception("error dispatching redis backbone message")

    async def stop(self) -> None:
        if self._listen_task is not None:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None
        if self._pubsub is not None:
            await self._pubsub.unsubscribe(self._channel)
            await self._pubsub.close()
            self._pubsub = None

    # ── client connection state ──────────────────────────────────────
    #
    # Stored under `client:{client_id}` as a Redis hash so any process
    # sharing this Redis instance can see who is connected and to which
    # server, independent of any single process's in-memory registry.

    @staticmethod
    def _state_key(client_id: str) -> str:
        return f"client:{client_id}"

    async def set_client_state(self, client_id: str, **fields: str) -> None:
        key = self._state_key(client_id)
        await self._client.hset(key, mapping={"server_id": self.server_id, **fields})
        await self._client.expire(key, CLIENT_STATE_TTL_SECONDS)
        await self._client.sadd("clients:active", client_id)

    async def clear_client_state(self, client_id: str) -> None:
        await self._client.delete(self._state_key(client_id))
        await self._client.srem("clients:active", client_id)

    async def get_client_state(self, client_id: str) -> dict[str, str] | None:
        raw = await self._client.hgetall(self._state_key(client_id))
        if not raw:
            return None
        return {_decode(k): _decode(v) for k, v in raw.items()}

    async def active_client_count(self) -> int:
        return await self._client.scard("clients:active")


def _decode(value: Any) -> str:
    return value.decode() if isinstance(value, bytes) else value
