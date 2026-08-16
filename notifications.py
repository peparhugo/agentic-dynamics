"""Notification server with a pluggable transport layer.

The server accepts client connections, assigns each client a unique ID, and
supports broadcast / direct / system message types. It also exposes REST
endpoints for health, channels, and message history.

Pluggable transports
--------------------
Connection handling is delegated to a :class:`BaseTransport` implementation.
The default :class:`WebSocketTransport` accepts WebSocket connections; other
mechanisms (SSE, polling, raw TCP) can be added by implementing the transport
interface and registering it. The active transport is selected through the
``TRANSPORT`` environment variable (``websocket`` by default). The core
:class:`NotificationServer` logic is transport-agnostic.

Redis pub/sub backbone
----------------------
When ``REDIS_URL`` (or an explicit ``redis_url`` / ``redis_client``) is
configured, the server uses Redis pub/sub as its message backbone. Every
outbound message is published to a Redis channel; every server instance
subscribes to the channels its local clients care about and delivers what it
receives to those local clients. Multiple server instances can therefore share
the same Redis and exchange messages. Client connection state (client IDs,
channel subscriptions) is persisted in Redis so it survives a server restart.

Persistence
-----------
Every distributed message is stored in SQLite (``DATABASE_URL``) and can be
queried via ``GET /messages?limit=50&offset=0`` or, per channel / time range,
via ``GET /history?channel=X&since=ISO_TIMESTAMP&limit=50``. Messages older
than ``MESSAGE_TTL_DAYS`` days (default 7) are deleted by a background cleanup
task that starts with the server.

Rate limiting
-------------
Each client is limited to ``RATE_LIMIT`` messages per minute (default 100).
Counters are kept per client ID in Redis when a Redis backbone is configured,
and in memory otherwise. Clients that exceed the limit are told so with a
system error message; they are never silently dropped.

Everything runs inside a single asyncio event loop. Because asyncio guarantees
thread safety by construction, the client registry uses a plain dict with no
locking, even when background threads touch the registry.
"""

import abc
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from itertools import count
from typing import Any

import websockets
from aiohttp import web
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from message_store import MessageStore
from rate_limiter import DEFAULT_RATE_LIMIT, RateLimiter
from redis_broker import (
    BROADCAST_CHANNEL,
    CHANNEL_PUBSUB_PREFIX,
    CLIENT_PUBSUB_PREFIX,
    RedisBackbone,
)

log = logging.getLogger(__name__)

_client_ids = count(1)
_server_ids = count(1)

# Supported message types.
TYPE_BROADCAST = "broadcast"
TYPE_DIRECT = "direct"
TYPE_SYSTEM = "system"
TYPE_SUBSCRIBE = "subscribe"
TYPE_UNSUBSCRIBE = "unsubscribe"

ALLOWED_TYPES = {
    TYPE_BROADCAST,
    TYPE_DIRECT,
    TYPE_SYSTEM,
    TYPE_SUBSCRIBE,
    TYPE_UNSUBSCRIBE,
}

# Channel column values used when persisting messages.
CHANNEL_BROADCAST = "broadcast"
CHANNEL_DIRECT = "direct"


def utcnow_iso() -> str:
    """ISO-8601 UTC timestamp for messages."""
    return datetime.now(timezone.utc).isoformat()


def make_message(message_type: str, payload: dict) -> dict:
    """Build a message dict with the required {type, payload, timestamp} shape."""
    return {
        "type": message_type,
        "payload": payload,
        "timestamp": utcnow_iso(),
    }


def serialize(message: dict) -> str:
    """Serialize a message dict to a JSON string."""
    return json.dumps(message)


