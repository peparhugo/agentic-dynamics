"""WebSocket notification server with a small HTTP health API."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from flask import Flask, jsonify, request
import redis
from websockets.asyncio.server import Server, ServerConnection, serve


app = Flask(__name__)

# This is the only lock used for the registry. Never perform socket I/O while
# holding it: a slow client must not block connects, disconnects, or health.
clients_lock = threading.Lock()
clients: dict[str, ServerConnection] = {}
channels: dict[str, set[str]] = {}

SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
REDIS_MESSAGE_CHANNEL = "notifications:messages"
REDIS_CLIENTS_KEY = "notifications:clients"
REDIS_CHANNELS_KEY = "notifications:channels"
REDIS_RATE_LIMIT_PREFIX = "notifications:rate-limit"


def database_path(database_url: str | None = None) -> str:
    url = database_url or os.getenv("DATABASE_URL", "sqlite:///messages.db")
    if url == "sqlite:///:memory:":
        return ":memory:"
    parsed = urlparse(url)
    if parsed.scheme != "sqlite":
        raise ValueError("DATABASE_URL must be a SQLite URL")
    if parsed.netloc:
        return unquote(f"//{parsed.netloc}{parsed.path}")
    path = unquote(parsed.path)
    if path.startswith("//"):
        return path[1:]
    return path.lstrip("/")


class MessageStore:
    """SQLite-backed message history, safe to use from multiple threads."""

    def __init__(self, database_url: str | None = None) -> None:
        self.path = database_path(database_url)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._connection:
            self._connection.execute(
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

    def save(self, message: dict[str, Any]) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                INSERT INTO messages (channel, type, payload, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (
                    message.get("channel"),
                    message["type"],
                    json.dumps(message["payload"], separators=(",", ":")),
                    message["timestamp"],
                ),
            )
            return int(cursor.lastrowid)

    def list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT id, channel, type, payload, timestamp
                FROM messages ORDER BY id DESC LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "channel": row["channel"],
                "type": row["type"],
                "payload": json.loads(row["payload"]),
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    def history(
        self, channel: str, since: datetime, limit: int
    ) -> tuple[list[dict[str, Any]], bool]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT id, channel, type, payload, timestamp
                FROM messages
                WHERE channel = ? AND julianday(timestamp) >= julianday(?)
                ORDER BY julianday(timestamp) ASC, id ASC
                LIMIT ?
                """,
                (channel, since.isoformat(), limit + 1),
            ).fetchall()
        messages = [self._row_to_message(row) for row in rows[:limit]]
        return messages, len(rows) > limit

    def delete_older_than(self, cutoff: datetime) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "DELETE FROM messages WHERE julianday(timestamp) < julianday(?)",
                (cutoff.isoformat(),),
            )
            return cursor.rowcount

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "channel": row["channel"],
            "type": row["type"],
            "payload": json.loads(row["payload"]),
            "timestamp": row["timestamp"],
        }

    def close(self) -> None:
        with self._lock:
            self._connection.close()


class RedisConnectionState:
    """Persistent connection metadata shared by all server instances."""

    def __init__(self, client: redis.Redis) -> None:
        self.client = client

    def connect(self, client_id: str, server_id: str) -> None:
        self.client.hset(REDIS_CLIENTS_KEY, client_id, server_id)

    def disconnect(self, client_id: str) -> None:
        channel_names = self.client.smembers(REDIS_CHANNELS_KEY)
        pipeline = self.client.pipeline()
        pipeline.hdel(REDIS_CLIENTS_KEY, client_id)
        for channel in channel_names:
            pipeline.srem(self._channel_key(channel), client_id)
        pipeline.execute()
        for channel in channel_names:
            key = self._channel_key(channel)
            if not self.client.exists(key):
                self.client.srem(REDIS_CHANNELS_KEY, channel)

    def subscribe(self, client_id: str, channel: str) -> None:
        pipeline = self.client.pipeline()
        pipeline.sadd(REDIS_CHANNELS_KEY, channel)
        pipeline.sadd(self._channel_key(channel), client_id)
        pipeline.execute()

    def has_client(self, client_id: str) -> bool:
        return bool(self.client.hexists(REDIS_CLIENTS_KEY, client_id))

    def unsubscribe(self, client_id: str, channel: str) -> None:
        key = self._channel_key(channel)
        self.client.srem(key, client_id)
        if not self.client.exists(key):
            self.client.srem(REDIS_CHANNELS_KEY, channel)

    @staticmethod
    def _channel_key(channel: str | bytes) -> str:
        if isinstance(channel, bytes):
            channel = channel.decode()
        return f"notifications:channel:{channel}:clients"


