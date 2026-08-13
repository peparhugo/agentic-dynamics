"""Async WebSocket notification server with a small HTTP health endpoint."""

import asyncio
import json
import os
import sqlite3
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote, urlsplit

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Response

MESSAGE_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
BROKER_CHANNEL = "notifications:messages"


class SQLiteMessageStore:
    """SQLite-backed history for accepted client messages."""

    def __init__(self, database_url: str | None = None) -> None:
        url = database_url or os.environ.get("DATABASE_URL", "sqlite:///:memory:")
        self.path = self._path_from_url(url)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS messages "
            "(id TEXT PRIMARY KEY, channel TEXT, type TEXT NOT NULL, payload TEXT NOT NULL, timestamp TEXT NOT NULL)"
        )
        self._connection.commit()
        self._lock = asyncio.Lock()

    @staticmethod
    def _path_from_url(url: str) -> str:
        return url.removeprefix("sqlite:///") if url.startswith("sqlite:///") else url

    async def save(self, message: dict[str, object]) -> None:
        async with self._lock:
            self._connection.execute(
                "INSERT INTO messages (id, channel, type, payload, timestamp) VALUES (?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, message.get("channel"), message["type"], json.dumps(message["payload"]), message["timestamp"]),
            )
            self._connection.commit()

    async def list(self, limit: int, offset: int) -> list[dict[str, object]]:
        async with self._lock:
            rows = self._connection.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY rowid DESC LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        return [
            {"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]}
            for row in rows
        ]

    def close(self) -> None:
        self._connection.close()


class RedisBroker:
    """Redis pub/sub transport and shared client subscription registry."""

    def __init__(self, redis: object) -> None:
        self._redis = redis

    @classmethod
    def from_url(cls, url: str) -> "RedisBroker":
        from redis.asyncio import Redis

        return cls(Redis.from_url(url, decode_responses=True))

    async def publish(self, channel: str, event: dict[str, object]) -> None:
        await self._redis.publish(channel, json.dumps(event))

    async def subscribe(self, channel: str) -> AsyncIterator[dict[str, object]]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for event in pubsub.listen():
                if event["type"] == "message":
                    yield json.loads(event["data"])
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    async def register_client(self, client_id: str, instance_id: str) -> None:
        await self._redis.hset("notifications:clients", client_id, instance_id)

    async def remove_client(self, client_id: str) -> None:
        await self._redis.hdel("notifications:clients", client_id)
        async for key in self._redis.scan_iter("notifications:channel:*"):
            await self._redis.srem(key, client_id)

    async def subscribe_client(self, client_id: str, channel: str) -> None:
        await self._redis.sadd(f"notifications:channel:{channel}", client_id)

    async def unsubscribe_client(self, client_id: str, channel: str) -> None:
        key = f"notifications:channel:{channel}"
        await self._redis.srem(key, client_id)
        if not await self._redis.scard(key):
            await self._redis.delete(key)

    async def channels(self) -> dict[str, int]:
        result = {}
        async for key in self._redis.scan_iter("notifications:channel:*"):
            result[key.removeprefix("notifications:channel:")] = await self._redis.scard(key)
        return result

    async def channel_subscribers(self, channel: str) -> list[str]:
        return sorted(await self._redis.smembers(f"notifications:channel:{channel}"))

    async def close(self) -> None:
        await self._redis.aclose()


class NotificationServer:
    """Manages connected clients and routes validated notification messages."""

    def __init__(self, broker: RedisBroker | None = None, message_store: SQLiteMessageStore | None = None) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()
        self._broker = broker or (RedisBroker.from_url(os.environ["REDIS_URL"]) if os.environ.get("REDIS_URL") else None)
        self._message_store = message_store or SQLiteMessageStore()
        self._instance_id = uuid.uuid4().hex
        self._listener_task: asyncio.Task[None] | None = None

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def handler(self, websocket: ServerConnection) -> None:
        await self.start()
        client_id = uuid.uuid4().hex
        async with self._lock:
            self._clients[client_id] = websocket
        if self._broker:
            await self._broker.register_client(client_id, self._instance_id)

        await self._send(
            websocket,
            self._message("system", {"event": "connected", "client_id": client_id}),
        )
        try:
            async for raw_message in websocket:
                await self._handle_message(client_id, raw_message)
        finally:
            async with self._lock:
                self._remove_client(client_id)
            if self._broker:
                await self._broker.remove_client(client_id)

    async def start(self) -> None:
        if self._broker and self._listener_task is None:
            self._listener_task = asyncio.create_task(self._listen_for_messages())

    async def close(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        self._message_store.close()
        if self._broker:
            await self._broker.close()

    async def _listen_for_messages(self) -> None:
        assert self._broker is not None
        async for event in self._broker.subscribe(BROKER_CHANNEL):
            target = event.pop("target", None)
            channel = event.pop("channel_target", None)
            if target is not None:
                await self._send_to_local_client(target, event)
            elif channel is not None:
                await self._broadcast_to_local_channel(channel, event)
            else:
                await self._broadcast_to_all_local(event)

    async def _handle_message(self, sender_id: str, raw_message: str | bytes) -> None:
        if isinstance(raw_message, bytes):
            await self._send_error(sender_id, "messages must be JSON text")
            return

        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            await self._send_error(sender_id, "invalid JSON")
            return

        if not self._is_valid_message(message):
            await self._send_error(sender_id, "invalid message format")
            return

        message["timestamp"] = self._timestamp()
        await self._message_store.save(message)
        if message["type"] == "subscribe":
            channel = self._channel_from(message)
            if channel is None:
                await self._send_error(sender_id, "subscribe messages require a channel")
                return
            await self.subscribe(sender_id, channel)
        elif message["type"] == "unsubscribe":
            channel = self._channel_from(message)
            if channel is None:
                await self._send_error(sender_id, "unsubscribe messages require a channel")
                return
            await self.unsubscribe(sender_id, channel)
        elif message["type"] == "direct":
            recipient_id = message["payload"].get("client_id")
            if not isinstance(recipient_id, str):
                await self._send_error(sender_id, "direct messages require payload.client_id")
                return
            await self.send_to(recipient_id, message)
        else:
            channel = message.get("channel")
            if channel is None:
                await self.broadcast(message)
            elif isinstance(channel, str) and channel:
                await self.broadcast_to_channel(channel, message)
            else:
                await self._send_error(sender_id, "channel must be a non-empty string")

    @staticmethod
    def _is_valid_message(message: object) -> bool:
        return (
            isinstance(message, dict)
            and message.get("type") in MESSAGE_TYPES
            and isinstance(message.get("payload"), dict)
            and isinstance(message.get("timestamp"), str)
        )

    @staticmethod
    def _channel_from(message: dict[str, object]) -> str | None:
        channel = message.get("channel")
        return channel if isinstance(channel, str) and channel else None

    async def subscribe(self, client_id: str, channel: str) -> bool:
        async with self._lock:
            if client_id not in self._clients:
                return False
            self._channels.setdefault(channel, set()).add(client_id)
        if self._broker:
            await self._broker.subscribe_client(client_id, channel)
        return True

    async def unsubscribe(self, client_id: str, channel: str) -> bool:
        async with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None or client_id not in subscribers:
                return False
            subscribers.remove(client_id)
            if not subscribers:
                self._channels.pop(channel, None)
        if self._broker:
            await self._broker.unsubscribe_client(client_id, channel)
        return True

    async def channels(self) -> dict[str, int]:
        if self._broker:
            return await self._broker.channels()
        async with self._lock:
            return {channel: len(subscribers) for channel, subscribers in self._channels.items()}

    async def channel_subscribers(self, channel: str) -> list[str]:
        if self._broker:
            return await self._broker.channel_subscribers(channel)
        async with self._lock:
            return sorted(self._channels.get(channel, set()))

    async def broadcast(self, message: dict[str, object]) -> None:
        if self._broker:
            await self._broker.publish(BROKER_CHANNEL, message)
            return
        await self._broadcast_to_all_local(message)

    async def _broadcast_to_all_local(self, message: dict[str, object]) -> None:
        async with self._lock:
            recipients = list(self._clients.items())
        await self._send_to_recipients(recipients, message)

    async def broadcast_to_channel(self, channel: str, message: dict[str, object]) -> None:
        if self._broker:
            await self._broker.publish(BROKER_CHANNEL, {**message, "channel_target": channel})
            return
        await self._broadcast_to_local_channel(channel, message)

    async def _broadcast_to_local_channel(self, channel: str, message: dict[str, object]) -> None:
        async with self._lock:
            recipients = [
                (client_id, self._clients[client_id])
                for client_id in self._channels.get(channel, set())
                if client_id in self._clients
            ]
        await self._send_to_recipients(recipients, message)

    async def _send_to_recipients(
        self, recipients: list[tuple[str, ServerConnection]], message: dict[str, object]
    ) -> None:
        await asyncio.gather(
            *(self._send(client, message, client_id) for client_id, client in recipients),
            return_exceptions=True,
        )

    async def send_to(self, client_id: str, message: dict[str, object]) -> bool:
        if self._broker:
            await self._broker.publish(BROKER_CHANNEL, {**message, "target": client_id})
            return True
        return await self._send_to_local_client(client_id, message)

    async def _send_to_local_client(self, client_id: str, message: dict[str, object]) -> bool:
        async with self._lock:
            client = self._clients.get(client_id)
        if client is None:
            return False
        await self._send(client, message, client_id)
        return True

    async def _send_error(self, client_id: str, detail: str) -> None:
        await self.send_to(client_id, self._message("system", {"event": "error", "detail": detail}))

    async def _send(
        self, websocket: ServerConnection, message: dict[str, object], client_id: str | None = None
    ) -> None:
        try:
            await websocket.send(json.dumps(message))
        except Exception:
            if client_id is not None:
                async with self._lock:
                    self._remove_client(client_id)

    def _remove_client(self, client_id: str) -> None:
        self._clients.pop(client_id, None)
        for channel, subscribers in list(self._channels.items()):
            subscribers.discard(client_id)
            if not subscribers:
                self._channels.pop(channel)

    @staticmethod
    def _message(message_type: str, payload: dict[str, object]) -> dict[str, object]:
        return {"type": message_type, "payload": payload, "timestamp": NotificationServer._timestamp()}

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()


def create_process_request(server: NotificationServer) -> Callable[..., Awaitable[Response | None]]:
    """Create the HTTP request handler bound to a notification server instance."""

    async def process_request(connection: ServerConnection, request: object) -> Response | None:
        path = urlsplit(getattr(request, "path", "")).path
        query = parse_qs(urlsplit(getattr(request, "path", "")).query)
        if path == "/health":
            body = json.dumps({"connected_clients": server.client_count}).encode()
        elif path == "/messages":
            try:
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
            except ValueError:
                return Response(400, "Bad Request", Headers({"Content-Type": "application/json"}), b'{"detail": "limit and offset must be integers"}')
            if limit < 0 or offset < 0:
                return Response(400, "Bad Request", Headers({"Content-Type": "application/json"}), b'{"detail": "limit and offset must be non-negative"}')
            body = json.dumps(await server._message_store.list(limit, offset)).encode()
        elif path == "/channels":
            body = json.dumps(await server.channels()).encode()
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            channel = unquote(path[len("/channels/") : -len("/subscribers")]).rstrip("/")
            if not channel:
                return None
            body = json.dumps(await server.channel_subscribers(channel)).encode()
        else:
            return None
        return Response(200, "OK", Headers({"Content-Type": "application/json"}), body)

    return process_request


async def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = NotificationServer()
    async with serve(server.handler, host, port, process_request=create_process_request(server)):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(run_server())
