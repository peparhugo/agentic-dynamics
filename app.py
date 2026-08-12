"""Async WebSocket notification server with Redis and SQLite backends."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import websockets
from websockets.exceptions import ConnectionClosed

try:
    import redis.asyncio as redis
except ImportError:  # pragma: no cover - installation is part of deployment
    redis = None


SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
REDIS_CHANNEL = "notifications:messages"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MessageStore:
    """Synchronous SQLite store; its short transactions are safe in the event loop."""

    def __init__(self, url: str | None = None) -> None:
        configured = url or os.getenv("DATABASE_URL", "messages.db")
        if configured.startswith("sqlite://"):
            self.path = urlparse(configured).path or ":memory:"
        else:
            self.path = configured
        if self.path == "sqlite://":
            self.path = ":memory:"
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, type TEXT NOT NULL, "
            "payload TEXT NOT NULL, timestamp TEXT NOT NULL)"
        )
        self.connection.commit()

    def add(self, channel: str | None, message_type: str, payload: dict[str, Any], timestamp: str) -> None:
        self.connection.execute(
            "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
            (channel, message_type, json.dumps(payload), timestamp),
        )
        self.connection.commit()

    def list(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT id, channel, type, payload, timestamp FROM messages "
            "ORDER BY id LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
        return [
            {"id": row["id"], "channel": row["channel"], "type": row["type"],
             "payload": json.loads(row["payload"]), "timestamp": row["timestamp"]}
            for row in rows
        ]

    def close(self) -> None:
        self.connection.close()


class NotificationServer:
    """Manage clients while Redis distributes envelopes between server instances."""

    def __init__(self, host: str = "localhost", port: int = 8765,
                 redis_url: str | None = None, database_url: str | None = None) -> None:
        self.host = host
        self.port = port
        self.redis_url = redis_url if redis_url is not None else os.getenv("REDIS_URL")
        self.instance_id = uuid.uuid4().hex
        self.clients: dict[int, Any] = {}
        self.client_registry = self.clients
        self.channels: dict[str, set[int]] = {}
        self._client_channels: dict[int, set[str]] = {}
        self._lock = asyncio.Lock()
        self._server: Any = None
        self._redis: Any = None
        self._pubsub: Any = None
        self._redis_task: asyncio.Task[Any] | None = None
        self.store = MessageStore(database_url)

    async def start(self) -> None:
        if self.redis_url and redis is not None:
            try:
                self._redis = redis.from_url(self.redis_url, decode_responses=True)
                await self._redis.ping()
                self._pubsub = self._redis.pubsub()
                await self._pubsub.subscribe(REDIS_CHANNEL)
                self._redis_task = asyncio.create_task(self._redis_loop())
            except Exception:
                await self._close_redis()
        self._server = await websockets.serve(
            self._handle_connection, self.host, self.port, process_request=self._process_request
        )
        if self._server.sockets:
            self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._redis_task is not None:
            self._redis_task.cancel()
            await asyncio.gather(self._redis_task, return_exceptions=True)
            self._redis_task = None
        await self._close_redis()
        async with self._lock:
            connections = list(self.clients.values())
            self.clients.clear()
            self.channels.clear()
            self._client_channels.clear()
        await asyncio.gather(*(self._close(connection) for connection in connections))
        self.store.close()

    async def _close_redis(self) -> None:
        for resource in (self._pubsub, self._redis):
            if resource is not None:
                try:
                    result = resource.close()
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    pass
        self._pubsub = self._redis = None

    @property
    def connected_clients(self) -> int:
        return len(self.clients)

    async def _close(self, connection: Any) -> None:
        try:
            await connection.close()
        except Exception:
            pass

    async def _process_request(self, connection: Any, request: Any) -> Any:
        path = urlparse(request.path).path
        if path == "/health":
            async with self._lock:
                return self._http_response(200, {"connected_clients": len(self.clients)})
        if path == "/channels":
            async with self._lock:
                body = {"channels": [{"name": name, "subscriber_count": len(ids)}
                                      for name, ids in sorted(self.channels.items()) if ids]}
            return self._http_response(200, body)
        if path.startswith("/channels/") and path.endswith("/subscribers"):
            name = unquote(path[len("/channels/"):-len("/subscribers")]).strip("/")
            async with self._lock:
                ids = sorted(self.channels.get(name, set()))
            return self._http_response(200, {"subscribers": ids})
        if path == "/messages":
            query = parse_qs(urlparse(request.path).query)
            try:
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
            except ValueError:
                return self._http_response(400, {"error": "limit and offset must be integers"})
            if limit < 0 or offset < 0:
                return self._http_response(400, {"error": "limit and offset must be non-negative"})
            return self._http_response(200, {"messages": self.store.list(limit, offset)})
        return None

    @staticmethod
    def _http_response(status: int, body_data: dict[str, Any]) -> Any:
        from websockets.http11 import Headers, Response
        body = json.dumps(body_data).encode("utf-8")
        headers = Headers()
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
        return Response(status, "OK", headers, body)

    async def _handle_connection(self, connection: Any) -> None:
        peer = connection.transport.get_extra_info("peername")
        if not peer or len(peer) < 2:
            await connection.close(code=1011, reason="unable to determine client id")
            return
        client_id = int(peer[1])
        async with self._lock:
            self.clients[client_id] = connection
            restored = await self._state_channels(client_id)
            self._client_channels.setdefault(client_id, set()).update(restored)
            for channel in restored:
                self.channels.setdefault(channel, set()).add(client_id)
        try:
            async for raw_message in connection:
                await self._handle_message(client_id, raw_message)
        except (ConnectionClosed, asyncio.CancelledError):
            pass
        finally:
            async with self._lock:
                if self.clients.get(client_id) is connection:
                    self.clients.pop(client_id, None)
                    # Keep subscription state in Redis so a reconnect can restore it.
                    for channel in self._client_channels.pop(client_id, set()):
                        subscribers = self.channels.get(channel)
                        if subscribers is not None:
                            subscribers.discard(client_id)
                            if not subscribers:
                                self.channels.pop(channel, None)

    async def _state_channels(self, client_id: int) -> set[str]:
        if self._redis is None:
            return set()
        try:
            values = await self._redis.smembers(f"notifications:client:{client_id}:channels")
            return set(values)
        except Exception:
            return set()

    async def _handle_message(self, sender_id: int, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(message, dict):
            return
        message_type = message.get("type")
        payload = message.get("payload")
        if message_type not in SUPPORTED_TYPES or not isinstance(payload, dict):
            return
        channel = message.get("channel", payload.get("channel"))
        if message_type in {"subscribe", "unsubscribe"}:
            if not isinstance(channel, str) or not channel:
                return
            async with self._lock:
                if sender_id not in self.clients:
                    return
                if message_type == "subscribe":
                    self.channels.setdefault(channel, set()).add(sender_id)
                    self._client_channels.setdefault(sender_id, set()).add(channel)
                    await self._redis_state(sender_id, channel, True)
                else:
                    subscribers = self.channels.get(channel)
                    if subscribers is not None:
                        subscribers.discard(sender_id)
                        if not subscribers:
                            self.channels.pop(channel, None)
                    self._client_channels.setdefault(sender_id, set()).discard(channel)
                    await self._redis_state(sender_id, channel, False)
            return
        if message_type == "direct" and channel is None:
            target = payload.get("client_id", payload.get("recipient"))
            try:
                target_id = int(target)
            except (TypeError, ValueError):
                return
            await self.send_to(target_id, message_type, payload)
            return
        await self.broadcast(message_type, payload, channel=channel if isinstance(channel, str) else None)

    async def _redis_state(self, client_id: int, channel: str, add: bool) -> None:
        if self._redis is None:
            return
        try:
            key = f"notifications:client:{client_id}:channels"
            if add:
                await self._redis.sadd(key, channel)
            else:
                await self._redis.srem(key, channel)
        except Exception:
            pass

    async def broadcast(self, message_type: str | dict[str, Any] = "broadcast",
                        payload: dict[str, Any] | None = None, channel: str | None = None) -> None:
        if isinstance(message_type, dict):
            envelope = message_type
            message_type = envelope.get("type", "broadcast")
            payload = envelope.get("payload", {})
            channel = envelope.get("channel", channel)
        if message_type not in SUPPORTED_TYPES:
            raise ValueError(f"unsupported message type: {message_type}")
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary")
        timestamp = _timestamp()
        envelope: dict[str, Any] = {"type": message_type, "payload": payload, "timestamp": timestamp}
        if channel is not None:
            envelope["channel"] = channel
        self.store.add(channel, message_type, payload, timestamp)
        serialized = json.dumps(envelope)
        if self._redis is not None:
            try:
                await self._redis.publish(REDIS_CHANNEL, serialized)
                return
            except Exception:
                pass
        await self._deliver(envelope)

    async def _redis_loop(self) -> None:
        try:
            async for item in self._pubsub.listen():
                if item.get("type") == "message":
                    await self._deliver(json.loads(item["data"]))
        except (asyncio.CancelledError, Exception):
            return

    async def _deliver(self, envelope: dict[str, Any]) -> None:
        channel = envelope.get("channel")
        async with self._lock:
            target_id = envelope.get("client_id") if envelope.get("type") == "direct" else None
            if target_id is not None:
                connection = self.clients.get(int(target_id))
                connections = [connection] if connection is not None else []
            elif channel is None:
                connections = list(self.clients.values())
            else:
                connections = [self.clients[i] for i in self.channels.get(channel, set()) if i in self.clients]
        message = json.dumps(envelope)
        await asyncio.gather(*(self._send(connection, message) for connection in connections))

    async def send_to(self, client_id: int, message_type: str, payload: dict[str, Any]) -> None:
        if message_type not in SUPPORTED_TYPES:
            raise ValueError(f"unsupported message type: {message_type}")
        async with self._lock:
            connection = self.clients.get(client_id)
        timestamp = _timestamp()
        self.store.add(None, message_type, payload, timestamp)
        envelope = {"type": message_type, "payload": payload, "timestamp": timestamp,
                    "client_id": client_id}
        if self._redis is not None:
            try:
                await self._redis.publish(REDIS_CHANNEL, json.dumps(envelope))
                return
            except Exception:
                pass
        if connection is not None:
            await self._send(connection, json.dumps(envelope))

    async def _send(self, connection: Any, message: str) -> None:
        try:
            await connection.send(message)
        except ConnectionClosed:
            pass


async def main() -> None:
    server = NotificationServer()
    await server.start()
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
