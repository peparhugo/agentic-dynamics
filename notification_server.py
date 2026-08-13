"""
Notification server with a Redis pub/sub message backbone and a pluggable
transport layer.

Accepts client connections through a configurable transport, assigns each
client a unique ID, broadcasts messages to all connected clients, handles
clean disconnects, and exposes REST endpoints for health, channels, and
message history. The WebSocket transport is the default; other transports
(SSE, polling, raw TCP) can be added by subclassing ``BaseTransport`` without
touching the core notification logic.

Message backbone
----------------
Messages are distributed over Redis pub/sub channels. A server publishes every
broadcast to a Redis channel and every server instance runs a subscriber that
delivers the message to its own connected clients. This lets multiple server
instances share a single Redis backbone. When Redis is unavailable the server
delivers locally, so it keeps working without a broker.

Client connection state (client IDs and their channel subscriptions) is
mirrored into Redis when a broker is available, so the state survives a server
restart.

Persistence
-----------
Every broadcast and direct message is stored in SQLite so a history can be
served back through ``GET /messages`` and ``GET /history``.

Rate limiting
-------------
Each client is limited to ``RATE_LIMIT`` messages per minute (default 100).
Counters are enforced per client ID using Redis when a broker is available,
with an in-memory sliding-window fallback otherwise. Exceeding the limit
returns an error message to the client instead of silently dropping messages.

Message expiry
--------------
Messages older than ``MESSAGE_TTL_DAYS`` days (default 7) are purged
periodically by a background task started when the server boots.

Configuration
-------------
``REDIS_URL``                optional Redis connection URL for the pub/sub
                             backbone.
``DATABASE_URL``             optional SQLite path (or ``sqlite:///...`` URL)
                             for history.
``TRANSPORT``                transport name to use for client connections
                             (default ``"websocket"``).
``RATE_LIMIT``               per-client messages allowed per minute (default
                             100).
``MESSAGE_TTL_DAYS``         age at which stored messages are purged (default
                             7).
``CLEANUP_INTERVAL_SECONDS`` how often the expiry sweep runs (default 3600).

Clients can subscribe to named channels (e.g. ``"alerts"``, ``"system"``,
``"chat"``). Messages that carry a ``channel`` field are delivered only to the
clients subscribed to that channel; messages without a channel still broadcast
to all connected clients.

Message format (JSON)::

    {"type": str, "payload": dict, "timestamp": str}

Supported types: ``"broadcast"``, ``"direct"``, ``"system"``, ``"subscribe"``,
``"unsubscribe"``.

REST endpoints::

    GET /health                          connected client count
    GET /channels                        active channels and subscriber counts
    GET /channels/{name}/subscribers     subscriber IDs for a channel
    GET /messages?limit=50&offset=0      persisted message history
    GET /history?channel=X&since=ISO&limit=50   channel/time-range history
"""

from __future__ import annotations

import abc
import asyncio
import json
import os
import sqlite3
import threading
import time
import uuid
import weakref
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import websockets
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

MESSAGE_TYPES = ("broadcast", "direct", "system", "subscribe", "unsubscribe")

HEALTH_PATH = "/health"
CHANNELS_PATH = "/channels"
MESSAGES_PATH = "/messages"
HISTORY_PATH = "/history"
WEBSOCKET_PATHS = ("/", "/ws")

DEFAULT_RATE_LIMIT = 100
DEFAULT_MESSAGE_TTL_DAYS = 7
DEFAULT_CLEANUP_INTERVAL = 3600

BROADCAST_CHANNEL = "broadcast"


def _redis_url() -> str | None:
    return os.environ.get("REDIS_URL")


def _database_url() -> str | None:
    return os.environ.get("DATABASE_URL")


def now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def make_message(msg_type: str, payload: dict, timestamp: str | None = None) -> dict:
    """Build a message dict conforming to the canonical message format."""
    if msg_type not in MESSAGE_TYPES:
        raise ValueError(f"unsupported message type: {msg_type!r}")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
    return {
        "type": msg_type,
        "payload": payload,
        "timestamp": timestamp or now_iso(),
    }


def _decode(value) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


