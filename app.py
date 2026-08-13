"""Async WebSocket notification server with a JSON health endpoint."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import sqlite3
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Awaitable, Callable
from urllib.parse import unquote

from websockets.asyncio.server import ServerConnection, serve

try:
    from redis import asyncio as redis_asyncio
except ImportError:  # Allows importing the application before optional dependencies are installed.
    redis_asyncio = None


MESSAGE_TYPES = {"broadcast", "direct", "subscribe", "system", "unsubscribe"}
BROKER_CHANNEL = "notifications:messages"
STATE_PREFIX = "notifications"


class ClientRegistry:
    """Thread-safe registry keyed by each live connection's remote address."""

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = RLock()

    @staticmethod
    def client_id(connection: Any) -> str:
        address = connection.remote_address
        if address is None:
            raise ValueError("connection has no remote address")
        return f"{address[0]}:{address[1]}"

    def add(self, connection: Any) -> str:
        client_id = self.client_id(connection)
        with self._lock:
            self._clients[client_id] = connection
        return client_id

    def remove(self, connection: Any) -> None:
        client_id = self.client_id(connection)
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in list(self._channels):
                subscribers = self._channels[channel]
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[channel]

    def get(self, client_id: str) -> Any | None:
        with self._lock:
            return self._clients.get(client_id)

    def connections(self, channel: str | None = None) -> list[Any]:
        with self._lock:
            if channel is not None:
                return [
                    self._clients[client_id]
                    for client_id in self._channels.get(channel, set())
                    if client_id in self._clients
                ]
            return list(self._clients.values())

    def subscribe(self, connection: Any, channel: str) -> None:
        client_id = self.client_id(connection)
        with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, connection: Any, channel: str) -> None:
        client_id = self.client_id(connection)
        with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    def channels(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"name": channel, "subscriber_count": len(subscribers)}
                for channel, subscribers in sorted(self._channels.items())
            ]

    def subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)


class BaseTransport(ABC):
    """Interface between notification delivery and a client transport."""

    @abstractmethod
    async def on_connect(self, connection: Any) -> None:
        """Prepare a newly connected client."""

    @abstractmethod
    async def on_disconnect(self, connection: Any) -> None:
        """Release a disconnected client."""

    @abstractmethod
    async def send_message(self, connection: Any, message: str) -> None:
        """Send one encoded message to a client."""

    @abstractmethod
    async def broadcast(self, message: str, connections: list[Any]) -> None:
        """Send one encoded message to multiple clients."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport interface."""

    async def on_connect(self, connection: ServerConnection) -> None:
        return None

    async def on_disconnect(self, connection: ServerConnection) -> None:
        return None

    async def send_message(self, connection: ServerConnection, message: str) -> None:
        await connection.send(message)

    async def broadcast(self, message: str, connections: list[ServerConnection]) -> None:
        await asyncio.gather(*(self.send_message(connection, message) for connection in connections))

    async def handle_connection(
        self,
        connection: ServerConnection,
        on_connect: Callable[[Any], Awaitable[None]],
        on_message: Callable[[Any, str], Awaitable[None]],
        on_disconnect: Callable[[Any], Awaitable[None]],
    ) -> None:
        await self.on_connect(connection)
        await on_connect(connection)
        try:
            async for raw_message in connection:
                await on_message(connection, raw_message)
        finally:
            try:
                await on_disconnect(connection)
            finally:
                await self.on_disconnect(connection)

    def create_server(
        self,
        handler: Callable[[ServerConnection], Awaitable[None]],
        host: str,
        port: int,
        process_request: Callable[[ServerConnection, Any], Awaitable[Any]],
    ) -> Any:
        return serve(handler, host, port, process_request=process_request)


