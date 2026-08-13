"""
Notification server built on a pluggable transport layer.

The core :class:`NotificationServer` implements all routing, channel,
Redis backbone and persistence logic on top of a :class:`BaseTransport`.
The transport owns the low-level, network-specific behaviour (accepting
connections, managing their lifecycle and writing outbound messages), so
new mechanisms (SSE, polling, raw TCP) can be added without touching the
core. The active transport is selected by the TRANSPORT env var;
:class:`WebSocketTransport` is the default.

Core features:
  * Accept WebSocket connections from clients.
  * Assign each client a unique ID on connect.
  * Broadcast a message to ALL connected clients.
  * Handle client disconnect (clean removal).
  * REST endpoint: GET /health - returns the connected client count.

Message format (JSON):
  {"type": str, "payload": dict, "timestamp": str}

Supported message types: "broadcast", "direct", "system",
"subscribe", "unsubscribe".

Channels:
  * Clients subscribe to named channels via "subscribe" messages.
  * Clients can unsubscribe via "unsubscribe" messages.
  * Messages with a "channel" field route only to that channel's
    subscribers; messages without a channel broadcast to everyone.
  * REST endpoints: GET /channels and GET /channels/{name}/subscribers.

Redis backbone (optional):
  * When a Redis broker is configured (REDIS_URL env var or an explicit
    `redis_client`), every outbound message is published to a pub/sub
    channel. A subscriber worker on each server instance picks the
    message up and delivers it to the local connected clients, so
    multiple server instances can share the same Redis backbone.
  * Client connection state (connected clients and channel memberships)
    is mirrored into Redis, allowing a server that restarts to restore
    the state via `restore_state()`.

Persistence (optional):
  * When a SQLite database is configured (DATABASE_URL env var or an
    explicit `database_url`), every notification message is stored in
    the `messages` table for history.
  * REST endpoint: GET /messages?limit=50&offset=0.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import threading
import urllib.parse
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Response

logger = logging.getLogger("notification_server")

BROADCAST = "broadcast"
DIRECT = "direct"
SYSTEM = "system"
SUBSCRIBE = "subscribe"
UNSUBSCRIBE = "unsubscribe"
MSG_TYPES = (BROADCAST, DIRECT, SYSTEM, SUBSCRIBE, UNSUBSCRIBE)

HEALTH_PATH = "/health"
CHANNELS_PATH = "/channels"
MESSAGES_PATH = "/messages"

REDIS_BACKBONE_CHANNEL = os.environ.get(
    "REDIS_BACKBONE_CHANNEL", "notification:events"
)
REDIS_CLIENTS_KEY = "notification:clients"
REDIS_CHANNEL_INDEX_KEY = "notification:channels"
REDIS_CHANNEL_PREFIX = "notification:channel:"
REDIS_CLIENT_PREFIX = "notification:client:"

TRANSPORT_ENV_VAR = "TRANSPORT"
DEFAULT_TRANSPORT = "websocket"


def extract_channels(message: dict) -> list[str]:
    """Collect channel names from a subscribe/unsubscribe message.

    Accepts the channel list either at the top level ("channel") or in
    the payload ("channel" / "channels").
    """
    candidates: list[object] = []
    payload = message.get("payload")
    if isinstance(payload, dict):
        if "channels" in payload:
            candidates.append(payload["channels"])
        elif "channel" in payload:
            candidates.append(payload["channel"])
    if "channel" in message:
        candidates.append(message["channel"])

    channels: list[str] = []
    for raw in candidates:
        if isinstance(raw, str):
            channels.append(raw)
        elif isinstance(raw, (list, tuple)):
            channels.extend(c for c in raw if isinstance(c, str))
    seen: set[str] = set()
    result: list[str] = []
    for channel in channels:
        if channel and channel not in seen:
            seen.add(channel)
            result.append(channel)
    return result


def message_channel(message: dict, payload: dict) -> str | None:
    """Return the routing channel for an outgoing message, if any."""
    channel = message.get("channel")
    if not isinstance(channel, str) or not channel:
        channel = payload.get("channel")
    if isinstance(channel, str) and channel:
        return channel
    return None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def build_message(msg_type: str, payload: dict) -> dict:
    """Build a well-formed notification message dict."""
    return {
        "type": msg_type,
        "payload": dict(payload),
        "timestamp": utc_now_iso(),
    }


def _decode(value: object) -> object:
    """Decode bytes returned by a redis client into plain values."""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, bytearray):
        return bytes(value).decode("utf-8")
    if isinstance(value, (list, tuple, set)):
        return [_decode(v) for v in value]
    return value


class EventLog:
    """Append-only JSON Lines log backed by a flat file.

    Safe to use from multiple threads: each write acquires a lock and
    flushes immediately so data survives process crashes.
    """

    def __init__(self, path: str | Path | None):
        self.path = Path(path) if path else None
        self._lock = threading.Lock()

    def append(self, event: str, data: dict) -> None:
        if self.path is None:
            return
        record = {
            "event": event,
            "data": data,
            "timestamp": utc_now_iso(),
        }
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
                fh.flush()

    def read(self) -> list[dict]:
        if self.path is None or not self.path.exists():
            return []
        with self._lock:
            with self.path.open("r", encoding="utf-8") as fh:
                return [json.loads(line) for line in fh if line.strip()]


class MessageStore:
    """SQLite-backed store for message history.

    Table `messages`: id, channel, type, payload (JSON), timestamp.
    Safe to use from multiple threads: every operation acquires a lock
    and uses its own short-lived connection.
    """

    def __init__(self, database_url: str | Path | None = None):
        self._lock = threading.Lock()
        self.path = self._resolve_path(database_url)
        if self.path is not None:
            self._init_schema()

    @staticmethod
    def _resolve_path(database_url: str | Path | None) -> Path | None:
        if not database_url:
            return None
        if isinstance(database_url, str) and database_url.startswith("sqlite:///"):
            return Path(database_url[len("sqlite:///"):])
        return Path(database_url)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._conn() as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS messages ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "channel TEXT,"
                    "type TEXT NOT NULL,"
                    "payload TEXT NOT NULL,"
                    "timestamp TEXT NOT NULL"
                    ")"
                )
                conn.commit()

    def store(self, msg_type: str, channel: str | None, payload: dict,
              timestamp: str) -> int | None:
        """Insert one message row and return its id (or None if disabled)."""
        if self.path is None:
            return None
        with self._lock:
            with self._conn() as conn:
                cursor = conn.execute(
                    "INSERT INTO messages (channel, type, payload, timestamp) "
                    "VALUES (?, ?, ?, ?)",
                    (channel, msg_type, json.dumps(payload), timestamp),
                )
                conn.commit()
                return cursor.lastrowid

    def list(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """Return stored messages, newest first."""
        if self.path is None:
            return []
        limit = max(0, int(limit))
        offset = max(0, int(offset))
        with self._lock:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT id, channel, type, payload, timestamp "
                    "FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["payload"] = json.loads(item["payload"])
            except (TypeError, ValueError):
                pass
            result.append(item)
        return result

    def count(self) -> int:
        if self.path is None or not self.path.exists():
            return 0
        with self._lock:
            with self._conn() as conn:
                row = conn.execute("SELECT COUNT(*) AS n FROM messages").fetchone()
                return int(row["n"])


class RedisBackbone:
    """Pub/sub message backbone built on top of a redis client.

    The server publishes JSON envelopes to a single channel; every
    worker (server instance) that subscribes to the channel receives
    them and delivers to its local clients.
    """

    def __init__(self, client, channel: str = REDIS_BACKBONE_CHANNEL):
        self.client = client
        self.channel = channel

    async def publish(self, envelope: dict) -> int:
        """Publish an envelope to the backbone channel."""
        return await self.client.publish(self.channel, json.dumps(envelope))


class ClientRegistry:
    """Thread-safe registry mapping unique client IDs to connections."""

    def __init__(self):
        self._clients: dict[str, object] = {}
        self._lock = threading.RLock()

    def register(self, connection) -> str:
        client_id = uuid.uuid4().hex
        with self._lock:
            self._clients[client_id] = connection
        return client_id

    def unregister(self, client_id: str) -> bool:
        with self._lock:
            return self._clients.pop(client_id, None) is not None

    def get(self, client_id: str):
        with self._lock:
            return self._clients.get(client_id)

    def restore(self, client_id: str) -> bool:
        """Restore a client ID recovered from Redis (no live connection)."""
        with self._lock:
            if client_id in self._clients:
                return False
            self._clients[client_id] = None
            return True

    def count(self) -> int:
        with self._lock:
            return len(self._clients)

    def connected_count(self) -> int:
        with self._lock:
            return sum(1 for conn in self._clients.values() if conn is not None)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return dict(self._clients)


class ChannelRegistry:
    """Thread-safe registry mapping channel names to subscriber client IDs."""

    def __init__(self):
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> bool:
        with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return False
            removed = client_id in subscribers
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]
            return removed

    def remove_client(self, client_id: str) -> list[str]:
        """Drop a client from every channel; return the channels involved."""
        with self._lock:
            removed: list[str] = []
            for channel in list(self._channels):
                if client_id in self._channels[channel]:
                    removed.append(channel)
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]
            return removed

    def subscribers(self, channel: str) -> set[str]:
        with self._lock:
            return set(self._channels.get(channel, ()))

    def count(self, channel: str) -> int:
        with self._lock:
            return len(self._channels.get(channel, ()))

    def has(self, channel: str) -> bool:
        with self._lock:
            return bool(self._channels.get(channel))

    def snapshot(self) -> dict[str, set[str]]:
        with self._lock:
            return {name: set(subs) for name, subs in self._channels.items()}


class BaseTransport(ABC):
    """Abstract transport layer for the notification server.

    A transport owns the low-level, network-specific behaviour: accepting
    connections, managing their lifecycle, and writing outbound messages
    to the connected clients. The core :class:`NotificationServer`
    implements all routing, channel and persistence logic on top of a
    transport, so new mechanisms (SSE, polling, raw TCP) can be added by
    implementing this interface without touching the core.

    Concrete transports must implement :meth:`send_message` and
    :meth:`broadcast`. The shared connect/disconnect lifecycle in
    :meth:`on_connect` / :meth:`on_disconnect` may be overridden as
    needed. Lifecycle hooks (:meth:`start`, :meth:`close`) and the
    listening :attr:`port` are provided by each transport.
    """

    def __init__(self, server):
        self.server = server
        self._conn_to_client: dict = {}

    async def start(self) -> None:
        """Start listening for incoming connections."""
        raise NotImplementedError

    async def close(self) -> None:
        """Stop listening and release all resources."""
        raise NotImplementedError

    @property
    def port(self) -> int:
        """The port the transport is actually listening on."""
        raise NotImplementedError

    async def on_connect(self, connection) -> str:
        """Register a freshly accepted connection.

        Assigns a unique client id, mirrors the connection state and
        sends the system "connected" welcome message. Returns the id.
        """
        client_id = self.server.registry.register(connection)
        self._conn_to_client[connection] = client_id
        self.server.event_log.append("connected", {"client_id": client_id})
        await self.server._redis_add_client(client_id)
        await self.send_message(connection, json.dumps(build_message(
            SYSTEM,
            {"event": "connected", "client_id": client_id},
        )))
        return client_id

    async def on_disconnect(self, connection) -> None:
        """Clean up a connection that has gone away."""
        client_id = self._conn_to_client.pop(connection, None)
        if client_id is None:
            return
        self.server.registry.unregister(client_id)
        channels = self.server.channels.remove_client(client_id)
        await self.server._redis_remove_client(client_id, channels=channels)
        self.server.event_log.append("disconnected", {"client_id": client_id})

    @abstractmethod
    async def send_message(self, connection, raw: str) -> bool:
        """Send one raw JSON message to a single connection.

        Returns True on success, False if the connection is no longer
        usable.
        """
        raise NotImplementedError

    @abstractmethod
    async def broadcast(self, connections, raw: str) -> int:
        """Send a raw JSON message to many connections.

        Returns the number of connections the message was successfully
        sent to.
        """
        raise NotImplementedError


class WebSocketTransport(BaseTransport):
    """WebSocket transport built on the `websockets` library.

    Accepts WebSocket connections from clients, reads inbound JSON
    messages and hands them to the server for dispatch, and sends
    outbound messages as JSON text frames.
    """

    def __init__(self, server):
        super().__init__(server)
        self._server = None

    async def start(self) -> None:
        self._server = await serve(
            self.handle_connection,
            self.server.host,
            self.server.requested_port,
            process_request=self.server.process_request,
        )

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    @property
    def port(self) -> int:
        if self._server is not None and self._server.sockets:
            return self._server.sockets[0].getsockname()[1]
        return self.server.requested_port

    async def handle_connection(self, connection) -> None:
        client_id = await self.on_connect(connection)
        try:
            async for raw in connection:
                try:
                    message = json.loads(raw)
                except (TypeError, ValueError):
                    self.server.event_log.append(
                        "invalid_message", {"client_id": client_id}
                    )
                    continue
                if not isinstance(message, dict):
                    continue
                await self.server._dispatch(client_id, message)
        except ConnectionClosed:
            pass
        finally:
            await self.on_disconnect(connection)

    async def send_message(self, connection, raw: str) -> bool:
        try:
            await connection.send(raw)
            return True
        except ConnectionClosed:
            return False

    async def broadcast(self, connections, raw: str) -> int:
        sent = 0
        for connection in list(connections):
            if await self.send_message(connection, raw):
                sent += 1
        return sent


def create_transport(name: str | None, server) -> BaseTransport:
    """Build the transport named by ``name``.

    Falls back to the TRANSPORT env var, then to the default
    (WebSocket). Raises ValueError for unknown transport names.
    """
    resolved = (
        name or os.environ.get(TRANSPORT_ENV_VAR) or DEFAULT_TRANSPORT
    ).strip().lower()
    if resolved in ("websocket", "ws"):
        return WebSocketTransport(server)
    raise ValueError(f"Unknown transport: {resolved!r}")


class NotificationServer:
    """Async WebSocket notification server with optional Redis/SQLite."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765,
                 log_path: str | Path | None = None,
                 redis_url: str | None = None,
                 database_url: str | Path | None = None,
                 redis_client=None,
                 transport: str | BaseTransport | None = None):
        self.host = host
        self.requested_port = port
        self.registry = ClientRegistry()
        self.channels = ChannelRegistry()
        self.event_log = EventLog(log_path)
        self.server_id = uuid.uuid4().hex
        self._pubsub = None
        self._subscriber_task = None

        self.transport = self._build_transport(transport)

        redis_url = redis_url or os.environ.get("REDIS_URL") or None
        database_url = database_url or os.environ.get("DATABASE_URL") or None

        self._redis_injected = redis_client is not None
        self.redis_url = redis_url
        if redis_client is None and redis_url:
            redis_client = self._create_redis_client(redis_url)
        self.redis_client = redis_client
        self.backbone = None
        if self.redis_client is not None:
            self.backbone = RedisBackbone(self.redis_client)

        self.message_store = MessageStore(database_url)

    # -- helpers ------------------------------------------------------

    def _build_transport(self, transport: str | BaseTransport | None
                         ) -> BaseTransport:
        if isinstance(transport, BaseTransport):
            return transport
        return create_transport(transport, self)

    @staticmethod
    def _create_redis_client(redis_url: str):
        try:
            from redis.asyncio import Redis
            return Redis.from_url(redis_url, decode_responses=True)
        except Exception:
            logger.warning("redis client unavailable; disabling backbone")
            return None

    @property
    def backbone_channel(self) -> str:
        if self.backbone is not None:
            return self.backbone.channel
        return REDIS_BACKBONE_CHANNEL

    # -- lifecycle -----------------------------------------------------

    async def start(self) -> "NotificationServer":
        await self.transport.start()
        await self._setup_backbone()
        return self

    async def _setup_backbone(self) -> None:
        if self.redis_client is None:
            return
        if not self._redis_injected:
            try:
                await self.redis_client.ping()
            except Exception:
                logger.warning(
                    "Redis backbone unavailable at %s; using local delivery",
                    self.redis_url,
                )
                self.redis_client = None
                self.backbone = None
                return
        self._subscriber_task = asyncio.create_task(self._subscriber_loop())

    async def close(self) -> None:
        if self._subscriber_task is not None:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
            self._subscriber_task = None
        if self._pubsub is not None:
            try:
                await self._pubsub.aclose()
            except Exception:
                pass
            self._pubsub = None
        if self.transport is not None:
            await self.transport.close()

    @property
    def port(self) -> int:
        return self.transport.port

    # -- HTTP ----------------------------------------------------------

    def process_request(self, connection, request):
        """Serve REST endpoints over plain HTTP."""
        path = request.path.split("?", 1)[0]
        if path == HEALTH_PATH:
            return self._http_json({
                "status": "ok",
                "connected_clients": self.registry.connected_count(),
            })
        if path == CHANNELS_PATH:
            channels = [
                {"name": name, "subscribers": len(subscribers)}
                for name, subscribers in sorted(self.channels.snapshot().items())
            ]
            return self._http_json({
                "channels": channels,
                "count": len(channels),
            })
        if path.startswith(CHANNELS_PATH + "/"):
            name = path[len(CHANNELS_PATH) + 1:].split("/", 1)[0]
            return self._http_json({
                "channel": name,
                "subscribers": sorted(self.channels.subscribers(name)),
            })
        if path == MESSAGES_PATH:
            query = request.path.split("?", 1)[1] if "?" in request.path else ""
            params = urllib.parse.parse_qs(query)
            limit = _parse_int((params.get("limit") or ["50"])[0], 50)
            offset = _parse_int((params.get("offset") or ["0"])[0], 0)
            return self._http_json({
                "messages": self.message_store.list(limit=limit, offset=offset),
                "count": self.message_store.count(),
                "limit": limit,
                "offset": offset,
            })
        return None

    @staticmethod
    def _http_json(data: dict) -> Response:
        body = json.dumps(data).encode("utf-8")
        return Response(
            status_code=200,
            reason_phrase="OK",
            headers=Headers([("Content-Type", "application/json")]),
            body=body,
        )

    # -- connections ------------------------------------------------------

    async def handle_connection(self, connection) -> None:
        """Backwards-compatible entry point delegating to the transport."""
        await self.transport.handle_connection(connection)

    async def _dispatch(self, client_id: str, message: dict) -> None:
        msg_type = message.get("type")
        payload = message.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        if msg_type == SUBSCRIBE:
            channels = extract_channels(message)
            for channel in channels:
                self.channels.subscribe(client_id, channel)
                await self._redis_add_channel(client_id, channel)
            self.event_log.append("subscribe", {
                "client_id": client_id,
                "channels": channels,
            })
        elif msg_type == UNSUBSCRIBE:
            channels = extract_channels(message)
            for channel in channels:
                self.channels.unsubscribe(client_id, channel)
                await self._redis_remove_channel(client_id, channel)
            self.event_log.append("unsubscribe", {
                "client_id": client_id,
                "channels": channels,
            })
        elif msg_type == BROADCAST:
            data = dict(payload)
            data.setdefault("sender", client_id)
            channel = message_channel(message, payload)
            if channel is not None:
                await self.send_to_channel(channel, data)
            else:
                await self.broadcast(data)
        elif msg_type == DIRECT:
            target = payload.get("target")
            await self.send_direct(target, payload)
        elif msg_type == SYSTEM:
            self.event_log.append("system", {
                "client_id": client_id,
                "payload": payload,
            })
        else:
            self.event_log.append("unknown_type", {
                "client_id": client_id,
                "type": str(msg_type),
            })

    async def broadcast(self, payload: dict) -> int:
        """Send a broadcast message to every connected client."""
        message = build_message(BROADCAST, payload)
        self.message_store.store(
            BROADCAST, None, message["payload"], message["timestamp"]
        )
        if self.backbone is not None:
            await self.backbone.publish({
                "type": BROADCAST,
                "channel": None,
                "message": message,
            })
            return self.registry.connected_count()
        return await self._send_to_local_all(json.dumps(message))

    async def send_direct(self, target_id: str, payload: dict) -> bool:
        """Send a direct message to a single client."""
        message = build_message(DIRECT, payload)
        self.message_store.store(
            DIRECT, None, message["payload"], message["timestamp"]
        )
        if self.backbone is not None:
            await self.backbone.publish({
                "type": DIRECT,
                "channel": None,
                "target": target_id,
                "message": message,
            })
            if self.registry.get(target_id) is not None:
                return True
            return target_id in await self._redis_connected_ids()
        conn = self.registry.get(target_id)
        if conn is None:
            self.event_log.append("direct_undelivered", {
                "target": target_id,
            })
            return False
        return await self._send_raw(target_id, conn, json.dumps(message))

    # -- channels -----------------------------------------------------

    def subscribe_client(self, client_id: str, channel: str) -> None:
        """Subscribe a client to a single channel."""
        self.channels.subscribe(client_id, channel)

    def unsubscribe_client(self, client_id: str, channel: str) -> bool:
        """Unsubscribe a client from a single channel."""
        return self.channels.unsubscribe(client_id, channel)

    def channel_subscribers(self, channel: str) -> set[str]:
        """Return the set of client IDs subscribed to a channel."""
        return self.channels.subscribers(channel)

    def channel_snapshot(self) -> dict[str, set[str]]:
        """Return a copy of the channel -> subscriber mapping."""
        return self.channels.snapshot()

    async def send_to_channel(self, channel: str, payload: dict) -> int:
        """Send a message only to the clients subscribed to a channel."""
        message = build_message(BROADCAST, payload)
        self.message_store.store(
            BROADCAST, channel, message["payload"], message["timestamp"]
        )
        if self.backbone is not None:
            await self.backbone.publish({
                "type": BROADCAST,
                "channel": channel,
                "message": message,
            })
            return len(self.channels.subscribers(channel))
        return await self._send_to_local_channel(channel, json.dumps(message))

    # -- delivery helpers ------------------------------------------------

    async def _send_raw(self, client_id: str, conn, raw: str) -> bool:
        if conn is None:
            return False
        ok = await self.transport.send_message(conn, raw)
        if not ok:
            self.registry.unregister(client_id)
            self.channels.remove_client(client_id)
            return False
        return True

    async def _send_to_local_all(self, raw: str) -> int:
        connections = [
            conn for conn in self.registry.snapshot().values()
            if conn is not None
        ]
        return await self.transport.broadcast(connections, raw)

    async def _send_to_local_channel(self, channel: str, raw: str) -> int:
        sent = 0
        connections = []
        for client_id in list(self.channels.subscribers(channel)):
            conn = self.registry.get(client_id)
            if conn is None:
                self.channels.unsubscribe(client_id, channel)
                continue
            connections.append(conn)
        return await self.transport.broadcast(connections, raw)

    # -- redis backbone delivery ------------------------------------------

    async def _subscriber_loop(self) -> None:
        pubsub = self.redis_client.pubsub()
        self._pubsub = pubsub
        try:
            await pubsub.subscribe(self.backbone.channel)
            async for raw in pubsub.listen():
                if not isinstance(raw, dict) or raw.get("type") != "message":
                    continue
                data = raw.get("data")
                if isinstance(data, (bytes, bytearray)):
                    data = bytes(data).decode("utf-8")
                try:
                    envelope = json.loads(data)
                except (TypeError, ValueError):
                    continue
                if not isinstance(envelope, dict):
                    continue
                try:
                    await self._deliver(envelope)
                except ConnectionClosed:
                    pass
                except Exception:
                    logger.exception("redis delivery failed")
        finally:
            try:
                await pubsub.unsubscribe(self.backbone.channel)
            except Exception:
                pass
            try:
                await pubsub.aclose()
            except Exception:
                pass
            self._pubsub = None

    async def _deliver(self, envelope: dict) -> None:
        msg_type = envelope.get("type")
        channel = envelope.get("channel")
        message = envelope.get("message")
        if not isinstance(message, dict):
            return
        raw = json.dumps(message)
        if msg_type == BROADCAST:
            if channel:
                await self._send_to_local_channel(channel, raw)
            else:
                await self._send_to_local_all(raw)
        elif msg_type == DIRECT:
            target = envelope.get("target")
            if target is None:
                return
            conn = self.registry.get(target)
            if conn is not None:
                await self._send_raw(target, conn, raw)

    # -- redis state mirroring -------------------------------------------

    async def _redis_connected_ids(self) -> set[str]:
        if self.redis_client is None:
            return set()
        members = await self.redis_client.smembers(REDIS_CLIENTS_KEY)
        return {_decode(m) for m in members}

    async def _redis_add_client(self, client_id: str) -> None:
        if self.redis_client is None:
            return
        try:
            await self.redis_client.sadd(REDIS_CLIENTS_KEY, client_id)
            await self.redis_client.hset(
                REDIS_CLIENT_PREFIX + client_id,
                mapping={
                    "server": self.server_id,
                    "connected_at": utc_now_iso(),
                },
            )
        except Exception:
            logger.exception("failed to store client state in redis")

    async def _redis_remove_client(self, client_id: str,
                                   channels: list[str] = ()) -> None:
        if self.redis_client is None:
            return
        try:
            await self.redis_client.srem(REDIS_CLIENTS_KEY, client_id)
            await self.redis_client.delete(REDIS_CLIENT_PREFIX + client_id)
            for channel in channels:
                await self._redis_remove_channel(client_id, channel)
        except Exception:
            logger.exception("failed to remove client state from redis")

    async def _redis_add_channel(self, client_id: str, channel: str) -> None:
        if self.redis_client is None:
            return
        try:
            await self.redis_client.sadd(REDIS_CHANNEL_PREFIX + channel, client_id)
            await self.redis_client.sadd(REDIS_CHANNEL_INDEX_KEY, channel)
        except Exception:
            logger.exception("failed to store channel state in redis")

    async def _redis_remove_channel(self, client_id: str, channel: str) -> None:
        if self.redis_client is None:
            return
        try:
            await self.redis_client.srem(REDIS_CHANNEL_PREFIX + channel, client_id)
            left = await self.redis_client.scard(REDIS_CHANNEL_PREFIX + channel)
            if left == 0:
                await self.redis_client.delete(REDIS_CHANNEL_PREFIX + channel)
                await self.redis_client.srem(REDIS_CHANNEL_INDEX_KEY, channel)
        except Exception:
            logger.exception("failed to remove channel state from redis")

    async def redis_snapshot(self) -> dict:
        """Return the client/channel state currently mirrored in Redis."""
        if self.redis_client is None:
            return {"clients": [], "channels": {}}
        clients = await self._redis_connected_ids()
        channels: dict[str, list[str]] = {}
        names = await self.redis_client.smembers(REDIS_CHANNEL_INDEX_KEY)
        for name in names:
            channel = _decode(name)
            members = await self.redis_client.smembers(REDIS_CHANNEL_PREFIX + channel)
            channels[channel] = sorted(_decode(m) for m in members)
        return {"clients": sorted(clients), "channels": channels}

    async def restore_state(self) -> int:
        """Restore client/channel state from Redis after a restart."""
        if self.redis_client is None:
            return 0
        snapshot = await self.redis_snapshot()
        restored = 0
        for client_id in snapshot["clients"]:
            if self.registry.restore(client_id):
                restored += 1
        for channel, members in snapshot["channels"].items():
            for client_id in members:
                if client_id not in self.channels.subscribers(channel):
                    self.channels.subscribe(client_id, channel)
                    restored += 1
        return restored


def _parse_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def run_server(host: str = "127.0.0.1", port: int = 8765,
               log_path: str | Path | None = None,
               redis_url: str | None = None,
               database_url: str | Path | None = None) -> None:
    """Blocking entry point: run the server until interrupted."""

    async def _main() -> None:
        server = NotificationServer(
            host=host,
            port=port,
            log_path=log_path,
            redis_url=redis_url,
            database_url=database_url,
        )
        await server.start()
        logger.info("Notification server listening on ws://%s:%s",
                    host, server.port)
        try:
            await asyncio.Future()  # run forever
        finally:
            await server.close()

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_server()
