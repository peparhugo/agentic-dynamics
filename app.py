"""Async WebSocket notification server with a small HTTP health endpoint."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

import websockets
import redis.asyncio as redis
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Headers, Response

LOGGER = logging.getLogger(__name__)
MESSAGE_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


def timestamp() -> str:
    """Return an ISO 8601 timestamp that is unambiguous across time zones."""
    return datetime.now(timezone.utc).isoformat()


def make_message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    if message_type not in MESSAGE_TYPES:
        raise ValueError(f"unsupported message type: {message_type}")
    return {"type": message_type, "payload": payload, "timestamp": timestamp()}


class ClientRegistry:
    """A thread-safe mapping of generated client IDs to WebSocket connections."""

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._subscriptions: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def add(self, websocket: Any) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = websocket
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in list(self._subscriptions):
                self._subscriptions[channel].discard(client_id)
                if not self._subscriptions[channel]:
                    del self._subscriptions[channel]

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            self._subscriptions.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._subscriptions.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._subscriptions[channel]

    def get(self, client_id: str) -> Any | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._clients)

    def channel_snapshot(self) -> dict[str, set[str]]:
        with self._lock:
            return {channel: set(subscribers) for channel, subscribers in self._subscriptions.items()}

    def channel_subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._subscriptions.get(channel, set()))

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)


class MessageStore:
    """Small SQLite store kept separate from the asyncio event loop."""

    def __init__(self, url: str | None = None) -> None:
        url = url or os.getenv("DATABASE_URL", "sqlite:///messages.db")
        self.path = url[10:] if url.startswith("sqlite:///") else url
        if self.path == ":memory:":
            self.path = ":memory:"
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, type TEXT NOT NULL, "
            "payload TEXT NOT NULL, timestamp TEXT NOT NULL)"
        )
        self._connection.commit()
        self._lock = threading.RLock()

    def add(self, message: dict[str, Any]) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT INTO messages(channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (message.get("channel"), message["type"], json.dumps(message["payload"]), message["timestamp"]),
            )
            self._connection.commit()

    def list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        return [
            {"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]}
            for row in rows
        ]

    def history(self, channel: str, since: str | None, limit: int) -> tuple[list[dict[str, Any]], bool]:
        with self._lock:
            conditions = ["channel = ?"]
            parameters: list[Any] = [channel]
            if since is not None:
                conditions.append("timestamp >= ?")
                parameters.append(since)
            rows = self._connection.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                f"WHERE {' AND '.join(conditions)} ORDER BY timestamp ASC, id ASC LIMIT ?",
                (*parameters, limit + 1),
            ).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        return ([
            {"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]}
            for row in rows
        ], has_more)

    def delete_older_than(self, cutoff: str) -> None:
        with self._lock:
            self._connection.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff,))
            self._connection.commit()

    def close(self) -> None:
        with self._lock:
            self._connection.close()


class BaseTransport(ABC):
    """Transport contract used by the notification routing code."""

    @abstractmethod
    async def on_connect(self, client_id: str, connection: Any, message: dict[str, Any]) -> None:
        """Handle a newly connected client."""

    @abstractmethod
    async def on_disconnect(self, client_id: str, connection: Any) -> None:
        """Handle a disconnected client."""

    @abstractmethod
    async def send_message(self, connection: Any, message: dict[str, Any]) -> None:
        """Send one message over the transport."""

    @abstractmethod
    async def broadcast(self, connections: list[Any], message: dict[str, Any]) -> None:
        """Send one message to a collection of connections."""

    async def start(
        self,
        on_connect: Callable[[Any], Awaitable[str]],
        on_message: Callable[[str | bytes, str], Awaitable[None]],
        on_disconnect: Callable[[str, Any], Awaitable[None]],
        host: str,
        port: int,
        process_request: Callable[[Any, Any], Awaitable[Response | None]],
    ) -> Any:
        raise NotImplementedError("transport does not provide a server listener")

    async def stop(self, server: Any) -> None:
        if server is not None:
            server.close()
            await server.wait_closed()


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport contract."""

    async def on_connect(self, client_id: str, connection: Any, message: dict[str, Any]) -> None:
        await self.send_message(connection, message)

    async def on_disconnect(self, client_id: str, connection: Any) -> None:
        return None

    async def send_message(self, connection: Any, message: dict[str, Any]) -> None:
        try:
            await connection.send(json.dumps(message))
        except ConnectionClosed:
            pass

    async def broadcast(self, connections: list[Any], message: dict[str, Any]) -> None:
        await asyncio.gather(
            *(self.send_message(connection, message) for connection in connections),
            return_exceptions=True,
        )

    async def start(
        self,
        on_connect: Callable[[Any], Awaitable[str]],
        on_message: Callable[[str | bytes, str], Awaitable[None]],
        on_disconnect: Callable[[str, Any], Awaitable[None]],
        host: str,
        port: int,
        process_request: Callable[[Any, Any], Awaitable[Response | None]],
    ) -> Any:
        async def handler(connection: Any) -> None:
            client_id = await on_connect(connection)
            try:
                async for raw_message in connection:
                    await on_message(raw_message, client_id)
            except ConnectionClosed:
                pass
            finally:
                await on_disconnect(client_id, connection)

        return await websockets.serve(handler, host, port, process_request=process_request)


