"""
WebSocket notification server.

Accepts WebSocket connections, assigns each client a unique ID, supports
broadcast / direct / system messages, and exposes a health endpoint both as a
WebSocket 'system' message and via a plain HTTP listener running in a separate
thread (thread-safety is guaranteed by a threading.Lock around the registry).

Channels: clients may subscribe/unsubscribe to named channels. Messages that
carry a 'channel' field are routed only to the subscribers of that channel;
messages without a channel broadcast to every connected client. The HTTP
listener also exposes GET /channels and GET /channels/{name}/subscribers.

Redis backbone: when a REDIS_URL is configured (or a redis client is injected)
every distributed message is published to a shared Redis pub/sub channel. Each
server instance subscribes to that channel and delivers remote messages to its
own local clients, so multiple server instances share one message backbone.
Client connection state is mirrored into Redis so it survives server restarts.

Persistence: every distributed message is stored in a SQLite database
configured with DATABASE_URL, queryable via GET /messages?limit=&offset=.

Transport layer: the core NotificationServer communicates with clients only
through a pluggable BaseTransport. WebSocketTransport is the default; the
TRANSPORT environment variable selects the implementation and new transports
(SSE, polling, raw TCP, ...) can be added by subclassing BaseTransport and
registering them in TRANSPORTS without touching the notification logic.
"""

import abc
import asyncio
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from websockets.asyncio.server import serve

try:
    from redis.asyncio import Redis as _Redis
except ImportError:  # pragma: no cover - redis is optional at runtime
    _Redis = None  # type: ignore[misc,assignment]

WS_HOST = os.environ.get("WS_HOST", "127.0.0.1")
WS_PORT = int(os.environ.get("WS_PORT", "8765"))
HEALTH_HOST = os.environ.get("HEALTH_HOST", "127.0.0.1")
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "8766"))

REDIS_CHANNEL = "notifications:messages"

RATE_LIMIT_KEY = "notifications:ratelimit"
RATE_LIMIT_WINDOW_SECONDS = 60
DEFAULT_RATE_LIMIT = 100
DEFAULT_MESSAGE_TTL_DAYS = 7
MESSAGE_EXPIRY_INTERVAL = 3600.0

SUPPORTED_TYPES = ("broadcast", "direct", "system", "subscribe", "unsubscribe")


def make_message(msg_type: str, payload: dict) -> dict:
    """Build a message in the canonical wire format."""
    return {
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def parse_iso_timestamp(value: str) -> str:
    """Parse an ISO-8601 timestamp and return it in canonical UTC form.

    Accepts ``+00:00`` offsets and a trailing ``Z``; naive timestamps are
    assumed to be UTC. The canonical form matches the timestamps produced by
    ``make_message`` so lexicographic ordering on the stored strings is
    equivalent to chronological ordering.
    """
    text = value
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(f"invalid timestamp: {value!r}") from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


class MessageStore:
    """SQLite-backed history of every distributed message.

    The schema is: id, channel, type, payload, timestamp. The database path is
    taken from DATABASE_URL (sqlite:///... form or a bare path); it defaults to
    an in-memory database when unset. A lock serialises writes because the
    store may be shared across server instances / threads.
    """

    def __init__(self, database_url: str | None = None):
        value = database_url or os.getenv("DATABASE_URL", "sqlite:///:memory:")
        if value.startswith("sqlite:///"):
            path = value[len("sqlite:///") :]
        elif value.startswith("sqlite://"):
            path = value[len("sqlite://") :]
        else:
            path = value
        self.path = path
        self._lock = threading.Lock()
        self._connection = None

    def open(self) -> None:
        """Create the table and open the connection (idempotent)."""
        if self._connection is not None:
            return
        self._connection = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
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

    def add(self, channel: str | None, msg_type: str, payload: dict, time: str) -> None:
        """Insert a message; the store must be open."""
        if self._connection is None:
            raise RuntimeError("message store is not open")
        with self._lock:
            self._connection.execute(
                "INSERT INTO messages(channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (channel, msg_type, json.dumps(payload), time),
            )
            self._connection.commit()

    def list(self, limit: int, offset: int) -> list:
        """Return persisted messages ordered by id, paginated by limit/offset."""
        return self._query(
            "SELECT id, channel, type, payload, timestamp FROM messages "
            "ORDER BY id LIMIT ? OFFSET ?",
            (limit, offset),
        )

    def history(self, channel: str, since: str | None, limit: int) -> list:
        """Return messages for a channel in chronological order.

        When ``since`` is given only messages strictly newer than it are
        returned; otherwise every message on the channel is a candidate. Both
        orderings are stable by timestamp then id, so pagination via ``since``
        never duplicates rows.
        """
        if since is not None:
            return self._query(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "WHERE channel = ? AND timestamp > ? "
                "ORDER BY timestamp, id LIMIT ?",
                (channel, since, limit),
            )
        return self._query(
            "SELECT id, channel, type, payload, timestamp FROM messages "
            "WHERE channel = ? ORDER BY timestamp, id LIMIT ?",
            (channel, limit),
        )

    def expire(self, older_than: str) -> int:
        """Delete every message older than the given ISO timestamp.

        Returns the number of removed rows. Safe to call when the store is not
        open (returns 0).
        """
        if self._connection is None:
            return 0
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM messages WHERE timestamp < ?", (older_than,)
            )
            self._connection.commit()
            return cursor.rowcount

    def _query(self, query: str, parameters: tuple) -> list:
        if self._connection is None:
            return []
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
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


