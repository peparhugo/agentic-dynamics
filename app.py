"""Async notification server backed by Redis and SQLite."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import parse_qs, unquote, urlsplit

import redis.asyncio as redis
from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Response

SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
SUBSCRIPTION_TYPES = {"subscribe", "unsubscribe"}
BACKBONE_CHANNEL = "notifications:messages"
CLIENTS_KEY = "notifications:clients"
CHANNELS_KEY = "notifications:channels"
CHANNEL_KEY_PREFIX = "notifications:channel:"
RATE_LIMIT_KEY_PREFIX = "notifications:rate_limit:"


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def sqlite_path(database_url: str) -> Path:
    if database_url.startswith("sqlite:///"):
        return Path(database_url[len("sqlite:///") :])
    if database_url.startswith("sqlite://"):
        return Path(database_url[len("sqlite://") :])
    return Path(database_url)


class SQLiteStore:
    """Persist message history in SQLite and optionally mirror legacy JSONL."""

    def __init__(self, database_url: str, legacy_history_path: Path | None = None) -> None:
        self.path = sqlite_path(database_url)
        self.legacy_history_path = legacy_history_path
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.legacy_history_path is not None:
            self.legacy_history_path.parent.mkdir(parents=True, exist_ok=True)
            self.legacy_history_path.touch(exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
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

    async def append_message(self, message: dict[str, Any]) -> int:
        async with self._lock:
            return await asyncio.to_thread(self._append_sync, message)

    def _append_sync(self, message: dict[str, Any]) -> int:
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (
                    message.get("channel"),
                    message["type"],
                    json.dumps(message["payload"], separators=(",", ":")),
                    message["timestamp"],
                ),
            )
            message_id = int(cursor.lastrowid)
        if self.legacy_history_path is not None:
            with self.legacy_history_path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(message, separators=(",", ":")) + "\n")
                file.flush()
                os.fsync(file.fileno())
        return message_id

    async def messages(self, limit: int, offset: int) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._messages_sync, limit, offset)

    def _messages_sync(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                """
                SELECT id, channel, type, payload, timestamp
                FROM messages ORDER BY id ASC LIMIT ? OFFSET ?
                """,
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

    async def history(
        self, channel: str, since: str, limit: int
    ) -> tuple[list[dict[str, Any]], bool]:
        rows = await asyncio.to_thread(self._history_sync, channel, since, limit + 1)
        return rows[:limit], len(rows) > limit

    def _history_sync(
        self, channel: str, since: str, fetch_limit: int
    ) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                """
                SELECT id, channel, type, payload, timestamp
                FROM messages
                WHERE channel = ? AND timestamp >= ?
                ORDER BY timestamp ASC, id ASC LIMIT ?
                """,
                (channel, since, fetch_limit),
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

    async def delete_before(self, cutoff: str) -> int:
        async with self._lock:
            return await asyncio.to_thread(self._delete_before_sync, cutoff)

    def _delete_before_sync(self, cutoff: str) -> int:
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                "DELETE FROM messages WHERE timestamp < ?", (cutoff,)
            )
            return cursor.rowcount


class BaseTransport(ABC):
    """Interface between notification routing and client connections."""

    def __init__(self) -> None:
        self.server: NotificationServer | None = None

    def bind(self, server: NotificationServer) -> None:
        self.server = server

    @abstractmethod
    async def on_connect(self, connection: Any) -> str:
        """Register a newly connected client and return its ID."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Remove a disconnected client."""

    @abstractmethod
    async def send_message(self, client_id: str, message: dict[str, Any]) -> None:
        """Send a message to one client."""

    @abstractmethod
    async def broadcast(self, client_ids: list[str], message: dict[str, Any]) -> None:
        """Send a message to a collection of clients."""

    @asynccontextmanager
    async def run(
        self, host: str, port: int, process_request: Any
    ) -> AsyncIterator[Any]:
        raise NotImplementedError
        yield


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport."""

    def __init__(self) -> None:
        super().__init__()
        self._connections: dict[str, ServerConnection] = {}

    def _server(self) -> NotificationServer:
        if self.server is None:
            raise RuntimeError("transport is not bound to a notification server")
        return self.server

    async def on_connect(self, connection: ServerConnection) -> str:
        server = self._server()
        client_id = str(uuid.uuid4())
        self._connections[client_id] = connection
        await server._register(client_id)
        connected = {
            "type": "system",
            "payload": {"event": "connected", "client_id": client_id},
            "timestamp": timestamp(),
        }
        await server.store.append_message(connected)
        await self.send_message(client_id, connected)
        return client_id

    async def on_disconnect(self, client_id: str) -> None:
        self._connections.pop(client_id, None)
        await self._server()._unregister(client_id)

    async def send_message(self, client_id: str, message: dict[str, Any]) -> None:
        connection = self._connections.get(client_id)
        if connection is None:
            return
        await connection.send(json.dumps(message, separators=(",", ":")))

    async def broadcast(self, client_ids: list[str], message: dict[str, Any]) -> None:
        results = await asyncio.gather(
            *(self.send_message(client_id, message) for client_id in client_ids),
            return_exceptions=True,
        )
        for client_id, result in zip(client_ids, results):
            if isinstance(result, ConnectionClosed):
                await self.on_disconnect(client_id)

    async def websocket_handler(self, websocket: ServerConnection) -> None:
        client_id = await self.on_connect(websocket)
        try:
            async for raw in websocket:
                await self._server()._process(client_id, raw)
        except ConnectionClosed:
            pass
        finally:
            await self.on_disconnect(client_id)

    @asynccontextmanager
    async def run(
        self, host: str, port: int, process_request: Any
    ) -> AsyncIterator[Server]:
        async with serve(
            self.websocket_handler,
            host,
            port,
            process_request=process_request,
        ) as server:
            yield server


TRANSPORTS: dict[str, type[BaseTransport]] = {
    "websocket": WebSocketTransport,
    "ws": WebSocketTransport,
}


class NotificationServer:
    def __init__(
        self,
        data_dir: str | Path = "data",
        *,
        redis_url: str | None = None,
        database_url: str | None = None,
        redis_client: Any | None = None,
        transport: BaseTransport | None = None,
        rate_limit: int | None = None,
        message_ttl_days: int | None = None,
    ) -> None:
        data_path = Path(data_dir)
        self.redis_url = redis_url or os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
        database_url = database_url or os.environ.get(
            "DATABASE_URL", f"sqlite:///{data_path / 'messages.db'}"
        )
        self.store = SQLiteStore(database_url, data_path / "messages.jsonl")
        self._redis = redis_client or redis.from_url(self.redis_url, decode_responses=True)
        self._owns_redis = redis_client is None
        self.transport = transport or self._transport_from_config()
        self.transport.bind(self)
        self._clients: set[str] = set()
        self._local_channels: dict[str, set[str]] = {}
        self._registry_lock = asyncio.Lock()
        self._legacy_clients_lock = asyncio.Lock()
        self._subscriber_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None
        self._subscriber_ready = asyncio.Event()
        self._legacy_clients_path = data_path / "clients.json"
        self.rate_limit = self._positive_setting("RATE_LIMIT", rate_limit, 100)
        self.message_ttl_days = self._positive_setting(
            "MESSAGE_TTL_DAYS", message_ttl_days, 7
        )

    @staticmethod
    def _positive_setting(name: str, value: int | None, default: int) -> int:
        configured = int(os.environ.get(name, str(default))) if value is None else value
        if configured < 1:
            raise ValueError(f"{name} must be a positive integer")
        return configured

    @staticmethod
    def _transport_from_config() -> BaseTransport:
        transport_name = os.environ.get("TRANSPORT", "websocket").strip().lower()
        try:
            transport_class = TRANSPORTS[transport_name]
        except KeyError as error:
            raise ValueError(f"unsupported transport: {transport_name}") from error
        return transport_class()

    @staticmethod
    def _channel_key(channel: str) -> str:
        return CHANNEL_KEY_PREFIX + channel

    async def initialize(self) -> None:
        await self.store.initialize()
        await self._redis.ping()
        self._subscriber_task = asyncio.create_task(self._subscriber_worker())
        self._cleanup_task = asyncio.create_task(self._cleanup_worker())
        await asyncio.wait_for(self._subscriber_ready.wait(), timeout=2)
        await self._write_legacy_clients()

    async def close(self) -> None:
        async with self._registry_lock:
            client_ids = list(self._clients)
        for client_id in client_ids:
            await self.transport.on_disconnect(client_id)
        if self._subscriber_task is not None:
            self._subscriber_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._subscriber_task
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._cleanup_task
        if self._owns_redis:
            await self._redis.aclose()

    async def _subscriber_worker(self) -> None:
        pubsub = self._redis.pubsub()
        try:
            await pubsub.subscribe(BACKBONE_CHANNEL)
            self._subscriber_ready.set()
            async for event in pubsub.listen():
                if event["type"] != "message":
                    continue
                raw = event["data"]
                if isinstance(raw, bytes):
                    raw = raw.decode()
                await self._deliver(json.loads(raw))
        finally:
            await pubsub.aclose()

    async def _cleanup_worker(self) -> None:
        while True:
            cutoff = datetime.now(timezone.utc) - timedelta(days=self.message_ttl_days)
            await self.store.delete_before(cutoff.isoformat())
            await asyncio.sleep(24 * 60 * 60)

    async def _deliver(self, envelope: dict[str, Any]) -> None:
        route = envelope["route"]
        async with self._registry_lock:
            if route == "all":
                recipients = list(self._clients)
            elif route == "channel":
                recipients = [
                    client_id
                    for client_id in self._local_channels.get(envelope["channel"], set())
                    if client_id in self._clients
                ]
            else:
                client_id = envelope["client_id"]
                recipients = [] if client_id not in self._clients else [client_id]
                if recipients and envelope.get("channel") not in (None, ""):
                    if client_id not in self._local_channels.get(envelope["channel"], set()):
                        recipients = []
        if recipients:
            await self.transport.broadcast(recipients, envelope["message"])

    async def _publish(self, message: dict[str, Any], **routing: Any) -> None:
        envelope = {"message": message, **routing}
        await self._redis.publish(
            BACKBONE_CHANNEL, json.dumps(envelope, separators=(",", ":"))
        )

    async def _write_legacy_clients(self) -> None:
        async with self._registry_lock:
            client_ids = sorted(self._clients)
        async with self._legacy_clients_lock:
            await asyncio.to_thread(self._write_legacy_clients_sync, client_ids)

    def _write_legacy_clients_sync(self, client_ids: list[str]) -> None:
        self._legacy_clients_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._legacy_clients_path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"clients": client_ids}, indent=2) + "\n")
        os.replace(temporary, self._legacy_clients_path)

    async def connected_count(self) -> int:
        return int(await self._redis.scard(CLIENTS_KEY))

    async def _register(self, client_id: str) -> None:
        async with self._registry_lock:
            self._clients.add(client_id)
        await self._redis.sadd(CLIENTS_KEY, client_id)
        await self._write_legacy_clients()

    async def _unregister(self, client_id: str) -> None:
        async with self._registry_lock:
            self._clients.discard(client_id)
            channels = [
                channel for channel, clients in self._local_channels.items() if client_id in clients
            ]
            for channel in channels:
                self._local_channels[channel].discard(client_id)
                if not self._local_channels[channel]:
                    del self._local_channels[channel]
        await self._redis.srem(CLIENTS_KEY, client_id)
        for channel in channels:
            key = self._channel_key(channel)
            await self._redis.srem(key, client_id)
            if not await self._redis.scard(key):
                await self._redis.srem(CHANNELS_KEY, channel)
        await self._write_legacy_clients()

    async def _subscribe(self, client_id: str, channel: str) -> None:
        async with self._registry_lock:
            self._local_channels.setdefault(channel, set()).add(client_id)
        await self._redis.sadd(CHANNELS_KEY, channel)
        await self._redis.sadd(self._channel_key(channel), client_id)

    async def _unsubscribe(self, client_id: str, channel: str) -> None:
        async with self._registry_lock:
            subscribers = self._local_channels.get(channel)
            if subscribers is not None:
                subscribers.discard(client_id)
                if not subscribers:
                    del self._local_channels[channel]
        key = self._channel_key(channel)
        await self._redis.srem(key, client_id)
        if not await self._redis.scard(key):
            await self._redis.srem(CHANNELS_KEY, channel)

    async def channel_counts(self) -> list[dict[str, Any]]:
        channels = await self._redis.smembers(CHANNELS_KEY)
        return [
            {
                "name": self._decode(name),
                "subscriber_count": int(await self._redis.scard(self._channel_key(self._decode(name)))),
            }
            for name in sorted(channels)
        ]

    @staticmethod
    def _decode(value: str | bytes) -> str:
        return value.decode() if isinstance(value, bytes) else value

    async def channel_subscribers(self, channel: str) -> list[str]:
        members = await self._redis.smembers(self._channel_key(channel))
        return sorted(self._decode(member) for member in members)

    @staticmethod
    def _error(detail: str) -> dict[str, Any]:
        return {"type": "system", "payload": {"error": detail}, "timestamp": timestamp()}

    async def _rate_limit_exceeded(self, client_id: str) -> bool:
        minute = int(datetime.now(timezone.utc).timestamp()) // 60
        key = f"{RATE_LIMIT_KEY_PREFIX}{client_id}:{minute}"
        count = int(await self._redis.incr(key))
        if count == 1:
            await self._redis.expire(key, 120)
        return count > self.rate_limit

    async def _process(self, sender_id: str, raw: str | bytes) -> None:
        if await self._rate_limit_exceeded(sender_id):
            await self.transport.send_message(sender_id, self._error("rate limit exceeded"))
            return
        try:
            incoming = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            await self.transport.send_message(sender_id, self._error("invalid JSON"))
            return
        if not isinstance(incoming, dict):
            await self.transport.send_message(
                sender_id, self._error("message must be a JSON object")
            )
            return
        message_type = incoming.get("type")
        payload = incoming.get("payload")
        if message_type not in SUPPORTED_TYPES:
            await self.transport.send_message(sender_id, self._error("unsupported message type"))
            return
        channel = incoming.get("channel")
        if channel is not None and (not isinstance(channel, str) or not channel.strip()):
            await self.transport.send_message(
                sender_id, self._error("channel must be a non-empty string")
            )
            return
        if message_type in SUBSCRIPTION_TYPES:
            if channel is None:
                await self.transport.send_message(
                    sender_id, self._error(f"{message_type} requires channel")
                )
                return
            if message_type == "subscribe":
                await self._subscribe(sender_id, channel)
            else:
                await self._unsubscribe(sender_id, channel)
            return
        if not isinstance(payload, dict):
            await self.transport.send_message(sender_id, self._error("payload must be an object"))
            return

        message = {"type": message_type, "payload": payload, "timestamp": timestamp()}
        if channel is not None:
            message["channel"] = channel
        if message_type == "direct":
            recipient_id = payload.get("client_id")
            if not isinstance(recipient_id, str):
                await self.transport.send_message(
                    sender_id, self._error("direct payload requires client_id")
                )
                return
            exists = await self._redis.sismember(CLIENTS_KEY, recipient_id)
            subscribed = channel is None or await self._redis.sismember(
                self._channel_key(channel), recipient_id
            )
            if not exists or not subscribed:
                detail = "client not subscribed" if channel is not None else "client not connected"
                await self.transport.send_message(sender_id, self._error(detail))
                return
            await self.store.append_message(message)
            await self._publish(
                message, route="direct", client_id=recipient_id, channel=channel
            )
            return

        await self.store.append_message(message)
        if channel is None:
            await self._publish(message, route="all")
        else:
            await self._publish(message, route="channel", channel=channel)

    @staticmethod
    def _response(status: int, body_value: dict[str, Any]) -> Response:
        body = json.dumps(body_value).encode()
        reason = "OK" if status == 200 else "Bad Request"
        return Response(
            status,
            reason,
            Headers({"Content-Type": "application/json", "Content-Length": str(len(body))}),
            body,
        )

    async def process_request(
        self, connection: ServerConnection, request: Any
    ) -> Response | None:
        parsed = urlsplit(request.path)
        path = parsed.path
        if path == "/health":
            response_body: dict[str, Any] = {
                "connected_clients": await self.connected_count()
            }
        elif path == "/messages":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
                if not 1 <= limit <= 1000 or offset < 0:
                    raise ValueError
            except ValueError:
                return self._response(400, {"error": "invalid limit or offset"})
            response_body = {"messages": await self.store.messages(limit, offset)}
        elif path == "/history":
            query = parse_qs(parsed.query)
            channel = query.get("channel", [None])[0]
            since_value = query.get("since", [None])[0]
            try:
                limit = int(query.get("limit", ["50"])[0])
                if not isinstance(channel, str) or not channel.strip():
                    raise ValueError
                if not isinstance(since_value, str):
                    raise ValueError
                parsed_since = datetime.fromisoformat(since_value.replace("Z", "+00:00"))
                if parsed_since.tzinfo is None or not 1 <= limit <= 1000:
                    raise ValueError
            except (TypeError, ValueError):
                return self._response(
                    400, {"error": "channel, ISO since, and valid limit are required"}
                )
            normalized_since = parsed_since.astimezone(timezone.utc).isoformat()
            messages, has_more = await self.store.history(
                channel, normalized_since, limit
            )
            response_body = {"messages": messages, "has_more": has_more}
        elif path == "/channels":
            response_body = {"channels": await self.channel_counts()}
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            encoded_name = path[len("/channels/") : -len("/subscribers")].rstrip("/")
            if not encoded_name or "/" in encoded_name:
                return None
            channel = unquote(encoded_name)
            response_body = {
                "channel": channel,
                "subscribers": await self.channel_subscribers(channel),
            }
        else:
            return None
        return self._response(200, response_body)

    @asynccontextmanager
    async def run(self, host: str = "127.0.0.1", port: int = 8765) -> AsyncIterator[Any]:
        await self.initialize()
        try:
            async with self.transport.run(host, port, self.process_request) as server:
                yield server
        finally:
            await self.close()


async def main(host: str, port: int, data_dir: str) -> None:
    server = NotificationServer(data_dir)
    async with server.run(host, port):
        print(f"Notification server listening on http://{host}:{port}")
        await asyncio.Future()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")))
    parser.add_argument("--data-dir", default=os.environ.get("DATA_DIR", "data"))
    arguments = parser.parse_args()
    try:
        asyncio.run(main(arguments.host, arguments.port, arguments.data_dir))
    except KeyboardInterrupt:
        pass
