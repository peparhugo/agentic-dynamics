"""Async WebSocket notification server with Redis distribution and SQLite history."""

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
import json
import os
import sqlite3
import threading
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Response


MESSAGE_TYPES = frozenset({"broadcast", "direct", "system", "subscribe", "unsubscribe"})
BROKER_CHANNEL = "notifications:messages"
MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]


class InMemoryBroker:
    """A process-local broker used when Redis hasn't been configured."""

    def __init__(self) -> None:
        self.clients: set[str] = set()
        self.channels: dict[str, set[str]] = defaultdict(set)
        self._handlers: set[MessageHandler] = set()

    async def start(self, handler: MessageHandler) -> None:
        self._handlers.add(handler)

    async def stop(self, handler: MessageHandler) -> None:
        self._handlers.discard(handler)

    async def publish(self, message: dict[str, Any]) -> None:
        await asyncio.gather(*(handler(message) for handler in list(self._handlers)))

    async def add_client(self, client_id: str) -> None:
        self.clients.add(client_id)

    async def remove_client(self, client_id: str) -> None:
        self.clients.discard(client_id)
        for channel in list(self.channels):
            self.channels[channel].discard(client_id)
            if not self.channels[channel]:
                del self.channels[channel]

    async def has_client(self, client_id: str) -> bool:
        return client_id in self.clients

    async def subscribe(self, client_id: str, channel: str) -> None:
        self.channels[channel].add(client_id)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        self.channels[channel].discard(client_id)
        if not self.channels[channel]:
            del self.channels[channel]

    async def channel_members(self, channel: str) -> list[str]:
        return sorted(self.channels.get(channel, set()))

    async def channel_summary(self) -> list[dict[str, Any]]:
        return [{"name": name, "subscriber_count": len(members)} for name, members in sorted(self.channels.items())]


