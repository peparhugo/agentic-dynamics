"""Redis-backed client connection state.

Which clients are connected and which channels they're subscribed to is
mirrored into Redis (rather than kept only in an in-process dict) so that
state is shared across multiple server instances and survives a server
restart -- a fresh process pointed at the same Redis backend sees the same
picture. Actual WebSocket objects still live only in the local process (they
can't be shared across processes); this store tracks presence/subscription
*metadata*, which is what the REST endpoints (`/health`, `/channels`, ...)
report.
"""
from __future__ import annotations

from typing import Any

CLIENTS_KEY = "ns:clients"
CHANNELS_KEY = "ns:channels"


def _channel_key(channel: str) -> str:
    return f"ns:channel:{channel}:subscribers"


class RedisClientState:
    def __init__(self, client: Any) -> None:
        self.client = client

    async def add_client(self, client_id: str) -> None:
        await self.client.sadd(CLIENTS_KEY, client_id)

    async def remove_client(self, client_id: str) -> None:
        await self.client.srem(CLIENTS_KEY, client_id)

    async def is_connected(self, client_id: str) -> bool:
        return bool(await self.client.sismember(CLIENTS_KEY, client_id))

    async def count(self) -> int:
        return await self.client.scard(CLIENTS_KEY)

    async def subscribe(self, channel: str, client_id: str) -> None:
        await self.client.sadd(_channel_key(channel), client_id)
        await self.client.sadd(CHANNELS_KEY, channel)

    async def unsubscribe(self, channel: str, client_id: str) -> None:
        key = _channel_key(channel)
        await self.client.srem(key, client_id)
        if await self.client.scard(key) == 0:
            await self.client.srem(CHANNELS_KEY, channel)

    async def unsubscribe_all(self, client_id: str) -> None:
        channels = await self.client.smembers(CHANNELS_KEY)
        for channel in channels:
            await self.unsubscribe(channel, client_id)

    async def channel_subscribers(self, channel: str) -> list[str]:
        members = await self.client.smembers(_channel_key(channel))
        return sorted(members)

    async def all_channels(self) -> dict[str, int]:
        channels = await self.client.smembers(CHANNELS_KEY)
        return {channel: await self.client.scard(_channel_key(channel)) for channel in channels}
