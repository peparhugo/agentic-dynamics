"""Async WebSocket notification service with Redis distribution and SQLite history."""

import asyncio
import json
import os
import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree as ET

from websockets.server import WebSocketServerProtocol, serve

SUPPORTED_MESSAGE_TYPES = frozenset({"broadcast", "direct", "system", "subscribe", "unsubscribe"})
SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
SERVICE_NS = "urn:notification-service"
BROKER_CHANNEL = "notification-service:messages"
CLIENTS_KEY = "notification-service:clients"
CHANNEL_KEY_PREFIX = "notification-service:channel:"


class MemoryBroker:
    """Small local broker used when Redis has not been configured."""

    def __init__(self) -> None:
        self.clients: dict[str, str] = {}
        self.channels: dict[str, set[str]] = defaultdict(set)
        self.listeners: set[asyncio.Queue[str]] = set()

    async def connect(self) -> asyncio.Queue[str]:
        listener: asyncio.Queue[str] = asyncio.Queue()
        self.listeners.add(listener)
        return listener

    async def disconnect(self, listener: asyncio.Queue[str]) -> None:
        self.listeners.discard(listener)

    async def publish(self, message: str) -> None:
        for listener in tuple(self.listeners):
            await listener.put(message)

    async def register(self, client_id: str, instance_id: str) -> None:
        self.clients[client_id] = instance_id

    async def unregister(self, client_id: str) -> None:
        self.clients.pop(client_id, None)
        for channel in tuple(self.channels):
            self.channels[channel].discard(client_id)
            if not self.channels[channel]:
                del self.channels[channel]

    async def subscribe(self, client_id: str, channel: str) -> None:
        self.channels[channel].add(client_id)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        self.channels[channel].discard(client_id)
        if not self.channels[channel]:
            del self.channels[channel]

    async def channel_members(self, channel: str) -> list[str]:
        return sorted(self.channels.get(channel, ()))

    async def client_members(self) -> list[str]:
        return sorted(self.clients)

    async def channel_counts(self) -> dict[str, int]:
        return {channel: len(members) for channel, members in self.channels.items()}

    async def close(self) -> None:
        return None


