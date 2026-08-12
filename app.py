"""Async WebSocket notification server.

The WebSocket service and the small HTTP health service intentionally share a
``NotificationServer`` instance so the health count is always current.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

import redis.asyncio as redis
from transport import BaseTransport, WebSocketTransport

LOGGER = logging.getLogger(__name__)
SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
REDIS_CHANNEL = "notification:messages"


def make_message(
    message_type: str, payload: dict[str, Any], channel: str | None = None
) -> dict[str, Any]:
    """Create a protocol message with a UTC timestamp."""
    if message_type not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported message type: {message_type}")
    message = {
        "type": message_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if channel is not None:
        message["channel"] = channel
    return message


class NotificationServer:
    """Serve notifications over WebSocket and status over HTTP."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        websocket_port: int = 8765,
        health_port: int | None = None,
        redis_url: str | None = None,
        database_url: str | None = None,
        transport: BaseTransport | None = None,
    ) -> None:
        self.host = host
        self.websocket_port = websocket_port
        self.health_port = health_port if health_port is not None else websocket_port + 1
        self.redis_url = redis_url if redis_url is not None else os.getenv("REDIS_URL")
        self.database_url = database_url if database_url is not None else os.getenv(
            "DATABASE_URL", ":memory:"
        )
        self._instance_id = str(uuid.uuid4())
        selected_transport = os.getenv("TRANSPORT", "websocket").lower()
        if transport is not None:
            self.transport = transport
        elif selected_transport in {"websocket", "ws"}:
            self.transport = WebSocketTransport()
        else:
            raise ValueError(f"unsupported transport: {selected_transport}")
        self._subscriptions: dict[str, set[str]] = {}
        self._clients_lock = threading.RLock()
        self._health_server: asyncio.AbstractServer | None = None
        self._redis: redis.Redis | None = None
        self._pubsub: redis.client.PubSub | None = None
        self._redis_task: asyncio.Task[None] | None = None
        self._database = sqlite3.connect(self._sqlite_path(), check_same_thread=False)
        self._database.row_factory = sqlite3.Row
        self._database_lock = threading.RLock()
        self._database.execute(
            """CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )"""
        )
        self._database.commit()

    def _sqlite_path(self) -> str:
        if self.database_url.startswith("sqlite:///"):
            return self.database_url[len("sqlite:///") :]
        if self.database_url.startswith("sqlite://"):
            return self.database_url[len("sqlite://") :]
        return self.database_url

    @property
    def clients(self) -> dict[str, Any]:
        """Return a snapshot of connected clients, never the mutable registry."""
        with self._clients_lock:
            return self.transport.clients

    @property
    def client_count(self) -> int:
        with self._clients_lock:
            return len(self.transport.clients)

    @property
    def channels(self) -> dict[str, set[str]]:
        """Return active channels and snapshots of their subscriber IDs."""
        with self._clients_lock:
            return {name: set(subscribers) for name, subscribers in self._subscriptions.items()}

    async def start(self) -> None:
        """Start both listeners."""
        if self.redis_url:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
            await self._redis.ping()
            self._pubsub = self._redis.pubsub()
            await self._pubsub.subscribe(REDIS_CHANNEL)
            self._redis_task = asyncio.create_task(self._redis_listener())
        await self.transport.start(
            self.host, self.websocket_port, self._client_connected,
            self._handle_client_message, self._client_disconnected,
        )
        self._health_server = await asyncio.start_server(
            self._health_handler, self.host, self.health_port
        )

    async def stop(self) -> None:
        """Stop listeners and close all active WebSocket connections."""
        if self._health_server is not None:
            self._health_server.close()
            await self._health_server.wait_closed()
            self._health_server = None
        await self.transport.stop()
        if self._redis_task is not None:
            self._redis_task.cancel()
            await asyncio.gather(self._redis_task, return_exceptions=True)
            self._redis_task = None
        if self._pubsub is not None:
            await self._pubsub.close()
            self._pubsub = None
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
        with self._clients_lock:
            self._subscriptions.clear()
        with self._database_lock:
            self._database.close()

    async def wait_closed(self) -> None:
        """Wait for either listener to be closed by the caller."""
        await self.transport.wait_closed()

    async def broadcast(self, payload: dict[str, Any], channel: str | None = None) -> None:
        """Send a broadcast message to every currently connected client."""
        if channel is None:
            channel = payload.get("channel")
        message = make_message("broadcast", payload, channel)
        await self._publish_or_deliver(message)

    async def send_direct(self, client_id: str, payload: dict[str, Any]) -> bool:
        """Send a direct message and return whether the client exists."""
        connection_exists = client_id in self.clients
        if not connection_exists and self._redis is not None:
            connection_exists = bool(await self._redis.exists(f"notification:client:{client_id}"))
        if not connection_exists:
            return False
        message = make_message("direct", payload)
        await self._publish_or_deliver(message, target_client_id=client_id)
        return True

    async def _publish_or_deliver(
        self, message: dict[str, Any], target_client_id: str | None = None
    ) -> None:
        self._store_message(message)
        envelope = {"message": message, "target_client_id": target_client_id}
        if self._redis is not None:
            await self._redis.publish(REDIS_CHANNEL, json.dumps(envelope))
        else:
            await self._deliver(message, target_client_id)

    async def _redis_listener(self) -> None:
        assert self._pubsub is not None
        try:
            async for item in self._pubsub.listen():
                if item.get("type") != "message":
                    continue
                envelope = json.loads(item["data"])
                await self._deliver(envelope["message"], envelope.get("target_client_id"))
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("Redis message listener stopped")

    async def _deliver(self, message: dict[str, Any], target_client_id: str | None = None) -> None:
        if target_client_id is not None:
            recipients = {
                target_client_id: self.clients[target_client_id]
            } if target_client_id in self.clients else {}
        else:
            channel = message.get("channel")
            recipients = self.clients
            if isinstance(channel, str):
                if self._redis is not None:
                    subscriber_ids = await self._redis.smembers(
                        f"notification:channel:{channel}"
                    )
                else:
                    with self._clients_lock:
                        subscriber_ids = self._subscriptions.get(channel, set())
                with self._clients_lock:
                    recipients = {
                        client_id: self.clients[client_id]
                        for client_id in subscriber_ids
                        if client_id in self.clients
                    }
        await self._send_to_many(message, recipients)

    def _store_message(self, message: dict[str, Any]) -> None:
        with self._database_lock:
            self._database.execute(
                "INSERT INTO messages(channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (message.get("channel"), message["type"], json.dumps(message["payload"]), message["timestamp"]),
            )
            self._database.commit()

    def _message_history(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with self._database_lock:
            rows = self._database.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        return [
            {"id": row["id"], "channel": row["channel"], "type": row["type"],
             "payload": json.loads(row["payload"]), "timestamp": row["timestamp"]}
            for row in rows
        ]

    async def _client_connected(self, client_id: str) -> None:
        if self._redis is not None:
            await self._redis.set(
                f"notification:client:{client_id}",
                json.dumps({"instance_id": self._instance_id, "connected": True}),
            )
        await self.transport.send_message(
            client_id, make_message("system", {"client_id": client_id})
        )

    async def _client_disconnected(self, client_id: str) -> None:
        with self._clients_lock:
            for channel in list(self._subscriptions):
                self._subscriptions[channel].discard(client_id)
                if not self._subscriptions[channel]:
                    del self._subscriptions[channel]
        if self._redis is not None:
            await self._redis.delete(f"notification:client:{client_id}")

    async def _handle_client_message(self, client_id: str, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
            message_type = message["type"]
            payload = message.get("payload", {})
            if message_type not in SUPPORTED_TYPES or not isinstance(payload, dict):
                raise ValueError
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            await self.send_direct(client_id, {"error": "invalid message"})
            return

        if message_type in {"subscribe", "unsubscribe"}:
            channel = message.get("channel", payload.get("channel"))
            if not isinstance(channel, str) or not channel:
                await self.send_direct(client_id, {"error": "invalid channel"})
                return
            with self._clients_lock:
                if message_type == "subscribe":
                    self._subscriptions.setdefault(channel, set()).add(client_id)
                elif channel in self._subscriptions:
                    self._subscriptions[channel].discard(client_id)
                    if not self._subscriptions[channel]:
                        del self._subscriptions[channel]
            if self._redis is not None:
                key = f"notification:subscriptions:{client_id}"
                if message_type == "subscribe":
                    await self._redis.sadd(key, channel)
                    await self._redis.sadd(f"notification:channel:{channel}", client_id)
                else:
                    await self._redis.srem(key, channel)
                    await self._redis.srem(f"notification:channel:{channel}", client_id)
        elif message_type == "broadcast":
            await self.broadcast(payload, message.get("channel"))
        elif message_type == "direct":
            recipient = payload.get("client_id")
            if isinstance(recipient, str):
                await self.send_direct(recipient, payload)

    async def _send_to_many(
        self, message: dict[str, Any], clients: dict[str, Any]
    ) -> None:
        await self.transport.broadcast(message, set(clients))

    async def _health_handler(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request_line = await reader.readline()
            path = urlsplit(request_line.decode("ascii", errors="ignore").split(" ")[1]).path
            if path == "/health":
                count = self.client_count
                body = json.dumps(
                    {"status": "ok", "clients": count, "connected_clients": count}
                ).encode()
                status = "200 OK"
            elif path == "/channels":
                body = json.dumps(
                    {"channels": {name: len(ids) for name, ids in self.channels.items()}}
                ).encode()
                status = "200 OK"
            elif path.startswith("/channels/") and path.endswith("/subscribers"):
                name = unquote(path[len("/channels/") : -len("/subscribers")]).rstrip("/")
                subscribers = sorted(self.channels.get(name, set()))
                body = json.dumps({"channel": name, "subscribers": subscribers}).encode()
                status = "200 OK"
            elif path == "/messages":
                query = parse_qs(urlsplit(request_line.decode("ascii", errors="ignore").split(" ")[1]).query)
                try:
                    limit = max(0, min(1000, int(query.get("limit", ["50"])[0])))
                    offset = max(0, int(query.get("offset", ["0"])[0]))
                except (TypeError, ValueError):
                    body = json.dumps({"error": "invalid pagination"}).encode()
                    status = "400 Bad Request"
                else:
                    body = json.dumps(self._message_history(limit, offset)).encode()
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
        except (IndexError, UnicodeError):
            writer.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()


def main() -> None:
    parser = argparse.ArgumentParser(description="WebSocket notification server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--websocket-port", type=int, default=8765)
    parser.add_argument("--health-port", type=int, default=None)
    args = parser.parse_args()

    async def run() -> None:
        server = NotificationServer(args.host, args.websocket_port, args.health_port)
        await server.start()
        await server.wait_closed()

    asyncio.run(run())


if __name__ == "__main__":
    main()
