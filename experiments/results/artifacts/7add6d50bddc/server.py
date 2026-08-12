import asyncio
import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

from transport import BaseTransport, WebSocketTransport

TRANSPORT = os.environ.get("TRANSPORT", "websocket")
REDIS_URL = os.environ.get("REDIS_URL", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "messages.db")
REDIS_CHANNEL = "chat:messages"
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "100"))
MESSAGE_TTL_DAYS = int(os.environ.get("MESSAGE_TTL_DAYS", "7"))

redis_client = None
_message_db_initialized = False
_subscriber_task = None

_rate_limits = {}
_rate_lock = threading.Lock()


class ClientRegistry:
    def __init__(self):
        self._clients = {}
        self._channels = {}
        self._lock = threading.Lock()

    def add(self, client_id, websocket):
        with self._lock:
            self._clients[client_id] = websocket

    def remove(self, client_id):
        with self._lock:
            self._clients.pop(client_id, None)
            empty_channels = []
            for channel, subscribers in self._channels.items():
                subscribers.discard(client_id)
                if not subscribers:
                    empty_channels.append(channel)
            for channel in empty_channels:
                del self._channels[channel]

    def get(self, client_id):
        with self._lock:
            return self._clients.get(client_id)

    def get_all(self):
        with self._lock:
            return list(self._clients.items())

    def count(self):
        with self._lock:
            return len(self._clients)

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

    def get_channel_subscribers(self, channel):
        with self._lock:
            return list(self._channels.get(channel, set()))

    def get_channel_info(self):
        with self._lock:
            return {name: len(subscribers) for name, subscribers in self._channels.items()}

    def get_clients_for_channel(self, channel):
        with self._lock:
            return self._channels.get(channel, set())


registry = ClientRegistry()

if TRANSPORT == "websocket":
    _transport = WebSocketTransport(registry)
else:
    _transport = WebSocketTransport(registry)


def _init_message_db():
    global _message_db_initialized
    if _message_db_initialized:
        return
    conn = sqlite3.connect(DATABASE_URL)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT,
            type TEXT,
            payload TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()
    _message_db_initialized = True


def store_message(channel, msg_type, payload, timestamp):
    _init_message_db()
    conn = sqlite3.connect(DATABASE_URL)
    conn.execute(
        "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
        (channel or "", msg_type, json.dumps(payload), timestamp)
    )
    conn.commit()
    conn.close()


def get_messages(limit=50, offset=0):
    _init_message_db()
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM messages ORDER BY timestamp DESC LIMIT ? OFFSET ?",
        (limit, offset)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


async def check_rate_limit(client_id):
    if redis_client:
        try:
            key = f"rate:{client_id}"
            count = await redis_client.incr(key)
            if count == 1:
                await redis_client.expire(key, 60)
            return count <= RATE_LIMIT
        except Exception:
            pass

    now = time.monotonic()
    with _rate_lock:
        timestamps = _rate_limits.get(client_id, [])
        timestamps = [t for t in timestamps if now - t < 60]
        if len(timestamps) >= RATE_LIMIT:
            _rate_limits[client_id] = timestamps
            return False
        timestamps.append(now)
        _rate_limits[client_id] = timestamps
        return True


def get_history(channel=None, since=None, limit=50):
    _init_message_db()
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row

    query = "SELECT * FROM messages"
    conditions = []
    params = []

    if channel:
        conditions.append("channel = ?")
        params.append(channel)

    if since:
        conditions.append("timestamp > ?")
        params.append(since)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY timestamp ASC LIMIT ?"
    params.append(limit + 1)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    has_more = len(rows) > limit
    messages = [dict(r) for r in rows[:limit]]

    return {"messages": messages, "has_more": has_more}


async def _cleanup_old_messages():
    while True:
        try:
            _cleanup_messages_once()
        except asyncio.CancelledError:
            break
        except Exception:
            pass
        await asyncio.sleep(3600)


def _cleanup_messages_once():
    _init_message_db()
    conn = sqlite3.connect(DATABASE_URL)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=MESSAGE_TTL_DAYS)).isoformat()
    conn.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff,))
    conn.commit()
    conn.close()


