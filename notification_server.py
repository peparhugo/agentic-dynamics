"""Notification server with a pluggable client transport and health endpoint."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from aiohttp import web
from redis.asyncio import Redis
from transport import BaseTransport, WebSocketTransport


SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
REDIS_CHANNEL = "notification-server:messages"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"type": message_type, "payload": payload, "timestamp": _timestamp()}


class ClientRegistry:
    """A client registry safe to access from event-loop and worker threads."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._clients: dict[str, Any] = {}
        self._subscriptions: dict[str, set[str]] = {}

    def add(self, connection: Any, client_id: str | None = None) -> str:
        client_id = client_id or str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = connection
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in list(self._subscriptions):
                subscribers = self._subscriptions[channel]
                subscribers.discard(client_id)
                if not subscribers:
                    del self._subscriptions[channel]

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            self._subscriptions.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._subscriptions.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._subscriptions[channel]

    def channel_snapshot(self) -> dict[str, list[str]]:
        with self._lock:
            return {
                channel: sorted(client_ids)
                for channel, client_ids in self._subscriptions.items()
                if client_ids
            }

    def get(self, client_id: str) -> Any | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._clients)

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)


class MessageStore:
    """Small SQLite store shared by the HTTP history endpoint and publisher."""

    def __init__(self, database_url: str | None = None) -> None:
        self.path = database_url or os.environ.get("DATABASE_URL", "messages.db")
        if self.path.startswith("sqlite:///"):
            self.path = self.path[10:]
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS messages ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "channel TEXT, type TEXT NOT NULL, payload TEXT NOT NULL, "
                "timestamp TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def add(self, message: dict[str, Any]) -> None:
        payload = message["payload"]
        channel = payload.get("channel") if isinstance(payload, dict) else None
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (channel, message["type"], json.dumps(payload), message["timestamp"]),
            )

    def list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        return [
            {"id": row["id"], "channel": row["channel"], "type": row["type"],
             "payload": json.loads(row["payload"]), "timestamp": row["timestamp"]}
            for row in rows
        ]


class RedisBackbone:
    """Redis transport and durable client subscription state."""

    def __init__(self, url: str) -> None:
        self.redis = Redis.from_url(url, decode_responses=True)
        self.pubsub = self.redis.pubsub()
        self.task: asyncio.Task[None] | None = None
        self.on_message = None

    async def start(self, on_message) -> None:
        await self.redis.ping()
        self.on_message = on_message
        await self.pubsub.subscribe(REDIS_CHANNEL)
        self.task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        async for item in self.pubsub.listen():
            if item["type"] == "message" and self.on_message is not None:
                await self.on_message(json.loads(item["data"]))

    async def publish(self, message: dict[str, Any]) -> None:
        await self.redis.publish(REDIS_CHANNEL, json.dumps(message))

    async def save_client(self, client_id: str) -> None:
        await self.redis.hset(f"notification:client:{client_id}", mapping={"active": "1"})

    async def add_subscription(self, client_id: str, channel: str) -> None:
        await self.redis.sadd(f"notification:subscriptions:{client_id}", channel)

    async def remove_subscription(self, client_id: str, channel: str) -> None:
        await self.redis.srem(f"notification:subscriptions:{client_id}", channel)

    async def subscriptions(self, client_id: str) -> set[str]:
        return set(await self.redis.smembers(f"notification:subscriptions:{client_id}"))

    async def close(self) -> None:
        await self.pubsub.close()
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        await self.redis.close()


