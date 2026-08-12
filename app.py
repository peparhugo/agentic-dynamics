"""Async WebSocket notification server backed by Redis and SQLite."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from websockets.asyncio.server import ServerConnection, serve

try:
    from redis.asyncio import Redis
except ImportError:  # pragma: no cover - requirements install redis in production
    Redis = Any  # type: ignore[misc,assignment]


SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class MessageStore:
    def __init__(self, database_url: str | None = None) -> None:
        value = database_url or os.getenv("DATABASE_URL", "sqlite:///:memory:")
        if value.startswith("sqlite:///"):
            path = value[10:]
        elif value.startswith("sqlite://"):
            path = value[9:]
        else:
            path = value
        self.path = path or ":memory:"
        self._lock = threading.Lock()
        self._connection: sqlite3.Connection | None = None

    def open(self) -> None:
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, type TEXT NOT NULL, "
            "payload TEXT NOT NULL, timestamp TEXT NOT NULL)"
        )
        self._connection.commit()

    def close(self) -> None:
        if self._connection is not None:
            with self._lock:
                self._connection.close()
            self._connection = None

    def add(self, channel: str | None, message_type: str, payload: dict[str, Any], time: str) -> None:
        if self._connection is None:
            raise RuntimeError("message store is not open")
        with self._lock:
            self._connection.execute(
                "INSERT INTO messages(channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (channel, message_type, json.dumps(payload), time),
            )
            self._connection.commit()

    def list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        if self._connection is None:
            return []
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        return [{"id": row[0], "channel": row[1], "type": row[2],
                 "payload": json.loads(row[3]), "timestamp": row[4]} for row in rows]


class _HealthHandler(BaseHTTPRequestHandler):
    server_version = "NotificationHealth/1.0"

    def do_GET(self) -> None:  # noqa: N802
        owner: NotificationServer = self.server.owner  # type: ignore[attr-defined]
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/health":
            body_data = {"connected_clients": owner.client_count}
        elif path == "/channels":
            body_data = {"channels": owner.channel_counts()}
        elif path == "/messages":
            query = parse_qs(parsed.query)
            try:
                limit = max(0, min(1000, int(query.get("limit", ["50"])[0])))
                offset = max(0, int(query.get("offset", ["0"])[0]))
            except ValueError:
                self.send_error(400, "limit and offset must be integers")
                return
            body_data = {"messages": owner.messages(limit, offset)}
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            channel = unquote(path[len("/channels/"):-len("/subscribers")])
            if not channel or "/" in channel:
                self.send_error(404)
                return
            body_data = {"subscribers": owner.channel_subscribers(channel)}
        else:
            self.send_error(404)
            return
        body = json.dumps(body_data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: Any) -> None:
        return


class _HealthServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], owner: "NotificationServer") -> None:
        self.owner = owner
        super().__init__(address, _HealthHandler)


class NotificationServer:
    """Manage WebSocket clients, with Redis distributing messages between instances."""

    redis_channel = "notifications:messages"

    def __init__(self, host: str = "127.0.0.1", websocket_port: int = 8765,
                 http_port: int = 8080, redis_url: str | None = None,
                 database_url: str | None = None, redis_client: Any = None) -> None:
        self.host, self.websocket_port, self.http_port = host, websocket_port, http_port
        self.redis_url = redis_url if redis_url is not None else os.getenv("REDIS_URL")
        self.redis = redis_client
        self.store = MessageStore(database_url)
        self.registry_lock = threading.Lock()
        self.clients: dict[str, ServerConnection] = {}
        self.client_channels: dict[str, set[str]] = {}
        self.channels: dict[str, set[str]] = {}
        self._websocket_server = None
        self._health_server: _HealthServer | None = None
        self._health_thread: threading.Thread | None = None
        self._subscriber_task: asyncio.Task[None] | None = None
        self._redis_pubsub: Any = None
        self._instance_id = str(uuid.uuid4())

    @property
    def client_count(self) -> int:
        with self.registry_lock:
            return len(self.clients)

    def channel_counts(self) -> dict[str, int]:
        with self.registry_lock:
            return {name: len(users) for name, users in self.channels.items() if users}

    def channel_subscribers(self, channel: str) -> list[str]:
        with self.registry_lock:
            return sorted(self.channels.get(channel, set()))

    def messages(self, limit: int, offset: int) -> list[dict[str, Any]]:
        return self.store.list(limit, offset)

    async def start(self) -> None:
        self.store.open()
        if self.redis is None and self.redis_url:
            self.redis = Redis.from_url(self.redis_url, decode_responses=True)
        if self.redis is not None:
            try:
                await self.redis.ping()
                self._redis_pubsub = self.redis.pubsub()
                await self._redis_pubsub.subscribe(self.redis_channel)
                self._subscriber_task = asyncio.create_task(self._consume_redis())
            except Exception:
                await self._close_redis()
        self._websocket_server = await serve(self._handle_client, self.host, self.websocket_port)
        self.websocket_port = self._websocket_server.sockets[0].getsockname()[1]
        self._health_server = _HealthServer((self.host, self.http_port), self)
        self.http_port = self._health_server.server_address[1]
        self._health_thread = threading.Thread(target=self._health_server.serve_forever,
                                                name="notification-health", daemon=True)
        self._health_thread.start()

    async def stop(self) -> None:
        if self._websocket_server is not None:
            self._websocket_server.close()
            await self._websocket_server.wait_closed()
        if self._subscriber_task:
            self._subscriber_task.cancel()
            await asyncio.gather(self._subscriber_task, return_exceptions=True)
        await self._close_redis()
        with self.registry_lock:
            connections = list(self.clients.values())
            self.clients.clear(); self.client_channels.clear(); self.channels.clear()
        await asyncio.gather(*(client.close() for client in connections), return_exceptions=True)
        if self._health_server is not None:
            self._health_server.shutdown(); self._health_server.server_close()
        if self._health_thread is not None:
            self._health_thread.join(timeout=2)
        self.store.close()

    async def _close_redis(self) -> None:
        if self._redis_pubsub is not None:
            await self._redis_pubsub.close()
            self._redis_pubsub = None
        if self.redis is not None and self.redis_url:
            await self.redis.aclose()
            self.redis = None

    async def _consume_redis(self) -> None:
        while True:
            item = await self._redis_pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if item and item.get("data"):
                envelope = json.loads(item["data"])
                if envelope.get("origin") != self._instance_id:
                    await self._deliver(envelope["message"])
            await asyncio.sleep(0)

    async def _handle_client(self, connection: ServerConnection) -> None:
        client_id = str(uuid.uuid4())
        with self.registry_lock:
            self.clients[client_id] = connection; self.client_channels[client_id] = set()
        await self._save_client_state(client_id, "connected", set())
        await connection.send(self._message("system", {"event": "connected", "client_id": client_id}))
        try:
            async for raw_message in connection:
                await self._handle_message(client_id, raw_message)
        finally:
            with self.registry_lock:
                self.clients.pop(client_id, None)
                saved_channels = self.client_channels.pop(client_id, set())
                for channel in saved_channels:
                    subscribers = self.channels.get(channel)
                    if subscribers is not None:
                        subscribers.discard(client_id)
                        if not subscribers: self.channels.pop(channel, None)
            await self._save_client_state(client_id, "disconnected", saved_channels)

    async def _save_client_state(self, client_id: str, status: str,
                                 channels: set[str]) -> None:
        if self.redis is None:
            return
        await self.redis.hset(
            f"notifications:client:{client_id}",
            mapping={"status": status, "channels": json.dumps(sorted(channels)),
                     "updated_at": timestamp()},
        )

    async def _handle_message(self, sender_id: str, raw_message: str) -> None:
        try: message = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError): return
        if not isinstance(message, dict): return
        message_type, payload = message.get("type"), message.get("payload", {})
        if message_type not in SUPPORTED_TYPES or not isinstance(payload, dict): return
        channel = message.get("channel", payload.get("channel"))
        if message_type in {"subscribe", "unsubscribe"}:
            if not isinstance(channel, str) or not channel: return
            with self.registry_lock:
                subscribed = self.client_channels.setdefault(sender_id, set())
                if message_type == "subscribe":
                    subscribed.add(channel); self.channels.setdefault(channel, set()).add(sender_id)
                else:
                    subscribed.discard(channel); subscribers = self.channels.get(channel)
                    if subscribers is not None:
                        subscribers.discard(sender_id)
                        if not subscribers: self.channels.pop(channel, None)
                state_channels = set(subscribed)
            await self._save_client_state(sender_id, "connected", state_channels)
            return
        outgoing = {"type": message_type, "payload": payload,
                    "timestamp": message.get("timestamp") or timestamp()}
        if isinstance(channel, str) and channel: outgoing["channel"] = channel
        await asyncio.to_thread(self.store.add, channel if isinstance(channel, str) else None,
                                message_type, payload, outgoing["timestamp"])
        if self.redis is not None:
            await self.redis.publish(self.redis_channel, json.dumps({"origin": self._instance_id,
                                                                       "message": outgoing}))
        else:
            await self._deliver(outgoing)

    async def _deliver(self, outgoing: dict[str, Any]) -> None:
        channel = outgoing.get("channel")
        with self.registry_lock:
            if outgoing["type"] == "direct":
                target_id = outgoing["payload"].get("client_id") or outgoing["payload"].get("target_id")
                target = self.clients.get(target_id)
                if channel and target_id not in self.channels.get(channel, set()): target = None
                recipients = [target] if target is not None else []
            elif isinstance(channel, str) and channel:
                recipients = [self.clients[cid] for cid in self.channels.get(channel, set()) if cid in self.clients]
            else: recipients = list(self.clients.values())
        await asyncio.gather(*(client.send(json.dumps(outgoing)) for client in recipients), return_exceptions=True)

    @staticmethod
    def _message(message_type: str, payload: dict[str, Any]) -> str:
        return json.dumps({"type": message_type, "payload": payload, "timestamp": timestamp()})


server = NotificationServer()


async def main() -> None:
    await server.start()
    try: await asyncio.Future()
    finally: await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
