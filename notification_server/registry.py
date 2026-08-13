"""Thread-safe registry of connected WebSocket clients."""
from __future__ import annotations

import asyncio
import uuid
from typing import Any, Iterable

CLIENTS_KEY = "notification_server:clients"
CHANNELS_KEY = "notification_server:channels"


def _channel_key(channel: str) -> str:
    return f"notification_server:channel:{channel}"


class ClientRegistry:
    """Tracks connected clients behind an asyncio.Lock.

    All mutation and iteration goes through the lock so concurrent
    connects, disconnects, and broadcasts never observe a torn state.

    Actual WebSocket objects only ever live in the local, in-memory maps
    below — they can't be serialized to Redis and only make sense on the
    process that owns the socket. When `redis_client` is supplied, this
    registry additionally mirrors *which clients and channel subscriptions
    exist* (not the sockets themselves) into Redis, so that connection
    state stays visible cluster-wide and survives any single server
    instance restarting. Callers that don't pass `redis_client` get the
    exact original local-only behavior.
    """

    def __init__(self, redis_client: Any = None, server_id: str | None = None) -> None:
        self._clients: dict[str, Any] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()
        self._redis = redis_client
        self._server_id = server_id or uuid.uuid4().hex

    async def register(self, websocket: Any) -> str:
        client_id = uuid.uuid4().hex
        async with self._lock:
            self._clients[client_id] = websocket
        if self._redis is not None:
            await self._redis.hset(CLIENTS_KEY, client_id, self._server_id)
        return client_id

    async def unregister(self, client_id: str) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)
            channels = []
            for name in list(self._channels.keys()):
                subs = self._channels[name]
                if client_id in subs:
                    channels.append(name)
                subs.discard(client_id)
                if not subs:
                    del self._channels[name]
        if self._redis is not None:
            await self._redis.hdel(CLIENTS_KEY, client_id)
            for name in channels:
                await self._srem_channel(name, client_id)

    async def get(self, client_id: str) -> Any | None:
        async with self._lock:
            return self._clients.get(client_id)

    async def exists(self, client_id: str) -> bool:
        """True if `client_id` is connected, locally or (with Redis) anywhere in the cluster."""
        async with self._lock:
            if client_id in self._clients:
                return True
        if self._redis is not None:
            return bool(await self._redis.hexists(CLIENTS_KEY, client_id))
        return False

    async def count(self) -> int:
        async with self._lock:
            return len(self._clients)

    async def global_count(self) -> int:
        """Cluster-wide connected client count when Redis is configured, else local count."""
        if self._redis is not None:
            return await self._redis.hlen(CLIENTS_KEY)
        return await self.count()

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            return dict(self._clients)

    async def subscribe(self, client_id: str, channel: str) -> bool:
        """Subscribe `client_id` to `channel`. Returns False if the client is unknown."""
        async with self._lock:
            if client_id not in self._clients:
                return False
            self._channels.setdefault(channel, set()).add(client_id)
        if self._redis is not None:
            await self._redis.sadd(_channel_key(channel), client_id)
            await self._redis.sadd(CHANNELS_KEY, channel)
        return True

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            subs = self._channels.get(channel)
            if subs is None:
                removed = False
            else:
                removed = client_id in subs
                subs.discard(client_id)
                if not subs:
                    del self._channels[channel]
        if self._redis is not None and removed:
            await self._srem_channel(channel, client_id)

    async def _srem_channel(self, channel: str, client_id: str) -> None:
        removed = await self._redis.srem(_channel_key(channel), client_id)
        if removed and await self._redis.scard(_channel_key(channel)) == 0:
            await self._redis.srem(CHANNELS_KEY, channel)

    async def channels_snapshot(self) -> dict[str, int]:
        """Map of channel name -> subscriber count, for active (non-empty) channels."""
        async with self._lock:
            return {name: len(subs) for name, subs in self._channels.items()}

    async def global_channels_snapshot(self) -> dict[str, int]:
        """Cluster-wide channel -> subscriber count when Redis is configured, else local."""
        if self._redis is None:
            return await self.channels_snapshot()
        names = await self._redis.smembers(CHANNELS_KEY)
        result = {}
        for raw in names:
            name = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            count = await self._redis.scard(_channel_key(name))
            if count:
                result[name] = count
        return result

    async def subscribers(self, channel: str) -> list[str]:
        async with self._lock:
            return sorted(self._channels.get(channel, set()))

    async def global_subscribers(self, channel: str) -> list[str]:
        """Cluster-wide subscriber list for `channel` when Redis is configured, else local."""
        if self._redis is None:
            return await self.subscribers(channel)
        raw_members = await self._redis.smembers(_channel_key(channel))
        members = [m.decode("utf-8") if isinstance(m, bytes) else m for m in raw_members]
        return sorted(members)

    async def broadcast_channel(self, text: str, channel: str, exclude: Iterable[str] = ()) -> list[str]:
        """Send `text` to every client subscribed to `channel`, except those in `exclude`.

        Clients whose send fails are dropped from the registry. Returns the
        list of client IDs that were dropped this way.
        """
        exclude = set(exclude)
        async with self._lock:
            targets = {
                cid: self._clients[cid]
                for cid in self._channels.get(channel, set())
                if cid in self._clients and cid not in exclude
            }
        if not targets:
            return []

        results = await asyncio.gather(
            *(self._safe_send(ws, text) for ws in targets.values()),
            return_exceptions=True,
        )

        dead = [cid for cid, ok in zip(targets.keys(), results) if ok is not True]
        for cid in dead:
            await self.unregister(cid)
        return dead

    async def broadcast(self, text: str, exclude: Iterable[str] = ()) -> list[str]:
        """Send `text` to every registered client except those in `exclude`.

        Clients whose send fails are dropped from the registry. Returns the
        list of client IDs that were dropped this way.
        """
        exclude = set(exclude)
        clients = await self.snapshot()
        targets = {cid: ws for cid, ws in clients.items() if cid not in exclude}
        if not targets:
            return []

        results = await asyncio.gather(
            *(self._safe_send(ws, text) for ws in targets.values()),
            return_exceptions=True,
        )

        dead = [cid for cid, ok in zip(targets.keys(), results) if ok is not True]
        for cid in dead:
            await self.unregister(cid)
        return dead

    @staticmethod
    async def _safe_send(websocket: Any, text: str) -> bool:
        try:
            await websocket.send(text)
            return True
        except Exception:
            return False
