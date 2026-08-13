"""Redis-backed WebSocket notification server with SQLite message history."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from redis import asyncio as redis_async
from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Response


SUPPORTED_MESSAGE_TYPES = frozenset(
    {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
)
REDIS_CHANNEL = "notifications:messages"
RATE_LIMIT_WINDOW_SECONDS = 60


class MessageStore:
    """Small SQLite repository for delivered application messages."""

    def __init__(self, database_url: str | None = None) -> None:
        url = database_url or os.getenv("DATABASE_URL", "sqlite:///:memory:")
        self.path = url.removeprefix("sqlite:///") if url.startswith("sqlite:///") else url
        self.connection = sqlite3.connect(self.path)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, type TEXT NOT NULL, "
            "payload TEXT NOT NULL, timestamp TEXT NOT NULL)"
        )
        self.connection.commit()

    def save(self, message: dict[str, Any]) -> None:
        self.connection.execute(
            "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
            (message.get("channel"), message["type"], json.dumps(message["payload"]), message["timestamp"]),
        )
        self.connection.commit()

    def list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT id, channel, type, payload, timestamp FROM messages "
            "ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [
            {"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]}
            for row in rows
        ]

    def history(self, channel: str, since: datetime, limit: int, offset: int) -> tuple[list[dict[str, Any]], bool]:
        rows = self.connection.execute(
            "SELECT id, channel, type, payload, timestamp FROM messages "
            "WHERE channel = ? AND datetime(timestamp) >= datetime(?) "
            "ORDER BY datetime(timestamp) ASC, id ASC LIMIT ? OFFSET ?",
            (channel, since.isoformat(), limit + 1, offset),
        ).fetchall()
        has_more = len(rows) > limit
        return (
            [
                {"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]}
                for row in rows[:limit]
            ],
            has_more,
        )

    def delete_older_than(self, cutoff: datetime) -> None:
        self.connection.execute("DELETE FROM messages WHERE datetime(timestamp) < datetime(?)", (cutoff.isoformat(),))
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()


class BaseTransport(ABC):
    """Connection mechanism used by a notification server."""

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
    async def broadcast(self, message: dict[str, Any]) -> int:
        """Send a message to every client, returning the delivery count."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport contract."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}

    async def on_connect(self, client_id: str, connection: Any) -> None:
        self._clients[client_id] = connection

    async def on_disconnect(self, client_id: str) -> None:
        self._clients.pop(client_id, None)

    async def send_message(self, client_id: str, message: dict[str, Any]) -> bool:
        websocket = self._clients.get(client_id)
        if websocket is None:
            return False
        try:
            await websocket.send(json.dumps(message))
        except Exception:
            return False
        return True

    async def broadcast(self, message: dict[str, Any]) -> int:
        sent = 0
        for client_id in list(self._clients):
            if await self.send_message(client_id, message):
                sent += 1
        return sent

    async def handle_connection(self, server: "NotificationServer", websocket: ServerConnection) -> None:
        """Adapt a WebSocket connection to the transport-neutral server API."""
        client_id = await server.register(websocket)
        await server.send_direct(client_id, server._message("system", {"client_id": client_id}))
        try:
            async for raw_message in websocket:
                await server.handle_message(client_id, raw_message)
        finally:
            await server.unregister(client_id)


TRANSPORTS: dict[str, type[BaseTransport]] = {"websocket": WebSocketTransport, "ws": WebSocketTransport}


def register_transport(name: str, transport_class: type[BaseTransport]) -> None:
    """Register a transport class for selection through ``TRANSPORT``."""
    TRANSPORTS[name.lower()] = transport_class


