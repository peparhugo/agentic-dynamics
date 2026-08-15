"""WebSocket notification server backed by Redis pub/sub and SQLite."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import threading
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any, Protocol
from urllib.parse import parse_qs, unquote, urlsplit

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response


SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
BROKER_CHANNEL = "notifications:messages"


def utc_timestamp() -> str:
    """Return an ISO 8601 timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Build a message in the server's wire format."""
    return {"type": message_type, "payload": payload, "timestamp": utc_timestamp()}


class MessageStore:
    """Persist and retrieve notification history in SQLite."""

    def __init__(self, database_url: str) -> None:
        path = database_url
        if path.startswith("sqlite:///"):
            path = path[len("sqlite:///") :]
        elif path.startswith("sqlite://"):
            path = path[len("sqlite://") :]
        self._connection = sqlite3.connect(path or ":memory:", check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
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

    def add(self, notification: dict[str, Any]) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (
                    notification.get("channel"),
                    notification["type"],
                    json.dumps(notification["payload"], separators=(",", ":")),
                    notification["timestamp"],
                ),
            )
            return int(cursor.lastrowid)

    def list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id ASC LIMIT ? OFFSET ?",
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

    def close(self) -> None:
        with self._lock:
            self._connection.close()


class ConnectionState(Protocol):
    async def connect(self, client_id: str, server_id: str) -> list[str]: ...

    async def disconnect(self, client_id: str) -> None: ...

    async def subscribe(self, client_id: str, channel: str) -> None: ...

    async def unsubscribe(self, client_id: str, channel: str) -> None: ...

    async def is_connected(self, client_id: str) -> bool: ...

    async def channels(self) -> list[dict[str, Any]]: ...

    async def subscribers(self, channel: str) -> list[str]: ...


class MemoryConnectionState:
    """Service-free state backend used only when REDIS_URL isn't configured."""

    def __init__(self) -> None:
        self.connected: set[str] = set()
        self.subscriptions: dict[str, set[str]] = {}

    async def connect(self, client_id: str, server_id: str) -> list[str]:
        del server_id
        self.connected.add(client_id)
        return sorted(self.subscriptions.get(client_id, set()))

    async def disconnect(self, client_id: str) -> None:
        self.connected.discard(client_id)

    async def subscribe(self, client_id: str, channel: str) -> None:
        if client_id in self.connected:
            self.subscriptions.setdefault(client_id, set()).add(channel)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        self.subscriptions.get(client_id, set()).discard(channel)

    async def is_connected(self, client_id: str) -> bool:
        return client_id in self.connected

    async def subscribers(self, channel: str) -> list[str]:
        return sorted(
            client_id
            for client_id in self.connected
            if channel in self.subscriptions.get(client_id, set())
        )

    async def channels(self) -> list[dict[str, Any]]:
        names = {name for values in self.subscriptions.values() for name in values}
        result = []
        for name in sorted(names):
            subscribers = await self.subscribers(name)
            if subscribers:
                result.append({"name": name, "subscriber_count": len(subscribers)})
        return result