class RedisBroker:
    """Redis pub/sub and Redis-backed connection state shared by server instances."""

    def __init__(self, redis: Any) -> None:
        self.redis = redis
        self._pubsub: Any = None
        self._listener: asyncio.Task[None] | None = None

    async def start(self, handler: MessageHandler) -> None:
        self._pubsub = self.redis.pubsub()
        await self._pubsub.subscribe(BROKER_CHANNEL)

        async def listen() -> None:
            async for event in self._pubsub.listen():
                if event.get("type") != "message":
                    continue
                data = event["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                await handler(json.loads(data))

        self._listener = asyncio.create_task(listen())

    async def stop(self, _handler: MessageHandler) -> None:
        if self._listener is not None:
            self._listener.cancel()
            try:
                await self._listener
            except asyncio.CancelledError:
                pass
            self._listener = None
        if self._pubsub is not None:
            await self._pubsub.unsubscribe(BROKER_CHANNEL)
            await self._pubsub.aclose()
            self._pubsub = None

    async def publish(self, message: dict[str, Any]) -> None:
        await self.redis.publish(BROKER_CHANNEL, json.dumps(message))

    async def add_client(self, client_id: str) -> None:
        await self.redis.sadd("notifications:clients", client_id)

    async def remove_client(self, client_id: str) -> None:
        await self.redis.srem("notifications:clients", client_id)
        for key in await self.redis.smembers("notifications:channels"):
            channel = key.decode() if isinstance(key, bytes) else key
            await self.redis.srem(f"notifications:channel:{channel}", client_id)

    async def has_client(self, client_id: str) -> bool:
        return bool(await self.redis.sismember("notifications:clients", client_id))

    async def subscribe(self, client_id: str, channel: str) -> None:
        await self.redis.sadd("notifications:channels", channel)
        await self.redis.sadd(f"notifications:channel:{channel}", client_id)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        key = f"notifications:channel:{channel}"
        await self.redis.srem(key, client_id)
        if not await self.redis.scard(key):
            await self.redis.srem("notifications:channels", channel)

    async def channel_members(self, channel: str) -> list[str]:
        members = await self.redis.smembers(f"notifications:channel:{channel}")
        return sorted(member.decode() if isinstance(member, bytes) else member for member in members)

    async def channel_summary(self) -> list[dict[str, Any]]:
        names = await self.redis.smembers("notifications:channels")
        result = []
        for raw_name in names:
            name = raw_name.decode() if isinstance(raw_name, bytes) else raw_name
            result.append({"name": name, "subscriber_count": await self.redis.scard(f"notifications:channel:{name}")})
        return sorted(result, key=lambda item: item["name"])


class NotificationServer:
    """Maintains local WebSocket connections and distributes messages through a broker."""

    def __init__(self, broker: InMemoryBroker | RedisBroker | None = None, database_url: str | None = None) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._channels: dict[str, set[str]] = defaultdict(set)
        self._clients_lock = threading.RLock()
        self._server: Server | None = None
        self._broker = broker
        self._database_url = database_url or os.environ.get("DATABASE_URL", ":memory:")
        self._database: sqlite3.Connection | None = None

    @property
    def client_count(self) -> int:
        with self._clients_lock:
            return len(self._clients)

    @property
    def port(self) -> int:
        if self._server is None or not self._server.sockets:
            raise RuntimeError("server is not running")
        return self._server.sockets[0].getsockname()[1]

    async def start(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        if self._server is not None:
            raise RuntimeError("server is already running")
        self._open_database()
        if self._broker is None:
            self._broker = await self._configured_broker()
        await self._broker.start(self._deliver_broker_message)
        self._server = await serve(self._handle_client, host, port, process_request=self._handle_http)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._broker is not None:
            await self._broker.stop(self._deliver_broker_message)
        if self._database is not None:
            self._database.close()
            self._database = None
        with self._clients_lock:
            self._clients.clear()
            self._channels.clear()

    async def broadcast(self, payload: dict[str, Any]) -> None:
        await self._publish("broadcast", payload)

    async def direct(self, client_id: str, payload: dict[str, Any]) -> bool:
        assert self._broker is not None
        if not await self._broker.has_client(client_id):
            return False
        await self._publish("direct", payload)
        return True

    async def system(self, payload: dict[str, Any]) -> None:
        await self._publish("system", payload)

    async def _configured_broker(self) -> InMemoryBroker | RedisBroker:
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            return InMemoryBroker()
        import redis.asyncio as redis

        return RedisBroker(redis.from_url(redis_url))

    def _open_database(self) -> None:
        path = self._database_url
        if path.startswith("sqlite:///"):
            path = path[len("sqlite:///") :]
        self._database = sqlite3.connect(path)
        self._database.execute(
            "CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, channel TEXT, type TEXT NOT NULL, payload TEXT NOT NULL, timestamp TEXT NOT NULL)"
        )
        self._database.commit()

    async def _handle_client(self, connection: ServerConnection) -> None:
        assert self._broker is not None
        client_id = str(uuid4())
        with self._clients_lock:
            self._clients[client_id] = connection
        await self._broker.add_client(client_id)
        try:
            await self._send_to_connections([connection], "system", {"event": "connected", "client_id": client_id})
            async for raw_message in connection:
                await self._handle_message(connection, client_id, raw_message)
        finally:
            with self._clients_lock:
                self._clients.pop(client_id, None)
                for channel in list(self._channels):
                    self._channels[channel].discard(client_id)
                    if not self._channels[channel]:
                        del self._channels[channel]
            await self._broker.remove_client(client_id)

    async def _handle_message(self, connection: ServerConnection, sender_id: str, raw_message: str | bytes) -> None:
        if isinstance(raw_message, bytes):
            await self._send_to_connections([connection], "system", {"event": "error", "message": "messages must be JSON text"})
            return
        try:
            message = json.loads(raw_message)
            message_type = message["type"]
            payload = message["payload"]
            if message_type not in MESSAGE_TYPES or not isinstance(payload, dict):
                raise ValueError
            channel = self._message_channel(message, payload)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            await self._send_to_connections([connection], "system", {"event": "error", "message": "invalid message format"})
            return
        if channel is not None and "channel" not in payload:
            payload = {**payload, "channel": channel}
        if message_type == "subscribe":
            if channel is None:
                await self._send_to_connections([connection], "system", {"event": "error", "message": "channel is required"})
                return
            await self._subscribe(sender_id, channel)
            await self._send_to_connections([connection], "system", {"event": "subscribed", "channel": channel})
        elif message_type == "unsubscribe":
            if channel is None:
                await self._send_to_connections([connection], "system", {"event": "error", "message": "channel is required"})
                return
            await self._unsubscribe(sender_id, channel)
            await self._send_to_connections([connection], "system", {"event": "unsubscribed", "channel": channel})
        elif message_type == "broadcast":
            await self.broadcast({"sender_id": sender_id, **payload})
        elif message_type == "direct":
            recipient_id = payload.get("client_id")
            if not isinstance(recipient_id, str) or not await self.direct(recipient_id, {"sender_id": sender_id, **payload}):
                await self._send_to_connections([connection], "system", {"event": "error", "message": "unknown client_id"})
        else:
            await self.system({"sender_id": sender_id, **payload})

    async def _publish(self, message_type: str, payload: dict[str, Any]) -> None:
        assert self._broker is not None
        message = self._message(message_type, payload)
        self._record(message)
        await self._broker.publish(message)

    async def _deliver_broker_message(self, message: dict[str, Any]) -> None:
        payload = message["payload"]
        if message["type"] == "direct":
            with self._clients_lock:
                connections = [self._clients[payload["client_id"]]] if payload["client_id"] in self._clients else []
        else:
            connections = self._channel_connections(payload)
        await self._send_encoded(connections, message)

    async def _handle_http(self, _connection: ServerConnection, request: Any) -> Response | None:
        assert self._broker is not None
        parsed = urlsplit(request.path)
        if parsed.path == "/health":
            return self._json_response({"connected_clients": self.client_count})
        if parsed.path == "/channels":
            return self._json_response({"channels": await self._broker.channel_summary()})
        if parsed.path.startswith("/channels/") and parsed.path.endswith("/subscribers"):
            name = parsed.path[len("/channels/") : -len("/subscribers")].rstrip("/")
            if not name:
                return None
            return self._json_response({"channel": name, "subscribers": await self._broker.channel_members(name)})
        if parsed.path == "/messages":
            try:
                query = parse_qs(parsed.query)
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
                if limit < 0 or offset < 0:
                    raise ValueError
            except ValueError:
                return self._json_response({"error": "limit and offset must be non-negative integers"}, "400 Bad Request")
            return self._json_response({"messages": self._messages(limit, offset)})
        return None

    def _json_response(self, value: Any, status: str = "200 OK") -> Response:
        body = json.dumps(value).encode("utf-8")
        return Response(int(status[:3]), status[4:], Headers({"Content-Type": "application/json", "Content-Length": str(len(body))}), body)

    def _messages(self, limit: int, offset: int) -> list[dict[str, Any]]:
        assert self._database is not None
        rows = self._database.execute(
            "SELECT id, channel, type, payload, timestamp FROM messages ORDER BY rowid LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
        return [{"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]} for row in rows]

    def _record(self, message: dict[str, Any]) -> None:
        assert self._database is not None
        self._database.execute(
            "INSERT INTO messages (id, channel, type, payload, timestamp) VALUES (?, ?, ?, ?, ?)",
            (message["id"], message["channel"], message["type"], json.dumps(message["payload"]), message["timestamp"]),
        )
        self._database.commit()

    def _message(self, message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"id": str(uuid4()), "channel": payload.get("channel"), "type": message_type, "payload": payload, "timestamp": datetime.now(timezone.utc).isoformat()}

    def _connections(self) -> list[ServerConnection]:
        with self._clients_lock:
            return list(self._clients.values())

    def _channel_connections(self, payload: dict[str, Any]) -> list[ServerConnection]:
        channel = payload.get("channel")
        if channel is None:
            return self._connections()
        with self._clients_lock:
            return [self._clients[client_id] for client_id in self._channels.get(channel, set()) if client_id in self._clients]

    @staticmethod
    def _message_channel(message: dict[str, Any], payload: dict[str, Any]) -> str | None:
        top_level_channel = message.get("channel")
        payload_channel = payload.get("channel")
        if top_level_channel is not None and payload_channel is not None and top_level_channel != payload_channel:
            raise ValueError
        channel = top_level_channel if top_level_channel is not None else payload_channel
        if channel is not None and (not isinstance(channel, str) or not channel):
            raise ValueError
        return channel

    async def _subscribe(self, client_id: str, channel: str) -> None:
        assert self._broker is not None
        with self._clients_lock:
            self._channels[channel].add(client_id)
        await self._broker.subscribe(client_id, channel)

    async def _unsubscribe(self, client_id: str, channel: str) -> None:
        assert self._broker is not None
        with self._clients_lock:
            self._channels[channel].discard(client_id)
            if not self._channels[channel]:
                del self._channels[channel]
        await self._broker.unsubscribe(client_id, channel)

    async def _send_to_connections(self, connections: list[ServerConnection], message_type: str, payload: dict[str, Any]) -> None:
        await self._send_encoded(connections, self._message(message_type, payload))

    async def _send_encoded(self, connections: list[ServerConnection], message: dict[str, Any]) -> None:
        encoded = json.dumps({"type": message["type"], "payload": message["payload"], "timestamp": message["timestamp"]})
        results = await asyncio.gather(*(connection.send(encoded) for connection in connections), return_exceptions=True)
        if any(isinstance(result, Exception) for result in results):
            return


async def main() -> None:
    server = NotificationServer()
    await server.start(host="0.0.0.0", port=8765)
    print("Notification server listening on ws://0.0.0.0:8765")
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
