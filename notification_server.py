"""Async WebSocket notification server with a small health endpoint."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import parse_qs, unquote, urlsplit

import websockets
from redis.asyncio import Redis
from websockets.exceptions import ConnectionClosed


LOGGER = logging.getLogger(__name__)
SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


def make_message(message_type: str, payload: dict[str, Any], channel: str | None = None) -> dict[str, Any]:
    """Create a message with the wire format used by the server."""
    if message_type not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported message type: {message_type}")
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    message = {
        "type": message_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if channel is not None:
        message["channel"] = channel
    return message


class ClientRegistry:
    """Maps generated client IDs to sockets and serializes registry changes."""

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    async def add(self, websocket: Any) -> str:
        client_id = str(uuid.uuid4())
        async with self._lock:
            self._clients[client_id] = websocket
        return client_id

    async def remove(self, client_id: str) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)
            for name in list(self._channels):
                subscribers = self._channels[name]
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[name]

    async def count(self) -> int:
        async with self._lock:
            return len(self._clients)

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            return dict(self._clients)

    async def get(self, client_id: str) -> Any | None:
        async with self._lock:
            return self._clients.get(client_id)

    async def subscribe(self, client_id: str, channel: str) -> bool:
        async with self._lock:
            if client_id not in self._clients:
                return False
            subscribers = self._channels.setdefault(channel, set())
            was_new = client_id not in subscribers
            subscribers.add(client_id)
            return was_new

    async def unsubscribe(self, client_id: str, channel: str) -> bool:
        async with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None or client_id not in subscribers:
                return False
            subscribers.remove(client_id)
            if not subscribers:
                del self._channels[channel]
            return True

    async def channel_clients(self, channel: str) -> dict[str, Any]:
        async with self._lock:
            return {
                client_id: self._clients[client_id]
                for client_id in self._channels.get(channel, set())
                if client_id in self._clients
            }

    async def channel_subscribers(self) -> dict[str, list[str]]:
        async with self._lock:
            return {
                name: sorted(client_id for client_id in subscribers if client_id in self._clients)
                for name, subscribers in self._channels.items()
                if any(client_id in self._clients for client_id in subscribers)
            }


class BaseTransport(ABC):
    """Transport contract used by the notification core."""

    def __init__(self, server: "NotificationServer") -> None:
        self.server = server

    @abstractmethod
    async def on_connect(self, connection: Any) -> str:
        """Register a newly connected client and return its client ID."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Remove a client from the transport."""

    @abstractmethod
    async def send_message(self, client_id: str, message: dict[str, Any]) -> None:
        """Send a message to one client."""

    @abstractmethod
    async def broadcast(
        self, message: dict[str, Any], client_ids: Iterable[str] | None = None
    ) -> None:
        """Send a message to all clients, or to the supplied client IDs."""

    async def start(self) -> None:
        """Start the transport listener, if it has one."""

    async def stop(self) -> None:
        """Stop the transport listener, if it has one."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport contract."""

    def __init__(self, server: "NotificationServer") -> None:
        super().__init__(server)
        self._server: Any | None = None

    async def on_connect(self, connection: Any) -> str:
        return await self.server.clients.add(connection)

    async def on_disconnect(self, client_id: str) -> None:
        await self.server.clients.remove(client_id)

    async def send_message(self, client_id: str, message: dict[str, Any]) -> None:
        connection = await self.server.clients.get(client_id)
        if connection is not None:
            await connection.send(json.dumps(message))

    async def broadcast(
        self, message: dict[str, Any], client_ids: Iterable[str] | None = None
    ) -> None:
        clients = await self.server.clients.snapshot()
        selected = set(client_ids) if client_ids is not None else set(clients)
        encoded = json.dumps(message)
        results = await asyncio.gather(
            *(clients[client_id].send(encoded) for client_id in selected if client_id in clients),
            return_exceptions=True,
        )
        for client_id, result in zip(
            (client_id for client_id in selected if client_id in clients), results
        ):
            if isinstance(result, Exception):
                await self.on_disconnect(client_id)

    async def start(self) -> None:
        self._server = await websockets.serve(
            self._handle_connection, self.server.host, self.server.websocket_port
        )
        self.server._websocket_server = self._server

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            self.server._websocket_server = None

    async def _handle_connection(self, websocket: Any, *_: Any) -> None:
        client_id = await self.on_connect(websocket)
        await self.server._store_client_state(client_id, [])
        try:
            welcome = make_message("system", {"client_id": client_id})
            await self.server._save_message(welcome)
            await self.send_message(client_id, welcome)
            async for raw_message in websocket:
                await self.server._handle_message(client_id, raw_message)
        except (ConnectionClosed, asyncio.CancelledError):
            raise
        except Exception:
            LOGGER.exception("WebSocket client %s failed", client_id)
        finally:
            await self.on_disconnect(client_id)
            await self.server._remove_client_state(client_id)


