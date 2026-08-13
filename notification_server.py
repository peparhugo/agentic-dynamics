"""
Notification server with a pluggable transport layer.

- Accepts client connections through a swappable `Transport`, assigns each
  client a unique ID.
- Supports broadcast / direct / system / subscribe / unsubscribe JSON messages.
- Clients can subscribe to named channels; a "broadcast" message carrying a
  "channel" field in its payload is delivered only to that channel's
  subscribers, while one without a channel still goes to every client.
- Cleans up clients (and their channel subscriptions) on disconnect.
- Exposes plain HTTP endpoints (served on the same port, intercepted before
  the WebSocket handshake): GET /health, GET /channels,
  GET /channels/{name}/subscribers, and GET /messages.

`NotificationServer` holds all of that core notification logic and never
touches a socket directly: it talks to clients only through a `BaseTransport`
(register/unregister a connection, send to one client, broadcast to all).
`WebSocketTransport` is the built-in implementation and the default; other
transports (SSE, long-polling, raw TCP, ...) can be added by subclassing
`BaseTransport` without changing `NotificationServer` at all. The transport
in use is selected by the `TRANSPORT` env var.

Redis pub/sub is the message backbone: "broadcast" and "direct" messages are
never delivered straight from the socket handler. Instead they are published
to Redis, and a background worker task (subscribed to the relevant Redis
channels) receives them and delivers to whichever clients are connected to
*this* process. That indirection is what lets multiple server processes
share one notification stream — a broadcast published by one instance is
delivered by every instance's worker, including the instance that published
it. Client connection ownership (which server instance a client is attached
to) and channel membership are mirrored into Redis so that direct messages
can be routed to the right instance even when the target client is not
connected locally.

All broadcast/direct messages are additionally persisted to SQLite for
history, retrievable via GET /messages?limit=&offset=.
"""

from __future__ import annotations

import abc
import asyncio
import contextlib
import json
import os
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any, Optional
from urllib.parse import parse_qs, unquote, urlsplit

import redis.asyncio as aioredis
import websockets
import websockets.legacy.server as legacy_server
from websockets.legacy.server import WebSocketServerProtocol

MESSAGE_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}

CHANNEL_SUBSCRIBERS_PATH = re.compile(r"^/channels/([^/]+)/subscribers$")

DEFAULT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_DATABASE_URL = "notifications.db"
DEFAULT_TRANSPORT = "websocket"

# Redis key/channel naming.
REDIS_GLOBAL_CHANNEL = "notify:global"
REDIS_CLIENTS_HASH = "notify:clients"


def redis_channel_key(channel: str) -> str:
    return f"notify:chan:{channel}"


def redis_direct_key(server_id: str) -> str:
    return f"notify:direct:{server_id}"


def redis_instance_key(server_id: str) -> str:
    return f"notify:instance:{server_id}"


def redis_client_channels_key(client_id: str) -> str:
    return f"notify:client_channels:{client_id}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_message(msg_type: str, payload: dict) -> dict:
    return {"type": msg_type, "payload": payload, "timestamp": utc_now_iso()}


class ProtocolError(Exception):
    """Raised when an incoming message does not match the expected format."""


def parse_message(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ProtocolError(f"invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ProtocolError("message must be a JSON object")

    msg_type = data.get("type")
    if msg_type not in MESSAGE_TYPES:
        raise ProtocolError(
            f"unsupported type {msg_type!r}; expected one of {sorted(MESSAGE_TYPES)}"
        )

    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise ProtocolError("payload must be a JSON object")

    return {"type": msg_type, "payload": payload}


def _parse_int(raw: Optional[str], default: int, minimum: int, maximum: Optional[int] = None) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    if value < minimum:
        return minimum
    if maximum is not None and value > maximum:
        return maximum
    return value


@dataclass
class ClientRegistry:
    """Thread-safe registry mapping client IDs to their live connection object."""

    _clients: dict = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, client_id: str, connection: Any) -> None:
        with self._lock:
            self._clients[client_id] = connection

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str) -> Optional[Any]:
        with self._lock:
            return self._clients.get(client_id)

    def count(self) -> int:
        with self._lock:
            return len(self._clients)

    def snapshot(self) -> list:
        with self._lock:
            return list(self._clients.items())


