"""
Notification server built on a pluggable transport layer.

The core ``NotificationServer`` implements all notification logic: client
registry, channel subscriptions, message routing, persistence and the message
backbone. All client I/O happens through a ``BaseTransport`` so different
transport mechanisms (WebSocket, SSE, polling, raw TCP, ...) can be plugged in
without touching the core.

Transports:
- ``WebSocketTransport`` (the default) accepts WebSocket connections via the
  ``websockets`` library, assigns each client a unique ID on connect,
  broadcasts messages to ALL connected clients, sends direct messages to a
  specific client and supports named channels.

The transport is selected with the ``TRANSPORT`` environment variable
(default: ``websocket``). Transport classes register themselves through the
``@register_transport`` decorator.

Message distribution runs over a configurable message backbone (see
`broker.py`):

- When ``REDIS_URL`` is set, the server uses Redis pub/sub. Every message is
  published to a single Redis channel and every server instance subscribed to
  the same Redis receives it and delivers to its local clients, so multiple
  server instances can share the same backbone. Client connection and
  subscription state is mirrored in Redis and survives server restarts.
- Without ``REDIS_URL`` the server falls back to an in-process backbone that
  delivers messages directly, preserving the historical single-instance
  behaviour.

All distributed messages are persisted to SQLite (``DATABASE_URL``) and can be
queried via ``GET /messages?limit=50&offset=0`` (newest first) or
``GET /history?channel=X&since=ISO_TIMESTAMP&limit=50`` (chronological,
pagination with ``has_more``). Messages older than ``MESSAGE_TTL_DAYS`` days
(default 7) are cleaned up by a background task at server startup.

Incoming client messages are rate limited per client-ID (``RATE_LIMIT``,
default 100 per minute). Counters live in Redis when ``REDIS_URL`` is set and
are shared across instances; a client that exceeds the limit receives a system
error message instead of being dropped.

Message format (JSON):
    {type: str, payload: dict, timestamp: str}

Supported types: 'broadcast', 'direct', 'system', 'subscribe', 'unsubscribe'.

Channel routing:
- A message with a top-level 'channel' field (or one inside its payload)
  is delivered only to clients subscribed to that channel.
- A message without a 'channel' field broadcasts to all connected clients.

Thread-safety: asyncio runs everything on a single event loop, so the
client registry needs no locking; plain dict reads/writes are safe by
construction.
"""

import asyncio
import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlsplit

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Headers, Response

from broker import (
    Broker,
    LocalBroker,
    MessageStore,
    default_backbone,
)
from ratelimit import RateLimiter, default_rate_limiter

SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
WELCOME_TIMEOUT = 5.0
DEFAULT_TTL_DAYS = 7


def _env_ttl_days() -> int:
    """Read the message retention window from ``MESSAGE_TTL_DAYS`` (default 7)."""
    raw = (os.environ.get("MESSAGE_TTL_DAYS") or "").strip()
    if not raw:
        return DEFAULT_TTL_DAYS
    try:
        return max(int(raw), 1)
    except ValueError:
        return DEFAULT_TTL_DAYS


