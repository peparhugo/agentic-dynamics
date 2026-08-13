"""
Notification server with a pluggable transport layer.

Core features:
- Accept client connections (the wire protocol is provided by a pluggable
  :class:`BaseTransport`; the default is the WebSocket transport).
- Assign each client a unique ID on connect.
- Broadcast a message to ALL connected clients.
- Channel-based subscriptions: clients subscribe to named channels and receive
  only the messages routed to those channels.
- Handle client disconnect (clean removal, including channel memberships).
- REST endpoints: GET /health, GET /channels, GET /channels/{name}/subscribers,
  GET /messages.

Pluggable transports:
- :class:`BaseTransport` defines the interface (``on_connect``,
  ``on_disconnect``, ``send_message``, ``broadcast``) that any transport
  (WebSocket, SSE, polling, raw TCP, ...) must implement so it can be dropped
  into :class:`NotificationServer` without touching the core notification
  logic.
- :class:`WebSocketTransport` implements the WebSocket wire protocol on top of
  the `websockets` library and is the default transport.
- The active transport is selected through the ``TRANSPORT`` environment
  variable (e.g. ``TRANSPORT=websocket``); see :func:`get_transport`.

Redis pub/sub backbone:
- When a RedisBackend is configured (REDIS_URL env var) every relayed message
  is published to a shared Redis channel.  Each server instance runs a worker
  that subscribes to that channel and delivers messages to its locally
  connected clients, so multiple server instances can share the same backbone.
- Client connection state (connected client ids, channel memberships) is
  mirrored into Redis and therefore survives server restarts.

Persistence:
- When a MessageStore is configured (DATABASE_URL env var) every relayed
  message is stored in SQLite and can be fetched via GET /messages.

Message format (all messages are JSON):
    {"type": str, "payload": dict, "timestamp": str}
Supported types: "broadcast", "direct", "subscribe", "unsubscribe", "system".

Protocol (client -> server):
- {"type": "broadcast", "payload": {...}}    -> relayed to every connected client.
- {"type": "broadcast", "channel": "name", "payload": {...}} -> relayed only to
  subscribers of the named channel (channel may also live inside payload).
- {"type": "direct", "target_id": "...", "payload": {...}} -> delivered to one client.
- {"type": "subscribe", "channel": "name"}   -> subscribe sender to a channel.
- {"type": "unsubscribe", "channel": "name"} -> unsubscribe sender from a channel.
- {"type": "system", ...}                    -> ignored (server-only).

Protocol (server -> client):
- On connect, the new client receives:
    {"type": "system", "payload": {"event": "connect", "client_id": "...",
     "connected_clients": N}, "timestamp": "..."}
- On disconnect, every remaining client receives a matching "disconnect" event.
- Errors are delivered back to the offending client as a "system" error event.

Uses the `websockets` library (asyncio implementation) and a lock-guarded
client registry that is safe to use across asyncio tasks/threads.
"""

from __future__ import annotations

import abc
import asyncio
import json
import os
import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from message_store import MessageStore
from redis_backend import RedisBackend


def now_iso() -> str:
    """Current UTC time as an ISO-8601 timestamp string."""
    return datetime.now(timezone.utc).isoformat()


def build_message(msg_type: str, payload: dict) -> dict:
    """Build a message conforming to the shared JSON schema."""
    return {"type": msg_type, "payload": payload, "timestamp": now_iso()}


