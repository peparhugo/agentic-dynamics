"""WebSocket notification server with Redis distribution and SQLite history."""

import asyncio
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs, urlsplit

from websockets.asyncio.server import ServerConnection, serve

from transport import BaseTransport, WebSocketTransport


Message = dict[str, Any]
BROKER_CHANNEL = "notifications:messages"
STATE_PREFIX = "notifications"


class NotificationServer:
    """Manages connected WebSocket clients and notification delivery."""

    def __init__(
        self,
        redis_client: Any | None = None,
        database_url: str | None = None,
        transport: BaseTransport | None = None,
    ) -> None:
        self._transport = transport or self._transport_from_config()
        self._connected_clients: set[str] = set()
        self._channels: dict[str, set[str]] = {}
        self._clients_lock = threading.Lock()
        self._database_lock = threading.Lock()
        self._redis = redis_client
        self._pubsub: Any | None = None
        self._listener_task: asyncio.Task[None] | None = None
        self._database = sqlite3.connect(self._database_path(database_url), check_same_thread=False)
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

    @staticmethod
    def _transport_from_config() -> BaseTransport:
        transport_name = os.environ.get("TRANSPORT", "websocket").lower()
        if transport_name == "websocket":
            return WebSocketTransport()
        raise ValueError(f"Unsupported transport: {transport_name}")

    @staticmethod
    def _database_path(database_url: str | None) -> str:
        value = database_url or os.environ.get("DATABASE_URL", ":memory:")
        if value.startswith("sqlite:///"):
            return value[len("sqlite:///"):]
        if value.startswith("sqlite://"):
            return value[len("sqlite://"):]
        return value

    @property
    def connected_client_count(self) -> int:
        with self._clients_lock:
            return len(self._connected_clients)

    @staticmethod
    def _message(message_type: str, payload: dict[str, Any], channel: str | None = None) -> Message:
        message: Message = {
            "type": message_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if channel is not None:
            message["channel"] = channel
        return message

    async def _ensure_broker(self) -> None:
        if self._redis is None:
            redis_url = os.environ.get("REDIS_URL")
            if not redis_url:
                return
            from redis.asyncio import Redis

            self._redis = Redis.from_url(redis_url, decode_responses=True)
        if self._listener_task is None or self._listener_task.done():
            self._pubsub = self._redis.pubsub()
            await self._pubsub.subscribe(BROKER_CHANNEL)
            self._listener_task = asyncio.create_task(self._listen_for_messages())

    async def _listen_for_messages(self) -> None:
        assert self._pubsub is not None
        try:
            async for event in self._pubsub.listen():
                if event.get("type") != "message":
                    continue
                data = event["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                await self._deliver_broker_message(json.loads(data))
        except asyncio.CancelledError:
            raise
        except (json.JSONDecodeError, TypeError, ValueError):
            return

    async def _deliver_broker_message(self, event: dict[str, Any]) -> None:
        message = event.get("message")
        if not isinstance(message, dict):
            return
        if event.get("route") == "direct":
            recipient = event.get("recipient")
            if isinstance(recipient, str):
                await self._transport.send_message(recipient, message)
            return
        channel = event.get("channel")
        client_ids = self._channel_snapshot(channel) if isinstance(channel, str) else None
        await self._transport.broadcast(message, client_ids)

    def _persist(self, message: Message) -> None:
        with self._database_lock:
            self._database.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (message.get("channel"), message["type"], json.dumps(message["payload"]), message["timestamp"]),
            )
            self._database.commit()

    async def _publish(self, event: dict[str, Any]) -> None:
        await self._ensure_broker()
        if self._redis is None:
            await self._deliver_broker_message(event)
            return
        await self._redis.publish(BROKER_CHANNEL, json.dumps(event))

    async def _set_client_state(self, client_id: str) -> None:
        if self._redis is not None:
            await self._redis.hset(f"{STATE_PREFIX}:clients", client_id, json.dumps({"connected": True}))

    async def _remove_client_state(self, client_id: str) -> None:
        if self._redis is not None:
            await self._redis.hdel(f"{STATE_PREFIX}:clients", client_id)
            for channel in self._channels:
                await self._redis.srem(f"{STATE_PREFIX}:channel:{channel}", client_id)

    async def _remove_client(self, client_id: str) -> None:
        with self._clients_lock:
            channels = [channel for channel, subscribers in self._channels.items() if client_id in subscribers]
            self._connected_clients.discard(client_id)
            for channel in channels:
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]
        await self._transport.on_disconnect(client_id)
        if self._redis is not None:
            await self._redis.hdel(f"{STATE_PREFIX}:clients", client_id)
            for channel in channels:
                await self._redis.srem(f"{STATE_PREFIX}:channel:{channel}", client_id)

    def _channel_snapshot(self, channel: str) -> list[str]:
        with self._clients_lock:
            return list(self._channels.get(channel, set()))

    async def _subscribe(self, client_id: str, channel: str) -> None:
        with self._clients_lock:
            self._channels.setdefault(channel, set()).add(client_id)
        if self._redis is not None:
            await self._redis.sadd(f"{STATE_PREFIX}:channel:{channel}", client_id)

    async def _unsubscribe(self, client_id: str, channel: str) -> None:
        with self._clients_lock:
            subscribers = self._channels.get(channel)
            if subscribers is not None:
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[channel]
        if self._redis is not None:
            await self._redis.srem(f"{STATE_PREFIX}:channel:{channel}", client_id)

    async def _channel_details(self) -> dict[str, int]:
        if self._redis is not None:
            channels = await self._redis.keys(f"{STATE_PREFIX}:channel:*")
            return {
                str(channel).removeprefix(f"{STATE_PREFIX}:channel:"): await self._redis.scard(channel)
                for channel in sorted(channels)
            }
        with self._clients_lock:
            return {channel: len(subscribers) for channel, subscribers in sorted(self._channels.items())}

    async def _channel_subscribers(self, channel: str) -> list[str]:
        if self._redis is not None:
            return sorted(await self._redis.smembers(f"{STATE_PREFIX}:channel:{channel}"))
        with self._clients_lock:
            return sorted(self._channels.get(channel, set()))

    async def broadcast(self, payload: dict[str, Any], channel: str | None = None) -> None:
        """Publish a broadcast and persist it before delivery."""
        message = self._message("broadcast", payload, channel)
        self._persist(message)
        await self._publish({"route": "broadcast", "channel": channel, "message": message})

    async def send_direct(self, client_id: str, payload: dict[str, Any]) -> bool:
        """Publish a direct message, returning local recipient availability without Redis."""
        await self._ensure_broker()
        with self._clients_lock:
            connected = client_id in self._connected_clients
        if self._redis is None and not connected:
            return False
        message = self._message("direct", payload)
        self._persist(message)
        await self._publish({"route": "direct", "recipient": client_id, "message": message})
        return True

    async def handler(self, connection: ServerConnection) -> None:
        await self._ensure_broker()
        client_id = await self._transport.on_connect(connection)
        with self._clients_lock:
            self._connected_clients.add(client_id)
        await self._set_client_state(client_id)
        await self._transport.send_message(client_id, self._message("system", {"client_id": client_id}))
        try:
            async for raw_message in connection:
                await self._handle_message(client_id, raw_message)
        finally:
            await self._remove_client(client_id)

    async def _handle_message(self, sender_id: str, raw_message: str | bytes) -> None:
        try:
            message = json.loads(raw_message)
            message_type = message["type"]
            payload = message.get("payload", {})
            if not isinstance(message_type, str):
                raise ValueError("type must be a string")
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            await self._transport.send_message(sender_id, self._message("system", {"error": "invalid message"}))
            return

        if message_type == "broadcast":
            channel = message.get("channel")
            if channel is not None and not isinstance(channel, str):
                await self._transport.send_message(sender_id, self._message("system", {"error": "channel must be a string"}))
                return
            await self.broadcast(payload, channel)
        elif message_type in {"subscribe", "unsubscribe"}:
            channel = message.get("channel")
            if not isinstance(channel, str):
                await self._transport.send_message(sender_id, self._message("system", {"error": "channel required"}))
                return
            if message_type == "subscribe":
                await self._subscribe(sender_id, channel)
            else:
                await self._unsubscribe(sender_id, channel)
        elif message_type == "direct":
            recipient_id = payload.get("client_id")
            if isinstance(recipient_id, str):
                await self.send_direct(recipient_id, payload)
            else:
                await self._transport.send_message(sender_id, self._message("system", {"error": "client_id required"}))
        elif message_type == "system":
            await self._transport.send_message(sender_id, self._message("system", payload))
        else:
            await self._transport.send_message(sender_id, self._message("system", {"error": "unsupported message type"}))

    def _messages(self, limit: int, offset: int) -> list[Message]:
        with self._database_lock:
            rows = self._database.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [
            {"id": row[0], "channel": row[1], "type": row[2], "payload": json.loads(row[3]), "timestamp": row[4]}
            for row in rows
        ]

    async def process_request(self, connection: ServerConnection, request: Any) -> Any:
        parsed = urlsplit(request.path)
        if parsed.path == "/health":
            return connection.respond(HTTPStatus.OK, json.dumps({"connected_clients": self.connected_client_count}))
        if parsed.path == "/messages":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
                if limit < 0 or offset < 0:
                    raise ValueError
            except ValueError:
                return connection.respond(HTTPStatus.BAD_REQUEST, json.dumps({"error": "limit and offset must be non-negative integers"}))
            return connection.respond(HTTPStatus.OK, json.dumps(self._messages(limit, offset)))
        if parsed.path == "/channels":
            return connection.respond(HTTPStatus.OK, json.dumps(await self._channel_details()))
        if parsed.path.startswith("/channels/") and parsed.path.endswith("/subscribers"):
            channel = parsed.path[len("/channels/"):-len("/subscribers")]
            if channel and "/" not in channel:
                return connection.respond(HTTPStatus.OK, json.dumps({"subscribers": await self._channel_subscribers(channel)}))
        return None


async def start_server(host: str = "127.0.0.1", port: int = 8765) -> Any:
    """Create an unstarted-by-context-manager websockets server instance."""
    notification_server = NotificationServer()
    return await serve(notification_server.handler, host, port, process_request=notification_server.process_request)


async def main() -> None:
    server = await start_server()
    print("Notification server listening on ws://127.0.0.1:8765")
    await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
