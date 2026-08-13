"""WebSocket-based notification server with a Redis pub/sub backbone.

A minimal async notification server built on the ``websockets`` library
(not Flask-SocketIO). Each connected client is assigned a unique ID on
connect. Clients may send messages to trigger broadcasts or direct
delivery. Every message is framed as JSON:

    {"type": str, "payload": dict, "timestamp": str}

Supported message types: ``broadcast``, ``direct``, ``system``,
``subscribe``, ``unsubscribe``.

Clients may subscribe to named channels (e.g. ``alerts``, ``system``,
``chat``). A message that carries a ``channel`` field is delivered only to
the clients subscribed to that channel; a message without one is broadcast
to every connected client.

Redis integration
-----------------
The server uses Redis pub/sub as its message backbone:

* A server instance publishes every notification (broadcast, channel or
  direct message) to the shared Redis channel ``ntf:notifications``.
* Every server instance runs a background subscriber task that listens on
  that channel and delivers the message to its locally connected clients.
  Multiple server instances can share the same Redis backbone, so a
  message published by one instance is delivered to clients connected to
  any instance.

The live client registry is mirrored to Redis as well: a set
``ntf:clients`` tracks every connected client id and a per-client set
``ntf:client:{id}:channels`` records that client's channel subscriptions.
This state survives a server restart, and ``ClientRegistry.restore_state``
rebuilds the in-memory channel membership from it.

Persistence
-----------
Every published message is stored in a SQLite ``messages`` table
(``id``, ``channel``, ``type``, ``payload``, ``timestamp``) and is
retrievable through the REST endpoint ``GET /messages?limit=50&offset=0``.

Transport layer
---------------
All wire-protocol concerns live behind the :class:`BaseTransport`
interface. ``WebSocketTransport`` (the default) implements it with the
``websockets`` library. The transport is selected by ``TRANSPORT``; other
mechanisms (SSE, polling, raw TCP) can be added by subclassing
``BaseTransport`` without touching the core notification logic.

Configuration
-------------
* ``REDIS_URL`` - Redis connection URL (default ``redis://localhost:6379/0``)
* ``DATABASE_URL`` - SQLite database path/URL (default ``sqlite:///notifications.db``)
* ``TRANSPORT`` - transport name (default ``websocket``)

REST endpoints
--------------
* ``GET /health`` - number of connected clients
* ``GET /channels`` - active channels with subscriber counts
* ``GET /channels/{name}/subscribers`` - a channel's subscriber IDs
* ``GET /messages?limit=50&offset=0`` - persisted message history

The client registry is shared between the asyncio WebSocket handlers and
a background OS thread running the HTTP health server, so it is guarded
with a ``threading.Lock`` (not ``asyncio.Lock``) to be truly thread-safe.
"""

import asyncio
import http.server
import json
import os
import sqlite3
import threading
import urllib.parse
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import redis
import redis.asyncio as aioredis
import websockets

WS_HOST = "127.0.0.1"
WS_PORT = 8765
HTTP_HOST = "127.0.0.1"
HTTP_PORT = 8080

REDIS_URL_DEFAULT = "redis://localhost:6379/0"
DATABASE_URL_DEFAULT = "sqlite:///notifications.db"
TRANSPORT_DEFAULT = "websocket"

# Redis channel used as the pub/sub message backbone.
NOTIFICATIONS_CHANNEL = "ntf:notifications"
# Redis keys that mirror live client connection state.
CLIENT_SET_KEY = "ntf:clients"
CLIENT_CHANNELS_PREFIX = "ntf:client:"
CLIENT_CHANNELS_SUFFIX = ":channels"

SUPPORTED_TYPES = ("broadcast", "direct", "system", "subscribe", "unsubscribe")


def utcnow_iso() -> str:
    """Current UTC timestamp in ISO 8601 string form."""
    return datetime.now(timezone.utc).isoformat()


def build_message(msg_type: str, payload: dict) -> dict:
    """Build a well-formed notification message."""
    if msg_type not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported message type: {msg_type!r}")
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")
    return {"type": msg_type, "payload": payload, "timestamp": utcnow_iso()}


def resolve_redis_url(explicit=None) -> str:
    """Resolve the Redis broker URL from an explicit value or ``REDIS_URL``."""
    if explicit:
        return explicit
    return os.environ.get("REDIS_URL") or REDIS_URL_DEFAULT


