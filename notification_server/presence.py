"""Redis-backed presence and subscription state.

Tracks which client IDs are connected and which channels they are
subscribed to in Redis rather than local process memory. This state is
shared by every server instance pointed at the same Redis backbone, so
it reflects the global system (not just one process) and outlives any
single server restart -- only the live WebSocket sockets themselves are
process-local and cannot survive a restart.
"""

from __future__ import annotations


class RedisPresence:
    def __init__(self, redis, namespace: str = "ns") -> None:
        self.redis = redis
        self.ns = namespace

    def _clients_key(self) -> str:
        return f"{self.ns}:clients"

    def _channel_key(self, channel: str) -> str:
        return f"{self.ns}:channel:{channel}"

    def _client_channels_key(self, client_id: str) -> str:
        return f"{self.ns}:client:{client_id}:channels"

    def _active_channels_key(self) -> str:
        return f"{self.ns}:active_channels"

    def _client_instance_key(self, client_id: str) -> str:
        return f"{self.ns}:client:{client_id}:instance"

    # -- connection lifecycle -----------------------------------------

    async def add_client(self, client_id: str, instance_id: str) -> None:
        await self.redis.sadd(self._clients_key(), client_id)
        await self.redis.set(self._client_instance_key(client_id), instance_id)

    async def remove_client(self, client_id: str) -> None:
        channels = await self.redis.smembers(self._client_channels_key(client_id))
        for channel in channels:
            await self.redis.srem(self._channel_key(channel), client_id)
            if await self.redis.scard(self._channel_key(channel)) == 0:
                await self.redis.srem(self._active_channels_key(), channel)
        await self.redis.delete(self._client_channels_key(client_id))
        await self.redis.srem(self._clients_key(), client_id)
        await self.redis.delete(self._client_instance_key(client_id))

    async def has_client(self, client_id: str) -> bool:
        return bool(await self.redis.sismember(self._clients_key(), client_id))

    async def client_count(self) -> int:
        return await self.redis.scard(self._clients_key())

    # -- channel subscriptions -----------------------------------------

    async def subscribe(self, client_id: str, channel: str) -> None:
        await self.redis.sadd(self._channel_key(channel), client_id)
        await self.redis.sadd(self._client_channels_key(client_id), channel)
        await self.redis.sadd(self._active_channels_key(), channel)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        await self.redis.srem(self._channel_key(channel), client_id)
        await self.redis.srem(self._client_channels_key(client_id), channel)
        if await self.redis.scard(self._channel_key(channel)) == 0:
            await self.redis.srem(self._active_channels_key(), channel)

    async def channels(self) -> dict[str, int]:
        names = await self.redis.smembers(self._active_channels_key())
        result = {}
        for name in names:
            count = await self.redis.scard(self._channel_key(name))
            if count:
                result[name] = count
        return result

    async def subscribers(self, channel: str) -> list[str]:
        members = await self.redis.smembers(self._channel_key(channel))
        return sorted(members)