def _parse_iso(value):
    """
    Parse an ISO-8601 timestamp into an aware datetime, or ``None`` when the
    value is not parseable. Naive timestamps are assumed to be UTC, and a
    trailing ``Z`` suffix is normalized to an explicit ``+00:00`` offset.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


# ── Pub/Sub backbone ────────────────────────────────────────────────

class Broker:
    """
    Pub/sub message backbone.

    When a ``redis_client`` is supplied (or ``REDIS_URL`` is set) messages are
    published to Redis channels and each server runs a subscriber task that
    delivers them to its local clients, letting multiple server instances share
    a single backbone. Without Redis the server falls back to a no-op broker and
    delivers locally, so it keeps working with no broker running.
    """

    def __init__(self, redis_client=None) -> None:
        self.redis_client = redis_client
        self._pubsub = None
        self._subscribed: set[str] = set()
        self._lock = threading.RLock()
        self._connected = False

    @property
    def redis_enabled(self) -> bool:
        return self.redis_client is not None

    async def connect(self) -> None:
        """Prepare the broker for use, degrading gracefully to in-memory."""
        if self._connected:
            return
        if self.redis_client is not None:
            try:
                await self.redis_client.ping()
            except Exception:
                self.redis_client = None
        self._connected = True
        if self.redis_client is not None:
            self._pubsub = self.redis_client.pubsub()

    async def subscribe(self, channel: str) -> None:
        await self.connect()
        if self.redis_client is None:
            return
        with self._lock:
            if channel in self._subscribed:
                return
            self._subscribed.add(channel)
        await self._pubsub.subscribe(channel)

    async def unsubscribe(self, channel: str) -> None:
        await self.connect()
        if self.redis_client is None:
            return
        with self._lock:
            if channel not in self._subscribed:
                return
            self._subscribed.discard(channel)
        await self._pubsub.unsubscribe(channel)

    def channels_subscribed(self) -> set[str]:
        with self._lock:
            return set(self._subscribed)

    async def publish(self, channel: str, payload: dict) -> None:
        """Publish a message dict to a channel."""
        await self.connect()
        if self.redis_client is None:
            return
        await self.redis_client.publish(channel, json.dumps(payload))

    async def next_message(self):
        """
        Return the next ``(channel, data)`` from Redis, or ``None`` when nothing
        is pending. Polls so cancellation during event loop shutdown is clean.
        """
        await self.connect()
        if self.redis_client is None:
            await asyncio.sleep(0.01)
            return None
        msg = await self._pubsub.get_message(ignore_subscribe_messages=True)
        if msg is None:
            await asyncio.sleep(0.01)
            return None
        channel = _decode(msg.get("channel"))
        data = _decode(msg.get("data"))
        if channel is None or data is None:
            return None
        return channel, data


def _make_default_broker() -> Broker:
    """Build the process-wide default broker from the environment."""
    redis_url = _redis_url()
    if not redis_url:
        return Broker()
    try:
        import redis.asyncio as aioredis
    except ImportError:
        return Broker()
    try:
        client = aioredis.from_url(redis_url)
    except Exception:
        return Broker()
    return Broker(redis_client=client)


# ── Rate limiting ────────────────────────────────────────────────────

class RateLimiter:
    """
    Per-client message rate limiting.

    Counters are keyed by client ID and enforced in Redis when a client is
    available, so limits are shared across server instances. Without Redis the
    limiter falls back to an in-memory sliding window. The per-minute limit is
    configurable via the ``RATE_LIMIT`` environment variable (default 100).
    """

    def __init__(
        self,
        redis_client=None,
        limit: int | None = None,
        window_seconds: int = 60,
    ) -> None:
        self.redis_client = redis_client
        self.limit = limit if limit is not None else _env_int(
            "RATE_LIMIT", DEFAULT_RATE_LIMIT
        )
        self.window_seconds = max(1, int(window_seconds))
        self._memory: dict[str, list[float]] = {}
        self._lock = threading.RLock()

    @property
    def redis_enabled(self) -> bool:
        return self.redis_client is not None

    @staticmethod
    def _counter_key(client_id: str, bucket: int) -> str:
        return f"ntf:rate:{client_id}:{bucket}"

    async def allow(self, client_id: str) -> bool:
        """Record a message from ``client_id``; False once the limit is hit."""
        if self.redis_client is not None:
            bucket = int(time.time() // self.window_seconds)
            key = self._counter_key(client_id, bucket)
            count = await self.redis_client.incr(key)
            if count == 1:
                await self.redis_client.expire(key, self.window_seconds + 60)
            return count <= self.limit
        now = time.time()
        window_start = now - self.window_seconds
        with self._lock:
            stamps = self._memory.setdefault(client_id, [])
            stamps[:] = [t for t in stamps if t > window_start]
            stamps.append(now)
            if len(stamps) > self.limit:
                self._memory[client_id] = stamps[:-1]
                return False
            return True

    async def reset(self, client_id: str) -> None:
        """Clear the counters for a client (used by tests and admin tooling)."""
        if self.redis_client is not None:
            await self.redis_client.delete(self._counter_key(client_id, int(time.time() // self.window_seconds)))
        else:
            with self._lock:
                self._memory.pop(client_id, None)


# ── Persistence ─────────────────────────────────────────────────────

class MessageStore:
    """
    SQLite-backed history for messages.

    The ``messages`` table holds ``id``, ``channel``, ``type``, ``payload``
    (JSON-encoded) and ``timestamp``. A single connection guarded by a lock is
    reused so in-memory databases (``:memory:``) work correctly.
    """

    def __init__(self, database: str | None = None) -> None:
        self.database = database or _database_url()
        self._path = self._resolve_path(self.database)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._init_schema()
        weakref.finalize(self, self._close_connection, self._conn)

    @staticmethod
    def _close_connection(conn) -> None:
        try:
            conn.close()
        except Exception:
            pass

    @staticmethod
    def _resolve_path(database: str | None) -> str:
        if not database:
            return ":memory:"
        if database.startswith("sqlite:///"):
            return database[len("sqlite:///"):]
        if database.startswith("sqlite://"):
            return database[len("sqlite://"):] or ":memory:"
        return database

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

    def save(self, message: dict, channel: str | None = None) -> int:
        """Persist a message dict. Returns the new row id."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (
                    channel,
                    message["type"],
                    json.dumps(message["payload"]),
                    message["timestamp"],
                ),
            )
            self._conn.commit()
            return cur.lastrowid

    def list(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """Return stored messages ordered by id (oldest first)."""
        limit = max(0, int(limit))
        offset = max(0, int(offset))
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, channel, type, payload, timestamp "
                "FROM messages ORDER BY id ASC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        out = []
        for row in rows:
            entry = dict(row)
            try:
                entry["payload"] = json.loads(entry["payload"])
            except (json.JSONDecodeError, TypeError):
                pass
            out.append(entry)
        return out

    def query(
        self,
        channel: str | None = None,
        since: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], bool]:
        """
        Return ``(messages, has_more)`` for an optional channel and optional
        ``since`` timestamp. Messages are returned in chronological order and
        paginated with ``limit``/``offset``; ``has_more`` is True when more
        matching messages exist beyond the returned page.
        """
        limit = max(0, int(limit))
        offset = max(0, int(offset))
        since_dt = _parse_iso(since) if since is not None else None
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, channel, type, payload, timestamp "
                "FROM messages"
            ).fetchall()
        matched = []
        for row in rows:
            if channel is not None and row["channel"] != channel:
                continue
            if since_dt is not None:
                ts = _parse_iso(row["timestamp"])
                if ts is None or ts < since_dt:
                    continue
            entry = dict(row)
            try:
                entry["payload"] = json.loads(entry["payload"])
            except (json.JSONDecodeError, TypeError):
                pass
            matched.append(entry)
        matched.sort(
            key=lambda m: (_parse_iso(m["timestamp"]) or datetime.min.replace(tzinfo=timezone.utc), m["id"])
        )
        has_more = len(matched) > offset + limit
        return matched[offset:offset + limit], has_more

    def purge_older_than(self, ttl_days: int) -> int:
        """
        Delete every message older than ``ttl_days`` days (based on its
        timestamp). Returns the number of deleted rows. A non-positive TTL
        disables cleanup and returns 0.
        """
        ttl_days = int(ttl_days)
        if ttl_days <= 0:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, timestamp FROM messages"
            ).fetchall()
            stale_ids = []
            for row in rows:
                ts = _parse_iso(row["timestamp"])
                if ts is not None and ts < cutoff:
                    stale_ids.append(row["id"])
            deleted = 0
            for message_id in stale_ids:
                cur = self._conn.execute(
                    "DELETE FROM messages WHERE id = ?", (message_id,)
                )
                deleted += cur.rowcount
            self._conn.commit()
            return deleted

    def count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) FROM messages").fetchone()
            return int(row[0])

    def close(self) -> None:
        with self._lock:
            self._conn.close()


