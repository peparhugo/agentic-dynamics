"""Async WebSocket notification server with an HTTP health endpoint."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs, unquote, urlsplit

import redis.asyncio as redis
from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response


SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
REDIS_MESSAGE_CHANNEL = "notifications:messages"


def sqlite_path(database_url: str) -> str:
    """Convert a SQLite URL (or plain path) to a sqlite3 path."""
    if database_url == "sqlite:///:memory:":
        return ":memory:"
    if database_url.startswith("sqlite:////"):
        return "/" + database_url[len("sqlite:////") :]
    if database_url.startswith("sqlite:///"):
        return database_url[len("sqlite:///") :]
    return database_url


def timestamp() -> str:
    """Return an ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"type": message_type, "payload": payload, "timestamp": timestamp()}


@dataclass(slots=True)
class Client:
    websocket: ServerConnection
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class ClientRegistry:
    """Thread-safe client and channel subscription state."""

    def __init__(self) -> None:
        self._clients: dict[str, Client] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def add(self, websocket: ServerConnection) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = Client(websocket)
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            empty_channels = []
            for channel, subscribers in self._channels.items():
                subscribers.discard(client_id)
                if not subscribers:
                    empty_channels.append(channel)
            for channel in empty_channels:
                del self._channels[channel]

    def get(self, client_id: str) -> Client | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> list[tuple[str, Client]]:
        with self._lock:
            return list(self._clients.items())

    def subscribe(self, client_id: str, channel: str) -> bool:
        with self._lock:
            if client_id not in self._clients:
                return False
            self._channels.setdefault(channel, set()).add(client_id)
            return True

    def unsubscribe(self, client_id: str, channel: str) -> bool:
        with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return False
            was_subscribed = client_id in subscribers
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]
            return was_subscribed

    def channel_snapshot(self, channel: str) -> list[tuple[str, Client]]:
        with self._lock:
            return [
                (client_id, self._clients[client_id])
                for client_id in self._channels.get(channel, set())
                if client_id in self._clients
            ]

    def channels(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"name": name, "subscriber_count": len(subscribers)}
                for name, subscribers in sorted(self._channels.items())
            ]

    def subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._clients)


class BaseTransport(ABC):
    """Interface between notification delivery and connected clients."""

    def __init__(self, registry: ClientRegistry | None = None) -> None:
        self.registry = registry or ClientRegistry()

    @abstractmethod
    async def on_connect(self, connection: Any) -> str:
        """Register a connection and return its client ID."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Remove a disconnected client."""

    @abstractmethod
    async def send_message(self, client_id: str, data: dict[str, Any]) -> bool:
        """Send a message to one client, returning whether it was delivered."""

    @abstractmethod
    async def broadcast(self, data: dict[str, Any]) -> None:
        """Send a message to all matching clients."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport interface."""

    async def on_connect(self, connection: ServerConnection) -> str:
        return self.registry.add(connection)

    async def on_disconnect(self, client_id: str) -> None:
        self.registry.remove(client_id)

    async def _send(self, client: Client, data: dict[str, Any]) -> bool:
        try:
            async with client.send_lock:
                await client.websocket.send(json.dumps(data))
            return True
        except ConnectionClosed:
            return False

    async def send_message(self, client_id: str, data: dict[str, Any]) -> bool:
        client = self.registry.get(client_id)
        if client is None:
            return False
        if await self._send(client, data):
            return True
        await self.on_disconnect(client_id)
        return False

    async def broadcast(self, data: dict[str, Any]) -> None:
        channel = data.get("channel")
        clients = (
            self.registry.channel_snapshot(channel)
            if isinstance(channel, str)
            else self.registry.snapshot()
        )
        results = await asyncio.gather(
            *(self._send(client, data) for _, client in clients),
            return_exceptions=True,
        )
        for (client_id, _), result in zip(clients, results, strict=True):
            if result is not True:
                await self.on_disconnect(client_id)

    async def handle_connection(
        self, websocket: ServerConnection, server: "NotificationServer"
    ) -> None:
        await server.start()
        client_id = await self.on_connect(websocket)
        await server.client_connected(client_id)
        try:
            await self.send_message(
                client_id,
                message("system", {"event": "connected", "client_id": client_id}),
            )
            async for raw_message in websocket:
                await server.handle_message(client_id, raw_message)
        except ConnectionClosed:
            pass
        finally:
            await self.on_disconnect(client_id)
            await server.client_disconnected(client_id)


def create_transport(
    name: str, registry: ClientRegistry | None = None
) -> BaseTransport:
    """Create the configured transport."""
    if name.lower() == "websocket":
        return WebSocketTransport(registry)
    raise ValueError(f"unsupported transport: {name}")


