"""Pluggable notification server.

The core :class:`NotificationServer` is transport-agnostic: it owns the client
registry, message routing, persistence, and the Redis backbone. The wire
protocol is delegated to a :class:`BaseTransport` implementation selected via
the ``TRANSPORT`` environment variable (``websocket`` by default).
"""

from __future__ import annotations

import abc
import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import parse_qs

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from broker import RedisBroker
from storage import MessageStore

SUPPORTED_TYPES = ("broadcast", "direct", "system", "subscribe", "unsubscribe")

REDIS_CHANNEL_PREFIX = "notif:"
BROADCAST_CHANNEL = "notif:broadcast"

DEFAULT_RATE_LIMIT = 100
DEFAULT_MESSAGE_TTL_DAYS = 7
CLEANUP_INTERVAL_SECONDS = 3600

Connection = Any


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_message(message_type: str, payload: Optional[dict] = None) -> dict:
    return {
        "type": message_type,
        "payload": payload if payload is not None else {},
        "timestamp": utcnow_iso(),
    }


def encode_message(message: dict) -> str:
    return json.dumps(message)


class BaseTransport(abc.ABC):
    """Abstract transport that the notification server runs on top of."""

    def __init__(self, server: "NotificationServer") -> None:
        self.server = server

    @property
    @abc.abstractmethod
    def host(self) -> str:
        """Address the transport is bound to."""

    @property
    @abc.abstractmethod
    def port(self) -> int:
        """Port the transport is bound to (after :meth:`start`)."""

    @abc.abstractmethod
    async def start(self) -> None:
        """Bind the transport and begin accepting connections."""

    @abc.abstractmethod
    async def stop(self) -> None:
        """Close the transport and release its listeners."""

    @abc.abstractmethod
    async def on_connect(self, connection: Connection) -> str:
        """Handle a freshly accepted connection and return its client id."""

    @abc.abstractmethod
    async def on_disconnect(self, connection: Connection, client_id: str) -> None:
        """Handle teardown once a connection goes away."""

    @abc.abstractmethod
    async def send_message(self, connection: Connection, message: str) -> None:
        """Deliver an encoded message to a single connection."""

    @abc.abstractmethod
    async def broadcast(self, connections: list[Connection], message: str) -> None:
        """Deliver an encoded message to a set of connections."""


class WebSocketTransport(BaseTransport):
    """WebSocket transport built on the ``websockets`` library."""

    def __init__(self, server: "NotificationServer", host: str, port: int) -> None:
        super().__init__(server)
        self._host = host
        self._port = port
        self._ws_server: Optional[asyncio.Server] = None

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    async def start(self) -> None:
        self._ws_server = await serve(self._handle_connection, self._host, self._port)
        self._port = self._ws_server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._ws_server is not None:
            self._ws_server.close()
            await self._ws_server.wait_closed()
            self._ws_server = None

    async def _handle_connection(self, websocket: ServerConnection) -> None:
        client_id = await self.on_connect(websocket)
        try:
            async for raw in websocket:
                await self.server._handle_incoming(client_id, raw)
        except ConnectionClosed:
            pass
        finally:
            await self.on_disconnect(websocket, client_id)

    async def on_connect(self, connection: Connection) -> str:
        return await self.server.register_connection(connection)

    async def on_disconnect(self, connection: Connection, client_id: str) -> None:
        await self.server.unregister_connection(client_id)

    async def send_message(self, connection: Connection, message: str) -> None:
        await connection.send(message)

    async def broadcast(self, connections: list[Connection], message: str) -> None:
        if connections:
            await asyncio.gather(
                *(connection.send(message) for connection in connections),
                return_exceptions=True,
            )


TRANSPORTS: dict[str, type[BaseTransport]] = {
    "websocket": WebSocketTransport,
    "ws": WebSocketTransport,
}


def create_transport(
    name: str, server: "NotificationServer", host: str, port: int
) -> BaseTransport:
    transport_cls = TRANSPORTS.get((name or "").lower())
    if transport_cls is None:
        raise ValueError(f"Unknown transport: {name!r}")
    return transport_cls(server, host, port)


