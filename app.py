"""Async WebSocket notification server backed by Redis and SQLite."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import threading
import uuid
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs, urlparse

from websockets.asyncio.server import ServerConnection, serve


SUPPORTED_TYPES = frozenset({"broadcast", "direct", "system", "subscribe", "unsubscribe"})
BROKER_CHANNEL = "notifications:messages"
ConnectionHandler = Callable[[dict[str, Any]], Awaitable[None]]
MessageHandler = Callable[[str, str | bytes], Awaitable[None]]
LifecycleHandler = Callable[[str], Awaitable[None]]


class MessageStore:
    """SQLite-backed notification history."""

    def __init__(self, database_url: str | None = None) -> None:
        database_url = database_url or os.getenv("DATABASE_URL", ":memory:")
        self.path = self._path_from_url(database_url)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._lock = threading.RLock()
        with self._connection:
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS messages ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, type TEXT NOT NULL, "
                "payload TEXT NOT NULL, timestamp TEXT NOT NULL)"
            )

    @staticmethod
    def _path_from_url(database_url: str) -> str:
        if database_url.startswith("sqlite:///"):
            return database_url[len("sqlite:///") :]
        if database_url.startswith("sqlite://"):
            raise ValueError("DATABASE_URL must be a SQLite path or sqlite:/// URL")
        return database_url

    def save(self, message: dict[str, Any]) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (message.get("channel"), message["type"], json.dumps(message["payload"]), message["timestamp"]),
            )

    def list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [
            {"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]}
            for row in rows
        ]

    def history(self, channel: str, since: str, limit: int, offset: int = 0) -> tuple[list[dict[str, Any]], bool]:
        """Return a chronological page of channel messages after ``since``."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "WHERE channel = ? AND datetime(timestamp) >= datetime(?) "
                "ORDER BY datetime(timestamp) ASC, id ASC LIMIT ? OFFSET ?",
                (channel, since, limit + 1, offset),
            ).fetchall()
        has_more = len(rows) > limit
        return (
            [
                {"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]}
                for row in rows[:limit]
            ],
            has_more,
        )

    def delete_before(self, cutoff: str) -> None:
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM messages WHERE datetime(timestamp) < datetime(?)", (cutoff,))


class MemoryRateLimiter:
    """Process-local limiter used when a Redis connection is unavailable."""

    def __init__(self) -> None:
        self._counts: dict[str, tuple[int, int]] = {}
        self._lock = asyncio.Lock()

    async def allow(self, client_id: str, limit: int) -> bool:
        now = int(datetime.now(timezone.utc).timestamp() // 60)
        async with self._lock:
            window, count = self._counts.get(client_id, (now, 0))
            if window != now:
                count = 0
            count += 1
            self._counts[client_id] = (now, count)
            return count <= limit


class RedisRateLimiter:
    """Fixed-window per-client rate limiter backed by Redis atomic counters."""

    def __init__(self, redis_client: Any) -> None:
        self.redis = redis_client

    async def allow(self, client_id: str, limit: int) -> bool:
        window = int(datetime.now(timezone.utc).timestamp() // 60)
        key = f"notifications:rate-limit:{client_id}:{window}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, 60)
        return count <= limit


class MemoryBroker:
    """Process-local broker used when REDIS_URL is not configured."""

    def __init__(self) -> None:
        self.clients: dict[str, set[str]] = {}
        self.channels: dict[str, set[str]] = {}
        self.handlers: list[ConnectionHandler] = []

    async def start(self, handler: ConnectionHandler) -> None:
        self.handlers.append(handler)

    async def close(self) -> None:
        return None

    async def publish(self, message: dict[str, Any]) -> None:
        await asyncio.gather(*(handler(message) for handler in list(self.handlers)))

    async def add_client(self, client_id: str) -> None:
        self.clients[client_id] = set()

    async def remove_client(self, client_id: str) -> None:
        for channel in self.clients.pop(client_id, set()):
            self.channels.get(channel, set()).discard(client_id)

    async def update_subscription(self, client_id: str, channel: str, subscribe: bool) -> None:
        subscriptions = self.clients.setdefault(client_id, set())
        if subscribe:
            subscriptions.add(channel)
            self.channels.setdefault(channel, set()).add(client_id)
        else:
            subscriptions.discard(channel)
            self.channels.get(channel, set()).discard(client_id)

    async def channel_names(self) -> list[str]:
        return sorted(name for name, clients in self.channels.items() if clients)

    async def subscribers(self, channel: str) -> list[str]:
        return sorted(self.channels.get(channel, set()))


class RedisBroker:
    """Redis pub/sub distribution plus durable connection subscription state."""

    def __init__(self, url: str) -> None:
        import redis.asyncio as redis

        self.redis = redis.from_url(url, decode_responses=True)
        self.pubsub: Any | None = None
        self.listener: asyncio.Task[None] | None = None

    async def start(self, handler: ConnectionHandler) -> None:
        self.pubsub = self.redis.pubsub()
        await self.pubsub.subscribe(BROKER_CHANNEL)

        async def listen() -> None:
            assert self.pubsub is not None
            async for event in self.pubsub.listen():
                if event["type"] == "message":
                    await handler(json.loads(event["data"]))

        self.listener = asyncio.create_task(listen())

    async def close(self) -> None:
        if self.listener is not None:
            self.listener.cancel()
            try:
                await self.listener
            except asyncio.CancelledError:
                pass
        if self.pubsub is not None:
            await self.pubsub.aclose()
        await self.redis.aclose()

    async def publish(self, message: dict[str, Any]) -> None:
        await self.redis.publish(BROKER_CHANNEL, json.dumps(message))

    async def add_client(self, client_id: str) -> None:
        await self.redis.hset("notifications:clients", client_id, json.dumps({"connected_at": _timestamp()}))

    async def remove_client(self, client_id: str) -> None:
        channels = await self.redis.smembers(f"notifications:client:{client_id}:channels")
        pipeline = self.redis.pipeline()
        pipeline.hdel("notifications:clients", client_id)
        pipeline.delete(f"notifications:client:{client_id}:channels")
        for channel in channels:
            pipeline.srem(f"notifications:channel:{channel}:clients", client_id)
        await pipeline.execute()

    async def update_subscription(self, client_id: str, channel: str, subscribe: bool) -> None:
        pipeline = self.redis.pipeline()
        if subscribe:
            pipeline.sadd(f"notifications:client:{client_id}:channels", channel)
            pipeline.sadd(f"notifications:channel:{channel}:clients", client_id)
        else:
            pipeline.srem(f"notifications:client:{client_id}:channels", channel)
            pipeline.srem(f"notifications:channel:{channel}:clients", client_id)
        await pipeline.execute()

    async def channel_names(self) -> list[str]:
        keys = await self.redis.keys("notifications:channel:*:clients")
        return sorted(key[len("notifications:channel:") : -len(":clients")] for key in keys if await self.redis.scard(key))

    async def subscribers(self, channel: str) -> list[str]:
        return sorted(await self.redis.smembers(f"notifications:channel:{channel}:clients"))


def _timestamp() -> str:
    return _utc_now().isoformat()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BaseTransport(ABC):
    """Connection transport used by the notification router."""

    def __init__(self) -> None:
        self._message_handler: MessageHandler | None = None
        self._connected_handler: LifecycleHandler | None = None
        self._disconnected_handler: LifecycleHandler | None = None

    def configure(
        self,
        message_handler: MessageHandler,
        connected_handler: LifecycleHandler,
        disconnected_handler: LifecycleHandler,
    ) -> None:
        """Attach the core server callbacks used by this transport."""
        self._message_handler = message_handler
        self._connected_handler = connected_handler
        self._disconnected_handler = disconnected_handler

    @abstractmethod
    async def on_connect(self, connection: Any) -> str:
        """Register a transport connection and return its client ID."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Remove a transport connection."""

    @abstractmethod
    async def send_message(self, client_id: str, message: dict[str, Any]) -> None:
        """Send a message to one connected client."""

    @abstractmethod
    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a message to every connected client."""

    async def handler(self, connection: Any) -> None:
        """Accept a transport connection when the transport exposes a server handler."""
        raise NotImplementedError(f"{type(self).__name__} does not provide a server handler")


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport interface."""

    def __init__(self) -> None:
        super().__init__()
        self._clients: dict[str, ServerConnection] = {}
        self._lock = threading.RLock()

    async def on_connect(self, connection: ServerConnection) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = connection
        if self._connected_handler is not None:
            await self._connected_handler(client_id)
        return client_id

    async def on_disconnect(self, client_id: str) -> None:
        with self._lock:
            removed = self._clients.pop(client_id, None)
        if removed is not None and self._disconnected_handler is not None:
            await self._disconnected_handler(client_id)

    async def send_message(self, client_id: str, message: dict[str, Any]) -> None:
        with self._lock:
            connection = self._clients.get(client_id)
        if connection is None:
            return
        try:
            await connection.send(json.dumps(message))
        except Exception:
            await self.on_disconnect(client_id)

    async def broadcast(self, message: dict[str, Any]) -> None:
        with self._lock:
            client_ids = list(self._clients)
        await asyncio.gather(*(self.send_message(client_id, message) for client_id in client_ids))

    async def handler(self, connection: ServerConnection) -> None:
        client_id = await self.on_connect(connection)
        try:
            await self.send_message(
                client_id,
                {"type": "system", "payload": {"event": "connected", "client_id": client_id}, "timestamp": _timestamp()},
            )
            async for raw_message in connection:
                if self._message_handler is not None:
                    await self._message_handler(client_id, raw_message)
        finally:
            await self.on_disconnect(client_id)


class NotificationServer:
    """Routes JSON notifications using a shared Redis pub/sub backbone."""

    def __init__(
        self,
        broker: Any | None = None,
        store: MessageStore | None = None,
        transport: BaseTransport | None = None,
        rate_limiter: Any | None = None,
    ) -> None:
        self._clients: set[str] = set()
        self._lock = threading.RLock()
        self._broker = broker or (RedisBroker(os.environ["REDIS_URL"]) if os.getenv("REDIS_URL") else MemoryBroker())
        self._store = store or MessageStore()
        self._rate_limit = self._rate_limit_from_config()
        self._rate_limiter = rate_limiter or self._rate_limiter_from_broker()
        self._transport = transport or self._transport_from_config()
        self._transport.configure(self.handle_message, self._add_client, self._remove_client)
        self._started = False
        self._start_lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task[None] | None = None

    @staticmethod
    def _transport_from_config() -> BaseTransport:
        transport_name = os.getenv("TRANSPORT", "websocket").lower()
        if transport_name == "websocket":
            return WebSocketTransport()
        raise ValueError(f"unsupported TRANSPORT: {transport_name}")

    @staticmethod
    def _rate_limit_from_config() -> int:
        try:
            rate_limit = int(os.getenv("RATE_LIMIT", "100"))
        except ValueError as error:
            raise ValueError("RATE_LIMIT must be a positive integer") from error
        if rate_limit < 1:
            raise ValueError("RATE_LIMIT must be a positive integer")
        return rate_limit

    def _rate_limiter_from_broker(self) -> MemoryRateLimiter | RedisRateLimiter:
        if isinstance(self._broker, RedisBroker):
            return RedisRateLimiter(self._broker.redis)
        return MemoryRateLimiter()

    @staticmethod
    def _message_ttl_from_config() -> int:
        try:
            ttl_days = int(os.getenv("MESSAGE_TTL_DAYS", "7"))
        except ValueError as error:
            raise ValueError("MESSAGE_TTL_DAYS must be a non-negative integer") from error
        if ttl_days < 0:
            raise ValueError("MESSAGE_TTL_DAYS must be a non-negative integer")
        return ttl_days

    @property
    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    async def start(self) -> None:
        async with self._start_lock:
            if not self._started:
                self._cleanup_task = asyncio.create_task(self._cleanup_expired_messages())
                await self._broker.start(self._deliver_published)
                self._started = True

    async def close(self) -> None:
        if self._cleanup_task is not None:
            await self._cleanup_task
            self._cleanup_task = None
        if self._started:
            await self._broker.close()
            self._started = False

    async def _cleanup_expired_messages(self) -> None:
        cutoff = (_utc_now() - timedelta(days=self._message_ttl_from_config())).isoformat()
        await asyncio.to_thread(self._store.delete_before, cutoff)

    async def handler(self, websocket: ServerConnection) -> None:
        await self.start()
        await self._transport.handler(websocket)

    async def _add_client(self, client_id: str) -> None:
        with self._lock:
            self._clients.add(client_id)
        await self._broker.add_client(client_id)

    async def handle_message(self, sender_id: str, raw_message: str | bytes) -> None:
        if not await self._rate_limiter.allow(sender_id, self._rate_limit):
            await self._send_error(sender_id, "rate limit exceeded")
            return
        try:
            message = json.loads(raw_message)
            message_type = message["type"]
            payload = message.get("payload", {}) if message_type in {"subscribe", "unsubscribe"} else message["payload"]
        except (json.JSONDecodeError, KeyError, TypeError):
            await self._send_error(sender_id, "message must contain type and payload")
            return
        if message_type not in SUPPORTED_TYPES or not isinstance(payload, dict):
            await self._send_error(sender_id, "unsupported message type or invalid payload")
            return
        channel = message.get("channel")
        if channel is not None and (not isinstance(channel, str) or not channel):
            await self._send_error(sender_id, "channel must be a non-empty string")
            return
        if message_type in {"subscribe", "unsubscribe"}:
            if not channel:
                await self._send_error(sender_id, f"{message_type} messages require channel")
                return
            await self._broker.update_subscription(sender_id, channel, message_type == "subscribe")
            return
        if message_type == "direct" and not channel and not isinstance(payload.get("client_id"), str):
            await self._send_error(sender_id, "direct messages require payload.client_id")
            return
        notification: dict[str, Any] = {"type": message_type, "payload": payload, "timestamp": message.get("timestamp") or _timestamp()}
        if channel:
            notification["channel"] = channel
        self._store.save(notification)
        await self._broker.publish(notification)

    async def _deliver_published(self, message: dict[str, Any]) -> None:
        if message.get("channel"):
            recipients = await self._broker.subscribers(message["channel"])
        elif message["type"] == "direct":
            recipients = [message["payload"]["client_id"]]
        else:
            await self._transport.broadcast(message)
            return
        await asyncio.gather(*(self._send_to(client_id, message) for client_id in recipients))

    async def _send_to(self, client_id: str, message: dict[str, Any]) -> None:
        await self._transport.send_message(client_id, message)

    async def _remove_client(self, client_id: str) -> None:
        with self._lock:
            self._clients.discard(client_id)
        await self._broker.remove_client(client_id)

    async def _send_error(self, client_id: str, error: str) -> None:
        await self._send_to(client_id, {"type": "system", "payload": {"event": "error", "message": error}, "timestamp": _timestamp()})

    async def process_request(self, connection: ServerConnection, request: Any) -> Any:
        parsed = urlparse(request.path)
        if parsed.path == "/health":
            return connection.respond(HTTPStatus.OK, json.dumps({"connected_clients": self.client_count}))
        if parsed.path == "/messages":
            parameters = parse_qs(parsed.query)
            try:
                limit, offset = int(parameters.get("limit", ["50"])[0]), int(parameters.get("offset", ["0"])[0])
                if not 0 <= offset and 1 <= limit <= 1000:
                    raise ValueError
            except ValueError:
                return connection.respond(HTTPStatus.BAD_REQUEST, "limit must be 1-1000 and offset must be non-negative")
            return connection.respond(HTTPStatus.OK, json.dumps({"messages": self._store.list(limit, offset)}))
        if parsed.path == "/history":
            parameters = parse_qs(parsed.query)
            channel = parameters.get("channel", [None])[0]
            since = parameters.get("since", [None])[0]
            try:
                limit = int(parameters.get("limit", ["50"])[0])
                offset = int(parameters.get("offset", ["0"])[0])
                if not isinstance(channel, str) or not channel or not isinstance(since, str) or not 1 <= limit <= 1000 or offset < 0:
                    raise ValueError
                parsed_since = datetime.fromisoformat(since.replace("Z", "+00:00"))
                if parsed_since.tzinfo is None:
                    raise ValueError
            except ValueError:
                return connection.respond(
                    HTTPStatus.BAD_REQUEST,
                    "channel and timezone-aware since are required; limit must be 1-1000 and offset must be non-negative",
                )
            messages, has_more = self._store.history(channel, parsed_since.astimezone(timezone.utc).isoformat(), limit, offset)
            return connection.respond(HTTPStatus.OK, json.dumps({"messages": messages, "has_more": has_more}))
        if parsed.path == "/channels":
            channels = [{"name": name, "subscriber_count": len(await self._broker.subscribers(name))} for name in await self._broker.channel_names()]
            return connection.respond(HTTPStatus.OK, json.dumps({"channels": channels}))
        if parsed.path.startswith("/channels/") and parsed.path.endswith("/subscribers"):
            name = parsed.path[len("/channels/") : -len("/subscribers")].rstrip("/")
            if not name:
                return connection.respond(HTTPStatus.NOT_FOUND, "not found")
            return connection.respond(HTTPStatus.OK, json.dumps({"channel": name, "subscribers": await self._broker.subscribers(name)}))
        return None


async def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    notification_server = NotificationServer()
    await notification_server.start()
    try:
        async with serve(notification_server.handler, host, port, process_request=notification_server.process_request):
            await asyncio.Future()
    finally:
        await notification_server.close()


if __name__ == "__main__":
    asyncio.run(run_server())
