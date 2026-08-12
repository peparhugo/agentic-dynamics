"""Async WebSocket notification server.

The WebSocket and health HTTP endpoint share one TCP port.  The server has no
framework dependency: ``websockets`` handles both the upgrade and the small
HTTP response needed by ``/health``.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import threading
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from urllib.parse import parse_qs, unquote, urlsplit

from redis.asyncio import Redis
from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response


SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
REDIS_CHANNEL = "notifications:messages"


def timestamp() -> str:
    """Return an unambiguous UTC timestamp for a message."""
    return datetime.now(timezone.utc).isoformat()


class MessageStore:
    """Small SQLite store shared by all server instances using one database."""

    def __init__(self, database_url: str | None = None) -> None:
        value = database_url or os.getenv("DATABASE_URL", "sqlite:///messages.db")
        if value.startswith("sqlite:///"):
            path = value[10:]
        elif value.startswith("sqlite://"):
            path = value[9:]
        else:
            path = value
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS messages "
                "(id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, type TEXT NOT NULL, "
                "payload TEXT NOT NULL, timestamp TEXT NOT NULL)"
            )
            self._connection.commit()

    def add(self, message: dict[str, Any]) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT INTO messages(channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (message.get("channel"), message["type"], json.dumps(message["payload"]), message["timestamp"]),
            )
            self._connection.commit()

    def list(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        return [
            {"id": row["id"], "channel": row["channel"], "type": row["type"],
             "payload": json.loads(row["payload"]), "timestamp": row["timestamp"]}
            for row in rows
        ]

    def history(self, channel: str, since: str | None, limit: int) -> tuple[list[dict[str, Any]], bool]:
        """Return a chronological page and whether another message exists."""
        conditions = ["channel = ?"]
        parameters: list[Any] = [channel]
        if since is not None:
            conditions.append("timestamp > ?")
            parameters.append(since)
        query = (
            "SELECT id, channel, type, payload, timestamp FROM messages WHERE "
            + " AND ".join(conditions)
            + " ORDER BY timestamp, id LIMIT ?"
        )
        parameters.append(limit + 1)
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        return [
            {"id": row["id"], "channel": row["channel"], "type": row["type"],
             "payload": json.loads(row["payload"]), "timestamp": row["timestamp"]}
            for row in rows
        ], has_more

    def delete_older_than(self, cutoff: str) -> int:
        with self._lock:
            cursor = self._connection.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff,))
            self._connection.commit()
            return cursor.rowcount

    def close(self) -> None:
        with self._lock:
            self._connection.close()


class RedisBroker:
    """Redis pub/sub transport. Redis is intentionally optional for local use."""

    def __init__(self, url: str, on_message: Any) -> None:
        self.redis = Redis.from_url(url, decode_responses=True)
        self.on_message = on_message
        self._pubsub = self.redis.pubsub()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        await self.redis.ping()
        await self._pubsub.subscribe(REDIS_CHANNEL)
        self._task = asyncio.create_task(self._consume())

    async def _consume(self) -> None:
        try:
            async for item in self._pubsub.listen():
                if item.get("type") == "message":
                    await self.on_message(json.loads(item["data"]))
        except asyncio.CancelledError:
            raise

    async def publish(self, envelope: dict[str, Any]) -> None:
        await self.redis.publish(REDIS_CHANNEL, json.dumps(envelope))

    async def allow_message(self, client_id: str, limit: int) -> bool:
        """Atomically count messages in a one-minute Redis window."""
        key = f"notifications:rate:{client_id}:{int(time.time() // 60)}"
        async with self.redis.pipeline(transaction=True) as pipe:
            await pipe.incr(key)
            await pipe.expire(key, 61)
            count, _ = await pipe.execute()
        return int(count) <= limit

    async def save_subscription(self, client_id: str, channel: str) -> None:
        await self.redis.sadd(f"notifications:client:{client_id}:channels", channel)

    async def remove_subscription(self, client_id: str, channel: str) -> None:
        await self.redis.srem(f"notifications:client:{client_id}:channels", channel)

    async def subscriptions(self, client_id: str) -> set[str]:
        return set(await self.redis.smembers(f"notifications:client:{client_id}:channels"))

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        await self._pubsub.close()
        await self.redis.close()


class ClientRegistry:
    """Thread-safe mapping of generated client IDs to WebSocket connections."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def add(self, connection: ServerConnection, client_id: str | None = None) -> str:
        client_id = client_id or uuid.uuid4().hex
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

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    def channel_subscribers(self, channel: str) -> set[str]:
        with self._lock:
            return set(self._channels.get(channel, set()))

    def channels(self) -> dict[str, set[str]]:
        with self._lock:
            return {name: set(ids) for name, ids in self._channels.items()}

    def get(self, client_id: str) -> ServerConnection | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> dict[str, ServerConnection]:
        with self._lock:
            return dict(self._clients)

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._clients)


