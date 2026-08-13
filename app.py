"""WebSocket notification server backed by Redis and SQLite."""

import asyncio
import json
import os
import sqlite3
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from websockets.asyncio.server import ServerConnection, serve


SUPPORTED_MESSAGE_TYPES = frozenset({"broadcast", "direct", "system", "subscribe", "unsubscribe"})
BROKER_CHANNEL = "notifications:messages"
RATE_LIMIT_WINDOW_SECONDS = 60


class BaseTransport(ABC):
    """Connection adapter used by ``NotificationServer`` to deliver messages."""

    @abstractmethod
    async def on_connect(self, connection: Any) -> str:
        """Initialize a connection and return its transport-specific client ID."""

    @abstractmethod
    async def on_disconnect(self, connection: Any) -> None:
        """Release resources associated with a connection."""

    @abstractmethod
    async def send_message(self, connection: Any, message: dict[str, Any]) -> None:
        """Send one notification to a connection."""

    @abstractmethod
    async def broadcast(self, connections: list[Any], message: dict[str, Any]) -> list[BaseException | None]:
        """Send one notification to a collection of connections."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport interface."""

    async def on_connect(self, connection: ServerConnection) -> str:
        return str(connection.id)

    async def on_disconnect(self, connection: ServerConnection) -> None:
        # websockets owns the underlying connection lifecycle.
        return None

    async def send_message(self, connection: ServerConnection, message: dict[str, Any]) -> None:
        await connection.send(json.dumps(message))

    async def broadcast(
        self, connections: list[ServerConnection], message: dict[str, Any]
    ) -> list[BaseException | None]:
        payload = json.dumps(message)
        return list(await asyncio.gather(*(connection.send(payload) for connection in connections), return_exceptions=True))

    async def handle_connection(self, server: "NotificationServer", websocket: ServerConnection) -> None:
        client_id = await server.register(websocket)
        await server.send_to_client(client_id, system_message({"client_id": client_id, "event": "connected"}))
        try:
            async for raw_message in websocket:
                try:
                    message = server._validate_message(json.loads(raw_message))
                except (json.JSONDecodeError, ValueError) as error:
                    await server.send_to_client(client_id, system_message({"error": str(error)}))
                    continue
                await server.handle_message(client_id, message)
        finally:
            await server.unregister(websocket)


def configured_transport() -> BaseTransport:
    """Create the transport selected by TRANSPORT, defaulting to WebSockets."""

    transport_name = os.environ.get("TRANSPORT", "websocket").lower()
    if transport_name == "websocket":
        return WebSocketTransport()
    raise ValueError(f"unsupported transport: {transport_name}")


