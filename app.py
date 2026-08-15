"""Async WebSocket notification server with a small health endpoint."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from aiohttp import web
from redis.asyncio import Redis
from redis.exceptions import RedisError
from websockets.asyncio.server import Server, ServerConnection, serve


MESSAGE_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


def timestamp() -> str:
    """Return an RFC 3339 timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat()


class NotificationServer:
    """Own WebSocket clients and route JSON notification messages."""

    def __init__(self, redis_url: str | None = None, database_url: str | None = None) -> None:
        # All access happens on the asyncio event loop; no lock is needed.
        self.clients: dict[str, ServerConnection] = {}
        self.channels: dict[str, set[str]] = {}
        self.websocket_server: Server | None = None
        self.health_runner: web.AppRunner | None = None
        self.websocket_port: int | None = None
        self.health_port: int | None = None
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///messages.db")
        self.instance_id = uuid4().hex
        self.redis: Redis | None = None
        self.redis_pubsub: Any = None
        self.redis_task: asyncio.Task[None] | None = None
        self._redis_enabled = False
        self._database = self._open_database(self.database_url)

    @staticmethod
    def _open_database(database_url: str) -> sqlite3.Connection:
        if database_url == ":memory:":
            path = database_url
        elif database_url.startswith("sqlite:///"):
            path = database_url[10:]
        elif database_url.startswith("sqlite://"):
            path = database_url[9:]
        else:
            path = database_url
        database = sqlite3.connect(path, check_same_thread=False)
        database.row_factory = sqlite3.Row
        database.execute(
            """CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                channel TEXT,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )"""
        )
        database.commit()
        return database

    async def _connect_redis(self) -> None:
        self.redis = Redis.from_url(
            self.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.25,
            socket_timeout=0.5,
        )
        try:
            await asyncio.wait_for(self.redis.ping(), timeout=0.75)
        except (RedisError, OSError, asyncio.TimeoutError):
            await self.redis.aclose()
            self.redis = None
            return
        self._redis_enabled = True
        self.redis_pubsub = self.redis.pubsub()
        await self.redis_pubsub.subscribe("notifications")
        self.redis_task = asyncio.create_task(self._redis_listener())

    async def _redis_listener(self) -> None:
        assert self.redis_pubsub is not None
        try:
            async for item in self.redis_pubsub.listen():
                if item.get("type") != "message":
                    continue
                try:
                    envelope = json.loads(item["data"])
                except (TypeError, json.JSONDecodeError):
                    continue
                message = envelope.get("message")
                if not isinstance(message, dict):
                    continue
                self._persist(message)
                await self._deliver_message(message, envelope.get("target_id"))
        except (asyncio.CancelledError, RedisError):
            return

    async def _publish(self, message: dict[str, Any], target_id: str | None = None) -> None:
        if not self._redis_enabled or self.redis is None:
            await self._deliver_message(message, target_id)
            return
        await self.redis.publish(
            "notifications",
            json.dumps({"source": self.instance_id, "message": message, "target_id": target_id}),
        )

    def _persist(self, message: dict[str, Any]) -> None:
        self._database.execute(
            "INSERT OR IGNORE INTO messages (id, channel, type, payload, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                message["id"],
                message.get("channel"),
                message["type"],
                json.dumps(message["payload"]),
                message["timestamp"],
            ),
        )
        self._database.commit()

    async def _deliver_message(self, message: dict[str, Any], target_id: str | None = None) -> None:
        channel = message.get("channel")
        if target_id is not None:
            client = self.clients.get(target_id)
            if client is not None:
                await client.send(json.dumps(message))
            return
        await self._broadcast(json.dumps(message), channel)

    @property
    def client_count(self) -> int:
        return len(self.clients)

    def _message(
        self, message_type: str, payload: dict[str, Any], channel: str | None = None
    ) -> str:
        message: dict[str, Any] = {
            "type": message_type,
            "payload": payload,
            "timestamp": timestamp(),
        }
        if channel is not None:
            message["channel"] = channel
        return json.dumps(message)

    async def _send_system(self, client: ServerConnection, payload: dict[str, Any]) -> None:
        await client.send(self._message("system", payload))

    async def _broadcast(self, message: str, channel: str | None = None) -> None:
        if channel is None:
            clients = tuple(self.clients.values())
        else:
            clients = tuple(
                self.clients[client_id]
                for client_id in self.channels.get(channel, ())
                if client_id in self.clients
            )
        if not clients:
            return
        results = await asyncio.gather(
            *(client.send(message) for client in clients), return_exceptions=True
        )
        # A failed send is cleaned up by that connection's finally block. This
        # also keeps one stale client from preventing delivery to the others.
        del results

    @staticmethod
    def _channel_from(data: dict[str, Any]) -> str | None:
        channel = data.get("channel")
        if channel is None and isinstance(data.get("payload"), dict):
            channel = data["payload"].get("channel")
        return channel if isinstance(channel, str) and channel else None

    async def _change_subscription(
        self, client_id: str, channel: str, subscribe: bool
    ) -> None:
        subscriptions = self.channels.setdefault(channel, set())
        if subscribe:
            subscriptions.add(client_id)
            if self._redis_enabled and self.redis is not None:
                await self.redis.sadd(f"notification:channel:{channel}", client_id)
        else:
            subscriptions.discard(client_id)
            if self._redis_enabled and self.redis is not None:
                await self.redis.srem(f"notification:channel:{channel}", client_id)
            if not subscriptions:
                self.channels.pop(channel, None)
        client = self.clients.get(client_id)
        if client is not None:
            action = "subscribed" if subscribe else "unsubscribed"
            await self._send_system(client, {action: channel})

    async def _handle_message(self, client_id: str, data: Any) -> None:
        client = self.clients.get(client_id)
        if client is None:
            return
        if not isinstance(data, dict):
            await self._send_system(client, {"error": "message must be a JSON object"})
            return

        message_type = data.get("type")
        payload = data.get("payload")
        if message_type not in MESSAGE_TYPES or (
            message_type not in {"subscribe", "unsubscribe"}
            and not isinstance(payload, dict)
        ):
            await self._send_system(
                client,
                {"error": "message requires a supported type and object payload"},
            )
            return

        if message_type in {"subscribe", "unsubscribe"}:
            channel = self._channel_from(data)
            if channel is None:
                await self._send_system(client, {"error": "channel is required"})
                return
            await self._change_subscription(
                client_id, channel, subscribe=message_type == "subscribe"
            )
            return

        channel = self._channel_from(data)
        if message_type == "direct":
            target_id = payload.get("client_id", payload.get("recipient_id"))
            target_exists = target_id in self.clients
            if self._redis_enabled and self.redis is not None and isinstance(target_id, str):
                target_exists = bool(await self.redis.sismember("notification:clients", target_id))
            if not isinstance(target_id, str) or not target_exists:
                await self._send_system(client, {"error": "target client not found"})
                return
            subscribed = target_id in self.channels.get(channel, ())
            if self._redis_enabled and self.redis is not None and channel is not None:
                subscribed = bool(await self.redis.sismember(f"notification:channel:{channel}", target_id))
            if channel is not None and not subscribed:
                await self._send_system(client, {"error": "target is not subscribed"})
                return
            target_payload = payload.get("message", payload)
            if not isinstance(target_payload, dict):
                await self._send_system(client, {"error": "direct message must be an object"})
                return
            message = self._message_dict("direct", target_payload, channel)
            self._persist(message)
            await self._publish(message, target_id)
            return

        message = self._message_dict(message_type, payload, channel)
        self._persist(message)
        await self._publish(message)

    def _message_dict(
        self, message_type: str, payload: dict[str, Any], channel: str | None = None
    ) -> dict[str, Any]:
        message: dict[str, Any] = {
            "id": uuid4().hex,
            "type": message_type,
            "payload": payload,
            "timestamp": timestamp(),
        }
        if channel is not None:
            message["channel"] = channel
        return message

    async def handler(self, websocket: ServerConnection) -> None:
        client_id = uuid4().hex
        self.clients[client_id] = websocket
        if self._redis_enabled and self.redis is not None:
            await self.redis.sadd("notification:clients", client_id)
        try:
            await self._send_system(websocket, {"client_id": client_id})
            async for raw_message in websocket:
                try:
                    data = json.loads(raw_message)
                except (TypeError, json.JSONDecodeError):
                    await self._send_system(websocket, {"error": "message must be valid JSON"})
                    continue
                await self._handle_message(client_id, data)
        finally:
            self.clients.pop(client_id, None)
            if self._redis_enabled and self.redis is not None:
                await self.redis.srem("notification:clients", client_id)
            for channel, subscribers in tuple(self.channels.items()):
                subscribers.discard(client_id)
                if self._redis_enabled and self.redis is not None:
                    await self.redis.srem(f"notification:channel:{channel}", client_id)
                if not subscribers:
                    self.channels.pop(channel, None)

    async def health(self, request: web.Request) -> web.Response:
        return web.json_response({"connected_clients": self.client_count})

    async def list_channels(self, request: web.Request) -> web.Response:
        channels = [
            {"name": name, "subscriber_count": len(subscribers)}
            for name, subscribers in sorted(self.channels.items())
        ]
        return web.json_response({"channels": channels})

    async def list_subscribers(self, request: web.Request) -> web.Response:
        name = request.match_info["name"]
        subscribers = self.channels.get(name, ())
        if self._redis_enabled and self.redis is not None:
            subscribers = await self.redis.smembers(f"notification:channel:{name}")
        return web.json_response(
            {"channel": name, "subscribers": sorted(subscribers)}
        )

    async def list_messages(self, request: web.Request) -> web.Response:
        try:
            limit = max(0, min(int(request.query.get("limit", "50")), 1000))
            offset = max(0, int(request.query.get("offset", "0")))
        except ValueError:
            raise web.HTTPBadRequest(text="limit and offset must be integers")
        rows = self._database.execute(
            "SELECT id, channel, type, payload, timestamp FROM messages "
            "ORDER BY rowid DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        messages = []
        for row in rows:
            message = dict(row)
            message["payload"] = json.loads(message["payload"])
            messages.append(message)
        return web.json_response({"messages": messages})

    async def start(
        self,
        websocket_host: str = "127.0.0.1",
        websocket_port: int = 8765,
        health_host: str = "127.0.0.1",
        health_port: int = 8080,
    ) -> None:
        """Start both listeners. Use ``stop`` to release their sockets."""
        self.websocket_server = await serve(self.handler, websocket_host, websocket_port)
        self.websocket_port = self.websocket_server.sockets[0].getsockname()[1]
        await self._connect_redis()

        health_app = web.Application()
        health_app.router.add_get("/health", self.health)
        health_app.router.add_get("/channels", self.list_channels)
        health_app.router.add_get("/channels/{name}/subscribers", self.list_subscribers)
        health_app.router.add_get("/messages", self.list_messages)
        self.health_runner = web.AppRunner(health_app)
        await self.health_runner.setup()
        site = web.TCPSite(self.health_runner, health_host, health_port)
        await site.start()
        self.health_port = site._server.sockets[0].getsockname()[1]  # type: ignore[union-attr]

    async def stop(self) -> None:
        if self.redis_task is not None:
            self.redis_task.cancel()
            await asyncio.gather(self.redis_task, return_exceptions=True)
            self.redis_task = None
        if self.redis_pubsub is not None:
            await self.redis_pubsub.aclose()
            self.redis_pubsub = None
        if self.redis is not None:
            await self.redis.aclose()
            self.redis = None
            self._redis_enabled = False
        if self.websocket_server is not None:
            self.websocket_server.close()
            await self.websocket_server.wait_closed()
            self.websocket_server = None
        if self.health_runner is not None:
            await self.health_runner.cleanup()
            self.health_runner = None
        self._database.close()


async def main() -> None:
    server = NotificationServer()
    await server.start()
    print(f"WebSocket server listening on port {server.websocket_port}")
    print(f"Health endpoint listening on port {server.health_port}")
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