def int_env(name: str, default: int) -> int:
    """Read an integer environment variable, falling back to *default*."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# ── Transport layer ─────────────────────────────────────────────────────


class TransportError(Exception):
    """Base class for transport-level failures."""


class TransportConnectionClosed(TransportError):
    """Raised when a send to a connection fails because the connection closed."""


class BaseTransport(abc.ABC):
    """
    Abstract transport layer for the notification server.

    A transport owns the wire protocol — how message bytes reach clients and
    how incoming client sessions are driven — while :class:`NotificationServer`
    owns the message semantics (dispatch, channels, persistence, REST state).
    Any implementation of this interface can be used by the server without
    modifying the core notification logic.

    Implementations receive a back-reference to the owning server through
    ``self.server`` so they can read client state (``server.registry``) and
    hand incoming messages to the core logic (``server._dispatch``).
    """

    name: str = "base"

    def __init__(self, server: NotificationServer | None = None) -> None:
        self.server = server

    @abc.abstractmethod
    async def on_connect(self, client_id: str, connection: object) -> None:
        """Called when a client session starts (its id has already been assigned)."""

    @abc.abstractmethod
    async def on_disconnect(self, client_id: str, connection: object) -> None:
        """Called when a client session ends; triggers server-side cleanup."""

    @abc.abstractmethod
    async def send_message(self, connection: object, message: dict) -> None:
        """Serialize and deliver *message* to a single *connection*."""

    @abc.abstractmethod
    async def broadcast(self, message: dict, exclude: set[str] | None = None) -> int:
        """Deliver *message* to every locally connected client."""


class WebSocketTransport(BaseTransport):
    """WebSocket transport built on the `websockets` library (default)."""

    name = "websocket"

    def __init__(
        self,
        server: NotificationServer | None = None,
        host: str = "127.0.0.1",
        port: int = 0,
    ) -> None:
        super().__init__(server=server)
        self.host = host
        self.port = port
        self._server = None

    # ── Server lifecycle ─────────────────────────────────────────

    async def start(
        self, host: str | None = None, port: int | None = None
    ) -> "WebSocketTransport":
        """Bind and start accepting WebSocket connections."""
        if host is not None:
            self.host = host
        if port is not None and port != 0:
            self.port = port
        self._server = await serve(
            self.handle_client,
            self.host,
            self.port,
            process_request=self.process_request,
        )
        if self.port == 0:
            self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def stop(self) -> None:
        """Close the WebSocket server and stop accepting connections."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def serve_forever(self) -> None:
        """Run the accept loop until the server is stopped."""
        if self._server is not None:
            await self._server.serve_forever()

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}"

    # ── Session lifecycle ────────────────────────────────────────

    async def handle_client(self, websocket: ServerConnection) -> None:
        """Session handler: register, notify, relay messages, clean up."""
        client_id = await self.server._assign_id()
        await self.on_connect(client_id, websocket)
        try:
            async for raw in websocket:
                await self.server._dispatch(client_id, websocket, raw)
        except ConnectionClosed:
            pass
        finally:
            await self.on_disconnect(client_id, websocket)

    async def on_connect(self, client_id: str, websocket: ServerConnection) -> None:
        await self.server.registry.add(client_id, websocket)
        await self.server._send_connect_notice(client_id, websocket)

    async def on_disconnect(self, client_id: str, websocket: ServerConnection) -> None:
        await self.server._shutdown_client(client_id)

    # ── Message delivery ─────────────────────────────────────────

    async def send_message(self, websocket: ServerConnection, message: dict) -> None:
        try:
            await websocket.send(json.dumps(message))
        except ConnectionClosed:
            raise TransportConnectionClosed() from None

    async def broadcast(self, message: dict, exclude: set[str] | None = None) -> int:
        """Send *message* to every locally connected WebSocket client."""
        exclude = exclude or set()
        delivered = 0
        for client_id, websocket in (await self.server.registry.snapshot()).items():
            if client_id in exclude:
                continue
            try:
                await self.send_message(websocket, message)
                delivered += 1
            except TransportConnectionClosed:
                await self.server.registry.remove(client_id)
        return delivered

    # ── REST endpoints ───────────────────────────────────────────

    async def _json_response(self, status: int, body: dict) -> Response:
        encoded = json.dumps(body).encode("utf-8")
        headers = Headers(
            {"Content-Type": "application/json", "Content-Length": str(len(encoded))}
        )
        return Response(status, "OK", headers, encoded)

    async def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        """Intercept plain HTTP requests for the REST endpoints."""
        parsed = urlparse(request.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/health":
            return await self._json_response(
                200, await self.server._rest_health()
            )
        if path == "/channels" or path == "/channels/":
            return await self._json_response(
                200, await self.server._rest_channels()
            )
        if path.startswith("/channels/"):
            segments = [seg for seg in path[len("/channels/"):].split("/") if seg]
            if not segments:
                return await self.process_request(connection, request)
            return await self._json_response(
                200, await self.server._rest_channel(segments[0])
            )
        if path == "/messages":
            return await self._json_response(
                200, await self.server._rest_messages(query)
            )
        if path == "/history":
            return await self._json_response(
                200, await self.server._rest_history(query)
            )
        return None


TRANSPORTS: dict[str, type[BaseTransport]] = {
    WebSocketTransport.name: WebSocketTransport,
}


def get_transport(
    name: str | None = None, server: NotificationServer | None = None
) -> BaseTransport:
    """Build a transport by name.

    The name defaults to the ``TRANSPORT`` environment variable and finally to
    ``websocket`` (WebSocketTransport is the default transport).  Unknown
    transports raise :class:`ValueError`.
    """
    transport_name = (name or os.environ.get("TRANSPORT") or "websocket").strip().lower()
    try:
        cls = TRANSPORTS[transport_name]
    except KeyError:
        raise ValueError(
            f"unknown transport {transport_name!r}; "
            f"available transports: {sorted(TRANSPORTS)}"
        ) from None
    return cls(server=server)


class RateLimiter:
    """Per-client sliding-window rate limit backed by Redis counters.

    Every incoming client message is checked through :meth:`allow`.  When the
    client has already used its quota the message is rejected and the caller
    replies with an error instead of dropping the connection.

    Enforcement is local-first for speed: an in-process sliding window per
    client answers the common case with no network round trip, while every
    allowed request is mirrored into a Redis counter (per client ID) in the
    background so limits are shared across server instances.  When the local
    window is full the authoritative Redis counter is consulted before
    rejecting.  Without a Redis backend the limiter is a no-op (there are no
    shared counters to enforce against).
    """

    def __init__(
        self,
        backend: RedisBackend | None,
        limit: int,
        window: int = 60,
    ) -> None:
        self.backend = backend
        self.limit = max(1, int(limit))
        self.window = max(1, int(window))
        self._local: dict[str, deque[float]] = {}
        self._sync_tasks: set[asyncio.Task] = set()

    def _queue(self, client_id: str) -> deque[float]:
        now = time.monotonic()
        queue = self._local.get(client_id)
        if queue is None:
            queue = self._local[client_id] = deque()
        while queue and now - queue[0] >= self.window:
            queue.popleft()
        return queue

    async def allow(self, client_id: str) -> bool:
        if self.backend is None:
            return True
        queue = self._queue(client_id)
        if len(queue) < self.limit:
            queue.append(time.monotonic())
            self._mirror(client_id)
            return True
        # Local window is full: the shared Redis counter has the final say.
        try:
            return await self.backend.rate_limit_allow(
                client_id, self.limit, self.window
            )
        except Exception:
            # Fail open: a Redis hiccup must not break message delivery.
            return True

    def _mirror(self, client_id: str) -> None:
        task = asyncio.create_task(self._sync_counter(client_id))
        self._sync_tasks.add(task)
        task.add_done_callback(self._sync_tasks.discard)

    async def _sync_counter(self, client_id: str) -> None:
        try:
            await self.backend.rate_limit_record(client_id, self.window)
        except Exception:
            pass

    async def close(self) -> None:
        for task in list(self._sync_tasks):
            task.cancel()
        if self._sync_tasks:
            await asyncio.gather(*self._sync_tasks, return_exceptions=True)
        self._sync_tasks.clear()


class ClientRegistry:
    """
    Thread-safe registry mapping unique client IDs to transport connections.

    Access is guarded by an asyncio.Lock so concurrent handlers (and external
    threads using the same event loop) never observe partial state.

    Connections are opaque transport handles: the core server never touches
    their internals, only the active :class:`BaseTransport` does.

    When a RedisBackend is provided the connection state (client ids and
    channel memberships) is mirrored into Redis so it survives restarts and
    is shared across server instances.  The live connection objects always stay
    in memory (they cannot be stored in Redis).
    """

    def __init__(
        self,
        backend: RedisBackend | None = None,
        server_id: str | None = None,
    ) -> None:
        self._clients: dict[str, object] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()
        self.backend = backend
        self.server_id = server_id or uuid.uuid4().hex

    async def add(self, client_id: str, connection: object) -> None:
        async with self._lock:
            self._clients[client_id] = connection
        if self.backend is not None:
            await self.backend.register_client(client_id, self.server_id)

    async def subscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)
        if self.backend is not None:
            await self.backend.add_channel_member(client_id, channel)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            members = self._channels.get(channel)
            if members is not None:
                members.discard(client_id)
                if not members:
                    del self._channels[channel]
        if self.backend is not None:
            await self.backend.remove_channel_member(client_id, channel)

    async def channel_members(self, channel: str) -> set[str]:
        async with self._lock:
            return set(self._channels.get(channel, set()))

    async def channels_snapshot(self) -> dict[str, set[str]]:
        async with self._lock:
            return {ch: set(members) for ch, members in self._channels.items()}

    async def remove_from_all_channels(self, client_id: str) -> None:
        async with self._lock:
            for channel in list(self._channels.keys()):
                members = self._channels[channel]
                members.discard(client_id)
                if not members:
                    del self._channels[channel]
        if self.backend is not None:
            for channel in await self.backend.global_channels():
                await self.backend.remove_channel_member(client_id, channel)

    async def remove(self, client_id: str) -> object | None:
        async with self._lock:
            removed = self._clients.pop(client_id, None)
        if removed is not None and self.backend is not None:
            await self.backend.unregister_client(client_id)
        return removed

    async def get(self, client_id: str) -> object | None:
        async with self._lock:
            return self._clients.get(client_id)

    async def contains(self, client_id: str) -> bool:
        async with self._lock:
            return client_id in self._clients

    async def global_contains(self, client_id: str) -> bool:
        """Whether *client_id* is known anywhere (local or another instance)."""
        if self.backend is not None:
            return await self.backend.client_exists(client_id)
        return await self.contains(client_id)

    async def count(self) -> int:
        async with self._lock:
            return len(self._clients)

    async def ids(self) -> list[str]:
        async with self._lock:
            return list(self._clients.keys())

    async def snapshot(self) -> dict[str, object]:
        async with self._lock:
            return dict(self._clients)


