"""Redis-backed asynchronous WebSocket notification server."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import redis.asyncio as redis
from websockets.asyncio.server import Request, Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Response

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
    ) -> None:
        self.host, self.port = host, port
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///messages.db")
        self.clients: dict[str, ServerConnection] = {}
        self.channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()
        self._server: Server | None = None
        self._redis: redis.Redis | None = None
        self._pubsub: Any = None
        self._redis_task: asyncio.Task[None] | None = None
        self._instance_id = str(uuid.uuid4())
        self._db_lock = threading.Lock()
        self._db_path = self._sqlite_path(self.database_url)
        with sqlite3.connect(self._db_path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT NOT NULL,
                type TEXT NOT NULL, payload TEXT NOT NULL, timestamp TEXT NOT NULL
            )""")

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
        if self._server is None or not self._server.sockets:
            return self.port
        return self._server.sockets[0].getsockname()[1]

    async def client_count(self) -> int:
        with self._lock:
            return len(self.clients)

    def _make_message(self, message_type: str, payload: dict[str, Any]) -> str:
        return json.dumps({"type": message_type, "payload": payload, "timestamp": timestamp()})

    def _persist(self, channel: str | None, message: dict[str, Any]) -> None:
        with self._db_lock, sqlite3.connect(self._db_path) as db:
            db.execute(
                "INSERT INTO messages(channel,type,payload,timestamp) VALUES (?,?,?,?)",
                (channel or "", message["type"], json.dumps(message["payload"]), message["timestamp"]),
            )

    def _history(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with self._db_lock, sqlite3.connect(self._db_path) as db:
            rows = db.execute(
                "SELECT id,channel,type,payload,timestamp FROM messages ORDER BY id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [{"id": i, "channel": c, "type": t, "payload": json.loads(p), "timestamp": ts}
                for i, c, t, p, ts in rows]

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
        if self._redis:
            subscriptions = await self._redis.smembers(f"notifications:client:{client_id}:subscriptions")
            for channel in subscriptions:
                await self._redis.srem(f"notifications:subscriptions:{channel}", client_id)
            await self._redis.delete(f"notifications:client:{client_id}:subscriptions")
            await self._redis.delete(f"notifications:client:{client_id}")

    async def _send_to(self, connection: ServerConnection, message: str) -> bool:
        try:
            await connection.send(message)
            return True
        except ConnectionClosed:
            return False

    async def _deliver(self, envelope: dict[str, Any]) -> None:
        message = envelope["message"]
        target_id = envelope.get("target_id")
        channel = envelope.get("channel")
        with self._lock:
            if target_id:
                recipients = [(target_id, self.clients[target_id])] if target_id in self.clients else []
            elif channel is None:
                recipients = list(self.clients.items())
            else:
                recipients = [(i, self.clients[i]) for i in self.channels.get(channel, set()) if i in self.clients]
        results = await asyncio.gather(*(self._send_to(c, message) for _, c in recipients))
        for (client_id, _), sent in zip(recipients, results):
            if not sent:
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
        try:
            message = json.loads(raw_message)
            message_type, payload = message.get("type"), message.get("payload")
            if message_type not in MESSAGE_TYPES or not isinstance(payload, dict):
                raise ValueError("type must be supported and payload must be an object")
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as exc:
            with self._lock:
                connection = self.clients.get(client_id)
            if connection:
                await self._send_to(connection, self._make_message("system", {"error": str(exc)}))
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
            connection = self.clients.get(client_id)
        if connection:
            await self._send_to(connection, self._make_message("system", {"error": error}))

    async def _handler(self, connection: ServerConnection) -> None:
        client_id = await self._register(connection)
        await connection.send(self._make_message("system", {"event": "connected", "client_id": client_id}))
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
        self._server = await serve(self._handler, self.host, self.port, process_request=self._process_request)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._redis_task:
            self._redis_task.cancel()
            await asyncio.gather(self._redis_task, return_exceptions=True)
            self._redis_task = None
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
