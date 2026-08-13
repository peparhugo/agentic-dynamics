"""Async WebSocket notification server backed by Redis and SQLite."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import datetime, timezone
import json
import os
import sqlite3
import threading
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4

from redis import asyncio as redis
from websockets.asyncio.server import Server
from websockets.datastructures import Headers
from websockets.http11 import Request, Response

from transports import BaseTransport, WebSocketTransport


SUPPORTED_MESSAGE_TYPES = frozenset(
    {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
)
BACKBONE_CHANNEL = "notifications"


class ClientRegistry:
    """A thread-safe mapping of assigned client IDs to local connections."""

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def add(self, connection: Any) -> str:
        client_id = str(uuid4())
        with self._lock:
            self._clients[client_id] = connection
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in list(self._channels):
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def get(self, client_id: str) -> Any | None:
        with self._lock:
            return self._clients.get(client_id)

    def connections(self) -> list[Any]:
        with self._lock:
            return list(self._clients.values())

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            if client_id in self._clients:
                self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers:
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[channel]

    def channel_connections(self, channel: str) -> list[Any]:
        with self._lock:
            return [
                self._clients[client_id]
                for client_id in self._channels.get(channel, set())
                if client_id in self._clients
            ]

    def channels(self) -> dict[str, int]:
        with self._lock:
            return {channel: len(clients) for channel, clients in self._channels.items() if clients}

    def subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)


class MessageStore:
    """SQLite history store shared safely by the server's async tasks."""

    def __init__(self, database_url: str | None = None) -> None:
        url = database_url or os.getenv("DATABASE_URL", "sqlite:///:memory:")
        if not url.startswith("sqlite:///"):
            raise ValueError("DATABASE_URL must be a sqlite:/// URL")
        path = url.removeprefix("sqlite:///") or ":memory:"
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.RLock()
        with self._lock:
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

    def add(self, message: dict[str, Any]) -> int:
        with self._lock:
            cursor = self._connection.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (message.get("channel"), message["type"], json.dumps(message["payload"]), message["timestamp"]),
            )
            self._connection.commit()
            return int(cursor.lastrowid)

    def list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [
            {"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]}
            for row in rows
        ]

    def history(self, channel: str, since: str | None, limit: int) -> tuple[list[dict[str, Any]], bool]:
        query = "SELECT id, channel, type, payload, timestamp FROM messages WHERE channel = ?"
        parameters: list[Any] = [channel]
        if since is not None:
            query += " AND timestamp >= ?"
            parameters.append(since)
        query += " ORDER BY timestamp ASC, id ASC LIMIT ?"
        parameters.append(limit + 1)
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        has_more = len(rows) > limit
        return (
            [
                {"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]}
                for row in rows[:limit]
            ],
            has_more,
        )

    def delete_older_than(self, timestamp: str) -> int:
        with self._lock:
            cursor = self._connection.execute("DELETE FROM messages WHERE timestamp < ?", (timestamp,))
            self._connection.commit()
            return cursor.rowcount

    def close(self) -> None:
        with self._lock:
            self._connection.close()


class InMemoryBroker:
    """Process-local fallback used when REDIS_URL is not configured."""

    subscribers: set[asyncio.Queue[str]] = set()

    async def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        self.subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        self.subscribers.discard(queue)

    async def publish(self, message: str) -> None:
        for queue in list(self.subscribers):
            await queue.put(message)


class RedisBroker:
    """Redis pub/sub adapter. Every server instance consumes the same backbone."""

    def __init__(self, url: str) -> None:
        self.client = redis.from_url(url, decode_responses=True)

    async def subscribe(self) -> Any:
        pubsub = self.client.pubsub()
        await pubsub.subscribe(BACKBONE_CHANNEL)
        return pubsub

    async def unsubscribe(self, subscription: Any) -> None:
        await subscription.unsubscribe(BACKBONE_CHANNEL)
        await subscription.aclose()
        await self.client.aclose()

    async def publish(self, message: str) -> None:
        await self.client.publish(BACKBONE_CHANNEL, message)


class RedisClientState:
    """Keeps client and channel membership visible across server instances."""

    PREFIX = "notification:"

    def __init__(self, url: str | None) -> None:
        self.client = redis.from_url(url, decode_responses=True) if url else None

    async def add(self, client_id: str) -> None:
        if self.client:
            await self.client.sadd(f"{self.PREFIX}clients", client_id)

    async def remove(self, client_id: str) -> None:
        if not self.client:
            return
        client_channels = f"{self.PREFIX}client:{client_id}:channels"
        channels = await self.client.smembers(client_channels)
        pipe = self.client.pipeline()
        pipe.srem(f"{self.PREFIX}clients", client_id)
        pipe.delete(client_channels)
        for channel in channels:
            pipe.srem(f"{self.PREFIX}channel:{channel}:clients", client_id)
        await pipe.execute()

    async def subscribe(self, client_id: str, channel: str) -> None:
        if self.client:
            await self.client.sadd(f"{self.PREFIX}client:{client_id}:channels", channel)
            await self.client.sadd(f"{self.PREFIX}channel:{channel}:clients", client_id)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        if self.client:
            await self.client.srem(f"{self.PREFIX}client:{client_id}:channels", channel)
            await self.client.srem(f"{self.PREFIX}channel:{channel}:clients", client_id)

    async def channels(self, local: ClientRegistry) -> dict[str, int]:
        if not self.client:
            return local.channels()
        result = {}
        async for key in self.client.scan_iter(match=f"{self.PREFIX}channel:*:clients"):
            channel = key[len(f"{self.PREFIX}channel:") : -len(":clients")]
            count = await self.client.scard(key)
            if count:
                result[channel] = count
        return result

    async def subscribers(self, channel: str, local: ClientRegistry) -> list[str]:
        if not self.client:
            return local.subscribers(channel)
        return sorted(await self.client.smembers(f"{self.PREFIX}channel:{channel}:clients"))


class RateLimiter:
    """Per-client fixed-window limiter using Redis counters when available."""

    PREFIX = "notification:rate:"

    def __init__(self, url: str | None, limit: int) -> None:
        self.client = redis.from_url(url, decode_responses=True) if url else None
        self.limit = limit
        self._counters: dict[str, tuple[int, float]] = {}

    async def allow(self, client_id: str) -> bool:
        if self.client:
            key = f"{self.PREFIX}{client_id}"
            count = await self.client.incr(key)
            if count == 1:
                await self.client.expire(key, 60)
            return count <= self.limit
        now = asyncio.get_running_loop().time()
        count, expires_at = self._counters.get(client_id, (0, now + 60))
        if now >= expires_at:
            count, expires_at = 0, now + 60
        self._counters[client_id] = (count + 1, expires_at)
        return count < self.limit

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()


class NotificationServer:
    """Routes JSON notifications using a shared pub/sub backbone."""

    def __init__(
        self,
        redis_url: str | None = None,
        database_url: str | None = None,
        transport: BaseTransport | None = None,
        rate_limit: int | None = None,
        message_ttl_days: int | None = None,
    ) -> None:
        redis_url = redis_url if redis_url is not None else os.getenv("REDIS_URL")
        self.rate_limit = rate_limit if rate_limit is not None else int(os.getenv("RATE_LIMIT", "100"))
        self.message_ttl_days = message_ttl_days if message_ttl_days is not None else int(os.getenv("MESSAGE_TTL_DAYS", "7"))
        if self.rate_limit < 1:
            raise ValueError("RATE_LIMIT must be positive")
        if self.message_ttl_days < 0:
            raise ValueError("MESSAGE_TTL_DAYS must be non-negative")
        self.clients = ClientRegistry()
        self.store = MessageStore(database_url)
        self.state = RedisClientState(redis_url)
        self.rate_limiter = RateLimiter(redis_url, self.rate_limit)
        self.broker: RedisBroker | InMemoryBroker = RedisBroker(redis_url) if redis_url else InMemoryBroker()
        self.transport = transport or self._configured_transport()
        self._subscription: Any = None
        self._listener: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None

    @staticmethod
    def _configured_transport() -> BaseTransport:
        transport_name = os.getenv("TRANSPORT", "websocket").lower()
        if transport_name in {"websocket", "ws"}:
            return WebSocketTransport()
        raise ValueError(f"Unsupported transport: {transport_name}")

    @staticmethod
    def message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"type": message_type, "payload": payload, "timestamp": datetime.now(timezone.utc).isoformat()}

    async def handler(self, connection: Any) -> None:
        await self.transport.on_connect(self, connection)

    async def _register_connection(self, connection: Any) -> str:
        client_id = self.clients.add(connection)
        await self.state.add(client_id)
        return client_id

    async def _unregister_connection(self, client_id: str) -> None:
        self.clients.remove(client_id)
        await self.state.remove(client_id)

    def welcome_message(self, client_id: str) -> str:
        return json.dumps(self.message("system", {"client_id": client_id}))

    async def handle_message(self, sender_id: str, raw_message: str | bytes) -> None:
        if not await self.rate_limiter.allow(sender_id):
            await self._send_error(sender_id, "rate limit exceeded")
            return
        if isinstance(raw_message, bytes):
            await self._send_error(sender_id, "messages must be JSON text")
            return
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            await self._send_error(sender_id, "invalid JSON")
            return
        if not isinstance(message, dict):
            await self._send_error(sender_id, "message must be an object")
            return
        message_type, payload, channel = message.get("type"), message.get("payload"), message.get("channel")
        if message_type not in SUPPORTED_MESSAGE_TYPES:
            await self._send_error(sender_id, "unsupported message type")
            return
        if channel is not None and (not isinstance(channel, str) or not channel):
            await self._send_error(sender_id, "channel must be a non-empty string")
            return
        if message_type in {"subscribe", "unsubscribe"}:
            if channel is None:
                await self._send_error(sender_id, f"{message_type} messages require channel")
            elif message_type == "subscribe":
                self.clients.subscribe(sender_id, channel)
                await self.state.subscribe(sender_id, channel)
            else:
                self.clients.unsubscribe(sender_id, channel)
                await self.state.unsubscribe(sender_id, channel)
            return
        if not isinstance(payload, dict):
            await self._send_error(sender_id, "payload must be an object")
            return
        if message_type == "direct" and not isinstance(payload.get("client_id"), str):
            await self._send_error(sender_id, "direct messages require payload.client_id")
            return
        notification = self.message(message_type, payload)
        if channel is not None:
            notification["channel"] = channel
        notification["id"] = self.store.add(notification)
        await self.broker.publish(json.dumps(notification))

    async def _listen(self) -> None:
        assert self._subscription is not None
        if isinstance(self.broker, RedisBroker):
            while True:
                event = await self._subscription.get_message(ignore_subscribe_messages=True, timeout=1)
                if event is not None:
                    await self._deliver(json.loads(event["data"]))
        else:
            while True:
                await self._deliver(json.loads(await self._subscription.get()))

    async def _deliver(self, message: dict[str, Any]) -> None:
        notification = json.dumps(message)
        if message["type"] == "direct":
            target = self.clients.get(message["payload"]["client_id"])
            if target is not None:
                await self.transport.send_message(target, notification)
        elif message.get("channel") is None:
            await self.send_raw(self.clients.connections(), notification)
        else:
            await self.send_raw(self.clients.channel_connections(message["channel"]), notification)

    async def send_raw(self, connections: list[Any], notification: str) -> None:
        await self.transport.broadcast(connections, notification)

    async def _send_error(self, client_id: str, error: str) -> None:
        connection = self.clients.get(client_id)
        if connection is not None:
            await self.transport.send_message(connection, json.dumps(self.message("system", {"error": error})))

    async def process_request(self, connection: Any, request: Request) -> Response | None:
        if request.headers.get("Upgrade") is not None:
            return None
        if request.path == "/health":
            return self._json_response({"connected_clients": len(self.clients)})
        if request.path == "/channels":
            channels = [{"name": name, "subscriber_count": count} for name, count in sorted((await self.state.channels(self.clients)).items())]
            return self._json_response({"channels": channels})
        if request.path.startswith("/channels/") and request.path.endswith("/subscribers"):
            encoded_name = request.path[len("/channels/") : -len("/subscribers")].rstrip("/")
            if not encoded_name:
                return Response(404, "Not Found", Headers(), b"Not Found")
            channel = unquote(encoded_name)
            return self._json_response({"channel": channel, "subscribers": await self.state.subscribers(channel, self.clients)})
        parsed = urlsplit(request.path)
        if parsed.path == "/history":
            try:
                params = parse_qs(parsed.query)
                channel = params["channel"][0]
                if not channel:
                    raise ValueError
                since = params.get("since", [None])[0]
                if since is not None:
                    parsed_since = datetime.fromisoformat(since.replace("Z", "+00:00"))
                    if parsed_since.tzinfo is None:
                        raise ValueError
                limit = int(params.get("limit", ["50"])[0])
                if not 1 <= limit <= 1000:
                    raise ValueError
            except (KeyError, ValueError):
                return self._json_response({"error": "channel, ISO_TIMESTAMP since, and limit (1-1000) are required"}, 400)
            messages, has_more = self.store.history(channel, since, limit)
            return self._json_response({"messages": messages, "has_more": has_more})
        if parsed.path == "/messages":
            try:
                params = parse_qs(parsed.query)
                limit = int(params.get("limit", ["50"])[0])
                offset = int(params.get("offset", ["0"])[0])
                if not 1 <= limit <= 1000 or offset < 0:
                    raise ValueError
            except ValueError:
                return self._json_response({"error": "limit must be 1-1000 and offset must be non-negative"}, 400)
            return self._json_response({"messages": self.store.list(limit, offset)})
        return Response(404, "Not Found", Headers(), b"Not Found")

    @staticmethod
    def _json_response(body: dict[str, Any], status: int = 200) -> Response:
        return Response(status, "OK", Headers({"Content-Type": "application/json"}), json.dumps(body).encode())

    async def start(self, host: str = "127.0.0.1", port: int = 8765) -> Server:
        self._subscription = await self.broker.subscribe()
        self._listener = asyncio.create_task(self._listen())
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_messages())
        return await self.transport.start(self, host, port)

    async def _cleanup_expired_messages(self) -> None:
        while True:
            cutoff = datetime.now(timezone.utc).timestamp() - self.message_ttl_days * 86400
            self.store.delete_older_than(datetime.fromtimestamp(cutoff, timezone.utc).isoformat())
            await asyncio.sleep(86400)

    async def stop(self) -> None:
        if self._listener:
            self._listener.cancel()
            with suppress(asyncio.CancelledError):
                await self._listener
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._cleanup_task
        if self._subscription is not None:
            await self.broker.unsubscribe(self._subscription)
        await self.rate_limiter.close()
        self.store.close()


async def main() -> None:
    notification_server = NotificationServer()
    server = await notification_server.start()
    try:
        async with server:
            await asyncio.Future()
    finally:
        await notification_server.stop()


if __name__ == "__main__":
    asyncio.run(main())