class BaseTransport(ABC):
    """Delivery interface used by the notification protocol."""

    @abstractmethod
    async def on_connect(self, client_id: str, connection: Any) -> None:
        """Register a newly connected client with the transport."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Remove a client from the transport."""

    @abstractmethod
    async def send_message(self, client_id: str, message: str) -> None:
        """Deliver an encoded message to one client."""

    @abstractmethod
    async def broadcast(self, message: str, client_ids: Iterable[str]) -> None:
        """Deliver an encoded message to the selected clients."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport."""

    def __init__(self) -> None:
        self._connections: dict[str, ServerConnection] = {}

    async def on_connect(self, client_id: str, connection: ServerConnection) -> None:
        self._connections[client_id] = connection

    async def on_disconnect(self, client_id: str) -> None:
        self._connections.pop(client_id, None)

    async def send_message(self, client_id: str, message: str) -> None:
        connection = self._connections.get(client_id)
        if connection is not None:
            await connection.send(message)

    async def broadcast(self, message: str, client_ids: Iterable[str]) -> None:
        connections = [
            self._connections[client_id]
            for client_id in client_ids
            if client_id in self._connections
        ]
        if connections:
            await asyncio.gather(
                *(connection.send(message) for connection in connections),
                return_exceptions=True,
            )


TRANSPORTS: dict[str, type[BaseTransport]] = {"websocket": WebSocketTransport}


def make_message(
    message_type: str, payload: dict[str, Any], channel: str | None = None
) -> dict[str, Any]:
    if message_type not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported message type: {message_type}")
    message = {"type": message_type, "payload": payload, "timestamp": timestamp()}
    if channel is not None:
        message["channel"] = channel
    return message


