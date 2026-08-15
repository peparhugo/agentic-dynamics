"""Async WebSocket notification server with Redis distribution and SQLite history."""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import os
import sqlite3
import threading
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable
from uuid import uuid4


MESSAGE_TYPES = frozenset({"broadcast", "direct", "system", "subscribe", "unsubscribe"})
BROKER_CHANNEL = "notifications:messages"
RATE_LIMIT_WINDOW_SECONDS = 60
CLEANUP_INTERVAL_SECONDS = 24 * 60 * 60
MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]


class InMemoryBroker:
    """A process-local broker used when Redis hasn't been configured."""

    def __init__(self) -> None:
        self.clients: set[str] = set()
        self.channels: dict[str, set[str]] = defaultdict(set)
        self._handlers: set[MessageHandler] = set()

    async def start(self, handler: MessageHandler) -> None:
        self._handlers.add(handler)

    async def stop(self, handler: MessageHandler) -> None:
        self._handlers.discard(handler)

    async def publish(self, message: dict[str, Any]) -> None:
        await asyncio.gather(*(handler(message) for handler in list(self._handlers)))

    async def add_client(self, client_id: str) -> None:
        self.clients.add(client_id)

    async def remove_client(self, client_id: str) -> None:
        self.clients.discard(client_id)
        for channel in list(self.channels):
            self.channels[channel].discard(client_id)
            if not self.channels[channel]:
                del self.channels[channel]

    async def has_client(self, client_id: str) -> bool:
        return client_id in self.clients

    async def subscribe(self, client_id: str, channel: str) -> None:
        self.channels[channel].add(client_id)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        self.channels[channel].discard(client_id)
        if not self.channels[channel]:
            del self.channels[channel]

    async def channel_members(self, channel: str) -> list[str]:
        return sorted(self.channels.get(channel, set()))

    async def channel_summary(self) -> list[dict[str, Any]]:
        return [{"name": name, "subscriber_count": len(members)} for name, members in sorted(self.channels.items())]