class ClientRegistry:
    """Registry of connected clients.

    asyncio runs everything on a single event loop, so plain dict reads and
    writes are always safe — no locking is required even when background
    threads touch the registry.
    """

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._channel_subscribers: dict[str, set[str]] = {}

    def add(self, connection: Any) -> str:
        """Register a client and return its unique ID."""
        client_id = f"client-{next(_client_ids)}"
        self._clients[client_id] = connection
        return client_id

    def remove(self, client_id: str) -> Any | None:
        """Remove a client and return the removed connection, if any."""
        removed = self._clients.pop(client_id, None)
        if removed is not None:
            self.unsubscribe_all(client_id)
        return removed

    def get(self, client_id: str) -> Any | None:
        """Return the connection for a client ID, if present."""
        return self._clients.get(client_id)

    def connections(self) -> list[Any]:
        """Return all live connections."""
        return list(self._clients.values())

    def connections_for(self, client_ids) -> list[Any]:
        """Return connections for the given client IDs."""
        return [self._clients[cid] for cid in client_ids if cid in self._clients]

    @property
    def count(self) -> int:
        """Number of connected clients."""
        return len(self._clients)

    # ── channel subscriptions ────────────────────────────────

    def subscribe(self, client_id: str, channel: str) -> None:
        """Subscribe a client to a named channel."""
        self._channel_subscribers.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        """Unsubscribe a client from a named channel."""
        subscribers = self._channel_subscribers.get(channel)
        if subscribers is None:
            return
        subscribers.discard(client_id)
        if not subscribers:
            del self._channel_subscribers[channel]

    def unsubscribe_all(self, client_id: str) -> None:
        """Remove a client from every channel it is subscribed to."""
        for channel in list(self._channel_subscribers):
            self.unsubscribe(client_id, channel)

    def channels_for(self, client_id: str) -> list[str]:
        """Return the names of channels a client is subscribed to."""
        return [
            name for name, members in self._channel_subscribers.items()
            if client_id in members
        ]

    def channel_members(self, channel: str) -> list[str]:
        """Return the IDs of clients subscribed to a channel."""
        return sorted(self._channel_subscribers.get(channel, set()))

    def channels(self) -> list[dict]:
        """Return all active channels with their subscriber counts."""
        return [
            {"name": name, "subscribers": len(subscribers)}
            for name, subscribers in sorted(self._channel_subscribers.items())
        ]

    @property
    def channel_names(self) -> list[str]:
        """Return the names of all active channels."""
        return sorted(self._channel_subscribers)


# ── transport layer ─────────────────────────────────────────

# Registry of transport implementations keyed by the ``TRANSPORT`` config name.
TRANSPORTS: dict[str, type["BaseTransport"]] = {}


def register_transport(name: str, transport_cls: type["BaseTransport"]) -> None:
    """Register a transport implementation under a config name."""
    TRANSPORTS[name.strip().lower()] = transport_cls


def get_transport_class(name: str | None = None) -> type["BaseTransport"]:
    """Resolve a transport class from the ``TRANSPORT`` config value.

    Falls back to ``websocket`` when nothing is configured.
    """
    key = (
        name if name is not None else os.environ.get("TRANSPORT", "websocket")
    )
    key = key.strip().lower()
    if key not in TRANSPORTS:
        raise ValueError(f"unknown transport: {key!r}")
    return TRANSPORTS[key]


