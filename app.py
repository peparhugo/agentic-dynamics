"""Async WebSocket notification server.

The server exposes a WebSocket endpoint at ``/`` and a small HTTP health
endpoint on the same listening port.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import os
import sqlite3
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

import redis.asyncio as redis
from websockets.asyncio.server import ServerConnection, serve
from websockets.http11 import Headers, Request, Response


_client_ids = itertools.count(1)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _message(
    message_type: str, payload: dict[str, Any], channel: str | None = None
) -> str:
    message = {"type": message_type, "payload": payload, "timestamp": _timestamp()}
    if channel is not None:
        message["channel"] = channel
    return json.dumps(message)


class BaseTransport(ABC):
    """Interface used by the notification server to communicate with clients."""

    def __init__(self, server: "NotificationServer" | None = None) -> None:
        self.server = server
        self.clients: dict[int, Any] = {}

    @abstractmethod
    async def on_connect(self, client_id: int, connection: Any) -> None:
        """Register a newly connected client."""

    @abstractmethod
    async def on_disconnect(self, client_id: int) -> None:
        """Remove a disconnected client."""

    @abstractmethod
    async def send_message(self, client_id: int, message: str) -> None:
        """Send one serialized message to a client."""

    @abstractmethod
    async def broadcast(self, message: str, client_ids: list[int] | None = None) -> None:
        """Send one serialized message to a set of clients."""

    async def start(self) -> Any:
        return None

    async def stop(self) -> None:
        return None

    async def handler(self, connection: Any) -> None:
        raise NotImplementedError


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport."""

    async def on_connect(self, client_id: int, connection: ServerConnection) -> None:
        self.clients[client_id] = connection

    async def on_disconnect(self, client_id: int) -> None:
        self.clients.pop(client_id, None)

    async def send_message(self, client_id: int, message: str) -> None:
        connection = self.clients.get(client_id)
        if connection is not None:
            await connection.send(message)

    async def broadcast(self, message: str, client_ids: list[int] | None = None) -> None:
        ids = list(self.clients) if client_ids is None else client_ids
        await asyncio.gather(
            *(self.send_message(client_id, message) for client_id in ids),
            return_exceptions=True,
        )

    async def handler(self, websocket: ServerConnection) -> None:
        if websocket.request.path != "/":
            await websocket.close(code=1008, reason="WebSocket path must be /")
            return

        client_id = self.server._allocate_client_id()
        await self.on_connect(client_id, websocket)
        await self.server._transport_connected(client_id)
        try:
            async for raw_message in websocket:
                await self.server.handle_message(client_id, raw_message)
        except Exception:
            # Connection errors are expected when a client disappears abruptly.
            pass
        finally:
            await self.on_disconnect(client_id)
            await self.server._transport_disconnected(client_id)

    async def start(self) -> Any:
        return await serve(
            self.handler,
            self.server.host,
            self.server.port,
            process_request=self.server.process_request,
        )


