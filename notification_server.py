"""Pluggable notification server.

Core features:
- Accept client connections and assign each client a unique ID.
- Broadcast messages to all connected clients.
- Route ``direct`` messages to a single client.
- Subscribe/unsubscribe clients to named channels.
- Route messages carrying a ``channel`` field only to that channel's
  subscribers.
- Cleanly remove clients on disconnect.
- REST endpoints ``GET /health``, ``GET /channels``,
  ``GET /channels/{name}/subscribers`` and ``GET /messages``.

All messages use the JSON envelope ``{type, payload, timestamp}``.

The connection layer is pluggable: the core server delegates all
connection-level work to a :class:`~transports.BaseTransport` implementation.
The active transport is selected via the ``TRANSPORT`` environment variable
(or an explicit argument) and defaults to the WebSocket transport, which
base64-encodes every frame. Incoming frames are base64-decoded before JSON
parsing and outgoing frames are base64-encoded before being sent.

Redis pub/sub is used as the message backbone when ``REDIS_URL`` is set (or a
Redis client is injected). The server publishes messages to a Redis channel
and a background worker subscribes to that channel and delivers messages to
locally-connected clients. This allows multiple server instances to share a
single Redis backbone, and client connection state is stored in Redis.

All distributed messages are also persisted to SQLite (``DATABASE_URL``) for
history, exposed via ``GET /messages?limit=&offset=``.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from websockets.asyncio.server import ServerConnection, serve
from websockets.http11 import Headers, Request, Response

from transports import (
    BaseTransport,
    WebSocketTransport,
    create_transport,
    decode_message,
    encode_message,
    now_iso,
)

SUPPORTED_TYPES = ("broadcast", "direct", "system", "subscribe", "unsubscribe")

CLEANUP_INTERVAL_SECONDS = 3600

__all__ = [
    "NotificationServer",
    "ClientRegistry",
    "RedisBus",
    "RateLimiter",
    "MessageStore",
    "encode_message",
    "decode_message",
    "now_iso",
    "BaseTransport",
    "WebSocketTransport",
    "SUPPORTED_TYPES",
]


def _int_env(name: str, default: int) -> int:
    """Read an integer environment variable, falling back to ``default``."""
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _normalize_database_url(url: str) -> str:
    """Strip a ``sqlite:///`` prefix from a database URL, if present."""
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    if url.startswith("sqlite://"):
        return url[len("sqlite://"):]
    return url


