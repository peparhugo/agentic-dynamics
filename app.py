"""Async notification server backed by Redis and SQLite."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import threading
from collections.abc import Awaitable
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlsplit

import redis.asyncio as redis
from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response

from transports import BaseTransport, ClientRegistry, WebSocketTransport, create_transport


SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
REDIS_CHANNEL = "notifications:messages"
DEFAULT_RATE_LIMIT = 100
DEFAULT_MESSAGE_TTL_DAYS = 7
RATE_LIMIT_WINDOW_SECONDS = 60
MESSAGE_CLEANUP_INTERVAL_SECONDS = 60 * 60


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"type": message_type, "payload": payload, "timestamp": utc_timestamp()}


class MessageStore:
    """Thread-safe SQLite message history."""

    def __init__(self, database_url: str | None = None) -> None:
        database_url = database_url or os.getenv("DATABASE_URL", "notifications.db")
        if database_url.startswith("sqlite:///"):
            database_url = database_url[len("sqlite:///") :]
        elif database_url.startswith("sqlite://"):
            database_url = database_url[len("sqlite://") :]
        self._connection = sqlite3.connect(database_url, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
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
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS messages_channel_timestamp "
                "ON messages (channel, timestamp, id)"
            )

    def add(self, outgoing: dict[str, Any]) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (
                    outgoing.get("channel"),
                    outgoing["type"],
                    json.dumps(outgoing["payload"]),
                    outgoing["timestamp"],
                ),
            )

    def list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id ASC LIMIT ? OFFSET ?",
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

    def history(
        self, channel: str, since: datetime, limit: int
    ) -> tuple[list[dict[str, Any]], bool]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "WHERE channel = ? AND julianday(timestamp) >= julianday(?) "
                "ORDER BY julianday(timestamp) ASC, id ASC LIMIT ?",
                (channel, since.isoformat(), limit + 1),
            ).fetchall()
        has_more = len(rows) > limit
        return (
            [
                {
                    "id": row["id"],
                    "channel": row["channel"],
                    "type": row["type"],
                    "payload": json.loads(row["payload"]),
                    "timestamp": row["timestamp"],
                }
                for row in rows[:limit]
            ],
            has_more,
        )

    def delete_older_than(self, cutoff: datetime) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "DELETE FROM messages WHERE julianday(timestamp) < julianday(?)",
                (cutoff.isoformat(),),
            )
        return cursor.rowcount

    def close(self) -> None:
        with self._lock:
            self._connection.close()


DeliveryCallback = Callable[[dict[str, Any]], Awaitable[None]]


class InMemoryBackbone:
    """Dependency-free backbone used when REDIS_URL isn't configured."""

    def __init__(self) -> None:
        self._clients: set[str] = set()
        self._channels: dict[str, set[str]] = {}
        self._callback: DeliveryCallback | None = None
        self._rate_limits: dict[tuple[str, int], int] = {}

    async def start(self, callback: DeliveryCallback) -> None:
        self._callback = callback

    async def close(self) -> None:
        self._callback = None

    async def publish(self, outgoing: dict[str, Any]) -> None:
        if self._callback:
            await self._callback(outgoing)

    async def add_client(self, client_id: str) -> None:
        self._clients.add(client_id)

    async def remove_client(self, client_id: str) -> None:
        self._clients.discard(client_id)
        for channel in list(self._channels):
            self._channels[channel].discard(client_id)
            if not self._channels[channel]:
                del self._channels[channel]

    async def has_client(self, client_id: str) -> bool:
        return client_id in self._clients

    async def subscribe(self, client_id: str, channel: str) -> None:
        self._channels.setdefault(channel, set()).add(client_id)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        subscribers = self._channels.get(channel)
        if subscribers:
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    async def client_count(self) -> int:
        return len(self._clients)

    async def channels(self) -> dict[str, int]:
        return {name: len(ids) for name, ids in sorted(self._channels.items())}

    async def subscribers(self, channel: str) -> list[str]:
        return sorted(self._channels.get(channel, set()))

    async def rate_limit_exceeded(self, client_id: str, limit: int) -> bool:
        bucket = int(datetime.now(timezone.utc).timestamp()) // RATE_LIMIT_WINDOW_SECONDS
        key = (client_id, bucket)
        self._rate_limits = {
            item: count for item, count in self._rate_limits.items() if item[1] >= bucket
        }
        self._rate_limits[key] = self._rate_limits.get(key, 0) + 1
        return self._rate_limits[key] > limit


