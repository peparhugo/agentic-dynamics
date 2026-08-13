"""Async WebSocket notification server."""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

import websockets
from redis import asyncio as redis_asyncio
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Response

SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
REDIS_MESSAGE_CHANNEL = "notifications:messages"
REDIS_CLIENTS_KEY = "notifications:clients"
REDIS_CHANNELS_KEY = "notifications:channels"


async def close_async_resource(resource: Any) -> None:
    close = getattr(resource, "aclose", None) or resource.close
    result = close()
    if inspect.isawaitable(result):
        await result


class MessageStore:
    """SQLite-backed message history."""

    def __init__(self, database_url: str | None = None) -> None:
        database_url = database_url or os.getenv("DATABASE_URL", ":memory:")
        path = (
            database_url[len("sqlite:///") :]
            if database_url.startswith("sqlite:///")
            else database_url
        )
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._connection:
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

    def add(self, message: dict[str, Any]) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                INSERT INTO messages (channel, type, payload, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (
                    message.get("channel"),
                    message["type"],
                    json.dumps(message["payload"]),
                    message["timestamp"],
                ),
            )
            return int(cursor.lastrowid)

    def list(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT id, channel, type, payload, timestamp
                FROM messages ORDER BY id ASC LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "channel": row["channel"],
                "type": row["type"],
                "payload": json.loads(row["payload"]),
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._connection.close()


class ClientRegistry:
    """Thread-safe mapping of client IDs to WebSocket connections."""

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def add(self, websocket: Any) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = websocket
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
            if client_id in self._clients:
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
                (client_id, self._clients[client_id])
                for client_id in subscriber_ids
                if client_id in self._clients
            ]

    def channels(self) -> dict[str, int]:
        with self._lock:
            return {
                channel: len(subscribers)
                for channel, subscribers in sorted(self._channels.items())
                if subscribers
            }

    def subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._clients)