def resolve_db_path(explicit=None) -> str:
    """Resolve the SQLite database path from an explicit value or ``DATABASE_URL``."""
    if explicit:
        value = explicit
    else:
        value = os.environ.get("DATABASE_URL") or DATABASE_URL_DEFAULT
    if value.startswith("sqlite:///"):
        path = value[len("sqlite:///"):]
        if path == ":":
            return ":memory:"
        return path
    if value.startswith("sqlite://"):
        return value[len("sqlite://"):]
    return value


def resolve_transport(explicit=None) -> str:
    """Resolve the transport name from an explicit value or ``TRANSPORT``."""
    if explicit:
        return explicit
    return os.environ.get("TRANSPORT") or TRANSPORT_DEFAULT


def _channels_key(client_id: str) -> str:
    return f"{CLIENT_CHANNELS_PREFIX}{client_id}{CLIENT_CHANNELS_SUFFIX}"


def _decode(value) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


class MessageStore:
    """SQLite-backed history of every published message.

    The store is shared between the asyncio event loop (message publishing)
    and the background HTTP handler thread (``GET /messages``), so it is
    guarded with a ``threading.Lock`` and a single connection that is
    explicitly marked safe for use from other threads.
    """

    def __init__(self, path: str = None) -> None:
        self._path = path if path is not None else resolve_db_path()
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT,
                    type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
                """
            )
            self._conn.commit()

    def record(self, message: dict, channel=None) -> int:
        """Persist ``message`` and return its row id."""
        payload = message.get("payload")
        if isinstance(payload, (dict, list, tuple)):
            payload = json.dumps(payload)
        else:
            payload = str(payload) if payload is not None else ""
        msg_type = message.get("type") or ""
        timestamp = message.get("timestamp") or utcnow_iso()
        if channel is None:
            channel = message.get("channel")
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (channel, msg_type, payload, timestamp),
            )
            self._conn.commit()
            return cur.lastrowid

    def list_messages(self, limit: int = 50, offset: int = 0) -> list:
        """Return persisted messages (newest first) within ``limit``/``offset``."""
        try:
            limit = max(1, int(limit))
        except (TypeError, ValueError):
            limit = 50
        try:
            offset = max(0, int(offset))
        except (TypeError, ValueError):
            offset = 0
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        messages = []
        for row in rows:
            payload = row["payload"]
            try:
                payload = json.loads(payload)
            except (json.JSONDecodeError, TypeError):
                pass
            messages.append(
                {
                    "id": row["id"],
                    "channel": row["channel"],
                    "type": row["type"],
                    "payload": payload,
                    "timestamp": row["timestamp"],
                }
            )
        return messages

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass


class ClientStateStore:
    """Redis-backed mirror of live client connection state.

    Keeps a set of every connected client id (``ntf:clients``) and, per
    client, a set of channel subscriptions (``ntf:client:{id}:channels``)
    so the state survives a server restart. All operations are best-effort:
    if Redis is unavailable the store degrades to a no-op.
    """

    def __init__(self, redis_url: str = None) -> None:
        self._url = resolve_redis_url(redis_url)
        self._client = None
        self.available = False

    def connect(self) -> None:
        try:
            client = redis.Redis.from_url(
                self._url, socket_connect_timeout=2, socket_timeout=2
            )
            client.ping()
            self._client = client
            self.available = True
        except Exception:
            self.available = False
            self._client = None

    def add(self, client_id: str) -> None:
        if not self.available:
            return
        try:
            self._client.sadd(CLIENT_SET_KEY, client_id)
            self._client.delete(_channels_key(client_id))
        except Exception:
            pass

    def remove(self, client_id: str) -> None:
        if not self.available:
            return
        try:
            self._client.srem(CLIENT_SET_KEY, client_id)
            self._client.delete(_channels_key(client_id))
        except Exception:
            pass

    def subscribe(self, client_id: str, channel: str) -> None:
        if not self.available:
            return
        try:
            self._client.sadd(_channels_key(client_id), channel)
        except Exception:
            pass

    def unsubscribe(self, client_id: str, channel: str) -> None:
        if not self.available:
            return
        try:
            self._client.srem(_channels_key(client_id), channel)
        except Exception:
            pass

    def has_client(self, client_id: str):
        """Return True/False if known, or ``None`` when Redis is unavailable."""
        if not self.available:
            return None
        try:
            return bool(self._client.sismember(CLIENT_SET_KEY, client_id))
        except Exception:
            return None

    def client_channels(self, client_id: str) -> set:
        if not self.available:
            return set()
        try:
            return {_decode(c) for c in self._client.smembers(_channels_key(client_id))}
        except Exception:
            return set()

    def live_client_ids(self) -> set:
        if not self.available:
            return set()
        try:
            return {_decode(c) for c in self._client.smembers(CLIENT_SET_KEY)}
        except Exception:
            return set()

    def clear(self) -> None:
        """Remove all client-state keys (used to reset between tests)."""
        if not self.available:
            return
        try:
            self._client.delete(CLIENT_SET_KEY)
            for key in self._client.scan_iter(match=f"{CLIENT_CHANNELS_PREFIX}*"):
                self._client.delete(key)
        except Exception:
            pass


class ClientRegistry:
    """Thread-safe registry of connected WebSocket clients.

    asyncio runs each coroutine on its own OS thread by default, so the
    registry is guarded with a ``threading.Lock`` (not ``asyncio.Lock``)
    to be truly thread-safe across threads. The lock also protects the
    registry from the background HTTP health-server thread.

    When a ``state_store`` (a Redis-backed :class:`ClientStateStore`) is
    provided, every membership change is mirrored to Redis so the state
    survives a server restart.
    """

    def __init__(self, state_store: ClientStateStore = None) -> None:
        self._clients: dict[str, object] = {}
        self._channels: dict[str, set[str]] = {}
        self._client_channels: dict[str, set[str]] = {}
        self._lock = threading.Lock()
        self._state = state_store
        self._transport = None

    @property
    def state_store(self):
        return self._state

    def set_transport(self, transport) -> None:
        """Attach the :class:`BaseTransport` used for outbound delivery."""
        self._transport = transport

    def add(self, ws: object) -> str:
        """Register a connection and return its unique client id."""
        client_id = uuid.uuid4().hex
        with self._lock:
            self._clients[client_id] = ws
        if self._state is not None:
            self._state.add(client_id)
        return client_id

    def remove(self, client_id: str) -> None:
        """Remove a client id if present (idempotent)."""
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in self._client_channels.pop(client_id, ()):
                subscribers = self._channels.get(channel)
                if subscribers:
                    subscribers.discard(client_id)
                    if not subscribers:
                        del self._channels[channel]
        if self._state is not None:
            self._state.remove(client_id)

    def get(self, client_id: str):
        """Return the connection for a client id, or ``None``."""
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> dict:
        """Return a copy of the current client map."""
        with self._lock:
            return dict(self._clients)

    @property
    def count(self) -> int:
        """Number of connected clients."""
        with self._lock:
            return len(self._clients)

    def subscribe(self, client_id: str, channel: str) -> bool:
        """Subscribe ``client_id`` to ``channel``.

        Returns ``True`` if the client exists and is now subscribed.
        Subscribing twice to the same channel is idempotent.
        """
        if self.get(client_id) is None:
            return False
        with self._lock:
            self._client_channels.setdefault(client_id, set()).add(channel)
            self._channels.setdefault(channel, set()).add(client_id)
        if self._state is not None:
            self._state.subscribe(client_id, channel)
        return True

    def unsubscribe(self, client_id: str, channel: str) -> bool:
        """Unsubscribe ``client_id`` from ``channel``.

        Returns ``True`` if the client was subscribed, ``False`` otherwise.
        """
        with self._lock:
            subscribed = self._client_channels.get(client_id)
            if not subscribed or channel not in subscribed:
                return False
            subscribed.discard(channel)
            subscribers = self._channels.get(channel)
            if subscribers:
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[channel]
        if self._state is not None:
            self._state.unsubscribe(client_id, channel)
        return True

    def channels(self) -> dict:
        """Return a snapshot of ``{channel: {client_id, ...}}`` for active channels."""
        with self._lock:
            return {channel: set(ids) for channel, ids in self._channels.items() if ids}

    def channel_subscribers(self, channel: str) -> set:
        """Return a snapshot of the subscriber ids for ``channel`` (possibly empty)."""
        with self._lock:
            subscribers = self._channels.get(channel)
            return set(subscribers) if subscribers else set()

    def client_exists(self, client_id: str):
        """Whether ``client_id`` is live locally or on a peer server.

        Returns ``True``/``False`` when determinable and ``None`` when the
        shared Redis state is unavailable (caller should fall back to a
        local delivery attempt).
        """
        if self.get(client_id) is not None:
            return True
        if self._state is not None:
            known = self._state.has_client(client_id)
            if known is not None:
                return bool(known)
        return None

    def restore_state(self) -> None:
        """Rebuild channel membership from the persisted Redis state.

        Restores only channel membership (the live WebSocket objects cannot
        survive a restart); reconnecting clients re-attach to the registry.
        """
        if self._state is None:
            return
        live = self._state.live_client_ids()
        with self._lock:
            for client_id in live:
                for channel in self._state.client_channels(client_id):
                    self._client_channels.setdefault(client_id, set()).add(channel)
                    self._channels.setdefault(channel, set()).add(client_id)

    async def broadcast_to_channel(self, channel: str, message: dict) -> int:
        """Send ``message`` to every client subscribed to ``channel``.

        Returns the number of clients that successfully received it.
        Failing connections are removed cleanly.
        """
        if self._transport is not None:
            return await self._transport.broadcast_to_channel(channel, message)
        sent = 0
        dead = []
        for client_id in self.channel_subscribers(channel):
            ws = self.get(client_id)
            if ws is None:
                dead.append(client_id)
                continue
            try:
                await ws.send(json.dumps(message))
                sent += 1
            except Exception:
                dead.append(client_id)
        for client_id in dead:
            self.remove(client_id)
        return sent

    async def broadcast(self, message: dict) -> int:
        """Send ``message`` to every connected client.

        Returns the number of clients that successfully received it.
        Failing connections are removed cleanly.
        """
        if self._transport is not None:
            return await self._transport.broadcast(message)
        sent = 0
        dead = []
        for client_id, ws in self.snapshot().items():
            try:
                await ws.send(json.dumps(message))
                sent += 1
            except Exception:
                dead.append(client_id)
        for client_id in dead:
            self.remove(client_id)
        return sent

    async def send_to(self, client_id: str, message: dict) -> bool:
        """Send ``message`` to one client. ``False`` if unknown/dead."""
        if self._transport is not None:
            return await self._transport.send_message(client_id, message)
        ws = self.get(client_id)
        if ws is None:
            return False
        try:
            await ws.send(json.dumps(message))
            return True
        except Exception:
            self.remove(client_id)
            return False


class RedisBroker:
    """Redis pub/sub message backbone.

    ``publish`` persists the message to SQLite and publishes it to the
    shared ``ntf:notifications`` Redis channel; every server instance's
    subscriber task (``subscribe_loop``) then delivers it to its local
    clients. When Redis is unreachable the broker degrades to direct
    in-process delivery, preserving the original single-server behaviour.
    """

    def __init__(self, redis_url: str = None, store: MessageStore = None,
                 registry: ClientRegistry = None) -> None:
        self._url = resolve_redis_url(redis_url)
        self._store = store
        self._registry = registry
        self._pub = None
        self._sub = None
        self.available = False
        self._stopped = False

    async def connect(self) -> None:
        try:
            pub = aioredis.from_url(self._url, socket_connect_timeout=2)
            await pub.ping()
            self._pub = pub
            self._sub = pub.pubsub()
            await self._sub.subscribe(NOTIFICATIONS_CHANNEL)
            self.available = True
        except Exception:
            self.available = False
            self._pub = None
            self._sub = None

    def stop(self) -> None:
        self._stopped = True

    async def close(self) -> None:
        self._stopped = True
        try:
            if self._sub is not None:
                await self._sub.unsubscribe(NOTIFICATIONS_CHANNEL)
                await self._sub.close()
        except Exception:
            pass
        try:
            if self._pub is not None:
                await self._pub.close()
        except Exception:
            pass

    async def publish(self, message: dict) -> None:
        """Persist and distribute ``message`` through the backbone."""
        if self._store is not None:
            try:
                self._store.record(message)
            except Exception:
                pass
        if self.available and self._pub is not None:
            # Only the pub/sub path is used when Redis is connected. We never
            # fall back to local delivery here: a publish error may still have
            # reached Redis, and re-delivering locally would duplicate messages.
            try:
                await self._pub.publish(NOTIFICATIONS_CHANNEL, json.dumps(message))
            except Exception:
                pass
            return
        await self._deliver(message)

    async def _deliver(self, message: dict) -> None:
        """Deliver ``message`` to the locally connected clients."""
        if self._registry is None:
            return
        if message.get("type") == "direct":
            target = (message.get("payload") or {}).get("to")
            if target:
                await self._registry.send_to(target, message)
        elif message.get("channel"):
            await self._registry.broadcast_to_channel(message["channel"], message)
        else:
            await self._registry.broadcast(message)

    async def subscribe_loop(self) -> None:
        """Continuously deliver backbone messages to local clients."""
        while not self._stopped:
            try:
                async for raw in self._sub.listen():
                    if self._stopped:
                        break
                    if raw.get("type") != "message":
                        continue
                    try:
                        message = json.loads(_decode(raw.get("data")))
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if self._registry is not None:
                        await self._deliver(message)
            except asyncio.CancelledError:
                break
            except (ConnectionError, OSError, asyncio.TimeoutError):
                if self._stopped:
                    break
                try:
                    await asyncio.sleep(0.5)
                    await self._sub.subscribe(NOTIFICATIONS_CHANNEL)
                except Exception:
                    await asyncio.sleep(0.5)


class BaseTransport(ABC):
    """Pluggable transport layer for the notification server.

    A transport owns the wire protocol: how connections are accepted, how
    individual messages are read from and written to a connection, and how
    broadcasts fan out to connected clients. The core notification logic
    (message framing, channel routing, direct delivery) only talks to this
    interface, so new mechanisms (SSE, polling, raw TCP) can be added
    without touching the server core.
    """

    def __init__(self, registry: ClientRegistry = None) -> None:
        self._registry = registry

    @property
    def registry(self) -> ClientRegistry:
        return self._registry

    @registry.setter
    def registry(self, registry: ClientRegistry) -> None:
        self._registry = registry

    @abstractmethod
    def on_connect(self, connection) -> str:
        """Register a newly connected client and return its client id."""
        raise NotImplementedError

    @abstractmethod
    def on_disconnect(self, client_id: str) -> None:
        """Unregister a disconnected client."""
        raise NotImplementedError

    @abstractmethod
    async def send_message(self, client_id: str, message: dict) -> bool:
        """Deliver ``message`` to a single client.

        Returns ``False`` (and deregisters the client) when the connection
        is gone.
        """
        raise NotImplementedError

    @abstractmethod
    async def broadcast(self, message: dict) -> int:
        """Deliver ``message`` to every connected client.

        Returns the number of clients that successfully received it.
        """
        raise NotImplementedError

    @abstractmethod
    async def receive(self, connection):
        """Return the next raw message from ``connection``, or ``None`` on close."""
        raise NotImplementedError

    @abstractmethod
    async def serve(self, host: str, port: int, handler) -> object:
        """Start listening for client connections.

        ``handler`` is called with each accepted connection.
        Returns the listening server object.
        """
        raise NotImplementedError

    @abstractmethod
    async def close(self, server) -> None:
        """Stop and close a listening server."""
        raise NotImplementedError

    async def broadcast_to_channel(self, channel: str, message: dict) -> int:
        """Deliver ``message`` to every client subscribed to ``channel``."""
        sent = 0
        if self._registry is None:
            return sent
        for client_id in self._registry.channel_subscribers(channel):
            if await self.send_message(client_id, message):
                sent += 1
        return sent


class WebSocketTransport(BaseTransport):
    """Default transport built on the ``websockets`` library."""

    def on_connect(self, connection) -> str:
        if self._registry is None:
            raise RuntimeError("WebSocketTransport has no registry")
        return self._registry.add(connection)

    def on_disconnect(self, client_id: str) -> None:
        if self._registry is not None:
            self._registry.remove(client_id)

    async def send_message(self, client_id: str, message: dict) -> bool:
        if self._registry is None:
            return False
        connection = self._registry.get(client_id)
        if connection is None:
            return False
        try:
            await connection.send(json.dumps(message))
            return True
        except Exception:
            self._registry.remove(client_id)
            return False

    async def broadcast(self, message: dict) -> int:
        sent = 0
        dead = []
        if self._registry is not None:
            for client_id, connection in self._registry.snapshot().items():
                try:
                    await connection.send(json.dumps(message))
                    sent += 1
                except Exception:
                    dead.append(client_id)
            for client_id in dead:
                self._registry.remove(client_id)
        return sent

    async def receive(self, connection):
        try:
            return await connection.recv()
        except websockets.exceptions.ConnectionClosed:
            return None

    async def serve(self, host: str, port: int, handler) -> object:
        return await websockets.serve(
            lambda connection: handler(connection), host, port
        )

    async def close(self, server) -> None:
        server.close()
        await server.wait_closed()


def get_transport(name=None, registry: ClientRegistry = None) -> BaseTransport:
    """Build a transport instance selected by ``name`` or ``TRANSPORT``."""
    resolved = resolve_transport(name).strip().lower()
    if resolved in ("websocket", "ws"):
        return WebSocketTransport(registry=registry)
    raise ValueError(f"unknown transport: {resolved!r}")


async def ws_handler(connection, transport: BaseTransport, broker: RedisBroker = None) -> None:
    """Handle a single client connection lifecycle.

    Protocol handling is transport-agnostic: the transport owns how
    messages are read from and written to ``connection``.
    """
    registry = transport.registry
    client_id = transport.on_connect(connection)
    try:
        welcome = build_message(
            "system", {"event": "connected", "client_id": client_id}
        )
        await transport.send_message(client_id, welcome)
        while True:
            raw = await transport.receive(connection)
            if raw is None:
                break
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                await transport.send_message(
                    client_id, build_message("system", {"error": "invalid JSON"})
                )
                continue
            if not isinstance(data, dict):
                await transport.send_message(
                    client_id,
                    build_message("system", {"error": "message must be a JSON object"}),
                )
                continue
            msg_type = data.get("type")
            payload = data.get("payload") or {}
            channel = None
            if isinstance(payload, dict):
                channel = payload.get("channel") or data.get("channel")
            else:
                channel = data.get("channel")
            if not isinstance(channel, str):
                channel = None
            if msg_type == "broadcast":
                message = build_message("broadcast", payload)
                if channel:
                    message = dict(message, channel=channel)
                if broker is not None:
                    await broker.publish(message)
                elif channel:
                    await registry.broadcast_to_channel(channel, message)
                else:
                    await registry.broadcast(message)
            elif msg_type == "subscribe":
                if not channel:
                    await transport.send_message(
                        client_id,
                        build_message(
                            "system",
                            {"error": "subscribe message requires a channel"},
                        ),
                    )
                    continue
                registry.subscribe(client_id, channel)
                await transport.send_message(
                    client_id,
                    build_message(
                        "system", {"event": "subscribed", "channel": channel}
                    ),
                )
            elif msg_type == "unsubscribe":
                if not channel:
                    await transport.send_message(
                        client_id,
                        build_message(
                            "system",
                            {"error": "unsubscribe message requires a channel"},
                        ),
                    )
                    continue
                registry.unsubscribe(client_id, channel)
                await transport.send_message(
                    client_id,
                    build_message(
                        "system", {"event": "unsubscribed", "channel": channel}
                    ),
                )
            elif msg_type == "direct":
                target = payload.get("to")
                if not target:
                    await transport.send_message(
                        client_id,
                        build_message(
                            "system",
                            {"error": "direct message missing payload.to"},
                        ),
                    )
                    continue
                message = build_message("direct", payload)
                if broker is not None and broker.available:
                    known = registry.client_exists(target)
                    if known is False:
                        await transport.send_message(
                            client_id,
                            build_message(
                                "system", {"error": f"no client with id {target}"}
                            ),
                        )
                        continue
                    await broker.publish(message)
                else:
                    if not await registry.send_to(target, message):
                        await transport.send_message(
                            client_id,
                            build_message(
                                "system", {"error": f"no client with id {target}"}
                            ),
                        )
            elif msg_type == "system":
                await transport.send_message(
                    client_id, build_message("system", {"echo": payload})
                )
            else:
                await transport.send_message(
                    client_id,
                    build_message(
                        "system",
                        {"error": f"unsupported message type: {msg_type!r}"},
                    ),
                )
    finally:
        transport.on_disconnect(client_id)


class HealthHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler exposing the connected client count at ``/health``."""

    registry = None
    store = None

    def do_GET(self):
        split = urllib.parse.urlsplit(self.path)
        path = split.path.rstrip("/") or "/"
        if path == "/health":
            body = json.dumps({"status": "ok", "clients": self.registry.count})
            self.send_json(200, body)
        elif path == "/channels":
            channels = self.registry.channels()
            payload = {
                "channels": [
                    {"name": name, "subscribers": len(subscribers)}
                    for name, subscribers in sorted(channels.items())
                ]
            }
            self.send_json(200, json.dumps(payload))
        elif path.startswith("/channels/"):
            name = path[len("/channels/"):]
            if name.endswith("/subscribers"):
                name = name[: -len("/subscribers")]
            subscribers = sorted(self.registry.channel_subscribers(name))
            self.send_json(
                200,
                json.dumps({"channel": name, "subscribers": subscribers}),
            )
        elif path == "/messages":
            query = urllib.parse.parse_qs(split.query)
            try:
                limit = int(query.get("limit", ["50"])[0])
            except (ValueError, IndexError):
                limit = 50
            try:
                offset = int(query.get("offset", ["0"])[0])
            except (ValueError, IndexError):
                offset = 0
            messages = self.store.list_messages(limit=limit, offset=offset)
            self.send_json(
                200, json.dumps({"messages": messages, "limit": limit, "offset": offset})
            )
        else:
            self.send_response(404)
            self.end_headers()

    def send_json(self, status: int, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *args):
        pass


