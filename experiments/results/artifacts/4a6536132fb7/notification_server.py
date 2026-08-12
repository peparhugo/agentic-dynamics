"""Async notification server with a small health endpoint."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
from urllib.parse import parse_qs, unquote, urlsplit

from transport import BaseTransport, WebSocketTransport

try:
    import redis.asyncio as redis
except ImportError:  # pragma: no cover - dependencies install in production
    redis = None


MESSAGE_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


def message(message_type: str, payload: dict[str, Any], channel: str | None = None) -> dict[str, Any]:
    """Build a message with the wire format used by the server."""
    result = {
        "type": message_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if channel is not None:
        result["channel"] = channel
    return result


class NotificationServer:
    """Manage WebSocket clients and serve their current count over HTTP."""

    def __init__(self, websocket_host: str = "127.0.0.1", websocket_port: int = 8765,
                 http_host: str | None = None, http_port: int = 8080,
                 redis_url: str | None = None, database_url: str | None = None,
                 transport: BaseTransport | None = None,
                 rate_limit: int | None = None, message_ttl_days: int | None = None) -> None:
        self.websocket_host = websocket_host
        self.websocket_port = websocket_port
        self.http_host = http_host or websocket_host
        self.http_port = http_port
        self.clients: dict[str, Any] = {}
        self.channels: dict[str, set[str]] = {}
        self._client_channels: dict[str, set[str]] = {}
        self._clients_lock = threading.RLock()
        self.transport = transport or self._create_transport()
        self._http_server: asyncio.AbstractServer | None = None
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.database_url = database_url or os.getenv("DATABASE_URL", "messages.db")
        self._redis: Any = None
        self._pubsub: Any = None
        self._redis_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None
        self._instance_id = str(uuid4())
        self.rate_limit = rate_limit if rate_limit is not None else self._env_int("RATE_LIMIT", 100)
        self.message_ttl_days = (message_ttl_days if message_ttl_days is not None
                                 else self._env_int("MESSAGE_TTL_DAYS", 7))
        self._local_rate_limits: dict[tuple[str, int], int] = {}
        self._database = self._open_database(self.database_url)

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        try:
            return int(os.getenv(name, str(default)))
        except ValueError:
            return default

    def _create_transport(self) -> BaseTransport:
        transport_name = os.getenv("TRANSPORT", "websocket").lower()
        if transport_name != "websocket":
            raise ValueError(f"unsupported transport: {transport_name}")
        return WebSocketTransport(self.websocket_host, self.websocket_port,
                                  self._handle_message, self._on_connect, self._on_disconnect)

    @staticmethod
    def _open_database(database_url: str) -> sqlite3.Connection:
        path = database_url
        if path.startswith("sqlite:///"):
            path = path[10:]
        connection = sqlite3.connect(path, check_same_thread=False)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        connection.commit()
        return connection

    @property
    def connected_clients(self) -> int:
        with self._clients_lock:
            return len(self.clients)

    async def start(self) -> "NotificationServer":
        self._cleanup_expired_messages()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        await self._start_redis()
        await self.transport.start()
        self._http_server = await asyncio.start_server(
            self._handle_http, self.http_host, self.http_port
        )
        self.websocket_port = getattr(self.transport, "port", self.websocket_port)
        self.http_port = self._http_server.sockets[0].getsockname()[1]
        return self

    def _cleanup_expired_messages(self) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max(0, self.message_ttl_days))).isoformat()
        self._database.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff,))
        self._database.commit()

    async def _cleanup_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(3600)
                self._cleanup_expired_messages()
        except asyncio.CancelledError:
            raise

    async def _start_redis(self) -> None:
        if redis is None:
            return
        client = redis.from_url(self.redis_url, decode_responses=True)
        try:
            await asyncio.wait_for(client.ping(), timeout=0.5)
            self._redis = client
            self._pubsub = client.pubsub()
            await self._pubsub.subscribe("notifications")
            self._redis_task = asyncio.create_task(self._redis_listener())
        except Exception:
            await self._close_resource(client)

    @staticmethod
    async def _close_resource(resource: Any) -> None:
        close = getattr(resource, "aclose", None) or getattr(resource, "close")
        result = close()
        if result is not None:
            await result

    async def _redis_listener(self) -> None:
        try:
            while True:
                item = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if item and item.get("type") == "message":
                    envelope = json.loads(item["data"])
                    await self._deliver(envelope["message"], envelope.get("target"))
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    async def _stop_redis(self) -> None:
        if self._redis_task is not None:
            self._redis_task.cancel()
            await asyncio.gather(self._redis_task, return_exceptions=True)
            self._redis_task = None
        if self._pubsub is not None:
            await self._pubsub.unsubscribe("notifications")
            await self._close_resource(self._pubsub)
            self._pubsub = None
        if self._redis is not None:
            await self._close_resource(self._redis)
            self._redis = None

    async def stop(self) -> None:
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            await asyncio.gather(self._cleanup_task, return_exceptions=True)
            self._cleanup_task = None
        await self._stop_redis()
        await self.transport.stop()
        if self._http_server is not None:
            self._http_server.close()
            await self._http_server.wait_closed()
            self._http_server = None
        with self._clients_lock:
            self.clients.clear()
            self.channels.clear()
            self._client_channels.clear()
        self._database.close()

    async def broadcast(self, payload: dict[str, Any], message_type: str = "broadcast",
                        channel: str | None = None) -> None:
        if message_type not in MESSAGE_TYPES:
            raise ValueError(f"unsupported message type: {message_type}")
        outgoing = message(message_type, payload, channel)
        await self._publish(outgoing)

    async def _publish(self, outgoing: dict[str, Any], target: str | None = None) -> None:
        self._store_message(outgoing)
        if self._redis is not None:
            await self._redis.publish("notifications", json.dumps({
                "message": outgoing, "target": target, "origin": self._instance_id
            }))
        else:
            await self._deliver(outgoing, target)

    def _store_message(self, outgoing: dict[str, Any]) -> None:
        self._database.execute(
            "INSERT INTO messages(channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
            (outgoing.get("channel"), outgoing["type"],
             json.dumps(outgoing["payload"]), outgoing["timestamp"]),
        )
        self._database.commit()

    async def _deliver(self, outgoing: dict[str, Any], target: str | None = None) -> None:
        wire_message = json.dumps(outgoing)
        with self._clients_lock:
            channel = outgoing.get("channel")
            if target is not None:
                client_ids = [target] if target in self.clients else []
            elif channel is None:
                client_ids = list(self.clients)
            else:
                subscriber_ids = self.channels.get(channel, set())
                client_ids = [client_id for client_id in subscriber_ids if client_id in self.clients]
        if client_ids:
            if target is not None:
                await self.transport.send_message(client_ids[0], wire_message)
            else:
                await self.transport.broadcast(wire_message, client_ids)

    def _set_subscription(self, client_id: str, channel: str, subscribed: bool) -> None:
        with self._clients_lock:
            client_channels = self._client_channels.setdefault(client_id, set())
            if subscribed:
                client_channels.add(channel)
                self.channels.setdefault(channel, set()).add(client_id)
            else:
                client_channels.discard(channel)
                subscribers = self.channels.get(channel)
                if subscribers is not None:
                    subscribers.discard(client_id)
                    if not subscribers:
                        self.channels.pop(channel, None)

    async def send_direct(self, client_id: str, payload: dict[str, Any]) -> bool:
        with self._clients_lock:
            local_target = client_id in self.clients
        if not local_target and self._redis is None:
            return False
        await self._publish(message("direct", payload), client_id)
        return True

    async def _on_connect(self, client_id: str, connection: Any) -> None:
        with self._clients_lock:
            self.clients[client_id] = connection
            self._client_channels[client_id] = set()
        if self._redis is not None:
            await self._redis.hset(f"notification:client:{client_id}", mapping={
                "server": self._instance_id, "connected": "1"
            })
        await self.transport.send_message(client_id,
                                          json.dumps(message("system", {"client_id": client_id})))

    async def _on_disconnect(self, client_id: str) -> None:
        with self._clients_lock:
            self.clients.pop(client_id, None)
            subscribed_channels = self._client_channels.pop(client_id, set())
            for channel in subscribed_channels:
                subscribers = self.channels.get(channel)
                if subscribers is not None:
                    subscribers.discard(client_id)
                    if not subscribers:
                        self.channels.pop(channel, None)
        if self._redis is not None:
            await self._redis.delete(f"notification:client:{client_id}")

    async def _check_rate_limit(self, client_id: str) -> bool:
        if self.rate_limit <= 0:
            return True
        bucket = int(time.time() // 60)
        key = f"notification:rate:{client_id}:{bucket}"
        if self._redis is not None:
            try:
                count = await self._redis.incr(key)
                if count == 1:
                    await self._redis.expire(key, 61)
                return count <= self.rate_limit
            except Exception:
                pass
        local_key = (client_id, bucket)
        count = self._local_rate_limits.get(local_key, 0) + 1
        self._local_rate_limits[local_key] = count
        for old_key in list(self._local_rate_limits):
            if old_key[1] < bucket:
                del self._local_rate_limits[old_key]
        return count <= self.rate_limit

    async def _handle_message(self, sender_id: str, raw_message: str) -> None:
        try:
            incoming = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(incoming, dict):
            return
        message_type = incoming.get("type")
        payload = incoming.get("payload")
        if message_type in {"subscribe", "unsubscribe"} and payload is None:
            payload = {}
        if message_type not in MESSAGE_TYPES or not isinstance(payload, dict):
            return
        if not await self._check_rate_limit(sender_id):
            await self.transport.send_message(sender_id, json.dumps(message(
                "system", {"error": "rate limit exceeded"})))
            return
        channel = incoming.get("channel")
        if channel is None:
            channel = payload.get("channel")
        if channel is not None and not isinstance(channel, str):
            return
        if message_type in {"subscribe", "unsubscribe"}:
            if not isinstance(channel, str) or not channel:
                return
            self._set_subscription(sender_id, channel, message_type == "subscribe")
            if self._redis is not None:
                key = f"notification:client:{sender_id}:channels"
                if message_type == "subscribe":
                    await self._redis.sadd(key, channel)
                else:
                    await self._redis.srem(key, channel)
            return
        if message_type == "direct":
            target_id = payload.get("client_id")
            if isinstance(target_id, str):
                direct_payload = {key: value for key, value in payload.items() if key != "client_id"}
                await self.send_direct(target_id, direct_payload)
            return
        await self.broadcast(payload, message_type, channel)

    def _channel_listing(self) -> list[dict[str, Any]]:
        with self._clients_lock:
            return [{"name": name, "subscriber_count": len(subscribers)}
                    for name, subscribers in sorted(self.channels.items())]

    def _channel_subscribers(self, channel: str) -> list[str] | None:
        with self._clients_lock:
            if channel not in self.channels:
                return None
            return sorted(self.channels[channel])

    async def _handle_http(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = (await reader.readline()).decode("ascii", "ignore").strip()
            method, path, *_ = request_line.split()
            parsed = urlsplit(path)
            route = parsed.path
            if method == "GET" and route == "/health":
                body = json.dumps({"connected_clients": self.connected_clients}).encode()
                status = "200 OK"
            elif method == "GET" and route == "/channels":
                body = json.dumps({"channels": self._channel_listing()}).encode()
                status = "200 OK"
            elif method == "GET" and route == "/messages":
                query = parse_qs(parsed.query)
                limit = max(0, min(int(query.get("limit", [50])[0]), 1000))
                offset = max(0, int(query.get("offset", [0])[0]))
                rows = self._database.execute(
                    "SELECT id, channel, type, payload, timestamp FROM messages "
                    "ORDER BY id LIMIT ? OFFSET ?", (limit, offset)
                ).fetchall()
                body = json.dumps({"messages": [
                    {"id": row[0], "channel": row[1], "type": row[2],
                     "payload": json.loads(row[3]), "timestamp": row[4]}
                    for row in rows
                ]}).encode()
                status = "200 OK"
            elif method == "GET" and route == "/history":
                query = parse_qs(parsed.query)
                channel_values = query.get("channel")
                if not channel_values or not channel_values[0]:
                    raise ValueError("channel is required")
                channel = channel_values[0]
                since = query.get("since", [None])[0]
                if since is not None:
                    since = datetime.fromisoformat(since.replace("Z", "+00:00")).isoformat()
                limit = max(1, min(int(query.get("limit", [50])[0]), 1000))
                sql = ("SELECT id, channel, type, payload, timestamp FROM messages "
                       "WHERE channel = ?")
                parameters: list[Any] = [channel]
                if since is not None:
                    sql += " AND timestamp > ?"
                    parameters.append(since)
                rows = self._database.execute(
                    sql + " ORDER BY timestamp ASC, id ASC LIMIT ?", parameters + [limit + 1]
                ).fetchall()
                has_more = len(rows) > limit
                rows = rows[:limit]
                body = json.dumps({"messages": [
                    {"id": row[0], "channel": row[1], "type": row[2],
                     "payload": json.loads(row[3]), "timestamp": row[4]}
                    for row in rows
                ], "has_more": has_more}).encode()
                status = "200 OK"
            elif method == "GET" and route.startswith("/channels/") and route.endswith("/subscribers"):
                channel = unquote(route[len("/channels/"):-len("/subscribers")])
                subscribers = self._channel_subscribers(channel)
                if subscribers is None:
                    body = json.dumps({"error": "channel not found"}).encode()
                    status = "404 Not Found"
                else:
                    body = json.dumps({"channel": channel, "subscribers": subscribers}).encode()
                    status = "200 OK"
            else:
                body = json.dumps({"error": "not found"}).encode()
                status = "404 Not Found"
            headers = (f"HTTP/1.1 {status}\r\nContent-Type: application/json\r\n"
                       f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode()
            writer.write(headers + body)
            await writer.drain()
        except (ValueError, UnicodeError):
            writer.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def serve_forever(self) -> None:
        if self._http_server is None:
            await self.start()
        await asyncio.Future()

    def run(self) -> None:
        asyncio.run(self.serve_forever())


def create_server() -> NotificationServer:
    return NotificationServer()
