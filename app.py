"""
WebSocket-based notification server.

Features:
- Accept WebSocket connections and assign each client a unique ID.
- Broadcast messages to all connected clients.
- Send direct and system messages to specific clients.
- Channel-based subscriptions: clients subscribe/unsubscribe to named
  channels and channel-tagged messages are routed only to subscribers.
- Clean removal of clients on disconnect.
- Redis pub/sub message backbone: servers publish serialized envelopes to a
  Redis channel and worker instances subscribe and deliver to their locally
  connected clients. Multiple server instances can share the same Redis
  backbone and each instance only delivers to its own clients.
- Client connection state (including channel subscriptions) mirrored into
  Redis so it survives a server restart.
- SQLite-backed message history with REST endpoint GET /messages.

Config (environment variables):
- REDIS_URL: broker connection URL. When unset a local in-memory fake Redis
  (fakeredis) is used, which keeps the server runnable without a broker.
- DATABASE_URL: SQLite path (plain path or sqlite:// URL). Defaults to an
  in-memory database.

Message format (JSON): {type: str, payload: dict, timestamp: str}
Supported types: 'broadcast', 'direct', 'system', 'subscribe', 'unsubscribe'.
"""

import asyncio
import json
import os
import threading
import uuid
from datetime import datetime, timezone

import aiosqlite
import websockets
from aiohttp import web

try:
    import redis.asyncio as redis_asyncio
except Exception:  # pragma: no cover - redis package is optional
    redis_asyncio = None

import fakeredis.aioredis

DEFAULT_WS_HOST = "0.0.0.0"
DEFAULT_WS_PORT = 8765
DEFAULT_HTTP_HOST = "0.0.0.0"
DEFAULT_HTTP_PORT = 8080

VALID_TYPES = ("broadcast", "direct", "system", "subscribe", "unsubscribe")


def utcnow_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


class ClientRegistry:
    """Thread-safe registry of connected WebSocket clients.

    Guards its internal dictionary with a threading.Lock so it is safe to
    access from the asyncio loop as well as any worker thread (e.g. an HTTP
    handler running in a separate thread).
    """

    def __init__(self) -> None:
        self._clients: dict[str, object] = {}
        self._lock = threading.Lock()

    def add(self, client_id: str, websocket: object) -> None:
        with self._lock:
            self._clients[client_id] = websocket

    def remove(self, client_id: str) -> object | None:
        with self._lock:
            return self._clients.pop(client_id, None)

    def get(self, client_id: str) -> object | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> list[tuple[str, object]]:
        with self._lock:
            return list(self._clients.items())

    def count(self) -> int:
        with self._lock:
            return len(self._clients)


class ChannelRegistry:
    """Thread-safe registry of channel memberships.

    Maps a channel name to the set of client IDs subscribed to it. Guarded by a
    threading.Lock so it can be used from the asyncio loop and HTTP handlers.
    """

    def __init__(self) -> None:
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def subscribe(self, channel: str, client_id: str) -> None:
        with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, channel: str, client_id: str) -> None:
        with self._lock:
            members = self._channels.get(channel)
            if members is None:
                return
            members.discard(client_id)
            if not members:
                del self._channels[channel]

    def unsubscribe_all(self, client_id: str) -> None:
        """Remove a client from every channel it is subscribed to."""
        with self._lock:
            for channel in list(self._channels):
                members = self._channels[channel]
                members.discard(client_id)
                if not members:
                    del self._channels[channel]

    def members(self, channel: str) -> set[str]:
        with self._lock:
            return set(self._channels.get(channel, ()))

    def count(self, channel: str) -> int:
        with self._lock:
            return len(self._channels.get(channel, ()))

    def snapshot(self) -> dict[str, int]:
        """Return a mapping of channel name to subscriber count."""
        with self._lock:
            return {name: len(members) for name, members in self._channels.items()}