class RedisBackbone:
    """Redis pub/sub transport and shared connection-state repository."""

    def __init__(self, url: str, client: redis.Redis | None = None) -> None:
        self.redis = client or redis.from_url(url, decode_responses=True)
        self._owns_client = client is None
        self._pubsub: Any = None
        self._listener: asyncio.Task[None] | None = None

    async def start(self, callback: DeliveryCallback) -> None:
        if self._listener is not None:
            return
        self._pubsub = self.redis.pubsub()
        await self._pubsub.subscribe(REDIS_CHANNEL)
        self._listener = asyncio.create_task(self._listen(callback))

    async def _listen(self, callback: DeliveryCallback) -> None:
        try:
            async for event in self._pubsub.listen():
                if event["type"] == "message":
                    data = event["data"]
                    if isinstance(data, bytes):
                        data = data.decode()
                    await callback(json.loads(data))
        except asyncio.CancelledError:
            pass

    async def close(self) -> None:
        if self._listener:
            self._listener.cancel()
            await self._listener
            self._listener = None
        if self._pubsub:
            await self._pubsub.aclose()
            self._pubsub = None
        if self._owns_client:
            await self.redis.aclose()

    async def publish(self, outgoing: dict[str, Any]) -> None:
        await self.redis.publish(REDIS_CHANNEL, json.dumps(outgoing))

    async def add_client(self, client_id: str) -> None:
        await self.redis.sadd("notifications:clients", client_id)

    async def remove_client(self, client_id: str) -> None:
        membership_key = f"notifications:client:{client_id}:channels"
        channels = await self.redis.smembers(membership_key)
        pipe = self.redis.pipeline()
        pipe.srem("notifications:clients", client_id)
        for channel in channels:
            pipe.srem(f"notifications:channel:{channel}", client_id)
        pipe.delete(membership_key)
        await pipe.execute()

    async def has_client(self, client_id: str) -> bool:
        return bool(await self.redis.sismember("notifications:clients", client_id))

    async def subscribe(self, client_id: str, channel: str) -> None:
        pipe = self.redis.pipeline()
        pipe.sadd("notifications:channels", channel)
        pipe.sadd(f"notifications:channel:{channel}", client_id)
        pipe.sadd(f"notifications:client:{client_id}:channels", channel)
        await pipe.execute()

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        key = f"notifications:channel:{channel}"
        pipe = self.redis.pipeline()
        pipe.srem(key, client_id)
        pipe.srem(f"notifications:client:{client_id}:channels", channel)
        await pipe.execute()
        if not await self.redis.scard(key):
            pipe = self.redis.pipeline()
            pipe.srem("notifications:channels", channel)
            pipe.delete(key)
            await pipe.execute()

    async def client_count(self) -> int:
        return int(await self.redis.scard("notifications:clients"))

    async def channels(self) -> dict[str, int]:
        channels = await self.redis.smembers("notifications:channels")
        result = {}
        for channel in sorted(channels):
            count = int(await self.redis.scard(f"notifications:channel:{channel}"))
            if count:
                result[channel] = count
        return result

    async def subscribers(self, channel: str) -> list[str]:
        return sorted(await self.redis.smembers(f"notifications:channel:{channel}"))

    async def rate_limit_exceeded(self, client_id: str, limit: int) -> bool:
        bucket = int(datetime.now(timezone.utc).timestamp()) // RATE_LIMIT_WINDOW_SECONDS
        key = f"notifications:rate-limit:{client_id}:{bucket}"
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, RATE_LIMIT_WINDOW_SECONDS * 2)
        count, _ = await pipe.execute()
        return int(count) > limit


