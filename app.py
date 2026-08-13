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
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs, unquote, urlsplit

from redis.asyncio import Redis
from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response


SUPPORTED_TYPES = {"broadcast", "direct", "subscribe", "unsubscribe", "system"}
REDIS_CHANNEL = "notifications:messages"


def utc_timestamp() -> str:
    """Return an ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def message(
    message_type: str,
    payload: dict[str, Any],
    channel: str | None = None,
) -> dict[str, Any]:
    outgoing = {
        "type": message_type,
        "payload": payload,
        "timestamp": utc_timestamp(),
    }
    if channel is not None:
        outgoing["channel"] = channel
    return outgoing


class MessageStore:
    """Thread-safe SQLite storage for delivered application messages."""

    def __init__(self, database_url: str) -> None:
        path = self._path(database_url)
        if path != ":memory:":
            Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
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

    @staticmethod
    def _path(database_url: str) -> str:
        if database_url == "sqlite:///:memory:" or database_url == ":memory:":
            return ":memory:"
        if database_url.startswith("sqlite:////"):
            return "/" + database_url[len("sqlite:////") :]
        if database_url.startswith("sqlite:///"):
            return database_url[len("sqlite:///") :]
        return database_url

    def add(self, outgoing: dict[str, Any]) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (
                    outgoing.get("channel"),
                    outgoing["type"],
                    json.dumps(outgoing["payload"]),
                    outgoing["timestamp"],
                ),
            )
            return int(cursor.lastrowid)

    def list(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
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

    def close(self) -> None:
        with self._lock:
            self._connection.close()


class RedisBackbone:
    """Redis pub/sub transport plus shared client presence and subscriptions."""

    def __init__(self, redis_url: str, redis: Redis | None = None) -> None:
        self.redis = redis or Redis.from_url(redis_url, decode_responses=True)
        self.instance_id = str(uuid.uuid4())
        self._pubsub: Any = None
        self._listener: asyncio.Task[None] | None = None

    async def start(
        self, receiver: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> None:
        if self._listener is not None:
            return
        self._pubsub = self.redis.pubsub()
        await self._pubsub.subscribe(REDIS_CHANNEL)
        self._listener = asyncio.create_task(self._listen(receiver))

    async def _listen(
        self, receiver: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> None:
        try:
            async for item in self._pubsub.listen():
                if item["type"] == "message":
                    await receiver(json.loads(item["data"]))
        except asyncio.CancelledError:
            raise

    async def publish(self, event: dict[str, Any]) -> None:
        await self.redis.publish(REDIS_CHANNEL, json.dumps(event))

    async def add_client(self, client_id: str) -> None:
        await self.redis.hset("notifications:clients", client_id, self.instance_id)

    async def remove_client(self, client_id: str) -> None:
        channels = await self.redis.smembers(f"notifications:client:{client_id}:channels")
        pipeline = self.redis.pipeline()
        pipeline.hdel("notifications:clients", client_id)
        for channel in channels:
            pipeline.srem(f"notifications:channel:{channel}", client_id)
        pipeline.delete(f"notifications:client:{client_id}:channels")
        await pipeline.execute()

    async def subscribe(self, client_id: str, channel: str) -> None:
        pipeline = self.redis.pipeline()
        pipeline.sadd(f"notifications:channel:{channel}", client_id)
        pipeline.sadd(f"notifications:client:{client_id}:channels", channel)
        await pipeline.execute()

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        pipeline = self.redis.pipeline()
        pipeline.srem(f"notifications:channel:{channel}", client_id)
        pipeline.srem(f"notifications:client:{client_id}:channels", channel)
        await pipeline.execute()

    async def client_exists(self, client_id: str) -> bool:
        return bool(await self.redis.hexists("notifications:clients", client_id))

    async def is_subscribed(self, client_id: str, channel: str) -> bool:
        return bool(await self.redis.sismember(f"notifications:channel:{channel}", client_id))

    async def close(self) -> None:
        if self._listener is not None:
            self._listener.cancel()
            await asyncio.gather(self._listener, return_exceptions=True)
            self._listener = None
        if self._pubsub is not None:
            await self._pubsub.aclose()
            self._pubsub = None
        await self.redis.aclose()


@dataclass(frozen=True)
class Client:
    id: str
    connection: Any


class ClientRegistry:
    """A thread-safe registry of connected transport clients."""

    def __init__(self) -> None:
        self._clients: dict[str, Client] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def add(self, connection: Any) -> Client:
        client = Client(str(uuid.uuid4()), connection)
        with self._lock:
            self._clients[client.id] = client
        return client

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in tuple(self._channels):
                subscribers = self._channels[channel]
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[channel]

    def get(self, client_id: str) -> Client | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> tuple[Client, ...]:
        with self._lock:
            return tuple(self._clients.values())

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            if client_id in self._clients:
                self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    def channel_snapshot(self, channel: str) -> tuple[Client, ...]:
        with self._lock:
            return tuple(
                self._clients[client_id]
                for client_id in self._channels.get(channel, set())
                if client_id in self._clients
            )

    def channels(self) -> dict[str, int]:
        with self._lock:
            return {
                name: len(subscribers)
                for name, subscribers in sorted(self._channels.items())
            }

    def subscriber_ids(self, channel: str) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._channels.get(channel, set())))

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)


class BaseTransport(ABC):
    """Interface between notification handling and a client transport."""

    def __init__(self) -> None:
        self.server: NotificationServer | None = None

    def attach(self, server: NotificationServer) -> None:
        self.server = server

    @abstractmethod
    async def on_connect(self, connection: Any) -> Client:
        """Register a newly connected transport client."""

    @abstractmethod
    async def on_disconnect(self, client: Client) -> None:
        """Release transport resources for a disconnected client."""

    @abstractmethod
    async def send_message(self, client: Client, outgoing: dict[str, Any]) -> bool:
        """Send one notification envelope to a client."""

    @abstractmethod
    async def broadcast(
        self, outgoing: dict[str, Any], channel: str | None = None
    ) -> None:
        """Send one notification envelope to all matching local clients."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport interface."""

    @property
    def notification_server(self) -> NotificationServer:
        if self.server is None:
            raise RuntimeError("transport is not attached to a notification server")
        return self.server

    async def on_connect(self, connection: ServerConnection) -> Client:
        return self.notification_server.clients.add(connection)

    async def on_disconnect(self, client: Client) -> None:
        self.notification_server.clients.remove(client.id)

    async def send_message(self, client: Client, outgoing: dict[str, Any]) -> bool:
        try:
            await client.connection.send(json.dumps(outgoing))
            return True
        except ConnectionClosed:
            await self.on_disconnect(client)
            return False

    async def broadcast(
        self, outgoing: dict[str, Any], channel: str | None = None
    ) -> None:
        clients = (
            self.notification_server.clients.snapshot()
            if channel is None
            else self.notification_server.clients.channel_snapshot(channel)
        )
        if clients:
            await asyncio.gather(
                *(self.send_message(client, outgoing) for client in clients)
            )

    async def handle_connection(self, connection: ServerConnection) -> None:
        server = self.notification_server
        client = await server._connect(connection)
        try:
            async for raw_message in connection:
                await server._handle_message(client, raw_message)
        except ConnectionClosed:
            pass
        finally:
            await server._disconnect(client)

    def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        server = self.notification_server
        parsed = urlsplit(request.path)
        path = parsed.path
        if path == "/health":
            return self._json_response(
                connection, {"connected_clients": len(server.clients)}
            )
        if path == "/channels":
            channels = [
                {"name": name, "subscriber_count": count}
                for name, count in server.clients.channels().items()
            ]
            return self._json_response(connection, {"channels": channels})
        if path == "/messages":
            if server.messages is None:
                return self._json_response(connection, {"messages": []})
            parameters = parse_qs(parsed.query)
            try:
                limit = int(parameters.get("limit", ["50"])[0])
                offset = int(parameters.get("offset", ["0"])[0])
                if not 1 <= limit <= 1000 or offset < 0:
                    raise ValueError
            except ValueError:
                return self._json_response(
                    connection,
                    {"error": "limit must be 1-1000 and offset must be non-negative"},
                    HTTPStatus.BAD_REQUEST,
                )
            return self._json_response(
                connection, {"messages": server.messages.list(limit, offset)}
            )
        prefix, separator, encoded_name = path.partition("/channels/")
        if not prefix and separator and encoded_name.endswith("/subscribers"):
            encoded_name = encoded_name[: -len("/subscribers")]
            if encoded_name:
                name = unquote(encoded_name)
                return self._json_response(
                    connection,
                    {
                        "channel": name,
                        "subscribers": list(server.clients.subscriber_ids(name)),
                    },
                )
        if request.headers.get("Upgrade", "").lower() != "websocket":
            return connection.respond(HTTPStatus.NOT_FOUND, "Not Found\n")
        return None

    @staticmethod
    def _json_response(
        connection: ServerConnection,
        body: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
    ) -> Response:
        response = connection.respond(status, json.dumps(body) + "\n")
        del response.headers["Content-Type"]
        response.headers["Content-Type"] = "application/json"
        return response

    def start(self, host: str = "127.0.0.1", port: int = 8765) -> Server:
        return serve(
            self.handle_connection,
            host,
            port,
            process_request=self.process_request,
        )


