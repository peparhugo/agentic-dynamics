"""Async pluggable notification server with a small HTTP health endpoint."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from urllib.parse import unquote, urlsplit

import redis.asyncio as redis
import websockets
from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.http11 import Headers, Request, Response


SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
REDIS_CHANNEL = "notification-server:messages"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _message(message_type: str, payload: dict[str, Any], channel: str | None = None) -> str:
    message: dict[str, Any] = {
        "type": message_type,
        "payload": payload,
        "timestamp": _timestamp(),
    }
    if channel is not None:
        message["channel"] = channel
    return json.dumps(message)


class BaseTransport(ABC):
    """Interface used by the notification core to communicate with clients."""

    def __init__(self) -> None:
        self.clients: dict[str, Any] = {}

    @abstractmethod
    async def on_connect(self, client_id: str, connection: Any) -> None:
        """Register a newly connected client."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Unregister a client."""

    @abstractmethod
    async def send_message(self, client_id: str, message: str) -> bool:
        """Send a message, returning false if the client is disconnected."""

    @abstractmethod
    async def broadcast(self, message: str, client_ids: set[str]) -> set[str]:
        """Send a message and return clients that could not receive it."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of :class:`BaseTransport`."""

    def __init__(self) -> None:
        super().__init__()
        self._server: Server | None = None

    async def on_connect(self, client_id: str, connection: ServerConnection) -> None:
        self.clients[client_id] = connection

    async def on_disconnect(self, client_id: str) -> None:
        self.clients.pop(client_id, None)

    async def send_message(self, client_id: str, message: str) -> bool:
        connection = self.clients.get(client_id)
        if connection is None:
            return False
        try:
            await connection.send(message)
        except websockets.exceptions.ConnectionClosed:
            self.clients.pop(client_id, None)
            return False
        return True

    async def broadcast(self, message: str, client_ids: set[str]) -> set[str]:
        disconnected: set[str] = set()
        for client_id in list(client_ids):
            if not await self.send_message(client_id, message):
                disconnected.add(client_id)
        return disconnected

    async def start(
        self,
        handler: Callable[[str, str], Awaitable[None]],
        host: str,
        port: int,
        process_request: Callable[[ServerConnection, Request], Awaitable[Response | None]],
        on_connect: Callable[[str], Awaitable[None]],
        on_disconnect: Callable[[str], Awaitable[None]],
    ) -> None:
        async def connection_handler(connection: ServerConnection) -> None:
            client_id = str(uuid.uuid4())
            await self.on_connect(client_id, connection)
            await on_connect(client_id)
            try:
                async for raw in connection:
                    await handler(client_id, raw)
            finally:
                await self.on_disconnect(client_id)
                await on_disconnect(client_id)

        self._server = await serve(
            connection_handler,
            host,
            port,
            process_request=process_request,
        )

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None