class NotificationServer:
    """Handles message dispatch, client state and REST state.

    The wire protocol is delegated to the configured :class:`BaseTransport`
    (WebSocket by default, selectable through the ``TRANSPORT`` env var), so
    the core logic works with any transport implementation.
    """

    def __init__(
        self,
        registry: ClientRegistry | None = None,
        backend: RedisBackend | None = None,
        store: MessageStore | None = None,
        server_id: str | None = None,
        transport: BaseTransport | None = None,
        rate_limit: int | None = None,
        rate_limit_window: int = 60,
        message_ttl_days: int | None = None,
        cleanup_interval: float | None = None,
    ) -> None:
        self.server_id = server_id or uuid.uuid4().hex
        self.backend = backend
        self.store = store
        self.transport = transport or get_transport()
        self.transport.server = self
        self.registry = registry or ClientRegistry(
            backend=backend, server_id=self.server_id
        )
        self._next_id = 0
        self._id_lock = asyncio.Lock()
        self._broker_task: asyncio.Task | None = None
        self._pubsub = None
        limit = int_env("RATE_LIMIT", 100) if rate_limit is None else rate_limit
        if limit and limit > 0:
            self._rate_limiter = RateLimiter(backend, limit, rate_limit_window)
        else:
            self._rate_limiter = None
        self._message_ttl_days = (
            int_env("MESSAGE_TTL_DAYS", 7)
            if message_ttl_days is None
            else message_ttl_days
        )
        self._cleanup_interval = cleanup_interval or 3600.0
        self._cleanup_task: asyncio.Task | None = None

    # ── Redis backbone lifecycle ────────────────────────────────────

    async def start_backend(self) -> None:
        """Subscribe the local worker to the Redis backbone."""
        if self.backend is None:
            return
        self._pubsub = self.backend.pubsub()
        await self._pubsub.subscribe(self.backend.messages_channel)
        self._broker_task = asyncio.create_task(self._broker_loop())

    async def stop_backend(self) -> None:
        """Stop the local Redis worker."""
        if self._broker_task is not None:
            self._broker_task.cancel()
            try:
                await self._broker_task
            except asyncio.CancelledError:
                pass
            self._broker_task = None
        if self._pubsub is not None:
            try:
                await self._pubsub.unsubscribe()
            except Exception:
                pass
            await self._pubsub.close()
            self._pubsub = None

    async def _broker_loop(self) -> None:
        while True:
            try:
                async for raw in self._pubsub.listen():
                    if raw["type"] != "message":
                        continue
                    try:
                        envelope = json.loads(raw["data"])
                    except (json.JSONDecodeError, TypeError):
                        continue
                    await self._handle_broker_envelope(envelope)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(0.05)

    async def _handle_broker_envelope(self, envelope: dict) -> None:
        kind = envelope.get("kind")
        message = envelope.get("message")
        if kind == "broadcast":
            await self.transport.broadcast(message)
        elif kind == "channel":
            await self._deliver_to_channel_local(envelope.get("channel"), message)
        elif kind == "direct":
            await self._deliver_direct_local(envelope.get("target_id"), message)

    # ── Message expiry maintenance ──────────────────────────────────

    async def start_maintenance(self) -> None:
        """Start the background task that expires messages older than the TTL."""
        if self.store is None or self._cleanup_task is not None:
            return
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_maintenance(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        if self._rate_limiter is not None:
            await self._rate_limiter.close()

    async def _cleanup_loop(self) -> None:
        while True:
            try:
                await self._run_cleanup()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            await asyncio.sleep(self._cleanup_interval)

    async def _run_cleanup(self) -> None:
        """Delete messages older than ``MESSAGE_TTL_DAYS`` days."""
        if self.store is None:
            return
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=self._message_ttl_days
        )
        await self.store.delete_older_than(cutoff.isoformat())

    # ── Session lifecycle ───────────────────────────────────────────

    async def _assign_id(self) -> str:
        if self.backend is not None:
            return await self.backend.next_client_id()
        async with self._id_lock:
            self._next_id += 1
            return str(self._next_id)

    async def _send_connect_notice(self, client_id: str, connection: object) -> None:
        count = await self.registry.count()
        message = build_message(
            "system",
            {"event": "connect", "client_id": client_id, "connected_clients": count},
        )
        try:
            await self.transport.send_message(connection, message)
        except TransportConnectionClosed:
            pass

    async def _shutdown_client(self, client_id: str) -> None:
        removed = await self.registry.remove(client_id)
        if removed is None:
            return
        await self.registry.remove_from_all_channels(client_id)
        count = await self.registry.count()
        message = build_message(
            "system",
            {"event": "disconnect", "client_id": client_id, "connected_clients": count},
        )
        await self.broadcast(message)

    # ── Message dispatch ────────────────────────────────────────────

    async def _persist(self, channel: str, message: dict) -> None:
        if self.store is None:
            return
        try:
            await self.store.record(
                channel, message["type"], message["payload"], message["timestamp"]
            )
        except Exception:
            pass

    async def _dispatch(self, sender_id: str, connection: object, raw) -> None:
        if self._rate_limiter is not None:
            allowed = await self._rate_limiter.allow(sender_id)
            if not allowed:
                await self._send_error(sender_id, "rate limit exceeded")
                return

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            await self._send_error(
                sender_id, "invalid JSON message", target_id=None
            )
            return

        if not isinstance(data, dict):
            await self._send_error(sender_id, "message must be a JSON object")
            return

        msg_type = data.get("type")
        payload = data.get("payload", {})
        if not isinstance(payload, dict):
            await self._send_error(sender_id, "payload must be a JSON object")
            return

        if msg_type == "broadcast":
            channel = data.get("channel")
            if not isinstance(channel, str) or not channel.strip():
                channel = payload.get("channel")
            if isinstance(channel, str) and channel.strip():
                channel = channel.strip()
                message = build_message("broadcast", payload)
                await self._persist(channel, message)
                await self._broadcast_to_channel(channel, message)
            else:
                message = build_message("broadcast", payload)
                await self._persist("", message)
                await self.broadcast(message)
        elif msg_type == "direct":
            target_id = data.get("target_id") or payload.get("target_id")
            await self._send_direct(sender_id, target_id, payload)
        elif msg_type == "subscribe":
            await self._subscribe(sender_id, data, payload)
        elif msg_type == "unsubscribe":
            await self._unsubscribe(sender_id, data, payload)
        elif msg_type == "system":
            # System messages are generated by the server only.
            pass
        else:
            await self._send_error(sender_id, f"unsupported message type: {msg_type!r}")

    async def _subscribe(self, sender_id: str, data: dict, payload: dict) -> None:
        channel = data.get("channel") or payload.get("channel")
        if not isinstance(channel, str) or not channel.strip():
            await self._send_error(
                sender_id, "subscribe requires a non-empty channel name"
            )
            return
        await self.registry.subscribe(sender_id, channel.strip())

    async def _unsubscribe(self, sender_id: str, data: dict, payload: dict) -> None:
        channel = data.get("channel") or payload.get("channel")
        if not isinstance(channel, str) or not channel.strip():
            await self._send_error(
                sender_id, "unsubscribe requires a non-empty channel name"
            )
            return
        await self.registry.unsubscribe(sender_id, channel.strip())

    async def _send_direct(self, sender_id: str, target_id, payload: dict) -> None:
        if not isinstance(target_id, str) or not target_id:
            await self._send_error(sender_id, "direct message requires a target_id")
            return
        if not await self.registry.global_contains(target_id):
            await self._send_error(
                sender_id, "target not found", target_id=target_id
            )
            return
        message = build_message("direct", payload)
        await self._persist("", message)
        if self.backend is not None:
            await self.backend.publish(
                {"kind": "direct", "target_id": target_id, "message": message}
            )
            return
        await self._deliver_direct_local(target_id, message)

    async def _send_error(self, sender_id: str, message: str, target_id=None) -> None:
        payload = {"event": "error", "message": message}
        if target_id is not None:
            payload["target_id"] = target_id
        connection = await self.registry.get(sender_id)
        if connection is None:
            return
        try:
            await self.transport.send_message(connection, build_message("system", payload))
        except TransportConnectionClosed:
            await self.registry.remove(sender_id)

    # ── Outgoing ────────────────────────────────────────────────────

    async def broadcast(self, message: dict, exclude: set[str] | None = None) -> int:
        """Route a broadcast: via Redis when a backbone is present, else local."""
        if self.backend is not None:
            await self.backend.publish({"kind": "broadcast", "message": message})
            return 0
        return await self.transport.broadcast(message, exclude)

    async def _broadcast_to_channel(self, channel: str, message: dict) -> int:
        """Route a channel message: via Redis when a backbone is present, else local."""
        if self.backend is not None:
            await self.backend.publish(
                {"kind": "channel", "channel": channel, "message": message}
            )
            return 0
        return await self._deliver_to_channel_local(channel, message)

    async def _deliver_to_channel_local(self, channel: str, message: dict) -> int:
        """Send *message* to locally connected subscribers of *channel*."""
        delivered = 0
        for client_id in await self.registry.channel_members(channel):
            connection = await self.registry.get(client_id)
            if connection is None:
                await self.registry.unsubscribe(client_id, channel)
                continue
            try:
                await self.transport.send_message(connection, message)
                delivered += 1
            except TransportConnectionClosed:
                await self.registry.remove(client_id)
                await self.registry.unsubscribe(client_id, channel)
        return delivered

    async def _deliver_direct_local(self, target_id: str, message: dict) -> int:
        """Deliver *message* to the local connection for *target_id*."""
        connection = await self.registry.get(target_id)
        if connection is None:
            return 0
        try:
            await self.transport.send_message(connection, message)
            return 1
        except TransportConnectionClosed:
            await self.registry.remove(target_id)
            return 0

    # ── REST state (transport-agnostic payloads) ───────────────────

    async def _rest_health(self) -> dict:
        count = await self.registry.count()
        return {"status": "ok", "connected_clients": count}

    async def _rest_channels(self) -> dict:
        channels = await self.registry.channels_snapshot()
        return {
            "channels": [
                {
                    "name": name,
                    "subscriber_count": len(members),
                    "subscribers": sorted(members),
                }
                for name, members in sorted(channels.items())
            ]
        }

    async def _rest_channel(self, name: str) -> dict:
        members = await self.registry.channel_members(name)
        return {"channel": name, "subscribers": sorted(members)}

    async def _rest_messages(self, query: dict) -> dict:
        if self.store is None:
            return {"messages": [], "total": 0}
        try:
            limit = int(query.get("limit", ["50"])[0])
        except (TypeError, ValueError):
            limit = 50
        try:
            offset = int(query.get("offset", ["0"])[0])
        except (TypeError, ValueError):
            offset = 0
        limit = max(0, min(limit, 1000))
        offset = max(0, offset)
        messages = await self.store.list_messages(limit=limit, offset=offset)
        total = await self.store.count()
        return {"messages": messages, "total": total}

    async def _rest_history(self, query: dict) -> dict:
        """Handle GET /history?channel=X&since=ISO_TIMESTAMP&limit=N&offset=N."""
        channel = (query.get("channel") or [""])[0]
        since = (query.get("since") or [None])[0]
        try:
            limit = int(query.get("limit", ["50"])[0])
        except (TypeError, ValueError):
            limit = 50
        try:
            offset = int(query.get("offset", ["0"])[0])
        except (TypeError, ValueError):
            offset = 0
        limit = max(0, min(limit, 1000))
        offset = max(0, offset)
        if self.store is None:
            return {
                "channel": channel,
                "since": since,
                "limit": limit,
                "offset": offset,
                "messages": [],
                "has_more": False,
            }
        messages, has_more = await self.store.query_history(
            channel=channel, since=since or None, limit=limit, offset=offset
        )
        return {
            "channel": channel,
            "since": since,
            "limit": limit,
            "offset": offset,
            "messages": messages,
            "has_more": has_more,
        }