class MessageStore:
    """SQLite-backed message history."""

    def __init__(self, database_url: str) -> None:
        self.connection = sqlite3.connect(
            sqlite_path(database_url), check_same_thread=False
        )
        self.connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self.connection:
            self.connection.execute(
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

    async def save(self, data: dict[str, Any]) -> int:
        def insert() -> int:
            with self._lock, self.connection:
                cursor = self.connection.execute(
                    "INSERT INTO messages (channel, type, payload, timestamp) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        data.get("channel"),
                        data["type"],
                        json.dumps(data["payload"], separators=(",", ":")),
                        data["timestamp"],
                    ),
                )
                return int(cursor.lastrowid)

        return await asyncio.to_thread(insert)

    async def list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        def select() -> list[dict[str, Any]]:
            with self._lock:
                rows = self.connection.execute(
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

        return await asyncio.to_thread(select)


class RedisBackbone:
    """Redis pub/sub and shared client connection state."""

    def __init__(self, client: redis.Redis) -> None:
        self.client = client
        self.pubsub: Any | None = None
        self._listener: asyncio.Task[None] | None = None

    @classmethod
    def from_url(cls, url: str) -> "RedisBackbone":
        return cls(redis.from_url(url, decode_responses=True))

    async def start(
        self, callback: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> None:
        if self._listener is not None:
            return
        self.pubsub = self.client.pubsub()
        await self.pubsub.subscribe(REDIS_MESSAGE_CHANNEL)

        async def listen() -> None:
            assert self.pubsub is not None
            async for event in self.pubsub.listen():
                if event["type"] == "message":
                    await callback(json.loads(event["data"]))

        self._listener = asyncio.create_task(listen())

    async def publish(self, data: dict[str, Any]) -> None:
        await self.client.publish(
            REDIS_MESSAGE_CHANNEL, json.dumps(data, separators=(",", ":"))
        )

    async def register(self, client_id: str, server_id: str) -> None:
        await self.client.hset(
            f"notifications:client:{client_id}",
            mapping={"server_id": server_id, "connected_at": timestamp()},
        )
        await self.client.sadd("notifications:clients", client_id)

    async def unregister(self, client_id: str) -> None:
        channels = await self.client.smembers(
            f"notifications:client:{client_id}:channels"
        )
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.srem("notifications:clients", client_id)
            for channel in channels:
                pipe.srem(f"notifications:channel:{channel}", client_id)
            pipe.delete(
                f"notifications:client:{client_id}",
                f"notifications:client:{client_id}:channels",
            )
            await pipe.execute()

    async def subscribe_client(self, client_id: str, channel: str) -> None:
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.sadd(f"notifications:client:{client_id}:channels", channel)
            pipe.sadd(f"notifications:channel:{channel}", client_id)
            await pipe.execute()

    async def unsubscribe_client(self, client_id: str, channel: str) -> None:
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.srem(f"notifications:client:{client_id}:channels", channel)
            pipe.srem(f"notifications:channel:{channel}", client_id)
            await pipe.execute()

    async def is_connected(self, client_id: str) -> bool:
        return bool(await self.client.sismember("notifications:clients", client_id))

    async def is_subscribed(self, client_id: str, channel: str) -> bool:
        return bool(
            await self.client.sismember(
                f"notifications:channel:{channel}", client_id
            )
        )

    async def close(self) -> None:
        if self._listener is not None:
            self._listener.cancel()
            await asyncio.gather(self._listener, return_exceptions=True)
            self._listener = None
        if self.pubsub is not None:
            await self.pubsub.aclose()
            self.pubsub = None
        await self.client.aclose()


class NotificationServer:
    def __init__(
        self,
        registry: ClientRegistry | None = None,
        backbone: RedisBackbone | None = None,
        store: MessageStore | None = None,
        transport: BaseTransport | None = None,
    ) -> None:
        if transport is None:
            self.registry = registry or ClientRegistry()
            self.transport = create_transport(
                os.getenv("TRANSPORT", "websocket"), self.registry
            )
        else:
            self.registry = registry or transport.registry
            transport.registry = self.registry
            self.transport = transport
        self.backbone = backbone
        self.store = store or MessageStore(os.getenv("DATABASE_URL", ":memory:"))
        self.server_id = str(uuid.uuid4())

    async def start(self) -> None:
        if self.backbone is not None:
            await self.backbone.start(self._deliver)

    async def send_to(self, client_id: str, data: dict[str, Any]) -> bool:
        return await self.transport.send_message(client_id, data)

    async def broadcast(self, data: dict[str, Any]) -> None:
        await self.transport.broadcast(data)

    async def _deliver(self, data: dict[str, Any]) -> None:
        if data["type"] in {"broadcast", "system"}:
            await self.broadcast(data)
        else:
            await self.send_to(data["payload"]["target_id"], data)

    async def _distribute(self, data: dict[str, Any]) -> None:
        await self.store.save(data)
        if self.backbone is not None:
            await self.start()
            await self.backbone.publish(data)
        else:
            await self._deliver(data)

    async def _error(self, client_id: str, detail: str) -> None:
        await self.send_to(client_id, message("system", {"error": detail}))

    async def handle_message(self, client_id: str, raw_message: str | bytes) -> None:
        try:
            data = json.loads(raw_message)
        except (json.JSONDecodeError, UnicodeDecodeError):
            await self._error(client_id, "message must be valid JSON")
            return

        if not isinstance(data, dict):
            await self._error(client_id, "message must be a JSON object")
            return

        message_type = data.get("type")
        payload = data.get("payload")
        incoming_timestamp = data.get("timestamp")
        channel = data.get("channel")
        if message_type not in SUPPORTED_TYPES:
            await self._error(client_id, "unsupported message type")
            return
        if "channel" in data and (not isinstance(channel, str) or not channel):
            await self._error(client_id, "channel must be a non-empty string")
            return
        if message_type in {"subscribe", "unsubscribe"}:
            if channel is None:
                await self._error(client_id, f"{message_type} messages require a channel")
                return
            if message_type == "subscribe":
                self.registry.subscribe(client_id, channel)
                if self.backbone is not None:
                    await self.backbone.subscribe_client(client_id, channel)
            else:
                self.registry.unsubscribe(client_id, channel)
                if self.backbone is not None:
                    await self.backbone.unsubscribe_client(client_id, channel)
            return

        if not isinstance(payload, dict):
            await self._error(client_id, "payload must be an object")
            return
        if not isinstance(incoming_timestamp, str):
            await self._error(client_id, "timestamp must be a string")
            return

        outgoing = {
            "type": message_type,
            "payload": payload,
            "timestamp": incoming_timestamp,
        }
        if channel is not None:
            outgoing["channel"] = channel
        if message_type in {"broadcast", "system"}:
            await self._distribute(outgoing)
            return

        target_id = payload.get("target_id")
        if not isinstance(target_id, str) or not target_id:
            await self._error(client_id, "direct messages require payload.target_id")
            return
        if self.backbone is not None:
            target_connected = await self.backbone.is_connected(target_id)
            target_subscribed = channel is None or await self.backbone.is_subscribed(
                target_id, channel
            )
        else:
            target_connected = self.registry.get(target_id) is not None
            target_subscribed = channel is None or target_id in {
                subscriber_id
                for subscriber_id, _ in self.registry.channel_snapshot(channel)
            }
        if not target_subscribed:
            await self._error(client_id, "target client is not subscribed to channel")
            return
        if not target_connected:
            await self._error(client_id, "target client is not connected")
            return
        await self._distribute(outgoing)

    async def client_connected(self, client_id: str) -> None:
        if self.backbone is not None:
            await self.backbone.register(client_id, self.server_id)

    async def client_disconnected(self, client_id: str) -> None:
        if self.backbone is not None:
            await self.backbone.unregister(client_id)

    async def websocket_handler(self, websocket: ServerConnection) -> None:
        if not isinstance(self.transport, WebSocketTransport):
            raise RuntimeError("websocket handler requires the websocket transport")
        await self.transport.handle_connection(websocket, self)

    async def process_request(
        self, _connection: ServerConnection, request: Request
    ) -> Response | None:
        path = request.path.partition("?")[0]
        if path == "/health":
            return self._json_response(
                HTTPStatus.OK, {"connected_clients": self.registry.count}
            )
        if path == "/channels":
            return self._json_response(
                HTTPStatus.OK, {"channels": self.registry.channels()}
            )
        prefix, suffix = "/channels/", "/subscribers"
        if path.startswith(prefix) and path.endswith(suffix):
            channel = unquote(path[len(prefix) : -len(suffix)])
            if channel and "/" not in channel:
                return self._json_response(
                    HTTPStatus.OK,
                    {
                        "channel": channel,
                        "subscribers": self.registry.subscribers(channel),
                    },
                )
        if path == "/messages":
            query = parse_qs(urlsplit(request.path).query)
            try:
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
                if not 1 <= limit <= 1000 or offset < 0:
                    raise ValueError
            except ValueError:
                return self._json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "limit must be 1-1000 and offset must be non-negative"},
                )
            return self._json_response(
                HTTPStatus.OK, {"messages": await self.store.list(limit, offset)}
            )
        if path not in {"/", "/ws"}:
            return self._json_response(HTTPStatus.NOT_FOUND, {"error": "not found"})
        return None

    @staticmethod
    def _json_response(status: HTTPStatus, data: dict[str, Any]) -> Response:
        body = json.dumps(data, separators=(",", ":")).encode()
        return Response(
            status,
            status.phrase,
            Headers(
                [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(body))),
                ]
            ),
            body,
        )


async def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    backbone = RedisBackbone.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    notification_server = NotificationServer(
        backbone=backbone,
        store=MessageStore(os.getenv("DATABASE_URL", "messages.db")),
    )
    await notification_server.start()
    try:
        async with serve(
            notification_server.websocket_handler,
            host,
            port,
            process_request=notification_server.process_request,
        ):
            await asyncio.get_running_loop().create_future()
    finally:
        await backbone.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8765")))
    args = parser.parse_args()
    try:
        asyncio.run(run(args.host, args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
