import asyncio
import json
import os
import sqlite3
import threading
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

from aiohttp import web
from websockets.asyncio.server import serve

REDIS_URL = os.environ.get("REDIS_URL", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "messages.db")
MESSAGE_TTL_DAYS = int(os.environ.get("MESSAGE_TTL_DAYS", "7"))
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "100"))

_server_id = str(uuid.uuid4())


class MessageStore:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
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

    def store(self, channel: str | None, msg_type: str, payload: dict, timestamp: str) -> int:
        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(
                    "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                    (channel or "", msg_type, json.dumps(payload), timestamp),
                )
                conn.commit()
                return cursor.lastrowid

    def get_messages(self, limit: int = 50, offset: int = 0) -> list[dict]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            messages = []
            for row in rows:
                msg = dict(row)
                try:
                    msg["payload"] = json.loads(msg["payload"])
                except (json.JSONDecodeError, TypeError):
                    pass
                msg["channel"] = msg["channel"] or None
                messages.append(msg)
            return messages

    def delete_older_than(self, days: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM messages WHERE timestamp < ?",
                    (cutoff,),
                )
                conn.commit()
                return cursor.rowcount

    def get_history(self, channel: str | None = None, since: str | None = None, limit: int = 50) -> dict:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT id, channel, type, payload, timestamp FROM messages WHERE 1=1"
            params: list = []

            if channel is not None:
                query += " AND channel = ?"
                params.append(channel)

            if since is not None:
                query += " AND timestamp >= ?"
                params.append(since)

            query += " ORDER BY id ASC LIMIT ?"
            params.append(limit + 1)

            rows = conn.execute(query, params).fetchall()

            has_more = len(rows) > limit
            if has_more:
                rows = rows[:limit]

            messages = []
            for row in rows:
                msg = dict(row)
                try:
                    msg["payload"] = json.loads(msg["payload"])
                except (json.JSONDecodeError, TypeError):
                    pass
                msg["channel"] = msg["channel"] or None
                messages.append(msg)

            return {"messages": messages, "has_more": has_more, "limit": limit}

    def clear(self) -> None:
        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("DELETE FROM messages")
                conn.commit()


message_store = MessageStore(DATABASE_URL)


class RedisMessageBroker:
    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._redis = None
        self._pubsub = None
        self._listener_task: asyncio.Task | None = None

    @property
    def enabled(self) -> bool:
        return bool(os.environ.get("REDIS_URL", ""))

    async def start(self) -> None:
        self._redis_url = os.environ.get("REDIS_URL", "")
        if not self._redis_url:
            return
        import redis.asyncio as aioredis
        self._redis = aioredis.from_url(self._redis_url)
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe("messages")
        self._listener_task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        if self._pubsub:
            await self._pubsub.unsubscribe("messages")
            await self._pubsub.close()
            self._pubsub = None
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def publish(self, channel: str | None, msg_type: str, payload: dict, timestamp: str) -> None:
        if not self._redis:
            return
        await self._redis.publish("messages", json.dumps({
            "channel": channel or "",
            "type": msg_type,
            "payload": payload,
            "timestamp": timestamp,
        }))

    async def store_client_state(self, client_id: str, connected: bool) -> None:
        if not self._redis:
            return
        key = f"clients:{client_id}"
        if connected:
            await self._redis.hset(key, mapping={
                "server_id": _server_id,
                "connected_at": datetime.now(timezone.utc).isoformat(),
            })
            await self._redis.sadd("connected_clients", client_id)
        else:
            await self._redis.delete(key)
            await self._redis.srem("connected_clients", client_id)

    async def is_rate_limited(self, client_id: str) -> bool:
        if not self._redis:
            return False
        rate_limit = int(os.environ.get("RATE_LIMIT", "100"))
        key = f"ratelimit:{client_id}"
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, 60)
        return count > rate_limit

    async def _listen(self) -> None:
        async for msg in self._pubsub.listen():
            if msg["type"] == "message":
                try:
                    data = json.loads(msg["data"])
                    server_channel = data.get("channel") or None
                    msg_type = data["type"]
                    payload = data.get("payload", {})
                    timestamp = data.get("timestamp", "")

                    outbound = make_message(msg_type, payload, timestamp)
                    if server_channel:
                        subscribers = channel_manager.get_subscribers(server_channel)
                        if subscribers:
                            for cid in subscribers:
                                await registry.send_message(cid, outbound)
                    else:
                        await registry.broadcast(outbound)
                except Exception:
                    pass


redis_broker = RedisMessageBroker(REDIS_URL)


class BaseTransport(ABC):
    @abstractmethod
    async def on_connect(self, connection) -> str:
        ...

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        ...

    @abstractmethod
    async def send_message(self, client_id: str, message: str) -> None:
        ...

    @abstractmethod
    async def broadcast(self, message: str) -> None:
        ...


class WebSocketTransport(BaseTransport):
    def __init__(self):
        self._clients: dict[str, object] = {}
        self._lock = threading.Lock()

    async def on_connect(self, connection) -> str:
        return self.add(connection)

    async def on_disconnect(self, client_id: str) -> None:
        self.remove(client_id)

    async def send_message(self, client_id: str, message: str) -> None:
        ws = self.get_ws(client_id)
        if ws is not None:
            try:
                await ws.send(message)
            except Exception:
                pass

    async def broadcast(self, message: str) -> None:
        for client_id, ws in self.get_all():
            try:
                await ws.send(message)
            except Exception:
                pass

    def add(self, websocket) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = websocket
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def count(self) -> int:
        with self._lock:
            return len(self._clients)

    def get_ws(self, client_id: str) -> object | None:
        with self._lock:
            return self._clients.get(client_id)

    def get_all(self) -> list[tuple[str, object]]:
        with self._lock:
            return list(self._clients.items())


