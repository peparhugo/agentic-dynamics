"""Async WebSocket notification server backed by Redis and SQLite."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import parse_qs, unquote, urlsplit

import redis.asyncio as redis
import websockets
from websockets.http11 import Headers, Response
from websockets.server import ServerConnection


LOGGER = logging.getLogger(__name__)
SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
REDIS_CHANNEL = "notifications:messages"
CLIENT_PREFIX = "notifications:client:"
CHANNEL_PREFIX = "notifications:channel:"
RATE_LIMIT_PREFIX = "notifications:rate-limit:"


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MessageStore:
    """Small SQLite repository. Database work is moved off the event loop."""

    def __init__(self, url: str) -> None:
        self.path = self._path(url)
        self.connection: sqlite3.Connection | None = None

    @staticmethod
    def _path(url: str) -> str:
        if url.startswith("sqlite:///"):
            return url[10:]
        if url.startswith("sqlite://"):
            return url[9:]
        return url

    async def start(self) -> None:
        await asyncio.to_thread(self._start)

    def _start(self) -> None:
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, type TEXT NOT NULL, "
            "payload TEXT NOT NULL, timestamp TEXT NOT NULL)"
        )
        self.connection.commit()

    async def add(self, channel: str | None, message_type: str, payload: dict[str, Any], sent_at: str) -> None:
        await asyncio.to_thread(self._add, channel, message_type, payload, sent_at)

    def _add(self, channel: str | None, message_type: str, payload: dict[str, Any], sent_at: str) -> None:
        assert self.connection is not None
        self.connection.execute(
            "INSERT INTO messages(channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
            (channel, message_type, json.dumps(payload), sent_at),
        )
        self.connection.commit()

    async def list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list, limit, offset)

    def _list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        assert self.connection is not None
        rows = self.connection.execute(
            "SELECT id, channel, type, payload, timestamp FROM messages "
            "ORDER BY id LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
        return [
            {"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]}
            for row in rows
        ]

    async def history(self, channel: str, since: str | None, limit: int) -> tuple[list[dict[str, Any]], bool]:
        return await asyncio.to_thread(self._history, channel, since, limit)

    def _history(self, channel: str, since: str | None, limit: int) -> tuple[list[dict[str, Any]], bool]:
        assert self.connection is not None
        query = (
            "SELECT id, channel, type, payload, timestamp FROM messages "
            "WHERE channel = ?"
        )
        parameters: list[Any] = [channel]
        if since is not None:
            query += " AND timestamp > ?"
            parameters.append(since)
        query += " ORDER BY timestamp ASC, id ASC LIMIT ?"
        parameters.append(limit + 1)
        rows = self.connection.execute(query, parameters).fetchall()
        has_more = len(rows) > limit
        return [
            {"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]}
            for row in rows[:limit]
        ], has_more

    async def cleanup(self, cutoff: str) -> None:
        await asyncio.to_thread(self._cleanup, cutoff)

    def _cleanup(self, cutoff: str) -> None:
        assert self.connection is not None
        self.connection.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff,))
        self.connection.commit()

    async def close(self) -> None:
        if self.connection is not None:
            await asyncio.to_thread(self.connection.close)
            self.connection = None


class LocalBroker:
    """Fallback used only when a Redis service is not reachable."""

    subscribers: set[asyncio.Queue[str]] = set()

    @classmethod
    async def publish(cls, message: str) -> None:
        for queue in tuple(cls.subscribers):
            await queue.put(message)


class BaseTransport(ABC):
    """Transport contract used by the notification routing layer."""

    def __init__(self, server: "NotificationServer | None" = None) -> None:
        self.server = server

    def attach(self, server: "NotificationServer") -> None:
        self.server = server

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    @abstractmethod
    def on_connect(self, client_id: str, client: Any) -> None:
        """Handle a newly connected client."""

    @abstractmethod
    def on_disconnect(self, client_id: str, client: Any) -> None:
        """Handle a disconnected client."""

    @abstractmethod
    async def send_message(self, client: Any, message: dict[str, Any]) -> None:
        """Send one encoded notification to a client."""

    @abstractmethod
    async def broadcast(self, clients: Iterable[Any], message: dict[str, Any]) -> list[Any]:
        """Send a notification to clients and return clients that failed."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport contract."""

    def __init__(self, server: "NotificationServer | None" = None) -> None:
        super().__init__(server)
        self._server: Any = None

    async def start(self) -> None:
        assert self.server is not None
        self._server = await websockets.serve(
            self._handle_connection,
            self.server.host,
            self.server.port,
            process_request=self.server._process_request,
        )
        self.server.port = self._server.sockets[0].getsockname()[1]
        self.server._server = self._server

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            if self.server is not None:
                self.server._server = None

    def on_connect(self, client_id: str, client: ServerConnection) -> None:
        return None

    def on_disconnect(self, client_id: str, client: ServerConnection) -> None:
        return None

    async def send_message(self, client: ServerConnection, message: dict[str, Any]) -> None:
        await client.send(json.dumps(message))

    async def broadcast(self, clients: Iterable[ServerConnection], message: dict[str, Any]) -> list[ServerConnection]:
        client_list = list(clients)
        results = await asyncio.gather(
            *(self.send_message(client, message) for client in client_list),
            return_exceptions=True,
        )
        return [client for client, result in zip(client_list, results) if isinstance(result, Exception)]

    async def _handle_connection(self, websocket: ServerConnection) -> None:
        assert self.server is not None
        query = parse_qs(urlsplit(websocket.request.path).query)
        client_id = query.get("client_id", [str(uuid.uuid4())])[0]
        self.server._register_connection(client_id, websocket)
        self.on_connect(client_id, websocket)
        if self.server._redis is not None:
            await self.server._restore_channels(client_id)
        try:
            async for raw_message in websocket:
                await self.server._handle_message(raw_message, client_id)
        except websockets.ConnectionClosed:
            pass
        finally:
            self.on_disconnect(client_id, websocket)
            await self.server._on_disconnect(client_id)


class NotificationServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765, redis_url: str | None = None,
                 database_url: str | None = None, transport: BaseTransport | None = None) -> None:
        self.host, self.port = host, port
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        self.database_url = database_url or os.getenv("DATABASE_URL", ":memory:")
        self.clients: dict[str, Any] = {}
        self.channels: dict[str, set[str]] = {}
        self._client_channels: dict[str, set[str]] = {}
        self._server: Any = None
        self._redis: redis.Redis | None = None
        self._pubsub: Any = None
        self._broker_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None
        self._local_queue: asyncio.Queue[str] | None = None
        self.rate_limit = self._positive_int_env("RATE_LIMIT", 100)
        self.message_ttl_days = self._positive_int_env("MESSAGE_TTL_DAYS", 7)
        self._local_rate_limits: dict[str, tuple[int, float]] = {}
        self.store = MessageStore(self.database_url)
        self.transport = transport or self._transport_from_config()
        self.transport.attach(self)

    @staticmethod
    def _transport_from_config() -> BaseTransport:
        transport_name = os.getenv("TRANSPORT", "websocket").strip().lower()
        if transport_name in {"websocket", "websockets", "ws"}:
            return WebSocketTransport()
        raise ValueError(f"unsupported transport: {transport_name}")

    @staticmethod
    def _positive_int_env(name: str, default: int) -> int:
        try:
            value = int(os.getenv(name, str(default)))
        except ValueError:
            return default
        return value if value > 0 else default

    @property
    def client_count(self) -> int:
        return len(self.clients)

    async def start(self) -> "NotificationServer":
        await self.store.start()
        self._redis = redis.Redis.from_url(self.redis_url, decode_responses=True)
        try:
            await self._redis.ping()
            self._pubsub = self._redis.pubsub()
            await self._pubsub.subscribe(REDIS_CHANNEL)
            self._broker_task = asyncio.create_task(self._redis_reader())
        except Exception as error:
            LOGGER.warning("Redis unavailable, using local broker: %s", error)
            await self._redis.aclose()
            self._redis = None
            self._local_queue = asyncio.Queue()
            LocalBroker.subscribers.add(self._local_queue)
            self._broker_task = asyncio.create_task(self._local_reader())
        await self.store.cleanup(self._cleanup_cutoff())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        await self.transport.start()
        return self

    async def stop(self) -> None:
        await self.transport.stop()
        if self._broker_task:
            self._broker_task.cancel()
            await asyncio.gather(self._broker_task, return_exceptions=True)
            self._broker_task = None
        if self._cleanup_task:
            self._cleanup_task.cancel()
            await asyncio.gather(self._cleanup_task, return_exceptions=True)
            self._cleanup_task = None
        if self._local_queue is not None:
            LocalBroker.subscribers.discard(self._local_queue)
            self._local_queue = None
        if self._pubsub is not None:
            await self._pubsub.aclose()
            self._pubsub = None
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
        await self.store.close()

    async def _publish(self, message: dict[str, Any], channel: str | None) -> None:
        message["channel"] = channel
        encoded = json.dumps(message)
        if self._redis is not None:
            await self._redis.publish(REDIS_CHANNEL, encoded)
        else:
            await LocalBroker.publish(encoded)

    async def _redis_reader(self) -> None:
        assert self._pubsub is not None
        async for item in self._pubsub.listen():
            if item["type"] == "message":
                await self._deliver(json.loads(item["data"]))

    async def _local_reader(self) -> None:
        assert self._local_queue is not None
        while True:
            await self._deliver(json.loads(await self._local_queue.get()))

    async def _cleanup_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(3600)
                await self.store.cleanup(self._cleanup_cutoff())
        except asyncio.CancelledError:
            raise

    def _cleanup_cutoff(self) -> str:
        cutoff = datetime.now(timezone.utc).timestamp() - self.message_ttl_days * 86400
        return datetime.fromtimestamp(cutoff, timezone.utc).isoformat().replace("+00:00", "Z")

    async def _deliver(self, envelope: dict[str, Any]) -> None:
        message = envelope["message"]
        target_id = envelope.get("target_id")
        channel = envelope.get("channel")
        if target_id:
            clients = [self.clients[target_id]] if target_id in self.clients else []
        elif isinstance(channel, str):
            ids = self.channels.get(channel, set())
            clients = [self.clients[client_id] for client_id in ids if client_id in self.clients]
        else:
            clients = list(self.clients.values())
        await self._send_to(clients, message)

    async def broadcast(self, payload: dict[str, Any], message_type: str = "broadcast") -> None:
        if message_type not in SUPPORTED_TYPES:
            raise ValueError(f"unsupported message type: {message_type}")
        sent = self._message(message_type, payload)
        await self.store.add(payload.get("channel") if isinstance(payload.get("channel"), str) else None,
                             message_type, payload, sent["timestamp"])
        await self._publish({"message": sent}, payload.get("channel"))

    async def send_direct(self, client_id: str, payload: dict[str, Any]) -> None:
        sent = self._message("direct", payload)
        await self.store.add(payload.get("channel") if isinstance(payload.get("channel"), str) else None,
                             "direct", payload, sent["timestamp"])
        await self._publish({"message": sent, "target_id": client_id}, payload.get("channel"))

    def _register_connection(self, client_id: str, client: Any) -> None:
        self.clients[client_id] = client
        self._client_channels[client_id] = set()

    async def _restore_channels(self, client_id: str) -> None:
        if self._redis is not None:
            saved_channels = await self._redis.smembers(CLIENT_PREFIX + client_id)
            for channel in saved_channels:
                self.channels.setdefault(channel, set()).add(client_id)
                self._client_channels[client_id].add(channel)

    async def _on_disconnect(self, client_id: str) -> None:
        self.clients.pop(client_id, None)
        for channel in self._client_channels.pop(client_id, set()):
            await self._unsubscribe(client_id, channel)

    async def _handle_connection(self, websocket: ServerConnection) -> None:
        """Compatibility entry point for code that used the old callback."""
        if isinstance(self.transport, WebSocketTransport):
            await self.transport._handle_connection(websocket)

    async def _handle_message(self, raw_message: str, client_id: str | None = None) -> None:
        try:
            message = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(message, dict):
            return
        message_type, payload = message.get("type"), message.get("payload", {})
        if message_type not in SUPPORTED_TYPES or not isinstance(payload, dict):
            return
        if client_id is not None and not await self._allow_message(client_id):
            client = self.clients.get(client_id)
            if client is not None:
                await self.transport.send_message(client, self._message("error", {"error": "rate limit exceeded"}))
            return
        channel = message.get("channel", payload.get("channel"))
        if message_type in {"subscribe", "unsubscribe"}:
            if client_id is None or not isinstance(channel, str) or not channel:
                return
            if message_type == "subscribe":
                self.channels.setdefault(channel, set()).add(client_id)
                self._client_channels.setdefault(client_id, set()).add(channel)
                if self._redis is not None:
                    await self._redis.sadd(CHANNEL_PREFIX + channel, client_id)
                    await self._redis.sadd(CLIENT_PREFIX + client_id, channel)
            else:
                await self._unsubscribe(client_id, channel)
            return
        if isinstance(channel, str) and "channel" not in payload:
            payload = {**payload, "channel": channel}
        if message_type == "direct":
            target_id = payload.get("client_id", payload.get("target_id"))
            if isinstance(target_id, str):
                direct_payload = {key: value for key, value in payload.items() if key not in {"client_id", "target_id"}}
                if isinstance(channel, str):
                    subscribed = target_id in self.channels.get(channel, set())
                    if self._redis is not None:
                        subscribed = bool(await self._redis.sismember(CHANNEL_PREFIX + channel, target_id))
                    if not subscribed:
                        return
                await self.send_direct(target_id, direct_payload)
        else:
            await self.broadcast(payload, message_type)

    async def _allow_message(self, client_id: str) -> bool:
        if self._redis is not None:
            key = RATE_LIMIT_PREFIX + client_id
            try:
                count = await self._redis.incr(key)
                if count == 1:
                    await self._redis.expire(key, 60)
                return count <= self.rate_limit
            except Exception as error:
                LOGGER.warning("Redis rate limiter unavailable, using local limiter: %s", error)
        now = asyncio.get_running_loop().time()
        count, started = self._local_rate_limits.get(client_id, (0, now))
        if now - started >= 60:
            count, started = 0, now
        count += 1
        self._local_rate_limits[client_id] = (count, started)
        return count <= self.rate_limit

    async def _unsubscribe(self, client_id: str, channel: str) -> None:
        self._client_channels.get(client_id, set()).discard(channel)
        subscribers = self.channels.get(channel)
        if subscribers is not None:
            subscribers.discard(client_id)
            if not subscribers:
                self.channels.pop(channel, None)
        if self._redis is not None:
            await self._redis.srem(CHANNEL_PREFIX + channel, client_id)
            await self._redis.srem(CLIENT_PREFIX + client_id, channel)

    async def _send_to(self, clients: list[Any], message: dict[str, Any]) -> None:
        failed = await self.transport.broadcast(clients, message)
        for client in failed:
            if isinstance(client, Exception):
                continue
            client_id = next((key for key, value in self.clients.items() if value is client), None)
            if client_id is not None:
                self.clients.pop(client_id, None)

    @staticmethod
    def _message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"type": message_type, "payload": payload, "timestamp": timestamp()}

    async def _process_request(self, _connection: ServerConnection, request: Any) -> Response | None:
        # Let already-queued client messages run before reporting connection state.
        await asyncio.sleep(0)
        parsed = urlsplit(request.path)
        path = parsed.path
        if path == "/health":
            body = json.dumps({"status": "ok", "connected_clients": self.client_count}).encode()
        elif path == "/messages":
            query = parse_qs(parsed.query)
            try:
                limit = min(max(int(query.get("limit", [50])[0]), 1), 1000)
                offset = max(int(query.get("offset", [0])[0]), 0)
            except ValueError:
                return Response(400, "Bad Request", Headers({"Content-Length": "0"}), b"")
            body = json.dumps({"messages": await self.store.list(limit, offset)}).encode()
        elif path == "/history":
            query = parse_qs(parsed.query)
            channel = query.get("channel", [""])[0]
            if not channel:
                return Response(400, "Bad Request", Headers({"Content-Length": "0"}), b"")
            try:
                limit = min(max(int(query.get("limit", [50])[0]), 1), 1000)
            except ValueError:
                return Response(400, "Bad Request", Headers({"Content-Length": "0"}), b"")
            messages, has_more = await self.store.history(channel, query.get("since", [None])[0], limit)
            body = json.dumps({"messages": messages, "has_more": has_more}).encode()
        elif path == "/channels":
            body = json.dumps({"channels": [{"name": name, "subscriber_count": len(subscribers)} for name, subscribers in sorted(self.channels.items()) if subscribers]}).encode()
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            name = unquote(path[len("/channels/") : -len("/subscribers")]).rstrip("/")
            if not name:
                return None
            body = json.dumps({"channel": name, "subscribers": sorted(self.channels.get(name, set()))}).encode()
        else:
            return None
        return Response(200, "OK", Headers({"Content-Type": "application/json", "Content-Length": str(len(body))}), body)

async def serve(host: str = "127.0.0.1", port: int = 8765) -> NotificationServer:
    return await NotificationServer(host, port).start()


async def main() -> None:
    server = await serve()
    LOGGER.info("notification server listening on %s:%s", server.host, server.port)
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