def make_message(msg_type, payload):
    return json.dumps({
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


async def broadcast(message):
    await _transport.broadcast(message)


async def broadcast_to_clients(client_ids, message):
    tasks = []
    for cid in client_ids:
        tasks.append(_transport.send_message(cid, message))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def send_direct(recipient_id, message):
    await _transport.send_message(recipient_id, message)


async def init_redis():
    global redis_client, _subscriber_task
    if REDIS_URL:
        import redis.asyncio as aioredis
        redis_client = aioredis.Redis.from_url(REDIS_URL)
        _subscriber_task = asyncio.create_task(_redis_subscriber_task())


async def _redis_subscriber_task():
    while True:
        try:
            async with redis_client.pubsub() as pubsub:
                await pubsub.subscribe(REDIS_CHANNEL)
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        raw = message["data"]
                        if isinstance(raw, bytes):
                            raw = raw.decode()
                        data = json.loads(raw)
                        msg_type = data.get("type", "broadcast")
                        payload = data.get("payload", {})

                        if msg_type == "broadcast":
                            channel = payload.get("channel")
                            if channel:
                                client_ids = registry.get_clients_for_channel(channel)
                                await broadcast_to_clients(client_ids, raw)
                            else:
                                await broadcast(raw)
                        elif msg_type == "direct":
                            recipient = payload.get("recipient")
                            if recipient:
                                await send_direct(recipient, raw)
                            sender_id = payload.get("from")
                            if sender_id:
                                await _transport.send_message(sender_id, raw)
                        elif msg_type == "system":
                            await broadcast(raw)
        except Exception:
            await asyncio.sleep(1)


async def publish_to_redis(message_str):
    if redis_client:
        await redis_client.publish(REDIS_CHANNEL, message_str)


async def handler(websocket):
    client_id = str(uuid.uuid4())
    await _transport.on_connect(client_id, websocket)

    try:
        welcome = make_message("system", {
            "message": f"Connected as {client_id}",
            "client_id": client_id
        })
        await _transport.send_message(client_id, welcome)
    except Exception:
        await _transport.on_disconnect(client_id)
        return

    try:
        async for raw in websocket:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if not await check_rate_limit(client_id):
                err = make_message("system", {
                    "error": f"Rate limit exceeded. Maximum {RATE_LIMIT} messages per minute.",
                    "client_id": client_id
                })
                try:
                    await _transport.send_message(client_id, err)
                except Exception:
                    pass
                continue

            msg_type = data.get("type", "broadcast")
            payload = data.get("payload", {})

            if msg_type == "subscribe":
                channel = payload.get("channel", "")
                if channel:
                    registry.subscribe(client_id, channel)
                    confirm = make_message("system", {
                        "message": f"Subscribed to {channel}",
                        "channel": channel,
                        "client_id": client_id
                    })
                    await _transport.send_message(client_id, confirm)
            elif msg_type == "unsubscribe":
                channel = payload.get("channel", "")
                if channel:
                    registry.unsubscribe(client_id, channel)
                    confirm = make_message("system", {
                        "message": f"Unsubscribed from {channel}",
                        "channel": channel,
                        "client_id": client_id
                    })
                    await _transport.send_message(client_id, confirm)
            elif msg_type == "broadcast":
                payload_for_storage = dict(payload)
                ts = datetime.now(timezone.utc).isoformat()
                store_message(payload.get("channel", ""), "broadcast", payload_for_storage, ts)
                broadcast_msg = make_message("broadcast", payload)
                if REDIS_URL:
                    await publish_to_redis(broadcast_msg)
                else:
                    channel = payload.get("channel")
                    if channel:
                        client_ids = registry.get_clients_for_channel(channel)
                        await broadcast_to_clients(client_ids, broadcast_msg)
                    else:
                        await broadcast(broadcast_msg)
            elif msg_type == "direct":
                recipient = payload.get("recipient")
                if recipient:
                    ts = datetime.now(timezone.utc).isoformat()
                    direct_payload = {
                        "from": client_id,
                        "message": payload.get("message", ""),
                        "recipient": recipient
                    }
                    store_message("", "direct", direct_payload, ts)
                    direct_msg = make_message("direct", direct_payload)
                    if REDIS_URL:
                        await publish_to_redis(direct_msg)
                    else:
                        await send_direct(recipient, direct_msg)
                        await _transport.send_message(client_id, direct_msg)
    except (ConnectionClosedOK, ConnectionClosedError):
        pass
    except Exception:
        pass
    finally:
        await _transport.on_disconnect(client_id)
        leave_msg = make_message("system", {
            "message": f"Client {client_id} disconnected",
            "client_id": client_id
        })
        await broadcast(leave_msg)


def process_request(connection, request):
    if request.path == "/health":
        count = registry.count()
        response = connection.respond(
            200,
            json.dumps({"clients": count, "status": "ok"}),
        )
        response.headers["Content-Type"] = "application/json"
        return response
    if request.path == "/channels":
        info = registry.get_channel_info()
        response = connection.respond(
            200,
            json.dumps(info),
        )
        response.headers["Content-Type"] = "application/json"
        return response
    if request.path.startswith("/channels/") and request.path.endswith("/subscribers"):
        channel = request.path[len("/channels/"):-len("/subscribers")]
        if channel:
            subscribers = registry.get_channel_subscribers(channel)
            response = connection.respond(
                200,
                json.dumps(subscribers),
            )
            response.headers["Content-Type"] = "application/json"
            return response
    if request.path.startswith("/messages"):
        parsed = urlparse(request.path)
        qs = parse_qs(parsed.query)
        limit = int(qs.get("limit", ["50"])[0])
        offset = int(qs.get("offset", ["0"])[0])
        messages = get_messages(limit=limit, offset=offset)
        response = connection.respond(
            200,
            json.dumps(messages),
        )
        response.headers["Content-Type"] = "application/json"
        return response
    if request.path.startswith("/history"):
        parsed = urlparse(request.path)
        qs = parse_qs(parsed.query)
        channel = qs.get("channel", [None])[0]
        since = qs.get("since", [None])[0]
        if since:
            since = since.replace(" ", "+")
        limit = int(qs.get("limit", ["50"])[0])
        result = get_history(channel=channel, since=since, limit=limit)
        response = connection.respond(
            200,
            json.dumps(result),
        )
        response.headers["Content-Type"] = "application/json"
        return response
    return None


async def main():
    await init_redis()
    asyncio.create_task(_cleanup_old_messages())
    async with serve(handler, "localhost", 8765, process_request=process_request):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
