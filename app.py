"""Async WebSocket notification server with a small HTTP health endpoint."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

import redis.asyncio as redis
import websockets
from websockets.exceptions import ConnectionClosed


MESSAGE_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _message(message_type: str, payload: dict[str, Any]) -> str:
    return json.dumps(
        {"type": message_type, "payload": payload, "timestamp": _timestamp()}
    )


class MessageStore:
    """Small thread-safe SQLite store shared by the HTTP and websocket paths."""

    def __init__(self, database_url: str | None = None) -> None:
        path = database_url or os.getenv("DATABASE_URL") or ":memory:"
        if path.startswith("sqlite:///"):
            path = path[10:]
        elif path.startswith("sqlite://"):
            path = path[9:]
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._connection:
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS messages ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, type TEXT NOT NULL, "
                "payload TEXT NOT NULL, timestamp TEXT NOT NULL)"
            )

    def save(self, channel: str | None, message_type: str, payload: dict[str, Any], timestamp: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (channel, message_type, json.dumps(payload), timestamp),
            )

    def list(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        limit = max(0, min(limit, 1000))
        offset = max(0, offset)
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        return [
            {"id": row["id"], "channel": row["channel"], "type": row["type"],
             "payload": json.loads(row["payload"]), "timestamp": row["timestamp"]}
            for row in rows
        ]


class RedisBackbone:
    """Redis pub/sub transport. A server subscribes once and routes received events."""

    channel = "notifications:messages"
    state_prefix = "notifications:client:"

    def __init__(self, url: str, on_message: Any) -> None:
        self.client = redis.from_url(url, decode_responses=True)
        self.on_message = on_message
        self._pubsub: Any = None
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        await self.client.ping()
        self._pubsub = self.client.pubsub()
        await self._pubsub.subscribe(self.channel)
        self._task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        try:
            async for event in self._pubsub.listen():
                if event.get("type") == "message":
                    await self.on_message(json.loads(event["data"]))
        except asyncio.CancelledError:
            pass

    async def publish(self, event: dict[str, Any]) -> None:
        await self.client.publish(self.channel, json.dumps(event))

    async def save_subscription(self, client_id: str, channel: str) -> None:
        await self.client.sadd(f"{self.state_prefix}{client_id}:channels", channel)
        await self.client.hset(f"{self.state_prefix}{client_id}", mapping={"connected": "1"})

    async def remove_subscription(self, client_id: str, channel: str) -> None:
        await self.client.srem(f"{self.state_prefix}{client_id}:channels", channel)

    async def close(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        if self._pubsub:
            await self._pubsub.close()
        close = getattr(self.client, "aclose", None) or getattr(self.client, "close", None)
        if close:
            result = close()
            if inspect.isawaitable(result):
                await result


class NotificationServer:
    """Manage connected clients and route validated JSON notifications."""

    def __init__(self, redis_url: str | None = None, database_url: str | None = None,
                 redis_client: Any | None = None) -> None:
        self._clients: dict[str, Any] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()
        self.store = MessageStore(database_url)
        self._backbone: RedisBackbone | None = None
        if redis_client is not None:
            self._backbone = RedisBackbone.__new__(RedisBackbone)
            self._backbone.client = redis_client
            self._backbone.on_message = self._receive_event
            self._backbone._pubsub = None
            self._backbone._task = None
        elif redis_url or os.getenv("REDIS_URL"):
            self._backbone = RedisBackbone(redis_url or os.environ["REDIS_URL"], self._receive_event)
        self._broker_started = False

    async def _ensure_broker(self) -> None:
        if self._backbone is None or self._broker_started:
            return
        try:
            await self._backbone.start()
            self._broker_started = True
        except Exception:
            # The in-process router remains available when Redis is not configured.
            self._backbone = None

    async def _receive_event(self, event: dict[str, Any]) -> None:
        channel = event.get("channel")
        outgoing = event["message"]
        if channel:
            await self._broadcast_to_channel(channel, outgoing)
        elif event.get("type") == "direct":
            await self._send_to(event.get("target_id", ""), outgoing)
        else:
            await self.broadcast(outgoing)

    @property
    def clients(self) -> dict[str, Any]:
        """Return a snapshot of the registry, never the mutable registry itself."""
        with self._lock:
            return dict(self._clients)

    @property
    def connected_client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    def add_client(self, websocket: Any) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = websocket
        return client_id

    def remove_client(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in list(self._channels):
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def subscribe(self, client_id: str, channel: str) -> None:
        if not isinstance(channel, str) or not channel:
            return
        with self._lock:
            if client_id in self._clients:
                self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    def channel_snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                channel: len(subscribers)
                for channel, subscribers in sorted(self._channels.items())
            }

    def channel_subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    async def _send_to(self, client_id: str, message: str) -> None:
        with self._lock:
            websocket = self._clients.get(client_id)
        if websocket is None:
            return
        try:
            await websocket.send(message)
        except ConnectionClosed:
            self.remove_client(client_id)

    async def broadcast(self, message: str) -> None:
        with self._lock:
            recipients = list(self._clients.items())
        if not recipients:
            return
        results = await asyncio.gather(
            *(self._send_to(client_id, message) for client_id, _ in recipients),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                continue

    async def _broadcast_to_channel(self, channel: str, message: str) -> None:
        with self._lock:
            recipients = list(self._channels.get(channel, set()))
        await asyncio.gather(
            *(self._send_to(client_id, message) for client_id in recipients),
            return_exceptions=True,
        )

    async def handle_client(self, websocket: Any) -> None:
        client_id = self.add_client(websocket)
        await self._send_to(client_id, _message("system", {"client_id": client_id}))
        try:
            async for raw_message in websocket:
                await self.handle_message(client_id, raw_message)
        except (ConnectionClosed, asyncio.CancelledError):
            pass
        finally:
            self.remove_client(client_id)

    async def handle_message(self, sender_id: str, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(message, dict):
            return
        message_type = message.get("type")
        payload = message.get("payload")
        if message_type not in MESSAGE_TYPES or not isinstance(payload, dict):
            return

        channel = message.get("channel")
        if channel is None:
            channel = payload.get("channel")
        if not isinstance(channel, str) or not channel:
            channel = None

        if message_type == "subscribe":
            if channel is not None:
                self.subscribe(sender_id, channel)
                await self._ensure_broker()
                if self._backbone:
                    await self._backbone.save_subscription(sender_id, channel)
            return
        if message_type == "unsubscribe":
            if channel is not None:
                self.unsubscribe(sender_id, channel)
                if self._backbone:
                    await self._backbone.remove_subscription(sender_id, channel)
            return

        await self._ensure_broker()
        timestamp = _timestamp()
        outgoing_data = {"type": message_type, "payload": payload, "timestamp": timestamp}
        if channel is not None:
            outgoing_data["channel"] = channel
        outgoing = json.dumps(outgoing_data)
        self.store.save(channel, message_type, payload, timestamp)
        if message_type == "direct":
            target_id = payload.get("client_id") or payload.get("target_id")
            if isinstance(target_id, str):
                event = {"message": outgoing, "type": message_type, "target_id": target_id}
                if self._backbone:
                    await self._backbone.publish(event)
                else:
                    await self._receive_event(event)
            return
        event = {"message": outgoing, "type": message_type, "channel": channel}
        if self._backbone:
            await self._backbone.publish(event)
        else:
            await self._receive_event(event)

    def health(self) -> dict[str, Any]:
        return {"status": "ok", "connected_clients": self.connected_client_count}


class NotificationHTTPServer:
    """Minimal asyncio HTTP server used so health shares the same event loop."""

    def __init__(self, notification_server: NotificationServer) -> None:
        self.notification_server = notification_server

    async def handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=5)
            method, path, *_ = request_line.decode("ascii", "replace").split()
            request = urlsplit(path)
            while await reader.readline() != b"\r\n":
                pass
            if method == "GET" and request.path == "/health":
                body = json.dumps(self.notification_server.health()).encode()
                response = (
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                    + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                    + body
                )
            elif method == "GET" and request.path == "/channels":
                body = json.dumps({"channels": self.notification_server.channel_snapshot()}).encode()
                response = (
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                    + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                    + body
                )
            elif method == "GET" and request.path == "/messages":
                query = parse_qs(request.query)
                try:
                    limit = int(query.get("limit", ["50"])[0])
                    offset = int(query.get("offset", ["0"])[0])
                except ValueError:
                    limit, offset = 50, 0
                body = json.dumps({"messages": self.notification_server.store.list(limit, offset)}).encode()
                response = (
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                    + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                    + body
                )
            elif method == "GET" and request.path.startswith("/channels/"):
                channel_path = request.path.removeprefix("/channels/")
                if channel_path.endswith("/subscribers"):
                    channel = unquote(channel_path.removesuffix("/subscribers").rstrip("/"))
                    body = json.dumps(
                        {"channel": channel, "subscribers": self.notification_server.channel_subscribers(channel)}
                    ).encode()
                    response = (
                        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                        + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                        + body
                    )
                else:
                    body = b'{"error":"not found"}'
                    response = (
                        b"HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\n"
                        + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                        + body
                    )
            else:
                body = b'{"error":"not found"}'
                response = (
                    b"HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\n"
                    + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                    + body
                )
            writer.write(response)
            await writer.drain()
        except (asyncio.TimeoutError, ValueError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()


async def run_server(
    websocket_host: str = "0.0.0.0",
    websocket_port: int = 8765,
    http_host: str = "0.0.0.0",
    http_port: int = 8080,
) -> None:
    server = NotificationServer(
        redis_url=os.getenv("REDIS_URL"),
        database_url=os.getenv("DATABASE_URL", "messages.db"),
    )
    websocket_server = await websockets.serve(server.handle_client, websocket_host, websocket_port)
    http_server = await asyncio.start_server(
        NotificationHTTPServer(server).handler, http_host, http_port
    )
    try:
        await asyncio.Future()
    finally:
        websocket_server.close()
        await websocket_server.wait_closed()
        http_server.close()
        await http_server.wait_closed()
        if server._backbone:
            await server._backbone.close()


# Convenient application object for callers that import ``app``.
app = NotificationServer()


if __name__ == "__main__":
    asyncio.run(
        run_server(
            websocket_port=int(os.getenv("WEBSOCKET_PORT", "8765")),
            http_port=int(os.getenv("HTTP_PORT", "8080")),
        )
    )
