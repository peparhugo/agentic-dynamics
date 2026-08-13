"""Async notification server backed by Redis and SQLite."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sqlite3
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4

from redis.asyncio import Redis
from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

LOGGER = logging.getLogger(__name__)
SUPPORTED_TYPES = frozenset({"broadcast", "direct", "system", "subscribe", "unsubscribe"})
DEFAULT_REDIS_CHANNEL = "notifications:messages"


def make_message(
    message_type: str, payload: dict[str, Any], channel: str | None = None
) -> dict[str, Any]:
    """Create a message in the server's wire format."""
    if message_type not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported message type: {message_type}")
    if not isinstance(payload, dict):
        raise TypeError("payload must be an object")
    message = {
        "type": message_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if channel is not None:
        message["channel"] = channel
    return message


class InMemoryBackbone:
    """Redis-compatible test and development backbone used without REDIS_URL."""

    def __init__(self) -> None:
        self.clients: set[str] = set()
        self.channels: dict[str, set[str]] = {}
        self.client_channels: dict[str, set[str]] = {}
        self._subscribers: set[asyncio.Queue[str]] = set()
        self._lock = asyncio.Lock()

    async def add_client(self, client_id: str) -> None:
        async with self._lock:
            self.clients.add(client_id)

    async def remove_client(self, client_id: str) -> None:
        async with self._lock:
            self.clients.discard(client_id)
            for channel in self.client_channels.pop(client_id, set()):
                subscribers = self.channels.get(channel)
                if subscribers is not None:
                    subscribers.discard(client_id)
                    if not subscribers:
                        del self.channels[channel]

    async def count(self) -> int:
        async with self._lock:
            return len(self.clients)

    async def is_connected(self, client_id: str) -> bool:
        async with self._lock:
            return client_id in self.clients

    async def subscribe_client(self, client_id: str, channel: str) -> None:
        async with self._lock:
            if client_id not in self.clients:
                raise ValueError("client is not connected")
            self.channels.setdefault(channel, set()).add(client_id)
            self.client_channels.setdefault(client_id, set()).add(channel)

    async def unsubscribe_client(self, client_id: str, channel: str) -> None:
        async with self._lock:
            self.client_channels.get(client_id, set()).discard(channel)
            subscribers = self.channels.get(channel)
            if subscribers is not None:
                subscribers.discard(client_id)
                if not subscribers:
                    del self.channels[channel]

    async def channel_counts(self) -> dict[str, int]:
        async with self._lock:
            return {name: len(ids) for name, ids in sorted(self.channels.items())}

    async def subscribers(self, channel: str) -> list[str]:
        async with self._lock:
            return sorted(self.channels.get(channel, set()))

    async def is_subscribed(self, client_id: str, channel: str) -> bool:
        async with self._lock:
            return client_id in self.channels.get(channel, set())

    async def publish(self, encoded: str) -> None:
        async with self._lock:
            subscribers = list(self._subscribers)
        for queue in subscribers:
            await queue.put(encoded)

    @asynccontextmanager
    async def listen(self) -> AsyncIterator[AsyncIterator[str]]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        async with self._lock:
            self._subscribers.add(queue)

        async def messages() -> AsyncIterator[str]:
            while True:
                yield await queue.get()

        try:
            yield messages()
        finally:
            async with self._lock:
                self._subscribers.discard(queue)

    async def close(self) -> None:
        return None


class RedisBackbone:
    """Redis pub/sub transport and global client-state repository."""

    def __init__(self, redis: Redis, pubsub_channel: str = DEFAULT_REDIS_CHANNEL) -> None:
        self.redis = redis
        self.pubsub_channel = pubsub_channel

    @staticmethod
    def _channel_key(channel: str) -> str:
        return f"notifications:channel:{channel}"

    @staticmethod
    def _client_channels_key(client_id: str) -> str:
        return f"notifications:client:{client_id}:channels"

    async def add_client(self, client_id: str) -> None:
        await self.redis.sadd("notifications:clients", client_id)

    async def remove_client(self, client_id: str) -> None:
        client_key = self._client_channels_key(client_id)
        channels = await self.redis.smembers(client_key)
        pipeline = self.redis.pipeline()
        pipeline.srem("notifications:clients", client_id)
        for channel in channels:
            pipeline.srem(self._channel_key(self._text(channel)), client_id)
        pipeline.delete(client_key)
        await pipeline.execute()

    async def count(self) -> int:
        return int(await self.redis.scard("notifications:clients"))

    async def is_connected(self, client_id: str) -> bool:
        return bool(await self.redis.sismember("notifications:clients", client_id))

    async def subscribe_client(self, client_id: str, channel: str) -> None:
        if not await self.is_connected(client_id):
            raise ValueError("client is not connected")
        pipeline = self.redis.pipeline()
        pipeline.sadd(self._channel_key(channel), client_id)
        pipeline.sadd(self._client_channels_key(client_id), channel)
        await pipeline.execute()

    async def unsubscribe_client(self, client_id: str, channel: str) -> None:
        pipeline = self.redis.pipeline()
        pipeline.srem(self._channel_key(channel), client_id)
        pipeline.srem(self._client_channels_key(client_id), channel)
        await pipeline.execute()

    async def channel_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        async for key in self.redis.scan_iter(match="notifications:channel:*"):
            name = self._text(key)[len("notifications:channel:") :]
            count = int(await self.redis.scard(key))
            if count:
                counts[name] = count
        return dict(sorted(counts.items()))

    async def subscribers(self, channel: str) -> list[str]:
        members = await self.redis.smembers(self._channel_key(channel))
        return sorted(self._text(member) for member in members)

    async def is_subscribed(self, client_id: str, channel: str) -> bool:
        return bool(await self.redis.sismember(self._channel_key(channel), client_id))

    async def publish(self, encoded: str) -> None:
        await self.redis.publish(self.pubsub_channel, encoded)

    @asynccontextmanager
    async def listen(self) -> AsyncIterator[AsyncIterator[str]]:
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self.pubsub_channel)

        async def messages() -> AsyncIterator[str]:
            async for item in pubsub.listen():
                if item["type"] == "message":
                    yield self._text(item["data"])

        try:
            yield messages()
        finally:
            await pubsub.aclose()

    async def close(self) -> None:
        await self.redis.aclose()

    @staticmethod
    def _text(value: str | bytes) -> str:
        return value.decode() if isinstance(value, bytes) else value