class MessageStore:
    """SQLite-backed message history."""

    def __init__(self, database_url: str) -> None:
        self.path = self._database_path(database_url)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = RLock()
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

    @staticmethod
    def _database_path(database_url: str) -> str:
        if database_url == "sqlite:///:memory:":
            return ":memory:"
        if database_url.startswith("sqlite:///"):
            return database_url.removeprefix("sqlite:///")
        return database_url

    def save(self, message: dict[str, Any]) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (
                    message.get("channel"),
                    message["type"],
                    json.dumps(message["payload"]),
                    message["timestamp"],
                ),
            )

    def list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
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

    def history(self, channel: str, since: str | None, limit: int, offset: int) -> list[dict[str, Any]]:
        clauses = ["channel = ?"]
        parameters: list[Any] = [channel]
        if since is not None:
            clauses.append("timestamp > ?")
            parameters.append(since)
        parameters.extend([limit, offset])
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages WHERE "
                + " AND ".join(clauses)
                + " ORDER BY timestamp ASC, id ASC LIMIT ? OFFSET ?",
                parameters,
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

    def delete_older_than(self, cutoff: datetime) -> None:
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff.isoformat(),))

    def close(self) -> None:
        self._connection.close()


class RedisBroker:
    """Redis pub/sub transport plus durable client subscription state."""

    def __init__(self, url: str, instance_id: str | None = None, client: Any = None) -> None:
        if redis_asyncio is None:
            raise RuntimeError("redis package is required for Redis integration")
        self.redis = client or redis_asyncio.from_url(url, decode_responses=True)
        self.instance_id = instance_id or uuid.uuid4().hex
        self.pubsub: Any = None

    async def publish(self, message: str) -> None:
        await self.redis.publish(BROKER_CHANNEL, message)

    async def check_rate_limit(self, client_id: str, limit: int) -> bool:
        key = f"{STATE_PREFIX}:rate-limit:{client_id}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, 60)
        return count <= limit

    async def listen(self):
        self.pubsub = self.redis.pubsub()
        await self.pubsub.subscribe(BROKER_CHANNEL)
        async for event in self.pubsub.listen():
            if event["type"] == "message":
                yield event["data"]

    async def add_client(self, client_id: str) -> None:
        await self.redis.hset(f"{STATE_PREFIX}:clients", client_id, self.instance_id)

    async def remove_client(self, client_id: str) -> None:
        pipeline = self.redis.pipeline()
        pipeline.hdel(f"{STATE_PREFIX}:clients", client_id)
        channels = await self.redis.smembers(f"{STATE_PREFIX}:client:{client_id}:channels")
        for channel in channels:
            pipeline.srem(f"{STATE_PREFIX}:channel:{channel}:clients", client_id)
        pipeline.delete(f"{STATE_PREFIX}:client:{client_id}:channels")
        await pipeline.execute()

    async def subscribe(self, client_id: str, channel: str) -> None:
        pipeline = self.redis.pipeline()
        pipeline.sadd(f"{STATE_PREFIX}:client:{client_id}:channels", channel)
        pipeline.sadd(f"{STATE_PREFIX}:channel:{channel}:clients", client_id)
        await pipeline.execute()

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        pipeline = self.redis.pipeline()
        pipeline.srem(f"{STATE_PREFIX}:client:{client_id}:channels", channel)
        pipeline.srem(f"{STATE_PREFIX}:channel:{channel}:clients", client_id)
        await pipeline.execute()

    async def client_subscribes(self, client_id: str, channel: str) -> bool:
        return bool(await self.redis.sismember(f"{STATE_PREFIX}:channel:{channel}:clients", client_id))

    async def channels(self) -> list[dict[str, Any]]:
        result = []
        async for key in self.redis.scan_iter(match=f"{STATE_PREFIX}:channel:*:clients"):
            channel = key[len(f"{STATE_PREFIX}:channel:") : -len(":clients")]
            count = await self.redis.scard(key)
            if count:
                result.append({"name": channel, "subscriber_count": count})
        return sorted(result, key=lambda item: item["name"])

    async def subscribers(self, channel: str) -> list[str]:
        return sorted(await self.redis.smembers(f"{STATE_PREFIX}:channel:{channel}:clients"))

    async def close(self) -> None:
        if self.pubsub is not None:
            await self.pubsub.unsubscribe(BROKER_CHANNEL)
            close = getattr(self.pubsub, "aclose", self.pubsub.close)
            result = close()
            if inspect.isawaitable(result):
                await result
        close = getattr(self.redis, "aclose", self.redis.close)
        result = close()
        if inspect.isawaitable(result):
            await result


