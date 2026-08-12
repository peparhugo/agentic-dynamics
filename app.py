import asyncio
import json
import os
import uuid
from datetime import datetime, timezone

import aiosqlite
import redis.asyncio as redis
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

REDIS_URL = os.environ.get("REDIS_URL", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "messages.db")


class MessageStore:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute(
            """CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL DEFAULT '',
                type TEXT NOT NULL,
                payload TEXT NOT NULL DEFAULT '{}',
                timestamp TEXT NOT NULL
            )"""
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp DESC)"
        )
        await self._db.commit()

    async def save_message(self, channel: str, msg_type: str, payload: str, timestamp: str) -> None:
        if self._db is None:
            return
        await self._db.execute(
            "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
            (channel, msg_type, payload, timestamp),
        )
        await self._db.commit()

    async def get_messages(self, limit: int = 50, offset: int = 0) -> list[dict]:
        if self._db is None:
            return []
        cursor = await self._db.execute(
            "SELECT id, channel, type, payload, timestamp FROM messages "
            "ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": row[0],
                "channel": row[1],
                "type": row[2],
                "payload": json.loads(row[3]),
                "timestamp": row[4],
            }
            for row in rows
        ]

    async def close(self) -> None:
        if self._db:
            await self._db.close()


class RedisMessageBus:
    def __init__(self, redis_url: str, registry: "ClientRegistry", store: MessageStore | None = None):
        self._redis_url = redis_url
        self._registry = registry
        self._store = store
        self._pub: redis.Redis | None = None
        self._sub: redis.Redis | None = None
        self._sub_task: asyncio.Task | None = None
        self._server_id = str(uuid.uuid4())
        self._running = False
        self._pubsub: redis.client.PubSub | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._redis_url)

    async def connect(self) -> None:
        if not self._redis_url:
            return
        self._pub = redis.from_url(self._redis_url)
        self._sub = redis.from_url(self._redis_url)
        self._running = True
        self._pubsub = self._sub.pubsub()
        await self._pubsub.subscribe("messages")
        self._sub_task = asyncio.create_task(self._subscriber_loop())

    async def publish(self, envelope: dict) -> None:
        if not self._pub:
            return
        await self._pub.publish("messages", json.dumps(envelope))

    async def _subscriber_loop(self) -> None:
        try:
            async for redis_msg in self._pubsub.listen():
                if redis_msg["type"] != "message":
                    continue
                if not self._running:
                    break
                try:
                    envelope = json.loads(redis_msg["data"])
                except (json.JSONDecodeError, TypeError):
                    continue

                routing = envelope.get("routing", "broadcast")
                message = envelope.get("message", "{}")
                exclude = envelope.get("exclude")
                channel = envelope.get("channel", "")
                target = envelope.get("target")

                if routing == "direct" and target:
                    await self._registry.send_to(target, message)
                elif routing == "channel" and channel:
                    await self._registry.broadcast_channel(message, channel, exclude=exclude)
                else:
                    await self._registry.broadcast(message, exclude=exclude)
        except asyncio.CancelledError:
            pass

    async def persist_and_publish(self, routing: str, message: str,
                                  channel: str = "", exclude: str | None = None,
                                  target: str | None = None) -> None:
        if self._store:
            parsed = json.loads(message)
            msg_type = parsed.get("type", "")
            payload_raw = json.dumps(parsed.get("payload", {}))
            timestamp = parsed.get("timestamp", datetime.now(timezone.utc).isoformat())
            await self._store.save_message(channel or "", msg_type, payload_raw, timestamp)

        envelope = {
            "routing": routing,
            "message": message,
            "channel": channel,
            "exclude": exclude,
            "target": target,
        }

        if self.enabled and self._pub:
            await self.publish(envelope)
        else:
            if routing == "direct" and target:
                await self._registry.send_to(target, message)
            elif routing == "channel" and channel:
                await self._registry.broadcast_channel(message, channel, exclude=exclude)
            else:
                await self._registry.broadcast(message, exclude=exclude)

    async def update_client_state(self, client_id: str, action: str,
                                  channel: str | None = None) -> None:
        if not self._pub:
            return
        if action == "subscribe" and channel:
            await self._pub.sadd(f"sub:{channel}", client_id)
            await self._pub.sadd(f"client:{client_id}:channels", channel)
        elif action == "unsubscribe" and channel:
            await self._pub.srem(f"sub:{channel}", client_id)
            await self._pub.srem(f"client:{client_id}:channels", channel)
        elif action == "unsubscribe_all":
            keys = await self._pub.smembers(f"client:{client_id}:channels")
            for ch in keys:
                ch_str = ch.decode() if isinstance(ch, bytes) else ch
                await self._pub.srem(f"sub:{ch_str}", client_id)
            await self._pub.delete(f"client:{client_id}:channels")
        elif action == "register":
            await self._pub.hset("clients", client_id, self._server_id)
        elif action == "unregister":
            await self._pub.hdel("clients", client_id)
            keys = await self._pub.smembers(f"client:{client_id}:channels")
            for ch in keys:
                ch_str = ch.decode() if isinstance(ch, bytes) else ch
                await self._pub.srem(f"sub:{ch_str}", client_id)
            await self._pub.delete(f"client:{client_id}:channels")

    async def close(self) -> None:
        self._running = False
        if self._sub_task:
            self._sub_task.cancel()
            try:
                await self._sub_task
            except asyncio.CancelledError:
                pass
        if self._pubsub:
            await self._pubsub.unsubscribe("messages")
            await self._pubsub.close()
        if self._pub:
            await self._pub.close()
        if self._sub:
            await self._sub.close()