def start_health_server(registry, store=None, host: str = HTTP_HOST, port: int = HTTP_PORT):
    """Start the ``/health`` HTTP server on a background OS thread."""
    handler = type(
        "BoundHealthHandler", (HealthHandler,), {"registry": registry, "store": store}
    )
    httpd = http.server.ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


async def make_server(
    ws_host: str = WS_HOST,
    ws_port: int = 0,
    http_host: str = HTTP_HOST,
    http_port: int = 0,
    redis_url: str = None,
    db_path: str = None,
    transport: str = None,
) -> dict:
    """Create a running notification server for programmatic use/tests.

    ``transport`` selects the transport by name (defaults to ``TRANSPORT``
    or ``websocket``). Returns a dict with the shared ``registry`` plus the
    actual bound ports (the default port ``0`` means "pick a free port"),
    along with the ``store`` (SQLite), ``broker`` (Redis pub/sub), the
    ``transport`` and the background ``subscriber_task`` used to deliver
    backbone messages.
    """
    store = MessageStore(db_path)
    state_store = ClientStateStore(redis_url)
    state_store.connect()
    registry = ClientRegistry(state_store=state_store)
    registry.restore_state()
    broker = RedisBroker(redis_url=redis_url, store=store, registry=registry)
    await broker.connect()
    subscriber_task = None
    if broker.available:
        subscriber_task = asyncio.get_event_loop().create_task(broker.subscribe_loop())
    httpd = start_health_server(registry, store=store, host=http_host, port=http_port)
    transport_obj = get_transport(transport, registry=registry)
    registry.set_transport(transport_obj)
    ws_server = await transport_obj.serve(
        ws_host, ws_port, lambda connection: ws_handler(connection, transport_obj, broker)
    )
    return {
        "registry": registry,
        "httpd": httpd,
        "ws_server": ws_server,
        "ws_port": ws_server.sockets[0].getsockname()[1],
        "http_port": httpd.server_address[1],
        "store": store,
        "broker": broker,
        "state_store": state_store,
        "subscriber_task": subscriber_task,
        "transport": transport_obj,
    }


async def close_server(server: dict) -> None:
    """Shut down a server created by :func:`make_server` cleanly."""
    broker = server.get("broker")
    subscriber_task = server.get("subscriber_task")
    if subscriber_task is not None:
        subscriber_task.cancel()
        try:
            await subscriber_task
        except (asyncio.CancelledError, Exception):
            pass
    if broker is not None:
        broker.stop()
        await broker.close()
    transport = server.get("transport")
    if transport is not None:
        await transport.close(server["ws_server"])
    else:
        server["ws_server"].close()
        await server["ws_server"].wait_closed()
    server["httpd"].shutdown()
    server["httpd"].server_close()
    store = server.get("store")
    if store is not None:
        store.close()


async def main() -> None:
    """Run the notification server forever."""
    server = await make_server(ws_port=WS_PORT, http_port=HTTP_PORT)
    print(f"WebSocket server listening on ws://{WS_HOST}:{server['ws_port']}")
    print(f"Health endpoint on http://{HTTP_HOST}:{server['http_port']}/health")
    print(
        "Broker: "
        + (f"Redis {resolve_redis_url()}" if server["broker"].available else "in-process")
    )
    print(f"History: {server['store']._path}")
    try:
        await asyncio.Future()
    finally:
        await close_server(server)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
