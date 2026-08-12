"""Async WebSocket notification server with Redis and SQLite backends."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
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

    def history(self, channel: str, since: str | None = None, limit: int = 50) -> tuple[list[dict[str, Any]], bool]:
        """Return a channel's messages in timestamp order, plus a continuation flag."""
        clauses = ["channel = ?"]
        parameters: list[Any] = [channel]
        if since is not None:
            clauses.append("timestamp > ?")
            parameters.append(since)
        parameters.append(limit + 1)
        rows = self.connection.execute(
            "SELECT id, channel, type, payload, timestamp FROM messages WHERE "
            + " AND ".join(clauses)
            + " ORDER BY timestamp ASC, id ASC LIMIT ?",
            parameters,
        ).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        return ([
            {"id": row["id"], "channel": row["channel"], "type": row["type"],
             "payload": json.loads(row["payload"]), "timestamp": row["timestamp"]}
            for row in rows
        ], has_more)

    def delete_older_than(self, cutoff: str) -> int:
        cursor = self.connection.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff,))
        self.connection.commit()
        return cursor.rowcount

    def close(self) -> None:
        self.connection.close()


class BaseTransport(ABC):
    """Transport contract used by the notification server."""

    async def start(self, on_connection: Any, host: str, port: int, process_request: Any) -> None:
        """Start accepting connections, if the transport requires a listener."""

    async def stop(self) -> None:
        """Stop accepting new connections."""

    @abstractmethod
    async def on_connect(self, connection: Any) -> None:
        """Register transport-specific state for a new connection."""

    @abstractmethod
    async def on_disconnect(self, connection: Any) -> None:
        """Release transport-specific state for a disconnected connection."""

    @abstractmethod
    async def send_message(self, connection: Any, message: str) -> None:
        """Send one serialized message to a connection."""

    @abstractmethod
    async def broadcast(self, connections: list[Any], message: str) -> None:
        """Send one serialized message to a group of connections."""


Transport = BaseTransport


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport contract."""

    def __init__(self) -> None:
        self._server: Any = None

    async def start(self, on_connection: Any, host: str, port: int, process_request: Any) -> None:
        self._server = await websockets.serve(
            on_connection, host, port, process_request=process_request
        )

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def on_connect(self, connection: Any) -> None:
        return None

    async def on_disconnect(self, connection: Any) -> None:
        return None

    async def send_message(self, connection: Any, message: str) -> None:
        try:
            await connection.send(message)
        except ConnectionClosed:
            pass

    async def broadcast(self, connections: list[Any], message: str) -> None:
        await asyncio.gather(*(self.send_message(connection, message) for connection in connections))


class NotificationServer:
    """Manage clients while Redis distributes envelopes between server instances."""

    def __init__(self, host: str = "localhost", port: int = 8765,
                 redis_url: str | None = None, database_url: str | None = None,
                 transport: BaseTransport | None = None) -> None:
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
        self._cleanup_task: asyncio.Task[Any] | None = None
        try:
            self.rate_limit = max(0, int(os.getenv("RATE_LIMIT", "100")))
        except ValueError:
            self.rate_limit = 100
        try:
            self.message_ttl_days = max(0, float(os.getenv("MESSAGE_TTL_DAYS", "7")))
        except ValueError:
            self.message_ttl_days = 7
        self._local_rate_limits: dict[tuple[int, int], int] = {}
        self.store = MessageStore(database_url)
        self.transport = transport or self._create_transport()

    @staticmethod
    def _create_transport() -> BaseTransport:
        configured = os.getenv("TRANSPORT", "websocket").strip().lower()
        if configured in {"websocket", "ws"}:
            return WebSocketTransport()
        raise ValueError(f"unsupported transport: {configured}")

    async def start(self) -> None:
        await self._cleanup_expired_messages()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        if self.redis_url and redis is not None:
            try:
                self._redis = redis.from_url(self.redis_url, decode_responses=True)
                await self._redis.ping()
                self._pubsub = self._redis.pubsub()
                await self._pubsub.subscribe(REDIS_CHANNEL)
                self._redis_task = asyncio.create_task(self._redis_loop())
            except Exception:
                await self._close_redis()
        await self.transport.start(
            self._handle_connection, self.host, self.port, process_request=self._process_request
        )
        self._server = getattr(self.transport, "_server", None)
        if self._server is not None and self._server.sockets:
            self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        await self.transport.stop()
        self._server = None
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            await asyncio.gather(self._cleanup_task, return_exceptions=True)
            self._cleanup_task = None
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

    async def _cleanup_expired_messages(self) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.message_ttl_days))
        self.store.delete_older_than(cutoff.isoformat().replace("+00:00", "Z"))

    async def _cleanup_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(24 * 60 * 60)
                await self._cleanup_expired_messages()
        except asyncio.CancelledError:
            return

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
        if path == "/history":
            query = parse_qs(urlparse(request.path).query)
            channel = query.get("channel", [None])[0]
            if not channel:
                return self._http_response(400, {"error": "channel is required"})
            since = query.get("since", [None])[0]
            if since is not None:
                try:
                    datetime.fromisoformat(since.replace("Z", "+00:00"))
                except ValueError:
                    return self._http_response(400, {"error": "since must be an ISO timestamp"})
            try:
                limit = int(query.get("limit", ["50"])[0])
            except ValueError:
                return self._http_response(400, {"error": "limit must be an integer"})
            if limit < 0:
                return self._http_response(400, {"error": "limit must be non-negative"})
            messages, has_more = self.store.history(channel, since, limit)
            return self._http_response(200, {"messages": messages, "has_more": has_more})
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
        await self.transport.on_connect(connection)
        async with self._lock:
            self.clients[client_id] = connection
            restored = await self._state_channels(client_id)
            self._client_channels.setdefault(client_id, set()).update(restored)
            for channel in restored:
                self.channels.setdefault(channel, set()).add(client_id)
        try:
            async for raw_message in connection:
                if not await self._allow_message(client_id):
                    await self.transport.send_message(connection, json.dumps({"error": "rate limit exceeded"}))
                    continue
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
            await self.transport.on_disconnect(connection)

    async def _allow_message(self, client_id: int) -> bool:
        if self.rate_limit == 0:
            return False
        window = int(time.time() // 60)
        key = f"notifications:rate:{client_id}:{window}"
        if self._redis is not None:
            try:
                count = int(await self._redis.incr(key))
                if count == 1:
                    await self._redis.expire(key, 61)
                return count <= self.rate_limit
            except Exception:
                pass
        local_key = (client_id, window)
        count = self._local_rate_limits.get(local_key, 0) + 1
        self._local_rate_limits[local_key] = count
        if len(self._local_rate_limits) > 1000:
            self._local_rate_limits = {
                key: value for key, value in self._local_rate_limits.items() if key[1] >= window
            }
        return count <= self.rate_limit

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
        await self.transport.broadcast(connections, message)

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
            await self.transport.send_message(connection, json.dumps(envelope))


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
