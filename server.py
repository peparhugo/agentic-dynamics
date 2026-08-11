import asyncio
import json
import os
import sqlite3
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from urllib.parse import parse_qs

from websockets.asyncio.server import serve as serve_ws
from websockets.exceptions import ConnectionClosed

try:
    import redis.asyncio as aioredis

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
DATABASE_URL = os.environ.get("DATABASE_URL", "messages.db")


class MessageStore:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS messages ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  channel TEXT,"
                "  type TEXT NOT NULL,"
                "  payload TEXT NOT NULL,"
                "  timestamp TEXT NOT NULL"
                ")"
            )

    def save(self, channel, msg_type, payload, timestamp):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (channel or "", msg_type, json.dumps(payload), timestamp),
            )
            conn.commit()

    def get_messages(self, limit=50, offset=0):
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return [
                {
                    "id": r["id"],
                    "channel": r["channel"],
                    "type": r["type"],
                    "payload": json.loads(r["payload"]),
                    "timestamp": r["timestamp"],
                }
                for r in rows
            ]


class ClientRegistry:
    def __init__(self):
        self._clients = {}
        self._subscriptions = {}
        self._client_channels = {}
        self._lock = threading.Lock()

    def add(self, client_id, websocket):
        with self._lock:
            self._clients[client_id] = websocket

    def remove(self, client_id):
        with self._lock:
            self._clients.pop(client_id, None)
            if client_id in self._client_channels:
                for channel in list(self._client_channels[client_id]):
                    if channel in self._subscriptions:
                        self._subscriptions[channel].discard(client_id)
                        if not self._subscriptions[channel]:
                            del self._subscriptions[channel]
                del self._client_channels[client_id]

    def count(self):
        with self._lock:
            return len(self._clients)

    def get_all(self):
        with self._lock:
            return dict(self._clients)

    def clear(self):
        with self._lock:
            self._clients.clear()
            self._subscriptions.clear()
            self._client_channels.clear()

    def subscribe(self, client_id, channel):
        with self._lock:
            if channel not in self._subscriptions:
                self._subscriptions[channel] = set()
            self._subscriptions[channel].add(client_id)
            if client_id not in self._client_channels:
                self._client_channels[client_id] = set()
            self._client_channels[client_id].add(channel)

    def unsubscribe(self, client_id, channel):
        with self._lock:
            if channel in self._subscriptions:
                self._subscriptions[channel].discard(client_id)
                if not self._subscriptions[channel]:
                    del self._subscriptions[channel]
            if client_id in self._client_channels:
                self._client_channels[client_id].discard(channel)
                if not self._client_channels[client_id]:
                    del self._client_channels[client_id]

    def get_subscribers(self, channel):
        with self._lock:
            if channel in self._subscriptions:
                return list(self._subscriptions[channel])
            return []

    def get_channels(self):
        with self._lock:
            return {name: len(subscribers) for name, subscribers in self._subscriptions.items()}

    def get_subscriber_websockets(self, channel):
        with self._lock:
            if channel not in self._subscriptions:
                return {}
            result = {}
            for cid in self._subscriptions[channel]:
                if cid in self._clients:
                    result[cid] = self._clients[cid]
            return result

    def get_client_channels(self, client_id):
        with self._lock:
            if client_id in self._client_channels:
                return list(self._client_channels[client_id])
            return []