class NotificationServer:
    def __init__(
        self,
        redis_url: str | None = None,
        database_url: str | None = None,
        redis_client: Any = None,
        transport: BaseTransport | None = None,
        rate_limit: int | None = None,
        message_ttl_days: int | None = None,
    ) -> None:
        self.clients = ClientRegistry()
        self.store = MessageStore(database_url or os.environ.get("DATABASE_URL", "sqlite:///messages.db"))
        self.broker = RedisBroker(
            redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0"), client=redis_client
        )
        self.transport = transport or self._create_transport(os.environ.get("TRANSPORT", "websocket"))
        self.rate_limit = rate_limit if rate_limit is not None else self._positive_int_env("RATE_LIMIT", 100)
        self.message_ttl_days = (
            message_ttl_days
            if message_ttl_days is not None
            else self._positive_int_env("MESSAGE_TTL_DAYS", 7)
        )
        self._listener_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None

    @staticmethod
    def _positive_int_env(name: str, default: int) -> int:
        value = os.environ.get(name)
        if value is None:
            return default
        try:
            parsed = int(value)
        except ValueError as error:
            raise ValueError(f"{name} must be a positive integer") from error
        if parsed < 1:
            raise ValueError(f"{name} must be a positive integer")
        return parsed

    @staticmethod
    def _create_transport(name: str) -> BaseTransport:
        if name.lower() in {"websocket", "ws"}:
            return WebSocketTransport()
        raise ValueError(f"unsupported transport: {name}")

    @staticmethod
    def build_message(
        message_type: str, payload: dict[str, Any], channel: str | None = None
    ) -> str:
        if message_type not in MESSAGE_TYPES:
            raise ValueError(f"unsupported message type: {message_type}")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        message = {
            "type": message_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if channel is not None:
            message["channel"] = channel
        return json.dumps(message)

    async def deliver(self, message: str) -> None:
        decoded = json.loads(message)
        channel = decoded.get("channel")
        if decoded["type"] == "direct":
            target = decoded["payload"].get("client_id")
            connections = [self.clients.get(target)] if isinstance(target, str) else []
        else:
            connections = self.clients.connections(channel)
            if channel is not None:
                connections = [
                    connection
                    for connection in connections
                    if await self.broker.client_subscribes(self.clients.client_id(connection), channel)
                ]
        connections = [connection for connection in connections if connection is not None]
        if connections:
            await self.transport.broadcast(message, connections)

    async def _listen(self) -> None:
        async for message in self.broker.listen():
            await self.deliver(message)

    async def _cleanup_expired_messages(self) -> None:
        while True:
            self.store.delete_older_than(datetime.now(timezone.utc) - timedelta(days=self.message_ttl_days))
            await asyncio.sleep(3600)

    async def start(self) -> None:
        if self._listener_task is None:
            self._listener_task = asyncio.create_task(self._listen())
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_messages())

    async def close(self) -> None:
        if self._listener_task is not None:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except BaseException as error:
                if not isinstance(error, asyncio.CancelledError):
                    raise
            self._listener_task = None
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        await self.broker.close()
        self.store.close()

    async def _on_connect(self, connection: Any) -> None:
        client_id = self.clients.add(connection)
        await self.broker.add_client(client_id)
        await self.transport.send_message(connection, self.build_message("system", {"client_id": client_id}))

    async def _on_message(self, connection: Any, raw_message: str) -> None:
        try:
            if not await self.broker.check_rate_limit(self.clients.client_id(connection), self.rate_limit):
                raise ValueError("rate limit exceeded")
            message = json.loads(raw_message)
            message_type = message["type"]
            payload = message["payload"]
            channel = message.get("channel")
            if channel is not None and (not isinstance(channel, str) or not channel):
                raise ValueError("channel must be a non-empty string")
            if message_type in {"subscribe", "unsubscribe"}:
                if channel is None:
                    raise ValueError("channel is required")
                if message_type == "subscribe":
                    self.clients.subscribe(connection, channel)
                    await self.broker.subscribe(self.clients.client_id(connection), channel)
                else:
                    self.clients.unsubscribe(connection, channel)
                    await self.broker.unsubscribe(self.clients.client_id(connection), channel)
                return

            encoded = self.build_message(message_type, payload, channel)
            self.store.save(json.loads(encoded))
            await self.broker.publish(encoded)
        except (json.JSONDecodeError, KeyError, ValueError) as error:
            await self.transport.send_message(connection, self.build_message("system", {"error": str(error)}))

    async def _on_disconnect(self, connection: Any) -> None:
        client_id = self.clients.client_id(connection)
        self.clients.remove(connection)
        await self.broker.remove_client(client_id)

    async def handler(self, connection: ServerConnection) -> None:
        if not isinstance(self.transport, WebSocketTransport):
            raise RuntimeError("the configured transport does not support WebSocket connections")
        await self.transport.handle_connection(connection, self._on_connect, self._on_message, self._on_disconnect)

    async def process_request(self, connection: ServerConnection, request: Any) -> Any:
        if request.path == "/health":
            response = connection.respond(200, json.dumps({"connected_clients": len(self.clients)}))
            response.headers["Content-Type"] = "application/json"
            return response
        if request.path == "/channels":
            response = connection.respond(200, json.dumps({"channels": await self.broker.channels()}))
            response.headers["Content-Type"] = "application/json"
            return response
        if request.path.startswith("/channels/") and request.path.endswith("/subscribers"):
            channel = unquote(request.path[len("/channels/") : -len("/subscribers")].rstrip("/"))
            response = connection.respond(
                200, json.dumps({"subscribers": await self.broker.subscribers(channel)})
            )
            response.headers["Content-Type"] = "application/json"
            return response
        if request.path.startswith("/messages"):
            from urllib.parse import parse_qs, urlsplit

            query = parse_qs(urlsplit(request.path).query)
            try:
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
                if not 1 <= limit <= 1000 or offset < 0:
                    raise ValueError
            except ValueError:
                response = connection.respond(400, json.dumps({"error": "limit must be 1-1000 and offset non-negative"}))
                response.headers["Content-Type"] = "application/json"
                return response
            response = connection.respond(200, json.dumps({"messages": self.store.list(limit, offset)}))
            response.headers["Content-Type"] = "application/json"
            return response
        if request.path.startswith("/history"):
            from urllib.parse import parse_qs, urlsplit

            query = parse_qs(urlsplit(request.path).query)
            channel = query.get("channel", [""])[0]
            since = query.get("since", [None])[0]
            try:
                if not channel:
                    raise ValueError("channel is required")
                if since is not None:
                    parsed_since = datetime.fromisoformat(since.replace("Z", "+00:00"))
                    if parsed_since.tzinfo is None:
                        raise ValueError("since must include a timezone")
                    since = parsed_since.astimezone(timezone.utc).isoformat()
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
                if not 1 <= limit <= 1000 or offset < 0:
                    raise ValueError("limit must be 1-1000 and offset non-negative")
            except ValueError as error:
                response = connection.respond(400, json.dumps({"error": str(error)}))
                response.headers["Content-Type"] = "application/json"
                return response
            messages = self.store.history(channel, since, limit + 1, offset)
            response = connection.respond(
                200, json.dumps({"messages": messages[:limit], "has_more": len(messages) > limit})
            )
            response.headers["Content-Type"] = "application/json"
            return response
        return None

    def create_server(self, host: str = "127.0.0.1", port: int = 8765) -> Any:
        if not isinstance(self.transport, WebSocketTransport):
            raise RuntimeError("the configured transport does not provide a server factory")
        return self.transport.create_server(self.handler, host, port, self.process_request)


async def main() -> None:
    notification_server = NotificationServer()
    await notification_server.start()
    try:
        async with notification_server.create_server():
            await asyncio.Future()
    finally:
        await notification_server.close()


if __name__ == "__main__":
    asyncio.run(main())
