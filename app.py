"""Async notification server with pluggable client transports."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit
from xml.etree import ElementTree

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

import redis.asyncio as redis
from redis.asyncio.client import PubSub, Redis


SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
SERVICE_NS = "urn:notification-server"
SUPPORTED_TYPES = {"broadcast", "direct", "subscribe", "unsubscribe", "system"}
REDIS_CHANNEL = "notification:messages"
REDIS_PREFIX = "notification"
RATE_LIMIT_WINDOW_SECONDS = 60
DEFAULT_RATE_LIMIT = 100
DEFAULT_MESSAGE_TTL_DAYS = 7


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def message(
    message_type: str, payload: dict[str, Any], channel: str | None = None
) -> dict[str, Any]:
    outgoing = {"type": message_type, "payload": payload, "timestamp": utc_timestamp()}
    if channel is not None:
        outgoing["channel"] = channel
    return outgoing


class MessageStore:
    """SQLite-backed history for accepted user messages."""

    def __init__(self, database_url: str) -> None:
        prefix = "sqlite:///"
        self.path = database_url[len(prefix) :] if database_url.startswith(prefix) else database_url
        if not self.path:
            raise ValueError("DATABASE_URL must contain a SQLite path")
        self._connection: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    def open(self) -> None:
        with self._lock:
            self._connection = sqlite3.connect(self.path, check_same_thread=False)
            self._connection.execute(
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
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS messages_channel_timestamp "
                "ON messages (channel, timestamp, id)"
            )
            self._connection.commit()

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def add(self, outgoing: dict[str, Any]) -> int:
        with self._lock:
            if self._connection is None:
                raise RuntimeError("message store is not open")
            cursor = self._connection.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (
                    outgoing.get("channel"),
                    outgoing["type"],
                    json.dumps(outgoing["payload"], separators=(",", ":")),
                    outgoing["timestamp"],
                ),
            )
            self._connection.commit()
            return int(cursor.lastrowid)

    def list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with self._lock:
            if self._connection is None:
                raise RuntimeError("message store is not open")
            rows = self._connection.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
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

    def history(
        self, channel: str, since: str, limit: int
    ) -> tuple[list[dict[str, Any]], bool]:
        with self._lock:
            if self._connection is None:
                raise RuntimeError("message store is not open")
            rows = self._connection.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "WHERE channel = ? AND timestamp >= ? "
                "ORDER BY timestamp ASC, id ASC LIMIT ?",
                (channel, since, limit + 1),
            ).fetchall()
        has_more = len(rows) > limit
        return (
            [
                {
                    "id": row[0],
                    "channel": row[1],
                    "type": row[2],
                    "payload": json.loads(row[3]),
                    "timestamp": row[4],
                }
                for row in rows[:limit]
            ],
            has_more,
        )

    def delete_before(self, timestamp: str) -> int:
        with self._lock:
            if self._connection is None:
                raise RuntimeError("message store is not open")
            cursor = self._connection.execute(
                "DELETE FROM messages WHERE timestamp < ?", (timestamp,)
            )
            self._connection.commit()
            return cursor.rowcount


class RedisState:
    """Distributed client presence and channel subscriptions."""

    def __init__(self, client: Redis) -> None:
        self.client = client

    @staticmethod
    def _text(value: Any) -> str:
        return value.decode() if isinstance(value, bytes) else str(value)

    async def add_client(self, client_id: str, instance_id: str) -> None:
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.sadd(f"{REDIS_PREFIX}:clients", client_id)
            pipe.hset(
                f"{REDIS_PREFIX}:client:{client_id}",
                mapping={"instance_id": instance_id, "connected_at": utc_timestamp()},
            )
            await pipe.execute()

    async def remove_client(self, client_id: str) -> None:
        channel_key = f"{REDIS_PREFIX}:client_channels:{client_id}"
        channels = await self.client.smembers(channel_key)
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.srem(f"{REDIS_PREFIX}:clients", client_id)
            pipe.delete(f"{REDIS_PREFIX}:client:{client_id}", channel_key)
            for raw_channel in channels:
                channel = self._text(raw_channel)
                pipe.srem(f"{REDIS_PREFIX}:channel:{channel}", client_id)
            await pipe.execute()
        for raw_channel in channels:
            channel = self._text(raw_channel)
            key = f"{REDIS_PREFIX}:channel:{channel}"
            if not await self.client.scard(key):
                await self.client.srem(f"{REDIS_PREFIX}:channels", channel)

    async def subscribe(self, client_id: str, channel: str) -> None:
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.sadd(f"{REDIS_PREFIX}:channels", channel)
            pipe.sadd(f"{REDIS_PREFIX}:channel:{channel}", client_id)
            pipe.sadd(f"{REDIS_PREFIX}:client_channels:{client_id}", channel)
            await pipe.execute()

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        key = f"{REDIS_PREFIX}:channel:{channel}"
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.srem(key, client_id)
            pipe.srem(f"{REDIS_PREFIX}:client_channels:{client_id}", channel)
            await pipe.execute()
        if not await self.client.scard(key):
            await self.client.srem(f"{REDIS_PREFIX}:channels", channel)

    async def client_exists(self, client_id: str) -> bool:
        return bool(await self.client.sismember(f"{REDIS_PREFIX}:clients", client_id))

    async def is_subscribed(self, client_id: str, channel: str) -> bool:
        return bool(
            await self.client.sismember(f"{REDIS_PREFIX}:channel:{channel}", client_id)
        )

    async def channels(self) -> list[dict[str, Any]]:
        channels = sorted(self._text(value) for value in await self.client.smembers(f"{REDIS_PREFIX}:channels"))
        result = []
        for channel in channels:
            count = await self.client.scard(f"{REDIS_PREFIX}:channel:{channel}")
            if count:
                result.append({"name": channel, "subscriber_count": count})
        return result

    async def subscriber_ids(self, channel: str) -> list[str]:
        values = await self.client.smembers(f"{REDIS_PREFIX}:channel:{channel}")
        return sorted(self._text(value) for value in values)

    async def count(self) -> int:
        return int(await self.client.scard(f"{REDIS_PREFIX}:clients"))

    async def rate_limit_exceeded(self, client_id: str, limit: int) -> bool:
        key = f"{REDIS_PREFIX}:rate_limit:{client_id}"
        count = int(await self.client.incr(key))
        if count == 1:
            await self.client.expire(key, RATE_LIMIT_WINDOW_SECONDS)
        return count > limit


class ClientRegistry:
    """A registry safe to inspect or mutate from multiple threads."""

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def add(self, client: Any) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = client
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in list(self._channels):
                subscribers = self._channels[channel]
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[channel]

    def get(self, client_id: str) -> Any | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> list[tuple[str, Any]]:
        with self._lock:
            return list(self._clients.items())

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    def channel_snapshot(self, channel: str) -> list[tuple[str, Any]]:
        with self._lock:
            subscriber_ids = self._channels.get(channel, set())
            return [
                (client_id, client)
                for client_id, client in self._clients.items()
                if client_id in subscriber_ids
            ]

    def channels(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"name": name, "subscriber_count": len(subscribers)}
                for name, subscribers in sorted(self._channels.items())
            ]

    def subscriber_ids(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    def is_subscribed(self, client_id: str, channel: str) -> bool:
        with self._lock:
            return client_id in self._channels.get(channel, set())

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._clients)


class BaseTransport(ABC):
    """Interface between notification routing and a client transport."""

    def __init__(self, notification_server: NotificationServer) -> None:
        self.notification_server = notification_server

    async def start(self) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError

    async def serve_forever(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def on_connect(self, client: Any) -> str:
        """Register a newly connected client and return its identifier."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Remove a disconnected client."""

    @abstractmethod
    async def send_message(self, client: Any, outgoing: dict[str, Any]) -> None:
        """Send one notification to one transport client."""

    @abstractmethod
    async def broadcast(
        self, outgoing: dict[str, Any], channel: str | None = None
    ) -> None:
        """Send one notification to all matching local clients."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport interface."""

    def __init__(
        self, notification_server: NotificationServer, host: str, port: int
    ) -> None:
        super().__init__(notification_server)
        self.host = host
        self.port = port
        self.server: Server | None = None

    async def start(self) -> None:
        self.server = await serve(self.handle_connection, self.host, self.port)
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            self.server = None

    async def serve_forever(self) -> None:
        if self.server is None:
            raise RuntimeError("transport is not started")
        async with self.server:
            await self.server.serve_forever()

    async def handle_connection(self, websocket: ServerConnection) -> None:
        client_id = await self.on_connect(websocket)
        try:
            async for raw_message in websocket:
                await self.notification_server._handle_message(
                    client_id, websocket, raw_message
                )
        except ConnectionClosed:
            pass
        finally:
            await self.on_disconnect(client_id)

    async def on_connect(self, client: Any) -> str:
        client_id = self.notification_server.clients.add(client)
        await self.notification_server.state.add_client(
            client_id, self.notification_server.instance_id
        )
        await self.send_message(
            client,
            message("system", {"event": "connected", "client_id": client_id}),
        )
        return client_id

    async def on_disconnect(self, client_id: str) -> None:
        self.notification_server.clients.remove(client_id)
        await self.notification_server.state.remove_client(client_id)

    async def send_message(self, client: Any, outgoing: dict[str, Any]) -> None:
        await client.send(json.dumps(outgoing, separators=(",", ":")))

    async def broadcast(
        self, outgoing: dict[str, Any], channel: str | None = None
    ) -> None:
        registry = self.notification_server.clients
        clients = registry.snapshot() if channel is None else registry.channel_snapshot(channel)
        if not clients:
            return
        results = await asyncio.gather(
            *(self.send_message(client, outgoing) for _, client in clients),
            return_exceptions=True,
        )
        for (client_id, _), result in zip(clients, results):
            if isinstance(result, ConnectionClosed):
                await self.on_disconnect(client_id)


