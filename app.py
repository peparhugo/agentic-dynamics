"""Async WebSocket notification server with an HTTP health endpoint."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import threading
import uuid
from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any
from urllib.parse import unquote, urlparse

from websockets.exceptions import ConnectionClosed
from websockets.legacy.server import WebSocketServerProtocol, serve


MESSAGE_TYPES = frozenset({"broadcast", "direct", "system", "subscribe", "unsubscribe"})
BROKER_CHANNEL = "notifications"


class BaseTransport(ABC):
    """Connection transport used by :class:`NotificationServer`."""

    @property
    @abstractmethod
    def client_ids(self) -> tuple[str, ...]:
        """Return the IDs of clients connected through this transport."""

    @abstractmethod
    async def on_connect(self, client_id: str, connection: Any) -> None:
        """Register a newly connected client."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Remove a disconnected client."""

    @abstractmethod
    async def send_message(self, client_id: str, message: dict[str, Any]) -> bool:
        """Send a message to one client, returning whether it was delivered."""

    @abstractmethod
    async def broadcast(
        self, message: dict[str, Any], client_ids: tuple[str, ...] | None = None
    ) -> tuple[str, ...]:
        """Send a message to selected clients and return IDs that could not receive it."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport interface."""

    def __init__(self) -> None:
        self._clients: dict[str, WebSocketServerProtocol] = {}
        self._clients_lock = threading.RLock()

    @property
    def client_ids(self) -> tuple[str, ...]:
        with self._clients_lock:
            return tuple(self._clients)

    async def on_connect(self, client_id: str, connection: Any) -> None:
        if not isinstance(connection, WebSocketServerProtocol):
            raise TypeError("WebSocketTransport requires a WebSocket connection")
        with self._clients_lock:
            self._clients[client_id] = connection

    async def on_disconnect(self, client_id: str) -> None:
        with self._clients_lock:
            self._clients.pop(client_id, None)

    async def send_message(self, client_id: str, message: dict[str, Any]) -> bool:
        with self._clients_lock:
            websocket = self._clients.get(client_id)
        if websocket is None:
            return False
        try:
            await websocket.send(json.dumps(message))
            return True
        except ConnectionClosed:
            return False

    async def broadcast(
        self, message: dict[str, Any], client_ids: tuple[str, ...] | None = None
    ) -> tuple[str, ...]:
        with self._clients_lock:
            target_ids = self.client_ids if client_ids is None else client_ids
        results = await asyncio.gather(
            *(self.send_message(client_id, message) for client_id in target_ids), return_exceptions=True
        )
        return tuple(client_id for client_id, result in zip(target_ids, results) if result is not True)

    async def handler(
        self, server: "NotificationServer", websocket: WebSocketServerProtocol, _path: str
    ) -> None:
        client_id = str(uuid.uuid4())
        await server._connected(client_id, websocket)
        try:
            async for raw_message in websocket:
                await server._handle_message(client_id, raw_message)
        except ConnectionClosed:
            pass
        finally:
            await server._disconnected(client_id)


class MessageStore:
    """SQLite-backed append-only message history."""

    def __init__(self, database_url: str) -> None:
        path = database_url.removeprefix("sqlite:///") if database_url.startswith("sqlite:///") else database_url
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.RLock()
        with self._connection:
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS messages "
                "(id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, type TEXT NOT NULL, "
                "payload TEXT NOT NULL, timestamp TEXT NOT NULL)"
            )

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
                "ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        return [
            {"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]}
            for row in rows
        ]


class InMemoryBroker:
    """Fallback broker for development when REDIS_URL cannot be reached."""

    subscribers: dict[Any, asyncio.AbstractEventLoop] = {}
    clients: dict[str, str] = {}
    channel_members: dict[str, set[str]] = {}

    async def start(self, callback: Any) -> None:
        self.callback = callback
        self.subscribers[callback] = asyncio.get_running_loop()

    async def publish(self, message: str) -> None:
        loop = asyncio.get_running_loop()
        await asyncio.gather(
            *(
                callback(message)
                for callback, subscriber_loop in list(self.subscribers.items())
                if subscriber_loop is loop and getattr(callback, "__self__", None).client_count > 0
            )
        )

    async def add_client(self, client_id: str, instance_id: str) -> None:
        self.clients[client_id] = instance_id

    async def remove_client(self, client_id: str) -> None:
        self.clients.pop(client_id, None)
        for members in self.channel_members.values():
            members.discard(client_id)

    async def client_exists(self, client_id: str) -> bool:
        return client_id in self.clients

    async def subscribe_client(self, channel: str, client_id: str) -> None:
        self.channel_members.setdefault(channel, set()).add(client_id)

    async def unsubscribe_client(self, channel: str, client_id: str) -> None:
        self.channel_members.get(channel, set()).discard(client_id)


