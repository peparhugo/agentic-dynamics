import abc
import asyncio
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import websockets
from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.http11 import Response


class MessageStore:
    def __init__(self, db_path):
        self._lock = threading.Lock()
        self._db_path = db_path
        self._init()

    def _init(self):
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
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

    def save(self, msg_id, channel, msg_type, payload, timestamp):
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT OR REPLACE INTO messages VALUES (?, ?, ?, ?, ?)",
                (msg_id, channel or "", msg_type, json.dumps(payload), timestamp),
            )
            conn.commit()
            conn.close()

    def query(self, limit=50, offset=0):
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.execute(
                "SELECT id, channel, type, payload, timestamp "
                "FROM messages ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = cursor.fetchall()
            conn.close()
            return [
                {
                    "id": r[0],
                    "channel": r[1] or None,
                    "type": r[2],
                    "payload": json.loads(r[3]),
                    "timestamp": r[4],
                }
                for r in rows
            ]


_store_instance = None


def _get_store():
    global _store_instance
    if _store_instance is None:
        raw = os.environ.get("DATABASE_URL", "sqlite:///messages.db")
        db_path = raw
        if db_path.startswith("sqlite:///"):
            db_path = db_path[len("sqlite:///"):]
        _store_instance = MessageStore(db_path)
    return _store_instance


def _reset_store():
    global _store_instance
    _store_instance = None


class ClientRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._clients: dict[str, websockets.ServerConnection] = {}
        self._channels: dict[str, set[str]] = {}

    def register(self, client_id: str, websocket: websockets.ServerConnection):
        with self._lock:
            self._clients[client_id] = websocket

    def unregister(self, client_id: str):
        with self._lock:
            self._clients.pop(client_id, None)

    def get_all(self):
        with self._lock:
            return list(self._clients.items())

    @property
    def count(self):
        with self._lock:
            return len(self._clients)

    def subscribe(self, client_id: str, channel: str):
        with self._lock:
            if channel not in self._channels:
                self._channels[channel] = set()
            self._channels[channel].add(client_id)

    def unsubscribe(self, client_id: str, channel: str):
        with self._lock:
            if channel in self._channels:
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def unsubscribe_all(self, client_id: str):
        with self._lock:
            for channel in list(self._channels):
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def get_channel_subscribers(self, channel: str):
        with self._lock:
            if channel not in self._channels:
                return []
            result = []
            for cid in list(self._channels[channel]):
                if cid in self._clients:
                    result.append((cid, self._clients[cid]))
                else:
                    self._channels[channel].discard(cid)
            if channel in self._channels and not self._channels[channel]:
                del self._channels[channel]
            return result

    def get_channels(self):
        with self._lock:
            return {name: len(subs) for name, subs in self._channels.items()}

    def get_channel_subscriber_ids(self, channel: str):
        with self._lock:
            if channel not in self._channels:
                return []
            return list(self._channels[channel])


registry = ClientRegistry()
_server_id = str(uuid.uuid4())
_redis = None


def _set_redis(r):
    global _redis
    _redis = r


async def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    url = os.environ.get("REDIS_URL")
    if not url:
        return None
    try:
        import redis.asyncio as aioredis
    except ImportError:
        return None
    try:
        r = aioredis.Redis.from_url(url, socket_connect_timeout=2)
        await r.ping()
        _redis = r
        return r
    except Exception:
        return None


async def _redis_subscriber():
    redis_conn = await _get_redis()
    if redis_conn is None:
        return
    try:
        async with redis_conn.pubsub() as pubsub:
            await pubsub.psubscribe("channel:*", "broadcast:*")
            async for msg in pubsub.listen():
                if msg["type"] not in ("pmessage",):
                    continue
                try:
                    data = json.loads(msg["data"])
                except json.JSONDecodeError:
                    continue
                if data.get("_server_id") == _server_id:
                    continue
                await _deliver_from_redis(data)
    except Exception:
        pass


class BaseTransport(abc.ABC):
    @abc.abstractmethod
    async def on_connect(self, client_id, connection):
        pass

    @abc.abstractmethod
    async def on_disconnect(self, client_id):
        pass

    @abc.abstractmethod
    async def send_message(self, connection, message):
        pass

    @abc.abstractmethod
    async def broadcast(self, targets, message):
        pass


class WebSocketTransport(BaseTransport):
    async def on_connect(self, client_id, connection):
        pass

    async def on_disconnect(self, client_id):
        pass

    async def send_message(self, connection, message):
        try:
            await connection.send(message)
        except websockets.exceptions.ConnectionClosedOK:
            pass
        except websockets.exceptions.ConnectionClosedError:
            pass

    async def broadcast(self, targets, message):
        for client_id, ws in targets:
            try:
                await ws.send(message)
            except websockets.exceptions.ConnectionClosedOK:
                registry.unregister(client_id)
            except websockets.exceptions.ConnectionClosedError:
                registry.unregister(client_id)


_transport = None


def _get_transport():
    global _transport
    if _transport is None:
        transport_type = os.environ.get("TRANSPORT", "websocket")
        if transport_type == "websocket":
            _transport = WebSocketTransport()
        else:
            raise ValueError(f"Unknown transport: {transport_type}")
    return _transport


def _reset_transport():
    global _transport
    _transport = None


async def _deliver_from_redis(data):
    transport = _get_transport()
    channel = data.get("channel")
    payload = data.get("payload", {})
    msg_type = data.get("type", "broadcast")
    timestamp = data.get("timestamp", datetime.now(timezone.utc).isoformat())

    message_dict = {
        "type": msg_type,
        "payload": payload,
        "timestamp": timestamp,
    }
    if channel:
        message_dict["channel"] = channel

    message = json.dumps(message_dict)

    if channel:
        targets = registry.get_channel_subscribers(channel)
    else:
        targets = registry.get_all()

    await transport.broadcast(targets, message)


async def _publish_to_redis(channel, message_dict):
    redis_conn = await _get_redis()
    if redis_conn is None:
        return
    try:
        redis_channel = f"channel:{channel}" if channel else "broadcast:all"
        pub_data = dict(message_dict)
        pub_data["_server_id"] = _server_id
        await redis_conn.publish(redis_channel, json.dumps(pub_data))
    except Exception:
        pass


async def _handle_broadcast(data, transport):
    channel = data.get("channel")
    payload = data.get("payload", {})
    timestamp = datetime.now(timezone.utc).isoformat()

    message_dict = {
        "type": "broadcast",
        "payload": payload,
        "timestamp": timestamp,
    }
    if channel:
        message_dict["channel"] = channel

    message = json.dumps(message_dict)

    if channel:
        targets = registry.get_channel_subscribers(channel)
    else:
        targets = registry.get_all()

    await transport.broadcast(targets, message)

    msg_id = str(uuid.uuid4())
    _get_store().save(msg_id, channel or "", "broadcast", payload, timestamp)

    await _publish_to_redis(channel, message_dict)


async def _handle_direct(data, transport):
    target_id = data.get("payload", {}).get("target_id")
    if not target_id:
        return
    payload = data.get("payload", {})
    timestamp = datetime.now(timezone.utc).isoformat()

    message = json.dumps({
        "type": "direct",
        "payload": payload,
        "timestamp": timestamp,
    })
    for client_id, ws in registry.get_all():
        if client_id == target_id:
            await transport.send_message(ws, message)
            break

    msg_id = str(uuid.uuid4())
    _get_store().save(msg_id, "", "direct", payload, timestamp)


async def _handle_system(data, connection, transport):
    message = json.dumps({
        "type": "system",
        "payload": data.get("payload", {}),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    await transport.send_message(connection, message)


async def _handle_subscribe(data, client_id, connection, transport):
    channel = data.get("channel")
    if not channel:
        return
    registry.subscribe(client_id, channel)
    message = json.dumps({
        "type": "system",
        "payload": {"event": "subscribed", "channel": channel},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    await transport.send_message(connection, message)


async def _handle_unsubscribe(data, client_id, connection, transport):
    channel = data.get("channel")
    if not channel:
        return
    registry.unsubscribe(client_id, channel)
    message = json.dumps({
        "type": "system",
        "payload": {"event": "unsubscribed", "channel": channel},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    await transport.send_message(connection, message)


async def handler(websocket):
    transport = _get_transport()
    client_id = str(uuid.uuid4())
    registry.register(client_id, websocket)
    await transport.on_connect(client_id, websocket)

    redis_conn = await _get_redis()
    if redis_conn:
        try:
            await redis_conn.sadd(f"clients:{_server_id}", client_id)
        except Exception:
            pass

    try:
        welcome = json.dumps({
            "type": "system",
            "payload": {"client_id": client_id, "event": "connected"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        await transport.send_message(websocket, welcome)

        async for raw_message in websocket:
            try:
                data = json.loads(raw_message)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "broadcast")

            if msg_type == "broadcast":
                await _handle_broadcast(data, transport)
            elif msg_type == "direct":
                await _handle_direct(data, transport)
            elif msg_type == "system":
                await _handle_system(data, websocket, transport)
            elif msg_type == "subscribe":
                await _handle_subscribe(data, client_id, websocket, transport)
            elif msg_type == "unsubscribe":
                await _handle_unsubscribe(data, client_id, websocket, transport)
    finally:
        registry.unsubscribe_all(client_id)
        registry.unregister(client_id)
        await transport.on_disconnect(client_id)

        if redis_conn:
            try:
                await redis_conn.srem(f"clients:{_server_id}", client_id)
            except Exception:
                pass


async def process_request(connection, request):
    parsed = urlparse(request.path)
    path = parsed.path
    qs = parse_qs(parsed.query)

    if path == "/health":
        count = registry.count
        body = json.dumps({"clients_connected": count}).encode()
        return Response(
            200, "OK", Headers({"Content-Type": "application/json"}), body
        )

    if path == "/channels":
        channels = registry.get_channels()
        body = json.dumps(channels).encode()
        return Response(
            200, "OK", Headers({"Content-Type": "application/json"}), body
        )

    if path.startswith("/channels/") and path.endswith("/subscribers"):
        channel_name = path[len("/channels/"):-len("/subscribers")]
        ids = registry.get_channel_subscriber_ids(channel_name)
        body = json.dumps({"channel": channel_name, "subscribers": ids}).encode()
        return Response(
            200, "OK", Headers({"Content-Type": "application/json"}), body
        )

    if path == "/messages":
        try:
            limit = int(qs.get("limit", ["50"])[0])
        except (ValueError, IndexError):
            limit = 50
        try:
            offset = int(qs.get("offset", ["0"])[0])
        except (ValueError, IndexError):
            offset = 0
        msgs = _get_store().query(limit=limit, offset=offset)
        body = json.dumps(msgs).encode()
        return Response(
            200, "OK", Headers({"Content-Type": "application/json"}), body
        )


async def main(host="127.0.0.1", port=8765):
    redis_task = asyncio.create_task(_redis_subscriber())
    try:
        async with serve(handler, host, port, process_request=process_request):
            await asyncio.Future()
    finally:
        redis_task.cancel()
        try:
            await redis_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