class ClientRegistry:
    """Thread-safe registry of connected clients (client_id -> connection).

    Also tracks channel subscriptions (channel -> set of client_ids). Every
    mutation is guarded by a threading.Lock so the separate HTTP health thread
    can safely observe and coordinate with the async world.
    """

    def __init__(self):
        self._clients = {}
        self._subscriptions = {}
        self._lock = threading.Lock()

    def add(self, connection) -> str:
        client_id = uuid.uuid4().hex
        with self._lock:
            self._clients[client_id] = connection
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            for channel, subscribers in list(self._subscriptions.items()):
                subscribers.discard(client_id)
                if not subscribers:
                    del self._subscriptions[channel]

    def get(self, client_id: str):
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._clients)

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            self._subscriptions.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._subscriptions.get(channel)
            if subscribers is not None:
                subscribers.discard(client_id)
                if not subscribers:
                    del self._subscriptions[channel]

    def subscribers_of(self, channel: str) -> set:
        with self._lock:
            return set(self._subscriptions.get(channel, ()))

    def channels_snapshot(self) -> dict:
        with self._lock:
            return {channel: set(ids) for channel, ids in self._subscriptions.items()}

    def channels_of(self, client_id: str) -> set:
        """Channels the given client is currently subscribed to."""
        with self._lock:
            return {channel for channel, ids in self._subscriptions.items() if client_id in ids}

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)


async def broadcast(registry: ClientRegistry, message: dict, exclude: str | None = None) -> None:
    """Broadcast to every connected client by iterating the registry and
    awaiting send() on each connection (websockets.broadcast is deprecated)."""
    for client_id, connection in registry.snapshot().items():
        if exclude is not None and client_id == exclude:
            continue
        try:
            await connection.send(json.dumps(message))
        except Exception:
            registry.remove(client_id)


async def broadcast_to_channel(
    registry: ClientRegistry, channel: str, message: dict, exclude: str | None = None
) -> None:
    """Deliver a message only to the clients subscribed to the given channel."""
    for client_id in registry.subscribers_of(channel):
        if exclude is not None and client_id == exclude:
            continue
        connection = registry.get(client_id)
        if connection is None:
            continue
        try:
            await connection.send(json.dumps(message))
        except Exception:
            registry.remove(client_id)