def make_message(msg_type: str, payload: dict) -> dict:
    """Build a message dict in the canonical wire format."""
    if msg_type not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported message type: {msg_type!r}")
    return {
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Transport layer ─────────────────────────────────────────────


class BaseTransport(ABC):
    """Abstract transport interface for client connections.

    Concrete transports implement the mechanics of accepting connections and
    exchanging messages (WebSocket, SSE, polling, raw TCP, ...). The core
    ``NotificationServer`` talks to clients only through this interface, so a
    new transport can be added without modifying the notification logic.
    """

    #: transport name used to select it via the ``TRANSPORT`` env var.
    name = "base"

    def __init__(self, server: "NotificationServer | None" = None) -> None:
        self.server = server
        # client_id -> connection handle owned by THIS instance.
        self.connections: dict[str, Any] = {}

    @abstractmethod
    async def start(self, host: str, port: int) -> None:
        """Begin accepting client connections."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop accepting connections and release resources."""

    @abstractmethod
    async def on_connect(self, connection) -> str:
        """Register a freshly accepted connection; return its client_id."""

    @abstractmethod
    async def on_disconnect(self, client_id: str, connection) -> None:
        """Tear down a connection that is closing."""

    @abstractmethod
    async def receive(self, connection) -> str | None:
        """Wait for the next raw message, or None when the client disconnects."""

    @abstractmethod
    async def send_message(self, client_id: str, message: dict) -> None:
        """Deliver a JSON-serialisable message to a single client."""

    @abstractmethod
    async def broadcast(self, targets: list[str], message: dict) -> None:
        """Deliver a JSON-serialisable message to every listed client."""


TRANSPORTS: dict[str, type[BaseTransport]] = {}


def register_transport(cls: type[BaseTransport]) -> type[BaseTransport]:
    """Register a transport class so it can be selected by name."""
    TRANSPORTS[cls.name] = cls
    for alias in getattr(cls, "aliases", ()):
        TRANSPORTS[alias] = cls
    return cls


@register_transport
class WebSocketTransport(BaseTransport):
    """Transport backed by the ``websockets`` library (the default)."""

    name = "websocket"
    aliases = ("ws",)

    async def start(self, host: str, port: int) -> None:
        self.server._server = await serve(
            self.server.handle_connection,
            host,
            port,
            process_request=self._process_request,
        )

    async def stop(self) -> None:
        self.server._server.close()
        await self.server._server.wait_closed()

    async def on_connect(self, connection: ServerConnection) -> str:
        client_id = await self.server._new_client_id()
        self.connections[client_id] = connection
        return client_id

    async def on_disconnect(
        self, client_id: str, connection: ServerConnection
    ) -> None:
        self.connections.pop(client_id, None)
        try:
            await connection.close()
        except Exception:
            pass

    async def receive(self, connection: ServerConnection) -> str | None:
        try:
            return await connection.recv()
        except ConnectionClosed:
            return None

    async def send_message(self, client_id: str, message: dict) -> None:
        connection = self.connections.get(client_id)
        if connection is None:
            raise ConnectionError(
                f"no connection registered for client {client_id!r}"
            )
        await connection.send(json.dumps(message))

    async def broadcast(self, targets: list[str], message: dict) -> None:
        for client_id in targets:
            try:
                await self.send_message(client_id, message)
            except Exception:
                self.server._drop_client(client_id)

    # ── HTTP (REST) handling ────────────────────────────────────

    async def _process_request(self, connection, request) -> Response | None:
        """Handle plain HTTP requests (e.g. GET /health) before WS upgrade."""
        if request.headers.get("Upgrade", "").lower() == "websocket":
            return None

        split = urlsplit(request.path)
        result = await self.server._rest_handler(
            split.path, parse_qs(split.query)
        )
        if result is None:
            return None
        status, data = result
        return self._json_response(status, data)

    @staticmethod
    def _json_response(status: int, data: dict) -> Response:
        body = json.dumps(data).encode("utf-8")
        headers = Headers(
            {
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
            }
        )
        return Response(status, "OK" if status == 200 else "Not Found", headers, body)


def default_transport() -> BaseTransport:
    """Build the transport selected by the ``TRANSPORT`` env var."""
    name = (os.environ.get("TRANSPORT") or "").strip().lower() or "websocket"
    try:
        cls = TRANSPORTS[name]
    except KeyError:
        raise ValueError(f"unknown transport: {name!r}") from None
    return cls()


class NotificationServer:
    """Async notification server with a pluggable transport layer."""

    def __init__(
        self,
        backbone: Broker | None = None,
        store: MessageStore | None = None,
        transport: BaseTransport | None = None,
        rate_limiter: RateLimiter | None = None,
        ttl_days: int | None = None,
    ) -> None:
        self._transport = transport or default_transport()
        self._transport.server = self
        # client_id -> connection handle for connections owned by THIS instance.
        self._clients = self._transport.connections
        # channel name -> set of client_ids subscribed to that channel (local mirror).
        self._local_channels: dict[str, set[str]] = {}
        # client_id -> set of channel names the client is subscribed to (local mirror).
        self._client_channels: dict[str, set[str]] = {}
        self._backbone = backbone or default_backbone()
        if isinstance(self._backbone, LocalBroker) and self._backbone.server is None:
            self._backbone.server = self
        self._store = store or MessageStore()
        self._rate_limiter = rate_limiter or default_rate_limiter()
        self._ttl_days = ttl_days if ttl_days is not None else _env_ttl_days()
        self._consumer_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server = None

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def client_ids(self) -> list[str]:
        return list(self._clients)

    @property
    def channel_names(self) -> list[str]:
        return list(self._local_channels)

    # ── Channel subscriptions ─────────────────────────────────

    def subscribe(self, client_id: str, channel: str) -> None:
        """Subscribe a client to a named channel."""
        if not channel:
            raise ValueError("channel name must be non-empty")
        self._local_channels.setdefault(channel, set()).add(client_id)
        self._client_channels.setdefault(client_id, set()).add(channel)
        if self._backbone.remote_state and self._loop is not None:
            self._background(self._backbone.subscribe(client_id, channel))

    def unsubscribe(self, client_id: str, channel: str) -> None:
        """Unsubscribe a client from a named channel."""
        subs = self._local_channels.get(channel)
        if subs is None:
            return
        subs.discard(client_id)
        if not subs:
            del self._local_channels[channel]
        own = self._client_channels.get(client_id)
        if own is not None:
            own.discard(channel)
            if not own:
                del self._client_channels[client_id]
        if self._backbone.remote_state and self._loop is not None:
            self._background(self._backbone.unsubscribe(client_id, channel))

    def subscribed_channels(self, client_id: str) -> list[str]:
        """List the channels a client is currently subscribed to."""
        return sorted(self._client_channels.get(client_id, set()))

    def channel_subscribers(self, channel: str) -> list[str]:
        """Return the IDs of clients subscribed to a channel."""
        return sorted(self._local_channels.get(channel, set()))

    def channels_info(self) -> list[dict]:
        """Return info for all active channels: name and subscriber count."""
        return [
            {"name": name, "subscribers": len(subs)}
            for name, subs in sorted(self._local_channels.items())
        ]

    def _drop_client(self, client_id: str) -> None:
        """Remove a client from the registry and all channel subscriptions."""
        self._clients.pop(client_id, None)
        self._client_channels.pop(client_id, None)
        if self._local_channels:
            for name, subs in list(self._local_channels.items()):
                subs.discard(client_id)
                if not subs:
                    del self._local_channels[name]
        if self._backbone.remote_state and self._loop is not None:
            self._background(self._backbone.unregister_client(client_id))

    def _background(self, coro) -> None:
        """Run a fire-and-forget coroutine, swallowing background failures."""

        def _done(task: asyncio.Task) -> None:
            if not task.cancelled():
                task.exception()

        task = self._loop.create_task(coro)
        task.add_done_callback(_done)

    # ── Outbound send helpers ───────────────────────────────────

    async def _new_client_id(self) -> str:
        return await self._backbone.next_client_id()

    async def _send(self, client_id: str, message: dict) -> None:
        await self._transport.send_message(client_id, message)

    async def _record(self, message: dict, channel: str | None = None) -> None:
        """Persist a distributed message to the SQLite history store."""
        try:
            await self._store.store(message, channel)
        except Exception:
            pass

    async def _system(
        self,
        client_id: str,
        event: str,
        error: str | None = None,
    ) -> None:
        """Send (and record) a system message to a single client."""
        payload = {"event": event}
        if error is not None:
            payload["error"] = error
        message = make_message("system", payload)
        await self._record(message)
        await self._send(client_id, message)

    async def _deliver_event(self, event: dict) -> None:
        """Deliver a backbone event to the clients this instance owns."""
        message = event.get("message") or {}
        targets = [
            client_id
            for client_id in (event.get("targets") or [])
            if client_id in self._clients
        ]
        if targets:
            await self._transport.broadcast(targets, message)

    async def broadcast(self, payload: dict, channel: str | None = None) -> int:
        """Send a 'broadcast' message to clients.

        When ``channel`` is given, the message is delivered only to clients
        subscribed to that channel; otherwise it goes to every connected
        client. Returns the number of clients the message was targeted at.
        """
        message = make_message("broadcast", payload)
        await self._record(message, channel)
        if channel is None:
            targets = await self._backbone.active_client_ids()
            targets = list(set(targets) | set(self._clients))
        else:
            targets = await self._backbone.channel_subscribers(channel)
        event = {
            "message": message,
            "channel": channel,
            "targets": targets,
        }
        await self._backbone.publish(event)
        return len(targets)

    async def send_direct(self, client_id: str, payload: dict) -> bool:
        """Send a 'direct' message to a single client. Returns success."""
        message = make_message("direct", payload)
        await self._record(message)
        if client_id in self._clients:
            try:
                await self._send(client_id, message)
                return True
            except Exception:
                self._clients.pop(client_id, None)
                return False
        known = await self._backbone.active_client_ids()
        if client_id in known:
            await self._backbone.publish(
                {"message": message, "channel": None, "targets": [client_id]}
            )
            return True
        return False

    # ── Connection lifecycle ────────────────────────────────────

    async def handle_connection(self, connection) -> None:
        """Per-connection coroutine: register, welcome, serve, clean up."""
        client_id = await self._transport.on_connect(connection)
        try:
            await self._on_connected(client_id)
            while True:
                raw = await self._transport.receive(connection)
                if raw is None:
                    break
                await self.handle_incoming(client_id, raw)
        finally:
            # Clean removal regardless of how the connection ended.
            await self._transport.on_disconnect(client_id, connection)
            self._drop_client(client_id)

    async def _on_connected(self, client_id: str) -> None:
        """Run the connect-time logic for a freshly registered client."""
        if self._backbone.remote_state:
            await self._backbone.register_client(client_id)
        welcome = make_message(
            "system", {"event": "connected", "client_id": client_id}
        )
        await self._record(welcome)
        await self._send(client_id, welcome)

    async def handle_incoming(self, client_id: str, raw) -> None:
        """Route a raw client message through the core notification logic."""
        if not await self._rate_limiter.allow(client_id):
            await self._system(client_id, "error", error="rate limit exceeded")
            return
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            await self._system(client_id, "error", error="invalid JSON message")
            return
        if not isinstance(data, dict) or data.get("type") not in SUPPORTED_TYPES:
            await self._system(client_id, "error", error="unsupported message")
            return
        payload = data.get("payload") or {}
        msg_type = data["type"]
        if msg_type == "broadcast":
            channel = data.get("channel") or payload.get("channel")
            await self.broadcast(payload, channel=channel)
        elif msg_type == "subscribe":
            channel = data.get("channel") or payload.get("channel")
            if not channel:
                await self._system(client_id, "error", error="subscribe missing channel")
            else:
                self.subscribe(client_id, channel)
        elif msg_type == "unsubscribe":
            channel = data.get("channel") or payload.get("channel")
            if not channel:
                await self._system(client_id, "error", error="unsubscribe missing channel")
            else:
                self.unsubscribe(client_id, channel)
        elif msg_type == "direct":
            target = payload.get("target_id")
            if target is None:
                await self._system(
                    client_id, "error", error="direct message missing target_id"
                )
            elif not await self.send_direct(target, payload):
                await self._system(
                    client_id, "error", error=f"unknown client {target!r}"
                )

    # ── HTTP (REST) handling ────────────────────────────────────

    async def _rest_handler(self, path: str, query: dict) -> tuple[int, dict] | None:
        """Resolve a REST path to a ``(status, json_body)`` pair, if handled."""
        if path == "/health":
            return 200, {"clients": self.client_count, "status": "ok"}
        if path == "/channels":
            return 200, {"channels": self.channels_info()}
        if path.startswith("/channels/") and path.endswith("/subscribers"):
            name = path[len("/channels/"):-len("/subscribers")]
            return 200, {
                "channel": name,
                "subscribers": self.channel_subscribers(name),
            }
        if path == "/messages":
            limit = self._int_query(query, "limit", 50)
            offset = self._int_query(query, "offset", 0)
            messages = await self._store.list(limit, offset)
            return 200, {
                "messages": messages,
                "limit": limit,
                "offset": offset,
            }
        if path == "/history":
            channel = self._query_value(query, "channel")
            since = self._query_value(query, "since")
            limit = self._int_query(query, "limit", 50)
            offset = self._int_query(query, "offset", 0)
            result = await self._store.history(
                channel, since=since, limit=limit, offset=offset
            )
            return 200, {
                "messages": result["messages"],
                "channel": channel,
                "since": since,
                "limit": limit,
                "offset": offset,
                "has_more": result["has_more"],
            }
        return None

    @staticmethod
    def _int_query(query: dict, key: str, default: int) -> int:
        try:
            return max(int(query.get(key, [str(default)])[0]), 0)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _query_value(query: dict, key: str) -> str | None:
        values = query.get(key)
        if not values:
            return None
        return values[0]

    # ── Lifecycle ───────────────────────────────────────────────

    async def _hydrate(self) -> None:
        """Reload subscription state from the backbone after a restart."""
        if not self._backbone.remote_state:
            return
        for name in await self._backbone.channel_names():
            subs = set(await self._backbone.channel_subscribers(name))
            self._local_channels[name] = subs
            for client_id in subs:
                self._client_channels.setdefault(client_id, set()).add(name)

    async def _run_startup_cleanup(self) -> None:
        """Delete expired messages in the background on server startup."""
        try:
            await self._store.cleanup(self._ttl_days)
        except Exception:
            pass

    async def start(self, host: str = "localhost", port: int = 8765) -> None:
        self._loop = asyncio.get_running_loop()
        await self._store.init()
        await self._hydrate()
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._run_startup_cleanup())
        if self._backbone.consumable:
            self._consumer_task = asyncio.create_task(
                self._backbone.consume(self._deliver_event)
            )
        await self._transport.start(host, port)

    async def stop(self) -> None:
        self._clients.clear()
        if self._consumer_task is not None:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except (asyncio.CancelledError, Exception):
                pass
            self._consumer_task = None
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except (asyncio.CancelledError, Exception):
                pass
            self._cleanup_task = None
        await self._transport.stop()
        await self._backbone.close()
        await self._rate_limiter.close()
        await self._store.close()


async def run_server(host: str = "localhost", port: int = 8765) -> None:
    """Run the notification server until interrupted."""
    server = NotificationServer()
    await server.start(host, port)
    print(f"Notification server listening on ws://{host}:{port}")
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        pass