class ClientRegistry:
    def __init__(self):
        self._clients: dict[str, object] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()
        self._bus: RedisMessageBus | None = None
        self._store: MessageStore | None = None

    def set_bus(self, bus: RedisMessageBus) -> None:
        self._bus = bus

    def set_store(self, store: MessageStore) -> None:
        self._store = store

    async def register(self, websocket) -> str:
        client_id = str(uuid.uuid4())
        async with self._lock:
            self._clients[client_id] = websocket
        return client_id

    async def unregister(self, client_id: str) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)

    async def broadcast(self, message: str, *, exclude: str | None = None) -> None:
        disconnected: list[str] = []
        async with self._lock:
            clients = list(self._clients.items())
        for cid, ws in clients:
            if cid == exclude:
                continue
            try:
                await ws.send(message)
            except (ConnectionClosed, OSError):
                disconnected.append(cid)
        for cid in disconnected:
            await self.unregister(cid)

    async def send_to(self, target_id: str, message: str) -> bool:
        async with self._lock:
            ws = self._clients.get(target_id)
        if ws is None:
            return False
        try:
            await ws.send(message)
            return True
        except (ConnectionClosed, OSError):
            await self.unregister(target_id)
            return False

    async def count(self) -> int:
        async with self._lock:
            return len(self._clients)

    async def has_client(self, client_id: str) -> bool:
        async with self._lock:
            return client_id in self._clients

    async def subscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            if channel not in self._channels:
                self._channels[channel] = set()
            self._channels[channel].add(client_id)
        if self._bus:
            await self._bus.update_client_state(client_id, "subscribe", channel)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            if channel in self._channels:
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]
        if self._bus:
            await self._bus.update_client_state(client_id, "unsubscribe", channel)

    async def unsubscribe_all(self, client_id: str) -> None:
        async with self._lock:
            for channel in list(self._channels):
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]
        if self._bus:
            await self._bus.update_client_state(client_id, "unsubscribe_all")

    async def broadcast_channel(self, message: str, channel: str, *, exclude: str | None = None) -> None:
        disconnected: list[str] = []
        async with self._lock:
            subscriber_ids = list(self._channels.get(channel, set()))
            clients = {cid: self._clients.get(cid) for cid in subscriber_ids if cid in self._clients}
        for cid, ws in clients.items():
            if cid == exclude:
                continue
            try:
                await ws.send(message)
            except (ConnectionClosed, OSError):
                disconnected.append(cid)
        for cid in disconnected:
            await self.unregister(cid)

    async def get_channels(self) -> dict[str, int]:
        async with self._lock:
            return {name: len(subs) for name, subs in self._channels.items() if subs}

    async def get_subscribers(self, channel: str) -> list[str]:
        async with self._lock:
            subs = self._channels.get(channel, set())
            return [cid for cid in subs if cid in self._clients]

    async def persist_and_publish(self, routing: str, message: str,
                                  channel: str = "", exclude: str | None = None,
                                  target: str | None = None) -> None:
        if self._bus:
            await self._bus.persist_and_publish(routing, message, channel, exclude, target)
        else:
            if self._store:
                parsed = json.loads(message)
                msg_type = parsed.get("type", "")
                payload_raw = json.dumps(parsed.get("payload", {}))
                timestamp = parsed.get("timestamp", datetime.now(timezone.utc).isoformat())
                await self._store.save_message(channel or "", msg_type, payload_raw, timestamp)

            if routing == "direct" and target:
                await self.send_to(target, message)
            elif routing == "channel" and channel:
                await self.broadcast_channel(message, channel, exclude=exclude)
            else:
                await self.broadcast(message, exclude=exclude)


registry = ClientRegistry()