class ClientRegistry:
    """Registry of connected clients keyed by their unique client id.

    Asyncio runs everything on a single event loop, so plain dict reads and
    writes are always safe and require no locking.
    """

    def __init__(self) -> None:
        self._clients: dict[str, Connection] = {}
        self._subscriptions: dict[str, set[str]] = {}

    def register(self, connection: Connection) -> str:
        client_id = uuid.uuid4().hex
        self._clients[client_id] = connection
        return client_id

    def unregister(self, client_id: str) -> None:
        self._clients.pop(client_id, None)
        self.unsubscribe_all(client_id)

    def get(self, client_id: str) -> Optional[Connection]:
        return self._clients.get(client_id)

    def count(self) -> int:
        return len(self._clients)

    def connections(self) -> list[Connection]:
        return list(self._clients.values())

    def ids(self) -> list[str]:
        return list(self._clients.keys())

    def subscribe(self, client_id: str, channel: str) -> bool:
        if client_id not in self._clients:
            return False
        self._subscriptions.setdefault(channel, set()).add(client_id)
        return True

    def unsubscribe(self, client_id: str, channel: str) -> bool:
        subscribers = self._subscriptions.get(channel)
        if subscribers is None:
            return False
        subscribers.discard(client_id)
        if not subscribers:
            del self._subscriptions[channel]
        return True

    def unsubscribe_all(self, client_id: str) -> None:
        for channel in list(self._subscriptions):
            subscribers = self._subscriptions[channel]
            subscribers.discard(client_id)
            if not subscribers:
                del self._subscriptions[channel]

    def channels(self) -> dict[str, int]:
        return {
            channel: len(subscribers)
            for channel, subscribers in self._subscriptions.items()
        }

    def subscribers(self, channel: str) -> list[str]:
        return sorted(
            client_id
            for client_id in self._subscriptions.get(channel, set())
            if client_id in self._clients
        )

    def channel_connections(self, channel: str) -> list[Connection]:
        return [
            self._clients[client_id]
            for client_id in self._subscriptions.get(channel, set())
            if client_id in self._clients
        ]


class RateLimiter:
    """Per-client message rate limiter.

    When a Redis broker is available the counters live in Redis so the limit
    holds across every server instance. When Redis is unavailable the limiter
    falls back to an in-memory fixed window so existing deployments without a
    Redis backbone keep working.
    """

    WINDOW_SECONDS = 60.0

    def __init__(self, server: "NotificationServer", limit: int) -> None:
        self.server = server
        self.limit = max(0, int(limit))
        self._local: dict[str, tuple[float, int]] = {}

    async def allowed(self, client_id: str) -> bool:
        broker = self.server.broker
        if broker is not None:
            try:
                count = await broker.increment_rate(client_id)
            except Exception:
                return self._allowed_local(client_id)
            return count <= self.limit
        return self._allowed_local(client_id)

    def _allowed_local(self, client_id: str) -> bool:
        now = time.monotonic()
        window_start, count = self._local.get(client_id, (0.0, 0))
        if now - window_start >= self.WINDOW_SECONDS:
            window_start, count = now, 0
        count += 1
        self._local[client_id] = (window_start, count)
        return count <= self.limit


