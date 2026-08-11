import asyncio
import json
import os
import sqlite3
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from http import HTTPStatus
from urllib.parse import unquote

import websockets
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed


# ── Transport Error ──────────────────────────────────────────────


class TransportError(Exception):
    pass


class ConnectionClosedError(TransportError):
    pass


# ── Base Transport ───────────────────────────────────────────────


class BaseTransport(ABC):
    @abstractmethod
    async def on_connect(self, client):
        """Called when a new client connects."""

    @abstractmethod
    async def on_disconnect(self, client):
        """Called when a client disconnects."""

    @abstractmethod
    async def send_message(self, client, message_str):
        """Send a message to a specific client."""

    @abstractmethod
    async def broadcast(self, clients, message_str, exclude=None):
        """Send a message to all clients in the list."""

    @abstractmethod
    async def serve(self, handler, host, port, http_handler=None):
        """Start the transport and process connections."""


# ── Client Registry ──────────────────────────────────────────────


class ClientRegistry:
    def __init__(self):
        self._clients = {}
        self._subscriptions = {}
        self._lock = asyncio.Lock()

    async def register(self, websocket):
        client_id = str(uuid.uuid4())
        async with self._lock:
            self._clients[websocket] = client_id
        return client_id

    async def unregister(self, websocket):
        async with self._lock:
            return self._clients.pop(websocket, None)

    async def get_all(self):
        async with self._lock:
            return list(self._clients.items())

    async def get_count(self):
        async with self._lock:
            return len(self._clients)

    async def get_client_id(self, websocket):
        async with self._lock:
            return self._clients.get(websocket)

    async def subscribe(self, websocket, channel):
        async with self._lock:
            if channel not in self._subscriptions:
                self._subscriptions[channel] = set()
            self._subscriptions[channel].add(websocket)

    async def unsubscribe(self, websocket, channel):
        async with self._lock:
            if channel in self._subscriptions:
                self._subscriptions[channel].discard(websocket)
                if not self._subscriptions[channel]:
                    del self._subscriptions[channel]

    async def unsubscribe_all(self, websocket):
        async with self._lock:
            for subs in list(self._subscriptions.values()):
                subs.discard(websocket)
            self._subscriptions = {
                k: v for k, v in self._subscriptions.items() if v
            }

    async def get_channels(self):
        async with self._lock:
            return {
                channel: len(subs)
                for channel, subs in self._subscriptions.items()
            }

    async def get_channel_subscribers(self, channel):
        async with self._lock:
            subs = self._subscriptions.get(channel, set())
            return [self._clients[ws] for ws in subs if ws in self._clients]

    async def get_channel_websockets(self, channel):
        async with self._lock:
            return list(self._subscriptions.get(channel, set()))


registry = ClientRegistry()


# ── Message Helper ───────────────────────────────────────────────


def message(type_, payload):
    return json.dumps({
        "type": type_,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ── Config ───────────────────────────────────────────────────────


REDIS_URL = os.environ.get("REDIS_URL", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "messages.db")
SERVER_ID = str(uuid.uuid4())
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "100"))
MESSAGE_TTL_DAYS = int(os.environ.get("MESSAGE_TTL_DAYS", "7"))


# ── Rate Limiting ────────────────────────────────────────────────

_rate_limit_cache = {}
_rate_limit_lock = asyncio.Lock()


async def _check_rate_limit(client_id):
    window = 60
    r = await _get_redis()
    if r is not None:
        try:
            key = f"ratelimit:{client_id}"
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, window)
            current = (await pipe.execute())[0]
            if current > RATE_LIMIT:
                return False
            return True
        except Exception:
            pass

    now = datetime.now(timezone.utc).timestamp()
    async with _rate_limit_lock:
        if client_id not in _rate_limit_cache:
            _rate_limit_cache[client_id] = []
        timestamps = _rate_limit_cache[client_id]
        timestamps = [t for t in timestamps if now - t < window]
        _rate_limit_cache[client_id] = timestamps
        if len(timestamps) >= RATE_LIMIT:
            return False
        timestamps.append(now)
        return True


# ── SQLite Persistence ───────────────────────────────────────────


def _get_db():
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    with _get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  channel TEXT,"
            "  type TEXT NOT NULL,"
            "  payload TEXT NOT NULL,"
            "  timestamp TEXT NOT NULL"
            ")"
        )
        conn.commit()