def _make_message(msg_type: str, payload: dict, **extra) -> str:
    msg = {
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    msg.update(extra)
    return json.dumps(msg)


def _send_ws(ws, message: str):
    return ws.send(message)


def make_ws_handler(reg: ClientRegistry):
    async def handler(websocket) -> None:
        client_id = await reg.register(websocket)

        welcome = _make_message("system", {"client_id": client_id, "connected": True, "message": "Welcome"})
        await _send_ws(websocket, welcome)

        join_notice = _make_message("system", {"client_id": client_id, "event": "connected"})
        await reg.broadcast(join_notice, exclude=client_id)

        if reg._bus:
            await reg._bus.update_client_state(client_id, "register")

        try:
            async for raw in websocket:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type", "broadcast")
                payload = data.get("payload", {})

                if msg_type == "subscribe":
                    channel = data.get("channel")
                    if channel:
                        await reg.subscribe(client_id, channel)
                elif msg_type == "unsubscribe":
                    channel = data.get("channel")
                    if channel:
                        await reg.unsubscribe(client_id, channel)
                elif msg_type == "direct":
                    target = data.get("target")
                    if target:
                        outbound = _make_message(msg_type, payload)
                        await reg.persist_and_publish("direct", outbound, target=target)
                else:
                    channel = data.get("channel")
                    if channel:
                        outbound = _make_message(msg_type, payload, channel=channel)
                        await reg.persist_and_publish("channel", outbound, channel=channel, exclude=client_id)
                    elif msg_type == "broadcast":
                        outbound = _make_message(msg_type, payload)
                        await reg.persist_and_publish("broadcast", outbound, exclude=client_id)
                    else:
                        outbound = _make_message(msg_type, payload)
                        await reg.persist_and_publish("broadcast", outbound, exclude=None)
        except ConnectionClosed:
            pass
        finally:
            await reg.unsubscribe_all(client_id)
            await reg.unregister(client_id)
            leave_notice = _make_message("system", {"client_id": client_id, "event": "disconnected"})
            await reg.broadcast(leave_notice, exclude=None)

            if reg._bus:
                await reg._bus.update_client_state(client_id, "unregister")

    return handler


def make_http_handler(reg: ClientRegistry):
    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            raw = await asyncio.wait_for(reader.readline(), timeout=10)
            line = raw.decode().strip()
            if not line:
                writer.close()
                return

            parts = line.split()
            if len(parts) < 2:
                writer.close()
                return

            method, path = parts[0], parts[1]
            query_params: dict[str, str] = {}
            if "?" in path:
                path, query_string = path.split("?", 1)
                for pair in query_string.split("&"):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        query_params[k] = v

            if method == "GET" and path == "/health":
                body = json.dumps({"connected_clients": await reg.count()})
                response = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                    f"{body}"
                )
            elif method == "GET" and path == "/messages":
                limit = int(query_params.get("limit", "50"))
                offset = int(query_params.get("offset", "0"))
                messages = []
                if reg._store:
                    messages = await reg._store.get_messages(limit=limit, offset=offset)
                body = json.dumps(messages)
                response = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                    f"{body}"
                )
            elif method == "GET" and path.startswith("/channels/") and path.endswith("/subscribers"):
                prefix = "/channels/"
                suffix = "/subscribers"
                name = path[len(prefix):-len(suffix)]
                if name:
                    subscribers = await reg.get_subscribers(name)
                    body = json.dumps({"channel": name, "subscribers": subscribers})
                    response = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-Type: application/json\r\n"
                        f"Content-Length: {len(body)}\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                        f"{body}"
                    )
                else:
                    body = json.dumps({"error": "not found"})
                    response = (
                        "HTTP/1.1 404 Not Found\r\n"
                        "Content-Type: application/json\r\n"
                        f"Content-Length: {len(body)}\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                        f"{body}"
                    )
            elif method == "GET" and path == "/channels":
                channels = await reg.get_channels()
                body = json.dumps({"channels": channels})
                response = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                    f"{body}"
                )
            else:
                body = json.dumps({"error": "not found"})
                response = (
                    "HTTP/1.1 404 Not Found\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                    f"{body}"
                )

            writer.write(response.encode())
            await writer.drain()
        except (asyncio.TimeoutError, OSError):
            pass
        finally:
            writer.close()

    return handler


async def start_server(ws_host: str = "localhost", ws_port: int = 8765,
                       http_host: str = "localhost", http_port: int = 8080,
                       reg: ClientRegistry | None = None) -> tuple:
    _reg = reg if reg is not None else registry
    ws_handler_fn = make_ws_handler(_reg)
    http_handler_fn = make_http_handler(_reg)
    ws_server = await serve(ws_handler_fn, ws_host, ws_port)
    http_server = await asyncio.start_server(http_handler_fn, http_host, http_port)
    return ws_server, http_server


async def main() -> None:
    store = MessageStore(DATABASE_URL)
    await store.connect()
    registry.set_store(store)

    bus = RedisMessageBus(REDIS_URL, registry, store)
    await bus.connect()
    registry.set_bus(bus)

    ws_server, http_server = await start_server()
    try:
        async with ws_server, http_server:
            await asyncio.Future()
    finally:
        await bus.close()
        await store.close()


if __name__ == "__main__":
    asyncio.run(main())