class RedisBroker:
    """Redis pub/sub message backbone.

    Every outbound message is wrapped in an envelope carrying routing metadata
    (a target kind of ``all``, ``channel``, ``direct`` or ``system``) and
    published to a single Redis pub/sub channel. Each server instance
    subscribes to that channel and delivers envelopes to the clients connected
    to *it* that match the envelope target. Because the publishing instance
    also receives its own publications, no local copy is sent directly, which
    avoids double delivery while allowing several instances to share one Redis.

    Client connection state is mirrored into Redis so it survives restarts.
    """

    DISTRIBUTION_CHANNEL = "ntf:messages"
    CLIENTS_SET = "notif:clients"
    CLIENT_PREFIX = "notif:client:"
    CLIENT_CHANNELS_PREFIX = "notif:clientchans:"

    def __init__(self, redis_url: str | None = None,
                 redis_client: object | None = None) -> None:
        self._redis_url = redis_url
        self._redis = redis_client
        self._pubsub = None
        self._deliver = None
        self._task = None
        self._owns_client = redis_client is None

    def _connect(self) -> object:
        """Build (or reuse) a redis.asyncio-compatible client."""
        if self._redis is not None:
            return self._redis
        url = self._redis_url or os.environ.get("REDIS_URL")
        if url:
            if redis_asyncio is None:
                raise RuntimeError(
                    "REDIS_URL is set but the 'redis' package is not installed"
                )
            return redis_asyncio.from_url(url, decode_responses=True)
        return fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def start(self, deliver) -> None:
        """Subscribe to the distribution channel and start delivering."""
        self._redis = self._connect()
        self._deliver = deliver
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(self.DISTRIBUTION_CHANNEL)
        self._task = asyncio.create_task(self._listen_loop())

    async def _listen_loop(self) -> None:
        while True:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=0.5
                )
                if message is None:
                    continue
                envelope = json.loads(message["data"])
                if self._deliver is not None:
                    await self._deliver(envelope)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(0.05)

    async def publish(self, envelope: dict) -> None:
        """Publish an envelope to the shared distribution channel."""
        if self._redis is None:
            return
        await self._redis.publish(
            self.DISTRIBUTION_CHANNEL, json.dumps(envelope)
        )

    # -- client connection state -------------------------------------------------

    async def store_client(self, client_id: str, state: dict) -> None:
        await self._redis.hset(
            self.CLIENT_PREFIX + client_id, mapping=state
        )
        await self._redis.sadd(self.CLIENTS_SET, client_id)

    async def drop_client(self, client_id: str) -> None:
        await self._redis.delete(self.CLIENT_PREFIX + client_id)
        await self._redis.delete(self.CLIENT_CHANNELS_PREFIX + client_id)
        await self._redis.srem(self.CLIENTS_SET, client_id)

    async def get_client_state(self, client_id: str) -> dict:
        return await self._redis.hgetall(self.CLIENT_PREFIX + client_id)

    async def list_clients(self) -> set:
        return await self._redis.smembers(self.CLIENTS_SET)

    async def add_client_channel(self, client_id: str, channel: str) -> None:
        await self._redis.sadd(self.CLIENT_CHANNELS_PREFIX + client_id, channel)

    async def remove_client_channel(self, client_id: str, channel: str) -> None:
        await self._redis.srem(self.CLIENT_CHANNELS_PREFIX + client_id, channel)

    async def get_client_channels(self, client_id: str) -> set:
        return await self._redis.smembers(self.CLIENT_CHANNELS_PREFIX + client_id)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except BaseException:
                pass
            self._task = None
        if self._pubsub is not None:
            try:
                await self._pubsub.unsubscribe()
            except Exception:
                pass
            try:
                close = getattr(self._pubsub, "aclose", None)
                if close is None:
                    close = getattr(self._pubsub, "close", None)
                if close is not None:
                    await close()
            except Exception:
                pass
            self._pubsub = None
        if self._owns_client and self._redis is not None:
            try:
                close = getattr(self._redis, "aclose", None)
                if close is None:
                    close = getattr(self._redis, "close", None)
                if close is not None:
                    await close()
            except Exception:
                pass
            self._redis = None