def _persist_message(type_, payload, channel=None):
    try:
        with _get_db() as conn:
            conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (channel, type_, json.dumps(payload), datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
    except Exception:
        pass


def _get_messages(limit=50, offset=0):
    with _get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def _get_history(channel=None, since=None, limit=50):
    with _get_db() as conn:
        query = "SELECT * FROM messages WHERE 1=1"
        params = []

        if channel is not None:
            query += " AND channel = ?"
            params.append(channel)

        if since is not None:
            query += " AND timestamp > ?"
            params.append(since)

        query += " ORDER BY timestamp ASC LIMIT ?"
        params.append(limit + 1)

        rows = conn.execute(query, params).fetchall()
        messages = [dict(r) for r in rows]
        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]
        return messages, has_more


async def _cleanup_expired_messages():
    while True:
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=MESSAGE_TTL_DAYS)).isoformat()
            with _get_db() as conn:
                conn.execute(
                    "DELETE FROM messages WHERE timestamp < ?",
                    (cutoff,),
                )
                conn.commit()
        except Exception:
            pass
        await asyncio.sleep(3600)


# ── Redis ────────────────────────────────────────────────────────

_redis_pool = None


async def _get_redis():
    global _redis_pool
    if _redis_pool is None:
        if REDIS_URL:
            try:
                import redis.asyncio as aioredis
                _redis_pool = aioredis.Redis.from_url(REDIS_URL)
                return _redis_pool
            except Exception:
                pass
        _redis_pool = False
        return None
    return _redis_pool if _redis_pool is not False else None


async def _publish_to_redis(channel, message_str):
    r = await _get_redis()
    if r is None:
        return
    try:
        envelope = json.dumps({
            "source": SERVER_ID,
            "channel": channel,
            "data": message_str,
        })
        await r.publish("broadcast", envelope)
    except Exception:
        pass


async def _store_client_in_redis(client_id):
    r = await _get_redis()
    if r is None:
        return
    try:
        await r.sadd("connected_clients", client_id)
    except Exception:
        pass


async def _remove_client_from_redis(client_id):
    r = await _get_redis()
    if r is None:
        return
    try:
        await r.srem("connected_clients", client_id)
    except Exception:
        pass


async def _redis_subscriber():
    r = await _get_redis()
    if r is None:
        return
    try:
        pubsub = r.pubsub()
        await pubsub.subscribe("broadcast")
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg is None:
                await asyncio.sleep(0.01)
                continue
            try:
                envelope = json.loads(msg["data"])
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
            if envelope.get("source") == SERVER_ID:
                continue
            channel = envelope.get("channel")
            if channel:
                await broadcast_to_channel(envelope["data"], channel)
            else:
                await broadcast(envelope["data"])
    except Exception:
        pass
    finally:
        try:
            await pubsub.unsubscribe("broadcast")
        except Exception:
            pass


# ── WebSocket Transport ──────────────────────────────────────────


class WebSocketTransport(BaseTransport):
    def __init__(self):
        self._server = None

    async def on_connect(self, client):
        pass

    async def on_disconnect(self, client):
        pass

    async def send_message(self, client, message_str):
        await client.send(message_str)

    async def broadcast(self, clients, message_str, exclude=None):
        for client in clients:
            if client is exclude:
                continue
            try:
                await client.send(message_str)
            except ConnectionClosed:
                await registry.unsubscribe_all(client)
                await registry.unregister(client)

    async def serve(self, handler, host, port, http_handler=None):
        async def _ws_handler(websocket):
            await self.on_connect(websocket)
            try:
                await handler(websocket)
            finally:
                await self.on_disconnect(websocket)

        async with serve(
            _ws_handler,
            host,
            port,
            process_request=http_handler,
        ) as server:
            self._server = server
            await server.serve_forever()


# ── Transport Factory ────────────────────────────────────────────


def get_transport():
    transport_type = os.environ.get("TRANSPORT", "websocket").lower()
    if transport_type == "websocket":
        return WebSocketTransport()
    raise ValueError(f"Unknown transport type: {transport_type}")


# ── Transport Module-Level Reference ─────────────────────────────

transport = None


# ── Broadcasting ─────────────────────────────────────────────────


async def broadcast(message_str, exclude=None):
    clients = await registry.get_all()
    ws_list = [ws for ws, _ in clients]
    await transport.broadcast(ws_list, message_str, exclude=exclude)


async def broadcast_to_channel(message_str, channel):
    subs = await registry.get_channel_websockets(channel)
    await transport.broadcast(subs, message_str)


# ── Handler ──────────────────────────────────────────────────────