class NotificationApp:
    """Wraps a transport server bound to a host/port for easy (test) control."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        notifier: NotificationServer | None = None,
        backend: RedisBackend | None = None,
        store: MessageStore | None = None,
        transport: BaseTransport | None = None,
        rate_limit: int | None = None,
        rate_limit_window: int = 60,
        message_ttl_days: int | None = None,
        cleanup_interval: float | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.backend = backend
        self.store = store
        if notifier is None:
            notifier = NotificationServer(
                backend=backend,
                store=store,
                transport=transport,
                rate_limit=rate_limit,
                rate_limit_window=rate_limit_window,
                message_ttl_days=message_ttl_days,
                cleanup_interval=cleanup_interval,
            )
        self.notifier = notifier
        self.server = None

    async def start(self) -> "NotificationApp":
        if self.backend is not None:
            await self.notifier.start_backend()
        await self.notifier.start_maintenance()
        transport = self.notifier.transport
        await transport.start(self.host, self.port)
        self.host = transport.host
        self.port = transport.port
        return self

    @property
    def url(self) -> str:
        return self.notifier.transport.url

    async def stop(self) -> None:
        await self.notifier.transport.stop()
        await self.notifier.stop_maintenance()
        if self.backend is not None:
            await self.notifier.stop_backend()


async def main(host: str = "0.0.0.0", port: int = 8765) -> None:
    """Entry point: run the notification server until interrupted.

    The transport is selected by the ``TRANSPORT`` env var (default:
    ``websocket``).
    """
    backend = None
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        backend = RedisBackend(redis_url)
        await backend.connect()

    store = None
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        store = MessageStore(database_url)
        await store.connect()

    notifier = NotificationServer(backend=backend, store=store, transport=get_transport())
    try:
        if backend is not None:
            await notifier.start_backend()
        await notifier.start_maintenance()
        await notifier.transport.start(host, port)
        try:
            await notifier.transport.serve_forever()
        finally:
            await notifier.transport.stop()
    finally:
        await notifier.stop_maintenance()
        if backend is not None:
            await notifier.stop_backend()
            await backend.close()
        if store is not None:
            await store.close()


if __name__ == "__main__":
    asyncio.run(main())