class NotificationServer:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        health_port: int = 8766,
        redis_url: Optional[str] = None,
        database_url: Optional[str] = None,
        transport: Optional[str] = None,
        rate_limit: Optional[int] = None,
        message_ttl_days: Optional[int] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.health_port = health_port
        self.registry = ClientRegistry()
        self.redis_url = (
            redis_url if redis_url is not None else os.environ.get("REDIS_URL")
        )
        database_url = (
            database_url if database_url is not None else os.environ.get("DATABASE_URL")
        )
        if database_url is None:
            database_url = ":memory:"
        self.store = MessageStore(database_url)
        self.broker: Optional[RedisBroker] = (
            RedisBroker(self.redis_url) if self.redis_url else None
        )
        transport_name = (
            transport if transport is not None else os.environ.get("TRANSPORT", "websocket")
        )
        self.transport = create_transport(transport_name, self, self.host, self.port)
        self._health_server: Optional[asyncio.Server] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self.rate_limit = self._resolve_int_env("RATE_LIMIT", rate_limit, DEFAULT_RATE_LIMIT)
        self.message_ttl_days = self._resolve_int_env(
            "MESSAGE_TTL_DAYS", message_ttl_days, DEFAULT_MESSAGE_TTL_DAYS
        )
        self.rate_limiter = RateLimiter(self, self.rate_limit)

    @staticmethod
    def _resolve_int_env(
        name: str, explicit: Optional[int], default: int
    ) -> int:
        if explicit is not None:
            return int(explicit)
        raw = os.environ.get(name)
        if raw is None:
            return default
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    async def start(self) -> "NotificationServer":
        await self.transport.start()
        self.port = self.transport.port
        self._health_server = await asyncio.start_server(
            self._handle_http, self.host, self.health_port
        )
        self.health_port = self._health_server.sockets[0].getsockname()[1]
        if self.broker is not None:
            try:
                await self.broker.connect()
                await self.broker.start_listener(self._deliver_from_redis)
            except Exception:
                self.broker = None
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        return self

    async def stop(self) -> None:
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except (asyncio.CancelledError, Exception):
                pass
            self._cleanup_task = None
        if self.broker is not None:
            await self.broker.close()
            self.broker = None
        await self.transport.stop()
        if self._health_server is not None:
            self._health_server.close()
            await self._health_server.wait_closed()
            self._health_server = None
        self.store.close()

    async def _cleanup_loop(self) -> None:
        while True:
            try:
                await self.run_cleanup()
            except Exception:
                pass
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)

    async def run_cleanup(self) -> int:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self.store.cleanup_older_than, self.message_ttl_days
        )

    async def __aenter__(self) -> "NotificationServer":
        return await self.start()

    async def __aexit__(self, *exc) -> None:
        await self.stop()

    async def register_connection(self, connection: Connection) -> str:
        client_id = self.registry.register(connection)
        await self._on_client_registered(client_id)
        await self.transport.send_message(
            connection, encode_message(make_message("system", {"client_id": client_id}))
        )
        return client_id

    async def unregister_connection(self, client_id: str) -> None:
        self.registry.unregister(client_id)
        await self._on_client_unregistered(client_id)

    async def _handle_incoming(self, client_id: str, raw: str) -> None:
        if not await self.rate_limiter.allowed(client_id):
            connection = self.registry.get(client_id)
            if connection is not None:
                await self.transport.send_message(
                    connection,
                    encode_message(
                        make_message(
                            "error",
                            {
                                "code": "rate_limited",
                                "message": "rate limit exceeded",
                            },
                        )
                    ),
                )
            return
        try:
            message = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return
        if not isinstance(message, dict):
            return
        message_type = message.get("type", "broadcast")
        payload = message.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        channel = message.get("channel")
        if channel is None:
            channel = payload.get("channel")
        if message_type == "subscribe":
            if channel:
                await self.subscribe(client_id, channel)
        elif message_type == "unsubscribe":
            if channel:
                await self.unsubscribe(client_id, channel)
        elif message_type == "broadcast":
            if channel:
                await self.publish_to_channel(channel, "broadcast", payload)
            else:
                await self.broadcast("broadcast", payload)
        elif message_type == "direct":
            target = payload.get("to")
            if target:
                await self.send_to(target, "direct", payload)

    async def broadcast(
        self, message_type: str = "broadcast", payload: Optional[dict] = None
    ) -> int:
        message = make_message(message_type, payload)
        encoded = encode_message(message)
        targets = self.registry.connections()
        await self.transport.broadcast(targets, encoded)
        await self._record_and_publish(
            "", message_type, message["payload"], message["timestamp"]
        )
        return len(targets)

    async def send_to(
        self, client_id: str, message_type: str = "direct", payload: Optional[dict] = None
    ) -> bool:
        message = make_message(message_type, payload)
        connection = self.registry.get(client_id)
        if connection is not None:
            await self.transport.send_message(connection, encode_message(message))
        await self._record_and_publish(
            client_id, message_type, message["payload"], message["timestamp"]
        )
        return connection is not None

    async def subscribe(self, client_id: str, channel: str) -> bool:
        if not channel:
            return False
        subscribed = self.registry.subscribe(client_id, channel)
        if subscribed and self.broker is not None:
            await self.broker.subscribe_client(client_id, channel)
        return subscribed

    async def unsubscribe(self, client_id: str, channel: str) -> bool:
        if not channel:
            return False
        unsubscribed = self.registry.unsubscribe(client_id, channel)
        if unsubscribed and self.broker is not None:
            await self.broker.unsubscribe_client(client_id, channel)
        return unsubscribed

    async def publish_to_channel(
        self, channel: str, message_type: str = "broadcast", payload: Optional[dict] = None
    ) -> int:
        message = make_message(message_type, payload)
        encoded = encode_message(message)
        targets = self.registry.channel_connections(channel)
        await self.transport.broadcast(targets, encoded)
        await self._record_and_publish(
            channel, message_type, message["payload"], message["timestamp"]
        )
        return len(targets)

    async def _record_and_publish(
        self,
        channel: str,
        message_type: str,
        payload: Optional[dict],
        timestamp: str,
    ) -> None:
        self.store.add(channel, message_type, payload, timestamp)
        if self.broker is not None:
            await self.broker.publish(channel, message_type, payload, timestamp)

    async def _deliver_from_redis(self, redis_channel: str, data: dict) -> None:
        message = make_message(data.get("type", "broadcast"), data.get("payload"))
        message["timestamp"] = data.get("timestamp", message["timestamp"])
        encoded = encode_message(message)
        if redis_channel == BROADCAST_CHANNEL:
            targets = self.registry.connections()
        elif redis_channel.startswith(f"{REDIS_CHANNEL_PREFIX}channel:"):
            channel = redis_channel[len(f"{REDIS_CHANNEL_PREFIX}channel:"):]
            targets = self.registry.channel_connections(channel)
        elif redis_channel.startswith(f"{REDIS_CHANNEL_PREFIX}direct:"):
            client_id = redis_channel[len(f"{REDIS_CHANNEL_PREFIX}direct:"):]
            connection = self.registry.get(client_id)
            targets = [connection] if connection is not None else []
        else:
            targets = []
        await self.transport.broadcast(targets, encoded)

    async def _on_client_registered(self, client_id: str) -> None:
        if self.broker is not None:
            await self.broker.register_client(client_id)

    async def _on_client_unregistered(self, client_id: str) -> None:
        if self.broker is not None:
            await self.broker.unregister_client(client_id)

    async def _handle_http(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=10)
            if not request_line:
                return
            parts = request_line.decode("latin-1").strip().split()
            method = parts[0] if parts else ""
            raw_path = parts[1] if len(parts) > 1 else ""
            if "?" in raw_path:
                path, _, query_string = raw_path.partition("?")
            else:
                path, query_string = raw_path, ""
            params = parse_qs(query_string)
            while True:
                line = await reader.readline()
                if not line or line in (b"\r\n", b"\n"):
                    break
            if method == "GET" and path == "/health":
                status = "200 OK"
                body = json.dumps(
                    {"status": "ok", "connected": self.registry.count()}
                ).encode("utf-8")
            elif method == "GET" and path == "/channels":
                status = "200 OK"
                body = json.dumps(self.registry.channels()).encode("utf-8")
            elif method == "GET" and path == "/messages":
                try:
                    limit = int(params.get("limit", ["50"])[0])
                except (ValueError, IndexError):
                    limit = 50
                try:
                    offset = int(params.get("offset", ["0"])[0])
                except (ValueError, IndexError):
                    offset = 0
                status = "200 OK"
                body = json.dumps(self.store.query(limit=limit, offset=offset)).encode(
                    "utf-8"
                )
            elif method == "GET" and path == "/history":
                channel = params.get("channel", [None])[0]
                since = params.get("since", [None])[0]
                try:
                    limit = int(params.get("limit", ["50"])[0])
                except (ValueError, IndexError):
                    limit = 50
                messages, has_more = self.store.history(
                    channel=channel, since=since, limit=limit
                )
                status = "200 OK"
                body = json.dumps(
                    {"messages": messages, "has_more": has_more}
                ).encode("utf-8")
            elif (
                method == "GET"
                and path.startswith("/channels/")
                and path.endswith("/subscribers")
            ):
                channel_name = path[len("/channels/"):-len("/subscribers")]
                status = "200 OK"
                body = json.dumps(self.registry.subscribers(channel_name)).encode("utf-8")
            else:
                status = "404 Not Found"
                body = json.dumps({"error": "not found"}).encode("utf-8")
            response = (
                f"HTTP/1.1 {status}\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode("latin-1") + body
            writer.write(response)
            await writer.drain()
        except (asyncio.TimeoutError, ConnectionError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass

    def run(self) -> None:
        asyncio.run(self._run_forever())

    async def _run_forever(self) -> None:
        await self.start()
        try:
            await asyncio.Future()
        finally:
            await self.stop()


if __name__ == "__main__":
    NotificationServer().run()