class NotificationServer:
    """Routes clients while Redis distributes messages between instances."""

    def __init__(
        self,
        redis_url: str | None = None,
        database_url: str | None = None,
        transport: BaseTransport | None = None,
    ) -> None:
        self._clients: set[str] = set()
        self._channels: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()
        self._store = MessageStore(database_url)
        self._transport = transport or self._transport_from_config()
        self._instance_id = str(uuid.uuid4())
        self._redis_url = redis_url if redis_url is not None else os.getenv("REDIS_URL")
        self._redis: Any = None
        self._pubsub: Any = None
        self._subscriber_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def start(self) -> None:
        """Connect to Redis and begin receiving messages published by peer servers."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_messages())
        if self._redis is not None or not self._redis_url:
            return
        try:
            redis = redis_async.from_url(self._redis_url, decode_responses=True)
            await redis.ping()
            pubsub = redis.pubsub()
            await pubsub.subscribe(REDIS_CHANNEL)
        except Exception:
            # A standalone server remains functional when Redis is not configured/reachable.
            if 'redis' in locals():
                await redis.aclose()
            return
        self._redis = redis
        self._pubsub = pubsub
        self._subscriber_task = asyncio.create_task(self._listen_for_messages())

    async def close(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
        if self._pubsub:
            await self._pubsub.unsubscribe(REDIS_CHANNEL)
            close = getattr(self._pubsub, "aclose", self._pubsub.close)
            result = close()
            if hasattr(result, "__await__"):
                await result
        if self._redis:
            close = getattr(self._redis, "aclose", self._redis.close)
            result = close()
            if hasattr(result, "__await__"):
                await result
        self._store.close()

    async def register(self, connection: Any) -> str:
        await self.start()
        client_id = str(uuid.uuid4())
        await self._transport.on_connect(client_id, connection)
        async with self._lock:
            self._clients.add(client_id)
        if self._redis:
            await self._redis.hset(f"notifications:client:{client_id}", mapping={"instance": self._instance_id})
        return client_id

    async def unregister(self, client_id: str) -> None:
        await self._transport.on_disconnect(client_id)
        async with self._lock:
            self._clients.discard(client_id)
            channels = self._remove_client_from_channels(client_id)
        if self._redis:
            pipe = self._redis.pipeline()
            pipe.delete(f"notifications:client:{client_id}")
            for channel in channels:
                pipe.srem(f"notifications:channel:{channel}:clients", client_id)
            await pipe.execute()

    async def subscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)
        if self._redis:
            await self._redis.sadd(f"notifications:channel:{channel}:clients", client_id)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is not None:
                subscribers.discard(client_id)
                if not subscribers:
                    self._channels.pop(channel, None)
        if self._redis:
            await self._redis.srem(f"notifications:channel:{channel}:clients", client_id)

    async def broadcast(self, message: dict[str, Any]) -> None:
        await self._transport.broadcast(message)

    async def send_channel(self, channel: str, message: dict[str, Any]) -> None:
        async with self._lock:
            clients = [client_id for client_id in self._channels.get(channel, set()) if client_id in self._clients]
        await self._send_clients(clients, message)

    async def send_direct(self, client_id: str, message: dict[str, Any]) -> bool:
        return await self._send_clients([client_id], message) == 1

    async def websocket_handler(self, websocket: ServerConnection) -> None:
        if not isinstance(self._transport, WebSocketTransport):
            raise RuntimeError("websocket_handler requires the websocket transport")
        await self._transport.handle_connection(self, websocket)

    async def handle_message(self, client_id: str, raw_message: str | bytes) -> None:
        """Process an incoming message supplied by any transport."""
        try:
            if not await self._within_rate_limit(client_id):
                await self.send_direct(client_id, self._message("system", {"error": "rate limit exceeded"}))
                return
            message = self._parse_message(raw_message)
            if message["type"] == "subscribe":
                await self.subscribe(client_id, message["channel"])
            elif message["type"] == "unsubscribe":
                await self.unsubscribe(client_id, message["channel"])
            elif message["type"] == "direct":
                target_id = message["payload"].get("client_id")
                if not isinstance(target_id, str) or not await self._client_exists(target_id):
                    await self.send_direct(client_id, self._message("system", {"error": "client not found"}))
                else:
                    await self._publish_and_deliver(message)
            else:
                await self._publish_and_deliver(message)
        except ValueError as error:
            await self.send_direct(client_id, self._message("system", {"error": str(error)}))

    async def _publish_and_deliver(self, message: dict[str, Any]) -> bool:
        self._store.save(message)
        delivered = await self._deliver(message)
        if self._redis:
            envelope = json.dumps({"origin": self._instance_id, "message": message})
            await self._redis.publish(REDIS_CHANNEL, envelope)
        return delivered

    async def _listen_for_messages(self) -> None:
        while True:
            event = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
            if event and event["type"] == "message":
                envelope = json.loads(event["data"])
                if envelope["origin"] != self._instance_id:
                    await self._deliver(envelope["message"])

    async def _deliver(self, message: dict[str, Any]) -> bool:
        if message["type"] == "direct":
            return await self.send_direct(message["payload"].get("client_id", ""), message)
        if "channel" in message:
            await self.send_channel(message["channel"], message)
            return True
        await self.broadcast(message)
        return True

    async def _client_exists(self, client_id: str) -> bool:
        async with self._lock:
            if client_id in self._clients:
                return True
        return bool(self._redis and await self._redis.exists(f"notifications:client:{client_id}"))

    async def _send_clients(self, clients: list[str], message: dict[str, Any]) -> int:
        sent = 0
        for client_id in clients:
            if await self._transport.send_message(client_id, message):
                sent += 1
            else:
                await self.unregister(client_id)
        return sent

    async def _within_rate_limit(self, client_id: str) -> bool:
        """Increment the Redis counter for this client and enforce its one-minute quota."""
        if not self._redis:
            return True
        count = await self._redis.incr(f"notifications:rate:{client_id}")
        if count == 1:
            await self._redis.expire(f"notifications:rate:{client_id}", RATE_LIMIT_WINDOW_SECONDS)
        return count <= self._rate_limit()

    async def _cleanup_expired_messages(self) -> None:
        await asyncio.sleep(0)
        self._store.delete_older_than(datetime.now(timezone.utc) - self._message_ttl())

    @staticmethod
    def _rate_limit() -> int:
        return NotificationServer._positive_integer_env("RATE_LIMIT", 100)

    @staticmethod
    def _message_ttl() -> timedelta:
        return timedelta(days=NotificationServer._positive_integer_env("MESSAGE_TTL_DAYS", 7))

    @staticmethod
    def _positive_integer_env(name: str, default: int) -> int:
        try:
            value = int(os.getenv(name, str(default)))
        except ValueError as error:
            raise ValueError(f"{name} must be a positive integer") from error
        if value < 1:
            raise ValueError(f"{name} must be a positive integer")
        return value

    @staticmethod
    def _transport_from_config() -> BaseTransport:
        transport_name = os.getenv("TRANSPORT", "websocket").lower()
        try:
            return TRANSPORTS[transport_name]()
        except KeyError as error:
            raise ValueError(f"unsupported transport: {transport_name}") from error

    def health_response(self, connection: ServerConnection, request: Any) -> Response | None:
        parsed = urlsplit(request.path)
        path = parsed.path
        if path == "/health":
            return self._json_response({"connected_clients": self.client_count})
        if path == "/messages":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
                if not 1 <= limit <= 1000 or offset < 0:
                    raise ValueError
            except ValueError:
                return self._json_response({"error": "limit must be 1-1000 and offset must be non-negative"}, HTTPStatus.BAD_REQUEST)
            return self._json_response({"messages": self._store.list(limit, offset)})
        if path == "/history":
            query = parse_qs(parsed.query)
            channel = query.get("channel", [""])[0]
            since = query.get("since", [""])[0]
            try:
                if not channel:
                    raise ValueError("channel is required")
                since_timestamp = datetime.fromisoformat(since.replace("Z", "+00:00"))
                if since_timestamp.tzinfo is None:
                    raise ValueError("since must be an ISO timestamp with a timezone")
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
                if not 1 <= limit <= 1000 or offset < 0:
                    raise ValueError("limit must be 1-1000 and offset must be non-negative")
            except ValueError as error:
                return self._json_response({"error": str(error) or "since must be an ISO timestamp"}, HTTPStatus.BAD_REQUEST)
            messages, has_more = self._store.history(channel, since_timestamp, limit, offset)
            return self._json_response({"messages": messages, "has_more": has_more})
        if path == "/channels":
            return self._json_response({"channels": [{"name": name, "subscriber_count": len(subscribers)} for name, subscribers in sorted(self._channels.items())]})
        if path.startswith("/channels/") and path.endswith("/subscribers"):
            name = unquote(path[len("/channels/") : -len("/subscribers")]).rstrip("/")
            subscribers = self._channels.get(name)
            if subscribers is None:
                return self._json_response({"error": "channel not found"}, HTTPStatus.NOT_FOUND)
            return self._json_response({"subscribers": sorted(subscribers)})
        return None

    @staticmethod
    def _json_response(body: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> Response:
        return Response(status, status.phrase, headers=Headers({"Content-Type": "application/json"}), body=json.dumps(body).encode())

    def _remove_client_from_channels(self, client_id: str) -> list[str]:
        removed_from = []
        for channel, subscribers in list(self._channels.items()):
            if client_id in subscribers:
                removed_from.append(channel)
            subscribers.discard(client_id)
            if not subscribers:
                self._channels.pop(channel, None)
        return removed_from

    @staticmethod
    def _message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"type": message_type, "payload": payload, "timestamp": datetime.now(timezone.utc).isoformat()}

    @staticmethod
    def _parse_message(raw_message: str | bytes) -> dict[str, Any]:
        if not isinstance(raw_message, str):
            raise ValueError("messages must be JSON text")
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError as error:
            raise ValueError("messages must be valid JSON") from error
        if not isinstance(message, dict):
            raise ValueError("messages must be JSON objects")
        if message.get("type") not in SUPPORTED_MESSAGE_TYPES:
            raise ValueError("unsupported message type")
        if not isinstance(message.get("payload"), dict):
            raise ValueError("payload must be an object")
        if not isinstance(message.get("timestamp"), str):
            raise ValueError("timestamp must be a string")
        if "channel" in message and (not isinstance(message["channel"], str) or not message["channel"]):
            raise ValueError("channel must be a non-empty string")
        if message["type"] in {"subscribe", "unsubscribe"} and "channel" not in message:
            raise ValueError("channel is required")
        return message


async def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    notification_server = NotificationServer()
    await notification_server.start()
    try:
        async with serve(notification_server.websocket_handler, host, port, process_request=notification_server.health_response):
            await asyncio.Future()
    finally:
        await notification_server.close()


if __name__ == "__main__":
    asyncio.run(run_server())