class NotificationServer:
    def __init__(
        self,
        redis_url: str | None = None,
        database_url: str | None = None,
        redis_client: Any | None = None,
    ) -> None:
        self.clients = ClientRegistry()
        self.messages = MessageStore(database_url)
        self.server_id = str(uuid.uuid4())
        self.redis = redis_client
        self._owns_redis = False
        configured_redis_url = redis_url or os.getenv("REDIS_URL")
        if self.redis is None and configured_redis_url:
            self.redis = redis_asyncio.from_url(
                configured_redis_url, decode_responses=True
            )
            self._owns_redis = True
        self._subscriber_task: asyncio.Task[Any] | None = None
        self._subscriber_ready = asyncio.Event()
        self._lifecycle_lock = asyncio.Lock()

    @staticmethod
    def message(
        message_type: str,
        payload: dict[str, Any],
        channel: str | None = None,
    ) -> dict[str, Any]:
        message = {
            "type": message_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if channel is not None:
            message["channel"] = channel
        return message

    async def send(
        self,
        websocket: Any,
        message_type: str,
        payload: dict[str, Any],
        channel: str | None = None,
    ) -> None:
        await websocket.send(json.dumps(self.message(message_type, payload, channel)))

    @staticmethod
    def _client_channels_key(client_id: str) -> str:
        return f"notifications:client:{client_id}:channels"

    @staticmethod
    def _channel_clients_key(channel: str) -> str:
        return f"notifications:channel:{channel}:clients"

    async def _start_subscriber(self) -> None:
        if self.redis is None or self._subscriber_task is not None:
            return
        async with self._lifecycle_lock:
            if self._subscriber_task is None:
                self._subscriber_ready.clear()
                self._subscriber_task = asyncio.create_task(self._subscriber_worker())
                await self._subscriber_ready.wait()

    async def _stop_subscriber(self) -> None:
        if self._subscriber_task is None:
            return
        async with self._lifecycle_lock:
            task = self._subscriber_task
            self._subscriber_task = None
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _subscriber_worker(self) -> None:
        pubsub = self.redis.pubsub()
        try:
            await pubsub.subscribe(REDIS_MESSAGE_CHANNEL)
            self._subscriber_ready.set()
            async for event in pubsub.listen():
                if event["type"] != "message":
                    continue
                data = event["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                await self._deliver_event(json.loads(data))
        finally:
            self._subscriber_ready.set()
            await close_async_resource(pubsub)

    async def _deliver_event(self, event: dict[str, Any]) -> None:
        target = event["target"]
        message = event["message"]
        if target["kind"] == "direct":
            recipient = self.clients.get(target["client_id"])
            clients = [] if recipient is None else [(target["client_id"], recipient)]
        elif target["kind"] == "channel":
            clients = self.clients.channel_snapshot(target["channel"])
        else:
            clients = self.clients.snapshot()
        if not clients:
            return
        encoded = json.dumps(message)
        results = await asyncio.gather(
            *(websocket.send(encoded) for _, websocket in clients),
            return_exceptions=True,
        )
        for (client_id, _), result in zip(clients, results):
            if isinstance(result, ConnectionClosed):
                await self._remove_client(client_id)

    async def _publish(
        self, message: dict[str, Any], target: dict[str, Any]
    ) -> None:
        self.messages.add(message)
        if self.redis is None:
            await self._deliver_event({"message": message, "target": target})
            return
        await self.redis.publish(
            REDIS_MESSAGE_CHANNEL,
            json.dumps({"message": message, "target": target}),
        )

    async def _add_client(self, websocket: Any) -> str:
        await self._start_subscriber()
        client_id = self.clients.add(websocket)
        if self.redis is not None:
            await self.redis.hset(REDIS_CLIENTS_KEY, client_id, self.server_id)
        return client_id

    async def _remove_client(self, client_id: str) -> None:
        self.clients.remove(client_id)
        if self.redis is not None:
            channel_key = self._client_channels_key(client_id)
            channels = await self.redis.smembers(channel_key)
            if channels:
                pipeline = self.redis.pipeline()
                for channel in channels:
                    pipeline.srem(self._channel_clients_key(channel), client_id)
                pipeline.delete(channel_key)
                pipeline.hdel(REDIS_CLIENTS_KEY, client_id)
                await pipeline.execute()
                await self._remove_empty_channels(channels)
            else:
                await self.redis.hdel(REDIS_CLIENTS_KEY, client_id)

    async def _remove_empty_channels(self, channels: Any) -> None:
        for channel in channels:
            if not await self.redis.exists(self._channel_clients_key(channel)):
                await self.redis.srem(REDIS_CHANNELS_KEY, channel)

    async def _subscribe(self, client_id: str, channel: str) -> None:
        self.clients.subscribe(client_id, channel)
        if self.redis is not None:
            pipeline = self.redis.pipeline()
            pipeline.sadd(self._client_channels_key(client_id), channel)
            pipeline.sadd(self._channel_clients_key(channel), client_id)
            pipeline.sadd(REDIS_CHANNELS_KEY, channel)
            await pipeline.execute()

    async def _unsubscribe(self, client_id: str, channel: str) -> None:
        self.clients.unsubscribe(client_id, channel)
        if self.redis is not None:
            pipeline = self.redis.pipeline()
            pipeline.srem(self._client_channels_key(client_id), channel)
            pipeline.srem(self._channel_clients_key(channel), client_id)
            await pipeline.execute()
            await self._remove_empty_channels([channel])

    async def broadcast(
        self,
        payload: dict[str, Any],
        channel: str | None = None,
    ) -> None:
        message = self.message("broadcast", payload, channel)
        await self._publish(
            message,
            {"kind": "global"} if channel is None else {"kind": "channel", "channel": channel},
        )

    async def direct(self, recipient_id: str, payload: dict[str, Any]) -> bool:
        exists = self.clients.get(recipient_id) is not None
        if self.redis is not None:
            exists = bool(await self.redis.hexists(REDIS_CLIENTS_KEY, recipient_id))
        if not exists:
            return False
        await self._publish(
            self.message("direct", payload),
            {"kind": "direct", "client_id": recipient_id},
        )
        return True

    async def handle_message(self, websocket: Any, client_id: str, raw: str) -> None:
        try:
            message = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            await self.send(websocket, "system", {"error": "invalid JSON"})
            return

        if not isinstance(message, dict):
            await self.send(websocket, "system", {"error": "message must be an object"})
            return
        message_type = message.get("type")
        payload = message.get("payload")
        channel = message.get("channel")
        if message_type not in SUPPORTED_TYPES or (
            message_type not in {"subscribe", "unsubscribe"}
            and not isinstance(payload, dict)
        ):
            await self.send(
                websocket,
                "system",
                {"error": "message requires a supported type and object payload"},
            )
            return

        if message_type in {"subscribe", "unsubscribe"}:
            if not isinstance(channel, str) or not channel:
                await self.send(
                    websocket,
                    "system",
                    {"error": f"{message_type} requires a non-empty channel"},
                )
            elif message_type == "subscribe":
                await self._subscribe(client_id, channel)
            else:
                await self._unsubscribe(client_id, channel)
            return

        if channel is not None and (not isinstance(channel, str) or not channel):
            await self.send(
                websocket,
                "system",
                {"error": "channel must be a non-empty string"},
            )
            return

        if message_type == "broadcast":
            await self.broadcast(payload, channel)
        elif message_type == "direct":
            recipient_id = payload.get("client_id")
            content = payload.get("message")
            if not isinstance(recipient_id, str) or not isinstance(content, dict):
                await self.send(
                    websocket,
                    "system",
                    {"error": "direct payload requires client_id and message object"},
                )
            elif not await self.direct(recipient_id, content):
                await self.send(websocket, "system", {"error": "client not found"})
        else:
            await self.send(
                websocket,
                "system",
                {"error": "system messages are generated by the server"},
            )

    async def handler(self, websocket: Any) -> None:
        client_id = await self._add_client(websocket)
        try:
            await self.send(websocket, "system", {"client_id": client_id})
            async for raw in websocket:
                await self.handle_message(websocket, client_id, raw)
        except ConnectionClosed:
            pass
        finally:
            await self._remove_client(client_id)
            if self.clients.count == 0:
                await self._stop_subscriber()

    async def process_request(self, path: str, request_headers: Any) -> Any:
        modern_api = not isinstance(path, str)
        request_target = path if not modern_api else request_headers.path
        parsed = urlsplit(request_target)
        request_path = parsed.path
        if request_path == "/health":
            count = self.clients.count
            if self.redis is not None:
                count = int(await self.redis.hlen(REDIS_CLIENTS_KEY))
            response = {"connected_clients": count}
        elif request_path == "/channels":
            channels = self.clients.channels()
            if self.redis is not None:
                names = sorted(await self.redis.smembers(REDIS_CHANNELS_KEY))
                channels = {
                    name: int(await self.redis.scard(self._channel_clients_key(name)))
                    for name in names
                }
                channels = {name: count for name, count in channels.items() if count}
            response = {"channels": channels}
        elif request_path.startswith("/channels/") and request_path.endswith("/subscribers"):
            encoded_name = request_path[len("/channels/") : -len("/subscribers")].rstrip("/")
            if not encoded_name:
                return None
            channel = unquote(encoded_name)
            subscribers = self.clients.subscribers(channel)
            if self.redis is not None:
                subscribers = sorted(
                    await self.redis.smembers(self._channel_clients_key(channel))
                )
            response = {
                "channel": channel,
                "subscribers": subscribers,
            }
        elif request_path == "/messages":
            try:
                query = parse_qs(parsed.query)
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
                if not 1 <= limit <= 1000 or offset < 0:
                    raise ValueError
            except (TypeError, ValueError):
                return self._json_response(
                    {"error": "limit must be 1-1000 and offset must be non-negative"},
                    HTTPStatus.BAD_REQUEST,
                    modern_api,
                )
            response = {"messages": self.messages.list(limit, offset)}
        else:
            return None
        return self._json_response(response, modern_api=modern_api)

    @staticmethod
    def _json_response(
        response: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
        modern_api: bool = False,
    ) -> Any:
        body = json.dumps(response).encode("utf-8")
        headers = [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
        if modern_api:
            return Response(status.value, status.phrase, Headers(headers), body)
        return (
            status,
            headers,
            body,
        )

    async def close(self) -> None:
        await self._stop_subscriber()
        if self._owns_redis and self.redis is not None:
            await close_async_resource(self.redis)
        self.messages.close()


async def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = NotificationServer()
    try:
        async with websockets.serve(
            server.handler,
            host,
            port,
            process_request=server.process_request,
        ):
            await asyncio.Future()
    finally:
        await server.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    asyncio.run(serve(args.host, args.port))


if __name__ == "__main__":
    main()