class MessageStore:
    """SQLite message history repository."""

    def __init__(self, database_url: str) -> None:
        path = database_url
        if database_url.startswith("sqlite:///"):
            path = database_url[len("sqlite:///") :]
        if path != ":memory:":
            Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = asyncio.Lock()
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )"""
        )
        self._connection.commit()

    async def save(self, message: dict[str, Any]) -> int:
        async with self._lock:
            cursor = await asyncio.to_thread(
                self._connection.execute,
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (
                    message.get("channel"),
                    message["type"],
                    json.dumps(message["payload"]),
                    message["timestamp"],
                ),
            )
            await asyncio.to_thread(self._connection.commit)
            return int(cursor.lastrowid)

    async def list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        async with self._lock:
            cursor = await asyncio.to_thread(
                self._connection.execute,
                """SELECT id, channel, type, payload, timestamp
                   FROM messages ORDER BY id DESC LIMIT ? OFFSET ?""",
                (limit, offset),
            )
            rows = await asyncio.to_thread(cursor.fetchall)
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

    async def close(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._connection.close)


class ClientRegistry:
    """Local transport connections paired with globally shared connection state."""

    def __init__(self, backbone: InMemoryBackbone | RedisBackbone) -> None:
        self._backbone = backbone
        self._clients: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def add(self, connection: Any) -> str:
        client_id = str(uuid4())
        async with self._lock:
            self._clients[client_id] = connection
        await self._backbone.add_client(client_id)
        return client_id

    async def remove(self, client_id: str) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)
        await self._backbone.remove_client(client_id)

    async def count(self) -> int:
        return await self._backbone.count()

    async def snapshot(self) -> list[tuple[str, Any]]:
        async with self._lock:
            return list(self._clients.items())

    async def get(self, client_id: str) -> Any | None:
        async with self._lock:
            return self._clients.get(client_id)

    async def subscribe(self, client_id: str, channel: str) -> None:
        await self._backbone.subscribe_client(client_id, channel)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        await self._backbone.unsubscribe_client(client_id, channel)

    async def channel_snapshot(self, channel: str) -> list[tuple[str, Any]]:
        async with self._lock:
            local = list(self._clients.items())
        return [item for item in local if await self._backbone.is_subscribed(item[0], channel)]

    async def channels(self) -> dict[str, int]:
        return await self._backbone.channel_counts()

    async def subscribers(self, channel: str) -> list[str]:
        return await self._backbone.subscribers(channel)

    async def is_subscribed(self, client_id: str, channel: str) -> bool:
        return await self._backbone.is_subscribed(client_id, channel)

    async def is_connected(self, client_id: str) -> bool:
        return await self._backbone.is_connected(client_id)


class BaseTransport(ABC):
    """Interface between notification routing and a client transport."""

    def bind(self, server: NotificationServer) -> None:
        self.server = server

    @abstractmethod
    async def on_connect(self, connection: Any) -> str:
        """Register a transport connection and return its client ID."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Remove a transport connection."""

    @abstractmethod
    async def send_message(self, connection: Any, message: dict[str, Any]) -> None:
        """Send one wire-format message to a connection."""

    @abstractmethod
    async def broadcast(
        self, clients: list[tuple[str, Any]], message: dict[str, Any]
    ) -> None:
        """Deliver a message to a collection of local connections."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport interface."""

    async def handler(self, websocket: ServerConnection) -> None:
        await self.server.start()
        client_id = await self.on_connect(websocket)
        try:
            async for raw_message in websocket:
                try:
                    message = json.loads(raw_message)
                except (json.JSONDecodeError, UnicodeDecodeError) as error:
                    await self.send_message(
                        websocket,
                        make_message("system", {"event": "error", "message": str(error)}),
                    )
                    continue
                await self.server.handle_message(client_id, websocket, message)
        except ConnectionClosed:
            pass
        finally:
            await self.on_disconnect(client_id)

    async def on_connect(self, connection: ServerConnection) -> str:
        client_id = await self.server.clients.add(connection)
        await self.send_message(
            connection, make_message("system", {"event": "connected", "client_id": client_id})
        )
        return client_id

    async def on_disconnect(self, client_id: str) -> None:
        await self.server.clients.remove(client_id)

    async def send_message(
        self, connection: ServerConnection, message: dict[str, Any]
    ) -> None:
        await connection.send(json.dumps(message))

    async def broadcast(
        self, clients: list[tuple[str, Any]], message: dict[str, Any]
    ) -> None:
        results = await asyncio.gather(
            *(self.send_message(connection, message) for _, connection in clients),
            return_exceptions=True,
        )
        for (client_id, _), result in zip(clients, results):
            if isinstance(result, Exception):
                await self.on_disconnect(client_id)


