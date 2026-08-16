"""Async WebSocket notification server backed by Redis and SQLite."""

import asyncio
import json
import os
import sqlite3
import threading
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any, AsyncIterator
from urllib.parse import quote, unquote

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response


SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
BROKER_PREFIX = "notifications:"


class BaseTransport(ABC):
    """Protocol adapter between notification delivery and client connections."""

    @abstractmethod
    async def on_connect(self, server: "NotificationServer", connection: Any) -> None:
        """Serve a newly established client connection."""

    @abstractmethod
    async def on_disconnect(self, server: "NotificationServer", connection: Any) -> None:
        """Release transport-specific resources for a client connection."""

    @abstractmethod
    async def send_message(self, client: Any, message: dict[str, Any]) -> None:
        """Send one normalized notification to a client."""

    @abstractmethod
    async def broadcast(self, clients: list[Any], message: dict[str, Any]) -> None:
        """Send one normalized notification to multiple clients."""

    @asynccontextmanager
    async def listen(self, server: "NotificationServer", host: str, port: int) -> AsyncIterator[Any]:
        """Accept connections for this transport when it supports a listener."""
        raise NotImplementedError(f"{type(self).__name__} does not provide a listener")
        yield None


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport interface."""

    async def on_connect(self, server: "NotificationServer", connection: ServerConnection) -> None:
        client_id = await server._connect(connection)
        try:
            async for raw_message in connection:
                await server._handle_message(client_id, raw_message)
        except ConnectionClosed:
            pass
        finally:
            await server._disconnect(client_id)
            await self.on_disconnect(server, connection)

    async def on_disconnect(self, server: "NotificationServer", connection: ServerConnection) -> None:
        return None

    async def send_message(self, client: ServerConnection, message: dict[str, Any]) -> None:
        try:
            await client.send(json.dumps(message))
        except ConnectionClosed:
            pass

    async def broadcast(self, clients: list[ServerConnection], message: dict[str, Any]) -> None:
        await asyncio.gather(*(self.send_message(client, message) for client in clients))

    @asynccontextmanager
    async def listen(self, server: "NotificationServer", host: str, port: int) -> AsyncIterator[Any]:
        async with serve(server.handler, host, port, process_request=server.process_request) as listener:
            yield listener


class InMemoryBroker:
    """Process-local broker used only when REDIS_URL is not configured."""

    _subscribers: set[asyncio.Queue[str]] = set()

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def publish(self, message: dict[str, Any]) -> None:
        encoded = json.dumps(message)
        for subscriber in list(self._subscribers):
            subscriber.put_nowait(encoded)

    async def messages(self) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.add(queue)
        try:
            while True:
                yield json.loads(await queue.get())
        finally:
            self._subscribers.discard(queue)

    async def connect(self, client_id: str) -> None:
        return None

    async def disconnect(self, client_id: str) -> None:
        return None

    async def subscribe(self, client_id: str, channel: str) -> None:
        return None

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        return None

    async def connected(self, client_id: str) -> bool:
        return False


class RedisBroker:
    """Redis pub/sub transport and shared client/subscription registry."""

    def __init__(self, url: str | None = None, client: Any | None = None) -> None:
        if client is None:
            if url is None:
                raise ValueError("RedisBroker requires a Redis URL or client")
            import redis.asyncio as redis

            client = redis.from_url(url, decode_responses=True)
        self._redis = client
        self._pubsub: Any = None

    async def start(self) -> None:
        await self._redis.ping()
        self._pubsub = self._redis.pubsub()
        await self._pubsub.psubscribe(f"{BROKER_PREFIX}*")

    async def stop(self) -> None:
        if self._pubsub is not None:
            await self._pubsub.aclose()
            self._pubsub = None
        await self._redis.aclose()

    async def publish(self, message: dict[str, Any]) -> None:
        channel = message.get("channel")
        if message["type"] == "direct":
            destination = f"direct:{message['payload']['client_id']}"
        elif channel is None:
            destination = "broadcast"
        else:
            destination = f"channel:{quote(channel, safe='')}"
        await self._redis.publish(f"{BROKER_PREFIX}{destination}", json.dumps(message))

    async def messages(self) -> AsyncIterator[dict[str, Any]]:
        if self._pubsub is None:
            raise RuntimeError("Redis broker has not been started")
        async for event in self._pubsub.listen():
            if event["type"] == "pmessage":
                yield json.loads(event["data"])

    async def connect(self, client_id: str) -> None:
        await self._redis.hset(f"{BROKER_PREFIX}clients", client_id, "1")

    async def disconnect(self, client_id: str) -> None:
        pipeline = self._redis.pipeline()
        pipeline.hdel(f"{BROKER_PREFIX}clients", client_id)
        channels = await self._redis.smembers(f"{BROKER_PREFIX}client:{client_id}:channels")
        for channel in channels:
            pipeline.srem(f"{BROKER_PREFIX}channel:{quote(channel, safe='')}:clients", client_id)
        pipeline.delete(f"{BROKER_PREFIX}client:{client_id}:channels")
        await pipeline.execute()

    async def subscribe(self, client_id: str, channel: str) -> None:
        pipeline = self._redis.pipeline()
        pipeline.sadd(f"{BROKER_PREFIX}channel:{quote(channel, safe='')}:clients", client_id)
        pipeline.sadd(f"{BROKER_PREFIX}client:{client_id}:channels", channel)
        await pipeline.execute()

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        pipeline = self._redis.pipeline()
        pipeline.srem(f"{BROKER_PREFIX}channel:{quote(channel, safe='')}:clients", client_id)
        pipeline.srem(f"{BROKER_PREFIX}client:{client_id}:channels", channel)
        await pipeline.execute()

    async def connected(self, client_id: str) -> bool:
        return bool(await self._redis.hexists(f"{BROKER_PREFIX}clients", client_id))


class MessageStore:
    def __init__(self, database_url: str) -> None:
        path = database_url.removeprefix("sqlite:///")
        if database_url.startswith("sqlite:///") and path == ":memory:":
            path = ":memory:"
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, type TEXT NOT NULL, "
            "payload TEXT NOT NULL, timestamp TEXT NOT NULL)"
        )
        self._connection.commit()
        self._lock = threading.RLock()

    def save(self, message: dict[str, Any]) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (message.get("channel"), message["type"], json.dumps(message["payload"]), message["timestamp"]),
            )
            self._connection.commit()

    def list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages ORDER BY id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [
            {"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]}
            for row in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._connection.close()


class NotificationServer:
    """Manage clients while Redis distributes messages among server instances."""

    def __init__(
        self,
        redis_url: str | None = None,
        database_url: str | None = None,
        broker: Any | None = None,
        transport: BaseTransport | None = None,
    ) -> None:
        redis_url = redis_url if redis_url is not None else os.environ.get("REDIS_URL")
        database_url = database_url if database_url is not None else os.environ.get("DATABASE_URL", ":memory:")
        self.clients: dict[str, Any] = {}
        self.channels: dict[str, set[str]] = {}
        self._clients_lock = threading.RLock()
        self._broker = broker if broker is not None else RedisBroker(redis_url) if redis_url else InMemoryBroker()
        self._transport = transport if transport is not None else self._transport_from_config()
        self._store = MessageStore(database_url)
        self._worker: asyncio.Task[None] | None = None

    @staticmethod
    def _transport_from_config() -> BaseTransport:
        transport_name = os.environ.get("TRANSPORT", "websocket").lower()
        if transport_name == "websocket":
            return WebSocketTransport()
        raise ValueError(f"Unsupported transport: {transport_name}")

    @property
    def client_count(self) -> int:
        with self._clients_lock:
            return len(self.clients)

    async def start(self) -> None:
        await self._broker.start()
        self._worker = asyncio.create_task(self._deliver_messages())
        # Register the consumer before accepting WebSocket publishers.
        await asyncio.sleep(0)

    async def stop(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            self._worker = None
        await self._broker.stop()
        self._store.close()

    async def handler(self, connection: Any) -> None:
        await self._transport.on_connect(self, connection)

    async def _connect(self, connection: Any) -> str:
        client_id = uuid.uuid4().hex
        with self._clients_lock:
            self.clients[client_id] = connection
        await self._broker.connect(client_id)
        await self._send(connection, self._message("system", {"event": "connected", "client_id": client_id}))
        return client_id

    async def _disconnect(self, client_id: str) -> None:
        await self._broker.disconnect(client_id)
        with self._clients_lock:
            self.clients.pop(client_id, None)
            for channel, subscribers in list(self.channels.items()):
                subscribers.discard(client_id)
                if not subscribers:
                    del self.channels[channel]

    async def _handle_message(self, sender_id: str, raw_message: str | bytes) -> None:
        if isinstance(raw_message, bytes):
            await self._send_error(sender_id, "messages must be JSON text")
            return
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            await self._send_error(sender_id, "invalid JSON")
            return
        if not self._valid_message(message):
            await self._send_error(sender_id, "message must contain a supported type and a dict payload")
            return

        message_type, channel = message["type"], message.get("channel")
        if message_type in {"subscribe", "unsubscribe"}:
            if not self._valid_channel(channel):
                await self._send_error(sender_id, "subscription messages require a non-empty channel")
                return
            await self._update_subscription(sender_id, channel, message_type == "subscribe")
            return
        if channel is not None and not self._valid_channel(channel):
            await self._send_error(sender_id, "channel must be a non-empty string")
            return

        normalized = self._message(message_type, message["payload"], channel)
        if normalized["type"] == "direct" and not isinstance(normalized["payload"].get("client_id"), str):
            await self._send_error(sender_id, "direct messages require payload.client_id")
            return
        if normalized["type"] == "direct":
            recipient_id = normalized["payload"]["client_id"]
            with self._clients_lock:
                local_recipient = recipient_id in self.clients
            if not local_recipient and not await self._broker.connected(recipient_id):
                await self._send_error(sender_id, "target client is not connected")
                return
        self._store.save(normalized)
        await self._broker.publish(normalized)

    async def _deliver_messages(self) -> None:
        async for message in self._broker.messages():
            if message["type"] == "direct":
                with self._clients_lock:
                    recipient = self.clients.get(message["payload"]["client_id"])
                    recipients = [recipient] if recipient is not None else []
            elif message.get("channel") is None:
                with self._clients_lock:
                    recipients = list(self.clients.values())
            else:
                with self._clients_lock:
                    recipients = [self.clients[client_id] for client_id in self.channels.get(message["channel"], set()) if client_id in self.clients]
            await self._transport.broadcast(recipients, message)

    async def broadcast(self, message: dict[str, Any]) -> None:
        await self._broker.publish(message)

    async def broadcast_channel(self, channel: str, message: dict[str, Any]) -> None:
        await self._broker.publish(message)

    async def _update_subscription(self, client_id: str, channel: str, subscribe: bool) -> None:
        with self._clients_lock:
            if subscribe:
                self.channels.setdefault(channel, set()).add(client_id)
            else:
                subscribers = self.channels.get(channel)
                if subscribers is not None:
                    subscribers.discard(client_id)
                    if not subscribers:
                        del self.channels[channel]
        if subscribe:
            await self._broker.subscribe(client_id, channel)
        else:
            await self._broker.unsubscribe(client_id, channel)

    async def _send_error(self, client_id: str, detail: str) -> None:
        with self._clients_lock:
            client = self.clients.get(client_id)
        if client is not None:
            await self._send(client, self._message("system", {"event": "error", "detail": detail}))

    async def _send(self, client: Any, message: dict[str, Any]) -> None:
        await self._transport.send_message(client, message)

    @staticmethod
    def _valid_message(message: Any) -> bool:
        return isinstance(message, dict) and message.get("type") in SUPPORTED_TYPES and isinstance(message.get("payload"), dict)

    @staticmethod
    def _valid_channel(channel: Any) -> bool:
        return isinstance(channel, str) and bool(channel)

    @staticmethod
    def _message(message_type: str, payload: dict[str, Any], channel: str | None = None) -> dict[str, Any]:
        message = {"type": message_type, "payload": payload, "timestamp": datetime.now(timezone.utc).isoformat()}
        if channel is not None:
            message["channel"] = channel
        return message

    async def process_request(self, connection: ServerConnection, request: Request) -> Response | None:
        if request.path == "/health":
            body = json.dumps({"connected_clients": self.client_count}).encode()
        elif request.path == "/channels":
            with self._clients_lock:
                body = json.dumps({channel: len(subscribers) for channel, subscribers in self.channels.items()}).encode()
        elif request.path.startswith("/channels/") and request.path.endswith("/subscribers"):
            channel = unquote(request.path[len("/channels/"):-len("/subscribers")]).rstrip("/")
            if not channel:
                return None
            with self._clients_lock:
                subscribers = sorted(self.channels.get(channel, set()))
            body = json.dumps({"channel": channel, "subscribers": subscribers}).encode()
        elif request.path.startswith("/messages"):
            try:
                query = request.path.partition("?")[2]
                values = dict(item.split("=", 1) for item in query.split("&") if item)
                limit, offset = int(values.get("limit", "50")), int(values.get("offset", "0"))
                if limit < 0 or offset < 0:
                    raise ValueError
            except ValueError:
                body = json.dumps({"error": "limit and offset must be non-negative integers"}).encode()
                return Response(HTTPStatus.BAD_REQUEST, "Bad Request", Headers({"Content-Type": "application/json", "Content-Length": str(len(body))}), body)
            body = json.dumps(self._store.list(limit, offset)).encode()
        else:
            return None
        return Response(HTTPStatus.OK, "OK", Headers({"Content-Type": "application/json", "Content-Length": str(len(body))}), body)

    @asynccontextmanager
    async def listen(self, host: str = "127.0.0.1", port: int = 8765):
        await self.start()
        try:
            async with self._transport.listen(self, host, port) as listener:
                yield listener
        finally:
            await self.stop()


async def main() -> None:
    server = NotificationServer()
    async with server.listen("0.0.0.0", 8765):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
