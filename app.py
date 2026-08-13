"""Redis-backed WebSocket notification server with SQLite message history."""

import asyncio
import inspect
import json
import os
import sqlite3
import uuid
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs, urlsplit

from websockets.asyncio.server import ServerConnection, Server as WebSocketServer, serve

Message = dict[str, Any]
BrokerCallback = Callable[[Message], Awaitable[None]]
SUPPORTED_MESSAGE_TYPES = frozenset(
    {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
)
BROKER_CHANNEL = "notifications"
CLIENTS_KEY = "notifications:clients"


class MessageStore:
    """SQLite repository for messages distributed by the server."""

    def __init__(self, database_url: str | None = None) -> None:
        value = database_url or os.getenv("DATABASE_URL", ":memory:")
        self._connection = sqlite3.connect(self._path(value), check_same_thread=False)
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

    @staticmethod
    def _path(database_url: str) -> str:
        if database_url == "sqlite:///:memory:":
            return ":memory:"
        if database_url.startswith("sqlite://"):
            return urlsplit(database_url).path or ":memory:"
        return database_url

    def save(self, message: Message) -> None:
        self._connection.execute(
            "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
            (
                message.get("channel"),
                message["type"],
                json.dumps(message["payload"]),
                message["timestamp"],
            ),
        )
        self._connection.commit()

    def list(self, limit: int, offset: int) -> list[Message]:
        rows = self._connection.execute(
            "SELECT id, channel, type, payload, timestamp FROM messages "
            "ORDER BY id LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [
            {
                "id": row[0],
                "channel": row[1],
                "type": row[2],
                "payload": json.loads(row[3]),
                "timestamp": row[4],
            }
            for row in rows
        ]


class InMemoryBroker:
    """Local broker used when REDIS_URL is not configured."""

    def __init__(self) -> None:
        self._subscribers: list[BrokerCallback] = []

    async def start(self, callback: BrokerCallback) -> None:
        self._subscribers.append(callback)

    async def publish(self, message: Message) -> None:
        await asyncio.gather(*(callback(message) for callback in tuple(self._subscribers)))

    async def register_client(self, client_id: str, instance_id: str) -> None:
        return None

    async def unregister_client(self, client_id: str) -> None:
        return None

    async def subscribe_client(self, client_id: str, channel: str) -> None:
        return None

    async def unsubscribe_client(self, client_id: str, channel: str) -> None:
        return None

    async def close(self) -> None:
        return None


class RedisBroker:
    """Redis pub/sub transport and durable connection-state registry."""

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client
        self._pubsub: Any = None
        self._listener: asyncio.Task[None] | None = None

    async def start(self, callback: BrokerCallback) -> None:
        if self._listener is not None:
            return
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(BROKER_CHANNEL)

        async def listen() -> None:
            async for event in self._pubsub.listen():
                if event.get("type") != "message":
                    continue
                data = event["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                await callback(json.loads(data))

        self._listener = asyncio.create_task(listen())

    async def publish(self, message: Message) -> None:
        await self._redis.publish(BROKER_CHANNEL, json.dumps(message))

    async def register_client(self, client_id: str, instance_id: str) -> None:
        await self._redis.hset(CLIENTS_KEY, client_id, instance_id)

    async def unregister_client(self, client_id: str) -> None:
        await self._redis.hdel(CLIENTS_KEY, client_id)
        await self._redis.delete(f"notifications:client:{client_id}:channels")

    async def subscribe_client(self, client_id: str, channel: str) -> None:
        await self._redis.sadd(f"notifications:client:{client_id}:channels", channel)

    async def unsubscribe_client(self, client_id: str, channel: str) -> None:
        await self._redis.srem(f"notifications:client:{client_id}:channels", channel)

    async def close(self) -> None:
        if self._listener is not None:
            self._listener.cancel()
            try:
                await self._listener
            except asyncio.CancelledError:
                pass
        if self._pubsub is not None:
            await self._pubsub.unsubscribe(BROKER_CHANNEL)
            close = getattr(self._pubsub, "aclose", self._pubsub.close)()
            if inspect.isawaitable(close):
                await close


class NotificationServer:
    """Maintains local sockets while Redis distributes messages across instances."""

    def __init__(self, *, redis_client: Any = None, database_url: str | None = None) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()
        self._store = MessageStore(database_url)
        self._instance_id = str(uuid.uuid4())
        if redis_client is None and (redis_url := os.getenv("REDIS_URL")):
            from redis.asyncio import Redis

            redis_client = Redis.from_url(redis_url)
        self._broker: RedisBroker | InMemoryBroker = (
            RedisBroker(redis_client) if redis_client is not None else InMemoryBroker()
        )
        self._started = False

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def start(self) -> None:
        if not self._started:
            await self._broker.start(self._deliver)
            self._started = True

    async def close(self) -> None:
        await self._broker.close()

    async def handler(self, websocket: ServerConnection) -> None:
        await self.start()
        client_id = str(uuid.uuid4())
        async with self._lock:
            self._clients[client_id] = websocket
        await self._broker.register_client(client_id, self._instance_id)
        await self._send(websocket, self._message("system", {"client_id": client_id}))
        try:
            async for raw_message in websocket:
                await self._handle_message(client_id, raw_message)
        finally:
            async with self._lock:
                self._clients.pop(client_id, None)
                for channel in tuple(self._channels):
                    self._channels[channel].discard(client_id)
                    if not self._channels[channel]:
                        del self._channels[channel]
            await self._broker.unregister_client(client_id)

    async def broadcast(self, message: Message) -> None:
        """Persist and distribute a message through the configured broker."""
        await self.start()
        self._store.save(message)
        await self._broker.publish(message)

    async def _handle_message(self, sender_id: str, raw_message: str | bytes) -> None:
        try:
            message = self._validate_message(json.loads(raw_message))
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            await self._send_error(sender_id, str(error))
            return
        if message["type"] in {"subscribe", "unsubscribe"}:
            await self._update_subscription(sender_id, message)
            return
        if message["type"] == "direct" and not isinstance(message["payload"].get("client_id"), str):
            await self._send_error(sender_id, "direct messages require payload.client_id")
            return
        await self.broadcast(message)

    async def _update_subscription(self, client_id: str, message: Message) -> None:
        channel = message.get("channel")
        if channel is None:
            await self._send_error(client_id, f"{message['type']} messages require channel")
            return
        async with self._lock:
            if message["type"] == "subscribe":
                self._channels.setdefault(channel, set()).add(client_id)
            else:
                subscribers = self._channels.get(channel)
                if subscribers is not None:
                    subscribers.discard(client_id)
                    if not subscribers:
                        del self._channels[channel]
        if message["type"] == "subscribe":
            await self._broker.subscribe_client(client_id, channel)
        else:
            await self._broker.unsubscribe_client(client_id, channel)

    async def _deliver(self, message: Message) -> None:
        async with self._lock:
            if "channel" in message:
                clients = tuple(
                    self._clients[client_id]
                    for client_id in self._channels.get(message["channel"], set())
                    if client_id in self._clients
                )
            elif message["type"] == "direct":
                recipient = self._clients.get(message["payload"]["client_id"])
                clients = (recipient,) if recipient is not None else ()
            else:
                clients = tuple(self._clients.values())
        await asyncio.gather(*(self._send(client, message) for client in clients), return_exceptions=True)

    @staticmethod
    def _message(message_type: str, payload: dict[str, Any]) -> Message:
        return {"type": message_type, "payload": payload, "timestamp": datetime.now(timezone.utc).isoformat()}

    @staticmethod
    def _validate_message(value: Any) -> Message:
        if not isinstance(value, Mapping):
            raise ValueError("message must be a JSON object")
        message_type, payload, timestamp = value.get("type"), value.get("payload"), value.get("timestamp")
        if message_type not in SUPPORTED_MESSAGE_TYPES:
            raise ValueError("unsupported message type")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        if not isinstance(timestamp, str):
            raise ValueError("timestamp must be a string")
        channel = value.get("channel")
        if channel is not None and (not isinstance(channel, str) or not channel):
            raise ValueError("channel must be a non-empty string")
        message = {"type": message_type, "payload": payload, "timestamp": timestamp}
        if channel is not None:
            message["channel"] = channel
        return message

    async def _send_error(self, client_id: str, detail: str) -> None:
        async with self._lock:
            client = self._clients.get(client_id)
        if client is not None:
            await self._send(client, self._message("system", {"error": detail}))

    @staticmethod
    async def _send(client: ServerConnection, message: Message) -> None:
        try:
            await client.send(json.dumps(message))
        except Exception:
            pass

    async def process_request(self, connection: ServerConnection, request: Any) -> Any:
        parsed = urlsplit(request.path)
        if parsed.path == "/health":
            return connection.respond(HTTPStatus.OK, json.dumps({"connected_clients": self.client_count}))
        if parsed.path == "/messages":
            params = parse_qs(parsed.query)
            try:
                limit, offset = int(params.get("limit", ["50"])[0]), int(params.get("offset", ["0"])[0])
                if limit < 0 or offset < 0:
                    raise ValueError
            except ValueError:
                return connection.respond(HTTPStatus.BAD_REQUEST, "limit and offset must be non-negative integers")
            return connection.respond(HTTPStatus.OK, json.dumps({"messages": self._store.list(limit, offset)}))
        if parsed.path == "/channels":
            async with self._lock:
                channels = {name: len(subscribers) for name, subscribers in self._channels.items()}
            return connection.respond(HTTPStatus.OK, json.dumps({"channels": channels}))
        if parsed.path.startswith("/channels/") and parsed.path.endswith("/subscribers"):
            name = parsed.path[len("/channels/") : -len("/subscribers")].strip("/")
            if not name:
                return connection.respond(HTTPStatus.NOT_FOUND, "Not found")
            async with self._lock:
                subscribers = sorted(self._channels.get(name, set()))
            return connection.respond(HTTPStatus.OK, json.dumps({"subscribers": subscribers}))
        return None


async def start_server(host: str = "127.0.0.1", port: int = 8765) -> WebSocketServer:
    """Start and return the notification server without blocking the event loop."""
    notification_server = NotificationServer()
    await notification_server.start()
    return await serve(notification_server.handler, host, port, process_request=notification_server.process_request)


async def main() -> None:
    server = await start_server()
    await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
