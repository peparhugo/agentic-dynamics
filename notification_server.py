"""Async notification server with pluggable transports."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from redis.asyncio import Redis
from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response


MESSAGE_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class BaseTransport(ABC):
    """Transport contract used by the notification routing layer."""

    def __init__(self) -> None:
        self.clients: dict[str, Any] = {}

    @abstractmethod
    async def on_connect(self, client_id: str, client: Any) -> None:
        """Register a newly connected client."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Remove a disconnected client."""

    @abstractmethod
    async def send_message(self, client_id: str, message: dict[str, Any]) -> None:
        """Send one message to a client."""

    @abstractmethod
    async def broadcast(
        self, message: dict[str, Any], client_ids: list[str] | None = None
    ) -> None:
        """Send a message to all, or to the supplied clients."""

    async def start(self) -> None:
        """Start the transport, if it owns a listener."""

    async def stop(self) -> None:
        """Stop the transport and close its clients."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport contract."""

    def __init__(
        self,
        host: str,
        port: int,
        on_message: Callable[[str, str], Awaitable[None]],
        on_connect_callback: Callable[[str], Awaitable[None]],
        on_disconnect_callback: Callable[[str], Awaitable[None]],
        process_request: Callable[[ServerConnection, Request], Awaitable[Response | None]],
    ) -> None:
        super().__init__()
        self.host = host
        self.port = port
        self._on_message = on_message
        self._on_connect_callback = on_connect_callback
        self._on_disconnect_callback = on_disconnect_callback
        self._process_request = process_request
        self._server: Server | None = None

    async def start(self) -> None:
        self._server = await serve(
            self._handle_client,
            self.host,
            self.port,
            process_request=self._process_request,
        )

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        clients = list(self.clients)
        if clients:
            await asyncio.gather(*(self._close_client(client_id) for client_id in clients))

    async def on_connect(self, client_id: str, client: ServerConnection) -> None:
        self.clients[client_id] = client
        await self._on_connect_callback(client_id)

    async def on_disconnect(self, client_id: str) -> None:
        self.clients.pop(client_id, None)
        await self._on_disconnect_callback(client_id)

    async def send_message(self, client_id: str, message: dict[str, Any]) -> None:
        client = self.clients.get(client_id)
        if client is None:
            return
        try:
            await client.send(json.dumps(message))
        except Exception:
            await self.on_disconnect(client_id)

    async def broadcast(
        self, message: dict[str, Any], client_ids: list[str] | None = None
    ) -> None:
        ids = list(self.clients) if client_ids is None else client_ids
        await asyncio.gather(
            *(self.send_message(client_id, message) for client_id in ids),
            return_exceptions=True,
        )

    async def _close_client(self, client_id: str) -> None:
        client = self.clients.get(client_id)
        if client is not None:
            try:
                await client.close()
            finally:
                await self.on_disconnect(client_id)

    async def _handle_client(self, websocket: ServerConnection) -> None:
        requested_id = parse_qs(urlsplit(websocket.request.path).query).get("client_id", [None])[0]
        client_id = requested_id if isinstance(requested_id, str) and requested_id else uuid.uuid4().hex
        await self.on_connect(client_id, websocket)
        try:
            async for raw_message in websocket:
                await self._on_message(client_id, raw_message)
        finally:
            await self.on_disconnect(client_id)