# ── Redis-backed client connection state ───────────────────────────

class ConnectionStore:
    """
    Client connection state, mirrored to Redis when available.

    Client IDs and their channel subscriptions are recorded here so the state
    survives a server restart. Falls back to an in-memory map when no Redis
    connection is available.
    """

    CLIENTS_KEY = "ntf:clients"

    def __init__(self, redis_client=None) -> None:
        self.redis_client = redis_client
        self._memory: dict[str, dict] = {}
        self._lock = threading.RLock()

    @property
    def redis_enabled(self) -> bool:
        return self.redis_client is not None

    @staticmethod
    def _client_key(client_id: str) -> str:
        return f"ntf:client:{client_id}"

    async def register(self, client_id: str) -> None:
        if self.redis_client is not None:
            await self.redis_client.sadd(self.CLIENTS_KEY, client_id)
            await self.redis_client.hset(
                self._client_key(client_id), "channels", "[]"
            )
        else:
            with self._lock:
                self._memory[client_id] = {"channels": set()}

    async def unregister(self, client_id: str) -> None:
        if self.redis_client is not None:
            await self.redis_client.srem(self.CLIENTS_KEY, client_id)
            await self.redis_client.delete(self._client_key(client_id))
        else:
            with self._lock:
                self._memory.pop(client_id, None)

    async def add_channel(self, client_id: str, channel: str) -> None:
        if self.redis_client is not None:
            channels = await self.channels_for(client_id)
            if channel not in channels:
                channels.append(channel)
                await self.redis_client.hset(
                    self._client_key(client_id),
                    "channels",
                    json.dumps(channels),
                )
        else:
            with self._lock:
                entry = self._memory.get(client_id)
                if entry is not None:
                    entry["channels"].add(channel)

    async def remove_channel(self, client_id: str, channel: str) -> None:
        if self.redis_client is not None:
            channels = await self.channels_for(client_id)
            if channel in channels:
                channels.remove(channel)
                await self.redis_client.hset(
                    self._client_key(client_id),
                    "channels",
                    json.dumps(channels),
                )
        else:
            with self._lock:
                entry = self._memory.get(client_id)
                if entry is not None:
                    entry["channels"].discard(channel)

    async def channels_for(self, client_id: str) -> list[str]:
        if self.redis_client is not None:
            raw = await self.redis_client.hget(
                self._client_key(client_id), "channels"
            )
            if raw is None:
                return []
            try:
                return json.loads(_decode(raw))
            except (json.JSONDecodeError, TypeError):
                return []
        with self._lock:
            entry = self._memory.get(client_id)
            return sorted(entry["channels"]) if entry else []

    async def clients(self) -> list[str]:
        if self.redis_client is not None:
            raw = await self.redis_client.smembers(self.CLIENTS_KEY)
            return sorted(_decode(c) for c in raw)
        with self._lock:
            return sorted(self._memory)