class NotificationServer:
    """Manage clients and route notification messages through a transport."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        redis_url: str | None = None,
        database_url: str | None = None,
        transport: BaseTransport | None = None,
    ) -> None:
        self.host = host
        self.port = port
        transport_name = os.getenv("TRANSPORT", "websocket").lower()
        if transport is None:
            if transport_name != "websocket":
                raise ValueError(f"unsupported transport: {transport_name}")
            transport = WebSocketTransport()
        self.transport = transport
        self.clients = transport.clients
        self.channels: dict[str, set[str]] = {}
        self._client_channels: dict[str, set[str]] = {}
        self._server: Any = None
        self.redis_url = redis_url if redis_url is not None else os.getenv("REDIS_URL")
        self.database_url = database_url or os.getenv("DATABASE_URL", "messages.db")
        self._redis: redis.Redis | None = None
        self._pubsub: redis.client.PubSub | None = None
        self._redis_task: asyncio.Task[None] | None = None
        self._server_id = str(uuid.uuid4())
        self._database = self._sqlite_path(self.database_url)
        self._init_database()

    @staticmethod
    def _sqlite_path(database_url: str) -> str:
        if database_url.startswith("sqlite:///"):
            return database_url[9:]
        if database_url.startswith("sqlite://"):
            return database_url[9:]
        return database_url

    def _init_database(self) -> None:
        with sqlite3.connect(self._database) as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT,
                    type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )"""
            )

    async def _save_message(self, message: dict[str, Any]) -> None:
        await asyncio.to_thread(self._save_message_sync, message)

    def _save_message_sync(self, message: dict[str, Any]) -> None:
        with sqlite3.connect(self._database) as connection:
            connection.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (
                    message.get("channel"),
                    message["type"],
                    json.dumps(message["payload"]),
                    message["timestamp"],
                ),
            )

    async def _get_messages(self, limit: int, offset: int) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._get_messages_sync, limit, offset)

    def _get_messages_sync(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with sqlite3.connect(self._database) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id LIMIT ? OFFSET ?",
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

    @property
    def client_count(self) -> int:
        return len(self.clients)

    async def _process_request(
        self, _connection: ServerConnection, request: Request
    ) -> Response | None:
        path = urlsplit(request.path).path
        if path == "/health":
            body = json.dumps({"connected_clients": self.client_count}).encode()
        elif path == "/channels":
            body = json.dumps(
                {"channels": {name: len(client_ids) for name, client_ids in self.channels.items()}}
            ).encode()
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            name = unquote(path[len("/channels/") : -len("/subscribers")]).rstrip("/")
            body = json.dumps(
                {"channel": name, "subscribers": sorted(self.channels.get(name, set()))}
            ).encode()
        elif path == "/messages":
            query = dict(part.split("=", 1) for part in urlsplit(request.path).query.split("&") if "=" in part)
            try:
                limit = max(0, min(1000, int(query.get("limit", "50"))))
                offset = max(0, int(query.get("offset", "0")))
            except ValueError:
                return Response(400, "Bad Request", Headers(), b"invalid limit or offset")
            body = json.dumps({"messages": await self._get_messages(limit, offset)}).encode()
        else:
            return None
        return Response(
            200,
            "OK",
            Headers(
                [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(body))),
                ]
            ),
            body,
        )

    async def _send_error(self, client_id: str, detail: str) -> None:
        await self.transport.send_message(client_id, _message("system", {"error": detail}))

    async def _broadcast(self, message: str, channel: str | None = None) -> None:
        recipient_ids = (
            self.channels.get(channel, set()) if channel is not None else set(self.clients)
        )
        disconnected = await self.transport.broadcast(message, set(recipient_ids))
        for client_id in disconnected:
            self._remove_client(client_id)

    async def _deliver_redis(self, event: dict[str, Any]) -> None:
        if event.get("kind") == "broadcast":
            await self._broadcast(event["message"], event.get("channel"))
        elif event.get("kind") == "direct":
            target = self.clients.get(event.get("target_client_id"))
            if target is not None:
                delivered = await self.transport.send_message(
                    event["target_client_id"], event["message"]
                )
                if not delivered:
                    self._remove_client(event["target_client_id"])

    async def _redis_listener(self) -> None:
        assert self._pubsub is not None
        async for item in self._pubsub.listen():
            if item["type"] == "message":
                event = json.loads(item["data"])
                if event.get("server_id") != self._server_id:
                    await self._deliver_redis(event)

    async def _publish_or_deliver(self, event: dict[str, Any]) -> None:
        if self._redis is None:
            await self._deliver_redis(event)
        else:
            await self._deliver_redis(event)
            await self._redis.publish(REDIS_CHANNEL, json.dumps(event))

    def _remove_client(self, client_id: str) -> None:
        self.clients.pop(client_id, None)
        for channel in self._client_channels.pop(client_id, set()):
            subscribers = self.channels.get(channel)
            if subscribers is not None:
                subscribers.discard(client_id)
                if not subscribers:
                    self.channels.pop(channel, None)

    def _set_subscription(self, client_id: str, channel: str, subscribed: bool) -> None:
        if subscribed:
            self.channels.setdefault(channel, set()).add(client_id)
            self._client_channels.setdefault(client_id, set()).add(channel)
            return
        self.channels.get(channel, set()).discard(client_id)
        if channel in self.channels and not self.channels[channel]:
            self.channels.pop(channel)
        client_channels = self._client_channels.get(client_id)
        if client_channels is not None:
            client_channels.discard(channel)
            if not client_channels:
                self._client_channels.pop(client_id)

    async def _handle_message(self, client_id: str, raw: str) -> None:
        try:
            incoming = json.loads(raw)
        except json.JSONDecodeError:
            await self._send_error(client_id, "message must be valid JSON")
            return

        message_type = incoming.get("type") if isinstance(incoming, dict) else None
        payload = incoming.get("payload") if isinstance(incoming, dict) else None
        if message_type not in SUPPORTED_TYPES:
            await self._send_error(client_id, "unsupported message type")
            return
        if message_type in {"subscribe", "unsubscribe"} and payload is None:
            payload = {}
        if not isinstance(payload, dict):
            await self._send_error(client_id, "payload must be an object")
            return

        channel = incoming.get("channel")
        if channel is None:
            channel = payload.get("channel")
        if message_type in {"subscribe", "unsubscribe"}:
            if not isinstance(channel, str) or not channel:
                await self._send_error(client_id, "channel must be a non-empty string")
                return
            self._set_subscription(client_id, channel, message_type == "subscribe")
            if self._redis is not None:
                await self._redis.hset(
                    f"notification-server:client:{client_id}",
                    mapping={"server_id": self._server_id, "channels": json.dumps(sorted(self._client_channels.get(client_id, set())))},
                )
            return

        if channel is not None and not isinstance(channel, str):
            await self._send_error(client_id, "channel must be a string")
            return

        outgoing = _message(message_type, payload, channel)
        outgoing_data = json.loads(outgoing)
        await self._save_message(outgoing_data)
        if message_type in {"broadcast", "system"}:
            await self._publish_or_deliver({"kind": "broadcast", "server_id": self._server_id, "channel": channel, "message": outgoing})
            return

        target_id = payload.get("client_id", payload.get("target_client_id"))
        target_exists = target_id in self.clients
        if not target_exists and self._redis is not None:
            target_exists = bool(await self._redis.exists(f"notification-server:client:{target_id}"))
        if not target_exists:
            await self._send_error(client_id, "target client not found")
            return
        await self._publish_or_deliver({"kind": "direct", "server_id": self._server_id, "target_client_id": target_id, "message": outgoing})

    async def _on_disconnect(self, client_id: str) -> None:
        self._remove_client(client_id)
        if self._redis is not None:
            await self._redis.delete(f"notification-server:client:{client_id}")

    async def _on_connect(self, client_id: str) -> None:
        if self._redis is not None:
            await self._redis.hset(
                f"notification-server:client:{client_id}",
                mapping={"server_id": self._server_id, "channels": "[]"},
            )

    async def start(self) -> None:
        """Start serving. The returned server runs until :meth:`stop` is called."""
        if self.redis_url:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
            await self._redis.ping()
            self._pubsub = self._redis.pubsub()
            await self._pubsub.subscribe(REDIS_CHANNEL)
            self._redis_task = asyncio.create_task(self._redis_listener())
        start = getattr(self.transport, "start", None)
        if start is None:
            raise TypeError("transport must provide start()")
        await start(
            self._handle_message,
            self.host,
            self.port,
            self._process_request,
            self._on_connect,
            self._on_disconnect,
        )
        self._server = getattr(self.transport, "_server", self.transport)
        sockets = getattr(self._server, "sockets", None)
        if sockets:
            self.port = sockets[0].getsockname()[1]

    async def stop(self) -> None:
        stop = getattr(self.transport, "stop", None)
        if stop is not None:
            await stop()
        self._server = None
        if self._redis_task is not None:
            self._redis_task.cancel()
            await asyncio.gather(self._redis_task, return_exceptions=True)
            self._redis_task = None
        if self._pubsub is not None:
            await self._pubsub.close()
            self._pubsub = None
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
        self.clients.clear()
        self.channels.clear()
        self._client_channels.clear()

    async def __aenter__(self) -> "NotificationServer":
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.stop()


async def create_server(host: str = "127.0.0.1", port: int = 8765, **kwargs: Any) -> NotificationServer:
    """Create and start a notification server, useful for application embedding."""
    server = NotificationServer(host, port, **kwargs)
    await server.start()
    return server


async def main(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = await create_server(host, port)
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        asyncio.run(main(args.host, args.port))
    except KeyboardInterrupt:
        pass