def configured_transport() -> BaseTransport:
    transport_name = os.getenv("TRANSPORT", "websocket").lower()
    if transport_name == "websocket":
        return WebSocketTransport()
    raise ValueError(f"unsupported transport: {transport_name}")


class NotificationServer:
    def __init__(
        self,
        backbone: RedisBackbone | None = None,
        database_url: str | None = None,
        transport: BaseTransport | None = None,
    ) -> None:
        self.clients = ClientRegistry()
        self.transport = transport or configured_transport()
        self.transport.attach(self)
        configured_redis = os.getenv("REDIS_URL")
        self.backbone = backbone or (
            RedisBackbone(configured_redis) if configured_redis else None
        )
        configured_database = database_url or os.getenv("DATABASE_URL")
        self.messages = MessageStore(configured_database) if configured_database else None
        self._backbone_lock = asyncio.Lock()
        self._backbone_started = False

    async def _ensure_backbone(self) -> None:
        if self.backbone is None or self._backbone_started:
            return
        async with self._backbone_lock:
            if not self._backbone_started:
                await self.backbone.start(self._receive_event)
                self._backbone_started = True

    async def handle_connection(self, connection: ServerConnection) -> None:
        if not isinstance(self.transport, WebSocketTransport):
            raise RuntimeError("handle_connection is only available for WebSocket transport")
        await self.transport.handle_connection(connection)

    async def _connect(self, connection: Any) -> Client:
        await self._ensure_backbone()
        client = await self.transport.on_connect(connection)
        if self.backbone is not None:
            await self.backbone.add_client(client.id)
        await self._send(
            client,
            message("system", {"event": "connected", "client_id": client.id}),
        )
        return client

    async def _disconnect(self, client: Client) -> None:
        await self.transport.on_disconnect(client)
        if self.backbone is not None:
            await self.backbone.remove_client(client.id)

    async def _handle_message(self, sender: Client, raw_message: str | bytes) -> None:
        if isinstance(raw_message, bytes):
            await self._error(sender, "messages must be UTF-8 JSON text")
            return

        try:
            incoming = json.loads(raw_message)
        except (json.JSONDecodeError, TypeError):
            await self._error(sender, "invalid JSON")
            return

        error = self._validation_error(incoming)
        if error:
            await self._error(sender, error)
            return

        message_type = incoming["type"]
        payload = incoming["payload"]
        channel = incoming.get("channel")
        if message_type == "broadcast":
            await self._publish(message("broadcast", payload, channel), channel=channel)
        elif message_type == "direct":
            await self._direct(sender, payload, channel)
        elif message_type == "subscribe":
            self.clients.subscribe(sender.id, channel)
            if self.backbone is not None:
                await self.backbone.subscribe(sender.id, channel)
        elif message_type == "unsubscribe":
            self.clients.unsubscribe(sender.id, channel)
            if self.backbone is not None:
                await self.backbone.unsubscribe(sender.id, channel)
        else:
            await self._error(sender, "clients cannot send system messages")

    @staticmethod
    def _validation_error(incoming: Any) -> str | None:
        if not isinstance(incoming, dict):
            return "message must be a JSON object"
        if not isinstance(incoming.get("type"), str):
            return "type must be a string"
        if incoming["type"] not in SUPPORTED_TYPES:
            return "unsupported message type"
        if not isinstance(incoming.get("payload"), dict):
            return "payload must be an object"
        if "timestamp" not in incoming or not isinstance(incoming["timestamp"], str):
            return "timestamp must be a string"
        if "channel" in incoming and (
            not isinstance(incoming["channel"], str) or not incoming["channel"]
        ):
            return "channel must be a non-empty string"
        if incoming["type"] in {"subscribe", "unsubscribe"} and "channel" not in incoming:
            return f'{incoming["type"]} requires channel'
        return None

    async def _direct(
        self,
        sender: Client,
        payload: dict[str, Any],
        channel: str | None = None,
    ) -> None:
        target_id = payload.get("client_id")
        if not isinstance(target_id, str) or not target_id:
            await self._error(sender, "direct payload requires client_id")
            return

        target = self.clients.get(target_id)
        target_exists = target is not None
        if not target_exists and self.backbone is not None:
            target_exists = await self.backbone.client_exists(target_id)
        if not target_exists:
            await self._error(sender, "target client is not connected")
            return
        target_subscribed = channel is None or (
            target is not None and target in self.clients.channel_snapshot(channel)
        )
        if channel is not None and not target_subscribed and self.backbone is not None:
            target_subscribed = await self.backbone.is_subscribed(target_id, channel)
        if not target_subscribed:
            await self._error(sender, "target client is not subscribed to channel")
            return

        direct_payload = {key: value for key, value in payload.items() if key != "client_id"}
        direct_payload["sender_id"] = sender.id
        await self._publish(
            message("direct", direct_payload, channel),
            channel=channel,
            target_id=target_id,
        )

    async def _publish(
        self,
        outgoing: dict[str, Any],
        channel: str | None = None,
        target_id: str | None = None,
    ) -> None:
        if self.messages is not None:
            self.messages.add(outgoing)
        event = {"message": outgoing, "channel": channel, "target_id": target_id}
        if self.backbone is not None:
            await self.backbone.publish(event)
        else:
            await self._receive_event(event)

    async def _receive_event(self, event: dict[str, Any]) -> None:
        outgoing = event["message"]
        target_id = event.get("target_id")
        if target_id is not None:
            target = self.clients.get(target_id)
            if target is not None:
                await self._send(target, outgoing)
            return
        await self.broadcast(outgoing, event.get("channel"))

    async def broadcast(
        self,
        outgoing: dict[str, Any],
        channel: str | None = None,
    ) -> None:
        await self.transport.broadcast(outgoing, channel)

    async def _error(self, client: Client, detail: str) -> None:
        await self._send(client, message("system", {"event": "error", "detail": detail}))

    async def _send(self, client: Client, outgoing: dict[str, Any]) -> bool:
        return await self.transport.send_message(client, outgoing)

    def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        if not isinstance(self.transport, WebSocketTransport):
            raise RuntimeError("process_request is only available for WebSocket transport")
        return self.transport.process_request(connection, request)

    @staticmethod
    def _json_response(
        connection: ServerConnection,
        body: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
    ) -> Response:
        return WebSocketTransport._json_response(connection, body, status)

    def start(self, host: str = "127.0.0.1", port: int = 8765) -> Server:
        """Create a server context manager for use with ``async with``."""
        start = getattr(self.transport, "start", None)
        if start is None:
            raise RuntimeError("configured transport cannot start a network server")
        return start(host, port)


async def run(host: str, port: int) -> None:
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    database_url = os.getenv("DATABASE_URL", "sqlite:///messages.db")
    notification_server = NotificationServer(RedisBackbone(redis_url), database_url)
    try:
        async with notification_server.start(host, port):
            print(f"Notification server listening on {host}:{port}")
            await asyncio.get_running_loop().create_future()
    finally:
        await notification_server.backbone.close()
        notification_server.messages.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        asyncio.run(run(args.host, args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