class RedisBroker:
    """Redis publisher and pub/sub consumer used as the delivery backbone."""

    def __init__(self, client: redis.Redis) -> None:
        self.client = client

    @classmethod
    def from_url(cls, url: str) -> "RedisBroker":
        return cls(redis.Redis.from_url(url, decode_responses=True))

    def publish(self, envelope: dict[str, Any]) -> None:
        self.client.publish(REDIS_MESSAGE_CHANNEL, encode_message(envelope))

    def pubsub(self):
        return self.client.pubsub(ignore_subscribe_messages=True)


class RedisRateLimiter:
    """Fixed-window per-client message limiter backed by Redis counters."""

    def __init__(self, client: redis.Redis, limit: int) -> None:
        self.client = client
        self.limit = limit

    def allow(self, client_id: str) -> bool:
        minute = int(time.time() // 60)
        key = f"{REDIS_RATE_LIMIT_PREFIX}:{client_id}:{minute}"
        pipeline = self.client.pipeline()
        pipeline.incr(key)
        pipeline.expire(key, 120)
        count, _ = pipeline.execute()
        return int(count) <= self.limit


_message_store: MessageStore | None = None
_message_store_url: str | None = None
_message_store_lock = threading.Lock()


def get_message_store() -> MessageStore:
    global _message_store, _message_store_url
    url = os.getenv("DATABASE_URL", "sqlite:///messages.db")
    with _message_store_lock:
        if _message_store is None or _message_store_url != url:
            if _message_store is not None:
                _message_store.close()
            _message_store = MessageStore(url)
            _message_store_url = url
        return _message_store


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_message(
    message_type: str, payload: dict[str, Any], channel: str | None = None
) -> dict[str, Any]:
    message = {
        "type": message_type,
        "payload": payload,
        "timestamp": utc_timestamp(),
    }
    if channel is not None:
        message["channel"] = channel
    return message


def encode_message(message: dict[str, Any]) -> str:
    return json.dumps(message, separators=(",", ":"))


def validate_message(value: Any) -> str | None:
    if not isinstance(value, dict):
        return "message must be a JSON object"
    required_fields = {"type", "payload", "timestamp"}
    allowed_fields = required_fields | {"channel"}
    if not required_fields.issubset(value) or not set(value).issubset(allowed_fields):
        return "message must contain type, payload, timestamp, and optionally channel"
    if value["type"] not in SUPPORTED_TYPES:
        return "unsupported message type"
    if not isinstance(value["payload"], dict):
        return "payload must be an object"
    if not isinstance(value["timestamp"], str):
        return "timestamp must be a string"
    if "channel" in value and (
        not isinstance(value["channel"], str) or not value["channel"]
    ):
        return "channel must be a non-empty string"
    if value["type"] in {"subscribe", "unsubscribe"} and "channel" not in value:
        return f'{value["type"]} message requires channel'
    return None


def client_count() -> int:
    with clients_lock:
        return len(clients)


def _add_client(client_id: str, websocket: ServerConnection) -> None:
    with clients_lock:
        clients[client_id] = websocket


def _remove_client(client_id: str, websocket: ServerConnection) -> None:
    with clients_lock:
        if clients.get(client_id) is websocket:
            del clients[client_id]
            for channel in list(channels):
                channels[channel].discard(client_id)
                if not channels[channel]:
                    del channels[channel]


def _client_snapshot() -> list[tuple[str, ServerConnection]]:
    with clients_lock:
        return list(clients.items())


def _channel_snapshot(channel: str) -> list[tuple[str, ServerConnection]]:
    with clients_lock:
        return [
            (client_id, clients[client_id])
            for client_id in channels.get(channel, set())
            if client_id in clients
        ]


def _set_subscription(client_id: str, channel: str, subscribed: bool) -> None:
    with clients_lock:
        if subscribed:
            channels.setdefault(channel, set()).add(client_id)
        elif channel in channels:
            channels[channel].discard(client_id)
            if not channels[channel]:
                del channels[channel]


async def _send(websocket: ServerConnection, message: dict[str, Any]) -> None:
    await websocket.send(encode_message(message))


async def broadcast(message: dict[str, Any]) -> None:
    """Send a valid message to all clients, or one channel's subscribers."""
    error = validate_message(message)
    if error:
        raise ValueError(error)

    channel = message.get("channel")
    snapshot = _channel_snapshot(channel) if channel is not None else _client_snapshot()
    if not snapshot:
        return

    results = await asyncio.gather(
        *(_send(websocket, message) for _, websocket in snapshot),
        return_exceptions=True,
    )
    for (client_id, websocket), result in zip(snapshot, results):
        if isinstance(result, BaseException):
            _remove_client(client_id, websocket)


async def send_direct(client_id: str, message: dict[str, Any]) -> bool:
    """Send to one client, taking the socket reference under the registry lock."""
    with clients_lock:
        websocket = clients.get(client_id)
        channel = message.get("channel")
        is_subscribed = channel is None or client_id in channels.get(channel, set())
    if websocket is None:
        return False
    if not is_subscribed:
        return True
    try:
        await _send(websocket, message)
    except Exception:
        _remove_client(client_id, websocket)
        return False
    return True


async def _send_error(websocket: ServerConnection, detail: str) -> None:
    await _send(websocket, make_message("system", {"error": detail}))


async def websocket_handler(websocket: ServerConnection) -> None:
    client_id = str(uuid.uuid4())
    _add_client(client_id, websocket)
    try:
        await _send(
            websocket,
            make_message("system", {"event": "connected", "client_id": client_id}),
        )
        async for raw_message in websocket:
            try:
                message = json.loads(raw_message)
            except (json.JSONDecodeError, TypeError):
                await _send_error(websocket, "invalid JSON")
                continue

            error = validate_message(message)
            if error:
                await _send_error(websocket, error)
                continue

            if message["type"] == "subscribe":
                _set_subscription(client_id, message["channel"], True)
            elif message["type"] == "unsubscribe":
                _set_subscription(client_id, message["channel"], False)
            elif message["type"] == "broadcast":
                await broadcast(message)
            elif message["type"] == "direct":
                recipient = message["payload"].get("client_id")
                if not isinstance(recipient, str) or not recipient:
                    await _send_error(websocket, "direct payload requires client_id")
                elif not await send_direct(recipient, message):
                    await _send_error(websocket, "client not found")
            else:
                await _send_error(websocket, "system messages are server-only")
    finally:
        _remove_client(client_id, websocket)


@app.get("/health")
def health():
    return jsonify({"connected_clients": client_count()})


@app.get("/channels")
def list_channels():
    with clients_lock:
        result = [
            {"name": name, "subscriber_count": len(subscribers)}
            for name, subscribers in sorted(channels.items())
        ]
    return jsonify({"channels": result})


@app.get("/channels/<name>/subscribers")
def list_channel_subscribers(name: str):
    with clients_lock:
        subscribers = sorted(channels.get(name, set()))
    return jsonify({"channel": name, "subscribers": subscribers})


@app.get("/messages")
def list_messages():
    try:
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return jsonify({"error": "limit and offset must be integers"}), 400
    if not 1 <= limit <= 1000 or offset < 0:
        return jsonify({"error": "limit must be 1-1000 and offset must be non-negative"}), 400
    return jsonify({"messages": get_message_store().list(limit, offset)})


@app.get("/history")
def message_history():
    channel = request.args.get("channel", "").strip()
    since_value = request.args.get("since", "")
    if not channel or not since_value:
        return jsonify({"error": "channel and since are required"}), 400
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400
    if not 1 <= limit <= 1000:
        return jsonify({"error": "limit must be 1-1000"}), 400
    try:
        since = datetime.fromisoformat(since_value.replace("Z", "+00:00"))
    except ValueError:
        return jsonify({"error": "since must be an ISO timestamp"}), 400
    if since.tzinfo is None:
        return jsonify({"error": "since must include a timezone"}), 400
    messages, has_more = get_message_store().history(channel, since, limit)
    return jsonify({"messages": messages, "has_more": has_more})


class BaseTransport(ABC):
    """Connection and delivery boundary used by the notification server."""

    def __init__(self) -> None:
        self.notification_server: NotificationServer | None = None

    def bind(self, server: NotificationServer) -> None:
        self.notification_server = server

    async def start(self, host: str, port: int) -> int:
        """Start accepting clients and return the bound port."""
        raise NotImplementedError

    async def stop(self) -> None:
        """Stop accepting clients and close transport resources."""
        raise NotImplementedError

    @abstractmethod
    async def on_connect(self, connection: Any) -> str:
        """Register a connection and return its client identifier."""

    @abstractmethod
    async def on_disconnect(self, client_id: str, connection: Any) -> None:
        """Remove a connection and its transport state."""

    @abstractmethod
    async def send_message(self, client_id: str, message: dict[str, Any]) -> bool:
        """Send a message to one connected client."""

    @abstractmethod
    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a message to all applicable connected clients."""

    def subscribe(self, client_id: str, channel: str) -> None:
        """Record transport-specific channel membership when needed."""

    def unsubscribe(self, client_id: str, channel: str) -> None:
        """Remove transport-specific channel membership when needed."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport contract."""

    def __init__(self) -> None:
        super().__init__()
        self.clients: dict[str, ServerConnection] = {}
        self.channels: dict[str, set[str]] = {}
        self.server: Server | None = None

    async def start(self, host: str, port: int) -> int:
        self.server = await serve(self._handler, host, port)
        sockets = self.server.sockets
        return sockets[0].getsockname()[1] if sockets else port

    async def stop(self) -> None:
        if self.server is None:
            return
        self.server.close()
        await self.server.wait_closed()
        self.server = None

    async def on_connect(self, connection: ServerConnection) -> str:
        client_id = str(uuid.uuid4())
        self.clients[client_id] = connection
        _add_client(client_id, connection)
        return client_id

    async def on_disconnect(
        self, client_id: str, connection: ServerConnection
    ) -> None:
        _remove_client(client_id, connection)
        if self.clients.get(client_id) is connection:
            del self.clients[client_id]
            for channel in list(self.channels):
                self.channels[channel].discard(client_id)
                if not self.channels[channel]:
                    del self.channels[channel]

    async def send_message(self, client_id: str, message: dict[str, Any]) -> bool:
        connection = self.clients.get(client_id)
        if connection is None:
            return False
        channel = message.get("channel")
        if channel is not None and client_id not in self.channels.get(channel, set()):
            return True
        try:
            await _send(connection, message)
        except Exception:
            await self.on_disconnect(client_id, connection)
            return False
        return True

    async def broadcast(self, message: dict[str, Any]) -> None:
        channel = message.get("channel")
        client_ids = (
            list(self.clients)
            if channel is None
            else list(self.channels.get(channel, set()))
        )
        if client_ids:
            await asyncio.gather(
                *(self.send_message(client_id, message) for client_id in client_ids)
            )

    def subscribe(self, client_id: str, channel: str) -> None:
        self.channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        if channel not in self.channels:
            return
        self.channels[channel].discard(client_id)
        if not self.channels[channel]:
            del self.channels[channel]

    async def _handler(self, connection: ServerConnection) -> None:
        if self.notification_server is None:
            raise RuntimeError("transport is not bound to a notification server")
        client_id = await self.on_connect(connection)
        await self.notification_server._on_connect(client_id)
        try:
            await self.send_message(
                client_id,
                make_message("system", {"event": "connected", "client_id": client_id}),
            )
            async for raw_message in connection:
                await self.notification_server._on_message(client_id, raw_message)
        finally:
            await self.on_disconnect(client_id, connection)
            await self.notification_server._on_disconnect(client_id)


def create_transport(name: str | None = None) -> BaseTransport:
    """Create the configured transport, defaulting to WebSockets."""
    transport_name = (name or os.getenv("TRANSPORT", "websocket")).strip().lower()
    if transport_name in {"websocket", "websockets", "ws"}:
        return WebSocketTransport()
    raise ValueError(f"unsupported transport: {transport_name}")


class NotificationServer:
    """Run transport-independent notification logic in a daemon thread."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        *,
        redis_url: str | None = None,
        redis_client: redis.Redis | None = None,
        message_store: MessageStore | None = None,
        transport: BaseTransport | None = None,
        rate_limit: int | None = None,
        message_ttl_days: int | None = None,
    ) -> None:
        self.host = host
        self.port = port
        configured_redis_url = redis_url or os.getenv("REDIS_URL")
        self.broker = (
            RedisBroker(redis_client)
            if redis_client is not None
            else RedisBroker.from_url(configured_redis_url)
            if configured_redis_url
            else None
        )
        self.connection_state = (
            RedisConnectionState(self.broker.client) if self.broker is not None else None
        )
        configured_rate_limit = (
            rate_limit if rate_limit is not None else int(os.getenv("RATE_LIMIT", "100"))
        )
        if configured_rate_limit < 1:
            raise ValueError("RATE_LIMIT must be a positive integer")
        self.rate_limiter = (
            RedisRateLimiter(self.broker.client, configured_rate_limit)
            if self.broker is not None
            else None
        )
        self.message_ttl_days = (
            message_ttl_days
            if message_ttl_days is not None
            else int(os.getenv("MESSAGE_TTL_DAYS", "7"))
        )
        if self.message_ttl_days < 1:
            raise ValueError("MESSAGE_TTL_DAYS must be a positive integer")
        self.message_store = message_store
        self.transport = transport or create_transport()
        self.transport.bind(self)
        self.server_id = str(uuid.uuid4())
        self._clients = getattr(self.transport, "clients", {})
        self._channels: dict[str, set[str]] = {}
        self.loop: asyncio.AbstractEventLoop | None = None
        self._server: Server | None = None
        self._subscriber_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None
        self._pubsub = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._startup_error: BaseException | None = None

    def start(self, timeout: float = 5.0) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._ready.clear()
        self._startup_error = None
        self._thread = threading.Thread(
            target=self._run,
            name="notification-websocket-loop",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout):
            raise TimeoutError("WebSocket server did not start")
        if self._startup_error is not None:
            raise RuntimeError("WebSocket server failed to start") from self._startup_error

    def _run(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        async def start_server() -> Server:
            if self.broker is not None:
                self.broker.client.ping()
                self._pubsub = self.broker.pubsub()
                self._pubsub.subscribe(REDIS_MESSAGE_CHANNEL)
                self._subscriber_task = asyncio.create_task(self._subscriber_worker())
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_messages())
            self.port = await self.transport.start(self.host, self.port)
            return getattr(self.transport, "server", None)

        try:
            self._server = self.loop.run_until_complete(start_server())
        except BaseException as exc:
            self._startup_error = exc
            self._ready.set()
            self.loop.close()
            return

        self._ready.set()
        try:
            self.loop.run_forever()
        finally:
            self.loop.run_until_complete(self.transport.stop())
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()
            if pending:
                self.loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            if self._pubsub is not None:
                self._pubsub.close()
            self.loop.close()

    async def _subscriber_worker(self) -> None:
        while True:
            event = await asyncio.to_thread(
                self._pubsub.get_message, ignore_subscribe_messages=True, timeout=0.1
            )
            if event is None:
                await asyncio.sleep(0)
                continue
            try:
                envelope = json.loads(event["data"])
                message = envelope["message"]
                recipient = envelope.get("recipient")
                if recipient is None:
                    await self._broadcast_local(message)
                else:
                    await self._send_direct_local(recipient, message)
            except (KeyError, TypeError, json.JSONDecodeError, ValueError):
                continue

    def _store(self, message: dict[str, Any]) -> None:
        (self.message_store or get_message_store()).save(message)

    async def _cleanup_expired_messages(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.message_ttl_days)
        store = self.message_store or get_message_store()
        await asyncio.to_thread(store.delete_older_than, cutoff)

    async def _broadcast_local(self, message: dict[str, Any]) -> None:
        await self.transport.broadcast(message)

    async def _send_direct_local(
        self, client_id: str, message: dict[str, Any]
    ) -> bool:
        return await self.transport.send_message(client_id, message)

    async def _distribute(
        self, message: dict[str, Any], recipient: str | None = None
    ) -> bool:
        self._store(message)
        if self.broker is not None:
            if recipient is not None and not self.connection_state.has_client(recipient):
                return False
            await asyncio.to_thread(
                self.broker.publish, {"message": message, "recipient": recipient}
            )
            return True
        if recipient is not None:
            return await self._send_direct_local(recipient, message)
        await self._broadcast_local(message)
        return True

    async def _on_connect(self, client_id: str) -> None:
        if self.connection_state is not None:
            await asyncio.to_thread(
                self.connection_state.connect, client_id, self.server_id
            )

    async def _on_message(self, client_id: str, raw_message: Any) -> None:
        if self.rate_limiter is not None and not await asyncio.to_thread(
            self.rate_limiter.allow, client_id
        ):
            await self._send_error(client_id, "rate limit exceeded")
            return
        try:
            message = json.loads(raw_message)
        except (json.JSONDecodeError, TypeError):
            await self._send_error(client_id, "invalid JSON")
            return

        error = validate_message(message)
        if error:
            await self._send_error(client_id, error)
        elif message["type"] == "subscribe":
            _set_subscription(client_id, message["channel"], True)
            self._channels.setdefault(message["channel"], set()).add(client_id)
            self.transport.subscribe(client_id, message["channel"])
            if self.connection_state is not None:
                await asyncio.to_thread(
                    self.connection_state.subscribe, client_id, message["channel"]
                )
        elif message["type"] == "unsubscribe":
            _set_subscription(client_id, message["channel"], False)
            if message["channel"] in self._channels:
                self._channels[message["channel"]].discard(client_id)
                if not self._channels[message["channel"]]:
                    del self._channels[message["channel"]]
            self.transport.unsubscribe(client_id, message["channel"])
            if self.connection_state is not None:
                await asyncio.to_thread(
                    self.connection_state.unsubscribe, client_id, message["channel"]
                )
        elif message["type"] == "broadcast":
            await self._distribute(message)
        elif message["type"] == "direct":
            recipient = message["payload"].get("client_id")
            if not isinstance(recipient, str) or not recipient:
                await self._send_error(client_id, "direct payload requires client_id")
            elif not await self._distribute(message, recipient):
                await self._send_error(client_id, "client not found")
        else:
            await self._send_error(client_id, "system messages are server-only")

    async def _send_error(self, client_id: str, detail: str) -> None:
        await self.transport.send_message(
            client_id, make_message("system", {"error": detail})
        )

    async def _on_disconnect(self, client_id: str) -> None:
        for channel in list(self._channels):
            self._channels[channel].discard(client_id)
            if not self._channels[channel]:
                del self._channels[channel]
        if self.connection_state is not None:
            await asyncio.to_thread(self.connection_state.disconnect, client_id)

    def stop(self, timeout: float = 5.0) -> None:
        if self.loop is None or self._thread is None or not self._thread.is_alive():
            return
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout)
        if self._thread.is_alive():
            raise TimeoutError("WebSocket server did not stop")

    def broadcast(
        self,
        payload: dict[str, Any],
        timeout: float = 5.0,
        channel: str | None = None,
    ) -> None:
        if self.loop is None or not self.loop.is_running():
            raise RuntimeError("WebSocket server is not running")
        future = asyncio.run_coroutine_threadsafe(
            self._distribute(make_message("broadcast", payload, channel)), self.loop
        )
        future.result(timeout)


def main() -> None:
    server = NotificationServer()
    server.start()
    try:
        app.run(host="0.0.0.0", port=5000, threaded=True)
    finally:
        server.stop()


if __name__ == "__main__":
    main()