class RedisBroker:
    """Minimal Redis RESP pub/sub client; no third-party Redis package is required."""

    def __init__(self, redis_url: str) -> None:
        parsed = urlparse(redis_url)
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or 6379
        self.password = parsed.password
        self._fallback: InMemoryBroker | None = InMemoryBroker() if redis_url == "memory://" else None

    @staticmethod
    def _command(*parts: str) -> bytes:
        encoded = [part.encode() for part in parts]
        return b"*%d\r\n" % len(encoded) + b"".join(b"$%d\r\n%s\r\n" % (len(part), part) for part in encoded)

    async def _read(self, reader: asyncio.StreamReader) -> Any:
        marker = await reader.readexactly(1)
        if marker == b"+":
            return (await reader.readline()).rstrip(b"\r\n").decode()
        if marker == b":":
            return int(await reader.readline())
        if marker == b"$":
            length = int(await reader.readline())
            return None if length == -1 else (await reader.readexactly(length + 2))[:-2].decode()
        if marker == b"*":
            return [await self._read(reader) for _ in range(int(await reader.readline()))]
        raise RuntimeError((await reader.readline()).decode())

    async def _execute(self, *parts: str) -> Any:
        reader, writer = await asyncio.open_connection(self.host, self.port)
        try:
            if self.password:
                writer.write(self._command("AUTH", self.password))
                await writer.drain()
                await self._read(reader)
            writer.write(self._command(*parts))
            await writer.drain()
            return await self._read(reader)
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self, callback: Any) -> None:
        if self._fallback:
            await self._fallback.start(callback)
            return
        try:
            reader, writer = await asyncio.open_connection(self.host, self.port)
            if self.password:
                writer.write(self._command("AUTH", self.password))
                await writer.drain()
                await self._read(reader)
            writer.write(self._command("SUBSCRIBE", BROKER_CHANNEL))
            await writer.drain()
            await self._read(reader)
        except OSError:
            self._fallback = InMemoryBroker()
            await self._fallback.start(callback)
            return

        async def listen() -> None:
            try:
                while True:
                    event = await self._read(reader)
                    if event[0] == "message":
                        await callback(event[2])
            finally:
                writer.close()
                await writer.wait_closed()

        asyncio.create_task(listen())

    async def publish(self, message: str) -> None:
        if self._fallback:
            await self._fallback.publish(message)
        else:
            await self._execute("PUBLISH", BROKER_CHANNEL, message)

    async def add_client(self, client_id: str, instance_id: str) -> None:
        if self._fallback:
            await self._fallback.add_client(client_id, instance_id)
        else:
            await self._execute("HSET", "notifications:clients", client_id, instance_id)

    async def remove_client(self, client_id: str) -> None:
        if self._fallback:
            await self._fallback.remove_client(client_id)
        else:
            await self._execute("HDEL", "notifications:clients", client_id)

    async def client_exists(self, client_id: str) -> bool:
        result = await (self._fallback.client_exists(client_id) if self._fallback else self._execute("HEXISTS", "notifications:clients", client_id))
        return bool(result)

    async def subscribe_client(self, channel: str, client_id: str) -> None:
        if self._fallback:
            await self._fallback.subscribe_client(channel, client_id)
        else:
            await self._execute("SADD", f"notifications:channel:{channel}", client_id)

    async def unsubscribe_client(self, channel: str, client_id: str) -> None:
        if self._fallback:
            await self._fallback.unsubscribe_client(channel, client_id)
        else:
            await self._execute("SREM", f"notifications:channel:{channel}", client_id)