class RedisBroker:
    """Redis pub/sub transport and shared connection-state store."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.redis: Any = None
        self.pubsub: Any = None

    async def connect(self) -> Any:
        import redis.asyncio as redis

        self.redis = redis.from_url(self.url, decode_responses=True)
        self.pubsub = self.redis.pubsub()
        await self.pubsub.subscribe(BROKER_CHANNEL)
        return self.pubsub

    async def disconnect(self, listener: Any) -> None:
        await listener.unsubscribe(BROKER_CHANNEL)
        await listener.close()

    async def publish(self, message: str) -> None:
        await self.redis.publish(BROKER_CHANNEL, message)

    async def register(self, client_id: str, instance_id: str) -> None:
        await self.redis.hset(CLIENTS_KEY, client_id, instance_id)

    async def unregister(self, client_id: str) -> None:
        channels = await self.redis.smembers(f"notification-service:client:{client_id}:channels")
        pipe = self.redis.pipeline()
        pipe.hdel(CLIENTS_KEY, client_id)
        pipe.delete(f"notification-service:client:{client_id}:channels")
        for channel in channels:
            pipe.srem(f"{CHANNEL_KEY_PREFIX}{channel}", client_id)
        await pipe.execute()

    async def subscribe(self, client_id: str, channel: str) -> None:
        pipe = self.redis.pipeline()
        pipe.sadd(f"{CHANNEL_KEY_PREFIX}{channel}", client_id)
        pipe.sadd(f"notification-service:client:{client_id}:channels", channel)
        await pipe.execute()

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        pipe = self.redis.pipeline()
        pipe.srem(f"{CHANNEL_KEY_PREFIX}{channel}", client_id)
        pipe.srem(f"notification-service:client:{client_id}:channels", channel)
        await pipe.execute()

    async def channel_members(self, channel: str) -> list[str]:
        return sorted(await self.redis.smembers(f"{CHANNEL_KEY_PREFIX}{channel}"))

    async def client_members(self) -> list[str]:
        return sorted(await self.redis.hkeys(CLIENTS_KEY))

    async def channel_counts(self) -> dict[str, int]:
        counts = {}
        async for key in self.redis.scan_iter(match=f"{CHANNEL_KEY_PREFIX}*"):
            count = await self.redis.scard(key)
            if count:
                counts[key.removeprefix(CHANNEL_KEY_PREFIX)] = count
        return counts

    async def close(self) -> None:
        if self.redis is not None:
            await self.redis.aclose()


class MessageStore:
    def __init__(self, database_url: str | None) -> None:
        path = database_url.removeprefix("sqlite:///") if database_url else ":memory:"
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, type TEXT NOT NULL, payload TEXT NOT NULL, timestamp TEXT NOT NULL)"
        )
        self.connection.commit()
        self.lock = asyncio.Lock()

    async def add(self, channel: str | None, message_type: str, payload: dict[str, Any], timestamp: str) -> None:
        async with self.lock:
            self.connection.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (channel, message_type, json.dumps(payload), timestamp),
            )
            self.connection.commit()

    async def list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        async with self.lock:
            rows = self.connection.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        return [{"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]} for row in rows]

    def close(self) -> None:
        self.connection.close()


class NotificationServer:
    """Coordinates connected clients and distributes notifications through a broker."""

    def __init__(self, redis_url: str | None = None, database_url: str | None = None, broker: Any = None) -> None:
        redis_url = redis_url if redis_url is not None else os.getenv("REDIS_URL")
        self.broker = broker or (RedisBroker(redis_url) if redis_url else MemoryBroker())
        self.store = MessageStore(database_url if database_url is not None else os.getenv("DATABASE_URL"))
        self.clients: dict[str, WebSocketServerProtocol] = {}
        self._clients_lock = asyncio.Lock()
        self.instance_id = str(uuid.uuid4())
        self.listener: Any = None
        self.worker: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self.worker is None:
            self.listener = await self.broker.connect()
            self.worker = asyncio.create_task(self._deliver_published_messages())

    async def close(self) -> None:
        if self.worker is not None:
            self.worker.cancel()
            await asyncio.gather(self.worker, return_exceptions=True)
            await self.broker.disconnect(self.listener)
            self.worker = None
        await self.broker.close()
        self.store.close()

    async def _deliver_published_messages(self) -> None:
        while True:
            if isinstance(self.listener, asyncio.Queue):
                raw_message = await self.listener.get()
            else:
                event = await self.listener.get_message(ignore_subscribe_messages=True, timeout=1)
                if event is None:
                    continue
                raw_message = event["data"]
            message = json.loads(raw_message)
            recipients = message.get("recipients")
            async with self._clients_lock:
                local = set(self.clients)
            for client_id in recipients:
                if client_id in local:
                    await self._send_serialized(client_id, message["message"])

    async def register(self, websocket: WebSocketServerProtocol) -> str:
        await self.start()
        client_id = str(uuid.uuid4())
        async with self._clients_lock:
            self.clients[client_id] = websocket
        await self.broker.register(client_id, self.instance_id)
        await self.send(client_id, "system", {"event": "connected", "client_id": client_id}, persist=False)
        return client_id

    async def unregister(self, client_id: str) -> None:
        async with self._clients_lock:
            self.clients.pop(client_id, None)
        await self.broker.unregister(client_id)

    async def client_count(self) -> int:
        async with self._clients_lock:
            return len(self.clients)

    @staticmethod
    def message(message_type: str, payload: dict[str, Any], channel: str | None = None) -> str:
        message = {"type": message_type, "payload": payload, "timestamp": datetime.now(timezone.utc).isoformat()}
        if channel is not None:
            message["channel"] = channel
        return json.dumps(message)

    async def _send_serialized(self, client_id: str, message: str) -> bool:
        async with self._clients_lock:
            websocket = self.clients.get(client_id)
        if websocket is None:
            return False
        try:
            await websocket.send(message)
        except Exception:
            await self.unregister(client_id)
            return False
        return True

    async def send(self, client_id: str, message_type: str, payload: dict[str, Any], channel: str | None = None, persist: bool = True) -> bool:
        message = self.message(message_type, payload, channel)
        if persist:
            await self.store.add(channel, message_type, payload, json.loads(message)["timestamp"])
        return await self._send_serialized(client_id, message)

    async def broadcast(
        self,
        message_type: str,
        payload: dict[str, Any],
        channel: str | None = None,
        recipients_override: list[str] | None = None,
    ) -> None:
        await self.start()
        recipients = recipients_override or (await self.broker.channel_members(channel) if channel is not None else await self.broker.client_members())
        message = self.message(message_type, payload, channel)
        await self.store.add(channel, message_type, payload, json.loads(message)["timestamp"])
        await self.broker.publish(json.dumps({"message": message, "recipients": recipients}))

    async def subscribe(self, client_id: str, channel: str) -> None:
        await self.broker.subscribe(client_id, channel)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        await self.broker.unsubscribe(client_id, channel)

    async def channel_counts(self) -> dict[str, int]:
        return await self.broker.channel_counts()

    async def channel_subscribers(self, channel: str) -> list[str]:
        return await self.broker.channel_members(channel)

    async def websocket_handler(self, websocket: WebSocketServerProtocol) -> None:
        client_id = await self.register(websocket)
        try:
            async for raw_message in websocket:
                await self.handle_message(client_id, raw_message)
        finally:
            await self.unregister(client_id)

    async def handle_message(self, sender_id: str, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
            message_type, payload = message["type"], message["payload"]
            if message_type not in SUPPORTED_MESSAGE_TYPES or not isinstance(payload, dict):
                raise ValueError
            channel = message.get("channel")
            if channel is not None and (not isinstance(channel, str) or not channel):
                raise ValueError
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            await self.send(sender_id, "system", {"event": "error", "message": "invalid message"}, persist=False)
            return
        if message_type == "subscribe":
            if channel is None:
                await self.send(sender_id, "system", {"event": "error", "message": "invalid channel"}, persist=False)
                return
            await self.subscribe(sender_id, channel)
        elif message_type == "unsubscribe":
            if channel is None:
                await self.send(sender_id, "system", {"event": "error", "message": "invalid channel"}, persist=False)
                return
            await self.unsubscribe(sender_id, channel)
        elif message_type == "broadcast":
            await self.broadcast("broadcast", payload, channel)
        elif message_type == "direct":
            recipient_id, content = payload.get("client_id"), payload.get("message")
            if not isinstance(recipient_id, str) or not isinstance(content, dict):
                await self.send(sender_id, "system", {"event": "error", "message": "invalid direct message"}, persist=False)
                return
            await self.broadcast("direct", content, recipients_override=[recipient_id])
        else:
            await self.broadcast("system", payload, channel)

    async def soap_handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request = await reader.readuntil(b"\r\n\r\n")
            headers = request.decode("iso-8859-1")
            method, path, _ = headers.split("\r\n", 1)[0].split(" ", 2)
            parsed = urlsplit(path)
            if method == "GET" and parsed.path == "/channels":
                response = self.http_response("200 OK", json.dumps(await self.channel_counts()).encode(), "application/json")
            elif method == "GET" and parsed.path.startswith("/channels/") and parsed.path.endswith("/subscribers"):
                channel = parsed.path[len("/channels/") : -len("/subscribers")]
                response = self.http_response("200 OK", json.dumps(await self.channel_subscribers(channel)).encode(), "application/json") if channel and "/" not in channel else self.http_response("404 Not Found", b'{"error":"not found"}', "application/json")
            elif method == "GET" and parsed.path == "/messages":
                query = parse_qs(parsed.query)
                limit, offset = int(query.get("limit", [50])[0]), int(query.get("offset", [0])[0])
                if not 0 <= offset or not 1 <= limit <= 1000:
                    raise ValueError
                response = self.http_response("200 OK", json.dumps(await self.store.list(limit, offset)).encode(), "application/json")
            elif method != "POST":
                response = self.http_response("404 Not Found", b'{"error":"not found"}', "application/json")
            else:
                response = await self.soap_response(headers, reader)
        except (ValueError, ET.ParseError, asyncio.IncompleteReadError, UnicodeDecodeError):
            response = self.http_response("400 Bad Request", self.soap_fault("Invalid SOAP request"))
        writer.write(response)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def soap_response(self, headers: str, reader: asyncio.StreamReader) -> bytes:
        content_length = next(int(line.split(":", 1)[1].strip()) for line in headers.split("\r\n") if line.lower().startswith("content-length:"))
        root = ET.fromstring(await reader.readexactly(content_length))
        if next(iter(root)).find(".//{*}Health") is None:
            raise ValueError("unsupported SOAP operation")
        return self.http_response("200 OK", self.soap_health_response(await self.client_count()))

    @staticmethod
    def soap_health_response(client_count: int) -> bytes:
        return (f'<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="{SOAP_NS}" xmlns:ns="{SERVICE_NS}"><soap:Body><ns:HealthResponse><ns:connectedClientCount>{client_count}</ns:connectedClientCount></ns:HealthResponse></soap:Body></soap:Envelope>').encode()

    @staticmethod
    def soap_fault(message: str) -> bytes:
        return (f'<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="{SOAP_NS}"><soap:Body><soap:Fault><faultcode>soap:Client</faultcode><faultstring>{message}</faultstring></soap:Fault></soap:Body></soap:Envelope>').encode()

    @staticmethod
    def http_response(status: str, body: bytes, content_type: str = "text/xml; charset=utf-8") -> bytes:
        return (f"HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode() + body


async def main() -> None:
    server = NotificationServer()
    await server.start()
    try:
        async with serve(server.websocket_handler, "localhost", 8765), await asyncio.start_server(server.soap_handler, "localhost", 8766):
            await asyncio.Future()
    finally:
        await server.close()


if __name__ == "__main__":
    asyncio.run(main())
