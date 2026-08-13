"""Async WebSocket notification server."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sqlite3
import uuid
from collections.abc import Mapping
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlparse, urlsplit

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Response
from websockets.datastructures import Headers

MESSAGE_TYPES = frozenset({"broadcast", "direct", "system", "subscribe", "unsubscribe"})
REDIS_MESSAGES_CHANNEL = "notifications:messages"


class MemoryBroker:
    """In-process broker used when Redis isn't configured and by tests."""

    def __init__(self) -> None:
        self._subscribers: set = set()
        self.client_state: dict[str, str] = {}
        self.channel_state: dict[str, set[str]] = {}

    async def start(self, callback) -> None:
        self._subscribers.add(callback)

    async def close(self, callback=None) -> None:
        if callback is None:
            self._subscribers.clear()
        else:
            self._subscribers.discard(callback)

    async def publish(self, message: dict[str, object]) -> None:
        await asyncio.gather(*(callback(message) for callback in tuple(self._subscribers)))

    async def add_client(self, client_id: str, server_id: str) -> None:
        self.client_state[client_id] = server_id

    async def remove_client(self, client_id: str) -> None:
        self.client_state.pop(client_id, None)
        for subscribers in self.channel_state.values():
            subscribers.discard(client_id)

    async def subscribe_client(self, client_id: str, channel: str) -> None:
        self.channel_state.setdefault(channel, set()).add(client_id)

    async def unsubscribe_client(self, client_id: str, channel: str) -> None:
        self.channel_state.get(channel, set()).discard(client_id)


class RedisBroker:
    """Small async Redis RESP client for pub/sub and connection state."""

    def __init__(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
            raise ValueError("REDIS_URL must be a redis URL")
        if parsed.scheme == "rediss":
            raise ValueError("rediss URLs are not supported")
        self.host = parsed.hostname
        self.port = parsed.port or 6379
        self.password = parsed.password
        self.database = int(parsed.path.lstrip("/") or "0")
        self._callback = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._listener: asyncio.Task[None] | None = None

    @staticmethod
    def _command(*parts: str) -> bytes:
        encoded = [part.encode() for part in parts]
        return b"*%d\r\n" % len(encoded) + b"".join(
            b"$%d\r\n" % len(part) + part + b"\r\n" for part in encoded
        )

    async def _read(self, reader: asyncio.StreamReader):
        prefix = await reader.readexactly(1)
        if prefix == b"+":
            return (await reader.readline()).rstrip(b"\r\n").decode()
        if prefix == b"-":
            raise RuntimeError((await reader.readline()).decode().strip())
        if prefix == b":":
            return int(await reader.readline())
        if prefix == b"$":
            length = int(await reader.readline())
            return None if length == -1 else (await reader.readexactly(length + 2))[:-2].decode()
        if prefix == b"*":
            length = int(await reader.readline())
            return [await self._read(reader) for _ in range(length)]
        raise RuntimeError("invalid Redis response")

    async def _connect(self):
        reader, writer = await asyncio.open_connection(self.host, self.port)
        if self.password is not None:
            writer.write(self._command("AUTH", self.password))
            await writer.drain()
            await self._read(reader)
        if self.database:
            writer.write(self._command("SELECT", str(self.database)))
            await writer.drain()
            await self._read(reader)
        return reader, writer

    async def _execute(self, *parts: str) -> object:
        reader, writer = await self._connect()
        try:
            writer.write(self._command(*parts))
            await writer.drain()
            return await self._read(reader)
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self, callback) -> None:
        self._callback = callback
        self._reader, self._writer = await self._connect()
        self._writer.write(self._command("SUBSCRIBE", REDIS_MESSAGES_CHANNEL))
        await self._writer.drain()
        await self._read(self._reader)
        self._listener = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        assert self._reader is not None
        try:
            while True:
                response = await self._read(self._reader)
                if isinstance(response, list) and response[0] == "message" and self._callback:
                    await self._callback(json.loads(response[2]))
        except (asyncio.CancelledError, asyncio.IncompleteReadError):
            raise

    async def close(self, callback=None) -> None:
        if self._listener:
            self._listener.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()

    async def publish(self, message: dict[str, object]) -> None:
        await self._execute("PUBLISH", REDIS_MESSAGES_CHANNEL, json.dumps(message))

    async def add_client(self, client_id: str, server_id: str) -> None:
        await self._execute("SET", f"notifications:client:{client_id}", server_id)

    async def remove_client(self, client_id: str) -> None:
        await self._execute("DEL", f"notifications:client:{client_id}")

    async def subscribe_client(self, client_id: str, channel: str) -> None:
        await self._execute("SADD", f"notifications:channel:{channel}", client_id)

    async def unsubscribe_client(self, client_id: str, channel: str) -> None:
        await self._execute("SREM", f"notifications:channel:{channel}", client_id)


