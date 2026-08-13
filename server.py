"""Notification server with a Redis pub/sub backbone and a pluggable transport.

The core notification logic lives in :class:`NotificationServer` and is
completely transport-agnostic: it talks to clients exclusively through the
:class:`BaseTransport` interface. Concrete transports (WebSocket, SSE,
polling, raw TCP, ...) can be plugged in without touching the core logic.
The active transport is chosen from the ``TRANSPORT`` environment variable
(``websocket`` by default).

Features
--------
* Assigns each connected client a unique ID on connect.
* Broadcasts messages to all connected clients.
* Delivers direct messages to a single target client.
* Sends system messages for lifecycle / error events.
* Cleans up clients on disconnect.
* Supports named channels: clients subscribe/unsubscribe dynamically and
  channel messages are delivered only to that channel's subscribers.
* Exposes REST endpoints ``GET /health``, ``GET /channels``,
  ``GET /channels/{name}/subscribers``, ``GET /messages`` and
  ``GET /history``.

Redis integration
-----------------
* When a ``REDIS_URL`` is configured (or a ``redis_client`` is injected) the
  server publishes every broadcast / direct message to a shared Redis channel
  and runs a subscriber task that delivers inbound messages to local clients.
  Multiple server instances sharing the same Redis backbone act as a single
  logical cluster: a message published by one instance is delivered to the
  subscribers of every instance.
* Live client connection state is mirrored into a Redis hash so it survives a
  server process restart and is visible to every instance.
* Without a Redis configuration the server falls back to in-process delivery,
  preserving the original single-node behavior.

Persistence
-----------
* Every message the server emits (broadcast, direct and system) is stored in a
  SQLite database for history. The database path is taken from the
  ``DATABASE_URL`` environment variable (``sqlite:///...`` or a plain path);
  when unset an in-memory database is used.
* ``GET /messages?limit=50&offset=0`` returns stored messages newest-first.
* ``GET /history?channel=X&since=ISO&limit=50&offset=0`` returns stored
  messages for a channel/time range in chronological order, paginated with a
  ``has_more`` flag.

Rate limiting
-------------
* Every client is limited to ``RATE_LIMIT`` inbound messages per minute
  (``100`` by default). Limits are enforced per client ID with Redis counters
  when a Redis backend is available, and with an in-process sliding window
  otherwise. A client that exceeds the limit receives a ``system`` error
  message instead of having its message processed.

Message expiry
--------------
* Messages older than ``MESSAGE_TTL_DAYS`` days (``7`` by default) are
  automatically deleted by a background task that runs on server startup and
  then periodically.

Message format
--------------
All messages are JSON objects::

    {"type": "broadcast" | "direct" | "system" | "subscribe" | "unsubscribe",
     "payload": {...}, "timestamp": "..."}

A ``broadcast`` message carrying a ``channel`` field is routed only to the
subscribers of that channel; without a ``channel`` field it goes to every
connected client.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
import os
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, unquote, urlsplit

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Headers, Response

logger = logging.getLogger("notifyserver")

VALID_TYPES = ("broadcast", "direct", "system", "subscribe", "unsubscribe")

BUS_CHANNEL = "notify:messages"
CLIENTS_KEY = "notify:clients"


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def make_message(msg_type: str, payload: dict) -> dict:
    """Build a message dict using the canonical message format."""
    if msg_type not in VALID_TYPES:
        raise ValueError(f"unsupported message type: {msg_type!r}")
    return {
        "type": msg_type,
        "payload": payload,
        "timestamp": utc_now_iso(),
    }


class ClientRegistry:
    """Thread-safe registry mapping client IDs to connection handles.

    All mutating and reading operations are guarded by a ``threading.Lock``,
    so the registry is safe to touch from any thread. Operations never block
    on I/O, so holding the lock is harmless to the event loop.
    """

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = threading.Lock()

    def add(self, client_id: str, connection: ServerConnection) -> None:
        with self._lock:
            self._clients[client_id] = connection

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str) -> ServerConnection | None:
        with self._lock:
            return self._clients.get(client_id)

    def count(self) -> int:
        with self._lock:
            return len(self._clients)

    def snapshot(self) -> dict[str, ServerConnection]:
        """Return a shallow copy so callers can iterate without the lock."""
        with self._lock:
            return dict(self._clients)

    def __len__(self) -> int:
        return self.count()


class ChannelRegistry:
    """Thread-safe registry mapping channel names to subscribed client IDs.

    All mutating and reading operations are guarded by a ``threading.Lock``,
    so the registry is safe to touch from any thread. Operations never block
    on I/O, so holding the lock is harmless to the event loop.
    """

    def __init__(self) -> None:
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def subscribe(self, channel: str, client_id: str) -> bool:
        """Subscribe ``client_id`` to ``channel``.

        Returns ``True`` if the subscription was newly created.
        """
        with self._lock:
            subs = self._channels.setdefault(channel, set())
            if client_id in subs:
                return False
            subs.add(client_id)
            return True

    def unsubscribe(self, channel: str, client_id: str) -> bool:
        """Unsubscribe ``client_id`` from ``channel``.

        Returns ``True`` if the subscription was actually removed. Empty
        channels are dropped from the registry.
        """
        with self._lock:
            subs = self._channels.get(channel)
            if subs is None or client_id not in subs:
                return False
            subs.discard(client_id)
            if not subs:
                del self._channels[channel]
            return True

    def remove_client(self, client_id: str) -> None:
        """Remove ``client_id`` from every channel (used on disconnect)."""
        with self._lock:
            for subs in self._channels.values():
                subs.discard(client_id)
            self._channels = {
                name: subs for name, subs in self._channels.items() if subs
            }

    def subscribers(self, channel: str) -> set[str]:
        """Return a copy of the subscriber IDs for ``channel``."""
        with self._lock:
            return set(self._channels.get(channel, ()))

    def is_active(self, channel: str) -> bool:
        with self._lock:
            return channel in self._channels

    def is_subscribed(self, channel: str, client_id: str) -> bool:
        with self._lock:
            subs = self._channels.get(channel)
            return subs is not None and client_id in subs

    def snapshot(self) -> dict[str, set[str]]:
        """Return a shallow copy so callers can iterate without the lock."""
        with self._lock:
            return {name: set(subs) for name, subs in self._channels.items()}


class MessageStore:
    """SQLite-backed history of every message the server emits.

    The database path comes from the ``DATABASE_URL`` environment variable
    (accepted as ``sqlite:///path``, a plain path or ``:memory:``). When it is
    not configured an in-memory database is used.
    """

    def __init__(self, database_url: str | None = None) -> None:
        self._lock = threading.Lock()
        path = database_url or os.environ.get("DATABASE_URL")
        self._path = self._resolve_path(path)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    @staticmethod
    def _resolve_path(database_url: str | None) -> str:
        if not database_url:
            return ":memory:"
        url = database_url.strip()
        if url.startswith("sqlite:///"):
            rest = url[len("sqlite:///") :]
            return rest.split("?", 1)[0] or ":memory:"
        if url.startswith("sqlite://"):
            return ":memory:"
        return url

    def _init_db(self) -> None:
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS messages ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  channel TEXT,"
                "  type TEXT NOT NULL,"
                "  payload TEXT NOT NULL,"
                "  timestamp TEXT NOT NULL"
                ")"
            )
            self._conn.commit()

    def insert(
        self,
        channel: str | None,
        msg_type: str,
        payload: dict,
        timestamp: str,
    ) -> int:
        """Persist one message and return its row id."""
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp)"
                " VALUES (?, ?, ?, ?)",
                (channel, msg_type, json.dumps(payload), timestamp),
            )
            self._conn.commit()
            return int(cursor.lastrowid)

    def query(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """Return stored messages newest-first, bounded by limit/offset."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        messages = []
        for row in rows:
            record = dict(row)
            try:
                record["payload"] = json.loads(record["payload"])
            except (TypeError, json.JSONDecodeError):
                record["payload"] = {}
            messages.append(record)
        return messages

    def count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM messages").fetchone()
            return int(row["n"])

    @staticmethod
    def _parse_utc(ts: str) -> datetime | None:
        """Parse an ISO-8601 timestamp, assuming UTC when naive."""
        try:
            parsed = datetime.fromisoformat(ts)
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    def history(
        self,
        channel: str | None = None,
        since: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], bool]:
        """Return messages for a channel / time range in chronological order.

        ``channel`` narrows the query to one channel (or all channels when
        ``None``); ``since`` is an ISO-8601 timestamp that keeps only messages
        at or after that instant. Returns ``(page, has_more)`` where ``page``
        is bounded by ``limit``/``offset`` and ``has_more`` tells the caller
        whether additional pages exist.
        """
        with self._lock:
            if channel:
                rows = self._conn.execute(
                    "SELECT * FROM messages WHERE channel = ? ORDER BY id ASC",
                    (channel,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM messages ORDER BY id ASC"
                ).fetchall()
        messages: list[dict] = []
        for row in rows:
            record = dict(row)
            try:
                record["payload"] = json.loads(record["payload"])
            except (TypeError, json.JSONDecodeError):
                record["payload"] = {}
            messages.append(record)

        since_dt = self._parse_utc(since) if since else None
        if since_dt is not None:
            messages = [
                record
                for record in messages
                if (parsed := self._parse_utc(record.get("timestamp", ""))) is not None
                and parsed >= since_dt
            ]

        page = messages[offset : offset + limit]
        has_more = (offset + len(page)) < len(messages)
        return page, has_more

    def cleanup(self, ttl_days: int = 7) -> int:
        """Delete messages older than ``ttl_days``; return the count removed."""
        ttl_days = max(0, int(ttl_days))
        cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
        with self._lock:
            rows = self._conn.execute("SELECT id, timestamp FROM messages").fetchall()
            stale_ids = [
                row["id"]
                for row in rows
                if (parsed := self._parse_utc(row["timestamp"])) is not None
                and parsed < cutoff
            ]
            if stale_ids:
                placeholders = ",".join("?" for _ in stale_ids)
                self._conn.execute(
                    f"DELETE FROM messages WHERE id IN ({placeholders})", stale_ids
                )
                self._conn.commit()
            return len(stale_ids)

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class RedisBroker:
    """Redis pub/sub backbone shared between server instances.

    Wraps an async Redis client. When constructed from a ``REDIS_URL`` the
    broker owns the client it creates; when injected with ``redis_client`` the
    caller retains ownership (useful in tests that share one fake server).
    """

    def __init__(
        self, redis_client=None, url: str | None = None
    ) -> None:
        self._client = redis_client
        self._url = url
        self._owned = redis_client is None
        self._pubsub = None
        self.ready = asyncio.Event()

    async def connect(self) -> None:
        """Create the client if needed, subscribe to the bus and signal ready."""
        if self._client is None:
            from redis.asyncio import from_url

            self._client = from_url(self._url or os.environ.get("REDIS_URL") or "redis://localhost:6379/0")
        self._pubsub = self._client.pubsub()
        await self._pubsub.subscribe(BUS_CHANNEL)
        self.ready.set()

    @property
    def client(self):
        """The underlying Redis client (may be ``None`` before connect)."""
        return self._client

    async def listen(self):
        """Yield raw pub/sub messages received on the bus channel."""
        if self._pubsub is None:
            await self.connect()
        async for raw in self._pubsub.listen():
            yield raw

    async def publish(self, channel: str, payload: str) -> None:
        await self._client.publish(channel, payload)

    async def set_client(self, client_id: str, meta: str) -> None:
        await self._client.hset(CLIENTS_KEY, client_id, meta)

    async def remove_client(self, client_id: str) -> None:
        await self._client.hdel(CLIENTS_KEY, client_id)

    async def client_exists(self, client_id: str) -> bool:
        return bool(await self._client.hexists(CLIENTS_KEY, client_id))

    async def client_state(self) -> dict[str, str]:
        raw = await self._client.hgetall(CLIENTS_KEY)
        decoded: dict[str, str] = {}
        for key, value in raw.items():
            k = key.decode() if isinstance(key, bytes) else key
            v = value.decode() if isinstance(value, bytes) else value
            decoded[k] = v
        return decoded

    async def close(self) -> None:
        if self._pubsub is not None:
            try:
                await self._pubsub.close()
            except Exception:  # pragma: no cover - best-effort cleanup
                pass
            self._pubsub = None
        if self._owned and self._client is not None:
            close = getattr(self._client, "aclose", None) or getattr(
                self._client, "close", None
            )
            if close is not None:
                try:
                    await close()
                except Exception:  # pragma: no cover - best-effort cleanup
                    pass


def _clamp_int(
    value: str,
    default: int,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    """Parse an integer query parameter, clamping it into a sane range."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    parsed = max(parsed, minimum)
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed


class RateLimiter:
    """Per-client message rate limiter.

    Limits are enforced per client ID. When a Redis client is available a
    fixed one-minute window is tracked with Redis counters (``notify:rate:``
    keys); otherwise an in-process sliding window keeps the server functional
    without a Redis backend. The ``RATE_LIMIT`` environment variable sets the
    maximum number of inbound messages a client may send per minute.
    """

    def __init__(
        self,
        limit: int = 100,
        window_seconds: int = 60,
        redis_client=None,
    ) -> None:
        self.limit = max(1, limit)
        self.window = window_seconds
        self._redis = redis_client
        self._local: dict[str, deque] = {}
        self._lock = threading.Lock()

    def attach_redis(self, redis_client) -> None:
        """Point the limiter at a Redis client (idempotent)."""
        if redis_client is not None:
            self._redis = redis_client

    @staticmethod
    def _redis_key(client_id: str) -> str:
        return f"notify:rate:{client_id}"

    async def allow(self, client_id: str) -> bool:
        """Record one inbound message from ``client_id``.

        Returns ``True`` while the client is within its per-minute quota and
        ``False`` once the quota is exceeded.
        """
        if self._redis is not None:
            key = self._redis_key(client_id)
            count = await self._redis.incr(key)
            await self._redis.expire(key, self.window)
            return count <= self.limit
        return self._allow_local(client_id)

    def _allow_local(self, client_id: str) -> bool:
        now = time.monotonic()
        with self._lock:
            history = self._local.setdefault(client_id, deque())
            while history and now - history[0] >= self.window:
                history.popleft()
            if len(history) >= self.limit:
                if not history:
                    del self._local[client_id]
                return False
            history.append(now)
            if len(self._local) > 4096:
                self._prune(now)
            return True

    def _prune(self, now: float) -> None:
        """Drop bookkeeping for clients whose window has fully expired."""
        cutoff = now - self.window
        for client_id in list(self._local):
            history = self._local[client_id]
            while history and history[0] < cutoff:
                history.popleft()
            if not history:
                del self._local[client_id]


class BaseTransport(ABC):
    """Abstract interface between the core notification logic and a client
    transport mechanism.

    A transport owns the connection plumbing (accepting connections, holding
    the client->connection map and the per-client receive loop) and bridges it
    to the server through a small set of callbacks:

    * ``server.on_client_connected(client_id)``  -- connection established
    * ``server.on_client_message(client_id, raw)`` -- one inbound message
    * ``server.on_client_disconnected(client_id)`` -- connection torn down

    The core server never sees transport-specific objects; it only sends
    encoded messages through :meth:`send_message` and :meth:`broadcast`.
    Implement SSE, polling or raw TCP transports by subclassing this class and
    wiring them into the :func:`create_transport` factory.
    """

    def __init__(self, server: "NotificationServer", host: str, port: int) -> None:
        self.server = server
        self.host = host
        self.port = port

    # ── lifecycle ──────────────────────────────────────────────

    @abstractmethod
    async def start(self) -> None:
        """Begin accepting client connections."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop accepting connections and release resources."""

    @property
    @abstractmethod
    def started(self) -> bool:
        """Whether the transport is currently accepting connections."""

    # ── client lifecycle ───────────────────────────────────────

    @abstractmethod
    async def on_connect(self, connection) -> str:
        """Register a new connection and return its unique client id."""

    @abstractmethod
    async def on_disconnect(self, client_id: str, connection=None) -> None:
        """Deregister a client connection."""

    # ── messaging ──────────────────────────────────────────────

    @abstractmethod
    async def send_message(self, client_id: str, message: str) -> bool:
        """Deliver an encoded message to one client; returns success."""

    @abstractmethod
    async def broadcast(
        self, message: str, targets: set[str] | None = None
    ) -> int:
        """Deliver an encoded message to ``targets`` (all clients if None).

        Returns the number of clients the message was actually delivered to.
        """

    # ── introspection ──────────────────────────────────────────

    @abstractmethod
    async def client_exists(self, client_id: str) -> bool:
        """Return whether ``client_id`` is currently connected."""

    @abstractmethod
    async def client_count(self) -> int:
        """Return the number of currently connected clients."""

    @property
    @abstractmethod
    def sockets(self):
        """The underlying listening sockets, or ``None`` when not started."""

    @property
    @abstractmethod
    def bound_port(self) -> int:
        """The port clients connect to (handles ``port=0``)."""


class WebSocketTransport(BaseTransport):
    """WebSocket transport built on the ``websockets`` library.

    Accepts connections over ``ws://host:port`` and also serves the server's
    plain-HTTP REST endpoints (``/health``, ``/channels``, ``/messages``)
    during the WebSocket handshake request.
    """

    def __init__(self, server: "NotificationServer", host: str, port: int) -> None:
        super().__init__(server, host, port)
        self.registry = ClientRegistry()
        self._ids = itertools.count(1)
        self._server = None

    # ── lifecycle ──────────────────────────────────────────────

    async def start(self) -> None:
        if self._server is not None:
            return
        self._server = await serve(
            self._client_handler,
            self.host,
            self.port,
            process_request=self.server._process_request,
        )

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    @property
    def started(self) -> bool:
        return self._server is not None

    @property
    def sockets(self):
        return self._server.sockets if self._server is not None else None

    @property
    def bound_port(self) -> int:
        if self.sockets is None:
            return self.port
        return self.sockets[0].getsockname()[1]

    # ── client lifecycle ───────────────────────────────────────

    async def on_connect(self, connection: ServerConnection) -> str:
        client_id = f"client-{next(self._ids)}"
        self.registry.add(client_id, connection)
        logger.info("client connected: %s", client_id)
        return client_id

    async def on_disconnect(self, client_id: str, connection=None) -> None:
        self.registry.remove(client_id)
        logger.info("client disconnected: %s", client_id)

    # ── messaging ──────────────────────────────────────────────

    async def send_message(self, client_id: str, message: str) -> bool:
        ws = self.registry.get(client_id)
        if ws is None:
            return False
        try:
            await ws.send(message)
            return True
        except ConnectionClosed:
            await self.on_disconnect(client_id, ws)
            await self.server.on_client_disconnected(client_id)
            return False

    async def broadcast(
        self, message: str, targets: set[str] | None = None
    ) -> int:
        if targets is None:
            targets = set(self.registry.snapshot())
        sent = 0
        for client_id in targets:
            ws = self.registry.get(client_id)
            if ws is None:
                continue
            try:
                await ws.send(message)
                sent += 1
            except ConnectionClosed:
                await self.on_disconnect(client_id, ws)
                await self.server.on_client_disconnected(client_id)
        return sent

    # ── introspection ──────────────────────────────────────────

    async def client_exists(self, client_id: str) -> bool:
        return self.registry.get(client_id) is not None

    async def client_count(self) -> int:
        return self.registry.count()

    # ── connection handling ────────────────────────────────────

    async def _client_handler(self, ws: ServerConnection) -> None:
        client_id = await self.on_connect(ws)
        try:
            await self.server.on_client_connected(client_id)
            async for raw in ws:
                await self.server.on_client_message(client_id, raw)
        except ConnectionClosed:
            pass
        finally:
            await self.on_disconnect(client_id, ws)
            await self.server.on_client_disconnected(client_id)


def create_transport(server: "NotificationServer", host: str, port: int) -> BaseTransport:
    """Build the transport selected by the ``TRANSPORT`` environment variable.

    ``websocket`` (or ``ws``) is the default and currently the only built-in
    transport; additional transports (SSE, polling, raw TCP) can be registered
    here by extending ``TRANSPORTS``.
    """
    transports: dict[str, type[BaseTransport]] = {
        "websocket": WebSocketTransport,
        "ws": WebSocketTransport,
    }
    name = os.environ.get("TRANSPORT", "websocket").strip().lower()
    try:
        transport_cls = transports[name]
    except KeyError:
        raise ValueError(
            f"unknown transport: {name!r} (expected one of {sorted(transports)})"
        ) from None
    return transport_cls(server, host, port)


class NotificationServer:
    """Transport-agnostic notification server.

    The server owns the core notification logic (channels, history, Redis
    backbone, message protocol) and communicates with clients exclusively
    through its :attr:`transport`, an instance of :class:`BaseTransport`.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        redis_client=None,
        database_url: str | None = None,
        transport: BaseTransport | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.channels = ChannelRegistry()
        self.store = MessageStore(database_url)
        self.transport = transport or create_transport(self, host, port)
        self._listener_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None
        self._cleanup_interval = _clamp_int(
            os.environ.get("CLEANUP_INTERVAL_SECONDS", "3600"),
            default=3600,
            minimum=10,
        )
        self.rate_limit = _clamp_int(
            os.environ.get("RATE_LIMIT", "100"),
            default=100,
            minimum=1,
            maximum=1_000_000,
        )
        self.rate_limiter = RateLimiter(
            limit=self.rate_limit, redis_client=redis_client
        )
        if redis_client is not None or os.environ.get("REDIS_URL"):
            self.broker = RedisBroker(
                redis_client=redis_client, url=os.environ.get("REDIS_URL")
            )
        else:
            self.broker = None

    # ── lifecycle ──────────────────────────────────────────────

    async def start(self) -> None:
        """Start accepting connections on ``host:port``."""
        if self.transport.started:
            return
        if self.broker is not None:
            await self.broker.connect()
            self.rate_limiter.attach_redis(self.broker.client)
        await self.transport.start()
        if self.broker is not None:
            self._listener_task = asyncio.create_task(self._redis_listener())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """Close the listening socket and stop accepting connections."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except (asyncio.CancelledError, Exception):
                pass
            self._cleanup_task = None
        if self._listener_task is not None:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except (asyncio.CancelledError, Exception):
                pass
            self._listener_task = None
        if self.broker is not None:
            await self.broker.close()
        await self.transport.stop()
        self.store.close()

    async def _cleanup_loop(self) -> None:
        """Periodically purge messages older than ``MESSAGE_TTL_DAYS`` days.

        Runs on server startup (first iteration deletes immediately) and then
        every ``CLEANUP_INTERVAL_SECONDS`` seconds.
        """
        ttl_days = _clamp_int(
            os.environ.get("MESSAGE_TTL_DAYS", "7"), default=7, minimum=0
        )
        while True:
            try:
                removed = self.store.cleanup(ttl_days)
                if removed:
                    logger.info("cleaned up %d expired messages", removed)
            except Exception:
                logger.exception("message cleanup task failed")
            try:
                await asyncio.sleep(self._cleanup_interval)
            except asyncio.CancelledError:
                raise

    @property
    def sockets(self):
        return self.transport.sockets

    @property
    def bound_port(self) -> int:
        """Return the actual bound port (handles ``port=0``)."""
        return self.transport.bound_port

    # ── message helpers ────────────────────────────────────────

    @staticmethod
    def _encode(msg: dict) -> str:
        return json.dumps(msg)

    async def _send(self, client_id: str, msg_type: str, payload: dict) -> None:
        msg = make_message(msg_type, payload)
        await self.transport.send_message(client_id, self._encode(msg))
        self.store.insert(None, msg_type, payload, msg["timestamp"])

    # ── public API ─────────────────────────────────────────────

    async def broadcast(self, payload: dict, channel: str | None = None) -> int:
        """Send a ``broadcast`` message to clients.

        When ``channel`` is provided the message is delivered only to the
        subscribers of that channel; otherwise it goes to every connected
        client. Returns the number of clients the message was delivered to
        (in Redis mode this is the number of *local* clients that will
        receive it; remote instances deliver on their own).
        """
        msg = make_message("broadcast", payload)
        if channel is not None:
            msg["channel"] = channel
        self.store.insert(channel, "broadcast", payload, msg["timestamp"])

        if self.broker is not None:
            await self.broker.publish(
                BUS_CHANNEL,
                json.dumps({"kind": "broadcast", "channel": channel, "message": msg}),
            )
            if channel is not None:
                count = 0
                for cid in self.channels.subscribers(channel):
                    if await self.transport.client_exists(cid):
                        count += 1
                return count
            return await self.transport.client_count()

        if channel is not None:
            targets = self.channels.subscribers(channel)
        else:
            targets = None
        return await self.transport.broadcast(self._encode(msg), targets=targets)

    async def send_direct(self, target_id: str, payload: dict) -> bool:
        """Send a ``direct`` message to a single client.

        Returns ``False`` if the target client is not connected (or, in Redis
        mode, not known to any instance of the cluster).
        """
        msg = make_message("direct", payload)

        if self.broker is not None:
            if not await self.transport.client_exists(
                target_id
            ) and not await self.broker.client_exists(target_id):
                return False
            self.store.insert(None, "direct", payload, msg["timestamp"])
            await self.broker.publish(
                BUS_CHANNEL,
                json.dumps({"kind": "direct", "target": target_id, "message": msg}),
            )
            return True

        if not await self.transport.client_exists(target_id):
            return False
        self.store.insert(None, "direct", payload, msg["timestamp"])
        return await self.transport.send_message(target_id, self._encode(msg))

    async def client_count(self) -> int:
        """Return the number of currently connected clients."""
        return await self.transport.client_count()

    # ── transport callbacks ────────────────────────────────────

    async def on_client_connected(self, client_id: str) -> None:
        """Hook called by the transport when a client connection is accepted."""
        if self.broker is not None:
            await self.broker.set_client(
                client_id, json.dumps({"connected_at": utc_now_iso()})
            )
        await self._send(
            client_id, "system", {"event": "connected", "client_id": client_id}
        )

    async def on_client_message(self, client_id: str, raw: str) -> None:
        """Hook called by the transport for each inbound client message."""
        await self._handle_message(client_id, raw)

    async def on_client_disconnected(self, client_id: str) -> None:
        """Hook called by the transport when a client connection is torn down."""
        self.channels.remove_client(client_id)
        if self.broker is not None:
            await self.broker.remove_client(client_id)

    # ── Redis backbone ─────────────────────────────────────────

    async def _redis_listener(self) -> None:
        """Subscribe to the shared bus and deliver inbound messages locally."""
        try:
            async for raw in self.broker.listen():
                if not isinstance(raw, dict) or raw.get("type") != "message":
                    continue
                data = raw.get("data")
                if isinstance(data, bytes):
                    data = data.decode("utf-8", "replace")
                if not isinstance(data, str):
                    continue
                try:
                    envelope = json.loads(data)
                except json.JSONDecodeError:
                    continue
                await self._deliver_envelope(envelope)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("redis listener failed")

    async def _deliver_envelope(self, envelope: dict) -> None:
        """Route an inbound bus envelope to the local clients that want it."""
        if not isinstance(envelope, dict):
            return
        kind = envelope.get("kind")
        message = envelope.get("message")
        if not isinstance(message, dict):
            return
        encoded = json.dumps(message)

        if kind == "broadcast":
            channel = envelope.get("channel")
            if channel:
                targets = {
                    cid
                    for cid in self.channels.subscribers(channel)
                    if await self.transport.client_exists(cid)
                }
            else:
                targets = None
        elif kind == "direct":
            target = envelope.get("target")
            targets = (
                {target}
                if await self.transport.client_exists(target)
                else set()
            )
        else:
            return

        await self.transport.broadcast(encoded, targets=targets)

    # ── message handling ───────────────────────────────────────

    async def _handle_message(self, client_id: str, raw: str) -> None:
        if not await self.rate_limiter.allow(client_id):
            await self._send(
                client_id,
                "system",
                {
                    "client_id": client_id,
                    "error": "rate limit exceeded: too many messages",
                },
            )
            return
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await self._send(
                client_id,
                "system",
                {"client_id": client_id, "error": "invalid JSON message"},
            )
            return

        if not isinstance(data, dict):
            await self._send(
                client_id,
                "system",
                {"client_id": client_id, "error": "message must be a JSON object"},
            )
            return

        msg_type = data.get("type")
        payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}

        if msg_type == "broadcast":
            await self.broadcast(payload, channel=self._extract_channel(data, payload))
        elif msg_type == "subscribe":
            await self._handle_subscribe(client_id, data, payload)
        elif msg_type == "unsubscribe":
            await self._handle_unsubscribe(client_id, data, payload)
        elif msg_type == "direct":
            target = payload.get("to")
            if not isinstance(target, str) or not target:
                await self._send(
                    client_id,
                    "system",
                    {
                        "client_id": client_id,
                        "error": "direct message requires a string 'to' target",
                    },
                )
                return
            forwarded = dict(payload)
            forwarded["from"] = client_id
            if not await self.send_direct(target, forwarded):
                await self._send(
                    client_id,
                    "system",
                    {
                        "client_id": client_id,
                        "error": f"unknown target client: {target}",
                    },
                )
        else:
            await self._send(
                client_id,
                "system",
                {
                    "client_id": client_id,
                    "error": f"unsupported message type: {msg_type!r}",
                },
            )

    # ── channel helpers ────────────────────────────────────────

    @staticmethod
    def _extract_channels(data: dict, payload: dict) -> list[str]:
        """Extract a list of channel names from a message.

        The ``channel`` field may live at the top level of the message or
        inside the payload. A ``channels`` list inside the payload is also
        accepted so clients can subscribe to several channels at once.
        """
        raw = data.get("channel", payload.get("channel"))
        if raw is None:
            raw = payload.get("channels")
        if isinstance(raw, str):
            cleaned = raw.strip()
            return [cleaned] if cleaned else []
        if isinstance(raw, list):
            return [c.strip() for c in raw if isinstance(c, str) and c.strip()]
        return []

    def _extract_channel(self, data: dict, payload: dict) -> str | None:
        channels = self._extract_channels(data, payload)
        return channels[0] if channels else None

    async def _handle_subscribe(
        self, client_id: str, data: dict, payload: dict
    ) -> None:
        channels = self._extract_channels(data, payload)
        if not channels:
            await self._send(
                client_id,
                "system",
                {
                    "client_id": client_id,
                    "error": "subscribe requires a 'channel'",
                },
            )
            return
        for channel in channels:
            self.channels.subscribe(channel, client_id)
        await self._send(
            client_id,
            "system",
            {
                "client_id": client_id,
                "event": "subscribed",
                "channels": channels,
            },
        )

    async def _handle_unsubscribe(
        self, client_id: str, data: dict, payload: dict
    ) -> None:
        channels = self._extract_channels(data, payload)
        if not channels:
            await self._send(
                client_id,
                "system",
                {
                    "client_id": client_id,
                    "error": "unsubscribe requires a 'channel'",
                },
            )
            return
        for channel in channels:
            self.channels.unsubscribe(channel, client_id)
        await self._send(
            client_id,
            "system",
            {
                "client_id": client_id,
                "event": "unsubscribed",
                "channels": channels,
            },
        )

    # ── REST endpoints ─────────────────────────────────────────

    async def _process_request(self, connection, request) -> Response | None:
        """Serve ``GET /health``, ``GET /channels``, ``GET
        /channels/{name}/subscribers`` and ``GET /messages`` over plain HTTP;
        pass everything else through."""
        path = urlsplit(request.path).path.rstrip("/")
        if path == "/health":
            return await self._health_response()
        if path == "/channels":
            return await self._channels_response()
        if path == "/messages":
            return await self._messages_response(request)
        if path == "/history":
            return await self._history_response(request)
        if path.startswith("/channels/") and path.endswith("/subscribers"):
            name = unquote(path[len("/channels/") : -len("/subscribers")])
            return await self._subscribers_response(name)
        return None

    @staticmethod
    def _json_response(status: int, body: dict) -> Response:
        encoded = json.dumps(body).encode("utf-8")
        headers = Headers()
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(encoded))
        reason = "OK" if status == 200 else "Not Found"
        return Response(status, reason, headers, encoded)

    async def _health_response(self) -> Response:
        body = json.dumps(
            {
                "status": "ok",
                "clients": await self.client_count(),
                "timestamp": utc_now_iso(),
            }
        ).encode("utf-8")
        headers = Headers()
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
        return Response(200, "OK", headers, body)

    async def _channels_response(self) -> Response:
        snapshot = self.channels.snapshot()
        channels = {name: len(subscribers) for name, subscribers in snapshot.items()}
        return self._json_response(
            200,
            {"channels": channels, "timestamp": utc_now_iso()},
        )

    async def _subscribers_response(self, channel: str) -> Response:
        if not channel or not self.channels.is_active(channel):
            return self._json_response(
                404,
                {"error": f"unknown channel: {channel!r}"},
            )
        subscribers = sorted(self.channels.subscribers(channel))
        return self._json_response(
            200,
            {
                "channel": channel,
                "subscribers": subscribers,
                "timestamp": utc_now_iso(),
            },
        )

    async def _messages_response(self, request) -> Response:
        """Serve ``GET /messages?limit=N&offset=M`` from persisted history."""
        query = parse_qs(urlsplit(request.path).query)
        limit = _clamp_int(
            query.get("limit", ["50"])[0], default=50, minimum=0, maximum=500
        )
        offset = _clamp_int(query.get("offset", ["0"])[0], default=0, minimum=0)
        return self._json_response(
            200,
            {
                "messages": self.store.query(limit, offset),
                "total": self.store.count(),
                "limit": limit,
                "offset": offset,
            },
        )

    async def _history_response(self, request) -> Response:
        """Serve ``GET /history?channel=X&since=ISO&limit=N&offset=M``."""
        query = parse_qs(urlsplit(request.path).query)
        channel = query.get("channel", [None])[0]
        since = query.get("since", [None])[0]
        limit = _clamp_int(
            query.get("limit", ["50"])[0], default=50, minimum=0, maximum=500
        )
        offset = _clamp_int(query.get("offset", ["0"])[0], default=0, minimum=0)
        messages, has_more = self.store.history(channel, since, limit, offset)
        return self._json_response(
            200,
            {
                "messages": messages,
                "has_more": has_more,
                "limit": limit,
                "offset": offset,
            },
        )


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    server = NotificationServer()
    await server.start()
    print(
        f"Notification server ({type(server.transport).__name__}) listening on "
        f"{server.host}:{server.bound_port}"
    )
    try:
        await asyncio.Future()  # run forever
    finally:
        await server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
