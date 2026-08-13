"""Async WebSocket notification server backed by Redis and SQLite."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import threading
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs, unquote, urlsplit

import redis.asyncio as redis
from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response


SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
CONTROL_TYPES = {"subscribe", "unsubscribe"}
BROKER_CHANNEL = "notification-server:messages"
REDIS_PREFIX = "notification-server"


def timestamp() -> str:
    """Return an ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def message(
    message_type: str, payload: dict[str, Any], channel: str | None = None
) -> str:
    data = {"type": message_type, "payload": payload, "timestamp": timestamp()}
    if channel is not None:
        data["channel"] = channel
    return json.dumps(data, separators=(",", ":"))


class MessageStore:
    """Thread-safe SQLite message history."""

    def __init__(self, database_url: str) -> None:
        self.path = self._path_from_url(database_url)
        if self.path != ":memory:":
            Path(self.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._connection:
            self._connection.execute(
                """CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT,
                    type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )"""
            )

    @staticmethod
    def _path_from_url(database_url: str) -> str:
        if database_url == "sqlite:///:memory:":
            return ":memory:"
        if database_url.startswith("sqlite:////"):
            return "/" + database_url[len("sqlite:////") :]
        if database_url.startswith("sqlite:///"):
            return database_url[len("sqlite:///") :]
        raise ValueError("DATABASE_URL must be a sqlite:/// URL")

    def add(self, data: dict[str, Any]) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (
                    data.get("channel"),
                    data["type"],
                    json.dumps(data["payload"], separators=(",", ":")),
                    data["timestamp"],
                ),
            )

    def list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """SELECT id, channel, type, payload, timestamp
                   FROM messages ORDER BY id DESC LIMIT ? OFFSET ?""",
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


class ClientRegistry:
    """Registry of transport connections owned by this server instance."""

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._subscriptions: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def add(self, connection: Any) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = connection
        return client_id

    def remove(self, client_id: str) -> list[str]:
        removed_channels: list[str] = []
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in list(self._subscriptions):
                subscribers = self._subscriptions[channel]
                if client_id in subscribers:
                    removed_channels.append(channel)
                    subscribers.remove(client_id)
                if not subscribers:
                    del self._subscriptions[channel]
        return removed_channels

    def get(self, client_id: str) -> Any | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self, channel: str | None = None) -> list[Any]:
        with self._lock:
            if channel is not None:
                return [
                    self._clients[client_id]
                    for client_id in self._subscriptions.get(channel, set())
                    if client_id in self._clients
                ]
            return list(self._clients.values())

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            if client_id in self._clients:
                self._subscriptions.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._subscriptions.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._subscriptions[channel]

    def is_subscribed(self, client_id: str, channel: str) -> bool:
        with self._lock:
            return client_id in self._subscriptions.get(channel, set())

    def channels(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"name": name, "subscriber_count": len(subscribers)}
                for name, subscribers in sorted(self._subscriptions.items())
            ]

    def subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._subscriptions.get(channel, set()))

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._clients)


class LocalBroker:
    """Development fallback retaining the broker/worker delivery boundary."""

    def __init__(self) -> None:
        self.callback: Callable[[str], Awaitable[None]] | None = None

    async def start(self, callback: Callable[[str], Awaitable[None]]) -> None:
        self.callback = callback

    async def publish(self, data: str) -> None:
        if self.callback is not None:
            await self.callback(data)

    async def stop(self) -> None:
        self.callback = None