def create_transport(name: str) -> BaseTransport:
    """Create the configured client transport."""
    if name.lower() == "websocket":
        return WebSocketTransport()
    raise ValueError(f"unsupported transport: {name}")


class NotificationServer:
    """Route notifications through a shared backbone and pluggable transport."""

    def __init__(
        self,
        backbone: InMemoryBackbone | RedisBackbone | None = None,
        database_url: str | None = None,
        transport: BaseTransport | None = None,
    ) -> None:
        redis_url = os.getenv("REDIS_URL")
        self.backbone = backbone or (
            RedisBackbone(Redis.from_url(redis_url)) if redis_url else InMemoryBackbone()
        )
        self.store = MessageStore(database_url or os.getenv("DATABASE_URL", ":memory:"))
        self.clients = ClientRegistry(self.backbone)
        self.transport = transport or create_transport(os.getenv("TRANSPORT", "websocket"))
        self.transport.bind(self)
        self._worker: asyncio.Task[None] | None = None
        self._worker_ready = asyncio.Event()

    async def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._delivery_worker())
            await self._worker_ready.wait()

    async def close(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)
            self._worker = None
        for client_id, _ in await self.clients.snapshot():
            await self.transport.on_disconnect(client_id)
        await self.store.close()
        await self.backbone.close()

    async def _delivery_worker(self) -> None:
        try:
            async with self.backbone.listen() as messages:
                self._worker_ready.set()
                async for encoded in messages:
                    envelope = json.loads(encoded)
                    await self._deliver(envelope["message"], envelope)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("Redis delivery worker stopped")
            self._worker_ready.set()

    async def websocket_handler(self, websocket: ServerConnection) -> None:
        """Compatibility entry point for the default WebSocket API."""
        if not isinstance(self.transport, WebSocketTransport):
            raise RuntimeError("websocket_handler requires the websocket transport")
        await self.transport.handler(websocket)

    async def handle_message(
        self, client_id: str, connection: Any, message: Any
    ) -> None:
        """Process a decoded message received by any transport."""
        try:
            self._validate_message(message)
            message_type = message["type"]
            channel = message.get("channel")
            if message_type == "broadcast":
                await self.broadcast(make_message("broadcast", message["payload"], channel), channel)
            elif message_type == "direct":
                await self._send_direct(message["payload"], channel)
            elif message_type == "subscribe":
                await self.clients.subscribe(client_id, channel)
            elif message_type == "unsubscribe":
                await self.clients.unsubscribe(client_id, channel)
            else:
                raise ValueError("clients cannot send system messages")
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            await self.transport.send_message(
                connection, make_message("system", {"event": "error", "message": str(error)})
            )

    async def _handle_message(
        self, client_id: str, connection: Any, raw_message: str | bytes
    ) -> None:
        """Preserve the previous internal WebSocket message entry point."""
        try:
            message = json.loads(raw_message)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            await self.transport.send_message(
                connection, make_message("system", {"event": "error", "message": str(error)})
            )
            return
        await self.handle_message(client_id, connection, message)

    @staticmethod
    def _validate_message(message: Any) -> None:
        if not isinstance(message, dict):
            raise TypeError("message must be an object")
        required_fields = {"type", "payload", "timestamp"}
        extra_fields = set(message) - required_fields
        if not required_fields.issubset(message) or not extra_fields <= {"channel"}:
            raise ValueError("message must contain type, payload, and timestamp, with optional channel")
        if message["type"] not in SUPPORTED_TYPES:
            raise ValueError("unsupported message type")
        if not isinstance(message["payload"], dict):
            raise TypeError("payload must be an object")
        if not isinstance(message["timestamp"], str):
            raise TypeError("timestamp must be a string")
        channel = message.get("channel")
        if channel is not None and (not isinstance(channel, str) or not channel.strip()):
            raise ValueError("channel must be a non-empty string")
        if message["type"] in {"subscribe", "unsubscribe"} and channel is None:
            raise ValueError(f'{message["type"]} messages require a channel')

    async def broadcast(self, message: dict[str, Any], channel: str | None = None) -> None:
        """Persist and publish a message for all clients or one channel."""
        await self.start()
        if channel is None:
            channel = message.get("channel")
        await self.store.save(message)
        await self.backbone.publish(
            json.dumps({"target": "channel" if channel else "all", "channel": channel, "message": message})
        )

    async def _send_direct(self, payload: dict[str, Any], channel: str | None = None) -> None:
        recipient_id = payload.get("client_id")
        if not isinstance(recipient_id, str):
            raise ValueError("direct payload requires client_id")
        if not await self.clients.is_connected(recipient_id):
            raise ValueError("direct recipient is not connected")
        if channel is not None and not await self.clients.is_subscribed(recipient_id, channel):
            return
        message = make_message("direct", payload, channel)
        await self.store.save(message)
        await self.backbone.publish(
            json.dumps({"target": "direct", "recipient_id": recipient_id, "message": message})
        )

    async def _deliver(self, message: dict[str, Any], envelope: dict[str, Any]) -> None:
        target = envelope["target"]
        if target == "direct":
            recipient = await self.clients.get(envelope["recipient_id"])
            clients = [] if recipient is None else [(envelope["recipient_id"], recipient)]
        elif target == "channel":
            clients = await self.clients.channel_snapshot(envelope["channel"])
        else:
            clients = await self.clients.snapshot()
        await self.transport.broadcast(clients, message)

    async def health_handler(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        status = "404 Not Found"
        body: dict[str, Any] | list[dict[str, Any]] = {"error": "not found"}
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=5)
            parts = request_line.decode("ascii", errors="replace").strip().split()
            if len(parts) == 3 and parts[0] == "GET":
                target = urlsplit(parts[1])
                path = target.path
                if path == "/health":
                    status = "200 OK"
                    body = {"connected_clients": await self.clients.count()}
                elif path == "/messages":
                    try:
                        query = parse_qs(target.query)
                        limit = int(query.get("limit", ["50"])[0])
                        offset = int(query.get("offset", ["0"])[0])
                        if not 1 <= limit <= 1000 or offset < 0:
                            raise ValueError
                        status = "200 OK"
                        body = await self.store.list(limit, offset)
                    except ValueError:
                        status = "400 Bad Request"
                        body = {"error": "limit must be 1-1000 and offset must be non-negative"}
                elif path == "/channels":
                    status = "200 OK"
                    body = {"channels": await self.clients.channels()}
                elif path.startswith("/channels/") and path.endswith("/subscribers"):
                    encoded_name = path[len("/channels/") : -len("/subscribers")].strip("/")
                    if encoded_name:
                        channel = unquote(encoded_name)
                        status = "200 OK"
                        body = {"channel": channel, "subscribers": await self.clients.subscribers(channel)}

            encoded = json.dumps(body).encode()
            writer.write(
                f"HTTP/1.1 {status}\r\nContent-Type: application/json\r\n"
                f"Content-Length: {len(encoded)}\r\nConnection: close\r\n\r\n".encode()
                + encoded
            )
            await writer.drain()
        except (asyncio.TimeoutError, ConnectionError):
            LOGGER.debug("HTTP client disconnected before receiving a response")
        finally:
            writer.close()
            await writer.wait_closed()


async def run_server(host: str, websocket_port: int, health_port: int) -> None:
    notification_server = NotificationServer()
    await notification_server.start()
    websocket_server: Server
    try:
        async with serve(notification_server.websocket_handler, host, websocket_port) as websocket_server:
            health_server = await asyncio.start_server(
                notification_server.health_handler, host, health_port
            )
            LOGGER.info(
                "WebSocket server listening on %s:%d; HTTP endpoint on %s:%d",
                host,
                websocket_port,
                host,
                health_port,
            )
            async with health_server:
                await websocket_server.serve_forever()
    finally:
        await notification_server.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket port")
    parser.add_argument("--health-port", type=int, default=8080)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_server(args.host, args.port, args.health_port))


if __name__ == "__main__":
    main()
