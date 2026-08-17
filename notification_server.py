"""WebSocket-based notification server.

Core features:
- Accept WebSocket connections and assign each client a unique ID.
- Broadcast messages to all connected clients.
- Route ``direct`` messages to a single client.
- Subscribe/unsubscribe clients to named channels.
- Route messages carrying a ``channel`` field only to that channel's
  subscribers.
- Cleanly remove clients on disconnect.
- REST endpoints ``GET /health``, ``GET /channels``,
  ``GET /channels/{name}/subscribers`` and ``GET /messages``.

All messages use the JSON envelope ``{type, payload, timestamp}``.
The websockets transport base64-encodes every frame, so incoming frames are
base64-decoded before JSON parsing and outgoing frames are base64-encoded
before being sent.

Redis pub/sub is used as the message backbone when ``REDIS_URL`` is set (or a
Redis client is injected). The server publishes messages to a Redis channel
and a background worker subscribes to that channel and delivers messages to
locally-connected WebSocket clients. This allows multiple server instances to
share a single Redis backbone, and client connection state is stored in Redis.

All distributed messages are also persisted to SQLite (``DATABASE_URL``) for
history, exposed via ``GET /messages?limit=&offset=``.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sqlite3
import threading
import uuid
from contextlib import closing
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from websockets.asyncio.server import ServerConnection, serve
from websockets.http11 import Headers, Request, Response

SUPPORTED_TYPES = ("broadcast", "direct", "system", "subscribe", "unsubscribe")


def now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def encode_message(message: dict) -> str:
    """Serialize a message to JSON and base64-encode it for the wire."""
    return base64.b64encode(json.dumps(message).encode("utf-8")).decode("ascii")


def decode_message(raw: Any) -> dict:
    """Base64-decode an incoming frame and parse it as JSON."""
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    return json.loads(base64.b64decode(raw).decode("utf-8"))


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
    """Thread-safe registry of connected WebSocket clients."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = threading.Lock()

    def add(self, client_id: str, connection: ServerConnection) -> None:
        with self._lock:
            self._clients[client_id] = connection

    def remove(self, client_id: str) -> Optional[ServerConnection]:
        with self._lock:
            return self._clients.pop(client_id, None)

    def get(self, client_id: str) -> Optional[ServerConnection]:
        with self._lock:
            return self._clients.get(client_id)

    def items(self) -> list[tuple[str, ServerConnection]]:
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
    """WebSocket notification server.

    Optionally backed by Redis pub/sub (``REDIS_URL`` env var or an injected
    client) and SQLite message persistence (``DATABASE_URL`` env var).
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        database_url: Optional[str] = None,
        redis_client: Any = None,
        redis_channel: str = "notifications",
    ) -> None:
        self.registry = ClientRegistry()
        self._subscriptions: dict[str, set[str]] = {}
        self._sub_lock = threading.Lock()
        self.server_id = str(uuid.uuid4())
        self.store = MessageStore(database_url)
        self.bus: Optional[RedisBus] = None
        if redis_client is not None or redis_url or os.environ.get("REDIS_URL"):
            self.bus = RedisBus(
                redis_url=redis_url,
                channel=redis_channel,
                client=redis_client,
            )
        self._worker_task: Optional[asyncio.Task] = None
        self._pubsub: Any = None

    # ── Lifecycle ────────────────────────────────────────────────

    async def start(self) -> None:
        """Subscribe to the Redis backbone and start the delivery worker."""
        if self.bus is not None and self._worker_task is None:
            self._pubsub = await self.bus.subscribe()
            self._worker_task = asyncio.create_task(self._run_worker(self._pubsub))

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

    async def handler(self, connection: ServerConnection) -> None:
        """Handle a single client connection for its full lifetime."""
        client_id = str(uuid.uuid4())
        self.registry.add(client_id, connection)
        if self.bus is not None:
            await self.bus.register_client(client_id, self.server_id)
        try:
            connected = {
                "type": "system",
                "payload": {"event": "connected", "client_id": client_id},
                "timestamp": now_iso(),
            }
            await connection.send(encode_message(connected))

            async for raw in connection:
                try:
                    message = decode_message(raw)
                except (ValueError, TypeError, json.JSONDecodeError, base64.binascii.Error):
                    continue
                await self.route_message(client_id, message)
        finally:
            self.registry.remove(client_id)
            self.remove_client(client_id)
            if self.bus is not None:
                await self.bus.unregister_client(client_id)

    async def route_message(self, sender_id: str, message: dict) -> None:
        """Route an inbound message based on its type."""
        mtype = message.get("type")
        if not isinstance(message, dict) or mtype not in SUPPORTED_TYPES:
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
        encoded = encode_message(message)
        for client_id, connection in self.registry.items():
            try:
                await connection.send(encoded)
            except Exception:
                self.registry.remove(client_id)

    async def send_to_channel(self, channel: str, message: dict) -> None:
        """Send a message only to subscribers of the given channel."""
        encoded = encode_message(message)
        for client_id in self.channel_subscribers(channel):
            connection = self.registry.get(client_id)
            if connection is None:
                self.unsubscribe(client_id, channel)
                continue
            try:
                await connection.send(encoded)
            except Exception:
                self.registry.remove(client_id)
                self.unsubscribe(client_id, channel)

    async def send_to(self, target_id: str, message: dict) -> bool:
        """Send a message to a single client. Returns True if delivered."""
        connection = self.registry.get(target_id)
        if connection is None:
            return False
        await connection.send(encode_message(message))
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