class NotificationServer:
    def __init__(self, host="localhost", port=8765, redis_url=None, database_url=None):
        self.host = host
        self.port = port
        self.registry = ClientRegistry()
        self._redis_url = redis_url if redis_url is not None else REDIS_URL
        self._database_url = database_url if database_url is not None else DATABASE_URL
        self.message_store = MessageStore(self._database_url)
        self._redis = None
        self._redis_available = False
        self._redis_sub_task = None

    async def _connect_redis(self):
        if not self._redis_url or not HAS_REDIS:
            self._redis_available = False
            return
        try:
            self._redis = aioredis.from_url(self._redis_url)
            await self._redis.ping()
            self._redis_available = True
        except Exception:
            self._redis = None
            self._redis_available = False

    async def _redis_subscriber(self):
        while self._redis_available and self._redis:
            try:
                pubsub = self._redis.pubsub()
                await pubsub.subscribe("notifications")
                async for message in pubsub.listen():
                    if message and message.get("type") == "message":
                        try:
                            data = json.loads(message["data"])
                            await self._deliver_locally(data)
                        except Exception:
                            pass
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1)
            finally:
                try:
                    await pubsub.close()
                except Exception:
                    pass

    async def _deliver_locally(self, message):
        channel = message.get("channel")
        if channel:
            clients = self.registry.get_subscriber_websockets(channel)
        else:
            clients = self.registry.get_all()
        message_str = json.dumps(message)
        disconnected = []
        for cid, ws in clients.items():
            try:
                await ws.send(message_str)
            except ConnectionClosed:
                disconnected.append(cid)
        for cid in disconnected:
            self.registry.remove(cid)

    async def _handler(self, websocket):
        client_id = str(uuid.uuid4())
        self.registry.add(client_id, websocket)
        try:
            welcome = {
                "type": "system",
                "payload": {"client_id": client_id, "message": "Connected"},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await websocket.send(json.dumps(welcome))

            async for message in websocket:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type", "broadcast")
                payload = data.get("payload", {})

                if msg_type == "broadcast":
                    timestamp = datetime.now(timezone.utc).isoformat()
                    notification = {
                        "type": "broadcast",
                        "payload": payload,
                        "timestamp": timestamp,
                        "sender": client_id,
                    }
                    channel = data.get("channel")
                    if channel:
                        notification["channel"] = channel

                    self.message_store.save(
                        channel=channel or "",
                        msg_type="broadcast",
                        payload=payload,
                        timestamp=timestamp,
                    )

                    if self._redis_available and self._redis:
                        await self._redis.publish("notifications", json.dumps(notification))
                    else:
                        await self._deliver_locally(notification)
                elif msg_type == "direct":
                    target = data.get("target")
                    if target:
                        timestamp = datetime.now(timezone.utc).isoformat()
                        notification = {
                            "type": "direct",
                            "payload": payload,
                            "timestamp": timestamp,
                            "sender": client_id,
                        }
                        self.message_store.save(
                            channel="",
                            msg_type="direct",
                            payload=payload,
                            timestamp=timestamp,
                        )
                        await self._send_direct(target, notification)
                elif msg_type == "subscribe":
                    channel = data.get("channel")
                    if channel:
                        self.registry.subscribe(client_id, channel)
                        if self._redis_available and self._redis:
                            await self._redis.sadd(f"sub:{channel}", client_id)
                elif msg_type == "unsubscribe":
                    channel = data.get("channel")
                    if channel:
                        self.registry.unsubscribe(client_id, channel)
                        if self._redis_available and self._redis:
                            await self._redis.srem(f"sub:{channel}", client_id)
        finally:
            channels = self.registry.get_client_channels(client_id)
            self.registry.remove(client_id)
            if self._redis_available and self._redis:
                for channel in channels:
                    await self._redis.srem(f"sub:{channel}", client_id)

    async def _send_direct(self, target_id, message):
        clients = self.registry.get_all()
        ws = clients.get(target_id)
        if ws is not None:
            try:
                await ws.send(json.dumps(message))
            except ConnectionClosed:
                self.registry.remove(target_id)

    def _process_request(self, connection, request):
        path = request.path
        query = {}
        if "?" in path:
            path, qs = path.split("?", 1)
            query = parse_qs(qs)

        if path == "/health":
            count = self.registry.count()
            response = connection.respond(200, json.dumps({"clients": count}))
            response.headers["Content-Type"] = "application/json"
            return response
        if path == "/channels":
            channels = self.registry.get_channels()
            response = connection.respond(200, json.dumps({"channels": channels}))
            response.headers["Content-Type"] = "application/json"
            return response
        if path.startswith("/channels/") and path.endswith("/subscribers"):
            channel_name = path[len("/channels/"):-len("/subscribers")]
            subscribers = self.registry.get_subscribers(channel_name)
            response = connection.respond(200, json.dumps({
                "channel": channel_name,
                "subscribers": subscribers,
            }))
            response.headers["Content-Type"] = "application/json"
            return response
        if path == "/messages":
            limit = int(query.get("limit", ["50"])[0])
            offset = int(query.get("offset", ["0"])[0])
            messages = self.message_store.get_messages(limit=limit, offset=offset)
            response = connection.respond(200, json.dumps({"messages": messages}))
            response.headers["Content-Type"] = "application/json"
            return response
        return None

    @asynccontextmanager
    async def run(self):
        await self._connect_redis()
        if self._redis_available:
            self._redis_sub_task = asyncio.create_task(self._redis_subscriber())
        try:
            async with serve_ws(
                self._handler,
                self.host,
                self.port,
                process_request=self._process_request,
            ) as ws_server:
                yield ws_server
        finally:
            if self._redis_sub_task:
                self._redis_sub_task.cancel()
                try:
                    await self._redis_sub_task
                except (asyncio.CancelledError, Exception):
                    pass
                self._redis_sub_task = None
            if self._redis:
                await self._redis.close()
                self._redis = None


async def main():
    server = NotificationServer()
    async with server.run():
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
