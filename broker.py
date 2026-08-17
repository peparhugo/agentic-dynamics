"""
Message broker abstraction over Redis pub/sub.

Two implementations:
- RedisBroker: publishes to and subscribes from a Redis instance (or any
  Redis-compatible client such as fakeredis). Used when REDIS_URL is set or a
  client is injected.
- LocalBroker: an in-process fallback with the same interface, used when no
  Redis connection is configured. Keeps the server fully functional standalone.
"""

import asyncio
import json
from typing import Awaitable, Callable, Optional

MessageHandler = Callable[[dict], Awaitable[None]]


class Broker:
    """Common interface for a pub/sub message broker."""

    async def publish(self, channel: str, message: dict) -> None:  # pragma: no cover
        raise NotImplementedError

    async def subscribe(self, channels: list[str], handler: MessageHandler):
        raise NotImplementedError  # pragma: no cover

    async def set_client_state(self, client_id: int, state: dict) -> None:  # pragma: no cover
        raise NotImplementedError

    async def del_client_state(self, client_id: int) -> None:  # pragma: no cover
        raise NotImplementedError

    async def all_client_states(self) -> dict:  # pragma: no cover
        raise NotImplementedError

    async def close(self) -> None:  # pragma: no cover
        raise NotImplementedError


class RedisBroker(Broker):
    """Redis-backed broker. Stores client connection state in a Redis hash."""

    CLIENT_STATE_KEY = "notification:clients"

    def __init__(self, client) -> None:
        self._client = client
        self._pubsub = None
        self._task: Optional[asyncio.Task] = None

    async def publish(self, channel: str, message: dict) -> None:
        await self._client.publish(channel, json.dumps(message))

    async def subscribe(self, channels: list[str], handler: MessageHandler):
        self._pubsub = self._client.pubsub()
        await self._pubsub.subscribe(*channels)
        self._task = asyncio.create_task(self._run(handler))
        return self._task

    async def _run(self, handler: MessageHandler) -> None:
        try:
            async for msg in self._pubsub.listen():
                if msg["type"] == "message":
                    data = msg["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    await handler(json.loads(data))
        except asyncio.CancelledError:
            raise
        except Exception:
            return

    async def set_client_state(self, client_id: int, state: dict) -> None:
        await self._client.hset(self.CLIENT_STATE_KEY, str(client_id), json.dumps(state))

    async def del_client_state(self, client_id: int) -> None:
        await self._client.hdel(self.CLIENT_STATE_KEY, str(client_id))

    async def all_client_states(self) -> dict:
        raw = await self._client.hgetall(self.CLIENT_STATE_KEY)
        return {
            int(key.decode() if isinstance(key, bytes) else key): json.loads(
                value.decode() if isinstance(value, bytes) else value
            )
            for key, value in raw.items()
        }

    async def close(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._pubsub is not None:
            try:
                await self._pubsub.aclose()
            except Exception:
                pass
            self._pubsub = None


class LocalBroker(Broker):
    """In-process broker with Redis-compatible client-state storage (a dict)."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[MessageHandler]] = {}
        self._client_states: dict[int, dict] = {}

    async def publish(self, channel: str, message: dict) -> None:
        for handler in list(self._subscribers.get(channel, ())):
            await handler(message)

    async def subscribe(self, channels: list[str], handler: MessageHandler):
        for channel in channels:
            self._subscribers.setdefault(channel, []).append(handler)
        return None

    async def set_client_state(self, client_id: int, state: dict) -> None:
        self._client_states[client_id] = state

    async def del_client_state(self, client_id: int) -> None:
        self._client_states.pop(client_id, None)

    async def all_client_states(self) -> dict:
        return dict(self._client_states)

    async def close(self) -> None:
        self._subscribers.clear()
        self._client_states.clear()


def make_broker(redis_url: Optional[str] = None, client=None) -> Broker:
    """Build a broker from REDIS_URL, an injected client, or a local fallback."""
    if client is not None:
        return RedisBroker(client)
    if redis_url:
        import redis.asyncio as aioredis

        return RedisBroker(aioredis.from_url(redis_url))
    return LocalBroker()