class RedisBroker:
    """Redis pub/sub and Redis-backed connection state shared by server instances."""

    def __init__(self, redis: Any) -> None:
        self.redis = redis
        self._pubsub: Any = None
        self._listener: asyncio.Task[None] | None = None

    async def start(self, handler: MessageHandler) -> None:
        self._pubsub = self.redis.pubsub()
        await self._pubsub.subscribe(BROKER_CHANNEL)

        async def listen() -> None:
            async for event in self._pubsub.listen():
                if event.get("type") != "message":
                    continue
                data = event["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                await handler(json.loads(data))

        self._listener = asyncio.create_task(listen())

    async def stop(self, _handler: MessageHandler) -> None:
        if self._listener is not None:
            self._listener.cancel()
            try:
                await self._listener
            except asyncio.CancelledError:
                pass
            self._listener = None
        if self._pubsub is not None:
            await self._pubsub.unsubscribe(BROKER_CHANNEL)
            await self._pubsub.aclose()
            self._pubsub = None

    async def publish(self, message: dict[str, Any]) -> None:
        await self.redis.publish(BROKER_CHANNEL, json.dumps(message))

    async def add_client(self, client_id: str) -> None:
        await self.redis.sadd("notifications:clients", client_id)

    async def remove_client(self, client_id: str) -> None:
        await self.redis.srem("notifications:clients", client_id)
        for key in await self.redis.smembers("notifications:channels"):
            channel = key.decode() if isinstance(key, bytes) else key
            await self.redis.srem(f"notifications:channel:{channel}", client_id)

    async def has_client(self, client_id: str) -> bool:
        return bool(await self.redis.sismember("notifications:clients", client_id))

    async def subscribe(self, client_id: str, channel: str) -> None:
        await self.redis.sadd("notifications:channels", channel)
        await self.redis.sadd(f"notifications:channel:{channel}", client_id)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        key = f"notifications:channel:{channel}"
        await self.redis.srem(key, client_id)
        if not await self.redis.scard(key):
            await self.redis.srem("notifications:channels", channel)

    async def channel_members(self, channel: str) -> list[str]:
        members = await self.redis.smembers(f"notifications:channel:{channel}")
        return sorted(member.decode() if isinstance(member, bytes) else member for member in members)

    async def channel_summary(self) -> list[dict[str, Any]]:
        names = await self.redis.smembers("notifications:channels")
        result = []
        for raw_name in names:
            name = raw_name.decode() if isinstance(raw_name, bytes) else raw_name
            result.append({"name": name, "subscriber_count": await self.redis.scard(f"notifications:channel:{name}")})
        return sorted(result, key=lambda item: item["name"])


class BaseTransport(ABC):
    """Connection transport used by ``NotificationServer``."""

    @property
    @abstractmethod
    def port(self) -> int:
        """Return the listening port."""

    @abstractmethod
    async def start(self, host: str, port: int, client_handler: Callable[[Any], Awaitable[None]], server: "NotificationServer") -> None:
        """Start accepting clients and dispatch them to ``client_handler``."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop accepting clients."""

    @abstractmethod
    async def on_connect(self, connection: Any) -> None:
        """Handle a new transport connection."""

    @abstractmethod
    async def on_disconnect(self, connection: Any) -> None:
        """Handle a closed transport connection."""

    @abstractmethod
    async def send_message(self, connection: Any, message: str) -> None:
        """Send an encoded message to one connection."""

    @abstractmethod
    async def broadcast(self, connections: list[Any], message: str) -> None:
        """Send an encoded message to several connections."""


class WebSocketTransport(BaseTransport):
    """The default WebSocket implementation of the notification transport."""

    def __init__(self) -> None:
        self._server: Any = None
        self._client_handler: Callable[[Any], Awaitable[None]] | None = None

    @property
    def port(self) -> int:
        if self._server is None or not self._server.sockets:
            raise RuntimeError("server is not running")
        return self._server.sockets[0].getsockname()[1]

    async def start(self, host: str, port: int, client_handler: Callable[[Any], Awaitable[None]], server: "NotificationServer") -> None:
        from websockets.asyncio.server import serve

        self._client_handler = client_handler
        self._server = await serve(self._handle_connection, host, port, process_request=lambda connection, request: self._handle_http(server, request))

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self._client_handler = None

    async def on_connect(self, _connection: Any) -> None:
        pass

    async def on_disconnect(self, _connection: Any) -> None:
        pass

    async def send_message(self, connection: Any, message: str) -> None:
        await connection.send(message)

    async def broadcast(self, connections: list[Any], message: str) -> None:
        results = await asyncio.gather(*(self.send_message(connection, message) for connection in connections), return_exceptions=True)
        if any(isinstance(result, Exception) for result in results):
            return

    async def _handle_connection(self, connection: Any) -> None:
        assert self._client_handler is not None
        await self.on_connect(connection)
        try:
            await self._client_handler(connection)
        finally:
            await self.on_disconnect(connection)

    async def _handle_http(self, server: "NotificationServer", request: Any) -> Any:
        from urllib.parse import parse_qs, urlsplit

        from websockets.datastructures import Headers
        from websockets.http11 import Response

        parsed = urlsplit(request.path)
        if parsed.path == "/health":
            value, status = {"connected_clients": server.client_count}, "200 OK"
        elif parsed.path == "/channels":
            assert server._broker is not None
            value, status = {"channels": await server._broker.channel_summary()}, "200 OK"
        elif parsed.path.startswith("/channels/") and parsed.path.endswith("/subscribers"):
            name = parsed.path[len("/channels/") : -len("/subscribers")].rstrip("/")
            if not name:
                return None
            assert server._broker is not None
            value, status = {"channel": name, "subscribers": await server._broker.channel_members(name)}, "200 OK"
        elif parsed.path == "/messages":
            try:
                query = parse_qs(parsed.query)
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
                if limit < 0 or offset < 0:
                    raise ValueError
            except ValueError:
                value, status = {"error": "limit and offset must be non-negative integers"}, "400 Bad Request"
            else:
                value, status = {"messages": server._messages(limit, offset)}, "200 OK"
        elif parsed.path == "/history":
            try:
                query = parse_qs(parsed.query)
                channel = query["channel"][0]
                since = datetime.fromisoformat(query["since"][0].replace("Z", "+00:00"))
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
                if not channel or since.tzinfo is None or limit < 1 or offset < 0:
                    raise ValueError
            except (KeyError, IndexError, ValueError):
                value, status = {"error": "channel, timezone-aware since, positive limit, and non-negative offset are required"}, "400 Bad Request"
            else:
                messages, has_more = server._history(channel, since, limit, offset)
                value, status = {"messages": messages, "has_more": has_more}, "200 OK"
        else:
            return None
        body = json.dumps(value).encode("utf-8")
        return Response(int(status[:3]), status[4:], Headers({"Content-Type": "application/json", "Content-Length": str(len(body))}), body)


class NotificationServer:
    """Coordinates notification delivery independently of its connection transport."""

    def __init__(self, broker: InMemoryBroker | RedisBroker | None = None, database_url: str | None = None, transport: BaseTransport | None = None) -> None:
        self._clients: dict[str, Any] = {}
        self._channels: dict[str, set[str]] = defaultdict(set)
        self._clients_lock = threading.RLock()
        self._transport = transport or self._configured_transport()
        self._broker = broker
        self._database_url = database_url or os.environ.get("DATABASE_URL", ":memory:")
        self._database: sqlite3.Connection | None = None
        self._rate_limit = self._environment_positive_int("RATE_LIMIT", 100)
        self._message_ttl_days = self._environment_positive_int("MESSAGE_TTL_DAYS", 7)
        self._local_rate_limits: dict[str, tuple[int, int]] = {}
        self._cleanup_task: asyncio.Task[None] | None = None

    @property
    def client_count(self) -> int:
        with self._clients_lock:
            return len(self._clients)

    @property
    def port(self) -> int:
        return self._transport.port

    async def start(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        try:
            self._transport.port
        except RuntimeError:
            pass
        else:
            raise RuntimeError("server is already running")
        self._open_database()
        if self._broker is None:
            self._broker = await self._configured_broker()
        await self._broker.start(self._deliver_broker_message)
        await self._transport.start(host, port, self._handle_client, self)
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_messages())

    async def stop(self) -> None:
        await self._transport.stop()
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        if self._broker is not None:
            await self._broker.stop(self._deliver_broker_message)
        if self._database is not None:
            self._database.close()
            self._database = None
        with self._clients_lock:
            self._clients.clear()
            self._channels.clear()

    async def broadcast(self, payload: dict[str, Any]) -> None:
        await self._publish("broadcast", payload)

    async def direct(self, client_id: str, payload: dict[str, Any]) -> bool:
        assert self._broker is not None
        if not await self._broker.has_client(client_id):
            return False
        await self._publish("direct", payload)
        return True

    async def system(self, payload: dict[str, Any]) -> None:
        await self._publish("system", payload)

    async def _configured_broker(self) -> InMemoryBroker | RedisBroker:
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            return InMemoryBroker()
        import redis.asyncio as redis

        return RedisBroker(redis.from_url(redis_url))

    @staticmethod
    def _configured_transport() -> BaseTransport:
        transport_name = os.environ.get("TRANSPORT", "websocket").lower()
        if transport_name in {"websocket", "ws"}:
            return WebSocketTransport()
        raise ValueError(f"unsupported transport: {transport_name}")

    @staticmethod
    def _environment_positive_int(name: str, default: int) -> int:
        try:
            value = int(os.environ.get(name, str(default)))
        except ValueError:
            return default
        return value if value > 0 else default

    def _open_database(self) -> None:
        path = self._database_url
        if path.startswith("sqlite:///"):
            path = path[len("sqlite:///") :]
        self._database = sqlite3.connect(path)
        self._database.execute(
            "CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, channel TEXT, type TEXT NOT NULL, payload TEXT NOT NULL, timestamp TEXT NOT NULL)"
        )
        self._database.execute("CREATE INDEX IF NOT EXISTS messages_channel_timestamp ON messages(channel, timestamp)")
        self._database.commit()

    async def _handle_client(self, connection: Any) -> None:
        assert self._broker is not None
        client_id = str(uuid4())
        with self._clients_lock:
            self._clients[client_id] = connection
        await self._broker.add_client(client_id)
        try:
            await self._send_to_connections([connection], "system", {"event": "connected", "client_id": client_id})
            async for raw_message in connection:
                await self._handle_message(connection, client_id, raw_message)
        finally:
            with self._clients_lock:
                self._clients.pop(client_id, None)
                for channel in list(self._channels):
                    self._channels[channel].discard(client_id)
                    if not self._channels[channel]:
                        del self._channels[channel]
            await self._broker.remove_client(client_id)

    async def _handle_message(self, connection: Any, sender_id: str, raw_message: str | bytes) -> None:
        if not await self._within_rate_limit(sender_id):
            await self._send_to_connections([connection], "system", {"event": "error", "message": "rate limit exceeded"})
            return
        if isinstance(raw_message, bytes):
            await self._send_to_connections([connection], "system", {"event": "error", "message": "messages must be JSON text"})
            return
        try:
            message = json.loads(raw_message)
            message_type = message["type"]
            payload = message["payload"]
            if message_type not in MESSAGE_TYPES or not isinstance(payload, dict):
                raise ValueError
            channel = self._message_channel(message, payload)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            await self._send_to_connections([connection], "system", {"event": "error", "message": "invalid message format"})
            return
        if channel is not None and "channel" not in payload:
            payload = {**payload, "channel": channel}
        if message_type == "subscribe":
            if channel is None:
                await self._send_to_connections([connection], "system", {"event": "error", "message": "channel is required"})
                return
            await self._subscribe(sender_id, channel)
            await self._send_to_connections([connection], "system", {"event": "subscribed", "channel": channel})
        elif message_type == "unsubscribe":
            if channel is None:
                await self._send_to_connections([connection], "system", {"event": "error", "message": "channel is required"})
                return
            await self._unsubscribe(sender_id, channel)
            await self._send_to_connections([connection], "system", {"event": "unsubscribed", "channel": channel})
        elif message_type == "broadcast":
            await self.broadcast({"sender_id": sender_id, **payload})
        elif message_type == "direct":
            recipient_id = payload.get("client_id")
            if not isinstance(recipient_id, str) or not await self.direct(recipient_id, {"sender_id": sender_id, **payload}):
                await self._send_to_connections([connection], "system", {"event": "error", "message": "unknown client_id"})
        else:
            await self.system({"sender_id": sender_id, **payload})

    async def _publish(self, message_type: str, payload: dict[str, Any]) -> None:
        assert self._broker is not None
        message = self._message(message_type, payload)
        self._record(message)
        await self._broker.publish(message)

    async def _deliver_broker_message(self, message: dict[str, Any]) -> None:
        payload = message["payload"]
        if message["type"] == "direct":
            with self._clients_lock:
                connections = [self._clients[payload["client_id"]]] if payload["client_id"] in self._clients else []
        else:
            connections = self._channel_connections(payload)
        await self._send_encoded(connections, message)

    def _messages(self, limit: int, offset: int) -> list[dict[str, Any]]:
        assert self._database is not None
        rows = self._database.execute(
            "SELECT id, channel, type, payload, timestamp FROM messages ORDER BY rowid LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
        return [{"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]} for row in rows]

    def _history(self, channel: str, since: datetime, limit: int, offset: int) -> tuple[list[dict[str, Any]], bool]:
        assert self._database is not None
        rows = self._database.execute(
            "SELECT id, channel, type, payload, timestamp FROM messages "
            "WHERE channel = ? AND timestamp >= ? ORDER BY timestamp, rowid LIMIT ? OFFSET ?",
            (channel, since.astimezone(timezone.utc).isoformat(), limit + 1, offset),
        ).fetchall()
        has_more = len(rows) > limit
        messages = [
            {"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]}
            for row in rows[:limit]
        ]
        return messages, has_more

    def _record(self, message: dict[str, Any]) -> None:
        assert self._database is not None
        self._database.execute(
            "INSERT INTO messages (id, channel, type, payload, timestamp) VALUES (?, ?, ?, ?, ?)",
            (message["id"], message["channel"], message["type"], json.dumps(message["payload"]), message["timestamp"]),
        )
        self._database.commit()

    async def _within_rate_limit(self, client_id: str) -> bool:
        assert self._broker is not None
        if isinstance(self._broker, RedisBroker):
            key = f"notifications:rate-limit:{client_id}"
            count = await self._broker.redis.incr(key)
            if count == 1:
                await self._broker.redis.expire(key, RATE_LIMIT_WINDOW_SECONDS)
            return count <= self._rate_limit

        now = int(datetime.now(timezone.utc).timestamp() // RATE_LIMIT_WINDOW_SECONDS)
        window, count = self._local_rate_limits.get(client_id, (now, 0))
        if window != now:
            count = 0
        count += 1
        self._local_rate_limits[client_id] = (now, count)
        return count <= self._rate_limit

    async def _cleanup_expired_messages(self) -> None:
        while True:
            assert self._database is not None
            cutoff = (datetime.now(timezone.utc) - timedelta(days=self._message_ttl_days)).isoformat()
            self._database.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff,))
            self._database.commit()
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)

    def _message(self, message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"id": str(uuid4()), "channel": payload.get("channel"), "type": message_type, "payload": payload, "timestamp": datetime.now(timezone.utc).isoformat()}

    def _connections(self) -> list[Any]:
        with self._clients_lock:
            return list(self._clients.values())

    def _channel_connections(self, payload: dict[str, Any]) -> list[Any]:
        channel = payload.get("channel")
        if channel is None:
            return self._connections()
        with self._clients_lock:
            return [self._clients[client_id] for client_id in self._channels.get(channel, set()) if client_id in self._clients]

    @staticmethod
    def _message_channel(message: dict[str, Any], payload: dict[str, Any]) -> str | None:
        top_level_channel = message.get("channel")
        payload_channel = payload.get("channel")
        if top_level_channel is not None and payload_channel is not None and top_level_channel != payload_channel:
            raise ValueError
        channel = top_level_channel if top_level_channel is not None else payload_channel
        if channel is not None and (not isinstance(channel, str) or not channel):
            raise ValueError
        return channel

    async def _subscribe(self, client_id: str, channel: str) -> None:
        assert self._broker is not None
        with self._clients_lock:
            self._channels[channel].add(client_id)
        await self._broker.subscribe(client_id, channel)

    async def _unsubscribe(self, client_id: str, channel: str) -> None:
        assert self._broker is not None
        with self._clients_lock:
            self._channels[channel].discard(client_id)
            if not self._channels[channel]:
                del self._channels[channel]
        await self._broker.unsubscribe(client_id, channel)

    async def _send_to_connections(self, connections: list[Any], message_type: str, payload: dict[str, Any]) -> None:
        await self._send_encoded(connections, self._message(message_type, payload))

    async def _send_encoded(self, connections: list[Any], message: dict[str, Any]) -> None:
        encoded = json.dumps({"type": message["type"], "payload": message["payload"], "timestamp": message["timestamp"]})
        await self._transport.broadcast(connections, encoded)


async def main() -> None:
    server = NotificationServer()
    await server.start(host="0.0.0.0", port=8765)
    print("Notification server listening on ws://0.0.0.0:8765")
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