class BaseTransport(abc.ABC):
    """Pluggable interface for client connection transports.

    A transport is responsible for accepting client connections, delivering
    outbound messages to connected clients, and feeding inbound messages back
    into the core server. Subclasses implement each transport mechanism
    (WebSocket, SSE, polling, raw TCP) without touching the core notification
    logic.
    """

    def __init__(self, server: "NotificationServer", **kwargs) -> None:
        self.server = server

    # ── lifecycle ─────────────────────────────────────────────

    @abc.abstractmethod
    async def start(self) -> None:
        """Start accepting client connections."""

    @abc.abstractmethod
    async def stop(self) -> None:
        """Stop accepting connections and release transport resources."""

    @property
    def bound_port(self) -> int | None:
        """Port clients connect to once the transport is running."""
        return None

    # ── connection hooks ──────────────────────────────────────

    @abc.abstractmethod
    async def on_connect(self, client_id: str) -> None:
        """Perform transport-specific work when a client connects."""

    @abc.abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Perform transport-specific work when a client disconnects."""

    # ── outbound delivery ─────────────────────────────────────

    @abc.abstractmethod
    async def send_message(self, client_id: str, message: dict) -> None:
        """Deliver a message dict to a single connected client."""

    @abc.abstractmethod
    async def broadcast(self, message: dict) -> None:
        """Deliver a message dict to every connected client."""

    async def channel_broadcast(self, channel: str, message: dict) -> None:
        """Deliver a message dict to every subscriber of a channel."""
        for client_id in self.server.registry.channel_members(channel):
            await self.send_message(client_id, message)


class WebSocketTransport(BaseTransport):
    """WebSocket transport (the default)."""

    def __init__(self, server: "NotificationServer", host: str = "127.0.0.1",
                 port: int = 8765, **kwargs) -> None:
        super().__init__(server)
        self.host = host
        self.port = port
        self._ws_server: websockets.Server | None = None
        self._bound_port: int | None = None

    @property
    def bound_port(self) -> int | None:
        return self._bound_port

    # ── lifecycle ─────────────────────────────────────────────

    async def start(self) -> None:
        self._ws_server = await serve(
            self._handler, self.host, self.port
        )
        self._bound_port = self._ws_server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._ws_server is not None:
            self._ws_server.close()
            await self._ws_server.wait_closed()
            self._ws_server = None

    # ── connection handling ───────────────────────────────────

    async def _handler(self, websocket: websockets.ServerConnection) -> None:
        """Handle a single WebSocket connection lifetime."""
        server = self.server
        client_id = server.registry.add(websocket)
        await server.handle_connect(client_id)
        try:
            async for raw in websocket:
                await server.handle_client_message(client_id, raw)
        except ConnectionClosed:
            pass
        finally:
            await server.handle_disconnect(client_id)

    async def on_connect(self, client_id: str) -> None:
        """Greet the newly connected client."""
        await self.send_message(client_id, make_message(
            TYPE_SYSTEM,
            {"client_id": client_id, "message": "connected"},
        ))

    async def on_disconnect(self, client_id: str) -> None:
        """Notify the remaining clients that this client disconnected."""
        if not self.server._stopping:
            await self.server.broadcast(make_message(
                TYPE_SYSTEM,
                {"client_id": client_id, "message": "disconnected"},
            ), persist=False)

    # ── outbound delivery ─────────────────────────────────────

    async def send_message(self, client_id: str, message: dict) -> None:
        connection = self.server.registry.get(client_id)
        if connection is None:
            return
        await connection.send(serialize(message))

    async def broadcast(self, message: dict) -> None:
        connections = self.server.registry.connections()
        if connections:
            websockets.broadcast(connections, serialize(message))

    async def channel_broadcast(self, channel: str, message: dict) -> None:
        member_ids = self.server.registry.channel_members(channel)
        if not member_ids:
            return
        connections = self.server.registry.connections_for(member_ids)
        if connections:
            websockets.broadcast(connections, serialize(message))


register_transport("websocket", WebSocketTransport)
register_transport("ws", WebSocketTransport)


class NotificationServer:
    """Notification server with a pluggable message backbone and transport."""

    def __init__(self, host: str = "127.0.0.1", ws_port: int = 8765,
                 rest_port: int = 8080, redis_url: str | None = None,
                 database_url: str | None = None,
                 redis_client=None, message_store=None,
                 transport: type[BaseTransport] | None = None,
                 rate_limit: int | None = None,
                 message_ttl_days: int | None = None) -> None:
        self.host = host
        self.ws_port = ws_port
        self.rest_port = rest_port
        self.registry = ClientRegistry()
        self.server_id = f"server-{next(_server_ids)}"
        self._stopping = False
        self._rest_runner: web.AppRunner | None = None
        self._rest_site: web.TCPSite | None = None
        self.ws_bound_port: int | None = None
        self.rest_bound_port: int | None = None

        self._rate_limit = (
            rate_limit if rate_limit is not None
            else int(os.environ.get("RATE_LIMIT", str(DEFAULT_RATE_LIMIT)))
        )
        self._message_ttl_days = (
            message_ttl_days if message_ttl_days is not None
            else int(os.environ.get("MESSAGE_TTL_DAYS", "7"))
        )
        self.rate_limiter = RateLimiter(limit=self._rate_limit)
        self._cleanup_interval_seconds = 3600
        self._cleanup_task: asyncio.Task | None = None

        transport_cls = transport or get_transport_class()
        self.transport: BaseTransport = transport_cls(
            server=self, host=host, port=ws_port
        )

        self._redis_url = (
            redis_url if redis_url is not None
            else os.environ.get("REDIS_URL")
        )
        self._database_url = (
            database_url if database_url is not None
            else os.environ.get("DATABASE_URL")
        )

        if redis_client is not None or self._redis_url:
            self.broker = RedisBackbone(
                redis_client=redis_client, redis_url=self._redis_url
            )
        else:
            self.broker = None

        self.store = message_store or MessageStore(
            database_url=self._database_url
        )

    @property
    def connected_clients(self) -> int:
        """Convenience alias for the current client count."""
        return self.registry.count

    @property
    def uses_redis_backbone(self) -> bool:
        """True when messages are distributed through Redis pub/sub."""
        return self.broker is not None

    # ── lifecycle ───────────────────────────────────────────────

    async def start(self) -> "NotificationServer":
        """Start the persistence layer, message backbone, transport and REST."""
        self._stopping = False
        await self.store.start()

        if self.broker is not None:
            await self.broker.start(self._dispatch)
            await self._restore_state()
            self.rate_limiter.set_redis(self.broker.redis)

        await self.transport.start()
        self.ws_bound_port = self.transport.bound_port

        self._cleanup_task = asyncio.create_task(self._run_message_cleanup())

        rest_app = web.Application()
        rest_app.router.add_get("/health", self.health_handler)
        rest_app.router.add_get("/channels", self.channels_handler)
        rest_app.router.add_get(
            "/channels/{name}/subscribers", self.channel_subscribers_handler
        )
        rest_app.router.add_get("/messages", self.messages_handler)
        rest_app.router.add_get("/history", self.history_handler)
        self._rest_runner = web.AppRunner(rest_app)
        await self._rest_runner.setup()
        self._rest_site = web.TCPSite(self._rest_runner, self.host, self.rest_port)
        await self._rest_site.start()
        self.rest_bound_port = self._rest_site._server.sockets[0].getsockname()[1]

        log.info(
            "Notification server listening on %s://%s:%s and http://%s:%s",
            type(self.transport).__name__.lower(),
            self.host, self.ws_bound_port, self.host, self.rest_bound_port,
        )
        return self

    async def stop(self) -> None:
        """Stop the backbone, transport, REST endpoint and store."""
        self._stopping = True
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        if self.broker is not None:
            await self.broker.stop()
        await self.transport.stop()
        if self._rest_runner is not None:
            await self._rest_runner.cleanup()
        await self.store.stop()

    # ── core client lifecycle hooks (called by the transport) ─

    async def handle_connect(self, client_id: str) -> None:
        """Register a client with the core and run transport connect hooks."""
        await self._register_client(client_id)
        await self.transport.on_connect(client_id)

    async def handle_disconnect(self, client_id: str) -> None:
        """Clean up a disconnected client and run transport disconnect hooks."""
        channels = self.registry.channels_for(client_id)
        await self._cleanup_client_state(client_id, channels)
        self.registry.remove(client_id)
        await self.transport.on_disconnect(client_id)

    async def handle_client_message(self, sender_id: str, raw: Any) -> None:
        """Parse and dispatch a message received from a client."""
        await self._handle_client_message(sender_id, raw)

    async def _register_client(self, client_id: str) -> None:
        """Persist a client's connection state and start listening for it."""
        if self.broker is None:
            return
        await self.broker.ensure_client_channel(client_id)
        await self.broker.store_client_state(client_id, {
            "client_id": client_id,
            "server_id": self.server_id,
            "connected_at": utcnow_iso(),
        })

    async def _cleanup_client_state(self, client_id: str, channels) -> None:
        """Remove a client's persisted state from Redis."""
        if self.broker is None or self._stopping:
            return
        for channel in channels:
            await self.broker.remove_channel_subscriber(channel, client_id)
            await self.broker.ensure_unsubscribed(channel)
        await self.broker.remove_client_state(client_id)

    async def _restore_state(self) -> None:
        """Rebuild local channel subscriptions from Redis state."""
        if self.broker is None:
            return
        subscriptions = await self.broker.load_channel_subscriptions()
        for channel, client_ids in subscriptions.items():
            for client_id in client_ids:
                self.registry.subscribe(client_id, channel)
            await self.broker.ensure_subscribed(channel)

    async def _handle_client_message(self, sender_id: str, raw: Any) -> None:
        """Parse and dispatch a message received from a client."""
        if not await self.rate_limiter.allow(sender_id):
            await self._send(sender_id, make_message(
                TYPE_SYSTEM,
                {"error": "rate limit exceeded",
                 "limit": self.rate_limiter.limit,
                 "client_id": sender_id},
            ))
            return
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            await self._send(sender_id, make_message(
                TYPE_SYSTEM, {"error": "invalid JSON message"}
            ))
            return

        message_type = data.get("type")
        payload = data.get("payload") or {}
        channel = data.get("channel") or payload.get("channel")

        if message_type not in ALLOWED_TYPES:
            await self._send(sender_id, make_message(
                TYPE_SYSTEM,
                {"error": f"unsupported message type: {message_type!r}"},
            ))
            return

        if message_type == TYPE_SUBSCRIBE:
            if not channel:
                await self._send(sender_id, make_message(
                    TYPE_SYSTEM, {"error": "subscribe requires a channel"}
                ))
                return
            self.registry.subscribe(sender_id, channel)
            if self.broker is not None:
                await self.broker.ensure_subscribed(channel)
                await self.broker.add_channel_subscriber(channel, sender_id)
            await self._send(sender_id, make_message(
                TYPE_SYSTEM,
                {"message": "subscribed", "channel": channel,
                 "client_id": sender_id},
            ))
        elif message_type == TYPE_UNSUBSCRIBE:
            if not channel:
                await self._send(sender_id, make_message(
                    TYPE_SYSTEM, {"error": "unsubscribe requires a channel"}
                ))
                return
            self.registry.unsubscribe(sender_id, channel)
            if self.broker is not None:
                if not self.registry.channel_members(channel):
                    await self.broker.ensure_unsubscribed(channel)
                await self.broker.remove_channel_subscriber(channel, sender_id)
            await self._send(sender_id, make_message(
                TYPE_SYSTEM,
                {"message": "unsubscribed", "channel": channel,
                 "client_id": sender_id},
            ))
        elif message_type == TYPE_BROADCAST:
            message = make_message(
                TYPE_BROADCAST, {"sender": sender_id, **payload}
            )
            if channel:
                await self.channel_broadcast(channel, message)
            else:
                await self.broadcast(message)
        elif message_type == TYPE_DIRECT:
            target = payload.get("target_id")
            delivered = await self.direct(target, make_message(
                TYPE_DIRECT, {"sender": sender_id, **payload}
            ))
            if not delivered:
                await self._send(sender_id, make_message(
                    TYPE_SYSTEM,
                    {"error": "direct target not connected",
                     "target_id": target},
                ))
        else:  # TYPE_SYSTEM
            message = make_message(
                TYPE_SYSTEM, {"sender": sender_id, **payload}
            )
            if channel:
                await self.channel_broadcast(channel, message)
            else:
                await self.broadcast(message)

    # ── messaging primitives ───────────────────────────────────

    async def _send(self, client_id: str, message: dict) -> None:
        """Send a message dict to a single client."""
        if self.broker is not None:
            await self.broker.publish_client(client_id, message)
            return
        await self._send_local(client_id, message)

    async def _send_local(self, client_id: str, message: dict) -> None:
        """Send a message directly to a locally connected client."""
        await self.transport.send_message(client_id, message)

    async def send(self, client_id: str, message: dict) -> None:
        """Public alias for :meth:`_send`."""
        await self._send(client_id, message)

    async def direct(self, client_id: str, message: dict) -> bool:
        """Send a message directly to one client by ID.

        Returns True when the message was routed, False when the target is
        unknown (and therefore unreachable).
        """
        if self.broker is not None:
            state = await self.broker.get_client_state(client_id)
            if state is None:
                return False
            await self.broker.publish_client(client_id, message)
        else:
            if self.registry.get(client_id) is None:
                return False
            await self._send_local(client_id, message)
        await self._persist(CHANNEL_DIRECT, message)
        return True

    async def broadcast(self, message: dict, persist: bool = True) -> None:
        """Broadcast a message dict to every connected client."""
        if self.broker is not None:
            await self.broker.publish_broadcast(message)
        else:
            await self.transport.broadcast(message)
        if persist:
            await self._persist(CHANNEL_BROADCAST, message)

    async def channel_broadcast(self, channel: str, message: dict) -> None:
        """Broadcast a message dict to subscribers of a named channel."""
        if self.broker is not None:
            await self.broker.publish_channel(channel, message)
        else:
            await self.transport.channel_broadcast(channel, message)
        await self._persist(channel, message)

    async def _persist(self, channel: str, message: dict) -> None:
        """Store a distributed message in the history store."""
        if self.store is None:
            return
        await self.store.store(
            channel, message["type"], message["payload"], message["timestamp"]
        )

    # ── message expiry ─────────────────────────────────────────

    async def _run_message_cleanup(self) -> None:
        """Background task deleting messages older than ``MESSAGE_TTL_DAYS``."""
        while not self._stopping:
            try:
                deleted = await self.store.cleanup_expired(
                    self._message_ttl_days
                )
                if deleted:
                    log.info("Cleaned up %d expired messages", deleted)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Message cleanup failed")
            try:
                await asyncio.sleep(self._cleanup_interval_seconds)
            except asyncio.CancelledError:
                raise

    # ── Redis backbone dispatch ────────────────────────────────

    async def _dispatch(self, channel: str, message: dict) -> None:
        """Deliver a message received from Redis to local clients."""
        if channel == BROADCAST_CHANNEL:
            await self._broadcast_local(message)
        elif channel.startswith(CHANNEL_PUBSUB_PREFIX):
            name = channel[len(CHANNEL_PUBSUB_PREFIX):]
            await self._channel_broadcast_local(name, message)
        elif channel.startswith(CLIENT_PUBSUB_PREFIX):
            client_id = channel[len(CLIENT_PUBSUB_PREFIX):]
            await self._send_local(client_id, message)

    async def _broadcast_local(self, message: dict) -> None:
        """Deliver a broadcast to every locally connected client."""
        await self.transport.broadcast(message)

    async def _channel_broadcast_local(self, channel: str, message: dict) -> None:
        """Deliver a channel message to local subscribers of the channel."""
        await self.transport.channel_broadcast(channel, message)

    # ── REST endpoints ─────────────────────────────────────────

    async def health_handler(self, request: web.Request) -> web.Response:
        """REST ``GET /health`` — report the connected client count."""
        return web.json_response({
            "status": "ok",
            "clients": self.registry.count,
        })

    async def channels_handler(self, request: web.Request) -> web.Response:
        """REST ``GET /channels`` — list channels and subscriber counts."""
        return web.json_response({
            "channels": self.registry.channels(),
        })

    async def channel_subscribers_handler(
        self, request: web.Request
    ) -> web.Response:
        """REST ``GET /channels/{name}/subscribers`` — list subscriber IDs."""
        name = request.match_info["name"]
        return web.json_response({
            "channel": name,
            "subscribers": self.registry.channel_members(name),
        })

    async def messages_handler(self, request: web.Request) -> web.Response:
        """REST ``GET /messages`` — return persisted message history."""
        try:
            limit = int(request.query.get("limit", "50"))
            offset = int(request.query.get("offset", "0"))
        except ValueError:
            limit, offset = 50, 0
        limit = max(0, min(limit, 500))
        offset = max(0, offset)
        messages, total = await self.store.list(limit=limit, offset=offset)
        return web.json_response({
            "messages": messages,
            "total": total,
            "limit": limit,
            "offset": offset,
        })

    async def history_handler(self, request: web.Request) -> web.Response:
        """REST ``GET /history`` — messages for a channel/time range."""
        channel = request.query.get("channel") or None
        since = request.query.get("since")
        try:
            limit = int(request.query.get("limit", "50"))
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 500))
        messages, has_more = await self.store.history(
            channel=channel, since=since, limit=limit
        )
        return web.json_response({
            "channel": channel,
            "since": since,
            "limit": limit,
            "messages": messages,
            "has_more": has_more,
        })