class MessageStore:
    """SQLite-backed append-only message history."""

    def __init__(self, database_url: str | None = None) -> None:
        value = database_url or os.getenv("DATABASE_URL", "sqlite:///notifications.db")
        if value == "sqlite:///:memory:":
            self.path = ":memory:"
        elif value.startswith("sqlite:///"):
            self.path = value[len("sqlite:///"):]
        else:
            self.path = value
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, type TEXT NOT NULL, payload TEXT NOT NULL, timestamp TEXT NOT NULL)")
        self.connection.commit()
        self.lock = asyncio.Lock()

    async def add(self, message: dict[str, object]) -> int:
        async with self.lock:
            cursor = self.connection.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (message.get("channel"), message["type"], json.dumps(message["payload"]), message["timestamp"]),
            )
            self.connection.commit()
            return cursor.lastrowid

    async def list(self, limit: int, offset: int) -> list[dict[str, object]]:
        async with self.lock:
            rows = self.connection.execute("SELECT id, channel, type, payload, timestamp FROM messages ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [{"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]} for row in rows]

    def close(self) -> None:
        self.connection.close()


class ClientRegistry:
    """Tracks active connections without exposing mutable internal state."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    async def add(self, connection: ServerConnection) -> str:
        client_id = str(uuid.uuid4())
        async with self._lock:
            self._clients[client_id] = connection
        return client_id

    async def remove(self, client_id: str) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)
            for channel in tuple(self._channels):
                subscribers = self._channels[channel]
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[channel]

    async def count(self) -> int:
        async with self._lock:
            return len(self._clients)

    async def get(self, client_id: str) -> ServerConnection | None:
        async with self._lock:
            return self._clients.get(client_id)

    async def connections(self) -> tuple[ServerConnection, ...]:
        async with self._lock:
            return tuple(self._clients.values())

    async def subscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            if client_id in self._clients:
                self._channels.setdefault(channel, set()).add(client_id)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    async def channel_connections(self, channel: str) -> tuple[ServerConnection, ...]:
        async with self._lock:
            return tuple(
                self._clients[client_id]
                for client_id in self._channels.get(channel, set())
                if client_id in self._clients
            )

    async def channels(self) -> dict[str, int]:
        async with self._lock:
            return {channel: len(subscribers) for channel, subscribers in self._channels.items()}

    async def subscribers(self, channel: str) -> tuple[str, ...]:
        async with self._lock:
            return tuple(sorted(self._channels.get(channel, set())))


class NotificationServer:
    """Routes client messages and owns the WebSocket client registry."""

    def __init__(self, redis_url: str | None = None, database_url: str | None = None, broker=None) -> None:
        self.clients = ClientRegistry()
        self.server_id = str(uuid.uuid4())
        self.broker = broker or (RedisBroker(redis_url or os.getenv("REDIS_URL")) if redis_url or os.getenv("REDIS_URL") else MemoryBroker())
        self.messages = MessageStore(database_url)
        self._started = False

    async def start(self) -> None:
        if not self._started:
            await self.broker.start(self._deliver_broker_message)
            self._started = True

    async def close(self) -> None:
        if self._started:
            await self.broker.close(self._deliver_broker_message)
            self._started = False
        self.messages.close()

    @staticmethod
    def message(message_type: str, payload: Mapping[str, object]) -> dict[str, object]:
        return {
            "type": message_type,
            "payload": dict(payload),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def validate_message(raw_message: str) -> dict[str, object]:
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError as error:
            raise ValueError("message must be valid JSON") from error

        if not isinstance(message, dict):
            raise ValueError("message must be a JSON object")
        if message.get("type") not in MESSAGE_TYPES:
            raise ValueError("unsupported message type")
        if not isinstance(message.get("payload"), dict):
            raise ValueError("payload must be a JSON object")
        if "timestamp" in message and not isinstance(message["timestamp"], str):
            raise ValueError("timestamp must be a string")
        if "channel" in message and (
            not isinstance(message["channel"], str) or not message["channel"]
        ):
            raise ValueError("channel must be a non-empty string")
        if message["type"] in {"subscribe", "unsubscribe"} and "channel" not in message:
            raise ValueError(f"{message['type']} messages require channel")
        return message

    async def send(self, connection: ServerConnection, message: dict[str, object]) -> None:
        try:
            await connection.send(json.dumps(message))
        except ConnectionClosed:
            return

    async def broadcast(self, message: dict[str, object]) -> None:
        await asyncio.gather(
            *(self.send(connection, message) for connection in await self.clients.connections())
        )

    async def broadcast_channel(self, channel: str, message: dict[str, object]) -> None:
        await asyncio.gather(
            *(self.send(connection, message) for connection in await self.clients.channel_connections(channel))
        )

    async def _deliver_broker_message(self, message: dict[str, object]) -> None:
        if message["type"] == "direct":
            target_id = message["payload"].get("client_id")
            if isinstance(target_id, str):
                target = await self.clients.get(target_id)
                if target is not None:
                    await self.send(target, message)
            return
        channel = message.get("channel")
        if isinstance(channel, str):
            await self.broadcast_channel(channel, message)
        else:
            await self.broadcast(message)

    async def handle_message(self, client_id: str, raw_message: str) -> None:
        try:
            message = self.validate_message(raw_message)
        except ValueError as error:
            connection = await self.clients.get(client_id)
            if connection is not None:
                await self.send(connection, self.message("system", {"error": str(error)}))
            return

        message["timestamp"] = datetime.now(timezone.utc).isoformat()
        if message["type"] == "subscribe":
            await self.clients.subscribe(client_id, message["channel"])
            await self.broker.subscribe_client(client_id, message["channel"])
            return
        if message["type"] == "unsubscribe":
            await self.clients.unsubscribe(client_id, message["channel"])
            await self.broker.unsubscribe_client(client_id, message["channel"])
            return
        if message["type"] == "direct":
            target_id = message["payload"].get("client_id")
            if not isinstance(target_id, str):
                connection = await self.clients.get(client_id)
                if connection is not None:
                    await self.send(connection, self.message("system", {"error": "direct messages require payload.client_id"}))
                return
            await self.messages.add(message)
            await self.broker.publish(message)
            return

        await self.messages.add(message)
        await self.broker.publish(message)

    async def websocket_handler(self, connection: ServerConnection) -> None:
        client_id = await self.clients.add(connection)
        await self.broker.add_client(client_id, self.server_id)
        try:
            await self.send(connection, self.message("system", {"client_id": client_id}))
            async for raw_message in connection:
                await self.handle_message(client_id, raw_message)
        finally:
            await self.clients.remove(client_id)
            await self.broker.remove_client(client_id)

    async def process_request(self, connection: ServerConnection, request: object) -> Response | None:
        parsed = urlsplit(getattr(request, "path", ""))
        path = parsed.path
        if path == "/health":
            return self.json_response({"connected_clients": await self.clients.count()})
        if path == "/channels":
            channels = await self.clients.channels()
            return self.json_response(
                {
                    "channels": [
                        {"name": name, "subscriber_count": count}
                        for name, count in sorted(channels.items())
                    ]
                }
            )
        if path.startswith("/channels/") and path.endswith("/subscribers"):
            name = unquote(path[len("/channels/") : -len("/subscribers")].rstrip("/"))
            if name:
                return self.json_response(
                    {"channel": name, "subscribers": list(await self.clients.subscribers(name))}
                )
        if path.startswith("/channels/"):
            return self.json_response({"error": "not found"}, HTTPStatus.NOT_FOUND)
        if path == "/messages":
            query = dict(parse_qsl(parsed.query))
            try:
                limit = int(query.get("limit", "50"))
                offset = int(query.get("offset", "0"))
            except ValueError:
                return self.json_response({"error": "limit and offset must be integers"}, HTTPStatus.BAD_REQUEST)
            if not 1 <= limit <= 1000 or offset < 0:
                return self.json_response({"error": "limit must be 1-1000 and offset non-negative"}, HTTPStatus.BAD_REQUEST)
            return self.json_response({"messages": await self.messages.list(limit, offset)})
        if path != "/health":
            return None

    @staticmethod
    def json_response(payload: Mapping[str, object], status: HTTPStatus = HTTPStatus.OK) -> Response:
        body = json.dumps(payload).encode()
        return Response(
            status,
            status.phrase,
            Headers({"Content-Type": "application/json", "Content-Length": str(len(body))}),
            body,
        )

    @asynccontextmanager
    async def create_server(self, host: str = "127.0.0.1", port: int = 8765):
        await self.start()
        try:
            async with serve(self.websocket_handler, host, port, process_request=self.process_request) as server:
                yield server
        finally:
            await self.close()


async def main() -> None:
    server = NotificationServer()
    async with server.create_server():
        await asyncio.get_running_loop().create_future()


if __name__ == "__main__":
    asyncio.run(main())