class NotificationServer:
    """Notification server with transport-independent notification logic."""

    def __init__(self, host: str = "localhost", port: int = 8765,
                 redis_url: str | None = None, database_url: str | None = None,
                 transport: BaseTransport | None = None) -> None:
        self.host = host
        self.port = port
        self.registry = ClientRegistry()
        self.store = MessageStore(database_url)
        self.redis_url = redis_url if redis_url is not None else os.getenv("REDIS_URL")
        self.broker: RedisBroker | None = None
        self._server: Any = None
        try:
            self.rate_limit = max(0, int(os.getenv("RATE_LIMIT", "100")))
        except ValueError:
            self.rate_limit = 100
        try:
            self.message_ttl_days = max(0, int(os.getenv("MESSAGE_TTL_DAYS", "7")))
        except ValueError:
            self.message_ttl_days = 7
        self._rate_windows: dict[str, tuple[int, int]] = {}
        self._rate_lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task[None] | None = None
        transport_name = os.getenv("TRANSPORT", "websocket").strip().lower()
        transport_type = TRANSPORTS.get(transport_name)
        if transport is None and transport_type is None:
            raise ValueError(f"unsupported transport: {transport_name}")
        self.transport: BaseTransport = transport or transport_type()

    async def start(self) -> None:
        if self.redis_url:
            self.broker = RedisBroker(self.redis_url, self._receive_from_broker)
            await self.broker.start()
        self._server = await serve(
            self._handle_connection,
            self.host,
            self.port,
            process_request=self._process_request,
        )
        if self._server.sockets:
            self.port = self._server.sockets[0].getsockname()[1]
        await self._cleanup_messages()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            await asyncio.gather(self._cleanup_task, return_exceptions=True)
            self._cleanup_task = None
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self.broker is not None:
            await self.broker.stop()
            self.broker = None
        self.store.close()

    async def _cleanup_messages(self) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.message_ttl_days)).isoformat()
        self.store.delete_older_than(cutoff)

    async def _cleanup_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(3600)
                await self._cleanup_messages()
        except asyncio.CancelledError:
            raise

    async def _allow_message(self, client_id: str) -> bool:
        if self.broker is not None:
            return await self.broker.allow_message(client_id, self.rate_limit)
        window = int(time.time() // 60)
        async with self._rate_lock:
            previous_window, count = self._rate_windows.get(client_id, (window, 0))
            if previous_window != window:
                count = 0
            count += 1
            self._rate_windows[client_id] = (window, count)
            return count <= self.rate_limit

    async def _process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        path = urlsplit(request.path).path
        body_data: dict[str, Any] | None = None
        if path == "/health":
            body_data = {"status": "ok", "clients": self.registry.count}
        elif path == "/channels":
            body_data = {
                "channels": [
                    {"name": name, "subscribers": len(subscribers)}
                    for name, subscribers in sorted(self.registry.channels().items())
                ]
            }
        elif path == "/messages":
            query = parse_qs(urlsplit(request.path).query)
            try:
                limit = max(0, min(1000, int(query.get("limit", ["50"])[0])))
                offset = max(0, int(query.get("offset", ["0"])[0]))
            except (TypeError, ValueError):
                return Response(400, "Bad Request", Headers({"Content-Length": "0"}), b"")
            body_data = {"messages": self.store.list(limit, offset), "limit": limit, "offset": offset}
        elif path == "/history":
            query = parse_qs(urlsplit(request.path).query)
            channel = query.get("channel", [""])[0].strip()
            since = query.get("since", [None])[0]
            if not channel:
                return Response(400, "Bad Request", Headers({"Content-Length": "0"}), b"")
            if since is not None:
                try:
                    parsed_since = datetime.fromisoformat(since.replace("Z", "+00:00"))
                except ValueError:
                    return Response(400, "Bad Request", Headers({"Content-Length": "0"}), b"")
                if parsed_since.tzinfo is None:
                    parsed_since = parsed_since.replace(tzinfo=timezone.utc)
                since = parsed_since.astimezone(timezone.utc).isoformat()
            try:
                limit = max(1, min(1000, int(query.get("limit", ["50"])[0])))
            except (TypeError, ValueError):
                return Response(400, "Bad Request", Headers({"Content-Length": "0"}), b"")
            messages, has_more = self.store.history(channel, since, limit)
            body_data = {"messages": messages, "has_more": has_more}
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            channel = unquote(path[len("/channels/") : -len("/subscribers")]).strip("/")
            if not channel:
                return None
            body_data = {
                "channel": channel,
                "subscribers": sorted(self.registry.channel_subscribers(channel)),
            }
        else:
            return None
        body = json.dumps(body_data).encode()
        return Response(
            200,
            "OK",
            Headers(
                {
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body)),
                }
            ),
            body,
        )

    async def _handle_connection(self, connection: ServerConnection) -> None:
        requested_id = parse_qs(urlsplit(connection.request.path).query).get("client_id", [None])[0]
        client_id = self.registry.add(connection, requested_id if isinstance(requested_id, str) else None)
        try:
            if self.broker is not None and requested_id:
                for channel in await self.broker.subscriptions(client_id):
                    self.registry.subscribe(client_id, channel)
            await self.transport.on_connect(client_id, connection)
            await self.transport.send_message(
                client_id,
                json.dumps(make_message("system", {"event": "connected", "client_id": client_id}))
            )
            async for raw_message in connection:
                await self._handle_message(client_id, raw_message)
        finally:
            self.registry.remove(client_id)
            await self.transport.on_disconnect(client_id)

    async def _handle_message(self, sender_id: str, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
            if not isinstance(message, dict):
                raise ValueError
            message_type = message.get("type")
            payload = message.get("payload")
            if message_type in {"subscribe", "unsubscribe"} and payload is None:
                payload = {}
            if message_type not in SUPPORTED_TYPES or not isinstance(payload, dict):
                raise ValueError
            channel = message.get("channel")
            if channel is None:
                channel = payload.get("channel")
            if channel is not None and (
                not isinstance(channel, str) or not channel.strip()
            ):
                raise ValueError
            if message_type in {"subscribe", "unsubscribe"} and channel is None:
                raise ValueError
        except (json.JSONDecodeError, TypeError, ValueError):
            sender = self.registry.get(sender_id)
            if sender is not None:
                await self.transport.send_message(
                    sender_id, json.dumps(make_message("system", {"error": "invalid message"}))
                )
            return

        channel = channel.strip() if isinstance(channel, str) else None
        if not await self._allow_message(sender_id):
            sender = self.registry.get(sender_id)
            if sender is not None:
                await self.transport.send_message(
                    sender_id, json.dumps(make_message("system", {"error": "rate limit exceeded"}))
                )
            return
        if message_type == "subscribe":
            self.registry.subscribe(sender_id, channel)
            if self.broker is not None:
                await self.broker.save_subscription(sender_id, channel)
            await self._send_control(sender_id, "subscribed", channel)
        elif message_type == "unsubscribe":
            self.registry.unsubscribe(sender_id, channel)
            if self.broker is not None:
                await self.broker.remove_subscription(sender_id, channel)
            await self._send_control(sender_id, "unsubscribed", channel)
        else:
            outgoing = make_message(message_type, payload, channel)
            self.store.add(outgoing)
            if message_type == "broadcast":
                await self._publish(outgoing, {"kind": "broadcast"})
            elif message_type == "direct":
                target_id = payload.get("client_id") or payload.get("recipient")
                await self._publish(outgoing, {"kind": "direct", "target_id": target_id})
            else:
                # System messages are server-generated; clients may send them only
                # to themselves, which keeps the message contract predictable.
                if self.registry.get(sender_id) is not None and (
                    channel is None
                    or sender_id in self.registry.channel_subscribers(channel)
                ):
                    await self.transport.send_message(sender_id, json.dumps(outgoing))

    async def _publish(self, message: dict[str, Any], routing: dict[str, Any]) -> None:
        envelope = {"message": message, **routing}
        if self.broker is None:
            await self._receive_from_broker(envelope)
        else:
            await self.broker.publish(envelope)

    async def _receive_from_broker(self, envelope: dict[str, Any]) -> None:
        message = envelope["message"]
        kind = envelope.get("kind")
        if kind == "broadcast":
            await self.broadcast(message, message.get("channel"))
        elif kind == "direct":
            target_id = envelope.get("target_id")
            target = self.registry.get(target_id) if isinstance(target_id, str) else None
            channel = message.get("channel")
            if target is not None and (channel is None or target_id in self.registry.channel_subscribers(channel)):
                await self.transport.send_message(target_id, json.dumps(message))

    async def _send_control(self, client_id: str, event: str, channel: str) -> None:
        client = self.registry.get(client_id)
        if client is not None:
            await self.transport.send_message(
                client_id,
                json.dumps(make_message("system", {"event": event, "channel": channel}))
            )

    async def broadcast(self, message: dict[str, Any], channel: str | None = None) -> None:
        encoded = json.dumps(message)
        clients = self.registry.snapshot()
        if channel is not None:
            client_ids = {
                client_id for client_id in clients
                if client_id in self.registry.channel_subscribers(channel)
            }
        else:
            client_ids = clients.keys()
        await self.transport.broadcast(encoded, client_ids)


async def run_server(host: str = "localhost", port: int = 8765) -> None:
    server = NotificationServer(host, port)
    await server.start()
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(run_server())