class NotificationServer:
    """Manage connected clients and route JSON notification messages."""

    def __init__(
        self,
        redis_url: str | None = None,
        database_url: str | None = None,
        transport: BaseTransport | None = None,
    ) -> None:
        self._channels: dict[str, set[str]] = {}
        self._clients_lock = threading.RLock()
        self._transport = transport or self._create_transport(os.getenv("TRANSPORT", "websocket"))
        self._instance_id = str(uuid.uuid4())
        self._broker = RedisBroker(redis_url or os.getenv("REDIS_URL", "redis://127.0.0.1:6379"))
        self._broker_started = False
        self._broker_lock = asyncio.Lock()
        self._store = MessageStore(database_url or os.getenv("DATABASE_URL", ":memory:"))

    @staticmethod
    def _create_transport(name: str) -> BaseTransport:
        if name.lower() == "websocket":
            return WebSocketTransport()
        raise ValueError(f"unsupported transport: {name}")

    async def _start_broker(self) -> None:
        if not self._broker_started:
            async with self._broker_lock:
                if not self._broker_started:
                    await self._broker.start(self._deliver_published)
                    self._broker_started = True

    @property
    def client_count(self) -> int:
        return len(self._transport.client_ids)

    @property
    def client_ids(self) -> tuple[str, ...]:
        return self._transport.client_ids

    @property
    def channels(self) -> dict[str, int]:
        """Return active channel names and their subscriber counts."""
        with self._clients_lock:
            return {channel: len(subscribers) for channel, subscribers in self._channels.items()}

    def channel_subscribers(self, channel: str) -> tuple[str, ...] | None:
        """Return subscriber IDs for an active channel, if it exists."""
        with self._clients_lock:
            subscribers = self._channels.get(channel)
            return None if subscribers is None else tuple(subscribers)

    async def handler(self, websocket: WebSocketServerProtocol, _path: str) -> None:
        """Handle WebSocket connections; retained for the public server API."""
        if not isinstance(self._transport, WebSocketTransport):
            raise RuntimeError("the selected transport does not provide a WebSocket handler")
        await self._transport.handler(self, websocket, _path)

    async def _connected(self, client_id: str, connection: Any) -> None:
        await self._start_broker()
        await self._transport.on_connect(client_id, connection)
        await self._broker.add_client(client_id, self._instance_id)
        await self.send_to_client(
            client_id,
            self._message("system", {"event": "connected", "client_id": client_id}),
        )

    async def _disconnected(self, client_id: str) -> None:
        await self._transport.on_disconnect(client_id)
        with self._clients_lock:
            self._remove_client(client_id)
        await self._broker.remove_client(client_id)

    async def _handle_message(self, sender_id: str, raw_message: str | bytes) -> None:
        if isinstance(raw_message, bytes):
            await self.send_to_client(
                sender_id,
                self._message("system", {"event": "error", "message": "messages must be JSON text"}),
            )
            return

        try:
            incoming = json.loads(raw_message)
            message_type = incoming["type"]
            payload = incoming["payload"]
            if message_type not in MESSAGE_TYPES or not isinstance(payload, Mapping):
                raise (KeyError if message_type not in MESSAGE_TYPES else TypeError)
            channel = incoming.get("channel")
            if channel is not None and (not isinstance(channel, str) or not channel):
                raise TypeError
        except (json.JSONDecodeError, KeyError, TypeError):
            await self.send_to_client(
                sender_id,
                self._message("system", {"event": "error", "message": "invalid message format"}),
            )
            return

        if message_type in {"subscribe", "unsubscribe"}:
            channel = payload.get("channel")
            if not isinstance(channel, str) or not channel:
                await self.send_to_client(
                    sender_id,
                    self._message("system", {"event": "error", "message": "invalid channel"}),
                )
                return
            with self._clients_lock:
                if message_type == "subscribe":
                    self._channels.setdefault(channel, set()).add(sender_id)
                    await self._broker.subscribe_client(channel, sender_id)
                else:
                    subscribers = self._channels.get(channel)
                    if subscribers is not None:
                        subscribers.discard(sender_id)
                        if not subscribers:
                            self._channels.pop(channel)
                    await self._broker.unsubscribe_client(channel, sender_id)
            return

        message = self._message(message_type, dict(payload), channel)
        self._store.save(message)
        if channel is not None:
            await self._publish("channel", message)
        elif message_type == "broadcast" or message_type == "system":
            await self._publish("broadcast", message)
        else:
            recipient_id = payload.get("client_id")
            if not isinstance(recipient_id, str) or not await self._broker.client_exists(recipient_id):
                await self.send_to_client(
                    sender_id,
                    self._message("system", {"event": "error", "message": "unknown direct recipient"}),
                )
            else:
                await self._publish("direct", message)

    async def _publish(self, scope: str, message: dict[str, Any]) -> None:
        await self._start_broker()
        await self._broker.publish(json.dumps({"scope": scope, "message": message}))

    async def _deliver_published(self, encoded: str) -> None:
        envelope = json.loads(encoded)
        message = envelope["message"]
        if envelope["scope"] == "channel":
            await self.broadcast_to_channel(message["channel"], message)
        elif envelope["scope"] == "broadcast":
            await self.broadcast(message)
        else:
            await self.send_to_client(message["payload"]["client_id"], message)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a valid notification message to every currently connected client."""
        await self._remove_stale_clients(await self._transport.broadcast(message))

    async def broadcast_to_channel(self, channel: str, message: dict[str, Any]) -> None:
        """Send a notification only to clients subscribed to ``channel``."""
        with self._clients_lock:
            client_ids = tuple(
                client_id for client_id in self._channels.get(channel, set()) if client_id in self.client_ids
            )
        await self._remove_stale_clients(await self._transport.broadcast(message, client_ids))

    async def send_to_client(self, client_id: str, message: dict[str, Any]) -> bool:
        delivered = await self._transport.send_message(client_id, message)
        if not delivered:
            await self._remove_stale_clients((client_id,))
        return delivered

    async def _remove_stale_clients(self, stale_ids: tuple[str, ...]) -> None:
        if stale_ids:
            await asyncio.gather(*(self._transport.on_disconnect(client_id) for client_id in stale_ids))
            with self._clients_lock:
                for client_id in stale_ids:
                    self._remove_client(client_id)

    def _remove_client(self, client_id: str) -> None:
        self._clients.pop(client_id, None)
        for channel, subscribers in list(self._channels.items()):
            subscribers.discard(client_id)
            if not subscribers:
                self._channels.pop(channel)

    async def health_response(
        self, path: str, _request_headers: Any
    ) -> tuple[Any, list[tuple[str, str]], bytes] | None:
        parsed_path = urlparse(path)
        if parsed_path.path == "/health":
            body = json.dumps({"connected_clients": self.client_count}).encode("utf-8")
        elif parsed_path.path == "/channels":
            body = json.dumps({"channels": self.channels}).encode("utf-8")
        elif parsed_path.path == "/messages":
            params = dict(part.split("=", 1) for part in parsed_path.query.split("&") if "=" in part)
            try:
                limit, offset = int(params.get("limit", "50")), int(params.get("offset", "0"))
                if not 0 <= offset or not 1 <= limit <= 1000:
                    raise ValueError
            except ValueError:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"error": "invalid pagination"})
            body = json.dumps({"messages": self._store.list(limit, offset)}).encode("utf-8")
        elif parsed_path.path.startswith("/channels/") and parsed_path.path.endswith("/subscribers"):
            channel = unquote(parsed_path.path.removeprefix("/channels/").removesuffix("/subscribers").rstrip("/"))
            subscribers = self.channel_subscribers(channel)
            if subscribers is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"error": "channel not found"})
            body = json.dumps({"subscribers": list(subscribers)}).encode("utf-8")
        else:
            return None
        return (
            HTTPStatus.OK,
            [("Content-Type", "application/json"), ("Content-Length", str(len(body)))],
            body,
        )

    @staticmethod
    def _json_response(status: HTTPStatus, content: dict[str, Any]) -> tuple[Any, list[tuple[str, str]], bytes]:
        body = json.dumps(content).encode("utf-8")
        return status, [("Content-Type", "application/json"), ("Content-Length", str(len(body)))], body

    @staticmethod
    def _message(message_type: str, payload: dict[str, Any], channel: str | None = None) -> dict[str, Any]:
        message = {
            "type": message_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if channel is not None:
            message["channel"] = channel
        return message


async def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the notification service until cancelled."""
    notification_server = NotificationServer()
    async with serve(
        notification_server.handler,
        host,
        port,
        process_request=notification_server.health_response,
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(run_server())
