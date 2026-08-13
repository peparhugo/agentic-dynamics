"""WebSocket-based notification server.

Accepts WebSocket connections, assigns each client a unique ID, and lets
clients broadcast JSON notifications to every connected peer or send one
directly to another client by ID. Clients may also subscribe to named
channels; broadcast messages that carry a 'channel' field are delivered
only to that channel's subscribers. Exposes GET /health, GET /channels,
GET /channels/{name}/subscribers, and GET /messages over plain HTTP on
the same port.

Redis pub/sub is the message backbone: publishing a message (broadcast or
direct) writes it to SQLite for history and publishes an event on a Redis
channel. A background worker task subscribed to that channel performs the
actual local delivery. Because delivery is driven purely by each process's
own local ClientRegistry/ChannelRegistry, multiple server instances can
share the same Redis backbone: every instance receives every published
event and each delivers only to the clients connected to it. The set of
currently-connected client IDs is mirrored in Redis so any instance can
answer "is this client connected somewhere" even after a restart wipes
its local, in-memory registry.
"""

import asyncio
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Optional
from urllib.parse import parse_qs

import aiosqlite
import redis.asyncio as aioredis
from websockets.asyncio.server import serve, ServerConnection
from websockets.exceptions import ConnectionClosed

MESSAGE_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}

CHANNEL_SUBSCRIBERS_PATH = re.compile(r"^/channels/([^/]+)/subscribers$")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL = os.environ.get("DATABASE_URL", "notifications.db")

REDIS_EVENTS_CHANNEL = "notifications:events"
CONNECTED_CLIENTS_KEY = "notifications:connected_clients"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_message(msg_type: str, payload: dict) -> str:
    return json.dumps({"type": msg_type, "payload": payload, "timestamp": now_iso()})


class ClientRegistry:
    """Tracks connected clients behind a lock, protecting registration and
    removal against concurrent access from multiple handler coroutines."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = threading.Lock()

    def add(self, connection: ServerConnection) -> str:
        client_id = uuid.uuid4().hex
        with self._lock:
            self._clients[client_id] = connection
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str) -> Optional[ServerConnection]:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> list[tuple[str, ServerConnection]]:
        with self._lock:
            return list(self._clients.items())

    def count(self) -> int:
        with self._lock:
            return len(self._clients)


class ChannelRegistry:
    """Tracks channel subscriptions behind a lock, mapping each channel name
    to the set of client IDs currently subscribed to it."""

    def __init__(self) -> None:
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    def remove_client(self, client_id: str) -> None:
        with self._lock:
            for channel in list(self._channels.keys()):
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    def channel_counts(self) -> dict[str, int]:
        with self._lock:
            return {name: len(ids) for name, ids in self._channels.items()}


registry = ClientRegistry()
channels = ChannelRegistry()

redis_client: Optional[aioredis.Redis] = None

_worker_task: Optional[asyncio.Task] = None
_start_lock = asyncio.Lock()
_db_ready = False


# ── Redis backbone ──────────────────────────────────────────────

async def get_redis_client() -> aioredis.Redis:
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    return redis_client


async def publish_event(event: dict) -> None:
    client = await get_redis_client()
    await client.publish(REDIS_EVENTS_CHANNEL, json.dumps(event))


async def deliver_broadcast(message: dict, channel: Optional[str], *, reg=None, chans=None) -> None:
    """Send an already-built message to locally-connected clients. Used by
    the Redis worker task, so this only ever touches this process's own
    registries -- delivery to clients on other instances happens in their
    own worker task, which receives the same published event."""
    reg = registry if reg is None else reg
    chans = channels if chans is None else chans
    if channel:
        targets = [(cid, reg.get(cid)) for cid in chans.subscribers(channel)]
    else:
        targets = reg.snapshot()
    text = json.dumps(message)
    for _client_id, connection in targets:
        if connection is None:
            continue
        try:
            await connection.send(text)
        except ConnectionClosed:
            pass


async def deliver_direct(message: dict, target_id: str, *, reg=None) -> None:
    reg = registry if reg is None else reg
    connection = reg.get(target_id)
    if connection is None:
        return
    try:
        await connection.send(json.dumps(message))
    except ConnectionClosed:
        pass


async def redis_worker(client: aioredis.Redis, *, reg=None, chans=None) -> None:
    """Subscribes to the shared Redis events channel and delivers each
    published message to this instance's locally-connected clients."""
    pubsub = client.pubsub()
    await pubsub.subscribe(REDIS_EVENTS_CHANNEL)
    try:
        async for raw in pubsub.listen():
            if raw.get("type") != "message":
                continue
            event = json.loads(raw["data"])
            message = event["message"]
            if event["delivery"] == "broadcast":
                await deliver_broadcast(
                    message, message["payload"].get("channel"), reg=reg, chans=chans
                )
            elif event["delivery"] == "direct":
                await deliver_direct(message, event["target"], reg=reg)
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(REDIS_EVENTS_CHANNEL)
        await pubsub.aclose()


async def ensure_started() -> None:
    """Idempotently initializes the SQLite schema and starts this process's
    Redis worker task. Safe to call from every request handler."""
    global _worker_task, _db_ready
    async with _start_lock:
        if not _db_ready:
            await init_db()
            _db_ready = True
        client = await get_redis_client()
        if _worker_task is None or _worker_task.done():
            _worker_task = asyncio.create_task(redis_worker(client))


# ── SQLite persistence ──────────────────────────────────────────