class ClientRegistry:
    def __init__(self):
        self._clients: dict[str, object] = {}
        self._lock = threading.Lock()

    def add(self, websocket) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = websocket
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def count(self) -> int:
        with self._lock:
            return len(self._clients)

    def get_all(self) -> list[tuple[str, object]]:
        with self._lock:
            return list(self._clients.items())

    def get_ws(self, client_id: str) -> object | None:
        with self._lock:
            return self._clients.get(client_id)


class ChannelManager:
    def __init__(self):
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            if channel not in self._channels:
                self._channels[channel] = set()
            self._channels[channel].add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            if channel in self._channels:
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def unsubscribe_all(self, client_id: str) -> None:
        with self._lock:
            for channel in list(self._channels):
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def get_channels(self) -> dict[str, int]:
        with self._lock:
            return {name: len(subscribers) for name, subscribers in self._channels.items()}

    def get_subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return list(self._channels.get(channel, set()))

    def reset(self) -> None:
        with self._lock:
            self._channels.clear()


def _create_transport():
    transport_type = os.environ.get("TRANSPORT", "websocket")
    return WebSocketTransport()


registry = _create_transport()
channel_manager = ChannelManager()


def make_message(msg_type: str, payload: dict, timestamp: str = "") -> str:
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    return json.dumps({
        "type": msg_type,
        "payload": payload,
        "timestamp": ts,
    })


async def deliver_message(channel: str | None, msg_type: str, payload: dict, timestamp: str) -> None:
    outbound = make_message(msg_type, payload, timestamp)
    if channel:
        subscribers = channel_manager.get_subscribers(channel)
        if subscribers:
            for cid in subscribers:
                await registry.send_message(cid, outbound)
    else:
        await registry.broadcast(outbound)


async def ws_handler(websocket):
    client_id = registry.add(websocket)
    if redis_broker.enabled:
        asyncio.create_task(redis_broker.store_client_state(client_id, True))

    welcome = make_message("system", {
        "message": "connected",
        "client_id": client_id,
    })
    await websocket.send(welcome)

    try:
        async for raw in websocket:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "broadcast")

            if msg_type == "subscribe":
                channel = data.get("channel", "")
                if channel:
                    channel_manager.subscribe(client_id, channel)
                    ack = make_message("subscribe", {
                        "channel": channel,
                        "client_id": client_id,
                        "status": "subscribed",
                    })
                    await websocket.send(ack)
            elif msg_type == "unsubscribe":
                channel = data.get("channel", "")
                if channel:
                    channel_manager.unsubscribe(client_id, channel)
                    ack = make_message("unsubscribe", {
                        "channel": channel,
                        "client_id": client_id,
                        "status": "unsubscribed",
                    })
                    await websocket.send(ack)
            else:
                if await redis_broker.is_rate_limited(client_id):
                    error = make_message("error", {
                        "message": "Rate limit exceeded",
                        "max_per_minute": int(os.environ.get("RATE_LIMIT", "100")),
                    })
                    await websocket.send(error)
                    continue

                payload = data.get("payload", {})
                channel = data.get("channel")
                timestamp = datetime.now(timezone.utc).isoformat()

                message_store.store(channel, msg_type, payload, timestamp)

                if redis_broker.enabled:
                    await redis_broker.publish(channel, msg_type, payload, timestamp)
                else:
                    await deliver_message(channel, msg_type, payload, timestamp)
    finally:
        registry.remove(client_id)
        channel_manager.unsubscribe_all(client_id)
        if redis_broker.enabled:
            asyncio.create_task(redis_broker.store_client_state(client_id, False))


async def health(request):
    return web.json_response({"clients": registry.count()})


async def channels_list(request):
    return web.json_response(channel_manager.get_channels())


async def channel_subscribers(request):
    name = request.match_info.get("name", "")
    subscribers = channel_manager.get_subscribers(name)
    return web.json_response({"channel": name, "subscribers": subscribers})


async def messages_list(request):
    limit = int(request.query.get("limit", "50"))
    offset = int(request.query.get("offset", "0"))
    messages = message_store.get_messages(limit, offset)
    return web.json_response({"messages": messages, "limit": limit, "offset": offset})


async def history_handler(request):
    channel = request.query.get("channel")
    since = request.query.get("since")
    limit = int(request.query.get("limit", "50"))
    result = message_store.get_history(channel=channel, since=since, limit=limit)
    return web.json_response(result)


async def cleanup_expired_messages():
    ttl_days = int(os.environ.get("MESSAGE_TTL_DAYS", "7"))
    await asyncio.to_thread(message_store.delete_older_than, ttl_days)


async def main():
    await redis_broker.start()

    asyncio.create_task(cleanup_expired_messages())

    ws_server = await serve(
        ws_handler,
        "127.0.0.1",
        8765,
    )

    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/channels", channels_list)
    app.router.add_get("/channels/{name}/subscribers", channel_subscribers)
    app.router.add_get("/messages", messages_list)
    app.router.add_get("/history", history_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8766)
    await site.start()

    try:
        await asyncio.Future()
    finally:
        ws_server.close()
        await ws_server.wait_closed()
        await runner.cleanup()
        await redis_broker.stop()


if __name__ == "__main__":
    asyncio.run(main())