# ── Connection and channel registries ──────────────────────────────

class ClientRegistry:
    """
    Thread-safe registry mapping client IDs to their transport connections.

    All operations are protected by a reentrant lock so the registry can be
    mutated from the asyncio event loop or from plain threads (e.g. the
    synchronous HTTP health check) without corruption.
    """

    def __init__(self) -> None:
        self._clients: dict[str, object] = {}
        self._lock = threading.RLock()

    def add(self, client_id: str, websocket: object) -> None:
        with self._lock:
            self._clients[client_id] = websocket

    def remove(self, client_id: str) -> object | None:
        with self._lock:
            return self._clients.pop(client_id, None)

    def get(self, client_id: str) -> object | None:
        with self._lock:
            return self._clients.get(client_id)

    def all(self) -> list[tuple[str, object]]:
        with self._lock:
            return list(self._clients.items())

    def count(self) -> int:
        with self._lock:
            return len(self._clients)


class ChannelRegistry:
    """
    Thread-safe registry mapping channel names to the set of subscribed client
    IDs. A client may subscribe to any number of channels.
    """

    def __init__(self) -> None:
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def subscribe(self, channel: str, client_id: str) -> None:
        with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, channel: str, client_id: str) -> None:
        with self._lock:
            members = self._channels.get(channel)
            if members is None:
                return
            members.discard(client_id)
            if not members:
                self._channels.pop(channel, None)

    def remove_client(self, client_id: str) -> None:
        with self._lock:
            empty = []
            for channel, members in self._channels.items():
                members.discard(client_id)
                if not members:
                    empty.append(channel)
            for channel in empty:
                self._channels.pop(channel, None)

    def subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    def channels(self) -> dict[str, int]:
        with self._lock:
            return {name: len(members) for name, members in self._channels.items()}


