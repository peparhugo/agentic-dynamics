"""Redis-backed asynchronous WebSocket notification server."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import redis.asyncio as redis
from websockets.asyncio.server import Request, ServerConnection
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Response

from transport import BaseTransport, WebSocketTransport

LOGGER = logging.getLogger(__name__)
MESSAGE_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
REDIS_CHANNEL = "notifications:messages"


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class NotificationServer:
    """Route messages through Redis and retain them in SQLite."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        redis_url: str | None = None,
        database_url: str | None = None,
        transport: BaseTransport | None = None,
    ) -> None:
        self.host, self.port = host, port
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///messages.db")
        transport_name = os.getenv("TRANSPORT", "websocket").lower()
        if transport is not None:
            self.transport = transport
        elif transport_name in {"websocket", "ws"}:
            self.transport = WebSocketTransport(port)
        else:
            raise ValueError(f"Unsupported transport: {transport_name}")
        self.clients: dict[str, ServerConnection] = {}
        self.channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()
        self._server: Any = None
        self._redis: redis.Redis | None = None
        self._pubsub: Any = None
        self._redis_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None
        self._instance_id = str(uuid.uuid4())
        self._db_lock = threading.Lock()
        self._db_path = self._sqlite_path(self.database_url)
        self._db_uri = self._db_path.startswith("file:")
        self._db_keeper: sqlite3.Connection | None = None
        if self._db_path == ":memory:":
            self._db_path = f"file:notifications-{self._instance_id}?mode=memory&cache=shared"
            self._db_uri = True
            self._db_keeper = sqlite3.connect(self._db_path, uri=True, check_same_thread=False)
        self.rate_limit = max(0, int(os.getenv("RATE_LIMIT", "100")))
        self.message_ttl_days = max(0, float(os.getenv("MESSAGE_TTL_DAYS", "7")))
        self._rate_windows: dict[str, tuple[int, float]] = {}
        with self._connect_db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT NOT NULL,
                type TEXT NOT NULL, payload TEXT NOT NULL, timestamp TEXT NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_messages_channel_timestamp ON messages(channel, timestamp)")

    def _connect_db(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, uri=self._db_uri)

    @staticmethod
    def _sqlite_path(url: str) -> str:
        if url == ":memory:" or url.startswith("file:"):
            return url
        if url.startswith("sqlite:////"):
            return url[len("sqlite://") :]
        if url.startswith("sqlite:///"):
            return url[len("sqlite:///") :]
        parsed = urlparse(url)
        if parsed.scheme in ("", "sqlite"):
            path = parsed.path if parsed.scheme else url
            if parsed.netloc and parsed.scheme == "sqlite":
                path = f"//{parsed.netloc}{path}"
            return path.lstrip("/") if path.startswith("///") else (path or ":memory:")
        raise ValueError("DATABASE_URL must be a SQLite URL")

    @property
    def bound_port(self) -> int:
        return self.transport.bound_port

    async def client_count(self) -> int:
        with self._lock:
            return len(self.clients)

    def _make_message(self, message_type: str, payload: dict[str, Any]) -> str:
        return json.dumps({"type": message_type, "payload": payload, "timestamp": timestamp()})

    def _persist(self, channel: str | None, message: dict[str, Any]) -> None:
        with self._db_lock, self._connect_db() as db:
            db.execute(
                "INSERT INTO messages(channel,type,payload,timestamp) VALUES (?,?,?,?)",
                (channel or "", message["type"], json.dumps(message["payload"]), message["timestamp"]),
            )

    def _history(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with self._db_lock, self._connect_db() as db:
            rows = db.execute(
                "SELECT id,channel,type,payload,timestamp FROM messages ORDER BY id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [{"id": i, "channel": c, "type": t, "payload": json.loads(p), "timestamp": ts}
                for i, c, t, p, ts in rows]

    def _channel_history(self, channel: str, since: str | None, limit: int) -> tuple[list[dict[str, Any]], bool]:
        conditions = ["channel = ?"]
        values: list[Any] = [channel]
        if since is not None:
            conditions.append("timestamp >= ?")
            values.append(since)
        values.append(limit + 1)
        with self._db_lock, self._connect_db() as db:
            rows = db.execute(
                f"SELECT id,channel,type,payload,timestamp FROM messages WHERE {' AND '.join(conditions)} "
                "ORDER BY timestamp ASC, id ASC LIMIT ?",
                values,
            ).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        return ([{"id": i, "channel": c, "type": t, "payload": json.loads(p), "timestamp": ts}
                 for i, c, t, p, ts in rows], has_more)

    def _cleanup_expired(self) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.message_ttl_days)).isoformat()
        with self._db_lock, self._connect_db() as db:
            db.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff,))

    async def _cleanup_loop(self) -> None:
        try:
            while True:
                await asyncio.to_thread(self._cleanup_expired)
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise

    async def _allow_message(self, client_id: str) -> bool:
        if self.rate_limit == 0:
            return False
        if self._redis:
            key = f"notifications:rate:{client_id}"
            try:
                count = await self._redis.incr(key)
                if count == 1:
                    await self._redis.expire(key, 60)
                return count <= self.rate_limit
            except redis.RedisError:
                LOGGER.warning("Redis rate limiter unavailable; using local limiter")
        now = time.monotonic()
        count, started = self._rate_windows.get(client_id, (0, now))
        if now - started >= 60:
            count, started = 0, now
        count += 1
        self._rate_windows[client_id] = (count, started)
        return count <= self.rate_limit

    def _json_response(self, value: Any, status: int = 200, reason: str = "OK") -> Response:
        body = json.dumps(value).encode()
        return Response(status, reason, Headers({"Content-Type": "application/json", "Content-Length": str(len(body))}), body)

    async def _process_request(self, _connection: ServerConnection, request: Request) -> Response | None:
        path, _, query = request.path.partition("?")
        if request.headers.get("Connection", "").lower() == "upgrade":
            return None
        if path == "/health":
            return self._json_response({"connected_clients": await self.client_count()})
        if path == "/messages":
            params = parse_qs(query)
            try:
                limit = max(0, min(int(params.get("limit", [50])[0]), 1000))
                offset = max(0, int(params.get("offset", [0])[0]))
            except ValueError:
                return self._json_response({"error": "limit and offset must be integers"}, 400, "Bad Request")
            return self._json_response({"messages": self._history(limit, offset)})
        if path == "/history":
            params = parse_qs(query)
            channel = params.get("channel", [""])[0].strip()
            if not channel:
                return self._json_response({"error": "channel is required"}, 400, "Bad Request")
            since = params.get("since", [None])[0]
            if since is not None:
                try:
                    datetime.fromisoformat(since.replace("Z", "+00:00"))
                except ValueError:
                    return self._json_response({"error": "since must be an ISO timestamp"}, 400, "Bad Request")
            try:
                limit = max(1, min(int(params.get("limit", [50])[0]), 1000))
            except ValueError:
                return self._json_response({"error": "limit must be an integer"}, 400, "Bad Request")
            messages, has_more = self._channel_history(channel, since, limit)
            return self._json_response({"messages": messages, "has_more": has_more})
        if path == "/channels":
            with self._lock:
                channels = {n: len(s) for n, s in self.channels.items() if s}
            return self._json_response({"channels": channels})
        if path.startswith("/channels/") and path.endswith("/subscribers"):
            name = unquote(path[len("/channels/") : -len("/subscribers")]).strip("/")
            if name:
                with self._lock:
                    subscribers = sorted(self.channels.get(name, set()))
                return self._json_response({"channel": name, "subscribers": subscribers})
        if path.startswith("/channels/"):
            return self._json_response({"error": "not found"}, 404, "Not Found")
        return None

    async def _register(self, connection: ServerConnection) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self.clients[client_id] = connection
        await self.transport.on_connect(client_id, connection)
        if self._redis:
            await self._redis.hset(f"notifications:client:{client_id}", mapping={"server": self._instance_id})
        return client_id

    async def _remove(self, client_id: str) -> None:
        with self._lock:
            self.clients.pop(client_id, None)
            for name in list(self.channels):
                self.channels[name].discard(client_id)
                if not self.channels[name]:
                    del self.channels[name]
        await self.transport.on_disconnect(client_id)
        if self._redis:
            subscriptions = await self._redis.smembers(f"notifications:client:{client_id}:subscriptions")
            for channel in subscriptions:
                await self._redis.srem(f"notifications:subscriptions:{channel}", client_id)
            await self._redis.delete(f"notifications:client:{client_id}:subscriptions")
            await self._redis.delete(f"notifications:client:{client_id}")

    async def _send_to(self, client_id: str, message: str) -> bool:
        return await self.transport.send_message(client_id, message)

    async def _deliver(self, envelope: dict[str, Any]) -> None:
        message = envelope["message"]
        target_id = envelope.get("target_id")
        channel = envelope.get("channel")
        with self._lock:
            if target_id:
                recipients = [target_id] if target_id in self.clients else []
            elif channel is None:
                recipients = list(self.clients)
            else:
                recipients = [i for i in self.channels.get(channel, set()) if i in self.clients]
        failed = await self.transport.broadcast(message, recipients)
        for client_id in failed:
            await self._remove(client_id)

    async def broadcast(self, message_type: str, payload: dict[str, Any], channel: str | None = None, target_id: str | None = None) -> None:
        message = json.loads(self._make_message(message_type, payload))
        self._persist(channel, message)
        envelope = {"message": json.dumps(message), "channel": channel, "target_id": target_id}
        if self._redis:
            await self._redis.publish(REDIS_CHANNEL, json.dumps(envelope))
        else:
            await self._deliver(envelope)

    async def _redis_listener(self) -> None:
        try:
            async for item in self._pubsub.listen():
                if item.get("type") == "message":
                    await self._deliver(json.loads(item["data"]))
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("Redis listener stopped")

    async def _handle_message(self, client_id: str, raw_message: str) -> None:
        if not await self._allow_message(client_id):
            await self._send_error(client_id, "rate limit exceeded")
            return
        try:
            message = json.loads(raw_message)
            message_type, payload = message.get("type"), message.get("payload")
            if message_type not in MESSAGE_TYPES or not isinstance(payload, dict):
                raise ValueError("type must be supported and payload must be an object")
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as exc:
            with self._lock:
                connected = client_id in self.clients
            if connected:
                await self._send_to(client_id, self._make_message("system", {"error": str(exc)}))
            return
        channel = payload.get("channel", message.get("channel"))
        if channel is not None and (not isinstance(channel, str) or not channel.strip()):
            await self._send_error(client_id, "channel must be a non-empty string")
            return
        channel = channel.strip() if channel else None
        if message_type == "direct" and channel is None:
            await self.broadcast("direct", payload, target_id=payload.get("client_id"))
        elif message_type in {"subscribe", "unsubscribe"}:
            if channel is None:
                await self._send_error(client_id, "channel must be a non-empty string")
                return
            with self._lock:
                if message_type == "subscribe":
                    self.channels.setdefault(channel, set()).add(client_id)
                elif channel in self.channels:
                    self.channels[channel].discard(client_id)
                    if not self.channels[channel]:
                        del self.channels[channel]
            if self._redis:
                key = f"notifications:subscriptions:{channel}"
                if message_type == "subscribe":
                    await self._redis.sadd(key, client_id)
                    await self._redis.sadd(f"notifications:client:{client_id}:subscriptions", channel)
                else:
                    await self._redis.srem(key, client_id)
                    await self._redis.srem(f"notifications:client:{client_id}:subscriptions", channel)
        else:
            await self.broadcast(message_type, payload, channel)

    async def _send_error(self, client_id: str, error: str) -> None:
        with self._lock:
            connected = client_id in self.clients
        if connected:
            await self._send_to(client_id, self._make_message("system", {"error": error}))

    async def _handler(self, connection: ServerConnection) -> None:
        client_id = await self._register(connection)
        await self._send_to(client_id, self._make_message("system", {"event": "connected", "client_id": client_id}))
        try:
            async for raw_message in connection:
                await self._handle_message(client_id, raw_message)
        except ConnectionClosed:
            pass
        finally:
            await self._remove(client_id)

    async def start(self) -> None:
        if self._server is not None:
            return
        try:
            candidate = redis.from_url(self.redis_url, decode_responses=True)
            await candidate.ping()
            self._redis = candidate
            self._pubsub = candidate.pubsub()
            await self._pubsub.subscribe(REDIS_CHANNEL)
            self._redis_task = asyncio.create_task(self._redis_listener())
        except Exception:
            LOGGER.warning("Redis unavailable; using local message delivery", exc_info=True)
            if self._redis:
                await self._redis.close()
            self._redis = None
        self._server = await self.transport.start(self._handler, self._process_request, self.host, self.port)
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        await self.transport.stop()
        self._server = None
        if self._redis_task:
            self._redis_task.cancel()
            await asyncio.gather(self._redis_task, return_exceptions=True)
            self._redis_task = None
        if self._cleanup_task:
            self._cleanup_task.cancel()
            await asyncio.gather(self._cleanup_task, return_exceptions=True)
            self._cleanup_task = None
        if self._pubsub:
            await self._pubsub.close()
            self._pubsub = None
        if self._redis:
            await self._redis.close()
            self._redis = None
        with self._lock:
            self.clients.clear()
            self.channels.clear()


async def main() -> None:
    server = NotificationServer()
    await server.start()
    LOGGER.info("Notification server listening on %s:%s", server.host, server.bound_port)
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