class MessageStore:
    """SQLite-backed persistence for message history.

    The database path comes from ``DATABASE_URL`` (a plain filesystem path or
    a ``sqlite://`` URL). When unset, an in-memory database is used.
    """

    SCHEMA = (
        "CREATE TABLE IF NOT EXISTS messages ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " channel TEXT,"
        " type TEXT,"
        " payload TEXT,"
        " timestamp TEXT)"
    )

    def __init__(self, database_url: str | None = None) -> None:
        self._path = self._parse_path(database_url)
        self._conn = None

    @staticmethod
    def _parse_path(database_url: str | None) -> str:
        url = database_url or os.environ.get("DATABASE_URL")
        if not url:
            return ":memory:"
        if url.startswith("sqlite:///"):
            return url[len("sqlite:///"):]
        if url.startswith("sqlite://"):
            return url[len("sqlite://"):]
        return url

    async def start(self) -> None:
        self._conn = await aiosqlite.connect(self._path)
        await self._conn.execute(self.SCHEMA)
        await self._conn.commit()

    async def save(self, channel: str, msg_type: str, payload: dict,
                   timestamp: str) -> int:
        cursor = await self._conn.execute(
            "INSERT INTO messages (channel, type, payload, timestamp)"
            " VALUES (?, ?, ?, ?)",
            (channel, msg_type, json.dumps(payload), timestamp),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def history(self, limit: int = 50, offset: int = 0) -> list[dict]:
        rows = await self._conn.execute_fetchall(
            "SELECT id, channel, type, payload, timestamp FROM messages"
            " ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [
            {
                "id": row[0],
                "channel": row[1],
                "type": row[2],
                "payload": json.loads(row[3]) if row[3] else {},
                "timestamp": row[4],
            }
            for row in rows
        ]

    async def count(self) -> int:
        rows = await self._conn.execute_fetchall(
            "SELECT COUNT(*) FROM messages"
        )
        return rows[0][0]

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None


class NotificationServer:
    """Async notification server exposing a WebSocket endpoint and REST
    endpoints, all running on the same asyncio event loop.

    Message distribution goes through the Redis pub/sub backbone. History is
    persisted to SQLite.
    """

    def __init__(self, registry: ClientRegistry | None = None,
                 channels: ChannelRegistry | None = None,
                 store: MessageStore | None = None,
                 broker: RedisBroker | None = None,
                 redis_url: str | None = None,
                 redis_client: object | None = None,
                 database_url: str | None = None) -> None:
        self.registry = registry or ClientRegistry()
        self.channels = channels or ChannelRegistry()
        self.store = store or MessageStore(database_url)
        self.broker = broker or RedisBroker(redis_url, redis_client)
        self._ws_server = None
        self._http_runner = None
        self._http_site = None
        self.ws_port = None
        self.http_port = None

    @staticmethod
    def make_message(msg_type: str, payload: dict) -> dict:
        if msg_type not in VALID_TYPES:
            raise ValueError(f"unsupported message type: {msg_type}")
        return {
            "type": msg_type,
            "payload": payload,
            "timestamp": utcnow_iso(),
        }

    @staticmethod
    def encode(message: dict) -> str:
        return json.dumps(message)

    @staticmethod
    def _channel_for_target(target: dict) -> str:
        kind = target.get("kind")
        if kind == "channel":
            return str(target.get("channel") or "global")
        if kind == "direct":
            return "direct"
        if kind == "system":
            return "system"
        return "global"

    async def _publish(self, message: dict, target: dict) -> None:
        """Persist a message and publish it to the Redis backbone."""
        envelope = {
            "msg_id": str(uuid.uuid4()),
            "type": message["type"],
            "payload": message["payload"],
            "timestamp": message["timestamp"],
            "target": target,
        }
        await self.store.save(
            self._channel_for_target(target),
            message["type"],
            message["payload"],
            message["timestamp"],
        )
        await self.broker.publish(envelope)

    async def broadcast(self, payload: dict, channel: str | None = None) -> int:
        """Send a 'broadcast' message to connected clients.

        When ``channel`` is given, the message is delivered only to clients
        subscribed to that channel. Otherwise it goes to every connected
        client. Returns the number of intended recipients.
        """
        message = self.make_message("broadcast", payload)
        if channel is not None:
            channel = str(channel)
            await self._publish(message, {"kind": "channel", "channel": channel})
            return self.channels.count(channel)
        await self._publish(message, {"kind": "all"})
        return self.registry.count()

    async def send_direct(self, client_id: str, payload: dict) -> bool:
        """Send a 'direct' message to a specific client.

        Returns True if the client is connected, False otherwise.
        """
        if self.registry.get(client_id) is None:
            return False
        message = self.make_message("direct", payload)
        await self._publish(message, {"kind": "direct", "client_id": client_id})
        return True

    async def send_system(self, client_id: str, payload: dict) -> bool:
        """Send a 'system' message to a specific client."""
        if self.registry.get(client_id) is None:
            return False
        message = self.make_message("system", payload)
        await self._publish(message, {"kind": "system", "client_id": client_id})
        return True

    async def _send_to(self, client_id: str, message: dict) -> bool:
        websocket = self.registry.get(client_id)
        if websocket is None:
            return False
        try:
            await websocket.send(self.encode(message))
            return True
        except Exception:
            self.registry.remove(client_id)
            return False

    async def _send_to_all(self, message: dict) -> None:
        data = self.encode(message)
        for client_id, websocket in self.registry.snapshot():
            try:
                await websocket.send(data)
            except Exception:
                self.registry.remove(client_id)

    async def _send_to_channel(self, channel: str, message: dict) -> None:
        data = self.encode(message)
        for client_id in self.channels.members(channel):
            websocket = self.registry.get(client_id)
            if websocket is None:
                self.channels.unsubscribe(channel, client_id)
                continue
            try:
                await websocket.send(data)
            except Exception:
                self.registry.remove(client_id)
                self.channels.unsubscribe(channel, client_id)

    async def _deliver_envelope(self, envelope: dict) -> None:
        """Deliver a message received from the Redis backbone to local clients."""
        message = {
            "type": envelope["type"],
            "payload": envelope["payload"],
            "timestamp": envelope["timestamp"],
        }
        target = envelope.get("target") or {}
        kind = target.get("kind")
        if kind == "channel":
            await self._send_to_channel(str(target.get("channel")), message)
        elif kind in ("direct", "system"):
            await self._send_to(target.get("client_id"), message)
        else:
            await self._send_to_all(message)

    async def handler(self, websocket, path: str | None = None) -> None:
        """Per-connection handler: registers the client, then relays messages."""
        client_id = str(uuid.uuid4())
        self.registry.add(client_id, websocket)
        address = ""
        try:
            address = str(websocket.remote_address[0])
        except Exception:
            pass
        await self.broker.store_client(client_id, {
            "connected_at": utcnow_iso(),
            "address": address,
        })
        await self.send_system(client_id, {"client_id": client_id})
        try:
            async for raw in websocket:
                await self._dispatch(client_id, raw)
        except websockets.ConnectionClosed:
            pass
        finally:
            self.registry.remove(client_id)
            self.channels.unsubscribe_all(client_id)
            await self.broker.drop_client(client_id)

    async def _dispatch(self, client_id: str, raw: str) -> None:
        """Route an incoming client message based on its type."""
        try:
            message = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return
        msg_type = message.get("type")
        payload = message.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {"data": payload}
        if msg_type == "broadcast":
            channel = message.get("channel") or payload.get("channel")
            if channel is not None:
                await self.broadcast(payload, str(channel))
            else:
                await self.broadcast(payload)
        elif msg_type == "direct":
            target = payload.get("to")
            if target is not None:
                await self.send_direct(str(target), payload)
        elif msg_type == "system":
            await self.send_system(client_id, {"ack": msg_type})
        elif msg_type == "subscribe":
            channel = message.get("channel") or payload.get("channel")
            if channel is not None:
                channel = str(channel)
                self.channels.subscribe(channel, client_id)
                await self.broker.add_client_channel(client_id, channel)
        elif msg_type == "unsubscribe":
            channel = message.get("channel") or payload.get("channel")
            if channel is not None:
                channel = str(channel)
                self.channels.unsubscribe(channel, client_id)
                await self.broker.remove_client_channel(client_id, channel)

    async def start(self, ws_host: str = DEFAULT_WS_HOST, ws_port: int = DEFAULT_WS_PORT,
                    http_host: str = DEFAULT_HTTP_HOST, http_port: int = DEFAULT_HTTP_PORT) -> None:
        """Start the WebSocket server and the REST endpoints."""
        await self.store.start()
        await self.broker.start(self._deliver_envelope)

        self._ws_server = await websockets.serve(self.handler, ws_host, ws_port)
        self.ws_port = self._ws_server.sockets[0].getsockname()[1]

        http_app = web.Application()
        http_app.router.add_get("/health", self._health_handler)
        http_app.router.add_get("/clients", self._clients_handler)
        http_app.router.add_get("/channels", self._channels_handler)
        http_app.router.add_get("/channels/{name}/subscribers", self._channel_subscribers_handler)
        http_app.router.add_get("/messages", self._messages_handler)
        self._http_runner = web.AppRunner(http_app)
        await self._http_runner.setup()
        self._http_site = web.TCPSite(self._http_runner, http_host, http_port)
        await self._http_site.start()
        self.http_port = self._http_site._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._ws_server is not None:
            self._ws_server.close()
            await self._ws_server.wait_closed()
        if self._http_runner is not None:
            await self._http_runner.cleanup()
        await self.broker.stop()
        await self.store.close()

    async def _health_handler(self, request):
        return web.json_response({"clients": self.registry.count()})

    async def _clients_handler(self, request):
        clients = set(await self.broker.list_clients())
        clients = sorted(
            client.decode() if isinstance(client, bytes) else client
            for client in clients
        )
        return web.json_response({"clients": clients})

    async def _channels_handler(self, request):
        snapshot = self.channels.snapshot()
        return web.json_response({
            "channels": [
                {"name": name, "subscribers": count}
                for name, count in snapshot.items()
            ],
        })

    async def _channel_subscribers_handler(self, request):
        name = request.match_info["name"]
        subscribers = sorted(self.channels.members(name))
        return web.json_response({
            "name": name,
            "subscribers": subscribers,
        })

    async def _messages_handler(self, request):
        try:
            limit = int(request.query.get("limit", 50))
        except (TypeError, ValueError):
            limit = 50
        try:
            offset = int(request.query.get("offset", 0))
        except (TypeError, ValueError):
            offset = 0
        limit = max(0, min(limit, 1000))
        offset = max(0, offset)
        messages = await self.store.history(limit=limit, offset=offset)
        total = await self.store.count()
        return web.json_response({
            "messages": messages,
            "limit": limit,
            "offset": offset,
            "total": total,
        })

    async def serve_forever(self) -> None:
        """Block forever, serving both endpoints."""
        stop = asyncio.Event()
        await stop.wait()


async def main() -> None:
    server = NotificationServer()
    await server.start()
    print(
        f"WebSocket server listening on ws://{DEFAULT_WS_HOST}:{server.ws_port} "
        f"and health on http://{DEFAULT_HTTP_HOST}:{server.http_port}"
    )
    await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