class RedisBroker:
    """Redis publisher and subscription worker."""

    def __init__(self, client: redis.Redis) -> None:
        self.client = client
        self._pubsub: Any = None
        self._task: asyncio.Task[None] | None = None

    async def start(self, callback: Callable[[str], Awaitable[None]]) -> None:
        self._pubsub = self.client.pubsub()
        await self._pubsub.subscribe(BROKER_CHANNEL)

        async def consume() -> None:
            assert self._pubsub is not None
            async for item in self._pubsub.listen():
                if item["type"] != "message":
                    continue
                data = item["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                await callback(data)

        self._task = asyncio.create_task(consume())

    async def publish(self, data: str) -> None:
        await self.client.publish(BROKER_CHANNEL, data)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        if self._pubsub is not None:
            await self._pubsub.aclose()
            self._pubsub = None


class BaseTransport(ABC):
    """Interface between notification handling and client delivery."""

    def __init__(self, notification_server: NotificationServer) -> None:
        self.notification_server = notification_server
        self.clients = ClientRegistry()

    @abstractmethod
    async def on_connect(self, connection: Any) -> str:
        """Register a newly connected client and return its ID."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Remove a disconnected client."""

    @abstractmethod
    async def send_message(self, connection: Any, data: str) -> None:
        """Send one message to one transport connection."""

    @abstractmethod
    async def broadcast(self, data: str, channel: str | None = None) -> None:
        """Send one message to all matching local connections."""

    async def start(self) -> None:
        """Start accepting transport connections."""

    async def stop(self) -> None:
        """Stop accepting transport connections."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport."""

    def __init__(self, notification_server: NotificationServer) -> None:
        super().__init__(notification_server)
        self.server: Server | None = None

    async def on_connect(self, connection: ServerConnection) -> str:
        client_id = self.clients.add(connection)
        await self.notification_server._register_client(client_id)
        await self.send_message(
            connection, message("system", {"event": "connected", "client_id": client_id})
        )
        return client_id

    async def on_disconnect(self, client_id: str) -> None:
        channels = self.clients.remove(client_id)
        await self.notification_server._remove_client(client_id, channels)

    async def send_message(self, connection: ServerConnection, data: str) -> None:
        try:
            await connection.send(data)
        except Exception:
            return

    async def broadcast(self, data: str, channel: str | None = None) -> None:
        recipients = self.clients.snapshot(channel)
        if recipients:
            await asyncio.gather(*(self.send_message(client, data) for client in recipients))

    async def handler(self, connection: ServerConnection) -> None:
        client_id = await self.on_connect(connection)
        try:
            async for raw in connection:
                await self.notification_server.process_message(client_id, connection, raw)
        finally:
            await self.on_disconnect(client_id)

    async def start(self) -> None:
        server = self.notification_server
        self.server = await serve(
            self.handler, server.host, server.port, process_request=server.process_request
        )
        if self.server.sockets:
            server.port = self.server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            self.server = None


TRANSPORTS: dict[str, type[BaseTransport]] = {"websocket": WebSocketTransport}


class NotificationServer:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        *,
        redis_url: str | None = None,
        database_url: str | None = None,
        redis_client: redis.Redis | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.server_id = str(uuid.uuid4())
        self.redis = redis_client
        configured_redis_url = redis_url if redis_url is not None else os.getenv("REDIS_URL")
        if self.redis is None and configured_redis_url:
            self.redis = redis.from_url(configured_redis_url, decode_responses=False)
        self._owns_redis = self.redis is not None and redis_client is None
        self.broker = RedisBroker(self.redis) if self.redis is not None else LocalBroker()
        configured_database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///:memory:")
        self.messages = MessageStore(configured_database_url)
        transport_name = os.getenv("TRANSPORT", "websocket").strip().lower()
        try:
            transport_type = TRANSPORTS[transport_name]
        except KeyError as error:
            supported = ", ".join(sorted(TRANSPORTS))
            raise ValueError(
                f"unsupported TRANSPORT {transport_name!r}; expected one of: {supported}"
            ) from error
        self.transport = transport_type(self)
        self.clients = self.transport.clients
        self._server: Server | None = None
        self._running = False

    @staticmethod
    def _client_key(client_id: str) -> str:
        return f"{REDIS_PREFIX}:client:{client_id}:channels"

    @staticmethod
    def _channel_key(channel: str) -> str:
        return f"{REDIS_PREFIX}:channel:{channel}:subscribers"

    async def _register_client(self, client_id: str) -> None:
        if self.redis is not None:
            await self.redis.hset(f"{REDIS_PREFIX}:clients", client_id, self.server_id)

    async def _remove_client(self, client_id: str, channels: list[str]) -> None:
        if self.redis is None:
            return
        stored_channels = await self.redis.smembers(self._client_key(client_id))
        names = {
            value.decode("utf-8") if isinstance(value, bytes) else value
            for value in stored_channels
        }
        names.update(channels)
        pipeline = self.redis.pipeline()
        pipeline.hdel(f"{REDIS_PREFIX}:clients", client_id)
        pipeline.delete(self._client_key(client_id))
        for channel in names:
            pipeline.srem(self._channel_key(channel), client_id)
        await pipeline.execute()
        for channel in names:
            if not await self.redis.scard(self._channel_key(channel)):
                await self.redis.srem(f"{REDIS_PREFIX}:channels", channel)

    async def _subscribe(self, client_id: str, channel: str) -> None:
        self.clients.subscribe(client_id, channel)
        if self.redis is not None:
            pipeline = self.redis.pipeline()
            pipeline.sadd(self._client_key(client_id), channel)
            pipeline.sadd(self._channel_key(channel), client_id)
            pipeline.sadd(f"{REDIS_PREFIX}:channels", channel)
            await pipeline.execute()

    async def _unsubscribe(self, client_id: str, channel: str) -> None:
        self.clients.unsubscribe(client_id, channel)
        if self.redis is not None:
            pipeline = self.redis.pipeline()
            pipeline.srem(self._client_key(client_id), channel)
            pipeline.srem(self._channel_key(channel), client_id)
            await pipeline.execute()
            if not await self.redis.scard(self._channel_key(channel)):
                await self.redis.srem(f"{REDIS_PREFIX}:channels", channel)

    async def _client_exists(self, client_id: str) -> bool:
        if self.clients.get(client_id) is not None:
            return True
        return bool(
            self.redis is not None
            and await self.redis.hexists(f"{REDIS_PREFIX}:clients", client_id)
        )

    async def _deliver(self, raw: str) -> None:
        data = json.loads(raw)
        message_type = data["type"]
        channel = data.get("channel")
        if message_type == "direct":
            target_id = data["payload"].get("target_id")
            target = self.clients.get(target_id) if isinstance(target_id, str) else None
            if target is not None and (
                channel is None or self.clients.is_subscribed(target_id, channel)
            ):
                await self.transport.send_message(target, raw)
            return
        await self.transport.broadcast(raw, channel)

    async def broadcast(self, data: str, channel: str | None = None) -> None:
        """Compatibility helper that delivers directly to local clients."""
        await self.transport.broadcast(data, channel)

    async def process_message(
        self, client_id: str, connection: Any, raw: str | bytes
    ) -> None:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            await self.transport.send_message(
                connection, message("system", {"error": "invalid JSON"})
            )
            return
        if not isinstance(data, dict):
            await self.transport.send_message(
                connection, message("system", {"error": "message must be an object"})
            )
            return

        message_type = data.get("type")
        payload = data.get("payload")
        if message_type not in SUPPORTED_TYPES:
            await self.transport.send_message(
                connection,
                message("system", {"error": "type must be supported and payload must be an object"})
            )
            return
        channel = data.get("channel")
        if channel is None and message_type in CONTROL_TYPES and isinstance(payload, dict):
            channel = payload.get("channel")
        if channel is not None and (not isinstance(channel, str) or not channel.strip()):
            await self.transport.send_message(
                connection, message("system", {"error": "channel must be a non-empty string"})
            )
            return
        if message_type in CONTROL_TYPES:
            if channel is None:
                await self.transport.send_message(
                    connection, message("system", {"error": "channel must be a non-empty string"})
                )
                return
            if message_type == "subscribe":
                await self._subscribe(client_id, channel)
            else:
                await self._unsubscribe(client_id, channel)
            return
        if not isinstance(payload, dict):
            await self.transport.send_message(
                connection,
                message("system", {"error": "type must be supported and payload must be an object"})
            )
            return
        if message_type == "direct":
            target_id = payload.get("target_id")
            if not isinstance(target_id, str) or not await self._client_exists(target_id):
                await self.transport.send_message(
                    connection, message("system", {"error": "target client not found"})
                )
                return

        outgoing_data = {"type": message_type, "payload": payload, "timestamp": timestamp()}
        if channel is not None:
            outgoing_data["channel"] = channel
        self.messages.add(outgoing_data)
        await self.broker.publish(json.dumps(outgoing_data, separators=(",", ":")))

    async def handler(self, websocket: ServerConnection) -> None:
        """Compatibility entry point for the default WebSocket transport."""
        if not isinstance(self.transport, WebSocketTransport):
            raise RuntimeError("handler is only available for the WebSocket transport")
        await self.transport.handler(websocket)

    @staticmethod
    def _response(status: HTTPStatus, data: dict[str, Any]) -> Response:
        body = json.dumps(data).encode("utf-8")
        headers = Headers(
            [("Content-Type", "application/json"), ("Content-Length", str(len(body))), ("Connection", "close")]
        )
        return Response(status, status.phrase, headers, body)

    async def _connection_count(self) -> int:
        if self.redis is None:
            return self.clients.count
        return int(await self.redis.hlen(f"{REDIS_PREFIX}:clients"))

    async def _channels(self) -> list[dict[str, Any]]:
        if self.redis is None:
            return self.clients.channels()
        values = await self.redis.smembers(f"{REDIS_PREFIX}:channels")
        names = sorted(value.decode() if isinstance(value, bytes) else value for value in values)
        return [
            {"name": name, "subscriber_count": int(await self.redis.scard(self._channel_key(name)))}
            for name in names
            if await self.redis.scard(self._channel_key(name))
        ]

    async def _subscribers(self, channel: str) -> list[str]:
        if self.redis is None:
            return self.clients.subscribers(channel)
        values = await self.redis.smembers(self._channel_key(channel))
        return sorted(value.decode() if isinstance(value, bytes) else value for value in values)

    async def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        del connection
        parsed = urlsplit(request.path)
        path = parsed.path
        if path == "/health":
            response_data: dict[str, Any] = {"connected_clients": await self._connection_count()}
        elif path == "/messages":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
                if not 1 <= limit <= 1000 or offset < 0:
                    raise ValueError
            except (TypeError, ValueError):
                return self._response(HTTPStatus.BAD_REQUEST, {"error": "invalid limit or offset"})
            response_data = {"messages": self.messages.list(limit, offset)}
        elif path == "/channels":
            response_data = {"channels": await self._channels()}
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            encoded_name = path[len("/channels/") : -len("/subscribers")].rstrip("/")
            if not encoded_name or "/" in encoded_name:
                return None
            channel = unquote(encoded_name)
            response_data = {"channel": channel, "subscribers": await self._subscribers(channel)}
        else:
            return None
        return self._response(HTTPStatus.OK, response_data)

    async def start(self) -> None:
        if self._running:
            raise RuntimeError("server is already running")
        await self.broker.start(self._deliver)
        try:
            await self.transport.start()
        except Exception:
            await self.broker.stop()
            raise
        if isinstance(self.transport, WebSocketTransport):
            self._server = self.transport.server
        self._running = True

    async def stop(self) -> None:
        await self.transport.stop()
        self._server = None
        self._running = False
        await self.broker.stop()
        if self._owns_redis and self.redis is not None:
            await self.redis.aclose()
        self.messages.close()

    async def run_forever(self) -> None:
        await self.start()
        if self._server is not None:
            await self._server.serve_forever()
        else:
            await asyncio.Future()


def main() -> None:
    parser = argparse.ArgumentParser(description="WebSocket notification server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        asyncio.run(NotificationServer(args.host, args.port).run_forever())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