class MessageStore:
    """SQLite-backed history of distributed messages."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        self.database_url = _normalize_database_url(
            database_url or os.environ.get("DATABASE_URL", "messages.db")
        )
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_url, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS messages ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  channel TEXT,"
                "  type TEXT,"
                "  payload TEXT,"
                "  timestamp TEXT"
                ")"
            )
            conn.commit()

    def save(
        self,
        channel: Optional[str],
        mtype: str,
        payload: Any,
        timestamp: str,
    ) -> int:
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp)"
                " VALUES (?, ?, ?, ?)",
                (channel, mtype, json.dumps(payload), timestamp),
            )
            conn.commit()
            return cursor.lastrowid

    def list_messages(self, limit: int = 50, offset: int = 0) -> list[dict]:
        try:
            limit = max(0, int(limit))
        except (TypeError, ValueError):
            limit = 50
        try:
            offset = max(0, int(offset))
        except (TypeError, ValueError):
            offset = 0
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages"
                " ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "channel": row["channel"],
                "type": row["type"],
                "payload": json.loads(row["payload"]) if row["payload"] else None,
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    def query_history(
        self,
        channel: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 50,
    ) -> tuple[list[dict], bool]:
        """Return messages for a channel/time range in chronological order.

        Returns a ``(messages, has_more)`` tuple. ``messages`` are ordered by
        timestamp ascending (then id ascending). ``has_more`` is ``True`` when
        more than ``limit`` messages match the query.
        """
        try:
            limit = max(0, int(limit))
        except (TypeError, ValueError):
            limit = 50

        conditions: list[str] = []
        params: list[Any] = []
        if channel:
            conditions.append("channel = ?")
            params.append(channel)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages"
                f"{where} ORDER BY timestamp ASC, id ASC LIMIT ?",
                (*params, limit + 1),
            ).fetchall()

        has_more = len(rows) > limit
        rows = rows[:limit]
        messages = [
            {
                "id": row["id"],
                "channel": row["channel"],
                "type": row["type"],
                "payload": json.loads(row["payload"]) if row["payload"] else None,
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]
        return messages, has_more

    def delete_older_than(self, ttl_days: int) -> int:
        """Delete messages older than ``ttl_days`` days. Returns count deleted."""
        try:
            ttl_days = max(0, int(ttl_days))
        except (TypeError, ValueError):
            ttl_days = 7
        cutoff = (datetime.now(timezone.utc) - timedelta(days=ttl_days)).isoformat()
        with closing(self._connect()) as conn:
            cursor = conn.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff,))
            conn.commit()
            return cursor.rowcount


class RateLimiter:
    """Fixed-window rate limiter keyed by client ID.

    Uses Redis counters (``INCR`` + ``EXPIRE``) when a Redis client is
    supplied; otherwise falls back to in-memory counters so the server keeps
    working without a Redis backbone.
    """

    KEY_PREFIX = "notifications:ratelimit:"

    def __init__(
        self,
        limit: Any = 100,
        window_seconds: Any = 60,
    ) -> None:
        try:
            self.limit = max(1, int(limit))
        except (TypeError, ValueError):
            self.limit = 100
        try:
            self.window_seconds = max(1, int(window_seconds))
        except (TypeError, ValueError):
            self.window_seconds = 60
        self._local: dict[str, list[float]] = {}

    async def allow(self, client_id: str, redis_client: Any = None) -> bool:
        """Return ``True`` if the client may send another message."""
        if redis_client is None:
            return self._allow_local(client_id)
        key = self.KEY_PREFIX + client_id
        try:
            count = await redis_client.incr(key)
            if count == 1:
                await redis_client.expire(key, self.window_seconds)
        except Exception:
            return self._allow_local(client_id)
        return count <= self.limit

    def _allow_local(self, client_id: str) -> bool:
        now = time.monotonic()
        stamps = self._local.setdefault(client_id, [])
        stamps[:] = [t for t in stamps if now - t < self.window_seconds]
        if len(stamps) >= self.limit:
            return False
        stamps.append(now)
        return True


class RedisBus:
    """Redis pub/sub backbone used for cross-instance message distribution."""

    CLIENT_KEY_PREFIX = "notifications:client:"
    CLIENTS_SET = "notifications:clients"

    def __init__(
        self,
        redis_url: Optional[str] = None,
        channel: str = "notifications",
        client: Any = None,
    ) -> None:
        self.redis_url = redis_url or os.environ.get("REDIS_URL")
        self.channel = channel
        self._client = client

    async def _get_client(self) -> Any:
        if self._client is None:
            import redis.asyncio as aioredis

            self._client = aioredis.from_url(self.redis_url, decode_responses=True)
        return self._client

    async def publish(self, message: dict) -> None:
        client = await self._get_client()
        await client.publish(self.channel, json.dumps(message))

    async def subscribe(self) -> Any:
        client = await self._get_client()
        pubsub = client.pubsub()
        await pubsub.subscribe(self.channel)
        return pubsub

    async def register_client(self, client_id: str, server_id: str) -> None:
        client = await self._get_client()
        await client.set(
            self.CLIENT_KEY_PREFIX + client_id,
            json.dumps({"client_id": client_id, "server_id": server_id}),
        )
        await client.sadd(self.CLIENTS_SET, client_id)

    async def unregister_client(self, client_id: str) -> None:
        client = await self._get_client()
        await client.delete(self.CLIENT_KEY_PREFIX + client_id)
        await client.srem(self.CLIENTS_SET, client_id)

    async def connected_clients(self) -> set[str]:
        client = await self._get_client()
        return await client.smembers(self.CLIENTS_SET)


class ClientRegistry:
    """Thread-safe registry of connected clients."""

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._lock = threading.Lock()

    def add(self, client_id: str, connection: Any) -> None:
        with self._lock:
            self._clients[client_id] = connection

    def remove(self, client_id: str) -> Optional[Any]:
        with self._lock:
            return self._clients.pop(client_id, None)

    def get(self, client_id: str) -> Optional[Any]:
        with self._lock:
            return self._clients.get(client_id)

    def items(self) -> list[tuple[str, Any]]:
        with self._lock:
            return list(self._clients.items())

    def ids(self) -> list[str]:
        with self._lock:
            return list(self._clients.keys())

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)

    def __contains__(self, client_id: str) -> bool:
        with self._lock:
            return client_id in self._clients


class NotificationServer:
    """Notification server with a pluggable transport layer.

    The transport is selected via the ``TRANSPORT`` environment variable (or
    an explicit ``transport`` argument) and defaults to WebSocket. Optionally
    backed by Redis pub/sub (``REDIS_URL`` env var or an injected client) and
    SQLite message persistence (``DATABASE_URL`` env var).
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        database_url: Optional[str] = None,
        redis_client: Any = None,
        redis_channel: str = "notifications",
        transport: Optional[str] = None,
        rate_limit: Any = None,
        message_ttl_days: Any = None,
    ) -> None:
        self.registry = ClientRegistry()
        self._subscriptions: dict[str, set[str]] = {}
        self._sub_lock = threading.Lock()
        self.server_id = str(uuid.uuid4())
        self.store = MessageStore(database_url)
        self.rate_limit = (
            rate_limit if rate_limit is not None else _int_env("RATE_LIMIT", 100)
        )
        self.rate_limiter = RateLimiter(self.rate_limit)
        self.message_ttl_days = (
            message_ttl_days
            if message_ttl_days is not None
            else _int_env("MESSAGE_TTL_DAYS", 7)
        )
        self.bus: Optional[RedisBus] = None
        if redis_client is not None or redis_url or os.environ.get("REDIS_URL"):
            self.bus = RedisBus(
                redis_url=redis_url,
                channel=redis_channel,
                client=redis_client,
            )
        self._worker_task: Optional[asyncio.Task] = None
        self._pubsub: Any = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self.transport: BaseTransport = create_transport(transport, self)

    # ── Lifecycle ────────────────────────────────────────────────

    async def start(self) -> None:
        """Subscribe to the Redis backbone and start the delivery worker."""
        if self.bus is not None and self._worker_task is None:
            self._pubsub = await self.bus.subscribe()
            self._worker_task = asyncio.create_task(self._run_worker(self._pubsub))
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """Stop the delivery worker and close the pub/sub subscription."""
        task = self._worker_task
        self._worker_task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._pubsub = None
        cleanup_task = self._cleanup_task
        self._cleanup_task = None
        if cleanup_task is not None:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except (asyncio.CancelledError, Exception):
                pass

    async def cleanup(self) -> int:
        """Delete messages older than the configured TTL. Returns count removed."""
        if self.store is None:
            return 0
        return await asyncio.to_thread(
            self.store.delete_older_than, self.message_ttl_days
        )

    async def _cleanup_loop(self) -> None:
        """Background task: clean expired messages, then periodically repeat."""
        while True:
            try:
                await self.cleanup()
            except Exception:
                pass
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)

    async def _run_worker(self, pubsub: Any) -> None:
        """Consume messages from Redis and deliver them to local clients."""
        try:
            async for message in pubsub.listen():
                if message.get("type") == "message":
                    try:
                        envelope = json.loads(message["data"])
                    except (TypeError, ValueError):
                        continue
                    await self._deliver(envelope)
        except asyncio.CancelledError:
            raise
        finally:
            try:
                await pubsub.unsubscribe(self.bus.channel)
            except Exception:
                pass
            try:
                await pubsub.aclose()
            except Exception:
                pass

    async def _deliver(self, message: dict) -> None:
        """Deliver a message received from the backbone to local clients."""
        mtype = message.get("type")
        channel = self._channel_of(message)
        if mtype == "direct":
            payload = message.get("payload") or {}
            target_id = payload.get("to") or payload.get("client_id")
            if target_id and target_id in self.registry:
                await self.send_to(target_id, message)
            return
        if channel:
            await self.send_to_channel(channel, message)
        elif mtype in ("broadcast", "system"):
            await self.broadcast(message)

    def _persist(self, channel: Optional[str], message: dict) -> None:
        """Store a distributed message in SQLite history."""
        if self.store is None:
            return
        self.store.save(
            channel=channel,
            mtype=message.get("type"),
            payload=message.get("payload"),
            timestamp=message.get("timestamp"),
        )

    # ── Channel subscription bookkeeping ─────────────────────────

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._sub_lock:
            self._subscriptions.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._sub_lock:
            subscribers = self._subscriptions.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                self._subscriptions.pop(channel, None)

    def remove_client(self, client_id: str) -> None:
        """Drop a client from every channel (used on disconnect)."""
        with self._sub_lock:
            for channel in list(self._subscriptions):
                subscribers = self._subscriptions[channel]
                subscribers.discard(client_id)
                if not subscribers:
                    self._subscriptions.pop(channel, None)

    def channel_subscribers(self, channel: str) -> list[str]:
        with self._sub_lock:
            return sorted(self._subscriptions.get(channel, set()))

    def channels(self) -> dict[str, int]:
        """Return active channels mapped to their subscriber counts."""
        with self._sub_lock:
            return {
                channel: len(subscribers)
                for channel, subscribers in self._subscriptions.items()
            }

    @staticmethod
    def _channel_of(message: dict) -> Optional[str]:
        """Extract a channel name from a message (top-level or payload)."""
        channel = message.get("channel")
        if channel is None:
            payload = message.get("payload")
            if isinstance(payload, dict):
                channel = payload.get("channel")
        if isinstance(channel, str) and channel:
            return channel
        return None

    async def _check_rate_limit(self, client_id: str) -> bool:
        """Return ``True`` if the client is allowed to send another message."""
        if self.rate_limiter is None:
            return True
        redis_client = None
        if self.bus is not None:
            try:
                redis_client = await self.bus._get_client()
            except Exception:
                redis_client = None
        return await self.rate_limiter.allow(client_id, redis_client)

    async def handler(self, connection: Any) -> None:
        """Handle a single client connection via the active transport."""
        await self.transport.handle(connection)

    async def route_message(self, sender_id: str, message: dict) -> None:
        """Route an inbound message based on its type."""
        mtype = message.get("type")
        if not isinstance(message, dict) or mtype not in SUPPORTED_TYPES:
            return

        if not await self._check_rate_limit(sender_id):
            await self.send_to(
                sender_id,
                {
                    "type": "error",
                    "payload": {
                        "error": "rate limit exceeded",
                        "code": "rate_limited",
                    },
                    "timestamp": now_iso(),
                },
            )
            return

        message.setdefault("timestamp", now_iso())

        if mtype == "subscribe":
            channel = self._channel_of(message)
            if channel:
                self.subscribe(sender_id, channel)
            return
        if mtype == "unsubscribe":
            channel = self._channel_of(message)
            if channel:
                self.unsubscribe(sender_id, channel)
            return

        channel = self._channel_of(message)
        self._persist(channel, message)

        if self.bus is not None:
            await self.bus.publish(message)
            return

        if channel:
            await self.send_to_channel(channel, message)
        elif mtype == "broadcast":
            await self.broadcast(message)
        elif mtype == "direct":
            payload = message.get("payload") or {}
            target_id = payload.get("to") or payload.get("client_id")
            if target_id:
                await self.send_to(target_id, message)
        elif mtype == "system":
            await self.broadcast(message)

    async def broadcast(self, message: dict) -> None:
        """Send a message to every connected client."""
        await self.transport.broadcast(message)

    async def send_to_channel(self, channel: str, message: dict) -> None:
        """Send a message only to subscribers of the given channel."""
        for client_id in self.channel_subscribers(channel):
            connection = self.registry.get(client_id)
            if connection is None:
                self.unsubscribe(client_id, channel)
                continue
            try:
                await self.transport.send_message(connection, message)
            except Exception:
                self.registry.remove(client_id)
                self.unsubscribe(client_id, channel)

    async def send_to(self, target_id: str, message: dict) -> bool:
        """Send a message to a single client. Returns True if delivered."""
        connection = self.registry.get(target_id)
        if connection is None:
            return False
        await self.transport.send_message(connection, message)
        return True

    def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Optional[Response]:
        """Serve the REST endpoints."""
        parsed = urlparse(request.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/health":
            body = json.dumps({"connected_clients": len(self.registry)}).encode("utf-8")
            headers = Headers([("Content-Type", "application/json")])
            return Response(200, "OK", headers, body)

        if path == "/channels":
            body = json.dumps(self.channels()).encode("utf-8")
            headers = Headers([("Content-Type", "application/json")])
            return Response(200, "OK", headers, body)

        if path == "/messages":
            limit = query.get("limit", ["50"])[0]
            offset = query.get("offset", ["0"])[0]
            body = json.dumps(self.store.list_messages(limit, offset)).encode("utf-8")
            headers = Headers([("Content-Type", "application/json")])
            return Response(200, "OK", headers, body)

        if path == "/history":
            channel = query.get("channel", [None])[0]
            since = query.get("since", [None])[0]
            limit = query.get("limit", ["50"])[0]
            messages, has_more = self.store.query_history(channel, since, limit)
            body = json.dumps(
                {"messages": messages, "has_more": has_more}
            ).encode("utf-8")
            headers = Headers([("Content-Type", "application/json")])
            return Response(200, "OK", headers, body)

        prefix = "/channels/"
        suffix = "/subscribers"
        if path.startswith(prefix) and path.endswith(suffix):
            name = path[len(prefix):-len(suffix)]
            if name:
                body = json.dumps(self.channel_subscribers(name)).encode("utf-8")
                headers = Headers([("Content-Type", "application/json")])
                return Response(200, "OK", headers, body)

        return None


async def main(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = NotificationServer()
    await server.start()
    try:
        async with serve(
            server.handler, host, port, process_request=server.process_request
        ):
            await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