class RedisConnectionState:
    """Store client presence and durable subscriptions in Redis."""

    def __init__(self, redis: Any, namespace: str = "notifications") -> None:
        self.redis = redis
        self.namespace = namespace

    @property
    def _connected(self) -> str:
        return f"{self.namespace}:connected"

    @property
    def _channels(self) -> str:
        return f"{self.namespace}:channels"

    def _client(self, client_id: str) -> str:
        return f"{self.namespace}:client:{client_id}"

    def _subscriptions(self, client_id: str) -> str:
        return f"{self.namespace}:subscriptions:{client_id}"

    def _subscribers(self, channel: str) -> str:
        return f"{self.namespace}:channel:{channel}"

    async def connect(self, client_id: str, server_id: str) -> list[str]:
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hset(
                self._client(client_id),
                mapping={"connected": "1", "server_id": server_id},
            )
            pipe.sadd(self._connected, client_id)
            pipe.smembers(self._subscriptions(client_id))
            results = await pipe.execute()
        return sorted(self._decode(value) for value in results[-1])

    async def disconnect(self, client_id: str) -> None:
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hset(self._client(client_id), "connected", "0")
            pipe.srem(self._connected, client_id)
            await pipe.execute()

    async def subscribe(self, client_id: str, channel: str) -> None:
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.sadd(self._subscriptions(client_id), channel)
            pipe.sadd(self._subscribers(channel), client_id)
            pipe.sadd(self._channels, channel)
            await pipe.execute()

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.srem(self._subscriptions(client_id), channel)
            pipe.srem(self._subscribers(channel), client_id)
            await pipe.execute()

    async def is_connected(self, client_id: str) -> bool:
        return bool(await self.redis.sismember(self._connected, client_id))

    async def subscribers(self, channel: str) -> list[str]:
        members = await self.redis.sinter(self._subscribers(channel), self._connected)
        return sorted(self._decode(value) for value in members)

    async def channels(self) -> list[dict[str, Any]]:
        names = sorted(self._decode(value) for value in await self.redis.smembers(self._channels))
        result = []
        for name in names:
            subscribers = await self.subscribers(name)
            if subscribers:
                result.append({"name": name, "subscriber_count": len(subscribers)})
        return result

    @staticmethod
    def _decode(value: str | bytes) -> str:
        return value.decode("utf-8") if isinstance(value, bytes) else value


BrokerHandler = Callable[[dict[str, Any]], Awaitable[None]]


class MessageBroker(Protocol):
    async def start(self, handler: BrokerHandler) -> None: ...

    async def publish(self, envelope: dict[str, Any]) -> None: ...

    async def close(self) -> None: ...


class MemoryBroker:
    """In-process compatibility broker for installations without REDIS_URL."""

    _handlers: set[BrokerHandler] = set()

    def __init__(self) -> None:
        self.handler: BrokerHandler | None = None

    async def start(self, handler: BrokerHandler) -> None:
        self.handler = handler
        self._handlers.add(handler)

    async def publish(self, envelope: dict[str, Any]) -> None:
        await asyncio.gather(*(handler(envelope) for handler in list(self._handlers)))

    async def close(self) -> None:
        if self.handler is not None:
            self._handlers.discard(self.handler)
            self.handler = None


class RedisBroker:
    """Publish messages and run this server instance's Redis subscriber worker."""

    def __init__(self, redis: Any, channel: str = BROKER_CHANNEL) -> None:
        self.redis = redis
        self.channel = channel
        self.pubsub: Any | None = None
        self.task: asyncio.Task[None] | None = None

    async def start(self, handler: BrokerHandler) -> None:
        self.pubsub = self.redis.pubsub()
        await self.pubsub.subscribe(self.channel)
        self.task = asyncio.create_task(self._worker(handler))

    async def _worker(self, handler: BrokerHandler) -> None:
        assert self.pubsub is not None
        try:
            async for item in self.pubsub.listen():
                if item["type"] != "message":
                    continue
                raw = item["data"]
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                await handler(json.loads(raw))
        except asyncio.CancelledError:
            pass

    async def publish(self, envelope: dict[str, Any]) -> None:
        await self.redis.publish(self.channel, json.dumps(envelope, separators=(",", ":")))

    async def close(self) -> None:
        if self.task is not None:
            self.task.cancel()
            await self.task
            self.task = None
        if self.pubsub is not None:
            await self.pubsub.aclose()
            self.pubsub = None