class NotificationServer:
    """Manage clients and route notification messages through a transport."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        redis_url: str | None = None,
        database_url: str | None = None,
        transport: BaseTransport | None = None,
    ) -> None:
        self.host = host
        self.port = port
        transport_name = os.getenv("TRANSPORT", "websocket").lower()
        if transport is not None:
            self.transport = transport
        elif transport_name == "websocket":
            self.transport = WebSocketTransport(
                host,
                port,
                self._handle_message,
                self._on_connect,
                self._on_disconnect,
                self._process_request,
            )
        else:
            raise ValueError(f"unsupported transport: {transport_name}")
        self._subscriptions: dict[str, set[str]] = {}
        self._client_channels: dict[str, set[str]] = {}
        self.redis_url = redis_url if redis_url is not None else os.getenv("REDIS_URL")
        self.database_url = database_url if database_url is not None else os.getenv(
            "DATABASE_URL", "notification_messages.db"
        )
        self._redis: Redis | None = None
        self._redis_pubsub: Any = None
        self._redis_task: asyncio.Task[None] | None = None
        self._redis_channel = "notifications"

    @property
    def clients(self) -> dict[str, Any]:
        return self.transport.clients

    @property
    def connected_client_count(self) -> int:
        return len(self.clients)

    async def start(self) -> None:
        """Start accepting WebSocket and health-check HTTP connections."""
        self._init_database()
        if self.redis_url:
            self._redis = Redis.from_url(self.redis_url, decode_responses=True)
            try:
                await self._redis.ping()
                self._redis_pubsub = self._redis.pubsub()
                await self._redis_pubsub.subscribe(self._redis_channel)
                self._redis_task = asyncio.create_task(self._consume_redis())
            except Exception:
                await self._close_redis()
        await self.transport.start()

    async def stop(self) -> None:
        """Stop accepting connections and close current clients."""
        await self.transport.stop()
        self._subscriptions.clear()
        self._client_channels.clear()
        await self._close_redis()

    def _database_path(self) -> str:
        value = self.database_url
        if value.startswith("sqlite:///"):
            return value[10:]
        if value.startswith("sqlite://"):
            return value[9:]
        return value

    def _init_database(self) -> None:
        with sqlite3.connect(self._database_path()) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT,
                    type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )"""
            )
            conn.commit()

    def _persist_message(self, message: dict[str, Any]) -> None:
        with sqlite3.connect(self._database_path()) as conn:
            conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (
                    message.get("channel"),
                    message["type"],
                    json.dumps(message.get("payload", {})),
                    message["timestamp"],
                ),
            )
            conn.commit()

    async def _close_redis(self) -> None:
        if self._redis_task is not None:
            self._redis_task.cancel()
            await asyncio.gather(self._redis_task, return_exceptions=True)
            self._redis_task = None
        if self._redis_pubsub is not None:
            await self._redis_pubsub.close()
            self._redis_pubsub = None
        if self._redis is not None:
            await self._redis.close()
            self._redis = None

    async def _consume_redis(self) -> None:
        assert self._redis_pubsub is not None
        try:
            async for event in self._redis_pubsub.listen():
                if event.get("type") != "message":
                    continue
                try:
                    message = json.loads(event["data"])
                except (TypeError, json.JSONDecodeError):
                    continue
                if isinstance(message, dict):
                    await self._deliver(message)
        except asyncio.CancelledError:
            raise
        except Exception:
            # A broker outage must not take down existing WebSocket clients.
            return

    async def _publish(self, message: dict[str, Any]) -> None:
        if self._redis is None:
            await self._deliver(message)
            return
        try:
            await self._redis.publish(self._redis_channel, json.dumps(message))
        except Exception:
            await self._deliver(message)

    async def _deliver(self, message: dict[str, Any]) -> None:
        if message.get("type") == "direct":
            target_id = message.get("target_id") or message.get("payload", {}).get("client_id")
            if isinstance(target_id, str) and target_id in self.clients:
                public_message = {key: value for key, value in message.items() if key != "target_id"}
                await self.transport.send_message(target_id, public_message)
            return
        channel = message.get("channel")
        if channel is None:
            clients = list(self.clients.items())
        else:
            subscriber_ids = self._subscriptions.get(channel, set())
            clients = [
                (client_id, self.clients[client_id])
                for client_id in subscriber_ids
                if client_id in self.clients
            ]
        await self.transport.broadcast(message, [client_id for client_id, _ in clients])

    async def _on_connect(self, client_id: str) -> None:
        await self._restore_client_state(client_id)
        await self.transport.send_message(
            client_id,
            {"type": "system", "payload": {"event": "connected", "client_id": client_id}},
        )

    async def _on_disconnect(self, client_id: str) -> None:
        self._remove_client(client_id)

    def _remove_client(self, client_id: str) -> None:
        self.clients.pop(client_id, None)
        for channel in self._client_channels.pop(client_id, set()):
            subscribers = self._subscriptions.get(channel)
            if subscribers is not None:
                subscribers.discard(client_id)
                if not subscribers:
                    self._subscriptions.pop(channel, None)

    async def _process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        parsed = urlsplit(request.path)
        path = parsed.path
        if path == "/health":
            body_data: Any = {"connected_clients": self.connected_client_count}
        elif path == "/channels":
            body_data = {
                "channels": [
                    {"name": name, "subscriber_count": len(subscribers)}
                    for name, subscribers in sorted(self._subscriptions.items())
                    if subscribers
                ]
            }
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            name = unquote(path[len("/channels/") : -len("/subscribers")]).strip("/")
            body_data = {
                "channel": name,
                "subscribers": sorted(self._subscriptions.get(name, set()) & self.clients.keys()),
            }
        elif path == "/messages":
            params = parse_qs(parsed.query)
            try:
                limit = max(0, min(int(params.get("limit", ["50"])[0]), 1000))
                offset = max(0, int(params.get("offset", ["0"])[0]))
            except ValueError:
                return Response(400, "Bad Request", Headers(), b"invalid pagination")
            with sqlite3.connect(self._database_path()) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT id, channel, type, payload, timestamp FROM messages "
                    "ORDER BY id LIMIT ? OFFSET ?", (limit, offset)
                ).fetchall()
            body_data = []
            for row in rows:
                item = dict(row)
                item["payload"] = json.loads(item["payload"])
                body_data.append(item)
        else:
            return None
        body = json.dumps(body_data).encode()
        return Response(
            200,
            "OK",
            Headers(
                [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(body))),
                ]
            ),
            body,
        )

    async def _handle_message(self, sender_id: str, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(message, dict):
            return
        message_type = message.get("type")
        payload = message.get("payload")
        if message_type not in MESSAGE_TYPES:
            return

        if not isinstance(payload, dict):
            payload = {}
        channel = message.get("channel")
        if not isinstance(channel, str):
            channel = payload.get("channel")
        if not isinstance(channel, str) or not channel.strip():
            channel = None
        else:
            channel = channel.strip()

        if message_type in {"subscribe", "unsubscribe"}:
            if channel is None:
                return
            if message_type == "subscribe":
                self._subscriptions.setdefault(channel, set()).add(sender_id)
                self._client_channels.setdefault(sender_id, set()).add(channel)
                await self._save_client_state(sender_id)
            else:
                subscribers = self._subscriptions.get(channel)
                if subscribers is not None:
                    subscribers.discard(sender_id)
                    if not subscribers:
                        self._subscriptions.pop(channel, None)
                self._client_channels.get(sender_id, set()).discard(channel)
                await self._save_client_state(sender_id)
            return

        outgoing: dict[str, Any] = {
            "type": message_type,
            "payload": payload,
            "timestamp": _timestamp(),
        }
        if channel is not None:
            outgoing["channel"] = channel
            self._persist_message(outgoing)
            await self._publish(outgoing)
        elif message_type == "direct":
            target_id = payload.get("client_id") or message.get("client_id")
            if isinstance(target_id, str):
                outgoing["target_id"] = target_id
                self._persist_message(outgoing)
                await self._publish(outgoing)
        elif message_type in {"broadcast", "system"}:
            self._persist_message(outgoing)
            await self._publish(outgoing)

    async def _save_client_state(self, client_id: str) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.hset(
                f"notification:client:{client_id}",
                mapping={"client_id": client_id, "channels": json.dumps(
                    sorted(self._client_channels.get(client_id, set()))
                )},
            )
        except Exception:
            pass

    async def _restore_client_state(self, client_id: str) -> None:
        if self._redis is None:
            return
        try:
            channels_json = await self._redis.hget(
                f"notification:client:{client_id}", "channels"
            )
            channels = json.loads(channels_json or "[]")
            if isinstance(channels, list):
                for channel in channels:
                    if isinstance(channel, str) and channel:
                        self._subscriptions.setdefault(channel, set()).add(client_id)
                        self._client_channels.setdefault(client_id, set()).add(channel)
        except Exception:
            pass

    async def _broadcast(self, message: dict[str, Any], channel: str | None = None) -> None:
        await self._deliver(message)

async def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = NotificationServer(host, port)
    await server.start()
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        pass