class BaseTransport(abc.ABC):
    """Pluggable transport interface for delivering messages to clients.

    The core NotificationServer communicates exclusively through a transport,
    so alternative mechanisms (SSE, polling, raw TCP, ...) can be added without
    touching the notification logic. Implementations are selected via the
    TRANSPORT environment variable (see ``get_transport_class``).
    """

    name = "base"

    def __init__(self, server):
        self.server = server

    @property
    def registry(self) -> ClientRegistry:
        return self.server.registry

    @abc.abstractmethod
    async def start(self, host: str, port: int):
        """Start the transport listener and return the underlying server object."""

    @abc.abstractmethod
    async def on_connect(self, connection, client_id: str) -> None:
        """Notify a client that it has connected (e.g. send a greeting)."""

    @abc.abstractmethod
    async def on_disconnect(self, client_id: str, channels: set) -> None:
        """Transport-side notification when a client disconnects."""

    @abc.abstractmethod
    async def send_message(self, connection, message: dict) -> None:
        """Serialize and deliver a single message to one connection."""

    @abc.abstractmethod
    async def broadcast(
        self, message: dict, exclude: str | None = None, channel: str | None = None
    ) -> None:
        """Deliver a message to the relevant connected clients.

        With ``channel`` set only the subscribers of that channel receive it,
        otherwise every connected client does. ``exclude`` skips one client id.
        """


class WebSocketTransport(BaseTransport):
    """WebSocket transport built on the ``websockets`` library (default)."""

    name = "websocket"

    async def start(self, host: str, port: int):
        return await serve(self.handle_connection, host, port)

    async def handle_connection(self, connection) -> None:
        server = self.server
        client_id = server.registry.add(connection)
        await server._save_client_state(client_id, "connected", set())
        try:
            await self.on_connect(connection, client_id)
            async for raw in connection:
                await server._process(client_id, connection, raw)
        finally:
            channels = server.registry.channels_of(client_id)
            server.registry.remove(client_id)
            await server._save_client_state(client_id, "disconnected", channels)
            await self.on_disconnect(client_id, channels)

    async def on_connect(self, connection, client_id: str) -> None:
        await self.send_message(
            connection,
            make_message("system", {"action": "connected", "client_id": client_id}),
        )

    async def on_disconnect(self, client_id: str, channels: set) -> None:
        return None

    async def send_message(self, connection, message: dict) -> None:
        await connection.send(json.dumps(message))

    async def broadcast(
        self, message: dict, exclude: str | None = None, channel: str | None = None
    ) -> None:
        if channel is not None:
            await broadcast_to_channel(self.registry, channel, message, exclude)
        else:
            await broadcast(self.registry, message, exclude)


TRANSPORTS: dict[str, type[BaseTransport]] = {
    WebSocketTransport.name: WebSocketTransport,
}


def get_transport_class(name: str | None = None) -> type[BaseTransport]:
    """Resolve a transport implementation by name (TRANSPORT env var by default)."""
    transport_name = (name or os.getenv("TRANSPORT", WebSocketTransport.name)).lower()
    try:
        return TRANSPORTS[transport_name]
    except KeyError as exc:
        raise ValueError(
            f"unknown transport: {transport_name!r} "
            f"(available: {', '.join(sorted(TRANSPORTS))})"
        ) from exc


