import asyncio
import json
import os
import sqlite3
import threading
import time as _time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import redis.asyncio as redis
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
DATABASE_URL = os.environ.get("DATABASE_URL", "messages.db")
TRANSPORT = os.environ.get("TRANSPORT", "websocket")
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "100"))
MESSAGE_TTL_DAYS = int(os.environ.get("MESSAGE_TTL_DAYS", "7"))

_server_id = str(uuid.uuid4())


class RateLimiter:
    def __init__(self, limit=100, redis_client=None):
        self._limit = limit
        self._redis = redis_client
        self._local = {}
        self._lock = threading.Lock()

    async def check(self, client_id):
        if self._redis is not None:
            return await self._check_redis(client_id)
        return self._check_local(client_id)

    async def _check_redis(self, client_id):
        try:
            key = f"rate_limit:{client_id}"
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, 60)
            return count <= self._limit
        except Exception:
            return self._check_local(client_id)

    def _check_local(self, client_id):
        now = _time.monotonic()
        with self._lock:
            if client_id not in self._local:
                self._local[client_id] = (1, now)
                return True
            count, window_start = self._local[client_id]
            if now - window_start > 60:
                self._local[client_id] = (1, now)
                return True
            if count < self._limit:
                self._local[client_id] = (count + 1, window_start)
                return True
            return False


rate_limiter = RateLimiter(limit=RATE_LIMIT)


class BaseTransport(ABC):
    @abstractmethod
    async def on_connect(self, client_id):
        pass

    @abstractmethod
    async def on_disconnect(self, client_id):
        pass

    @abstractmethod
    async def send_message(self, client_id, message):
        pass

    @abstractmethod
    async def broadcast(self, client_ids, message):
        pass


class WebSocketTransport(BaseTransport):
    async def on_connect(self, client_id):
        pass

    async def on_disconnect(self, client_id):
        pass

    async def send_message(self, client_id, message):
        ws = registry.get_client(client_id)
        if ws is not None:
            try:
                await ws.send(message)
            except ConnectionClosed:
                pass

    async def broadcast(self, client_ids, message):
        for cid in client_ids:
            await self.send_message(cid, message)


def _create_transport():
    name = TRANSPORT
    if name == "websocket":
        return WebSocketTransport()
    raise ValueError(f"Unknown transport: {name}")


transport = _create_transport()