class InMemoryBroker:
    """Process-local Redis substitute used when REDIS_URL isn't configured."""

    _instances: dict[str, str] = {}
    _subscriptions: dict[str, set[str]] = {}
    _listeners: set[asyncio.Queue[str]] = set()
    _rate_limits: dict[str, tuple[int, datetime]] = {}
    _lock = asyncio.Lock()

    async def listen(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        async with self._lock:
            self._listeners.add(queue)
        return queue

    async def publish(self, message: dict[str, Any]) -> None:
        encoded = json.dumps(message)
        async with self._lock:
            for listener in tuple(self._listeners):
                listener.put_nowait(encoded)

    async def set_client(self, client_id: str, instance_id: str) -> None:
        async with self._lock:
            self._instances[client_id] = instance_id

    async def remove_client(self, client_id: str) -> None:
        async with self._lock:
            self._instances.pop(client_id, None)
            for channel in tuple(self._subscriptions):
                self._subscriptions[channel].discard(client_id)
                if not self._subscriptions[channel]:
                    del self._subscriptions[channel]

    async def subscribe_client(self, channel: str, client_id: str) -> None:
        async with self._lock:
            self._subscriptions.setdefault(channel, set()).add(client_id)

    async def unsubscribe_client(self, channel: str, client_id: str) -> None:
        async with self._lock:
            subscribers = self._subscriptions.get(channel)
            if subscribers:
                subscribers.discard(client_id)
                if not subscribers:
                    del self._subscriptions[channel]

    async def client_owner(self, client_id: str) -> str | None:
        async with self._lock:
            return self._instances.get(client_id)

    async def subscribers(self, channel: str) -> set[str]:
        async with self._lock:
            return set(self._subscriptions.get(channel, set()))

    async def channels(self) -> list[dict[str, Any]]:
        async with self._lock:
            return [
                {"name": name, "subscriber_count": len(subscribers)}
                for name, subscribers in sorted(self._subscriptions.items())
            ]

    async def increment_rate_limit(self, client_id: str) -> int:
        now = datetime.now(timezone.utc)
        async with self._lock:
            count, expires_at = self._rate_limits.get(client_id, (0, now))
            if expires_at <= now:
                count = 0
                expires_at = now + timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
            count += 1
            self._rate_limits[client_id] = (count, expires_at)
            return count


class RedisBroker:
    """Redis pub/sub and key storage adapter shared by all server instances."""

    def __init__(self, url: str) -> None:
        import redis.asyncio as redis

        self.redis = redis.from_url(url, decode_responses=True)
        self.pubsub = self.redis.pubsub()

    async def listen(self) -> Any:
        await self.pubsub.subscribe(BROKER_CHANNEL)
        return self.pubsub

    async def publish(self, message: dict[str, Any]) -> None:
        await self.redis.publish(BROKER_CHANNEL, json.dumps(message))

    async def set_client(self, client_id: str, instance_id: str) -> None:
        await self.redis.set(f"notifications:client:{client_id}", instance_id)

    async def remove_client(self, client_id: str) -> None:
        pipeline = self.redis.pipeline()
        pipeline.delete(f"notifications:client:{client_id}")
        # The channel index lets cleanup work without an in-process subscription map.
        channels = await self.redis.smembers(f"notifications:client-channels:{client_id}")
        for channel in channels:
            pipeline.srem(f"notifications:channel:{channel}", client_id)
        pipeline.delete(f"notifications:client-channels:{client_id}")
        await pipeline.execute()

    async def subscribe_client(self, channel: str, client_id: str) -> None:
        pipeline = self.redis.pipeline()
        pipeline.sadd(f"notifications:channel:{channel}", client_id)
        pipeline.sadd(f"notifications:client-channels:{client_id}", channel)
        await pipeline.execute()

    async def unsubscribe_client(self, channel: str, client_id: str) -> None:
        pipeline = self.redis.pipeline()
        pipeline.srem(f"notifications:channel:{channel}", client_id)
        pipeline.srem(f"notifications:client-channels:{client_id}", channel)
        await pipeline.execute()

    async def client_owner(self, client_id: str) -> str | None:
        return await self.redis.get(f"notifications:client:{client_id}")

    async def subscribers(self, channel: str) -> set[str]:
        return set(await self.redis.smembers(f"notifications:channel:{channel}"))

    async def channels(self) -> list[dict[str, Any]]:
        names: set[str] = set()
        async for key in self.redis.scan_iter(match="notifications:channel:*"):
            names.add(key.removeprefix("notifications:channel:"))
        return [
            {"name": name, "subscriber_count": await self.redis.scard(f"notifications:channel:{name}")}
            for name in sorted(names)
            if await self.redis.scard(f"notifications:channel:{name}")
        ]

    async def increment_rate_limit(self, client_id: str) -> int:
        # INCR and EXPIRE execute atomically so every counter has a one-minute TTL.
        return int(
            await self.redis.eval(
                "local count = redis.call('INCR', KEYS[1]); "
                "if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end; "
                "return count",
                1,
                f"notifications:rate-limit:{client_id}",
                RATE_LIMIT_WINDOW_SECONDS,
            )
        )


class MessageStore:
    def __init__(self, database_url: str) -> None:
        path = database_url.removeprefix("sqlite:///")
        self.path = ":memory:" if path == "sqlite:///:memory:" else path
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, type TEXT NOT NULL, payload TEXT NOT NULL, timestamp TEXT NOT NULL)"
            )

    async def save(self, message: dict[str, Any]) -> None:
        def insert() -> None:
            with self._connection() as connection:
                connection.execute(
                    "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                    (message.get("channel"), message["type"], json.dumps(message["payload"]), message["timestamp"]),
                )
        await asyncio.to_thread(insert)

    async def messages(self, limit: int, offset: int) -> list[dict[str, Any]]:
        def select() -> list[dict[str, Any]]:
            with self._connection() as connection:
                rows = connection.execute(
                    "SELECT id, channel, type, payload, timestamp FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
            return [
                {"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]}
                for row in rows
            ]
        return await asyncio.to_thread(select)

    async def history(self, channel: str, since: str, limit: int) -> tuple[list[dict[str, Any]], bool]:
        def select() -> tuple[list[dict[str, Any]], bool]:
            with self._connection() as connection:
                rows = connection.execute(
                    "SELECT id, channel, type, payload, timestamp FROM messages "
                    "WHERE channel = ? AND timestamp >= ? "
                    "ORDER BY timestamp ASC, id ASC LIMIT ?",
                    (channel, since, limit + 1),
                ).fetchall()
            has_more = len(rows) > limit
            return (
                [
                    {"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]}
                    for row in rows[:limit]
                ],
                has_more,
            )
        return await asyncio.to_thread(select)

    async def cleanup(self, ttl_days: int) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=ttl_days)).isoformat()

        def delete() -> None:
            with self._connection() as connection:
                connection.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff,))

        await asyncio.to_thread(delete)


