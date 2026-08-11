import asyncio
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import aiosqlite
import redis.asyncio as aioredis
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Headers, Response

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
DATABASE_URL = os.environ.get("DATABASE_URL", "messages.db")

_redis: aioredis.Redis | None = None
_db: aiosqlite.Connection | None = None
_listener_task: asyncio.Task | None = None


class ClientRegistry:
    def __init__(self):
        self._clients = {}
        self._channels = {}
        self._client_channels = {}
        self._lock = threading.Lock()

    def add(self, websocket):
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = websocket
        return client_id

    def remove(self, client_id):
        with self._lock:
            self._clients.pop(client_id, None)
            channels = self._client_channels.pop(client_id, set())
            for ch in channels:
                if ch in self._channels:
                    self._channels[ch].discard(client_id)
                    if not self._channels[ch]:
                        del self._channels[ch]

    def subscribe(self, client_id, channel):
        with self._lock:
            if channel not in self._channels:
                self._channels[channel] = set()
            self._channels[channel].add(client_id)
            if client_id not in self._client_channels:
                self._client_channels[client_id] = set()
            self._client_channels[client_id].add(channel)

    def unsubscribe(self, client_id, channel):
        with self._lock:
            if channel in self._channels:
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]
            if client_id in self._client_channels:
                self._client_channels[client_id].discard(channel)
                if not self._client_channels[client_id]:
                    del self._client_channels[client_id]

    @property
    def count(self):
        with self._lock:
            return len(self._clients)

    def get_all(self):
        with self._lock:
            return dict(self._clients)

    def get_subscribers(self, channel):
        with self._lock:
            return set(self._channels.get(channel, set()))

    def get_channels(self):
        with self._lock:
            return {name: len(subs) for name, subs in self._channels.items()}


registry = ClientRegistry()


def _make_timestamp():
    return datetime.now(timezone.utc).isoformat()


async def _init_redis():
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis


async def _init_db():
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DATABASE_URL)
        await _db.execute(
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
        await _db.commit()
    return _db


async def _save_message(channel, msg_type, payload, timestamp):
    db = await _init_db()
    payload_str = json.dumps(payload)
    await db.execute(
        "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
        (channel or "", msg_type, payload_str, timestamp),
    )
    await db.commit()


async def _redis_publish(channel, message):
    r = await _init_redis()
    await r.publish(channel, json.dumps(message))


async def _local_broadcast(message):
    message_str = json.dumps(message)
    clients = registry.get_all()
    tasks = []
    for ws in clients.values():
        tasks.append(asyncio.create_task(ws.send(message_str)))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def _local_broadcast_to_channel(message, subscribers, clients):
    message_str = json.dumps(message)
    tasks = []
    for cid in subscribers:
        ws = clients.get(cid)
        if ws is not None:
            tasks.append(asyncio.create_task(ws.send(message_str)))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def _local_direct(target_id, message, clients):
    ws = clients.get(target_id)
    if ws is None:
        return
    try:
        await ws.send(json.dumps(message))
    except Exception:
        pass


async def _redis_listener():
    r = await _init_redis()
    async with r.pubsub() as pubsub:
        await pubsub.subscribe("ws:broadcast:all")
        await pubsub.psubscribe("ws:broadcast:*", "ws:direct:*")

        async for msg in pubsub.listen():
            if msg["type"] not in ("message", "pmessage"):
                continue

            channel = (
                msg["channel"].decode()
                if isinstance(msg["channel"], bytes)
                else msg["channel"]
            )
            data_str = (
                msg["data"].decode()
                if isinstance(msg["data"], bytes)
                else msg["data"]
            )

            try:
                message = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            if msg["type"] == "message":
                if channel == "ws:broadcast:all":
                    await _local_broadcast(message)
            elif msg["type"] == "pmessage":
                if channel == "ws:broadcast:*":
                    continue
                if channel.startswith("ws:broadcast:"):
                    ch_name = channel[len("ws:broadcast:"):]
                    subscribers = registry.get_subscribers(ch_name)
                    clients = registry.get_all()
                    await _local_broadcast_to_channel(message, subscribers, clients)
                elif channel.startswith("ws:direct:"):
                    target_id = channel[len("ws:direct:"):]
                    clients = registry.get_all()
                    await _local_direct(target_id, message, clients)


async def _start_background():
    global _listener_task
    await _init_redis()
    await _init_db()
    if _listener_task is None:
        _listener_task = asyncio.create_task(_redis_listener())


async def _stop_background():
    global _listener_task, _redis, _db
    if _listener_task is not None:
        _listener_task.cancel()
        try:
            await _listener_task
        except asyncio.CancelledError:
            pass
        _listener_task = None
    if _redis is not None:
        await _redis.close()
        _redis = None
    if _db is not None:
        await _db.close()
        _db = None


async def _broadcast(message):
    await _redis_publish("ws:broadcast:all", message)
    await _save_message(
        None, message.get("type"), message.get("payload"), message.get("timestamp")
    )


async def _broadcast_to_channel(channel, message):
    await _redis_publish(f"ws:broadcast:{channel}", message)
    await _save_message(
        channel, message.get("type"), message.get("payload"), message.get("timestamp")
    )


async def _send_direct(target_id, message):
    await _redis_publish(f"ws:direct:{target_id}", message)
    await _save_message(
        None, message.get("type"), message.get("payload"), message.get("timestamp")
    )


async def handler(websocket):
    client_id = registry.add(websocket)
    try:
        welcome = {
            "type": "system",
            "payload": {"client_id": client_id, "message": "connected"},
            "timestamp": _make_timestamp(),
        }
        await websocket.send(json.dumps(welcome))

        async for raw in websocket:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "broadcast")
            payload = data.get("payload", {})
            timestamp = _make_timestamp()

            if msg_type == "subscribe":
                channel = data.get("channel")
                if channel:
                    registry.subscribe(client_id, channel)
                    await websocket.send(
                        json.dumps(
                            {
                                "type": "system",
                                "payload": {
                                    "message": f"subscribed to {channel}",
                                    "channel": channel,
                                },
                                "timestamp": timestamp,
                            }
                        )
                    )
            elif msg_type == "unsubscribe":
                channel = data.get("channel")
                if channel:
                    registry.unsubscribe(client_id, channel)
                    await websocket.send(
                        json.dumps(
                            {
                                "type": "system",
                                "payload": {
                                    "message": f"unsubscribed from {channel}",
                                    "channel": channel,
                                },
                                "timestamp": timestamp,
                            }
                        )
                    )
            elif msg_type == "direct":
                target = payload.get("target")
                if target is not None:
                    await _send_direct(
                        target,
                        {
                            "type": "direct",
                            "payload": {
                                "from": client_id,
                                "message": payload.get("message", {}),
                            },
                            "timestamp": timestamp,
                        },
                    )
            else:
                channel = data.get("channel")
                message = {
                    "type": msg_type,
                    "payload": {"from": client_id, **payload},
                    "timestamp": timestamp,
                }
                if channel:
                    await _broadcast_to_channel(channel, message)
                else:
                    await _broadcast(message)
    except ConnectionClosed:
        pass
    finally:
        registry.remove(client_id)
        await _broadcast(
            {
                "type": "system",
                "payload": {"client_id": client_id, "message": "disconnected"},
                "timestamp": _make_timestamp(),
            }
        )