class NotificationServer:
    """Manage notification messages independently of client transport."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        redis_url: str | None = None,
        database_url: str | None = None,
        transport: BaseTransport | None = None,
        rate_limit: int | None = None,
        message_ttl_days: int | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.transport = transport or self._create_transport()
        self.transport.server = self
        self.clients = self.transport.clients
        self.channels: dict[str, set[int]] = {}
        self._client_channels: dict[int, set[str]] = {}
        self._clients_lock = asyncio.Lock()
        self._server: Any = None
        self.redis_url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        self.database_url = database_url or os.environ.get("DATABASE_URL", "sqlite:///messages.db")
        self.rate_limit = self._int_setting("RATE_LIMIT", rate_limit, 100)
        self.message_ttl_days = self._int_setting("MESSAGE_TTL_DAYS", message_ttl_days, 7)
        self.server_id = uuid.uuid4().hex
        self._redis: redis.Redis | None = None
        self._pubsub: Any = None
        self._redis_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None
        self._db: sqlite3.Connection | None = None
        self._db_lock = asyncio.Lock()
        self._next_reserved_client_id: int | None = None
        self._reserved_client_ids_end: int | None = None

    @staticmethod
    def _int_setting(name: str, value: int | None, default: int) -> int:
        if value is not None:
            return value
        try:
            return int(os.environ.get(name, str(default)))
        except ValueError:
            return default

    def _create_transport(self) -> BaseTransport:
        transport_name = os.environ.get("TRANSPORT", "websocket").lower()
        if transport_name in {"websocket", "ws"}:
            return WebSocketTransport(self)
        raise ValueError(f"Unsupported transport: {transport_name}")

    def _allocate_client_id(self) -> int:
        if self._next_reserved_client_id is not None and self._reserved_client_ids_end is not None:
            client_id = self._next_reserved_client_id
            self._next_reserved_client_id += 1
            if self._next_reserved_client_id > self._reserved_client_ids_end:
                self._next_reserved_client_id = None
            return client_id
        return next(_client_ids)

    async def _transport_connected(self, client_id: int) -> None:
        async with self._clients_lock:
            self._client_channels[client_id] = set()
        if self._redis is not None:
            await self._redis.set(f"notification:client:{client_id}", self.server_id, ex=3600)

    async def _transport_disconnected(self, client_id: int) -> None:
        async with self._clients_lock:
            for channel in self._client_channels.pop(client_id, set()):
                subscribers = self.channels.get(channel)
                if subscribers is not None:
                    subscribers.discard(client_id)
                    if not subscribers:
                        self.channels.pop(channel, None)
        if self._redis is not None:
            await self._redis.delete(f"notification:client:{client_id}")

    def _database_path(self) -> str:
        if self.database_url.startswith("sqlite:///"):
            return self.database_url[10:]
        if self.database_url.startswith("sqlite://"):
            return self.database_url[9:]
        return self.database_url

    async def _init_database(self) -> None:
        path = self._database_path()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, type TEXT NOT NULL, "
            "payload TEXT NOT NULL, timestamp TEXT NOT NULL)"
        )
        self._db.commit()

    async def _save_message(self, message: dict[str, Any]) -> None:
        assert self._db is not None
        async with self._db_lock:
            self._db.execute(
                "INSERT INTO messages(channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (message.get("channel"), message["type"], json.dumps(message["payload"]), message["timestamp"]),
            )
            self._db.commit()

    async def _read_messages(self, limit: int, offset: int) -> list[dict[str, Any]]:
        assert self._db is not None
        async with self._db_lock:
            rows = self._db.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        return [
            {"id": row[0], "channel": row[1], "type": row[2],
             "payload": json.loads(row[3]), "timestamp": row[4]}
            for row in rows
        ]

    async def _read_history(
        self, channel: str, since: str | None, limit: int
    ) -> tuple[list[dict[str, Any]], bool]:
        assert self._db is not None
        query = (
            "SELECT id, channel, type, payload, timestamp FROM messages "
            "WHERE channel = ?"
        )
        parameters: list[Any] = [channel]
        if since is not None:
            query += " AND timestamp >= ?"
            parameters.append(since)
        query += " ORDER BY timestamp ASC, id ASC LIMIT ?"
        parameters.append(limit + 1)
        async with self._db_lock:
            rows = self._db.execute(query, parameters).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        return (
            [
                {"id": row[0], "channel": row[1], "type": row[2],
                 "payload": json.loads(row[3]), "timestamp": row[4]}
                for row in rows
            ],
            has_more,
        )

    async def _cleanup_expired_messages(self) -> None:
        assert self._db is not None
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.message_ttl_days))
        cutoff_text = cutoff.isoformat().replace("+00:00", "Z")
        async with self._db_lock:
            self._db.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff_text,))
            self._db.commit()

    async def _expiry_worker(self) -> None:
        try:
            while True:
                await asyncio.sleep(3600)
                await self._cleanup_expired_messages()
        except asyncio.CancelledError:
            raise

    async def _check_rate_limit(self, client_id: int) -> bool:
        if self.rate_limit <= 0 or self._redis is None:
            return True
        bucket = int(datetime.now(timezone.utc).timestamp()) // 60
        key = f"notification:rate:{client_id}:{bucket}"
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, 61)
                result = await pipe.execute()
            return int(result[0]) <= self.rate_limit
        except Exception:
            # Redis is optional for local operation; do not reject messages if it is down.
            return True

    async def _send_rate_limit_error(self, client_id: int) -> None:
        error = {
            "type": "error",
            "payload": {"error": "rate limit exceeded"},
            "timestamp": _timestamp(),
        }
        await self.transport.send_message(client_id, json.dumps(error))

    async def _start_redis(self) -> None:
        try:
            candidate = redis.from_url(self.redis_url, decode_responses=True)
            await candidate.ping()
            self._redis = candidate
            self._pubsub = candidate.pubsub()
            await self._pubsub.subscribe("notifications")
            self._redis_task = asyncio.create_task(self._redis_listener())
        except Exception:
            if 'candidate' in locals():
                await candidate.close()

    async def _redis_listener(self) -> None:
        assert self._pubsub is not None
        try:
            async for item in self._pubsub.listen():
                if item.get("type") != "message":
                    continue
                try:
                    envelope = json.loads(item["data"])
                except (TypeError, json.JSONDecodeError):
                    continue
                if envelope.get("target_server") not in (None, self.server_id):
                    continue
                message = envelope.get("message")
                if isinstance(message, dict):
                    await self._deliver(message, envelope.get("target_client_id"))
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    async def _publish(self, message: dict[str, Any], target_client_id: int | None = None) -> None:
        envelope: dict[str, Any] = {"message": message, "target_client_id": target_client_id}
        if target_client_id is not None and self._redis is not None:
            try:
                target_server = await self._redis.get(f"notification:client:{target_client_id}")
            except Exception:
                target_server = self.server_id
            if target_server is None:
                return
            envelope["target_server"] = target_server
        if self._redis is not None:
            try:
                await self._redis.publish("notifications", json.dumps(envelope))
                return
            except Exception:
                pass
        await self._deliver(message, target_client_id)

    async def _deliver(self, message: dict[str, Any], target_client_id: int | None = None) -> None:
        channel = message.get("channel")
        async with self._clients_lock:
            if target_client_id is not None:
                recipient_ids = [target_client_id] if target_client_id in self.clients else []
                if channel is not None and target_client_id not in self.channels.get(channel, set()):
                    recipient_ids = []
            elif channel is None:
                recipient_ids = list(self.clients)
            else:
                recipient_ids = [
                    client_id
                    for client_id in self.channels.get(channel, set())
                    if client_id in self.clients
                ]
        if recipient_ids:
            serialized = json.dumps(message)
            if target_client_id is not None:
                await self.transport.send_message(target_client_id, serialized)
            else:
                await self.transport.broadcast(serialized, recipient_ids)

    @property
    def connected_client_count(self) -> int:
        """Return the count for callers outside the event loop lock context."""
        return len(self.clients)

    async def process_request(
        self, _connection: ServerConnection, request: Request
    ) -> Response | None:
        if request.path == "/health":
            body = json.dumps(
                {"status": "ok", "connected_clients": self.connected_client_count}
            ).encode()
            headers = Headers([
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
            ])
            return Response(200, "OK", headers, body)
        if request.path == "/channels":
            async with self._clients_lock:
                channels = {
                    name: len(subscribers)
                    for name, subscribers in self.channels.items()
                    if subscribers
                }
            return self._json_response({"channels": channels})
        if urlsplit(request.path).path == "/history":
            query = parse_qs(urlsplit(request.path).query)
            channel = query.get("channel", [None])[0]
            if not channel:
                return self._json_response({"error": "channel is required"}, 400, "Bad Request")
            since = query.get("since", [None])[0]
            if since is not None:
                try:
                    datetime.fromisoformat(since.replace("Z", "+00:00"))
                except ValueError:
                    return self._json_response({"error": "invalid since timestamp"}, 400, "Bad Request")
            try:
                limit = min(max(int(query.get("limit", ["50"])[0]), 0), 1000)
            except ValueError:
                return self._json_response({"error": "invalid pagination"}, 400, "Bad Request")
            messages, has_more = await self._read_history(channel, since, limit)
            return self._json_response({"messages": messages, "has_more": has_more})
        if urlsplit(request.path).path == "/messages":
            query = parse_qs(urlsplit(request.path).query)
            try:
                limit = min(max(int(query.get("limit", ["50"])[0]), 0), 1000)
                offset = max(int(query.get("offset", ["0"])[0]), 0)
            except ValueError:
                return self._json_response({"error": "invalid pagination"}, 400, "Bad Request")
            return self._json_response({"messages": await self._read_messages(limit, offset)})
        channel_prefix = "/channels/"
        if request.path.startswith(channel_prefix) and request.path.endswith(
            "/subscribers"
        ):
            encoded_name = request.path[len(channel_prefix) : -len("/subscribers")]
            if not encoded_name or "/" in encoded_name:
                return self._json_response({"error": "invalid channel"}, 400, "Bad Request")
            channel = unquote(encoded_name)
            async with self._clients_lock:
                subscribers = sorted(self.channels.get(channel, set()))
            return self._json_response(
                {"channel": channel, "subscribers": subscribers}
            )
        return None

    @staticmethod
    def _json_response(
        value: dict[str, Any], status_code: int = 200, reason: str = "OK"
    ) -> Response:
        body = json.dumps(value).encode()
        return Response(
            status_code,
            reason,
            Headers([
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
            ]),
            body,
        )

    async def handler(self, websocket: ServerConnection) -> None:
        await self.transport.handler(websocket)

    async def handle_message(self, sender_id: int, raw_message: str) -> None:
        try:
            incoming = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            return

        if not isinstance(incoming, dict):
            return
        if not await self._check_rate_limit(sender_id):
            await self._send_rate_limit_error(sender_id)
            return
        message_type = incoming.get("type")
        payload = incoming.get("payload")
        if message_type in {"subscribe", "unsubscribe"}:
            channel = incoming.get("channel")
            if channel is None and isinstance(payload, dict):
                channel = payload.get("channel")
            if not isinstance(channel, str) or not channel:
                return
            async with self._clients_lock:
                if sender_id not in self.clients:
                    return
                if message_type == "subscribe":
                    self.channels.setdefault(channel, set()).add(sender_id)
                    self._client_channels.setdefault(sender_id, set()).add(channel)
                else:
                    subscribers = self.channels.get(channel)
                    if subscribers is not None:
                        subscribers.discard(sender_id)
                        if not subscribers:
                            self.channels.pop(channel, None)
                    self._client_channels.setdefault(sender_id, set()).discard(channel)
            if self._redis is not None:
                subscriptions_key = f"notification:subscriptions:{sender_id}"
                if message_type == "subscribe":
                    await self._redis.sadd(subscriptions_key, channel)
                else:
                    await self._redis.srem(subscriptions_key, channel)
                await self._redis.expire(subscriptions_key, 3600)
            return

        if message_type not in {"broadcast", "direct", "system"} or not isinstance(
            payload, dict
        ):
            return

        channel = incoming.get("channel")
        if channel is None:
            channel = payload.get("channel")
        if channel is not None and not isinstance(channel, str):
            return

        if message_type == "direct":
            target_id = payload.get("client_id")
            if not isinstance(target_id, int):
                return
            async with self._clients_lock:
                target = self.clients.get(target_id)
                subscribed = channel is None or target_id in self.channels.get(channel, set())
            if target is None or subscribed:
                message = {"type": "direct", "payload": payload, "timestamp": _timestamp()}
                if channel is not None:
                    message["channel"] = channel
                await self._save_message(message)
                await self._publish(message, target_id)
            return

        message = {"type": message_type, "payload": payload, "timestamp": _timestamp()}
        if channel is not None:
            message["channel"] = channel
        await self._save_message(message)
        await self._publish(message)

    async def broadcast(
        self, message: str | dict[str, Any], channel: str | None = None
    ) -> None:
        """Send a message to every client, or only to subscribers of a channel."""
        if isinstance(message, str):
            message_data = json.loads(message)
        else:
            message_data = message
        channel = message_data.get("channel", channel)
        if channel is not None:
            message_data["channel"] = channel
        await self._save_message(message_data)
        await self._publish(message_data)

    async def start(self) -> Any:
        await self._init_database()
        await self._cleanup_expired_messages()
        self._cleanup_task = asyncio.create_task(self._expiry_worker())
        await self._start_redis()
        if self._redis is not None:
            end = int(await self._redis.incrby("notification:next_client_id", 1000))
            self._next_reserved_client_id = end - 999
            self._reserved_client_ids_end = end
        self._server = await self.transport.start()
        return self._server

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        await self.transport.stop()
        if self._redis_task is not None:
            self._redis_task.cancel()
            await asyncio.gather(self._redis_task, return_exceptions=True)
            self._redis_task = None
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            await asyncio.gather(self._cleanup_task, return_exceptions=True)
            self._cleanup_task = None
        if self._pubsub is not None:
            await self._pubsub.close()
            self._pubsub = None
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
        if self._db is not None:
            self._db.close()
            self._db = None

    async def run(self) -> None:
        await self.start()
        await asyncio.Future()


async def main() -> None:
    server = NotificationServer()
    try:
        await server.run()
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