class NotificationServer:
    """Coordinates notifications independently of the connection transport."""

    def __init__(
        self,
        broker: Any | None = None,
        database_url: str | None = None,
        transport: BaseTransport | None = None,
        rate_limit: int | None = None,
        message_ttl_days: int | None = None,
    ) -> None:
        redis_url = os.environ.get("REDIS_URL")
        self.broker = broker or (RedisBroker(redis_url) if redis_url else InMemoryBroker())
        self.store = MessageStore(database_url or os.environ.get("DATABASE_URL", "sqlite:///notifications.db"))
        self.instance_id = str(uuid.uuid4())
        self.transport = transport or configured_transport()
        self.rate_limit = rate_limit if rate_limit is not None else int(os.environ.get("RATE_LIMIT", "100"))
        self.message_ttl_days = (
            message_ttl_days if message_ttl_days is not None else int(os.environ.get("MESSAGE_TTL_DAYS", "7"))
        )
        if self.rate_limit < 0 or self.message_ttl_days < 0:
            raise ValueError("RATE_LIMIT and MESSAGE_TTL_DAYS must be non-negative integers")
        self.clients: dict[str, Any] = {}
        self._connection_ids: dict[int, str] = {}
        self._clients_lock = asyncio.Lock()
        self._worker: asyncio.Task[None] | None = None
        self._cleanup_worker: asyncio.Task[None] | None = None

    @property
    def connected_client_count(self) -> int:
        return len(self.clients)

    async def _start_worker(self) -> None:
        if self._worker is None:
            listener = await self.broker.listen()
            self._worker = asyncio.create_task(self._deliver_messages(listener))

    async def start(self) -> None:
        await self._start_worker()
        if self._cleanup_worker is None:
            self._cleanup_worker = asyncio.create_task(self._cleanup_messages())

    async def close(self) -> None:
        for worker in (self._worker, self._cleanup_worker):
            if worker is not None:
                worker.cancel()
        await asyncio.gather(*(worker for worker in (self._worker, self._cleanup_worker) if worker is not None), return_exceptions=True)
        self._worker = None
        self._cleanup_worker = None

    async def _cleanup_messages(self) -> None:
        while True:
            await self.store.cleanup(self.message_ttl_days)
            await asyncio.sleep(24 * 60 * 60)

    async def _deliver_messages(self, listener: Any) -> None:
        if isinstance(listener, asyncio.Queue):
            while True:
                await self._deliver(json.loads(await listener.get()))
        else:
            async for event in listener.listen():
                if event["type"] == "message":
                    await self._deliver(json.loads(event["data"]))

    async def register(self, connection: Any) -> str:
        await self.start()
        client_id = await self.transport.on_connect(connection)
        async with self._clients_lock:
            self.clients[client_id] = connection
            self._connection_ids[id(connection)] = client_id
        await self.broker.set_client(client_id, self.instance_id)
        return client_id

    async def unregister(self, connection: Any) -> None:
        async with self._clients_lock:
            client_id = self._connection_ids.pop(id(connection), None)
            if client_id is None:
                return
            self.clients.pop(client_id, None)
        await self.broker.remove_client(client_id)
        await self.transport.on_disconnect(connection)

    async def _local_clients(self, client_ids: set[str] | None = None) -> list[Any]:
        async with self._clients_lock:
            if client_ids is None:
                return list(self.clients.values())
            return [self.clients[client_id] for client_id in client_ids if client_id in self.clients]

    @staticmethod
    def _validate_message(message: Any) -> dict[str, Any]:
        if not isinstance(message, dict):
            raise ValueError("message must be a JSON object")
        if message.get("type") not in SUPPORTED_MESSAGE_TYPES:
            raise ValueError("unsupported message type")
        if not isinstance(message.get("payload"), dict):
            raise ValueError("payload must be a JSON object")
        if not isinstance(message.get("timestamp"), str) or not message["timestamp"]:
            raise ValueError("timestamp must be a non-empty string")
        channel = message.get("channel")
        if channel is not None and (not isinstance(channel, str) or not channel):
            raise ValueError("channel must be a non-empty string")
        if message["type"] in {"subscribe", "unsubscribe"}:
            if not isinstance(message["payload"].get("channel", channel), str) or not message["payload"].get("channel", channel):
                raise ValueError("subscription channel must be a non-empty string")
        return message

    async def _send(self, clients: list[Any], message: dict[str, Any]) -> None:
        results = list(
            await asyncio.gather(*(self.transport.send_message(client, message) for client in clients), return_exceptions=True)
        )
        await self._remove_failed_clients(clients, results)

    async def _remove_failed_clients(self, clients: list[Any], results: list[BaseException | None]) -> None:
        for client, result in zip(clients, results):
            if isinstance(result, BaseException):
                await self.unregister(client)

    async def send_to_client(self, client_id: str, message: dict[str, Any]) -> None:
        await self._send(await self._local_clients({client_id}), message)

    async def _deliver(self, message: dict[str, Any]) -> None:
        if message["type"] == "broadcast":
            channel = message.get("channel")
            clients = await self._local_clients(await self.broker.subscribers(channel) if channel else None)
            results = await self.transport.broadcast(clients, message)
            await self._remove_failed_clients(clients, results)
        elif message["type"] == "direct":
            client_id = str(message["payload"].get("client_id"))
            if await self.broker.client_owner(client_id) == self.instance_id:
                await self.send_to_client(client_id, message)

    async def update_subscription(self, client_id: str, message: dict[str, Any]) -> None:
        channel = message["payload"].get("channel", message.get("channel"))
        if message["type"] == "subscribe":
            await self.broker.subscribe_client(channel, client_id)
        else:
            await self.broker.unsubscribe_client(channel, client_id)

    async def handle_message(self, client_id: str, message: dict[str, Any]) -> None:
        if await self.broker.increment_rate_limit(client_id) > self.rate_limit:
            await self.send_to_client(client_id, system_message({"error": "rate limit exceeded"}))
            return
        await self.store.save(message)
        if message["type"] in {"subscribe", "unsubscribe"}:
            await self.update_subscription(client_id, message)
        elif message["type"] in {"broadcast", "direct"}:
            await self.broker.publish(message)

    async def handle_connection(self, websocket: ServerConnection) -> None:
        if not isinstance(self.transport, WebSocketTransport):
            raise RuntimeError("handle_connection is only available with the websocket transport")
        await self.transport.handle_connection(self, websocket)

    async def health_response(self, connection: ServerConnection, request: Any) -> Any:
        parsed = urlsplit(request.path)
        if parsed.path == "/health":
            return connection.respond(HTTPStatus.OK, json.dumps({"connected_clients": self.connected_client_count}))
        if parsed.path == "/messages":
            query = parse_qs(parsed.query)
            try:
                limit, offset = int(query.get("limit", ["50"])[0]), int(query.get("offset", ["0"])[0])
                if limit < 0 or offset < 0:
                    raise ValueError
            except ValueError:
                return connection.respond(HTTPStatus.BAD_REQUEST, json.dumps({"error": "limit and offset must be non-negative integers"}))
            return connection.respond(HTTPStatus.OK, json.dumps({"messages": await self.store.messages(limit, offset)}))
        if parsed.path == "/history":
            query = parse_qs(parsed.query)
            channel = query.get("channel", [""])[0]
            since = query.get("since", [""])[0]
            try:
                limit = int(query.get("limit", ["50"])[0])
                if not channel or not since or limit < 0:
                    raise ValueError
                datetime.fromisoformat(since.replace("Z", "+00:00"))
            except ValueError:
                return connection.respond(
                    HTTPStatus.BAD_REQUEST,
                    json.dumps({"error": "channel, since, and a non-negative integer limit are required"}),
                )
            messages, has_more = await self.store.history(channel, since, limit)
            return connection.respond(HTTPStatus.OK, json.dumps({"messages": messages, "has_more": has_more}))
        if parsed.path == "/channels":
            return connection.respond(HTTPStatus.OK, json.dumps({"channels": await self.broker.channels()}))
        prefix, suffix = "/channels/", "/subscribers"
        if parsed.path.startswith(prefix) and parsed.path.endswith(suffix):
            name = unquote(parsed.path[len(prefix):-len(suffix)])
            if name:
                return connection.respond(HTTPStatus.OK, json.dumps({"channel": name, "subscribers": sorted(await self.broker.subscribers(name))}))
        return None


def system_message(payload: dict[str, Any]) -> dict[str, Any]:
    return {"type": "system", "payload": payload, "timestamp": datetime.now(timezone.utc).isoformat()}


async def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    notification_server = NotificationServer()
    await notification_server.start()
    try:
        async with serve(notification_server.handle_connection, host, port, process_request=notification_server.health_response) as server:
            await server.serve_forever()
    finally:
        await notification_server.close()


if __name__ == "__main__":
    asyncio.run(run_server())