async def init_db() -> None:
    async with aiosqlite.connect(DATABASE_URL) as conn:
        await conn.execute(
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
        await conn.commit()


async def store_message(channel: Optional[str], msg_type: str, payload: dict, timestamp: str) -> None:
    async with aiosqlite.connect(DATABASE_URL) as conn:
        await conn.execute(
            "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
            (channel, msg_type, json.dumps(payload), timestamp),
        )
        await conn.commit()


async def fetch_messages(limit: int = 50, offset: int = 0) -> list[dict]:
    async with aiosqlite.connect(DATABASE_URL) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT id, channel, type, payload, timestamp FROM messages "
            "ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
    return [
        {
            "id": row["id"],
            "channel": row["channel"],
            "type": row["type"],
            "payload": json.loads(row["payload"]),
            "timestamp": row["timestamp"],
        }
        for row in rows
    ]


# ── Message publishing (broadcast / direct) ─────────────────────

async def broadcast(payload: dict) -> None:
    message = json.loads(make_message("broadcast", payload))
    await store_message(payload.get("channel"), "broadcast", payload, message["timestamp"])
    await publish_event({"delivery": "broadcast", "message": message})


async def send_direct(target_id: str, payload: dict) -> bool:
    client = await get_redis_client()
    if not await client.sismember(CONNECTED_CLIENTS_KEY, target_id):
        return False
    message = json.loads(make_message("direct", payload))
    await store_message(None, "direct", payload, message["timestamp"])
    await publish_event({"delivery": "direct", "target": target_id, "message": message})
    return True


async def handle_message(connection: ServerConnection, client_id: str, raw: str) -> None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        await connection.send(make_message("system", {"error": "invalid JSON"}))
        return

    if not isinstance(data, dict):
        await connection.send(make_message("system", {"error": "message must be a JSON object"}))
        return

    msg_type = data.get("type")
    payload = data.get("payload", {})

    if msg_type not in MESSAGE_TYPES:
        await connection.send(
            make_message("system", {"error": f"unsupported type: {msg_type!r}"})
        )
        return

    if not isinstance(payload, dict):
        await connection.send(make_message("system", {"error": "payload must be an object"}))
        return

    if msg_type == "broadcast":
        await broadcast(payload)
    elif msg_type == "direct":
        target_id = payload.get("target")
        if not target_id:
            await connection.send(
                make_message("system", {"error": "direct message requires 'target' in payload"})
            )
            return
        delivered = await send_direct(target_id, payload)
        if not delivered:
            await connection.send(
                make_message("system", {"error": f"client {target_id} not connected"})
            )
    elif msg_type == "system":
        await connection.send(make_message("system", {"ack": True}))
    elif msg_type == "subscribe":
        channel = payload.get("channel")
        if not channel:
            await connection.send(
                make_message("system", {"error": "subscribe requires 'channel' in payload"})
            )
            return
        channels.subscribe(client_id, channel)
        await connection.send(make_message("system", {"event": "subscribed", "channel": channel}))
    elif msg_type == "unsubscribe":
        channel = payload.get("channel")
        if not channel:
            await connection.send(
                make_message("system", {"error": "unsubscribe requires 'channel' in payload"})
            )
            return
        channels.unsubscribe(client_id, channel)
        await connection.send(make_message("system", {"event": "unsubscribed", "channel": channel}))


async def handler(connection: ServerConnection) -> None:
    await ensure_started()
    client_id = registry.add(connection)
    client = await get_redis_client()
    await client.sadd(CONNECTED_CLIENTS_KEY, client_id)
    try:
        await connection.send(make_message("system", {"event": "connected", "client_id": client_id}))
        async for raw in connection:
            await handle_message(connection, client_id, raw)
    except ConnectionClosed:
        pass
    finally:
        registry.remove(client_id)
        channels.remove_client(client_id)
        await client.srem(CONNECTED_CLIENTS_KEY, client_id)


# ── HTTP endpoints ───────────────────────────────────────────────

def _parse_int(query: dict, key: str, default: int, minimum: int, maximum: Optional[int] = None) -> int:
    raw = query.get(key, [None])[0]
    if raw is None:
        value = default
    else:
        try:
            value = int(raw)
        except ValueError:
            value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


async def process_request(connection: ServerConnection, request):
    await ensure_started()
    path, _, query_string = request.path.partition("?")

    if path == "/health":
        response = connection.respond(HTTPStatus.OK, "")
        response.headers["Content-Type"] = "application/json"
        response.body = json.dumps({"connected_clients": registry.count()}).encode()
        return response

    if path == "/channels":
        response = connection.respond(HTTPStatus.OK, "")
        response.headers["Content-Type"] = "application/json"
        response.body = json.dumps({
            "channels": [
                {"name": name, "subscribers": count}
                for name, count in sorted(channels.channel_counts().items())
            ]
        }).encode()
        return response

    match = CHANNEL_SUBSCRIBERS_PATH.match(path)
    if match:
        channel_name = match.group(1)
        response = connection.respond(HTTPStatus.OK, "")
        response.headers["Content-Type"] = "application/json"
        response.body = json.dumps({
            "channel": channel_name,
            "subscribers": channels.subscribers(channel_name),
        }).encode()
        return response

    if path == "/messages":
        query = parse_qs(query_string)
        limit = _parse_int(query, "limit", default=50, minimum=1, maximum=500)
        offset = _parse_int(query, "offset", default=0, minimum=0)
        rows = await fetch_messages(limit=limit, offset=offset)
        response = connection.respond(HTTPStatus.OK, "")
        response.headers["Content-Type"] = "application/json"
        response.body = json.dumps({
            "messages": rows,
            "limit": limit,
            "offset": offset,
        }).encode()
        return response

    return None


async def main(host: str = "localhost", port: int = 8765) -> None:
    await ensure_started()
    async with serve(handler, host, port, process_request=process_request):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