@dataclass
class ChannelRegistry:
    """Thread-safe registry mapping channel names to sets of subscribed client IDs."""

    _channels: dict = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def subscribe(self, channel: str, client_id: str) -> None:
        with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, channel: str, client_id: str) -> None:
        with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    def unsubscribe_all(self, client_id: str) -> None:
        with self._lock:
            for channel in list(self._channels.keys()):
                subscribers = self._channels[channel]
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[channel]

    def subscribers(self, channel: str) -> list:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    def channels_of(self, client_id: str) -> list:
        with self._lock:
            return sorted(name for name, subs in self._channels.items() if client_id in subs)

    def channel_counts(self) -> dict:
        with self._lock:
            return {name: len(subs) for name, subs in self._channels.items()}


class RedisConnectionState:
    """Mirrors client connection ownership and channel membership into Redis.

    This is what lets connection state outlive a single server process: which
    instance a client is attached to (used to route direct messages to the
    right process) and which channels it has joined are recorded in Redis,
    not just in this process's memory.
    """

    def __init__(self, redis_client: "aioredis.Redis", server_id: str):
        self.redis = redis_client
        self.server_id = server_id

    async def register_client(self, client_id: str) -> None:
        await self.redis.hset(REDIS_CLIENTS_HASH, client_id, self.server_id)
        await self.redis.sadd(redis_instance_key(self.server_id), client_id)

    async def unregister_client(self, client_id: str) -> None:
        await self.redis.hdel(REDIS_CLIENTS_HASH, client_id)
        await self.redis.srem(redis_instance_key(self.server_id), client_id)
        await self.redis.delete(redis_client_channels_key(client_id))

    async def owner_of(self, client_id: str) -> Optional[str]:
        return await self.redis.hget(REDIS_CLIENTS_HASH, client_id)

    async def add_channel(self, client_id: str, channel: str) -> None:
        await self.redis.sadd(redis_client_channels_key(client_id), channel)

    async def remove_channel(self, client_id: str, channel: str) -> None:
        await self.redis.srem(redis_client_channels_key(client_id), channel)

    async def channels_of(self, client_id: str) -> set:
        return set(await self.redis.smembers(redis_client_channels_key(client_id)))

    async def clear_instance(self) -> None:
        instance_key = redis_instance_key(self.server_id)
        client_ids = await self.redis.smembers(instance_key)
        for client_id in client_ids:
            await self.redis.hdel(REDIS_CLIENTS_HASH, client_id)
            await self.redis.delete(redis_client_channels_key(client_id))
        await self.redis.delete(instance_key)


@dataclass
class MessageStore:
    """SQLite-backed history of persisted (broadcast/direct) messages."""

    database_url: str
    _conn: sqlite3.Connection = field(init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        self._conn = sqlite3.connect(self.database_url, check_same_thread=False)
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT,
                    type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
                """
            )
            self._conn.commit()

    def save(self, channel: Optional[str], msg_type: str, payload: dict, timestamp: str) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (channel, msg_type, json.dumps(payload), timestamp),
            )
            self._conn.commit()
            return cursor.lastrowid

    def fetch(self, limit: int, offset: int) -> list:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [
            {
                "id": row[0],
                "channel": row[1],
                "type": row[2],
                "payload": json.loads(row[3]),
                "timestamp": row[4],
            }
            for row in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class BaseTransport(abc.ABC):
    """Abstract interface between `NotificationServer` and the wire protocol
    that actually carries messages to/from clients.

    The core notification logic (dispatch, channel subscriptions, Redis
    fan-out, persistence) never touches a socket directly — it only calls
    these methods. A new transport (SSE, long-polling, raw TCP, ...) plugs in
    by subclassing `BaseTransport` and registering itself in
    `TRANSPORT_REGISTRY`; `NotificationServer` needs no changes.
    """

    def __init__(self, server: "NotificationServer", host: str = "localhost", port: int = 8765):
        self.server = server
        self.host = host
        self.port = port

    @abc.abstractmethod
    async def start(self) -> None:
        """Begin accepting connections."""

    @abc.abstractmethod
    async def stop(self) -> None:
        """Stop accepting connections and release any resources held."""

    @abc.abstractmethod
    async def on_connect(self, client_id: str, connection: Any) -> None:
        """Register a newly accepted `connection` under `client_id`."""

    @abc.abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Forget the connection previously registered under `client_id`."""

    @abc.abstractmethod
    async def send_message(self, client_id: str, message: dict) -> bool:
        """Deliver `message` to the single client `client_id` if it is still
        locally connected to this transport. Returns whether it was sent."""

    @abc.abstractmethod
    async def broadcast(self, message: dict, exclude: Optional[str] = None) -> None:
        """Deliver `message` to every client locally connected to this
        transport, except `exclude`."""

    @abc.abstractmethod
    def connected_count(self) -> int:
        """Number of clients currently connected to this transport."""


class WebSocketTransport(BaseTransport):
    """Default transport: serves the WebSocket protocol, plus a handful of
    plain HTTP endpoints intercepted on the same port before the handshake."""

    def __init__(self, server: "NotificationServer", host: str = "localhost", port: int = 8765):
        super().__init__(server, host, port)
        self.registry = ClientRegistry()
        self._server: Optional[websockets.WebSocketServer] = None

    async def on_connect(self, client_id: str, connection: WebSocketServerProtocol) -> None:
        self.registry.add(client_id, connection)

    async def on_disconnect(self, client_id: str) -> None:
        self.registry.remove(client_id)

    def connected_count(self) -> int:
        return self.registry.count()

    async def send_message(self, client_id: str, message: dict) -> bool:
        websocket = self.registry.get(client_id)
        if websocket is None:
            return False
        try:
            await websocket.send(json.dumps(message))
            return True
        except websockets.ConnectionClosed:
            return False

    async def broadcast(self, message: dict, exclude: Optional[str] = None) -> None:
        data = json.dumps(message)
        for client_id, websocket in self.registry.snapshot():
            if client_id == exclude:
                continue
            try:
                await websocket.send(data)
            except websockets.ConnectionClosed:
                pass

    async def _handle_connection(self, websocket: WebSocketServerProtocol) -> None:
        client_id = await self.server.register(websocket)
        try:
            await self.server.handle_client_connected(client_id)
            async for raw in websocket:
                await self.server.handle_client_message(client_id, raw)
        except websockets.ConnectionClosed:
            pass
        finally:
            await self.server.handle_client_disconnected(client_id)

    async def start(self) -> None:
        self._server = await legacy_server.serve(
            self._handle_connection,
            self.host,
            self.port,
            process_request=self.server.process_request,
        )

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None


TRANSPORT_REGISTRY: dict = {
    "websocket": WebSocketTransport,
}


def create_transport(server: "NotificationServer", host: str, port: int) -> BaseTransport:
    name = os.environ.get("TRANSPORT", DEFAULT_TRANSPORT).lower()
    try:
        transport_cls = TRANSPORT_REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"unknown TRANSPORT {name!r}; expected one of {sorted(TRANSPORT_REGISTRY)}"
        ) from None
    return transport_cls(server, host=host, port=port)


