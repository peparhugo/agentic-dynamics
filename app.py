"""Async WebSocket notification server backed by Redis and SQLite."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import redis.asyncio as redis
import websockets
from websockets.exceptions import ConnectionClosed


MESSAGE_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
REDIS_PUBSUB_PATTERN = "notifications:*"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class NotificationServer:
    """Serve notifications over WebSockets and HTTP.

    Redis is used for cross-process delivery and connection membership.  If the
    default Redis instance is not available, the server falls back to its
    original in-process routing, which keeps local development backwards
    compatible. An explicitly supplied Redis client is always used.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        websocket_port: int = 8765,
        http_port: int = 8080,
        redis_url: str | None = None,
        database_url: str | None = None,
        redis_client: Any | None = None,
    ) -> None:
        self.host = host
        self.websocket_port = websocket_port
        self.http_port = http_port
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        self.database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///messages.db")
        self.instance_id = str(uuid.uuid4())
        self.clients: dict[str, Any] = {}
        self.channels: dict[str, set[str]] = {}
        self._clients_lock = asyncio.Lock()
        self._state_lock = asyncio.Lock()
        self._websocket_server: Any = None
        self._http_server: asyncio.AbstractServer | None = None
        self._redis = redis_client
        self._provided_redis = redis_client is not None
        self._pubsub: Any = None
        self._redis_listener: asyncio.Task[None] | None = None
        self._redis_enabled = redis_client is not None
        self._database_path = self._database_path_from_url(self.database_url)
        self._db = sqlite3.connect(self._database_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db_lock = asyncio.Lock()
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, type TEXT NOT NULL, "
            "payload TEXT NOT NULL, timestamp TEXT NOT NULL)"
        )
        self._db.commit()

    @staticmethod
    def _database_path_from_url(database_url: str) -> str:
        if database_url.startswith("sqlite:///"):
            return database_url[len("sqlite:///") :]
        if database_url.startswith("sqlite://"):
            return database_url[len("sqlite://") :]
        return database_url

    @property
    def connected_count(self) -> int:
        return len(self.clients)

    async def start(self) -> None:
        """Start listeners and the Redis subscription worker."""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        try:
            await self._redis.ping()
            self._redis_enabled = True
        except Exception:
            if not isinstance(self._redis, redis.Redis):
                raise
            self._redis_enabled = False
            await self._close_resource(self._redis)
            self._redis = None
        if self._redis_enabled:
            self._pubsub = self._redis.pubsub()
            await self._pubsub.psubscribe(REDIS_PUBSUB_PATTERN)
            self._redis_listener = asyncio.create_task(self._redis_loop())
        self._websocket_server = await websockets.serve(self._handle_websocket, self.host, self.websocket_port)
        self._http_server = await asyncio.start_server(self._handle_http, self.host, self.http_port)
        self.websocket_port = self._websocket_server.sockets[0].getsockname()[1]
        self.http_port = self._http_server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._websocket_server is not None:
            self._websocket_server.close()
            await self._websocket_server.wait_closed()
            self._websocket_server = None
        if self._http_server is not None:
            self._http_server.close()
            await self._http_server.wait_closed()
            self._http_server = None
        if self._redis_listener is not None:
            self._redis_listener.cancel()
            await asyncio.gather(self._redis_listener, return_exceptions=True)
            self._redis_listener = None
        async with self._clients_lock:
            client_ids = list(self.clients)
            clients = list(self.clients.values())
            self.clients.clear()
            self.channels.clear()
        await asyncio.gather(*(self._unregister_client(client_id) for client_id in client_ids), return_exceptions=True)
        await asyncio.gather(*(client.close() for client in clients), return_exceptions=True)
        if self._pubsub is not None:
            await self._close_resource(self._pubsub)
            self._pubsub = None
        if self._redis is not None and self._redis_client_owned:
            await self._close_resource(self._redis)
            self._redis = None
        async with self._db_lock:
            self._db.close()

    @property
    def _redis_client_owned(self) -> bool:
        return not self._provided_redis

    @staticmethod
    async def _close_resource(resource: Any) -> None:
        close = getattr(resource, "aclose", None) or getattr(resource, "close")
        result = close()
        if inspect.isawaitable(result):
            await result

    async def broadcast(self, message: dict[str, Any]) -> None:
        normalised = self._normalise_message(message)
        await self._publish(normalised)

    async def _publish(self, message: dict[str, Any]) -> None:
        await self._persist(message)
        if self._redis_enabled and self._redis is not None:
            channel = message.get("channel") or "broadcast"
            await self._redis.publish(
                f"notifications:{channel}",
                json.dumps({"server_id": self.instance_id, "message": message}),
            )
        else:
            await self._deliver(message)

    async def _redis_loop(self) -> None:
        while True:
            item = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if item and item.get("type") == "pmessage":
                envelope = json.loads(item["data"])
                await self._deliver(envelope["message"])

    async def _deliver(self, message: dict[str, Any]) -> None:
        async with self._clients_lock:
            if message.get("type") == "direct":
                target_id = message["payload"].get("client_id")
                recipients = [(target_id, self.clients[target_id])] if target_id in self.clients else []
            elif message.get("channel") is None:
                recipients = list(self.clients.items())
            else:
                ids = self.channels.get(message["channel"], set())
                recipients = [(client_id, self.clients[client_id]) for client_id in ids if client_id in self.clients]
        results = await asyncio.gather(*(client.send(json.dumps(message)) for _, client in recipients), return_exceptions=True)
        for (client_id, _), result in zip(recipients, results):
            if isinstance(result, Exception):
                await self._remove_client(client_id)

    async def _handle_websocket(self, websocket: Any) -> None:
        client_id = str(uuid.uuid4())
        async with self._clients_lock:
            self.clients[client_id] = websocket
        await self._register_client(client_id)
        await websocket.send(json.dumps({"type": "system", "payload": {"client_id": client_id}, "timestamp": _timestamp()}))
        try:
            async for raw_message in websocket:
                await self._handle_message(client_id, raw_message)
        except (ConnectionClosed, asyncio.CancelledError):
            pass
        finally:
            await self._remove_client(client_id)

    async def _handle_message(self, sender_id: str, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
            if not isinstance(message, dict):
                raise ValueError
            normalised = self._normalise_message(message)
        except (ValueError, TypeError, json.JSONDecodeError):
            await self._send_system(sender_id, {"error": "invalid message"})
            return
        if normalised["type"] in {"subscribe", "unsubscribe"}:
            channel = normalised.get("channel")
            if channel is None:
                await self._send_system(sender_id, {"error": "subscription requires channel"})
                return
            async with self._clients_lock:
                subscribers = self.channels.setdefault(channel, set())
                if normalised["type"] == "subscribe":
                    subscribers.add(sender_id)
                else:
                    subscribers.discard(sender_id)
                    if not subscribers:
                        self.channels.pop(channel, None)
            await self._update_subscription(sender_id, channel, normalised["type"] == "subscribe")
            return
        if normalised.get("channel") is not None or normalised["type"] in {"broadcast", "system", "direct"}:
            await self._publish(normalised)

    @staticmethod
    def _normalise_message(message: dict[str, Any]) -> dict[str, Any]:
        message_type, payload = message.get("type"), message.get("payload")
        if message_type not in MESSAGE_TYPES or not isinstance(payload, dict):
            raise ValueError("message must contain a supported type and dict payload")
        channel = NotificationServer._message_channel(message)
        return {"type": message_type, "payload": payload, "timestamp": message.get("timestamp") if isinstance(message.get("timestamp"), str) else _timestamp(), **({"channel": channel} if channel else {})}

    @staticmethod
    def _message_channel(message: dict[str, Any]) -> str | None:
        channel = message.get("channel")
        if channel is None and message.get("type") in {"subscribe", "unsubscribe"}:
            channel = message.get("payload", {}).get("channel")
        if not isinstance(channel, str) or not channel.strip():
            if channel is None:
                return None
            raise ValueError("channel must be a non-empty string")
        return channel.strip()

    async def _persist(self, message: dict[str, Any]) -> None:
        async with self._db_lock:
            self._db.execute("INSERT INTO messages(channel, type, payload, timestamp) VALUES (?, ?, ?, ?)", (message.get("channel"), message["type"], json.dumps(message["payload"]), message["timestamp"]))
            self._db.commit()

    async def _messages(self, limit: int, offset: int) -> list[dict[str, Any]]:
        async with self._db_lock:
            rows = self._db.execute("SELECT id, channel, type, payload, timestamp FROM messages ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [{"id": row["id"], "channel": row["channel"], "type": row["type"], "payload": json.loads(row["payload"]), "timestamp": row["timestamp"]} for row in rows]

    async def _send_system(self, client_id: str, payload: dict[str, Any]) -> None:
        async with self._clients_lock:
            client = self.clients.get(client_id)
        if client is not None:
            await client.send(json.dumps({"type": "system", "payload": payload, "timestamp": _timestamp()}))

    async def _remove_client(self, client_id: str) -> None:
        async with self._clients_lock:
            self.clients.pop(client_id, None)
            for channel in list(self.channels):
                self.channels[channel].discard(client_id)
                if not self.channels[channel]:
                    del self.channels[channel]
        await self._unregister_client(client_id)

    async def _register_client(self, client_id: str) -> None:
        if self._redis_enabled and self._redis is not None:
            await self._redis.hset(f"notifications:client:{client_id}", mapping={"server_id": self.instance_id})
            await self._redis.sadd(f"notifications:server:{self.instance_id}:clients", client_id)

    async def _unregister_client(self, client_id: str) -> None:
        if self._redis_enabled and self._redis is not None:
            await self._redis.delete(f"notifications:client:{client_id}")
            await self._redis.srem(f"notifications:server:{self.instance_id}:clients", client_id)

    async def _update_subscription(self, client_id: str, channel: str, subscribe: bool) -> None:
        if self._redis_enabled and self._redis is not None:
            key = f"notifications:channel:{channel}"
            if subscribe:
                await self._redis.sadd(key, client_id)
            else:
                await self._redis.srem(key, client_id)

    async def _channel_data(self) -> dict[str, Any]:
        async with self._clients_lock:
            return {"channels": {name: len(subscribers) for name, subscribers in sorted(self.channels.items()) if subscribers}}

    async def _channel_subscribers(self, channel: str) -> dict[str, Any]:
        async with self._clients_lock:
            return {"channel": channel, "subscribers": sorted(self.channels.get(channel, set()))}

    async def _handle_http(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = (await reader.readline()).decode("ascii", errors="replace")
            method, path, *_ = request_line.split()
            while await reader.readline() not in (b"\r\n", b"\n", b""):
                pass
            parsed = urlparse(path)
            if method == "GET" and parsed.path == "/health":
                body, status = {"status": "ok", "connected_clients": self.connected_count}, "200 OK"
            elif method == "GET" and parsed.path == "/channels":
                body, status = await self._channel_data(), "200 OK"
            elif method == "GET" and parsed.path == "/messages":
                query = parse_qs(parsed.query)
                try:
                    limit = max(0, min(int(query.get("limit", ["50"])[0]), 1000))
                    offset = max(0, int(query.get("offset", ["0"])[0]))
                except ValueError:
                    body, status = {"error": "invalid pagination"}, "400 Bad Request"
                else:
                    body, status = {"messages": await self._messages(limit, offset)}, "200 OK"
            elif method == "GET" and parsed.path.startswith("/channels/") and parsed.path.endswith("/subscribers"):
                channel = unquote(parsed.path[len("/channels/") : -len("/subscribers")].rstrip("/"))
                body, status = (({"error": "not found"}, "404 Not Found") if not channel else (await self._channel_subscribers(channel), "200 OK"))
            else:
                body, status = {"error": "not found"}, "404 Not Found"
            encoded = json.dumps(body).encode()
            response = f"HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {len(encoded)}\r\nConnection: close\r\n\r\n".encode() + encoded
            writer.write(response)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()


async def main() -> None:
    server = NotificationServer()
    await server.start()
    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