class MessageStore:
    def __init__(self, db_path):
        self._lock = threading.Lock()
        self._db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT,
                type TEXT,
                payload TEXT,
                timestamp TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_timestamp
            ON messages(timestamp DESC)
        """)
        conn.commit()
        conn.close()

    def store(self, channel, msg_type, payload, timestamp):
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (channel or "", msg_type, json.dumps(payload), timestamp),
            )
            conn.commit()
            conn.close()

    def get_messages(self, limit=50, offset=0):
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            conn.close()
            result = []
            for r in rows:
                item = dict(r)
                item["payload"] = json.loads(item["payload"])
                result.append(item)
            return result

    def get_history(self, channel, since=None, limit=50):
        with self._lock:
            conn = self._get_conn()
            query = "SELECT * FROM messages WHERE channel = ?"
            params = [channel]
            if since:
                query += " AND timestamp >= ?"
                params.append(since)
            query += " ORDER BY id ASC LIMIT ?"
            params.append(limit + 1)
            rows = conn.execute(query, params).fetchall()
            conn.close()
            has_more = len(rows) > limit
            rows = rows[:limit]
            result = []
            for r in rows:
                item = dict(r)
                item["payload"] = json.loads(item["payload"])
                result.append(item)
            return {"messages": result, "has_more": has_more}

    def delete_older_than(self, cutoff):
        with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff,))
            conn.commit()
            conn.close()

    def clear(self):
        with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM messages")
            conn.commit()
            conn.close()


message_store = MessageStore(DATABASE_URL)


class ClientRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._clients = {}

    def add(self, client_id, websocket):
        with self._lock:
            self._clients[client_id] = websocket

    def remove(self, client_id):
        with self._lock:
            self._clients.pop(client_id, None)

    def get_count(self):
        with self._lock:
            return len(self._clients)

    def get_all_websockets(self):
        with self._lock:
            return list(self._clients.values())

    def get_client(self, client_id):
        with self._lock:
            return self._clients.get(client_id)

    def get_ids(self):
        with self._lock:
            return set(self._clients.keys())

    def clear(self):
        with self._lock:
            self._clients.clear()


registry = ClientRegistry()


class ChannelManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._channels = {}

    def subscribe(self, client_id, channel):
        with self._lock:
            if channel not in self._channels:
                self._channels[channel] = set()
            self._channels[channel].add(client_id)

    def unsubscribe(self, client_id, channel):
        with self._lock:
            if channel in self._channels:
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def get_subscribers(self, channel):
        with self._lock:
            return set(self._channels.get(channel, set()))

    def remove_client(self, client_id):
        with self._lock:
            for channel in list(self._channels):
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def list_channels(self):
        with self._lock:
            return {name: len(subs) for name, subs in self._channels.items()}

    def clear(self):
        with self._lock:
            self._channels.clear()


channels = ChannelManager()


def make_message(msg_type, payload):
    return json.dumps({
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


redis_client = None
redis_available = False


async def _init_redis():
    global redis_client, redis_available
    try:
        redis_client = redis.from_url(REDIS_URL)
        await redis_client.ping()
        redis_available = True
    except Exception:
        redis_available = False
        redis_client = None


async def _publish_to_redis(channel_name, msg_type, payload):
    if not redis_available or redis_client is None:
        return
    try:
        redis_channel = f"messages:{channel_name or 'global'}"
        data = json.dumps({
            "_server_id": _server_id,
            "type": msg_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        await redis_client.publish(redis_channel, data)
    except Exception:
        pass


async def _sync_subscribe_to_redis(client_id, channel_name):
    if not redis_available or redis_client is None:
        return
    try:
        await redis_client.sadd(f"channel:{channel_name}:subscribers", client_id)
        await redis_client.hset(f"client:{client_id}", mapping={
            "channels": channel_name,
            "server_id": _server_id,
        })
    except Exception:
        pass


async def _sync_unsubscribe_from_redis(client_id, channel_name):
    if not redis_available or redis_client is None:
        return
    try:
        await redis_client.srem(f"channel:{channel_name}:subscribers", client_id)
    except Exception:
        pass


async def _sync_disconnect_to_redis(client_id):
    if not redis_available or redis_client is None:
        return
    try:
        await redis_client.delete(f"client:{client_id}")
    except Exception:
        pass


async def redis_subscriber():
    if not redis_available or redis_client is None:
        return
    pubsub = redis_client.pubsub()
    try:
        await pubsub.psubscribe("messages:*")
        async for message in pubsub.listen():
            if message["type"] != "pmessage":
                continue
            channel_raw = message["channel"]
            if isinstance(channel_raw, bytes):
                channel_raw = channel_raw.decode()
            channel_name = channel_raw.split(":", 1)[1] if ":" in channel_raw else "global"
            data_raw = message["data"]
            if isinstance(data_raw, bytes):
                data_raw = data_raw.decode()
            try:
                data = json.loads(data_raw)
            except json.JSONDecodeError:
                continue
            if data.get("_server_id") == _server_id:
                continue
            msg_type = data.get("type", "broadcast")
            payload = data.get("payload", {})
            msg = make_message(msg_type, payload)
            if channel_name == "global":
                await transport.broadcast(registry.get_ids(), msg)
            else:
                await transport.broadcast(channels.get_subscribers(channel_name), msg)
    except Exception:
        pass


async def handler(websocket):
    client_id = str(uuid.uuid4())
    registry.add(client_id, websocket)
    await transport.on_connect(client_id)
    try:
        await transport.send_message(client_id, make_message("system", {
            "message": f"Connected as {client_id}",
            "client_id": client_id,
        }))

        async for raw in websocket:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")
            payload = data.get("payload", {})

            if not await rate_limiter.check(client_id):
                await transport.send_message(client_id, json.dumps({
                    "type": "error",
                    "payload": {
                        "code": "rate_limit_exceeded",
                        "message": "Rate limit exceeded. Max {} messages per minute.".format(
                            rate_limiter._limit),
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))
                continue

            if msg_type == "subscribe":
                channel_name = payload.get("channel")
                if channel_name:
                    channels.subscribe(client_id, channel_name)
                    await _sync_subscribe_to_redis(client_id, channel_name)
            elif msg_type == "unsubscribe":
                channel_name = payload.get("channel")
                if channel_name:
                    channels.unsubscribe(client_id, channel_name)
                    await _sync_unsubscribe_from_redis(client_id, channel_name)
            elif msg_type == "broadcast":
                channel = data.get("channel")
                timestamp = datetime.now(timezone.utc).isoformat()
                message_store.store(channel or "global", "broadcast", payload, timestamp)
                await _publish_to_redis(channel, "broadcast", payload)
                msg = make_message("broadcast", payload)
                if channel:
                    await transport.broadcast(channels.get_subscribers(channel), msg)
                else:
                    await transport.broadcast(registry.get_ids(), msg)
            elif msg_type == "direct":
                target_id = payload.get("target")
                timestamp = datetime.now(timezone.utc).isoformat()
                message_store.store("direct", "direct", payload, timestamp)
                await _publish_to_redis("direct", "direct", payload)
                await transport.send_message(target_id, make_message("direct", payload))
    finally:
        channels.remove_client(client_id)
        registry.remove(client_id)
        await _sync_disconnect_to_redis(client_id)
        await transport.on_disconnect(client_id)


async def http_handler(reader, writer):
    request_line = await reader.readline()
    parts = request_line.decode().strip().split()
    if len(parts) < 2:
        writer.close()
        await writer.wait_closed()
        return

    method = parts[0]
    path = parts[1]

    while True:
        line = await reader.readline()
        if not line or line in (b"\r\n", b"\n"):
            break

    body = b""
    status = b"200 OK"

    parsed = urlparse(path)
    path_only = parsed.path
    qs = parse_qs(parsed.query)

    if path_only == "/health":
        count = registry.get_count()
        body = json.dumps({"clients_connected": count}).encode()
    elif path_only == "/channels":
        data = channels.list_channels()
        body = json.dumps(data).encode()
    elif path_only.startswith("/channels/") and path_only.endswith("/subscribers"):
        channel_name = path_only[len("/channels/"):-len("/subscribers")]
        subs = channels.get_subscribers(channel_name)
        body = json.dumps(list(subs)).encode()
    elif path_only == "/messages":
        try:
            limit = int(qs.get("limit", ["50"])[0])
        except (ValueError, IndexError):
            limit = 50
        try:
            offset = int(qs.get("offset", ["0"])[0])
        except (ValueError, IndexError):
            offset = 0
        messages = message_store.get_messages(limit=limit, offset=offset)
        body = json.dumps(messages).encode()
    elif path_only == "/history":
        channel = qs.get("channel", [None])[0]
        if not channel:
            status = b"400 Bad Request"
            body = json.dumps({"error": "channel query parameter is required"}).encode()
        else:
            since = qs.get("since", [None])[0]
            try:
                limit = int(qs.get("limit", ["50"])[0])
            except (ValueError, IndexError):
                limit = 50
            result = message_store.get_history(channel=channel, since=since, limit=limit)
            body = json.dumps(result).encode()
    else:
        status = b"404 Not Found"
        body = json.dumps({"error": "not found"}).encode()

    writer.write(
        b"HTTP/1.1 " + status + b"\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
        b"Connection: close\r\n"
        b"\r\n"
        + body
    )
    await writer.drain()
    writer.close()
    await writer.wait_closed()


async def cleanup_old_messages(ttl_days=MESSAGE_TTL_DAYS):
    while True:
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=ttl_days)).isoformat()
            message_store.delete_older_than(cutoff)
        except Exception:
            pass
        await asyncio.sleep(3600)


async def start(ws_host="127.0.0.1", ws_port=8765, http_host="127.0.0.1", http_port=8080,
                redis_url=None, database_url=None, rate_limit=None, message_ttl_days=None):
    global REDIS_URL, DATABASE_URL, _server_id, rate_limiter, MESSAGE_TTL_DAYS
    if redis_url is not None:
        REDIS_URL = redis_url
    if database_url is not None:
        DATABASE_URL = database_url
        global message_store
        message_store = MessageStore(DATABASE_URL)
    if message_ttl_days is not None:
        MESSAGE_TTL_DAYS = message_ttl_days
    _server_id = str(uuid.uuid4())

    limit = rate_limit if rate_limit is not None else RATE_LIMIT
    rate_limiter = RateLimiter(limit=limit)

    await _init_redis()

    if redis_available and redis_client is not None:
        rate_limiter._redis = redis_client

    ws_server = await serve(handler, ws_host, ws_port)
    http_server = await asyncio.start_server(http_handler, http_host, http_port)

    subscriber_task = asyncio.create_task(redis_subscriber())
    cleanup_task = asyncio.create_task(cleanup_old_messages(MESSAGE_TTL_DAYS))

    return ws_server, http_server, subscriber_task, cleanup_task


async def main():
    import os as _os
    ws_server, http_server, _, _ = await start(
        redis_url=_os.environ.get("REDIS_URL", "redis://localhost:6379"),
        database_url=_os.environ.get("DATABASE_URL", "messages.db"),
    )
    print(f"WebSocket server on ws://127.0.0.1:8765")
    print(f"HTTP endpoints on http://127.0.0.1:8080")
    await asyncio.gather(
        ws_server.wait_closed(),
        http_server.serve_forever(),
    )


if __name__ == "__main__":
    asyncio.run(main())