class NotificationServer:
    """Notification server independent of the underlying transport.

    Clients send JSON messages. ``broadcast`` and ``system`` messages are sent
    to every connected client. A ``direct`` message is sent to the client ID
    in ``payload["client_id"]`` (``target_id`` is accepted as an alias).
    """

    def __init__(self, host: str = "localhost", port: int = 8765, redis_url: str | None = None,
                 database_url: str | None = None, transport: BaseTransport | None = None) -> None:
        self.host = host
        self.port = port
        self.clients = ClientRegistry()
        self._server: Any | None = None
        self._redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis: Any | None = None
        self._pubsub: Any | None = None
        self._broker_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None
        self._server_id = str(uuid.uuid4())
        try:
            self._rate_limit = max(int(os.getenv("RATE_LIMIT", "100")), 0)
        except ValueError:
            self._rate_limit = 100
        try:
            self._message_ttl_days = max(float(os.getenv("MESSAGE_TTL_DAYS", "7")), 0)
        except ValueError:
            self._message_ttl_days = 7
        self._local_rate_counters: dict[tuple[str, int], int] = {}
        self._local_rate_lock = asyncio.Lock()
        self.store = MessageStore(database_url)
        self.transport = transport or self._create_transport()

    @staticmethod
    def _create_transport() -> BaseTransport:
        transport_name = os.getenv("TRANSPORT", "websocket").lower()
        if transport_name in {"websocket", "ws"}:
            return WebSocketTransport()
        raise ValueError(f"unsupported transport: {transport_name}")

    @property
    def broker_channel(self) -> str:
        return "notification:messages"

    @property
    def connected_clients(self) -> int:
        return len(self.clients)

    async def process_request(self, _connection: Any, request: Any) -> Response | None:
        # Let a just-received WebSocket frame finish dispatching before an HTTP
        # status request observes registry state.
        await asyncio.sleep(0.01)
        path = urlsplit(request.path).path
        if path == "/channels":
            channels = {
                name: len(subscribers) for name, subscribers in self.clients.channel_snapshot().items()
            }
            return self._json_response({"channels": channels})
        if path.startswith("/channels/") and path.endswith("/subscribers"):
            name = unquote(path[len("/channels/") : -len("/subscribers")])
            if name and "/" not in name:
                return self._json_response(
                    {"channel": name, "subscribers": self.clients.channel_subscribers(name)}
                )
        if path == "/messages":
            query = parse_qs(urlsplit(request.path).query)
            try:
                limit = min(max(int(query.get("limit", [50])[0]), 1), 1000)
                offset = max(int(query.get("offset", [0])[0]), 0)
            except (TypeError, ValueError):
                return self._json_response({"error": "limit and offset must be integers"}, HTTPStatus.BAD_REQUEST)
            return self._json_response({"messages": self.store.list(limit, offset)})
        if path == "/history":
            query = parse_qs(urlsplit(request.path).query)
            channel = query.get("channel", [None])[0]
            since = query.get("since", [None])[0]
            if not channel:
                return self._json_response({"error": "channel is required"}, HTTPStatus.BAD_REQUEST)
            if since is not None:
                try:
                    parsed_since = datetime.fromisoformat(since.replace("Z", "+00:00"))
                except ValueError:
                    return self._json_response({"error": "since must be an ISO timestamp"}, HTTPStatus.BAD_REQUEST)
                if parsed_since.tzinfo is not None:
                    since = parsed_since.astimezone(timezone.utc).isoformat()
            try:
                limit = min(max(int(query.get("limit", [50])[0]), 1), 1000)
            except (TypeError, ValueError):
                return self._json_response({"error": "limit must be an integer"}, HTTPStatus.BAD_REQUEST)
            messages, has_more = self.store.history(channel, since, limit)
            return self._json_response({"messages": messages, "has_more": has_more})
        if path != "/health":
            return None
        return self._json_response({"status": "ok", "connected_clients": len(self.clients)})

    @staticmethod
    def _json_response(value: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> Response:
        body = json.dumps(value).encode()
        headers = Headers([("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
        return Response(status.value, status.phrase, headers, body)

    async def _connect_broker(self) -> None:
        try:
            if not self._redis_url.startswith(("redis://", "rediss://")):
                raise ValueError("REDIS_URL must use redis:// or rediss://")
            client = redis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
            )
            await client.ping()
            self._redis = client
            self._pubsub = client.pubsub()
            await self._pubsub.subscribe(self.broker_channel)
            self._broker_task = asyncio.create_task(self._broker_loop())
        except Exception as exc:
            LOGGER.warning("Redis unavailable; using local message delivery: %s", exc)
            if self._redis is not None:
                close = getattr(self._redis, "aclose", self._redis.close)
                result = close()
                if result is not None:
                    await result
            self._redis = None

    async def _broker_loop(self) -> None:
        assert self._pubsub is not None
        try:
            async for item in self._pubsub.listen():
                if item.get("type") == "message":
                    await self._deliver(json.loads(item["data"]))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            LOGGER.warning("Redis listener stopped: %s", exc)

    async def _deliver(self, message: dict[str, Any]) -> None:
        channel = message.get("channel")
        if message.get("target_id"):
            target = self.clients.get(message["target_id"])
            if target is not None:
                await self.transport.send_message(target, message["message"])
            return
        await self.broadcast(message["message"], channel)

    async def _publish(self, message: dict[str, Any], target_id: str | None = None) -> None:
        envelope = {"message": message, "channel": message.get("channel"), "target_id": target_id}
        if self._redis is None:
            await self._deliver(envelope)
        else:
            await self._redis.publish(self.broker_channel, json.dumps(envelope))

    async def _allow_message(self, client_id: str) -> bool:
        window = int(time.time() // 60)
        if self._redis is not None:
            key = f"notification:rate:{client_id}:{window}"
            try:
                count = await self._redis.incr(key)
                if count == 1:
                    await self._redis.expire(key, 60)
                return count <= self._rate_limit
            except Exception as exc:
                LOGGER.warning("Redis rate limiter unavailable; using local limiter: %s", exc)
        async with self._local_rate_lock:
            key = (client_id, window)
            self._local_rate_counters[key] = self._local_rate_counters.get(key, 0) + 1
            self._local_rate_counters = {
                counter_key: value for counter_key, value in self._local_rate_counters.items()
                if counter_key[1] >= window
            }
            return self._local_rate_counters[key] <= self._rate_limit

    async def _send_rate_limit_error(self, client_id: str) -> None:
        connection = self.clients.get(client_id)
        if connection is not None:
            await self.transport.send_message(
                connection,
                make_message("system", {"error": "rate limit exceeded", "limit": self._rate_limit}),
            )

    async def _cleanup_loop(self) -> None:
        try:
            while True:
                cutoff = (datetime.now(timezone.utc) - timedelta(days=self._message_ttl_days)).isoformat()
                self.store.delete_older_than(cutoff)
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise

    async def _on_connect(self, connection: Any) -> str:
        client_id = self.clients.add(connection)
        connected = make_message("system", {"event": "connected", "client_id": client_id})
        self.store.add(connected)
        await self.transport.on_connect(client_id, connection, connected)
        if self._redis is not None:
            await self._redis.hset(f"notification:client:{client_id}", mapping={"server": self._server_id})
            await self._redis.expire(f"notification:client:{client_id}", 86400)
        return client_id

    async def _on_disconnect(self, client_id: str, connection: Any) -> None:
        await self.transport.on_disconnect(client_id, connection)
        self.clients.remove(client_id)
        if self._redis is not None:
            await self._redis.delete(f"notification:client:{client_id}")

    async def handle_message(self, raw_message: str | bytes, sender_id: str) -> None:
        if not await self._allow_message(sender_id):
            await self._send_rate_limit_error(sender_id)
            return
        try:
            message = json.loads(raw_message)
            if not isinstance(message, dict):
                raise ValueError("message must be a JSON object")
            message_type = message.get("type")
            payload = message.get("payload")
            if message_type not in MESSAGE_TYPES:
                raise ValueError("message requires a supported type")
            if payload is None:
                payload = {}
            if not isinstance(payload, dict):
                raise ValueError("message payload must be an object")
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            LOGGER.warning("Ignoring invalid message from %s: %s", sender_id, exc)
            return

        channel = message.get("channel", payload.get("channel"))
        if channel is not None and not isinstance(channel, str):
            LOGGER.warning("Ignoring invalid channel from %s", sender_id)
            return

        if message_type in {"subscribe", "unsubscribe"}:
            if not channel:
                LOGGER.warning("Ignoring %s without a channel from %s", message_type, sender_id)
                return
            if message_type == "subscribe":
                self.clients.subscribe(sender_id, channel)
            else:
                self.clients.unsubscribe(sender_id, channel)
            if self._redis is not None:
                key = f"notification:subscriptions:{channel}"
                if message_type == "subscribe":
                    await self._redis.sadd(key, sender_id)
                    await self._redis.expire(key, 86400)
                else:
                    await self._redis.srem(key, sender_id)
            return

        outgoing = make_message(message_type, payload)
        if channel is not None:
            outgoing["channel"] = channel
        if message_type in {"broadcast", "system"}:
            self.store.add(outgoing)
            await self._publish(outgoing)
            return

        target_id = payload.get("client_id", payload.get("target_id"))
        if channel is not None and isinstance(target_id, str):
            if target_id not in self.clients.channel_subscribers(channel):
                return
        target = self.clients.get(target_id) if isinstance(target_id, str) else None
        if target is not None:
            self.store.add(outgoing)
            await self._publish(outgoing, target_id)

    async def broadcast(self, message: dict[str, Any], channel: str | None = None) -> None:
        clients = self.clients.snapshot()
        if channel is not None:
            subscriber_ids = self.clients.channel_subscribers(channel)
            clients = {client_id: clients[client_id] for client_id in subscriber_ids if client_id in clients}
        await self.transport.broadcast(list(clients.values()), message)

    async def start(self) -> Any:
        await self._connect_broker()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._server = await self.transport.start(
            self._on_connect,
            self.handle_message,
            self._on_disconnect,
            self.host,
            self.port,
            self.process_request,
        )
        return self._server

    async def stop(self) -> None:
        if self._server is not None:
            await self.transport.stop(self._server)
            self._server = None
        if self._broker_task is not None:
            self._broker_task.cancel()
            await asyncio.gather(self._broker_task, return_exceptions=True)
            self._broker_task = None
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            await asyncio.gather(self._cleanup_task, return_exceptions=True)
            self._cleanup_task = None
        if self._pubsub is not None:
            await self._pubsub.unsubscribe(self.broker_channel)
            await self._pubsub.close()
            self._pubsub = None
        if self._redis is not None:
            close = getattr(self._redis, "aclose", self._redis.close)
            result = close()
            if result is not None:
                await result
            self._redis = None
        self.store.close()


async def run_server(host: str = "localhost", port: int = 8765) -> None:
    server = NotificationServer(host, port)
    await server.start()
    try:
        await asyncio.Future()
    finally:
        await server.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_server(args.host, args.port))


if __name__ == "__main__":
    main()
