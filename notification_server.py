"""
Pluggable-transport notification server backed by Redis pub/sub and SQLite.

Features
--------
- Accept client connections through a pluggable transport layer and assign
  each client a globally-unique ID.  The default transport is WebSocket; the
  ``TRANSPORT`` env var (or the ``transport`` constructor argument) selects an
  alternative such as SSE, polling, or raw TCP.
- Distribute messages through Redis pub/sub channels (the shared backbone):
  the server publishes; a subscriber "worker" on every instance delivers.
- Broadcast a message to all connected clients.
- Deliver a "direct" message to a single client by ID.
- Support named channels: clients subscribe/unsubscribe dynamically and
  messages carrying a ``channel`` field are delivered only to subscribers.
- Remove clients cleanly on disconnect.
- Persist every application message in SQLite for history.
- Expose ``GET /health`` returning the number of connected clients.
- Expose ``GET /channels`` and ``GET /channels/{name}/subscribers``.
- Expose ``GET /messages?limit=50&offset=0`` returning persisted history.

Configuration
-------------
- ``REDIS_URL``     — Redis broker connection string.  When unset, an
  in-process fakeredis instance is used.
- ``DATABASE_URL``  — SQLite path for message history (default ``messages.db``).
- ``TRANSPORT``     — transport name (default ``websocket``).

Message format
--------------
Every application message is a JSON object::

    {"type": str, "payload": dict, "timestamp": str}

Supported ``type`` values: ``broadcast``, ``direct``, ``system``,
``subscribe``, ``unsubscribe``.

Wire format
-----------
The default ``WebSocketTransport`` base64-encodes every frame on the wire.  We
follow that contract explicitly: every outgoing JSON message is base64-encoded
before it is sent and every incoming frame is base64-decoded before it is
parsed as JSON.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import os
import threading
import uuid
from typing import Any, Dict, List
from urllib.parse import parse_qs, unquote, urlsplit

from broker import (
    BROADCAST_CHANNEL,
    CHANNEL_PREFIX,
    DIRECT_PREFIX,
    SUBSCRIBE_PATTERN,
    MessageBroker,
    RateLimiter,
)
from store import MessageStore
from transport import (
    BaseTransport,
    WebSocketTransport,
    create_transport,
    decode_message,
    encode_message,
    utcnow,
)

__all__ = [
    "NotificationServer",
    "ClientRegistry",
    "BaseTransport",
    "WebSocketTransport",
    "decode_message",
    "encode_message",
    "utcnow",
]


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class ClientRegistry:
    """Thread-safe registry of connected clients and their subscriptions."""

    def __init__(self) -> None:
        self._clients: Dict[int, Any] = {}
        self._channels: Dict[str, set] = {}
        self._lock = threading.Lock()
        self._counter = itertools.count(1)

    def register(self, connection: Any, client_id: int | None = None) -> int:
        with self._lock:
            if client_id is None:
                client_id = next(self._counter)
            self._clients[client_id] = connection
            return client_id

    def unregister(self, client_id: int) -> Any | None:
        with self._lock:
            connection = self._clients.pop(client_id, None)
            for members in self._channels.values():
                members.discard(client_id)
            for name in [n for n, m in self._channels.items() if not m]:
                del self._channels[name]
            return connection

    def get(self, client_id: int) -> Any | None:
        with self._lock:
            return self._clients.get(client_id)

    def count(self) -> int:
        with self._lock:
            return len(self._clients)

    def snapshot(self) -> Dict[int, Any]:
        with self._lock:
            return dict(self._clients)

    # ── Subscriptions ──────────────────────────────────────────

    def subscribe(self, client_id: int, channel: str) -> None:
        with self._lock:
            if client_id in self._clients:
                self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: int, channel: str) -> None:
        with self._lock:
            members = self._channels.get(channel)
            if members is not None:
                members.discard(client_id)
                if not members:
                    del self._channels[channel]

    def subscribers(self, channel: str) -> List[int]:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    def channels(self) -> Dict[str, int]:
        with self._lock:
            return {name: len(members) for name, members in self._channels.items()}


class NotificationServer:
    """Asyncio notification server with a Redis pub/sub backbone.

    The network-facing behaviour is delegated to a pluggable
    :class:`BaseTransport` implementation (WebSocket by default).
    """

    def __init__(
        self,
        broker: MessageBroker | None = None,
        store: MessageStore | None = None,
        redis_url: str | None = None,
        database_url: str | None = None,
        transport: BaseTransport | str | type | None = None,
        rate_limit: int | None = None,
        message_ttl_days: int | None = None,
    ) -> None:
        self.clients = ClientRegistry()
        self.instance_id = uuid.uuid4().hex
        self.broker = broker if broker is not None else MessageBroker(redis_url=redis_url)
        self.store = store if store is not None else MessageStore(database_url)
        self.transport = self._select_transport(transport)
        self.rate_limit = _env_int("RATE_LIMIT", 100) if rate_limit is None else rate_limit
        self.rate_limiter = RateLimiter(self.broker.redis, self.rate_limit)
        self.message_ttl_days = (
            _env_int("MESSAGE_TTL_DAYS", 7) if message_ttl_days is None else message_ttl_days
        )
        self._cleanup_interval = 3600
        self._subscriber_task = None
        self._cleanup_task = None

    def _select_transport(self, transport: BaseTransport | str | type | None) -> BaseTransport:
        if transport is None:
            return create_transport(os.environ.get("TRANSPORT"), self)
        if isinstance(transport, BaseTransport):
            return transport
        if isinstance(transport, str):
            return create_transport(transport, self)
        if isinstance(transport, type) and issubclass(transport, BaseTransport):
            return transport(self)
        raise TypeError(f"unsupported transport: {transport!r}")

    async def start(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        await self.transport.start(host, port)
        self._subscriber_task = asyncio.create_task(self._subscriber_loop())
        self.store.delete_older_than_days(self.message_ttl_days)
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except (asyncio.CancelledError, Exception):
                pass
            self._cleanup_task = None
        if self._subscriber_task is not None:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except (asyncio.CancelledError, Exception):
                pass
            self._subscriber_task = None
        await self.transport.stop()

    @property
    def port(self) -> int | None:
        return self.transport.port

    # ── Redis worker (subscriber) ─────────────────────────────

    async def _subscriber_loop(self) -> None:
        ps = self.broker.pubsub()
        await ps.psubscribe(SUBSCRIBE_PATTERN)
        try:
            async for message in ps.listen():
                if message["type"] != "pmessage":
                    continue
                channel = message["channel"]
                try:
                    outgoing = json.loads(message["data"])
                except (ValueError, TypeError):
                    continue
                await self._route(channel, outgoing)
        finally:
            try:
                await ps.aclose()
            except Exception:
                pass

    async def _cleanup_loop(self) -> None:
        while True:
            try:
                self.store.delete_older_than_days(self.message_ttl_days)
            except Exception:
                pass
            await asyncio.sleep(self._cleanup_interval)

    async def _route(self, channel: str, message: Dict[str, Any]) -> None:
        if channel == BROADCAST_CHANNEL:
            await self.broadcast(message)
        elif channel.startswith(CHANNEL_PREFIX):
            name = channel[len(CHANNEL_PREFIX):]
            await self.send_to_channel(name, message)
        elif channel.startswith(DIRECT_PREFIX):
            try:
                target = int(channel[len(DIRECT_PREFIX):])
            except ValueError:
                return
            await self._deliver_to_client(target, message)

    # ── HTTP handler ──────────────────────────────────────────

    def _handle_http_request(self, path: str) -> str | None:
        """Return a JSON response body for ``path``, or ``None`` if unhandled."""
        parts = urlsplit(path)
        route = parts.path

        if route == "/health":
            return json.dumps({"connected_clients": self.clients.count()})

        if route == "/channels":
            return json.dumps({"channels": self.clients.channels()})

        if route.startswith("/channels/") and route.endswith("/subscribers"):
            name = unquote(route[len("/channels/"):-len("/subscribers")])
            return json.dumps(
                {"channel": name, "subscribers": self.clients.subscribers(name)}
            )

        if route == "/messages":
            query = parse_qs(parts.query)
            limit = query.get("limit", ["50"])[0]
            offset = query.get("offset", ["0"])[0]
            messages = self.store.query(limit=limit, offset=offset)
            return json.dumps({"messages": messages})

        if route == "/history":
            query = parse_qs(parts.query)
            channel = query.get("channel", [None])[0]
            since = query.get("since", [None])[0]
            limit = query.get("limit", ["50"])[0]
            result = self.store.query_history(
                channel=channel or None,
                since=since or None,
                limit=limit,
            )
            return json.dumps(result)

        return None

    # ── Message handling ──────────────────────────────────────

    async def _handle_message(self, sender_id: int, message: Dict[str, Any]) -> None:
        mtype = message.get("type")
        payload = message.get("payload") or {}
        timestamp = message.get("timestamp") or utcnow()

        if mtype == "subscribe":
            channel = payload.get("channel") or message.get("channel")
            if channel:
                self.clients.subscribe(sender_id, channel)
                await self.broker.subscribe_client(sender_id, channel)
            return

        if mtype == "unsubscribe":
            channel = payload.get("channel") or message.get("channel")
            if channel:
                self.clients.unsubscribe(sender_id, channel)
                await self.broker.unsubscribe_client(sender_id, channel)
            return

        if not await self.rate_limiter.allow(sender_id):
            connection = self.clients.get(sender_id)
            if connection is not None:
                try:
                    await self.transport.send_message(
                        connection,
                        {
                            "type": "error",
                            "payload": {"message": "rate limit exceeded"},
                            "timestamp": utcnow(),
                        },
                    )
                except Exception:
                    pass
            return

        if mtype == "broadcast":
            outgoing = {"type": "broadcast", "payload": payload, "timestamp": timestamp}
            outgoing["payload"]["sender_id"] = sender_id
            channel = message.get("channel")
            if channel:
                outgoing["channel"] = channel
                await self._publish_and_store(CHANNEL_PREFIX + channel, outgoing)
            else:
                await self._publish_and_store(BROADCAST_CHANNEL, outgoing)
        elif mtype == "direct":
            target = payload.get("client_id")
            if target is None:
                return
            outgoing = {"type": "direct", "payload": payload, "timestamp": timestamp}
            outgoing["payload"]["sender_id"] = sender_id
            await self._publish_and_store(DIRECT_PREFIX + str(target), outgoing)

    async def _publish_and_store(self, redis_channel: str, message: Dict[str, Any]) -> None:
        self.store.save(message)
        await self.broker.publish(redis_channel, json.dumps(message))

    # ── Local delivery (invoked by the worker) ────────────────

    async def broadcast(self, message: Dict[str, Any]) -> None:
        await self.transport.broadcast(message)

    async def send_to_channel(self, channel: str, message: Dict[str, Any]) -> None:
        for client_id in self.clients.subscribers(channel):
            connection = self.clients.get(client_id)
            if connection is None:
                continue
            try:
                await self.transport.send_message(connection, message)
            except Exception:
                continue

    async def _deliver_to_client(self, client_id: int, message: Dict[str, Any]) -> None:
        connection = self.clients.get(client_id)
        if connection is None:
            return
        try:
            await self.transport.send_message(connection, message)
        except Exception:
            pass


async def main() -> None:
    server = NotificationServer()
    await server.start(host="127.0.0.1", port=8765)
    print(f"notification server listening on ws://127.0.0.1:{server.port}")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