class ClientRegistry:
    """Track sockets and subscriptions local to one server worker."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._subscriptions: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def add(self, client_id: str, connection: ServerConnection, channels: list[str]) -> None:
        with self._lock:
            self._clients[client_id] = connection
            for channel in channels:
                self._subscriptions.setdefault(channel, set()).add(client_id)

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in list(self._subscriptions):
                self._subscriptions[channel].discard(client_id)
                if not self._subscriptions[channel]:
                    del self._subscriptions[channel]

    def get(self, client_id: str) -> ServerConnection | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self, channel: str | None = None) -> list[tuple[str, ServerConnection]]:
        with self._lock:
            if channel is None:
                return list(self._clients.items())
            subscribers = self._subscriptions.get(channel, set())
            return [(key, value) for key, value in self._clients.items() if key in subscribers]

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            if client_id in self._clients:
                self._subscriptions.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._subscriptions.get(channel)
            if subscribers is not None:
                subscribers.discard(client_id)
                if not subscribers:
                    del self._subscriptions[channel]

    def is_subscribed(self, client_id: str, channel: str) -> bool:
        with self._lock:
            return client_id in self._subscriptions.get(channel, set())

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)


class NotificationServer:
    """Manage WebSocket clients and route messages through a shared backbone."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        *,
        redis_client: Any | None = None,
        database_url: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.server_id = str(uuid.uuid4())
        self.clients = ClientRegistry()
        self.messages = MessageStore(database_url or os.getenv("DATABASE_URL", ":memory:"))
        redis_url = os.getenv("REDIS_URL")
        if redis_client is None and redis_url:
            from redis.asyncio import from_url

            redis_client = from_url(redis_url)
            self._owns_redis = True
        else:
            self._owns_redis = False
        if redis_client is None:
            self.state: ConnectionState = MemoryConnectionState()
            self.broker: MessageBroker = MemoryBroker()
        else:
            self.state = RedisConnectionState(redis_client)
            self.broker = RedisBroker(redis_client)
        self._redis = redis_client
        self._server: Server | None = None

    @property
    def connected_count(self) -> int:
        return len(self.clients)

    @property
    def bound_port(self) -> int:
        if self._server is None or not self._server.sockets:
            raise RuntimeError("server is not running")
        return int(self._server.sockets[0].getsockname()[1])

    async def start(self) -> None:
        if self._server is not None:
            raise RuntimeError("server is already running")
        await self.broker.start(self._deliver)
        try:
            self._server = await serve(
                self.handle_connection,
                self.host,
                self.port,
                process_request=self.process_request,
            )
        except BaseException:
            await self.broker.close()
            raise

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None
        await self.broker.close()
        self.messages.close()
        if self._owns_redis and self._redis is not None:
            await self._redis.aclose()

    async def __aenter__(self) -> NotificationServer:
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.stop()

    async def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        """Serve HTTP API requests without a second framework or port."""
        del connection
        parsed = urlsplit(request.path)
        path = parsed.path
        if path == "/health":
            return self._json_response({"connected_clients": self.connected_count})
        if path == "/messages":
            try:
                query = parse_qs(parsed.query, keep_blank_values=True)
                limit = self._query_integer(query, "limit", 50)
                offset = self._query_integer(query, "offset", 0)
            except ValueError as exc:
                return self._json_response({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return self._json_response({"messages": self.messages.list(limit, offset)})
        if path == "/channels":
            return self._json_response({"channels": await self.state.channels()})

        prefix = "/channels/"
        suffix = "/subscribers"
        if path.startswith(prefix) and path.endswith(suffix):
            encoded_name = path[len(prefix) : -len(suffix)]
            if encoded_name and "/" not in encoded_name:
                channel = unquote(encoded_name)
                return self._json_response(
                    {"channel": channel, "subscribers": await self.state.subscribers(channel)}
                )
        return None

    @staticmethod
    def _query_integer(query: dict[str, list[str]], name: str, default: int) -> int:
        values = query.get(name)
        if values is None:
            return default
        if len(values) != 1:
            raise ValueError(f"{name} must be a non-negative integer")
        try:
            value = int(values[0])
        except ValueError as exc:
            raise ValueError(f"{name} must be a non-negative integer") from exc
        if value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
        return value

    @staticmethod
    def _json_response(
        payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK
    ) -> Response:
        body = json.dumps(payload).encode("utf-8")
        headers = Headers(
            {
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
                "Connection": "close",
            }
        )
        return Response(status, status.phrase, headers, body)

    async def handle_connection(self, connection: ServerConnection) -> None:
        query = parse_qs(urlsplit(connection.request.path).query)
        requested_ids = query.get("client_id", [])
        client_id = requested_ids[0] if len(requested_ids) == 1 and requested_ids[0] else str(uuid.uuid4())
        channels = await self.state.connect(client_id, self.server_id)
        self.clients.add(client_id, connection, channels)
        try:
            await self._send(
                connection,
                message("system", {"event": "connected", "client_id": client_id}),
            )
            async for raw_message in connection:
                await self.handle_message(client_id, raw_message)
        except ConnectionClosed:
            pass
        finally:
            self.clients.remove(client_id)
            await self.state.disconnect(client_id)

    async def handle_message(self, sender_id: str, raw_message: str | bytes) -> None:
        connection = self.clients.get(sender_id)
        if connection is None:
            return
        try:
            incoming = self._parse_message(raw_message)
        except ValueError as exc:
            await self._send(connection, message("system", {"error": str(exc)}))
            return

        message_type = incoming["type"]
        if message_type in {"subscribe", "unsubscribe"}:
            channel = incoming.get("channel", incoming["payload"].get("channel"))
            if not isinstance(channel, str) or not channel:
                await self._send(
                    connection, message("system", {"error": f"{message_type} requires channel"})
                )
                return
            if message_type == "subscribe":
                self.clients.subscribe(sender_id, channel)
                await self.state.subscribe(sender_id, channel)
            else:
                self.clients.unsubscribe(sender_id, channel)
                await self.state.unsubscribe(sender_id, channel)
            return

        target_id: str | None = None
        if message_type == "direct":
            target_id = incoming["payload"].get("client_id")
            if not isinstance(target_id, str) or not target_id:
                await self._send(
                    connection, message("system", {"error": "direct payload requires client_id"})
                )
                return
            if not await self.state.is_connected(target_id):
                await self._send(
                    connection,
                    message("system", {"error": "client not connected", "client_id": target_id}),
                )
                return

        self.messages.add(incoming)
        await self.broker.publish(
            {"notification": incoming, "channel": incoming.get("channel"), "target_id": target_id}
        )

    async def broadcast(
        self, notification: dict[str, Any], channel: str | None = None
    ) -> None:
        """Publish a server-originated notification through the shared backbone."""
        self.messages.add(notification)
        await self.broker.publish(
            {"notification": notification, "channel": channel, "target_id": None}
        )

    async def _deliver(self, envelope: dict[str, Any]) -> None:
        notification = envelope["notification"]
        target_id = envelope.get("target_id")
        channel = envelope.get("channel")
        if target_id is not None:
            target = self.clients.get(target_id)
            clients = [] if target is None else [(target_id, target)]
            if channel is not None and not self.clients.is_subscribed(target_id, channel):
                clients = []
        else:
            clients = self.clients.snapshot(channel)
        if not clients:
            return
        results = await asyncio.gather(
            *(self._send(connection, notification) for _, connection in clients),
            return_exceptions=True,
        )
        for (client_id, _), result in zip(clients, results):
            if isinstance(result, ConnectionClosed):
                self.clients.remove(client_id)
                await self.state.disconnect(client_id)

    @staticmethod
    def _parse_message(raw_message: str | bytes) -> dict[str, Any]:
        try:
            decoded = json.loads(raw_message)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("message must be valid JSON") from exc
        if not isinstance(decoded, dict):
            raise ValueError("message must be a JSON object")
        required_fields = {"type", "payload", "timestamp"}
        if set(decoded) not in (required_fields, required_fields | {"channel"}):
            raise ValueError("message requires type, payload, and timestamp")
        if decoded["type"] not in SUPPORTED_TYPES:
            raise ValueError("unsupported message type")
        if not isinstance(decoded["payload"], dict):
            raise ValueError("payload must be an object")
        if not isinstance(decoded["timestamp"], str) or not decoded["timestamp"]:
            raise ValueError("timestamp must be a non-empty string")
        if "channel" in decoded and (
            not isinstance(decoded["channel"], str) or not decoded["channel"]
        ):
            raise ValueError("channel must be a non-empty string")
        return decoded

    @staticmethod
    async def _send(connection: ServerConnection, notification: dict[str, Any]) -> None:
        await connection.send(json.dumps(notification, separators=(",", ":")))


async def run(host: str, port: int) -> None:
    server = NotificationServer(host, port)
    await server.start()
    assert server._server is not None
    await server._server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    try:
        asyncio.run(run(args.host, args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