TRANSPORTS: dict[str, type[BaseTransport]] = {"websocket": WebSocketTransport}


class NotificationServer:
    def __init__(
        self,
        host: str = "127.0.0.1",
        websocket_port: int = 8765,
        soap_port: int = 8080,
        redis_url: str | None = None,
        database_url: str | None = None,
        redis_client: Redis | None = None,
        rate_limit: int | None = None,
        message_ttl_days: int | None = None,
    ) -> None:
        self.host = host
        self.websocket_port = websocket_port
        self.soap_port = soap_port
        self.clients = ClientRegistry()
        self.instance_id = str(uuid.uuid4())
        self.redis_url = redis_url or os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
        self.database_url = database_url or os.environ.get("DATABASE_URL", "sqlite:///messages.db")
        self.rate_limit = self._positive_setting(
            rate_limit, "RATE_LIMIT", DEFAULT_RATE_LIMIT
        )
        self.message_ttl_days = self._positive_setting(
            message_ttl_days, "MESSAGE_TTL_DAYS", DEFAULT_MESSAGE_TTL_DAYS
        )
        self.redis = redis_client or redis.from_url(self.redis_url)
        self._owns_redis = redis_client is None
        self.state = RedisState(self.redis)
        self.messages = MessageStore(self.database_url)
        transport_name = os.environ.get("TRANSPORT", "websocket").strip().lower()
        try:
            transport_class = TRANSPORTS[transport_name]
        except KeyError as error:
            raise ValueError(f"unsupported transport: {transport_name}") from error
        self.transport = transport_class(self, self.host, self.websocket_port)
        self._websocket_server: Server | None = None
        self._soap_server: asyncio.Server | None = None
        self._pubsub: PubSub | None = None
        self._worker: asyncio.Task[None] | None = None
        self._cleanup_worker: asyncio.Task[None] | None = None

    @staticmethod
    def _positive_setting(value: int | None, name: str, default: int) -> int:
        if value is None:
            try:
                value = int(os.environ.get(name, str(default)))
            except ValueError as error:
                raise ValueError(f"{name} must be a positive integer") from error
        if value <= 0:
            raise ValueError(f"{name} must be a positive integer")
        return value

    async def start(self) -> None:
        self.messages.open()
        await self._cleanup_expired_messages()
        self._cleanup_worker = asyncio.create_task(self._message_cleanup_worker())
        self._pubsub = self.redis.pubsub()
        await self._pubsub.subscribe(REDIS_CHANNEL)
        self._worker = asyncio.create_task(self._redis_worker())
        await self.transport.start()
        if isinstance(self.transport, WebSocketTransport):
            self._websocket_server = self.transport.server
            self.websocket_port = self.transport.port
        try:
            self._soap_server = await asyncio.start_server(
                self.handle_soap_connection, self.host, self.soap_port
            )
        except BaseException:
            await self.transport.stop()
            self._websocket_server = None
            await self._stop_backends()
            raise

        soap_socket = self._soap_server.sockets[0]
        self.soap_port = soap_socket.getsockname()[1]

    async def stop(self) -> None:
        await self.transport.stop()
        self._websocket_server = None
        if self._soap_server is not None:
            self._soap_server.close()
            await self._soap_server.wait_closed()
            self._soap_server = None
        await asyncio.gather(
            *(self.state.remove_client(client_id) for client_id, _ in self.clients.snapshot())
        )
        await self._stop_backends()

    async def _stop_backends(self) -> None:
        if self._cleanup_worker is not None:
            self._cleanup_worker.cancel()
            await asyncio.gather(self._cleanup_worker, return_exceptions=True)
            self._cleanup_worker = None
        if self._worker is not None:
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)
            self._worker = None
        if self._pubsub is not None:
            await self._pubsub.aclose()
            self._pubsub = None
        if self._owns_redis:
            await self.redis.aclose()
        self.messages.close()

    async def serve_forever(self) -> None:
        await self.start()
        assert self._soap_server is not None
        async with self._soap_server:
            await asyncio.gather(
                self.transport.serve_forever(),
                self._soap_server.serve_forever(),
            )

    async def handle_websocket(self, websocket: ServerConnection) -> None:
        if not isinstance(self.transport, WebSocketTransport):
            raise RuntimeError("WebSocket transport is not selected")
        await self.transport.handle_connection(websocket)

    async def _handle_message(
        self, client_id: str, client: Any, raw_message: str | bytes
    ) -> None:
        if await self.state.rate_limit_exceeded(client_id, self.rate_limit):
            await self._error(
                client,
                f"rate limit exceeded: maximum {self.rate_limit} messages per minute",
            )
            return
        try:
            incoming = json.loads(raw_message)
        except (json.JSONDecodeError, UnicodeDecodeError):
            await self._error(client, "message must be valid JSON")
            return

        if not isinstance(incoming, dict):
            await self._error(client, "message must be a JSON object")
            return
        message_type = incoming.get("type")
        payload = incoming.get("payload")
        if message_type not in SUPPORTED_TYPES or not isinstance(payload, dict):
            await self._error(client, "type and payload are invalid")
            return
        if message_type == "system":
            await self._error(client, "system messages are server-only")
            return

        channel = incoming.get("channel")
        if channel is not None and (not isinstance(channel, str) or not channel.strip()):
            await self._error(client, "channel must be a non-empty string")
            return
        if message_type in {"subscribe", "unsubscribe"}:
            if channel is None:
                await self._error(client, f"{message_type} requires channel")
                return
            if message_type == "subscribe":
                self.clients.subscribe(client_id, channel)
                await self.state.subscribe(client_id, channel)
            else:
                self.clients.unsubscribe(client_id, channel)
                await self.state.unsubscribe(client_id, channel)
            return

        outgoing_payload = dict(payload)
        outgoing_payload["sender_id"] = client_id
        outgoing = message(message_type, outgoing_payload, channel)
        if message_type == "broadcast":
            await self._publish(outgoing, channel=channel)
            return

        target_id = payload.get("client_id")
        if not isinstance(target_id, str):
            await self._error(client, "direct payload requires client_id")
            return
        if not await self.state.client_exists(target_id):
            await self._error(client, "direct message target is not connected")
            return
        if channel is not None and not await self.state.is_subscribed(target_id, channel):
            await self._error(client, "direct message target is not subscribed")
            return
        await self._publish(outgoing, target_id=target_id)

    async def _publish(
        self,
        outgoing: dict[str, Any],
        channel: str | None = None,
        target_id: str | None = None,
    ) -> None:
        message_id = await asyncio.to_thread(self.messages.add, outgoing)
        envelope = {
            "message_id": message_id,
            "channel": channel,
            "target_id": target_id,
            "message": outgoing,
        }
        await self.redis.publish(REDIS_CHANNEL, json.dumps(envelope, separators=(",", ":")))

    async def _cleanup_expired_messages(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.message_ttl_days)
        timestamp = cutoff.isoformat().replace("+00:00", "Z")
        await asyncio.to_thread(self.messages.delete_before, timestamp)

    async def _message_cleanup_worker(self) -> None:
        while True:
            await asyncio.sleep(3600)
            await self._cleanup_expired_messages()

    async def _redis_worker(self) -> None:
        assert self._pubsub is not None
        while True:
            event = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
            if event is None:
                await asyncio.sleep(0.001)
                continue
            try:
                raw = event["data"]
                envelope = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
                outgoing = envelope["message"]
                target_id = envelope.get("target_id")
                channel = envelope.get("channel")
            except (KeyError, TypeError, json.JSONDecodeError):
                continue
            if target_id is not None:
                target = self.clients.get(target_id)
                if target is not None:
                    await self.transport.send_message(target, outgoing)
            else:
                await self.transport.broadcast(outgoing, channel)

    async def broadcast(
        self, outgoing: dict[str, Any], channel: str | None = None
    ) -> None:
        await self.transport.broadcast(outgoing, channel)

    async def _error(self, client: Any, detail: str) -> None:
        await self.transport.send_message(
            client, message("system", {"event": "error", "detail": detail})
        )

    async def handle_soap_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=5)
            if not request_line:
                return
            parts = request_line.decode("ascii", errors="replace").strip().split()
            if len(parts) != 3:
                await self._write_http(writer, HTTPStatus.BAD_REQUEST, b"Bad request")
                return
            method, target, _ = parts
            parsed_target = urlsplit(target)
            path = parsed_target.path
            headers: dict[str, str] = {}
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=5)
                if line in (b"\r\n", b"\n", b""):
                    break
                name, separator, value = line.decode("latin-1").partition(":")
                if not separator:
                    await self._write_http(writer, HTTPStatus.BAD_REQUEST, b"Bad request")
                    return
                headers[name.strip().lower()] = value.strip()

            if method == "GET" and path == "/channels":
                await self._write_json(writer, {"channels": await self.state.channels()})
                return
            if method == "GET" and path == "/messages":
                try:
                    query = parse_qs(parsed_target.query, keep_blank_values=True)
                    limit = int(query.get("limit", ["50"])[0])
                    offset = int(query.get("offset", ["0"])[0])
                    if not 1 <= limit <= 1000 or offset < 0:
                        raise ValueError
                except (ValueError, TypeError):
                    await self._write_json(
                        writer,
                        {"error": "limit must be 1-1000 and offset must be non-negative"},
                        HTTPStatus.BAD_REQUEST,
                    )
                    return
                history = await asyncio.to_thread(self.messages.list, limit, offset)
                await self._write_json(writer, {"messages": history})
                return
            if method == "GET" and path == "/history":
                query = parse_qs(parsed_target.query, keep_blank_values=True)
                channel = query.get("channel", [""])[0]
                since = query.get("since", [""])[0]
                try:
                    limit = int(query.get("limit", ["50"])[0])
                    if not channel or not since or not 1 <= limit <= 1000:
                        raise ValueError
                    parsed_since = datetime.fromisoformat(since.replace("Z", "+00:00"))
                    if parsed_since.tzinfo is None:
                        raise ValueError
                    normalized_since = parsed_since.astimezone(timezone.utc).isoformat().replace(
                        "+00:00", "Z"
                    )
                except (ValueError, TypeError):
                    await self._write_json(
                        writer,
                        {
                            "error": "channel and timezone-aware since are required; "
                            "limit must be 1-1000"
                        },
                        HTTPStatus.BAD_REQUEST,
                    )
                    return
                history, has_more = await asyncio.to_thread(
                    self.messages.history, channel, normalized_since, limit
                )
                await self._write_json(
                    writer, {"messages": history, "has_more": has_more}
                )
                return
            prefix, suffix = "/channels/", "/subscribers"
            if method == "GET" and path.startswith(prefix) and path.endswith(suffix):
                channel = unquote(path[len(prefix) : -len(suffix)])
                if channel and "/" not in channel:
                    await self._write_json(
                        writer,
                        {
                            "channel": channel,
                            "subscribers": await self.state.subscriber_ids(channel),
                        },
                    )
                    return
            if method != "POST" or path != "/health":
                await self._write_http(writer, HTTPStatus.NOT_FOUND, b"Not found")
                return
            try:
                content_length = int(headers.get("content-length", "0"))
            except ValueError:
                await self._write_http(writer, HTTPStatus.BAD_REQUEST, b"Bad request")
                return
            if content_length <= 0 or content_length > 1_000_000:
                await self._write_http(writer, HTTPStatus.BAD_REQUEST, b"Bad request")
                return
            body = await asyncio.wait_for(reader.readexactly(content_length), timeout=5)
            response = await self._soap_health_response(body)
            await self._write_http(writer, HTTPStatus.OK, response, "text/xml; charset=utf-8")
        except (asyncio.IncompleteReadError, asyncio.TimeoutError):
            if not writer.is_closing():
                await self._write_http(writer, HTTPStatus.BAD_REQUEST, b"Bad request")
        finally:
            writer.close()
            await writer.wait_closed()

    async def _soap_health_response(self, body: bytes) -> bytes:
        try:
            root = ElementTree.fromstring(body)
            soap_body = root.find(f"{{{SOAP_ENV}}}Body")
            operation = next(iter(soap_body)) if soap_body is not None else None
            operation_name = operation.tag.rsplit("}", 1)[-1] if operation is not None else ""
            if operation_name != "Health":
                raise ValueError("unsupported SOAP operation")
        except (ElementTree.ParseError, ValueError):
            return self._soap_fault("Client", "Expected a SOAP Health operation")

        envelope = ElementTree.Element(f"{{{SOAP_ENV}}}Envelope")
        response_body = ElementTree.SubElement(envelope, f"{{{SOAP_ENV}}}Body")
        health = ElementTree.SubElement(response_body, f"{{{SERVICE_NS}}}HealthResponse")
        count = ElementTree.SubElement(health, f"{{{SERVICE_NS}}}connectedClientCount")
        count.text = str(await self.state.count())
        return ElementTree.tostring(envelope, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def _soap_fault(code: str, text: str) -> bytes:
        envelope = ElementTree.Element(f"{{{SOAP_ENV}}}Envelope")
        body = ElementTree.SubElement(envelope, f"{{{SOAP_ENV}}}Body")
        fault = ElementTree.SubElement(body, f"{{{SOAP_ENV}}}Fault")
        ElementTree.SubElement(fault, "faultcode").text = code
        ElementTree.SubElement(fault, "faultstring").text = text
        return ElementTree.tostring(envelope, encoding="utf-8", xml_declaration=True)

    @staticmethod
    async def _write_json(
        writer: asyncio.StreamWriter,
        value: Any,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        body = json.dumps(value, separators=(",", ":")).encode()
        await NotificationServer._write_http(
            writer, status, body, "application/json; charset=utf-8"
        )

    @staticmethod
    async def _write_http(
        writer: asyncio.StreamWriter,
        status: HTTPStatus,
        body: bytes,
        content_type: str = "text/plain; charset=utf-8",
    ) -> None:
        headers = (
            f"HTTP/1.1 {status.value} {status.phrase}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        writer.write(headers + body)
        await writer.drain()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--websocket-port", type=int, default=8765)
    parser.add_argument("--soap-port", type=int, default=8080)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = NotificationServer(args.host, args.websocket_port, args.soap_port)
    asyncio.run(server.serve_forever())


if __name__ == "__main__":
    main()