class NotificationServer:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8765,
        redis_url: Optional[str] = None,
        database_url: Optional[str] = None,
        redis_client: Optional["aioredis.Redis"] = None,
        transport: Optional[BaseTransport] = None,
    ):
        self.host = host
        self.port = port
        self.channels = ChannelRegistry()

        self.server_id = str(uuid.uuid4())

        self.redis_url = redis_url or os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)
        self._owns_redis = redis_client is None
        self.redis = redis_client or aioredis.from_url(self.redis_url, decode_responses=True)
        self.state = RedisConnectionState(self.redis, self.server_id)

        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
        self.messages = MessageStore(self.database_url)

        self.transport = transport or create_transport(self, self.host, self.port)

        self._pubsub: Optional["aioredis.client.PubSub"] = None
        self._worker_task: Optional[asyncio.Task] = None
        self._worker_ready: Optional[asyncio.Event] = None
        self._sub_commands: asyncio.Queue = asyncio.Queue()
        self._active_redis_channels: set = set()

    @property
    def registry(self):
        """Backwards-compatible view onto the active transport's local
        connection registry (present on `WebSocketTransport`)."""
        return self.transport.registry

    # ── Client / channel bookkeeping (local + mirrored to Redis) ────────

    async def register(self, connection: Any) -> str:
        client_id = str(uuid.uuid4())
        await self.transport.on_connect(client_id, connection)
        await self.state.register_client(client_id)
        return client_id

    async def unregister(self, client_id: str) -> None:
        await self.transport.on_disconnect(client_id)
        await self.state.unregister_client(client_id)

    async def send_to(self, client_id: str, message: dict) -> bool:
        return await self.transport.send_message(client_id, message)

    async def broadcast(self, message: dict, exclude: Optional[str] = None) -> None:
        """Deliver to every *locally* connected client. Used both for local-only
        system events and by the Redis worker when relaying a published message."""
        await self.transport.broadcast(message, exclude=exclude)

    async def broadcast_to_channel(
        self, channel: str, message: dict, exclude: Optional[str] = None
    ) -> None:
        """Deliver to locally connected subscribers of `channel`."""
        for client_id in self.channels.subscribers(channel):
            if client_id == exclude:
                continue
            await self.transport.send_message(client_id, message)

    # ── Redis publish helpers (the "server publishes" half of the backbone) ──

    async def publish_broadcast(self, message: dict) -> None:
        await self.redis.publish(REDIS_GLOBAL_CHANNEL, json.dumps(message))

    async def publish_channel_broadcast(self, channel: str, message: dict) -> None:
        await self.redis.publish(redis_channel_key(channel), json.dumps(message))

    async def publish_direct(self, server_id: str, target_id: str, message: dict) -> None:
        envelope = {**message, "_target": target_id}
        await self.redis.publish(redis_direct_key(server_id), json.dumps(envelope))

    async def route_direct(self, target_id: str, message: dict) -> bool:
        """Deliver a direct message, locally if possible, otherwise via Redis to
        whichever instance owns the target client. Returns False if the target
        client is not known to exist anywhere."""
        delivered = await self.send_to(target_id, message)
        if delivered:
            return True
        owner = await self.state.owner_of(target_id)
        if owner is None:
            return False
        if owner == self.server_id:
            # Registered to us but the socket is gone (e.g. mid-disconnect).
            return False
        await self.publish_direct(owner, target_id, message)
        return True

    # ── Redis subscribe/unsubscribe bookkeeping (the "workers subscribe" half) ──

    async def _ensure_channel_subscription(self, redis_channel: str) -> None:
        """Subscribe the worker to `redis_channel` and wait for it to actually
        take effect, so callers can rely on messages published right after
        this returns being seen (avoids a subscribe/publish race)."""
        if redis_channel in self._active_redis_channels:
            return
        self._active_redis_channels.add(redis_channel)
        done = asyncio.get_running_loop().create_future()
        await self._sub_commands.put(("subscribe", redis_channel, done))
        await done

    async def _maybe_drop_channel_subscription(self, redis_channel: str) -> None:
        if redis_channel not in self._active_redis_channels:
            return
        self._active_redis_channels.discard(redis_channel)
        done = asyncio.get_running_loop().create_future()
        await self._sub_commands.put(("unsubscribe", redis_channel, done))
        await done

    async def _redis_worker(self) -> None:
        """Background task: subscribes to Redis channels and delivers messages
        to locally-connected clients as they arrive."""
        self._pubsub = self.redis.pubsub()
        await self._pubsub.subscribe(REDIS_GLOBAL_CHANNEL, redis_direct_key(self.server_id))
        self._worker_ready.set()
        try:
            while True:
                while not self._sub_commands.empty():
                    action, redis_channel, done = await self._sub_commands.get()
                    try:
                        if action == "subscribe":
                            await self._pubsub.subscribe(redis_channel)
                        else:
                            await self._pubsub.unsubscribe(redis_channel)
                    finally:
                        done.set_result(None)
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=0.02
                )
                if message is None:
                    continue
                await self._handle_redis_message(message["channel"], message["data"])
        except asyncio.CancelledError:
            pass
        finally:
            await self._pubsub.close()

    async def _handle_redis_message(self, redis_channel: str, data: Any) -> None:
        try:
            payload = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return

        if redis_channel == REDIS_GLOBAL_CHANNEL:
            await self.broadcast(payload)
        elif redis_channel == redis_direct_key(self.server_id):
            target_id = payload.pop("_target", None)
            if target_id:
                await self.send_to(target_id, payload)
        elif redis_channel.startswith("notify:chan:"):
            channel = redis_channel[len("notify:chan:"):]
            await self.broadcast_to_channel(channel, payload)

    # ── Persistence ───────────────────────────────────────────────────

    async def _persist_message(
        self, channel: Optional[str], msg_type: str, payload: dict, timestamp: str
    ) -> None:
        await asyncio.to_thread(self.messages.save, channel, msg_type, payload, timestamp)

    # ── Dispatch ──────────────────────────────────────────────────────

    async def _dispatch(self, client_id: str, message: dict) -> None:
        msg_type = message["type"]
        payload = message["payload"]

        if msg_type == "broadcast":
            channel = payload.get("channel")
            outgoing = make_message("broadcast", payload)
            await self._persist_message(channel, "broadcast", payload, outgoing["timestamp"])
            if channel:
                await self.publish_channel_broadcast(channel, outgoing)
            else:
                await self.publish_broadcast(outgoing)

        elif msg_type == "subscribe":
            channel = payload.get("channel")
            if not isinstance(channel, str) or not channel:
                await self.send_to(
                    client_id,
                    make_message("system", {"error": "subscribe requires payload.channel"}),
                )
                return
            self.channels.subscribe(channel, client_id)
            await self.state.add_channel(client_id, channel)
            await self._ensure_channel_subscription(redis_channel_key(channel))
            await self.send_to(
                client_id, make_message("system", {"event": "subscribed", "channel": channel})
            )

        elif msg_type == "unsubscribe":
            channel = payload.get("channel")
            if not isinstance(channel, str) or not channel:
                await self.send_to(
                    client_id,
                    make_message("system", {"error": "unsubscribe requires payload.channel"}),
                )
                return
            self.channels.unsubscribe(channel, client_id)
            await self.state.remove_channel(client_id, channel)
            if not self.channels.subscribers(channel):
                await self._maybe_drop_channel_subscription(redis_channel_key(channel))
            await self.send_to(
                client_id, make_message("system", {"event": "unsubscribed", "channel": channel})
            )

        elif msg_type == "direct":
            target_id = payload.get("target")
            if not target_id:
                await self.send_to(
                    client_id,
                    make_message("system", {"error": "direct message requires payload.target"}),
                )
                return
            outgoing = make_message("direct", {"from": client_id, "data": payload.get("data")})
            await self._persist_message(None, "direct", outgoing["payload"], outgoing["timestamp"])
            delivered = await self.route_direct(target_id, outgoing)
            if not delivered:
                await self.send_to(
                    client_id,
                    make_message("system", {"error": f"client {target_id} not found"}),
                )

        elif msg_type == "system":
            # Clients may not originate system messages; echo back a rejection.
            await self.send_to(
                client_id,
                make_message("system", {"error": "clients cannot send system messages"}),
            )

    # ── Connection lifecycle (invoked by the active transport) ──────────

    async def handle_client_connected(self, client_id: str) -> None:
        await self.send_to(
            client_id, make_message("system", {"event": "connected", "client_id": client_id})
        )
        await self.broadcast(
            make_message("system", {"event": "client_joined", "client_id": client_id}),
            exclude=client_id,
        )

    async def handle_client_message(self, client_id: str, raw: str) -> None:
        try:
            message = parse_message(raw)
        except ProtocolError as exc:
            await self.send_to(client_id, make_message("system", {"error": str(exc)}))
            return
        await self._dispatch(client_id, message)

    async def handle_client_disconnected(self, client_id: str) -> None:
        client_channels = self.channels.channels_of(client_id)
        await self.unregister(client_id)
        self.channels.unsubscribe_all(client_id)
        for channel in client_channels:
            if not self.channels.subscribers(channel):
                await self._maybe_drop_channel_subscription(redis_channel_key(channel))
        await self.broadcast(
            make_message("system", {"event": "client_left", "client_id": client_id})
        )

    async def process_request(self, path: str, request_headers) -> Optional[tuple]:
        split = urlsplit(path)
        route = split.path
        query = parse_qs(split.query)

        if route == "/health":
            body = json.dumps({"connected_clients": self.transport.connected_count()}).encode()
            headers = [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
            return HTTPStatus.OK, headers, body

        if route == "/channels":
            counts = self.channels.channel_counts()
            body = json.dumps(
                {
                    "channels": [
                        {"name": name, "subscribers": count}
                        for name, count in sorted(counts.items())
                    ]
                }
            ).encode()
            headers = [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
            return HTTPStatus.OK, headers, body

        if route == "/messages":
            limit = _parse_int(query.get("limit", [None])[0], default=50, minimum=1, maximum=500)
            offset = _parse_int(query.get("offset", [None])[0], default=0, minimum=0)
            messages = await asyncio.to_thread(self.messages.fetch, limit, offset)
            body = json.dumps(
                {"messages": messages, "limit": limit, "offset": offset}
            ).encode()
            headers = [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
            return HTTPStatus.OK, headers, body

        match = CHANNEL_SUBSCRIBERS_PATH.match(route)
        if match:
            channel = unquote(match.group(1))
            subscribers = self.channels.subscribers(channel)
            body = json.dumps({"channel": channel, "subscribers": subscribers}).encode()
            headers = [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
            return HTTPStatus.OK, headers, body

        return None

    async def start(self) -> BaseTransport:
        self._worker_ready = asyncio.Event()
        self._worker_task = asyncio.create_task(self._redis_worker())
        await self._worker_ready.wait()
        await self.transport.start()
        return self.transport

    async def stop(self) -> None:
        await self.transport.stop()
        if self._worker_task is not None:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
            self._worker_task = None
        await self.state.clear_instance()
        if self._owns_redis:
            await self.redis.close()
        await asyncio.to_thread(self.messages.close)


async def main() -> None:
    server = NotificationServer(host="0.0.0.0", port=8765)
    await server.start()
    transport_name = type(server.transport).__name__
    print(f"Notification server ({transport_name}) listening on {server.host}:{server.port}")
    await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