# ── Transport layer ────────────────────────────────────────────────

class BaseTransport(abc.ABC):
    """
    Abstract transport interface for client connections.

    Concrete transports (WebSocket, SSE, polling, raw TCP) plug the
    connection-level mechanics into the :class:`NotificationServer` so the core
    logic never depends on how messages reach a client. A transport owns each
    client's connection object; the server keeps track of client identity,
    channel subscriptions and message routing.

    Implementations are registered with a name (``__init_subclass__``) and
    selected through the ``TRANSPORT`` environment variable, defaulting to
    ``"websocket"``.
    """

    _factories: dict[str, type["BaseTransport"]] = {}

    def __init_subclass__(
        cls, transport_name: str | None = None, **kwargs
    ) -> None:
        super().__init_subclass__(**kwargs)
        if transport_name:
            cls._factories[transport_name] = cls

    def __init__(self, server: "NotificationServer") -> None:
        self.server = server

    @abc.abstractmethod
    async def on_connect(self, connection) -> None:
        """Drive the full lifecycle of a single client connection."""

    @abc.abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Clean up server state after a client disconnects."""

    @abc.abstractmethod
    async def send_message(self, client_id: str, message: str) -> bool:
        """Deliver a serialized message. Return False if the client is gone."""

    @abc.abstractmethod
    async def broadcast(self, message: str) -> None:
        """Deliver a serialized message to every connected client."""


class WebSocketTransport(BaseTransport, transport_name="websocket"):
    """Transport built on the ``websockets`` library (the default)."""

    async def on_connect(self, websocket) -> None:
        server = self.server
        await server._ensure_listener()
        client_id = server._new_client_id()
        server.registry.add(client_id, websocket)
        await server.connection_store.register(client_id)
        welcome = make_message(
            "system",
            {"client_id": client_id, "message": "connected"},
        )
        try:
            await websocket.send(json.dumps(welcome))
            async for raw in websocket:
                await server._handle_message(client_id, raw)
        except ConnectionClosed:
            pass
        finally:
            await self.on_disconnect(client_id)

    async def on_disconnect(self, client_id: str) -> None:
        server = self.server
        server.registry.remove(client_id)
        server.channels.remove_client(client_id)
        await server._sync_channel_subscriptions()
        await server.connection_store.unregister(client_id)

    async def send_message(self, client_id: str, message: str) -> bool:
        websocket = self.server.registry.get(client_id)
        if websocket is None:
            return False
        try:
            await websocket.send(message)
        except ConnectionClosed:
            return False
        return True

    async def broadcast(self, message: str) -> None:
        for client_id, _ in list(self.server.registry.all()):
            await self.send_message(client_id, message)


def _make_transport(server: "NotificationServer") -> BaseTransport:
    """Build the transport named by the ``TRANSPORT`` env var (default websocket)."""
    name = os.environ.get("TRANSPORT", "websocket").strip().lower()
    try:
        factory = BaseTransport._factories[name]
    except KeyError:
        raise ValueError(
            f"unknown transport: {name!r}; available: "
            + ", ".join(sorted(BaseTransport._factories))
        )
    return factory(server)


# ── Server ──────────────────────────────────────────────────────────

class NotificationServer:
    """Notification server whose client delivery is provided by a transport."""

    def __init__(
        self,
        registry: ClientRegistry | None = None,
        channels: ChannelRegistry | None = None,
        broker: Broker | None = None,
        message_store: MessageStore | None = None,
        connection_store: ConnectionStore | None = None,
        transport: BaseTransport | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.registry = registry or ClientRegistry()
        self.channels = channels or ChannelRegistry()
        self.broker = broker or _make_default_broker()
        self.message_store = message_store or MessageStore()
        self.connection_store = connection_store or ConnectionStore()
        self.transport = transport or _make_transport(self)
        self.rate_limiter = rate_limiter or RateLimiter()
        self.message_ttl_days = _env_int("MESSAGE_TTL_DAYS", DEFAULT_MESSAGE_TTL_DAYS)
        self.cleanup_interval = _env_int(
            "CLEANUP_INTERVAL_SECONDS", DEFAULT_CLEANUP_INTERVAL
        )
        self._listener_task: asyncio.Task | None = None
        self._listener_started = False
        self._cleanup_task: asyncio.Task | None = None
        self._cleanup_started = False

    def start_background_tasks(self) -> None:
        """
        Start server-wide background tasks. Idempotent; typically invoked from
        ``run()`` so the periodic message-expiry cleanup begins at startup.
        """
        if self._cleanup_started:
            return
        self._cleanup_started = True
        self._cleanup_task = asyncio.get_running_loop().create_task(
            self._run_cleanup()
        )

    async def _run_cleanup(self) -> None:
        """Periodically purge messages that outlived their TTL."""
        while True:
            try:
                self.purge_expired_messages()
            except Exception:
                pass
            await asyncio.sleep(max(1, self.cleanup_interval))

    def purge_expired_messages(self) -> int:
        """Delete messages older than ``message_ttl_days``. Returns count."""
        return self.message_store.purge_older_than(self.message_ttl_days)

    async def _ensure_listener(self) -> None:
        """
        Start the broker subscriber task (once). Only needed in Redis mode;
        without a broker messages are delivered inline during publishing.
        """
        if self._listener_started or not self.broker.redis_enabled:
            return
        self._listener_started = True
        await self.broker.subscribe(BROADCAST_CHANNEL)
        self._listener_task = asyncio.get_running_loop().create_task(
            self._run_listener()
        )

    async def _run_listener(self) -> None:
        """Consume messages from the backbone and deliver them locally."""
        while True:
            item = await self.broker.next_message()
            if item is None:
                continue
            channel, data = item
            try:
                json.loads(data)
            except (json.JSONDecodeError, TypeError):
                continue
            if channel == BROADCAST_CHANNEL:
                client_ids = [cid for cid, _ in self.registry.all()]
            else:
                client_ids = self.channels.subscribers(channel)
            await self._deliver(data, client_ids)

    async def _sync_channel_subscriptions(self) -> None:
        """Subscribe the backbone to channels with local subscribers."""
        await self._ensure_listener()
        desired = {BROADCAST_CHANNEL, *self.channels.channels().keys()}
        current = self.broker.channels_subscribed()
        for channel in desired - current:
            await self.broker.subscribe(channel)
        for channel in current - desired:
            await self.broker.unsubscribe(channel)

    def close(self) -> None:
        """Cancel the broker subscriber and cleanup tasks (shutdown)."""
        if self._listener_task is not None and not self._listener_task.done():
            self._listener_task.cancel()
        self._listener_task = None
        if self._cleanup_task is not None and not self._cleanup_task.done():
            self._cleanup_task.cancel()
        self._cleanup_task = None

    async def handler(self, connection) -> None:
        """Handle a single client connection lifecycle via the transport."""
        await self.transport.on_connect(connection)

    def _new_client_id(self) -> str:
        while True:
            candidate = str(uuid.uuid4())
            if self.registry.get(candidate) is None:
                return candidate

    async def _handle_message(self, sender_id: str, raw: str) -> None:
        if not await self.rate_limiter.allow(sender_id):
            await self._send_error(sender_id, "rate limit exceeded")
            return

        try:
            message = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            await self._send_error(sender_id, "message must be valid JSON")
            return

        if not isinstance(message, dict):
            await self._send_error(sender_id, "message must be a JSON object")
            return

        msg_type = message.get("type")
        payload = message.get("payload")
        timestamp = message.get("timestamp") or now_iso()

        if msg_type not in MESSAGE_TYPES:
            await self._send_error(sender_id, f"unsupported message type: {msg_type!r}")
            return
        if not isinstance(payload, dict):
            await self._send_error(sender_id, "payload must be an object")
            return

        if msg_type == "subscribe":
            await self._handle_subscribe(sender_id, payload)
        elif msg_type == "unsubscribe":
            await self._handle_unsubscribe(sender_id, payload)
        elif msg_type == "broadcast":
            channel = message.get("channel") or payload.get("channel")
            await self.broadcast(msg_type, payload, timestamp, channel)
        elif msg_type == "direct":
            await self._handle_direct(sender_id, payload, timestamp)
        elif msg_type == "system":
            await self.transport.send_message(
                sender_id,
                json.dumps(
                    make_message(
                        "system",
                        {"message": "ack", "echo": payload},
                        timestamp,
                    )
                ),
            )

    async def _handle_subscribe(self, sender_id: str, payload: dict) -> None:
        channel = payload.get("channel")
        if not channel or not isinstance(channel, str):
            await self._send_error(sender_id, "subscribe requires payload.channel")
            return
        self.channels.subscribe(channel, sender_id)
        await self.connection_store.add_channel(sender_id, channel)
        await self._sync_channel_subscriptions()
        await self.transport.send_message(
            sender_id,
            json.dumps(
                make_message(
                    "system",
                    {"message": "subscribed", "channel": channel},
                )
            ),
        )

    async def _handle_unsubscribe(self, sender_id: str, payload: dict) -> None:
        channel = payload.get("channel")
        if not channel or not isinstance(channel, str):
            await self._send_error(sender_id, "unsubscribe requires payload.channel")
            return
        self.channels.unsubscribe(channel, sender_id)
        await self.connection_store.remove_channel(sender_id, channel)
        await self._sync_channel_subscriptions()
        await self.transport.send_message(
            sender_id,
            json.dumps(
                make_message(
                    "system",
                    {"message": "unsubscribed", "channel": channel},
                )
            ),
        )

    async def _handle_direct(
        self,
        sender_id: str,
        payload: dict,
        timestamp: str,
    ) -> None:
        target = payload.get("to")
        if not target:
            await self._send_error(sender_id, "direct message requires payload.to")
            return
        if not await self.direct(target, payload, timestamp):
            await self._send_error(sender_id, f"unknown target client: {target}")

    async def _send_error(self, client_id: str, message: str) -> None:
        await self.transport.send_message(
            client_id,
            json.dumps(
                make_message("system", {"message": "error", "error": message})
            ),
        )

    async def _deliver(self, msg: str, client_ids: list[str]) -> None:
        dead: list[str] = []
        for client_id in client_ids:
            if not await self.transport.send_message(client_id, msg):
                dead.append(client_id)
        for client_id in dead:
            self.registry.remove(client_id)
            self.channels.remove_client(client_id)

    async def broadcast(
        self,
        msg_type: str = "broadcast",
        payload: dict | None = None,
        timestamp: str | None = None,
        channel: str | None = None,
    ) -> None:
        """
        Publish a message to the backbone. With Redis every server instance's
        subscriber (including this one) receives it and delivers to its local
        clients; without Redis the message is delivered to local clients inline.
        """
        message = make_message(msg_type, payload or {}, timestamp)
        self.message_store.save(message, channel)
        await self._ensure_listener()
        await self.broker.publish(channel or BROADCAST_CHANNEL, message)
        if not self.broker.redis_enabled:
            data = json.dumps(message)
            if channel:
                await self._deliver(data, self.channels.subscribers(channel))
            else:
                await self._deliver(data, [cid for cid, _ in self.registry.all()])

    async def direct(self, target_id: str, payload: dict, timestamp: str | None = None) -> bool:
        """Send a message to a single client. Returns True if delivered."""
        if self.registry.get(target_id) is None:
            return False
        message = make_message("direct", payload, timestamp)
        self.message_store.save(message, None)
        await self.transport.send_message(target_id, json.dumps(message))
        return True

    async def process_request(
        self,
        connection,
        request: Request,
    ) -> Response | None:
        """Serve REST endpoints over HTTP; upgrade everything else to WS."""
        if request.path == HEALTH_PATH:
            return self._json_response(
                200,
                {"status": "ok", "connected_clients": self.registry.count()},
            )
        if request.path == CHANNELS_PATH:
            channels = [
                {"name": name, "subscribers": count}
                for name, count in sorted(self.channels.channels().items())
            ]
            return self._json_response(200, {"channels": channels})
        if request.path.startswith(CHANNELS_PATH + "/"):
            return self._handle_channel_detail(request.path)
        if request.path == MESSAGES_PATH or request.path.startswith(MESSAGES_PATH + "?"):
            return self._handle_messages(request)
        if request.path == HISTORY_PATH or request.path.startswith(HISTORY_PATH + "?"):
            return self._handle_history(request)
        if request.path in WEBSOCKET_PATHS:
            return None
        return self._json_response(404, {"error": "not found"})

    def _handle_messages(self, request: Request) -> Response:
        parsed = urlparse(request.path)
        if parsed.path != MESSAGES_PATH:
            return self._json_response(404, {"error": "not found"})
        query = parse_qs(parsed.query)
        limit = self._query_int(query, "limit", 50)
        offset = self._query_int(query, "offset", 0)
        return self._json_response(
            200,
            {
                "messages": self.message_store.list(limit, offset),
                "limit": limit,
                "offset": offset,
            },
        )

    def _handle_history(self, request: Request) -> Response:
        parsed = urlparse(request.path)
        if parsed.path != HISTORY_PATH:
            return self._json_response(404, {"error": "not found"})
        query = parse_qs(parsed.query)
        channel = query.get("channel", [None])[0]
        since = query.get("since", [None])[0]
        limit = self._query_int(query, "limit", 50)
        offset = self._query_int(query, "offset", 0)
        messages, has_more = self.message_store.query(
            channel=channel,
            since=since,
            limit=limit,
            offset=offset,
        )
        return self._json_response(
            200,
            {
                "channel": channel,
                "since": since,
                "messages": messages,
                "limit": limit,
                "offset": offset,
                "has_more": has_more,
            },
        )

    @staticmethod
    def _query_int(query: dict, key: str, default: int) -> int:
        try:
            return int(query.get(key, [str(default)])[0])
        except (TypeError, ValueError):
            return default

    def _handle_channel_detail(self, path: str) -> Response:
        parts = path[len(CHANNELS_PATH) + 1:].split("/")
        if len(parts) != 2 or parts[1] != "subscribers":
            return self._json_response(404, {"error": "not found"})
        name = parts[0]
        return self._json_response(
            200,
            {"channel": name, "subscribers": self.channels.subscribers(name)},
        )

    def _json_response(self, status_code: int, body: dict, status_message: str | None = None) -> Response:
        data = json.dumps(body).encode("utf-8")
        headers = Headers(
            {
                "Content-Type": "application/json",
                "Content-Length": str(len(data)),
            }
        )
        if status_message is None:
            status_message = "OK" if status_code == 200 else "Error"
        return Response(status_code, status_message, headers, data)

    async def run(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        """Serve until cancelled."""
        self.start_background_tasks()
        async with websockets.serve(
            self.handler,
            host,
            port,
            process_request=self.process_request,
        ):
            await asyncio.Future()


async def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))
    server = NotificationServer()
    await server.run(host, port)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
