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
import uuid
from datetime import datetime, timezone
from typing import Any
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
    """WebSocket notification server with broadcast and direct delivery."""

    def __init__(self, host: str = "localhost", port: int = 8765,
                 redis_url: str | None = None, database_url: str | None = None) -> None:
        self.host = host
        self.port = port
        self.registry = ClientRegistry()
        self.store = MessageStore(database_url)
        self.redis_url = redis_url if redis_url is not None else os.getenv("REDIS_URL")
        self.broker: RedisBroker | None = None
        self._server: Any = None

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

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self.broker is not None:
            await self.broker.stop()
            self.broker = None
        self.store.close()

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
            await connection.send(
                json.dumps(make_message("system", {"event": "connected", "client_id": client_id}))
            )
            async for raw_message in connection:
                await self._handle_message(client_id, raw_message)
        finally:
            self.registry.remove(client_id)

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
                await sender.send(json.dumps(make_message("system", {"error": "invalid message"})))
            return

        channel = channel.strip() if isinstance(channel, str) else None
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
                sender = self.registry.get(sender_id)
                if sender is not None and (
                    channel is None
                    or sender_id in self.registry.channel_subscribers(channel)
                ):
                    await sender.send(json.dumps(outgoing))

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
                await target.send(json.dumps(message))

    async def _send_control(self, client_id: str, event: str, channel: str) -> None:
        client = self.registry.get(client_id)
        if client is not None:
            await client.send(
                json.dumps(make_message("system", {"event": event, "channel": channel}))
            )

    async def broadcast(self, message: dict[str, Any], channel: str | None = None) -> None:
        encoded = json.dumps(message)
        clients = self.registry.snapshot()
        if channel is not None:
            clients = {
                client_id: connection
                for client_id, connection in clients.items()
                if client_id in self.registry.channel_subscribers(channel)
            }
        connections = clients.values()
        if connections:
            await asyncio.gather(*(connection.send(encoded) for connection in connections), return_exceptions=True)


async def run_server(host: str = "localhost", port: int = 8765) -> None:
    server = NotificationServer(host, port)
    await server.start()
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(run_server())
