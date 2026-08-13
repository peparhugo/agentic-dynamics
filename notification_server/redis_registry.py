"""Redis-backed mirror of client connection/subscription state.

`ClientRegistry` only knows about clients connected to its own process. To
answer "is this client connected anywhere?" or "who's subscribed to this
channel, cluster-wide?" server instances mirror connect/disconnect and
subscribe/unsubscribe events into Redis. That shared state is what lets a
direct message be routed to a client attached to a different server
instance, and it survives an individual server process restarting.
"""
from __future__ import annotations

from typing import Any

CLIENTS_KEY = "ns:clients"
CHANNELS_KEY = "ns:channels"


def _channel_key(channel: str) -> str:
    return f"ns:channel:{channel}"


def _client_channels_key(client_id: str) -> str:
    return f"ns:client-channels:{client_id}"


def _decode(value: Any) -> str:
    return value.decode() if isinstance(value, bytes) else value


class RedisPresence:
    def __init__(self, redis_client: Any, server_id: str) -> None:
        self._redis = redis_client
        self.server_id = server_id

    async def add_client(self, client_id: str) -> None:
        await self._redis.hset(CLIENTS_KEY, client_id, self.server_id)

    async def remove_client(self, client_id: str) -> None:
        channels = await self._redis.smembers(_client_channels_key(client_id))
        for channel in channels:
            await self.unsubscribe(client_id, _decode(channel))
        await self._redis.hdel(CLIENTS_KEY, client_id)

    async def is_connected(self, client_id: str) -> bool:
        return bool(await self._redis.hexists(CLIENTS_KEY, client_id))

    async def count(self) -> int:
        return await self._redis.hlen(CLIENTS_KEY)

    async def subscribe(self, client_id: str, channel: str) -> None:
        await self._redis.sadd(_channel_key(channel), client_id)
        await self._redis.sadd(_client_channels_key(client_id), channel)
        await self._redis.sadd(CHANNELS_KEY, channel)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        await self._redis.srem(_channel_key(channel), client_id)
        await self._redis.srem(_client_channels_key(client_id), channel)
        remaining = await self._redis.scard(_channel_key(channel))
        if remaining == 0:
            await self._redis.srem(CHANNELS_KEY, channel)

    async def channels(self) -> dict[str, int]:
        names = await self._redis.smembers(CHANNELS_KEY)
        result = {}
        for raw_name in names:
            name = _decode(raw_name)
            result[name] = await self._redis.scard(_channel_key(name))
        return result

    async def channel_subscribers(self, channel: str) -> list[str]:
        members = await self._redis.smembers(_channel_key(channel))
        return sorted(_decode(m) for m in members)