async def process_request(connection, request):
    if request.path == "/health":
        body = json.dumps({"connected_clients": registry.count}).encode()
        headers = Headers({"Content-Type": "application/json"})
        return Response(200, "OK", headers, body)

    if request.path == "/channels":
        body = json.dumps(registry.get_channels()).encode()
        headers = Headers({"Content-Type": "application/json"})
        return Response(200, "OK", headers, body)

    if request.path.startswith("/messages"):
        limit = 50
        offset = 0
        parsed = urlparse(request.path)
        if parsed.query:
            params = parse_qs(parsed.query)
            if "limit" in params:
                limit = int(params["limit"][0])
            if "offset" in params:
                offset = int(params["offset"][0])

        db = await _init_db()
        rows = await db.execute_fetchall(
            "SELECT id, channel, type, payload, timestamp FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        messages = [
            {
                "id": row[0],
                "channel": row[1],
                "type": row[2],
                "payload": json.loads(row[3]),
                "timestamp": row[4],
            }
            for row in rows
        ]
        body = json.dumps(messages).encode()
        headers = Headers({"Content-Type": "application/json"})
        return Response(200, "OK", headers, body)

    if request.path.startswith("/channels/"):
        parts = request.path.split("/")
        if len(parts) >= 4 and parts[3] == "subscribers":
            channel_name = parts[2]
            subscribers = registry.get_subscribers(channel_name)
            body = json.dumps(
                {"channel": channel_name, "subscribers": list(subscribers)}
            ).encode()
            headers = Headers({"Content-Type": "application/json"})
            return Response(200, "OK", headers, body)

    return None


async def start_server(host="0.0.0.0", port=8765):
    await _start_background()
    try:
        async with serve(
            handler,
            host,
            port,
            process_request=process_request,
        ) as server:
            await server.serve_forever()
    finally:
        await _stop_background()


if __name__ == "__main__":
    asyncio.run(start_server())