async def handler(websocket):
    client_id = await registry.register(websocket)
    await _store_client_in_redis(client_id)

    welcome = message("system", {
        "client_id": client_id,
        "message": "connected",
    })
    await transport.send_message(websocket, welcome)

    _persist_message("system", {"client_id": client_id, "message": "connected"})

    join_msg = message("system", {
        "client_id": client_id,
        "message": "joined",
    })
    _persist_message("system", {"client_id": client_id, "message": "joined"})
    await _publish_to_redis(None, join_msg)
    await broadcast(join_msg, exclude=websocket)

    try:
        async for raw in websocket:
            if not await _check_rate_limit(client_id):
                error_msg = message("error", {"message": "Rate limit exceeded. Please wait before sending more messages."})
                await transport.send_message(websocket, error_msg)
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            msg_type = data.get("type", "broadcast")
            payload = data.get("payload", {})

            if msg_type == "subscribe":
                channel = data.get("channel")
                if channel:
                    await registry.subscribe(websocket, channel)
                continue

            if msg_type == "unsubscribe":
                channel = data.get("channel")
                if channel:
                    await registry.unsubscribe(websocket, channel)
                continue

            msg_str = message(msg_type, payload)

            channel = data.get("channel")

            _persist_message(msg_type, payload, channel)
            await _publish_to_redis(channel, msg_str)

            if channel:
                await broadcast_to_channel(msg_str, channel)
            else:
                await broadcast(msg_str)
    finally:
        await registry.unsubscribe_all(websocket)
        await registry.unregister(websocket)
        await _remove_client_from_redis(client_id)
        leave_msg = message("system", {
            "client_id": client_id,
            "message": "left",
        })
        _persist_message("system", {"client_id": client_id, "message": "left"})
        await _publish_to_redis(None, leave_msg)
        await broadcast(leave_msg)


# ── HTTP ─────────────────────────────────────────────────────────


def _parse_query_string(path):
    limit = 50
    offset = 0
    if "?" in path:
        qs = path.split("?", 1)[1]
        for pair in qs.split("&"):
            if "=" in pair:
                key, val = pair.split("=", 1)
                if key == "limit":
                    try:
                        limit = int(val)
                    except ValueError:
                        pass
                elif key == "offset":
                    try:
                        offset = int(val)
                    except ValueError:
                        pass
    return limit, offset


async def process_request(connection, request):
    if request.path == "/health":
        count = await registry.get_count()
        body = json.dumps({"connected_clients": count})
        response = connection.respond(HTTPStatus.OK, body)
        response.headers["Content-Type"] = "application/json"
        return response

    if request.path.startswith("/messages"):
        limit, offset = _parse_query_string(request.path)
        messages = _get_messages(limit, offset)
        body = json.dumps(messages)
        response = connection.respond(HTTPStatus.OK, body)
        response.headers["Content-Type"] = "application/json"
        return response

    if request.path.startswith("/history"):
        channel = None
        since = None
        limit = 50

        if "?" in request.path:
            qs = request.path.split("?", 1)[1]
            for pair in qs.split("&"):
                if "=" in pair:
                    key, val = pair.split("=", 1)
                    if key == "channel":
                        channel = unquote(val)
                    elif key == "since":
                        since = unquote(val)
                    elif key == "limit":
                        try:
                            limit = int(val)
                        except ValueError:
                            pass

        if not channel:
            body = json.dumps({"error": "channel parameter required"})
            response = connection.respond(HTTPStatus.BAD_REQUEST, body)
            response.headers["Content-Type"] = "application/json"
            return response

        messages, has_more = _get_history(channel=channel, since=since, limit=limit)
        body = json.dumps({"messages": messages, "has_more": has_more})
        response = connection.respond(HTTPStatus.OK, body)
        response.headers["Content-Type"] = "application/json"
        return response

    if request.path == "/channels":
        channels = await registry.get_channels()
        body = json.dumps(channels)
        response = connection.respond(HTTPStatus.OK, body)
        response.headers["Content-Type"] = "application/json"
        return response

    if request.path.startswith("/channels/") and request.path.endswith("/subscribers"):
        channel_name = request.path[len("/channels/"):-len("/subscribers")]
        subscribers = await registry.get_channel_subscribers(channel_name)
        body = json.dumps(subscribers)
        response = connection.respond(HTTPStatus.OK, body)
        response.headers["Content-Type"] = "application/json"
        return response

    return None


# ── Main ─────────────────────────────────────────────────────────


async def main(host="localhost", port=8765):
    global transport
    _init_db()
    transport = get_transport()
    subscriber_task = None
    cleanup_task = asyncio.ensure_future(_cleanup_expired_messages())
    if REDIS_URL:
        subscriber_task = asyncio.ensure_future(_redis_subscriber())
    try:
        await transport.serve(handler, host, port, http_handler=process_request)
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        if subscriber_task:
            subscriber_task.cancel()
            try:
                await subscriber_task
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    asyncio.run(main())