class NotificationServer:
    """Run notification routing independently of the client transport."""

    def __init__(self, host: str = "127.0.0.1", websocket_port: int = 8765,
                 health_port: int = 8080, redis_url: str | None = None,
                 database_url: str | None = None,
                 transport: BaseTransport | None = None) -> None:
        self.host = host
        self.websocket_port = websocket_port
        self.health_port = health_port
        self.clients = ClientRegistry()
        self.store = MessageStore(database_url)
        self.redis_url = redis_url or os.environ.get("REDIS_URL")
        self.backbone: RedisBackbone | None = None
        transport_name = os.environ.get("TRANSPORT", "websocket").lower()
        if transport is not None:
            self.transport = transport
        elif transport_name == "websocket":
            self.transport = WebSocketTransport(host, websocket_port)
        else:
            raise ValueError(f"unsupported transport: {transport_name}")
        self._http_runner: web.AppRunner | None = None
        self._health_site: web.TCPSite | None = None

    async def start(self) -> "NotificationServer":
        if self.redis_url:
            candidate = RedisBackbone(self.redis_url)
            try:
                await candidate.start(self._receive_published)
                self.backbone = candidate
            except Exception:
                await candidate.close()
        await self.transport.start(
            self._transport_connect, self._handle_message, self._transport_disconnect,
            self._transport_ready,
        )
        if isinstance(self.transport, WebSocketTransport):
            self.websocket_port = self.transport.port

        app = web.Application()
        app.router.add_get("/health", self._health)
        app.router.add_get("/channels", self._channels)
        app.router.add_get("/channels/{name}/subscribers", self._channel_subscribers)
        app.router.add_get("/messages", self._messages)
        self._http_runner = web.AppRunner(app)
        await self._http_runner.setup()
        self._health_site = web.TCPSite(
            self._http_runner, self.host, self.health_port
        )
        await self._health_site.start()
        if self._health_site._server and self._health_site._server.sockets:
            self.health_port = self._health_site._server.sockets[0].getsockname()[1]
        return self

    async def stop(self) -> None:
        await self.transport.stop()
        if self._http_runner is not None:
            await self._http_runner.cleanup()
            self._http_runner = None
        if self.backbone is not None:
            await self.backbone.close()
            self.backbone = None

    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response({"connected_clients": len(self.clients)})

    async def _channels(self, request: web.Request) -> web.Response:
        channels = self.clients.channel_snapshot()
        return web.json_response({
            "channels": [
                {"name": name, "subscriber_count": len(subscribers)}
                for name, subscribers in sorted(channels.items())
            ]
        })

    async def _channel_subscribers(self, request: web.Request) -> web.Response:
        channel = request.match_info["name"]
        subscribers = self.clients.channel_snapshot().get(channel, [])
        return web.json_response({"subscribers": subscribers})

    async def _messages(self, request: web.Request) -> web.Response:
        try:
            limit = int(request.query.get("limit", "50"))
            offset = int(request.query.get("offset", "0"))
            if limit < 1 or limit > 1000 or offset < 0:
                raise ValueError
        except ValueError:
            return web.json_response({"error": "limit must be 1..1000 and offset must be non-negative"}, status=400)
        return web.json_response(await asyncio.to_thread(self.store.list, limit, offset))

    async def _transport_connect(self, connection: Any, requested_id: str | None) -> str:
        client_id = self.clients.add(connection, requested_id)
        if self.backbone:
            await self.backbone.save_client(client_id)
            for channel in await self.backbone.subscriptions(client_id):
                self.clients.subscribe(client_id, channel)
        return client_id

    async def _transport_ready(self, client_id: str) -> None:
        await self.transport.send_message(client_id, _message("system", {
            "event": "connected", "client_id": client_id
        }))

    async def _transport_disconnect(self, client_id: str) -> None:
        self.clients.remove(client_id)

    async def _handle_message(self, sender_id: str, raw_message: str) -> None:
        try:
            incoming = json.loads(raw_message)
            message_type = incoming.get("type")
            payload = incoming.get("payload")
            if message_type not in SUPPORTED_TYPES or not isinstance(payload, dict):
                raise ValueError("type must be supported and payload must be an object")
            channel = payload.get("channel")
            if message_type in {"subscribe", "unsubscribe"} and not self._valid_channel(channel):
                raise ValueError("subscription messages require payload.channel")
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as exc:
            await self._send_to(sender_id, _message("system", {"error": str(exc)}))
            return

        if message_type == "subscribe":
            self.clients.subscribe(sender_id, channel)
            if self.backbone:
                await self.backbone.add_subscription(sender_id, channel)
            return
        if message_type == "unsubscribe":
            self.clients.unsubscribe(sender_id, channel)
            if self.backbone:
                await self.backbone.remove_subscription(sender_id, channel)
            return

        outgoing = _message(message_type, payload)
        if message_type == "direct" and not self._valid_channel(payload.get("channel")):
            recipient_id = payload.get("recipient_id", payload.get("client_id"))
            if not isinstance(recipient_id, str):
                await self._send_to(sender_id, _message("system", {
                    "error": "direct messages require payload.recipient_id"
                }))
                return
            outgoing["_recipient_id"] = recipient_id
        self.store.add(outgoing)
        if self.backbone:
            await self.backbone.publish(outgoing)
        else:
            await self._receive_published(outgoing)

    async def _receive_published(self, message: dict[str, Any]) -> None:
        recipient_id = message.get("_recipient_id")
        payload = message.get("payload", {})
        delivered = {key: value for key, value in message.items() if key != "_recipient_id"}
        if recipient_id:
            await self._send_to(recipient_id, delivered)
        elif self._valid_channel(payload.get("channel")):
            await self._broadcast_channel(payload["channel"], delivered)
        else:
            await self._broadcast(delivered)

    @staticmethod
    def _valid_channel(channel: Any) -> bool:
        return isinstance(channel, str) and bool(channel.strip())

    async def _broadcast_channel(self, channel: str, message: dict[str, Any]) -> None:
        subscribers = self.clients.channel_snapshot().get(channel, [])
        await self.transport.broadcast(message, subscribers)

    async def _broadcast(self, message: dict[str, Any]) -> None:
        await self.transport.broadcast(message, self.clients.snapshot())

    async def _send_to(self, client_id: str, message: dict[str, Any]) -> None:
        if self.clients.get(client_id) is not None:
            await self.transport.send_message(client_id, message)

    async def run_forever(self) -> None:
        await self.start()
        try:
            await asyncio.Future()
        finally:
            await self.stop()


async def main() -> None:
    server = NotificationServer()
    await server.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