class NotificationServer:
    """Owns a ClientRegistry and drives the per-connection event loop.

    When a redis backend is available (via REDIS_URL or an injected client)
    distributed messages are published to a shared pub/sub channel that every
    instance listens to, and client connection state is mirrored into Redis.
    Every distributed message is also persisted into SQLite for history.
    """

    redis_channel = REDIS_CHANNEL

    def __init__(
        self,
        registry: ClientRegistry | None = None,
        redis_url: str | None = None,
        database_url: str | None = None,
        redis_client=None,
        transport: BaseTransport | type[BaseTransport] | None = None,
        rate_limit: int | None = None,
        message_ttl_days: int | None = None,
    ):
        self.registry = registry or ClientRegistry()
        self.store = MessageStore(database_url)
        self.redis_url = redis_url if redis_url is not None else os.getenv("REDIS_URL")
        self.redis = redis_client
        self._owns_redis = redis_client is None and bool(self.redis_url)
        self._instance_id = uuid.uuid4().hex
        self._redis_pubsub = None
        self._subscriber_task = None
        self._expiry_task = None
        self._expiry_interval = MESSAGE_EXPIRY_INTERVAL
        self.rate_limit = (
            rate_limit
            if rate_limit is not None
            else int(os.getenv("RATE_LIMIT", str(DEFAULT_RATE_LIMIT)))
        )
        self.message_ttl_days = (
            message_ttl_days
            if message_ttl_days is not None
            else float(os.getenv("MESSAGE_TTL_DAYS", str(DEFAULT_MESSAGE_TTL_DAYS)))
        )
        if transport is None:
            transport = get_transport_class()(self)
        elif isinstance(transport, type):
            transport = transport(self)
        self.transport = transport

    def __len__(self) -> int:
        return len(self.registry)

    def messages(self, limit: int = 50, offset: int = 0) -> list:
        """Return persisted messages for the GET /messages endpoint."""
        return self.store.list(limit, offset)

    def history(self, channel: str, since: str | None, limit: int) -> tuple:
        """Return (messages, has_more) for the GET /history endpoint."""
        rows = self.store.history(channel, since, limit + 1)
        has_more = len(rows) > limit
        return rows[:limit], has_more

    async def start_backend(self) -> None:
        """Open the message store and connect to the Redis backbone."""
        self.store.open()
        self._expiry_task = asyncio.create_task(self._run_expiry())
        if self.redis is None and self.redis_url and _Redis is not None:
            self.redis = _Redis.from_url(self.redis_url, decode_responses=True)
            self._owns_redis = True
        if self.redis is None:
            return
        try:
            await self.redis.ping()
            self._redis_pubsub = self.redis.pubsub()
            await self._redis_pubsub.subscribe(self.redis_channel)
            self._subscriber_task = asyncio.create_task(self._consume_redis())
        except Exception:
            self._redis_pubsub = None
            self._subscriber_task = None

    async def stop_backend(self) -> None:
        """Cancel background tasks, close connections and the store."""
        if self._expiry_task is not None:
            self._expiry_task.cancel()
            await asyncio.gather(self._expiry_task, return_exceptions=True)
            self._expiry_task = None
        if self._subscriber_task is not None:
            self._subscriber_task.cancel()
            await asyncio.gather(self._subscriber_task, return_exceptions=True)
            self._subscriber_task = None
        if self._redis_pubsub is not None:
            await _close_async(self._redis_pubsub)
            self._redis_pubsub = None
        if self._owns_redis and self.redis is not None:
            await _close_async(self.redis)
            self.redis = None
            self._owns_redis = False
        self.store.close()

    async def _run_expiry(self) -> None:
        """Periodically clean messages older than ``message_ttl_days``."""
        while True:
            try:
                await self.expire_old_messages()
            except Exception:
                pass
            await asyncio.sleep(self._expiry_interval)

    async def expire_old_messages(self) -> int:
        """Delete messages older than the configured TTL; return the count."""
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=self.message_ttl_days)
        ).isoformat()
        return await asyncio.to_thread(self.store.expire, cutoff)

    async def _check_rate_limit(self, client_id: str) -> bool:
        """Return True when the client may send another message.

        A fixed one-minute window is tracked per client in Redis with an INCR +
        EXPIRE pair, so limits are enforced across server instances. Without a
        Redis backend the check is a no-op.
        """
        if self.redis is None or self.rate_limit is None or self.rate_limit <= 0:
            return True
        window = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        key = f"{RATE_LIMIT_KEY}:{client_id}:{window}"
        try:
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, RATE_LIMIT_WINDOW_SECONDS)
            return count <= self.rate_limit
        except Exception:
            return True

    async def _consume_redis(self) -> None:
        """Deliver messages published by other instances to local clients."""
        while True:
            item = await self._redis_pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1.0
            )
            if item is not None and item.get("data"):
                try:
                    envelope = json.loads(item["data"])
                except (json.JSONDecodeError, TypeError):
                    continue
                if envelope.get("origin") != self._instance_id:
                    message = envelope.get("message")
                    if isinstance(message, dict):
                        await self._deliver(message)
            await asyncio.sleep(0)

    async def _process(self, client_id: str, connection, raw: str) -> None:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            await self.transport.send_message(
                connection, make_message("system", {"action": "error", "message": "invalid json"})
            )
            return

        msg_type = data.get("type")
        payload = data.get("payload") or {}

        if not await self._check_rate_limit(client_id):
            await self.transport.send_message(
                connection,
                make_message(
                    "system",
                    {"action": "error", "message": "rate limit exceeded"},
                ),
            )
            return

        if msg_type == "system" and payload.get("action") == "health":
            await self.transport.send_message(
                connection,
                make_message("system", {"action": "health", "client_count": len(self.registry)}),
            )
        elif msg_type == "subscribe":
            channel = payload.get("channel") or data.get("channel")
            if channel:
                self.registry.subscribe(client_id, channel)
                await self._save_client_state(client_id, "connected", self.registry.channels_of(client_id))
                await self.transport.send_message(
                    connection, make_message("system", {"action": "subscribed", "channel": channel})
                )
            else:
                await self.transport.send_message(
                    connection,
                    make_message("system", {"action": "error", "message": "channel required"}),
                )
        elif msg_type == "unsubscribe":
            channel = payload.get("channel") or data.get("channel")
            if channel:
                self.registry.unsubscribe(client_id, channel)
                await self._save_client_state(client_id, "connected", self.registry.channels_of(client_id))
                await self.transport.send_message(
                    connection,
                    make_message("system", {"action": "unsubscribed", "channel": channel}),
                )
            else:
                await self.transport.send_message(
                    connection,
                    make_message("system", {"action": "error", "message": "channel required"}),
                )
        elif msg_type == "broadcast":
            channel = payload.get("channel") or data.get("channel")
            outgoing = make_message("broadcast", payload)
            if isinstance(channel, str) and channel:
                outgoing["channel"] = channel
            await self._distribute(outgoing)
        elif msg_type == "direct":
            outgoing = make_message("direct", payload)
            target = payload.get("client_id")
            if self.redis is None and self.registry.get(target) is None:
                await self.transport.send_message(
                    connection,
                    make_message("system", {"action": "error", "message": "client not found"}),
                )
            else:
                await self._distribute(outgoing)
        else:
            await self.transport.send_message(
                connection,
                make_message("system", {"action": "error", "message": "unsupported type"}),
            )

    async def _distribute(self, outgoing: dict) -> None:
        """Persist a message, publish it to the Redis backbone, then deliver."""
        await self._persist(outgoing)
        if self.redis is not None:
            await self.redis.publish(
                self.redis_channel,
                json.dumps({"origin": self._instance_id, "message": outgoing}),
            )
        await self._deliver(outgoing)

    async def _persist(self, outgoing: dict) -> None:
        channel = outgoing.get("channel")
        if not isinstance(channel, str) or not channel:
            channel = None
        try:
            await asyncio.to_thread(
                self.store.add, channel, outgoing["type"], outgoing["payload"], outgoing["timestamp"]
            )
        except Exception:
            pass

    async def _deliver(self, outgoing: dict) -> None:
        """Deliver a message to the local clients of this instance."""
        if outgoing["type"] == "direct":
            target = outgoing["payload"].get("client_id")
            conn = self.registry.get(target)
            if conn is not None:
                try:
                    await self.transport.send_message(conn, outgoing)
                except Exception:
                    self.registry.remove(target)
            return
        channel = outgoing.get("channel")
        if isinstance(channel, str) and channel:
            await self.transport.broadcast(outgoing, channel=channel)
        else:
            await self.transport.broadcast(outgoing)

    async def _save_client_state(self, client_id: str, status: str, channels: set) -> None:
        """Mirror client connection state into Redis so it survives restarts."""
        if self.redis is None:
            return
        try:
            await self.redis.hset(
                f"notifications:client:{client_id}",
                mapping={
                    "status": status,
                    "channels": json.dumps(sorted(channels)),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception:
            pass


def _make_health_handler(owner):
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            registry = getattr(owner, "registry", owner)
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            if path == "/health":
                body = json.dumps({"client_count": len(registry)}).encode("utf-8")
            elif path == "/channels":
                channels = {
                    name: len(subscribers)
                    for name, subscribers in registry.channels_snapshot().items()
                }
                body = json.dumps({"channels": channels}).encode("utf-8")
            elif path == "/messages" and hasattr(owner, "messages"):
                query = parse_qs(parsed.query)
                try:
                    limit = max(0, min(1000, int(query.get("limit", ["50"])[0])))
                    offset = max(0, int(query.get("offset", ["0"])[0]))
                except (TypeError, ValueError):
                    self.send_error(400)
                    return
                body = json.dumps({"messages": owner.messages(limit, offset)}).encode("utf-8")
            elif path == "/history" and hasattr(owner, "history"):
                query = parse_qs(parsed.query)
                channel = (query.get("channel") or [None])[0]
                if not channel:
                    self.send_error(400)
                    return
                since_raw = (query.get("since") or [None])[0]
                since = None
                if since_raw is not None:
                    try:
                        since = parse_iso_timestamp(since_raw)
                    except ValueError:
                        self.send_error(400)
                        return
                try:
                    limit = max(1, min(1000, int(query.get("limit", ["50"])[0])))
                except (TypeError, ValueError):
                    self.send_error(400)
                    return
                messages, has_more = owner.history(channel, since, limit)
                body = json.dumps(
                    {
                        "channel": channel,
                        "since": since,
                        "limit": limit,
                        "messages": messages,
                        "has_more": has_more,
                    }
                ).encode("utf-8")
            elif path.startswith("/channels/") and len(path) > len("/channels/"):
                rest = path[len("/channels/") :]
                name = None
                if rest.endswith("/subscribers"):
                    name = rest[: -len("/subscribers")]
                elif "/" not in rest:
                    name = rest
                if not name or "/" in name:
                    self.send_error(404)
                    return
                subscribers = sorted(registry.subscribers_of(name))
                body = json.dumps(
                    {"channel": name, "subscribers": subscribers}
                ).encode("utf-8")
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    return HealthHandler


def start_health_server(owner, host: str = HEALTH_HOST, port: int = 0):
    """Run the HTTP health listener in a separate thread.

    ``owner`` is either a ClientRegistry or a NotificationServer.
    """
    httpd = ThreadingHTTPServer((host, port), _make_health_handler(owner))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def stop_health_server(httpd) -> None:
    httpd.shutdown()
    httpd.server_close()


async def start_ws_server(server: NotificationServer, host: str = WS_HOST, port: int = 0):
    """Start the listener for the server's transport and return the server object."""
    return await server.transport.start(host, port)


async def _close_async(client) -> None:
    """Close a redis client / pubsub object, tolerating either API."""
    close = getattr(client, "aclose", None) or getattr(client, "close", None)
    if close is None:
        return
    try:
        result = close()
        if asyncio.iscoroutine(result):
            await result
    except Exception:
        pass


async def main():
    server = NotificationServer()
    await server.start_backend()
    ws_server = await start_ws_server(server)
    httpd = start_health_server(server)
    ws_port = ws_server.sockets[0].getsockname()[1]
    health_port = httpd.server_address[1]
    print(f"WebSocket listening on {WS_HOST}:{ws_port}")
    print(f"Health listening on {HEALTH_HOST}:{health_port}")
    try:
        await asyncio.Future()
    finally:
        ws_server.close()
        stop_health_server(httpd)
        await server.stop_backend()


if __name__ == "__main__":
    asyncio.run(main())