class NotificationServer:
    def __init__(
        self,
        backbone: InMemoryBackbone | RedisBackbone | None = None,
        store: MessageStore | None = None,
        transport: BaseTransport | None = None,
        rate_limit: int | None = None,
        message_ttl_days: int | None = None,
    ) -> None:
        redis_url = os.getenv("REDIS_URL")
        self.backbone = backbone or (
            RedisBackbone(redis_url) if redis_url else InMemoryBackbone()
        )
        self.store = store or MessageStore()
        self.transport = transport or create_transport(os.getenv("TRANSPORT", "websocket"))
        self.transport.bind(self)
        self.clients = self.transport.clients
        self.rate_limit = rate_limit or self._positive_int_env(
            "RATE_LIMIT", DEFAULT_RATE_LIMIT
        )
        self.message_ttl_days = message_ttl_days or self._positive_int_env(
            "MESSAGE_TTL_DAYS", DEFAULT_MESSAGE_TTL_DAYS
        )
        self._started = False
        self._start_lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task[None] | None = None

    @staticmethod
    def _positive_int_env(name: str, default: int) -> int:
        try:
            value = int(os.getenv(name, str(default)))
        except ValueError as error:
            raise ValueError(f"{name} must be a positive integer") from error
        if value <= 0:
            raise ValueError(f"{name} must be a positive integer")
        return value

    async def start(self) -> None:
        async with self._start_lock:
            if not self._started:
                await self.backbone.start(self._deliver)
                self._cleanup_task = asyncio.create_task(self._cleanup_messages())
                self._started = True

    async def close(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        if self._started:
            await self.backbone.close()
            self._started = False
        self.store.close()

    async def _cleanup_messages(self) -> None:
        while True:
            cutoff = datetime.now(timezone.utc) - timedelta(days=self.message_ttl_days)
            self.store.delete_older_than(cutoff)
            await asyncio.sleep(MESSAGE_CLEANUP_INTERVAL_SECONDS)

    async def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        del connection
        await self.start()
        parsed_url = urlsplit(request.path)
        path = parsed_url.path
        if path == "/health":
            return self._json_response(
                200, {"connected_clients": await self.backbone.client_count()}
            )
        if path == "/messages":
            query = parse_qs(parsed_url.query, keep_blank_values=True)
            try:
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
                if limit < 0 or offset < 0:
                    raise ValueError
            except ValueError:
                return self._json_response(400, {"error": "invalid pagination"})
            return self._json_response(200, {"messages": self.store.list(limit, offset)})
        if path == "/history":
            query = parse_qs(parsed_url.query, keep_blank_values=True)
            channel = query.get("channel", [""])[0]
            since_value = query.get("since", [""])[0]
            try:
                limit = int(query.get("limit", ["50"])[0])
                if not channel or limit <= 0:
                    raise ValueError
                since = datetime.fromisoformat(since_value.replace("Z", "+00:00"))
                if since.tzinfo is None:
                    since = since.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                return self._json_response(400, {"error": "invalid history query"})
            messages, has_more = self.store.history(channel, since, limit)
            return self._json_response(
                200, {"messages": messages, "has_more": has_more}
            )
        if path == "/channels":
            return self._json_response(200, {"channels": await self.backbone.channels()})
        prefix, suffix = "/channels/", "/subscribers"
        if path.startswith(prefix) and path.endswith(suffix):
            encoded_name = path[len(prefix) : -len(suffix)]
            if not encoded_name or "/" in encoded_name:
                return self._json_response(404, {"error": "not found"})
            channel = unquote(encoded_name)
            return self._json_response(
                200,
                {"channel": channel, "subscribers": await self.backbone.subscribers(channel)},
            )
        return None

    @staticmethod
    def _json_response(status: int, content: dict[str, Any]) -> Response:
        body = json.dumps(content).encode()
        return Response(
            status,
            {200: "OK", 400: "Bad Request", 404: "Not Found"}[status],
            Headers(
                {
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body)),
                    "Connection": "close",
                }
            ),
            body,
        )

    async def handler(self, websocket: ServerConnection) -> None:
        handler = getattr(self.transport, "handler", None)
        if handler is None:
            raise RuntimeError("configured transport does not provide a WebSocket handler")
        await handler(websocket)

    async def client_connected(self, client_id: str) -> None:
        await self.backbone.add_client(client_id)

    async def client_disconnected(self, client_id: str) -> None:
        await self.backbone.remove_client(client_id)

    @staticmethod
    def connected_message(client_id: str) -> dict[str, Any]:
        return message("system", {"event": "connected", "client_id": client_id})

    async def handle_message(
        self, raw_message: str | bytes, sender: Any, sender_id: str
    ) -> None:
        if await self.backbone.rate_limit_exceeded(sender_id, self.rate_limit):
            await self.transport.send_message(
                sender, message("system", {"error": "rate limit exceeded"})
            )
            return
        parsed, error = self._parse_message(raw_message)
        if error:
            await self.transport.send_message(sender, message("system", {"error": error}))
            return
        self.store.add(parsed)
        await self._route(parsed, sender, sender_id)

    @staticmethod
    def _parse_message(raw_message: str | bytes) -> tuple[dict[str, Any], str | None]:
        if isinstance(raw_message, bytes):
            return {}, "messages must be JSON text"
        try:
            parsed = json.loads(raw_message)
        except (json.JSONDecodeError, TypeError):
            return {}, "invalid JSON"
        if not isinstance(parsed, dict):
            return {}, "message must be a JSON object"
        required = {"type", "payload", "timestamp"}
        if not required.issubset(parsed) or not set(parsed).issubset(required | {"channel"}):
            return {}, "message must contain type, payload, and timestamp"
        if parsed["type"] not in SUPPORTED_TYPES:
            return {}, "unsupported message type"
        if not isinstance(parsed["payload"], dict):
            return {}, "payload must be an object"
        if not isinstance(parsed["timestamp"], str):
            return {}, "timestamp must be a string"
        if "channel" in parsed and (
            not isinstance(parsed["channel"], str) or not parsed["channel"]
        ):
            return {}, "channel must be a non-empty string"
        if parsed["type"] in {"subscribe", "unsubscribe"} and "channel" not in parsed:
            return {}, f'{parsed["type"]} message requires channel'
        return parsed, None

    async def _route(
        self, outgoing: dict[str, Any], sender: Any, sender_id: str
    ) -> None:
        if outgoing["type"] == "subscribe":
            self.clients.subscribe(sender_id, outgoing["channel"])
            await self.backbone.subscribe(sender_id, outgoing["channel"])
            return
        if outgoing["type"] == "unsubscribe":
            self.clients.unsubscribe(sender_id, outgoing["channel"])
            await self.backbone.unsubscribe(sender_id, outgoing["channel"])
            return
        if outgoing["type"] in {"broadcast", "system"}:
            await self.backbone.publish(outgoing)
            return
        target_id = outgoing["payload"].get("client_id")
        if not isinstance(target_id, str):
            await self.transport.send_message(
                sender, message("system", {"error": "direct payload requires client_id"})
            )
            return
        if not await self.backbone.has_client(target_id):
            await self.transport.send_message(
                sender,
                message("system", {"error": "client not found", "client_id": target_id}),
            )
            return
        await self.backbone.publish(outgoing)

    async def _deliver(self, outgoing: dict[str, Any]) -> None:
        if outgoing["type"] == "direct":
            target_id = outgoing["payload"].get("client_id")
            if "channel" in outgoing and not self.clients.is_subscribed(
                target_id, outgoing["channel"]
            ):
                return
            target = self.clients.get(target_id)
            recipients = [target] if target else []
        elif "channel" in outgoing:
            recipients = self.clients.channel_snapshot(outgoing["channel"])
        else:
            recipients = self.clients.snapshot()
        if recipients:
            await self.transport.broadcast(outgoing, recipients)


async def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    server = NotificationServer(backbone=RedisBackbone(redis_url))
    if not isinstance(server.transport, WebSocketTransport):
        raise RuntimeError("the configured transport cannot be served by this entry point")
    await server.start()
    try:
        async with serve(server.handler, host, port, process_request=server.process_request):
            await asyncio.get_running_loop().create_future()
    finally:
        await server.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    try:
        asyncio.run(run(args.host, args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
