import abc
import asyncio
import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
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
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "100"))
MESSAGE_TTL_DAYS = int(os.environ.get("MESSAGE_TTL_DAYS", "7"))


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

    def get_history(self, channel=None, since=None, limit=50):
        with self._get_conn() as conn:
            conditions = []
            params = []

            if channel:
                conditions.append("channel = ?")
                params.append(channel)

            if since:
                conditions.append("timestamp >= ?")
                params.append(since)

            where = ""
            if conditions:
                where = " WHERE " + " AND ".join(conditions)

            params.append(limit + 1)
            rows = conn.execute(
                f"SELECT * FROM messages{where} ORDER BY timestamp ASC, id ASC LIMIT ?",
                params,
            ).fetchall()

            has_more = len(rows) > limit
            if has_more:
                rows = rows[:limit]

            messages = [
                {
                    "id": r["id"],
                    "channel": r["channel"],
                    "type": r["type"],
                    "payload": json.loads(r["payload"]),
                    "timestamp": r["timestamp"],
                }
                for r in rows
            ]

            return {"messages": messages, "has_more": has_more}

    def cleanup_old(self, ttl_days):
        with self._get_conn() as conn:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=ttl_days)).isoformat()
            conn.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff,))
            conn.commit()


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


class RateLimiter:
    def __init__(self, limit=None):
        self._limit = limit if limit is not None else RATE_LIMIT
        self._redis = None
        self._local = {}
        self._lock = threading.Lock()

    def set_redis(self, redis_client):
        self._redis = redis_client

    async def check_and_increment(self, client_id):
        minute = int(time.time() / 60)
        key = f"rate:{client_id}:{minute}"

        if self._redis:
            try:
                count = await self._redis.incr(key)
                if count == 1:
                    await self._redis.expire(key, 120)
                return count <= self._limit, count
            except Exception:
                pass

        with self._lock:
            self._local[key] = self._local.get(key, 0) + 1
            count = self._local[key]
            return count <= self._limit, count


class BaseTransport(abc.ABC):
    @abc.abstractmethod
    def on_connect(self, handler):
        """Register an async handler called with (connection) for each new client."""

    @abc.abstractmethod
    def on_disconnect(self, handler):
        """Register an async handler called with (connection) on client disconnect."""

    @abc.abstractmethod
    async def send_message(self, connection, message):
        """Send a text message to a connection."""

    @abc.abstractmethod
    async def broadcast(self, connections, message):
        """Send a text message to a collection of connections."""

    @property
    @abc.abstractmethod
    def port(self):
        """The port the transport is listening on."""

    @abc.abstractmethod
    async def start(self):
        """Start the transport server."""

    @abc.abstractmethod
    async def stop(self):
        """Stop the transport server."""


class WebSocketTransport(BaseTransport):
    def __init__(self, host="localhost", port=8765, process_request=None):
        self._host = host
        self._port = port
        self._process_request = process_request
        self._server = None
        self._on_connect_cb = None
        self._on_disconnect_cb = None

    def on_connect(self, handler):
        self._on_connect_cb = handler

    def on_disconnect(self, handler):
        self._on_disconnect_cb = handler

    async def send_message(self, connection, message):
        await connection.send(message)

    async def broadcast(self, connections, message):
        conns = connections.values() if isinstance(connections, dict) else connections
        for conn in conns:
            try:
                await conn.send(message)
            except ConnectionClosed:
                pass

    @property
    def port(self):
        if self._server is not None and self._server.sockets:
            return self._server.sockets[0].getsockname()[1]
        return self._port

    async def start(self):
        on_connect_cb = self._on_connect_cb
        on_disconnect_cb = self._on_disconnect_cb

        async def connection_handler(connection):
            try:
                await on_connect_cb(connection)
            finally:
                if on_disconnect_cb is not None:
                    await on_disconnect_cb(connection)

        self._server_ctx = serve_ws(
            connection_handler,
            self._host,
            self._port,
            process_request=self._process_request,
        )
        self._server = await self._server_ctx.__aenter__()

    async def stop(self):
        if self._server_ctx is not None:
            await self._server_ctx.__aexit__(None, None, None)
            self._server_ctx = None
            self._server = None


class NotificationServer:
    def __init__(self, host="localhost", port=8765, redis_url=None, database_url=None, transport=None, rate_limit=None):
        self.host = host
        self.port = port
        self.registry = ClientRegistry()
        self._redis_url = redis_url if redis_url is not None else REDIS_URL
        self._database_url = database_url if database_url is not None else DATABASE_URL
        self.message_store = MessageStore(self._database_url)
        self._redis = None
        self._redis_available = False
        self._redis_sub_task = None
        self._cleanup_task = None
        self.rate_limiter = RateLimiter(limit=rate_limit)

        if transport is not None:
            self._transport = transport
        else:
            transport_type = os.environ.get("TRANSPORT", "websocket")
            if transport_type == "websocket":
                self._transport = WebSocketTransport(host, port, process_request=self._process_request)
            else:
                raise ValueError(f"Unknown transport type: {transport_type}")

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
                await self._transport.send_message(ws, message_str)
            except ConnectionClosed:
                disconnected.append(cid)
        for cid in disconnected:
            self.registry.remove(cid)

    async def _handler(self, connection):
        client_id = str(uuid.uuid4())
        self.registry.add(client_id, connection)
        try:
            welcome = {
                "type": "system",
                "payload": {"client_id": client_id, "message": "Connected"},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await self._transport.send_message(connection, json.dumps(welcome))

            async for message in connection:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue

                allowed, _ = await self.rate_limiter.check_and_increment(client_id)
                if not allowed:
                    error_msg = json.dumps({
                        "type": "error",
                        "payload": {"message": f"Rate limit exceeded: max {RATE_LIMIT} messages per minute"},
                    })
                    try:
                        await self._transport.send_message(connection, error_msg)
                    except ConnectionClosed:
                        break
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
                await self._transport.send_message(ws, json.dumps(message))
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
        if path == "/history":
            channel = query.get("channel", [None])[0]
            since = query.get("since", [None])[0]
            limit = int(query.get("limit", ["50"])[0])
            result = self.message_store.get_history(channel=channel, since=since, limit=limit)
            response = connection.respond(200, json.dumps(result))
            response.headers["Content-Type"] = "application/json"
            return response
        return None

    async def _cleanup_loop(self):
        ttl_days = MESSAGE_TTL_DAYS
        while True:
            try:
                self.message_store.cleanup_old(ttl_days)
            except Exception:
                pass
            await asyncio.sleep(3600)

    @asynccontextmanager
    async def run(self):
        await self._connect_redis()
        self.rate_limiter.set_redis(self._redis)
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        if self._redis_available:
            self._redis_sub_task = asyncio.create_task(self._redis_subscriber())
        try:
            self._transport.on_connect(self._handler)
            await self._transport.start()
            yield self._transport._server
        finally:
            if self._cleanup_task:
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except (asyncio.CancelledError, Exception):
                    pass
                self._cleanup_task = None
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
            await self._transport.stop()


async def main():
    server = NotificationServer()
    async with server.run():
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
