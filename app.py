"""Async WebSocket notification server with a small HTTP health endpoint."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
import os
import sqlite3
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import redis.asyncio as redis
from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response


SUPPORTED_MESSAGE_TYPES = frozenset({"broadcast", "direct", "system", "subscribe", "unsubscribe"})
REDIS_CHANNEL = "notifications:messages"
REDIS_CLIENTS_KEY = "notifications:clients"
REDIS_RATE_LIMIT_KEY = "notifications:rate-limit"


class BaseTransport(ABC):
    """Connection mechanism used by :class:`NotificationServer`."""

    def __init__(self) -> None:
        self.server: NotificationServer | None = None

    def bind(self, server: NotificationServer) -> None:
        self.server = server

    async def start(self, host: str, port: int) -> Any:
        raise NotImplementedError("this transport does not provide a listener")

    async def stop(self) -> None:
        pass

    @abstractmethod
    async def on_connect(self, client: Any) -> None:
        """Record a newly connected client."""

    @abstractmethod
    async def on_disconnect(self, client: Any) -> None:
        """Release resources associated with a disconnected client."""

    @abstractmethod
    async def send_message(self, client: Any, message: dict[str, Any]) -> None:
        """Send one notification to a client."""

    @abstractmethod
    async def broadcast(self, clients: list[Any], message: dict[str, Any]) -> list[Any]:
        """Send one notification to a set of clients."""


class WebSocketTransport(BaseTransport):
    """The default WebSocket implementation of the notification transport."""

    def __init__(self) -> None:
        super().__init__()
        self._server: Server | None = None
        self._connections: set[ServerConnection] = set()

    async def start(self, host: str, port: int) -> Server:
        if self.server is None:
            raise RuntimeError("transport is not bound to a notification server")
        self._server = await serve(
            self._handle_client,
            host,
            port,
            process_request=self.server._handle_http_request,
        )
        return self._server

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def on_connect(self, client: Any) -> None:
        self._connections.add(client)

    async def on_disconnect(self, client: Any) -> None:
        self._connections.discard(client)

    async def send_message(self, client: Any, message: dict[str, Any]) -> None:
        await client.send(json.dumps(message))

    async def broadcast(self, clients: list[Any], message: dict[str, Any]) -> list[Any]:
        return await asyncio.gather(
            *(self.send_message(client, message) for client in clients), return_exceptions=True
        )

    async def _handle_client(self, websocket: ServerConnection) -> None:
        if self.server is None:
            return
        await self.server._on_connect(websocket)
        try:
            async for raw_message in websocket:
                await self.server._handle_message(websocket, raw_message)
        finally:
            await self.server._on_disconnect(websocket)


class NotificationServer:
    """Manage notifications independently of the selected client transport."""

    def __init__(
        self,
        redis_url: str | None = None,
        database_url: str | None = None,
        redis_client: Any | None = None,
        transport: BaseTransport | None = None,
    ) -> None:
        self.clients: dict[str, Any] = {}
        self.channels: dict[str, set[str]] = {}
        # An asyncio lock only coordinates tasks on one loop. This lock also
        # protects registry inspection or mutation when called from a thread.
        self._clients_lock = threading.RLock()
        self._server: Any | None = None
        self.transport = transport or self._transport_from_config()
        self.transport.bind(self)
        self._redis_url = redis_url if redis_url is not None else os.environ.get("REDIS_URL")
        self._redis = redis_client
        self._owns_redis = redis_client is None and self._redis_url is not None
        self._pubsub: Any | None = None
        self._subscriber_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None
        self._subscription_ready = asyncio.Event()
        self._rate_limit = self._environment_int("RATE_LIMIT", 100, minimum=1)
        self._message_ttl_days = self._environment_int("MESSAGE_TTL_DAYS", 7, minimum=0)
        self._local_rate_limits: dict[str, tuple[int, float]] = {}
        self._database_lock = threading.RLock()
        self._database = sqlite3.connect(
            self._sqlite_path(database_url if database_url is not None else os.environ.get("DATABASE_URL")),
            check_same_thread=False,
        )
        self._database.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                channel TEXT,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        self._database.commit()

    @property
    def client_count(self) -> int:
        with self._clients_lock:
            return len(self.clients)

    @staticmethod
    def _transport_from_config() -> BaseTransport:
        transport_name = os.environ.get("TRANSPORT", "websocket").lower()
        if transport_name == "websocket":
            return WebSocketTransport()
        raise ValueError(f"unsupported transport: {transport_name}")

    async def start(self, host: str = "127.0.0.1", port: int = 8765) -> Any:
        if self._server is not None:
            raise RuntimeError("server is already running")
        await self._start_subscriber()
        await self._cleanup_expired_messages()
        self._cleanup_task = asyncio.create_task(self._cleanup_messages_periodically())
        self._server = await self.transport.start(host, port)
        return self._server

    async def stop(self) -> None:
        await self.transport.stop()
        self._server = None
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        if self._subscriber_task is not None:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
            self._subscriber_task = None
        if self._pubsub is not None:
            await self._pubsub.aclose()
            self._pubsub = None
        if self._owns_redis and self._redis is not None:
            await self._redis.aclose()
            self._redis = None
        with self._database_lock:
            self._database.close()

    async def _handle_http_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        parsed = urlparse(request.path)
        if parsed.path == "/health":
            body = json.dumps({"connected_clients": self.client_count}).encode("utf-8")
        elif parsed.path == "/channels":
            with self._clients_lock:
                channels = [
                    {"name": name, "subscriber_count": len(subscribers)}
                    for name, subscribers in sorted(self.channels.items())
                ]
            body = json.dumps({"channels": channels}).encode("utf-8")
        elif parsed.path.startswith("/channels/") and parsed.path.endswith("/subscribers"):
            name = parsed.path[len("/channels/") : -len("/subscribers")].rstrip("/")
            if not name:
                return None
            with self._clients_lock:
                subscribers = sorted(self.channels.get(name, set()))
            body = json.dumps({"channel": name, "subscribers": subscribers}).encode("utf-8")
        elif parsed.path == "/messages":
            try:
                params = parse_qs(parsed.query)
                limit = int(params.get("limit", ["50"])[0])
                offset = int(params.get("offset", ["0"])[0])
                if limit < 0 or offset < 0:
                    raise ValueError
            except ValueError:
                return self._json_response(400, "Bad Request", {"detail": "limit and offset must be non-negative integers"})
            body = json.dumps({"messages": self._history(limit, offset)}).encode("utf-8")
        elif parsed.path == "/history":
            try:
                params = parse_qs(parsed.query)
                channel = params["channel"][0]
                if not self._is_valid_channel(channel):
                    raise ValueError
                since = self._parse_timestamp(params.get("since", [None])[0])
                limit = int(params.get("limit", ["50"])[0])
                if limit < 1:
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                return self._json_response(
                    400,
                    "Bad Request",
                    {"detail": "channel, since, and a positive limit are required"},
                )
            messages, has_more = self._channel_history(channel, since, limit)
            body = json.dumps({"messages": messages, "has_more": has_more}).encode("utf-8")
        else:
            return None
        return self._response(200, "OK", body)

    async def _on_connect(self, client: Any) -> None:
        client_id = str(uuid4())
        with self._clients_lock:
            self.clients[client_id] = client
        await self.transport.on_connect(client)
        await self._store_client(client_id)
        await self._send_to(
            client,
            self._message("system", {"event": "connected", "client_id": client_id}),
        )

    async def _on_disconnect(self, client: Any) -> None:
        client_id = self._client_id_for(client)
        if client_id is None:
            return
        with self._clients_lock:
            self._remove_client(client_id)
        await self.transport.on_disconnect(client)
        await self._delete_client(client_id)

    async def _handle_message(
        self, sender: Any, raw_message: str | bytes) -> None:
        client_id = self._client_id_for(sender)
        if client_id is not None and not await self._within_rate_limit(client_id):
            await self._send_error(sender, "rate limit exceeded")
            return
        if isinstance(raw_message, bytes):
            await self._send_error(sender, "messages must be text JSON")
            return
        try:
            incoming = json.loads(raw_message)
            message_type = incoming["type"]
            if message_type not in SUPPORTED_MESSAGE_TYPES:
                raise ValueError
            channel = incoming.get("channel")
            if message_type in {"subscribe", "unsubscribe"}:
                if not self._is_valid_channel(channel):
                    raise ValueError
                payload = incoming.get("payload", {})
                if not isinstance(payload, dict):
                    raise ValueError
            else:
                payload = incoming["payload"]
                if not isinstance(payload, dict) or (channel is not None and not self._is_valid_channel(channel)):
                    raise ValueError
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            await self._send_error(sender, "invalid message format")
            return

        if message_type == "subscribe":
            if client_id is not None:
                with self._clients_lock:
                    self.channels.setdefault(channel, set()).add(client_id)
                await self._store_client(client_id)
            return
        if message_type == "unsubscribe":
            if client_id is not None:
                with self._clients_lock:
                    subscribers = self.channels.get(channel)
                    if subscribers is not None:
                        subscribers.discard(client_id)
                        if not subscribers:
                            self.channels.pop(channel, None)
                await self._store_client(client_id)
            return

        if channel is not None:
            await self.broadcast(payload, message_type, channel)
            return

        if message_type == "direct":
            client_id = payload.get("client_id")
            if not isinstance(client_id, str):
                await self._send_error(sender, "direct messages require payload.client_id")
                return
            if not await self._client_exists(client_id):
                await self._send_error(sender, "recipient not connected")
                return
            await self._publish(self._message(message_type, payload))
            return

        await self.broadcast(payload, message_type)

    async def broadcast(
        self, payload: dict[str, Any], message_type: str = "broadcast", channel: str | None = None
    ) -> None:
        """Send a supported notification to all clients or channel subscribers."""
        if message_type not in SUPPORTED_MESSAGE_TYPES - {"subscribe", "unsubscribe"}:
            raise ValueError(f"unsupported message type: {message_type}")
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary")
        if channel is not None and not self._is_valid_channel(channel):
            raise ValueError("channel must be a non-empty string")
        message = self._message(message_type, payload, channel)
        await self._publish(message)

    async def _publish(self, message: dict[str, Any]) -> None:
        self._persist(message)
        if self._redis is None:
            await self._deliver(message)
            return
        await self._redis.publish(REDIS_CHANNEL, json.dumps(message))

    async def _deliver(self, message: dict[str, Any]) -> None:
        with self._clients_lock:
            channel = message.get("channel")
            if message["type"] == "direct":
                target = message["payload"].get("client_id")
                recipients = [self.clients[target]] if target in self.clients else []
            elif channel is None:
                recipients = list(self.clients.values())
            else:
                recipients = [
                    self.clients[client_id]
                    for client_id in self.channels.get(channel, set())
                    if client_id in self.clients
                ]
        results = await self.transport.broadcast(recipients, message)
        if any(isinstance(result, Exception) for result in results):
            await self._remove_closed_clients()

    async def _remove_closed_clients(self) -> None:
        with self._clients_lock:
            stale_ids = [
                client_id for client_id, client in self.clients.items() if getattr(client, "closed", False)
            ]
            for client_id in stale_ids:
                self._remove_client(client_id)

    def _client_id_for(self, client: Any) -> str | None:
        with self._clients_lock:
            return next(
                (client_id for client_id, connected_client in self.clients.items() if connected_client is client), None
            )

    def _remove_client(self, client_id: str) -> None:
        self.clients.pop(client_id, None)
        for channel, subscribers in list(self.channels.items()):
            subscribers.discard(client_id)
            if not subscribers:
                self.channels.pop(channel)

    async def _start_subscriber(self) -> None:
        if self._redis is None and self._redis_url is not None:
            self._redis = redis.from_url(self._redis_url, decode_responses=True)
        if self._redis is None:
            return
        self._subscription_ready.clear()
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(REDIS_CHANNEL)
        self._subscriber_task = asyncio.create_task(self._consume_messages())
        self._subscription_ready.set()
        await self._subscription_ready.wait()

    async def _consume_messages(self) -> None:
        assert self._pubsub is not None
        while True:
            message = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                continue
            data = message["data"]
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            await self._deliver(json.loads(data))

    async def _store_client(self, client_id: str) -> None:
        if self._redis is None:
            return
        with self._clients_lock:
            state = {"channels": sorted(channel for channel, clients in self.channels.items() if client_id in clients)}
        await self._redis.hset(REDIS_CLIENTS_KEY, client_id, json.dumps(state))

    async def _delete_client(self, client_id: str) -> None:
        if self._redis is not None:
            await self._redis.hdel(REDIS_CLIENTS_KEY, client_id)

    async def _client_exists(self, client_id: str) -> bool:
        if self._redis is None:
            with self._clients_lock:
                return client_id in self.clients
        return bool(await self._redis.hexists(REDIS_CLIENTS_KEY, client_id))

    async def _within_rate_limit(self, client_id: str) -> bool:
        """Increment the per-client Redis counter and report whether it is allowed."""
        window = int(datetime.now(timezone.utc).timestamp() // 60)
        key = f"{REDIS_RATE_LIMIT_KEY}:{client_id}:{window}"
        if self._redis is not None:
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, 60)
            return count <= self._rate_limit

        # Redis is optional for single-process deployments, so retain the
        # existing no-Redis startup behavior with an equivalent local counter.
        now = asyncio.get_running_loop().time()
        count, expires_at = self._local_rate_limits.get(key, (0, now + 60))
        if expires_at <= now:
            count, expires_at = 0, now + 60
        self._local_rate_limits[key] = (count + 1, expires_at)
        return count < self._rate_limit

    def _persist(self, message: dict[str, Any]) -> None:
        with self._database_lock:
            self._database.execute(
                "INSERT INTO messages (id, channel, type, payload, timestamp) VALUES (?, ?, ?, ?, ?)",
                (message["id"], message.get("channel"), message["type"], json.dumps(message["payload"]), message["timestamp"]),
            )
            self._database.commit()

    def _history(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with self._database_lock:
            rows = self._database.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages ORDER BY timestamp, id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [
            {"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]}
            for row in rows
        ]

    def _channel_history(
        self, channel: str, since: str, limit: int
    ) -> tuple[list[dict[str, Any]], bool]:
        with self._database_lock:
            rows = self._database.execute(
                """
                SELECT id, channel, type, payload, timestamp FROM messages
                WHERE channel = ? AND timestamp >= ?
                ORDER BY timestamp, id LIMIT ?
                """,
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

    async def _cleanup_messages_periodically(self) -> None:
        while True:
            await asyncio.sleep(24 * 60 * 60)
            await self._cleanup_expired_messages()

    async def _cleanup_expired_messages(self) -> None:
        cutoff = datetime.now(timezone.utc).timestamp() - self._message_ttl_days * 24 * 60 * 60
        cutoff_timestamp = datetime.fromtimestamp(cutoff, timezone.utc).isoformat()
        with self._database_lock:
            self._database.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff_timestamp,))
            self._database.commit()

    @staticmethod
    def _sqlite_path(database_url: str | None) -> str:
        if database_url is None:
            return ":memory:"
        if not database_url.startswith("sqlite:///"):
            raise ValueError("DATABASE_URL must use sqlite:///path format")
        return database_url[len("sqlite:///") :]

    @staticmethod
    def _environment_int(name: str, default: int, minimum: int) -> int:
        try:
            value = int(os.environ.get(name, str(default)))
        except ValueError as error:
            raise ValueError(f"{name} must be an integer") from error
        if value < minimum:
            raise ValueError(f"{name} must be at least {minimum}")
        return value

    @staticmethod
    def _parse_timestamp(value: str | None) -> str:
        if not value:
            raise ValueError("timestamp is required")
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        return timestamp.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _response(status: int, reason: str, body: bytes) -> Response:
        return Response(status, reason, Headers([("Content-Type", "application/json"), ("Content-Length", str(len(body)))]), body)

    @classmethod
    def _json_response(cls, status: int, reason: str, payload: dict[str, Any]) -> Response:
        return cls._response(status, reason, json.dumps(payload).encode("utf-8"))

    @staticmethod
    def _is_valid_channel(channel: Any) -> bool:
        return isinstance(channel, str) and bool(channel)

    @staticmethod
    def _message(
        message_type: str, payload: dict[str, Any], channel: str | None = None
    ) -> dict[str, Any]:
        message = {
            "id": str(uuid4()),
            "type": message_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if channel is not None:
            message["channel"] = channel
        return message

    async def _send_to(self, client: Any, message: dict[str, Any]) -> None:
        await self.transport.send_message(client, message)

    async def _send_error(self, client: Any, detail: str) -> None:
        await self._send_to(client, self._message("system", {"event": "error", "detail": detail}))


async def main() -> None:
    server = NotificationServer()
    await server.start()
    print("Notification server listening on ws://127.0.0.1:8765")
    await asyncio.get_running_loop().create_future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