class NotificationServer:
    """WebSocket notification server backed by Redis and SQLite."""

    def __init__(self, host: str = "127.0.0.1", websocket_port: int = 8765,
                 http_port: int = 8080, redis_url: str | None = None,
                 database_url: str | None = None,
                 transport: BaseTransport | None = None) -> None:
        self.host = host
        self.websocket_port = websocket_port
        self.http_port = http_port
        self.clients = ClientRegistry()
        self.redis_url = redis_url if redis_url is not None else os.getenv("REDIS_URL")
        self.database_url = database_url if database_url is not None else os.getenv(
            "DATABASE_URL", "sqlite:///notifications.db"
        )
        self._database_path = self._sqlite_path(self.database_url)
        self._database = sqlite3.connect(self._database_path, check_same_thread=False)
        self._database.row_factory = sqlite3.Row
        self._database_lock = asyncio.Lock()
        self._redis: Redis | None = None
        self._redis_pubsub: Any | None = None
        self._redis_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None
        self._broker_channel = "notifications:messages"
        try:
            self.rate_limit = max(0, int(os.getenv("RATE_LIMIT", "100")))
            self.message_ttl_days = max(0, float(os.getenv("MESSAGE_TTL_DAYS", "7")))
        except ValueError as exc:
            raise ValueError("RATE_LIMIT and MESSAGE_TTL_DAYS must be numeric") from exc
        self._local_rate_counters: dict[tuple[str, int], int] = {}
        self._websocket_server: Any | None = None
        self._http_server: asyncio.AbstractServer | None = None
        if transport is not None:
            self.transport = transport
        else:
            transport_name = os.getenv("TRANSPORT", "websocket").strip().lower()
            if transport_name != "websocket":
                raise ValueError(f"unsupported transport: {transport_name}")
            self.transport = WebSocketTransport(self)

    @staticmethod
    def _sqlite_path(database_url: str) -> str:
        if database_url.startswith("sqlite:///"):
            return database_url[10:]
        if database_url.startswith("sqlite://"):
            return database_url[9:]
        return database_url

    async def _init_database(self) -> None:
        async with self._database_lock:
            self._database.execute(
                "CREATE TABLE IF NOT EXISTS messages ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, type TEXT NOT NULL, "
                "payload TEXT NOT NULL, timestamp TEXT NOT NULL)"
            )
            self._database.commit()

    async def _cleanup_expired_messages(self) -> None:
        cutoff = datetime.now(timezone.utc).timestamp() - self.message_ttl_days * 86400
        async with self._database_lock:
            self._database.execute(
                "DELETE FROM messages WHERE timestamp < ?",
                (datetime.fromtimestamp(cutoff, timezone.utc).isoformat(),),
            )
            self._database.commit()

    async def _cleanup_loop(self) -> None:
        interval = max(1.0, min(3600.0, self.message_ttl_days * 8640.0))
        while True:
            await asyncio.sleep(interval)
            await self._cleanup_expired_messages()

    async def _save_message(self, message: dict[str, Any]) -> None:
        async with self._database_lock:
            self._database.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (message.get("channel"), message["type"], json.dumps(message["payload"]), message["timestamp"]),
            )
            self._database.commit()

    async def _messages(self, limit: int, offset: int) -> list[dict[str, Any]]:
        async with self._database_lock:
            rows = self._database.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        return [
            {"id": row["id"], "channel": row["channel"], "type": row["type"],
             "payload": json.loads(row["payload"]), "timestamp": row["timestamp"]}
            for row in rows
        ]

    async def _history(self, channel: str, since: str | None, limit: int) -> tuple[list[dict[str, Any]], bool]:
        query = (
            "SELECT id, channel, type, payload, timestamp FROM messages "
            "WHERE channel = ?"
        )
        parameters: list[Any] = [channel]
        if since is not None:
            query += " AND timestamp >= ?"
            parameters.append(since)
        query += " ORDER BY timestamp ASC, id ASC LIMIT ?"
        parameters.append(limit + 1)
        async with self._database_lock:
            rows = self._database.execute(query, parameters).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        return ([
            {"id": row["id"], "channel": row["channel"], "type": row["type"],
             "payload": json.loads(row["payload"]), "timestamp": row["timestamp"]}
            for row in rows
        ], has_more)

    async def _check_rate_limit(self, client_id: str) -> bool:
        if self.rate_limit == 0:
            return True
        bucket = int(time.time() // 60)
        key = f"notifications:rate:{client_id}:{bucket}"
        if self._redis is not None:
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, 60)
        else:
            counter_key = (client_id, bucket)
            self._local_rate_counters[counter_key] = self._local_rate_counters.get(counter_key, 0) + 1
            self._local_rate_counters = {
                item: value for item, value in self._local_rate_counters.items() if item[1] >= bucket
            }
            count = self._local_rate_counters[counter_key]
        return count <= self.rate_limit

    async def _publish(self, message: dict[str, Any]) -> None:
        if self._redis is None:
            await self._deliver(message)
        else:
            await self._redis.publish(self._broker_channel, json.dumps(message))

    async def _redis_listener(self) -> None:
        assert self._redis_pubsub is not None
        async for item in self._redis_pubsub.listen():
            if item["type"] == "message":
                await self._deliver(json.loads(item["data"]))

    async def _deliver(self, message: dict[str, Any]) -> None:
        channel = message.get("channel")
        if message.get("type") == "direct":
            recipient_id = message.get("payload", {}).get("client_id") or message.get("payload", {}).get("recipient_id")
            recipient = await self.clients.get(recipient_id) if isinstance(recipient_id, str) else None
            clients = {recipient_id: recipient} if recipient is not None else {}
        else:
            clients = (await self.clients.channel_clients(channel)
                       if isinstance(channel, str) else await self.clients.snapshot())
        if clients:
            await self.transport.broadcast(message, clients)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a message to all clients, or only subscribers of its channel."""
        await self._save_message(message)
        await self._publish(message)

    async def broadcast_payload(self, payload: dict[str, Any]) -> None:
        await self.broadcast(make_message("broadcast", payload))

    async def _handle_websocket(self, websocket: Any, *_: Any) -> None:
        await self.transport._handle_connection(websocket, *_)  # type: ignore[attr-defined]

    async def _store_client_state(self, client_id: str, channels: list[str]) -> None:
        if self._redis is not None:
            await self._redis.hset(
                f"notifications:client:{client_id}",
                mapping={"connected": "1", "channels": json.dumps(channels)},
            )

    async def _remove_client_state(self, client_id: str) -> None:
        if self._redis is not None:
            state = await self._redis.hget(f"notifications:client:{client_id}", "channels")
            if state:
                for channel in json.loads(state):
                    await self._redis.srem(f"notifications:channel:{channel}", client_id)
            await self._redis.delete(f"notifications:client:{client_id}")

    async def _shared_subscribers(self, channel: str) -> list[str] | None:
        if self._redis is None:
            return None
        return sorted(await self._redis.smembers(f"notifications:channel:{channel}"))

    async def _handle_message(self, sender_id: str, raw_message: str) -> None:
        if not await self._check_rate_limit(sender_id):
            await self.transport.send_message(
                sender_id, make_message("system", {"error": "rate limit exceeded"})
            )
            return
        try:
            message = json.loads(raw_message)
            message_type = message["type"]
            payload = message.get("payload", {})
            if message_type not in SUPPORTED_TYPES or not isinstance(payload, dict):
                raise ValueError
            channel = message.get("channel", payload.get("channel"))
            if channel is not None and (not isinstance(channel, str) or not channel.strip()):
                raise ValueError
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            sender = await self.clients.get(sender_id)
            if sender is not None:
                await self.transport.send_message(
                    sender_id, make_message("system", {"error": "invalid message"})
                )
            return

        if message_type in {"subscribe", "unsubscribe"}:
            if not isinstance(channel, str):
                await self._send_error(sender_id)
                return
            if message_type == "subscribe":
                await self.clients.subscribe(sender_id, channel)
                if self._redis is not None:
                    await self._redis.sadd(f"notifications:channel:{channel}", sender_id)
            else:
                await self.clients.unsubscribe(sender_id, channel)
                if self._redis is not None:
                    await self._redis.srem(f"notifications:channel:{channel}", sender_id)
            if self._redis is not None:
                channels = await self.clients.channel_subscribers()
                await self._store_client_state(sender_id, [name for name, ids in channels.items() if sender_id in ids])
            return

        outgoing = make_message(message_type, payload, channel)
        if message_type == "broadcast" or message_type == "system":
            await self.broadcast(outgoing)
            return

        recipient_id = payload.get("client_id") or payload.get("recipient_id")
        recipient = await self.clients.get(recipient_id) if isinstance(recipient_id, str) else None
        if isinstance(channel, str):
            subscribed = await self.clients.channel_clients(channel)
            if recipient_id not in subscribed:
                recipient = None
        if recipient is not None:
            await self._save_message(outgoing)
            await self._publish(outgoing)

    async def _send_error(self, client_id: str) -> None:
        sender = await self.clients.get(client_id)
        if sender is not None:
            await self.transport.send_message(
                client_id, make_message("system", {"error": "invalid message"})
            )

    async def _handle_http(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = await reader.readline()
            method, path, *_ = request_line.decode("ascii", "replace").split()
            route = urlsplit(path).path
            if method == "GET" and route == "/health":
                body = json.dumps({"connected_clients": await self.clients.count()}).encode()
                status = "200 OK"
            elif method == "GET" and route == "/channels":
                channels = await self.clients.channel_subscribers()
                if self._redis is not None:
                    names = await self._redis.keys("notifications:channel:*")
                    channels = {
                        name.removeprefix("notifications:channel:"): sorted(
                            await self._redis.smembers(name)
                        )
                        for name in names
                    }
                body = json.dumps({"channels": {name: len(ids) for name, ids in channels.items()}}).encode()
                status = "200 OK"
            elif method == "GET" and route.startswith("/channels/") and route.endswith("/subscribers"):
                name = unquote(route[len("/channels/"):-len("/subscribers")].rstrip("/"))
                channels = await self.clients.channel_subscribers()
                subscribers = await self._shared_subscribers(name)
                body = json.dumps({"channel": name, "subscribers": subscribers if subscribers is not None else channels.get(name, [])}).encode()
                status = "200 OK"
            elif method == "GET" and route == "/messages":
                query = parse_qs(urlsplit(path).query)
                try:
                    limit = max(0, min(1000, int(query.get("limit", ["50"])[0])))
                    offset = max(0, int(query.get("offset", ["0"])[0]))
                except (TypeError, ValueError):
                    body = json.dumps({"error": "invalid pagination"}).encode()
                    status = "400 Bad Request"
                else:
                     body = json.dumps({"messages": await self._messages(limit, offset)}).encode()
                     status = "200 OK"
            elif method == "GET" and route == "/history":
                query = parse_qs(urlsplit(path).query)
                channel = query.get("channel", [None])[0]
                since = query.get("since", [None])[0]
                try:
                    limit = max(1, min(1000, int(query.get("limit", ["50"])[0])))
                    if not channel:
                        raise ValueError
                    if since is not None:
                        since = datetime.fromisoformat(since.replace("Z", "+00:00")).isoformat()
                except (TypeError, ValueError):
                    body = json.dumps({"error": "invalid history query"}).encode()
                    status = "400 Bad Request"
                else:
                    messages, has_more = await self._history(channel, since, limit)
                    body = json.dumps({"messages": messages, "has_more": has_more}).encode()
                    status = "200 OK"
            else:
                body = json.dumps({"error": "not found"}).encode()
                status = "404 Not Found"
            headers = (
                f"HTTP/1.1 {status}\r\nContent-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
            ).encode()
            writer.write(headers + body)
            await writer.drain()
        except (ValueError, UnicodeDecodeError):
            writer.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self) -> None:
        await self._init_database()
        await self._cleanup_expired_messages()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        if self.redis_url:
            self._redis = Redis.from_url(self.redis_url, decode_responses=True)
            self._redis_pubsub = self._redis.pubsub()
            await self._redis_pubsub.subscribe(self._broker_channel)
            self._redis_task = asyncio.create_task(self._redis_listener())
        await self.transport.start()
        self._http_server = await asyncio.start_server(
            self._handle_http, self.host, self.http_port
        )

    async def stop(self) -> None:
        await self.transport.stop()
        if self._http_server is not None:
            self._http_server.close()
            await self._http_server.wait_closed()
            self._http_server = None
        if self._redis_task is not None:
            self._redis_task.cancel()
            await asyncio.gather(self._redis_task, return_exceptions=True)
            self._redis_task = None
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            await asyncio.gather(self._cleanup_task, return_exceptions=True)
            self._cleanup_task = None
        if self._redis_pubsub is not None:
            await self._redis_pubsub.close()
            self._redis_pubsub = None
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
        async with self._database_lock:
            self._database.close()

    async def run(self) -> None:
        await self.start()
        try:
            await asyncio.Future()
        finally:
            await self.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(NotificationServer().run())


if __name__ == "__main__":
    main()
