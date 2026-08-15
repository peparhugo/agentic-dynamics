"""WebSocket notification server built on the ``websockets`` library."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qs

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from broker import RedisBroker
from storage import MessageStore

SUPPORTED_TYPES = ("broadcast", "direct", "system", "subscribe", "unsubscribe")

REDIS_CHANNEL_PREFIX = "notif:"
BROADCAST_CHANNEL = "notif:broadcast"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_message(message_type: str, payload: Optional[dict] = None) -> dict:
    return {
        "type": message_type,
        "payload": payload if payload is not None else {},
        "timestamp": utcnow_iso(),
    }


def encode_message(message: dict) -> str:
    return json.dumps(message)


class ClientRegistry:
    """Registry of connected clients keyed by their unique client id.

    Asyncio runs everything on a single event loop, so plain dict reads and
    writes are always safe and require no locking.
    """

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._subscriptions: dict[str, set[str]] = {}

    def register(self, websocket: ServerConnection) -> str:
        client_id = uuid.uuid4().hex
        self._clients[client_id] = websocket
        return client_id

    def unregister(self, client_id: str) -> None:
        self._clients.pop(client_id, None)
        self.unsubscribe_all(client_id)

    def get(self, client_id: str) -> Optional[ServerConnection]:
        return self._clients.get(client_id)

    def count(self) -> int:
        return len(self._clients)

    def connections(self) -> list[ServerConnection]:
        return list(self._clients.values())

    def ids(self) -> list[str]:
        return list(self._clients.keys())

    def subscribe(self, client_id: str, channel: str) -> bool:
        if client_id not in self._clients:
            return False
        self._subscriptions.setdefault(channel, set()).add(client_id)
        return True

    def unsubscribe(self, client_id: str, channel: str) -> bool:
        subscribers = self._subscriptions.get(channel)
        if subscribers is None:
            return False
        subscribers.discard(client_id)
        if not subscribers:
            del self._subscriptions[channel]
        return True

    def unsubscribe_all(self, client_id: str) -> None:
        for channel in list(self._subscriptions):
            subscribers = self._subscriptions[channel]
            subscribers.discard(client_id)
            if not subscribers:
                del self._subscriptions[channel]

    def channels(self) -> dict[str, int]:
        return {
            channel: len(subscribers)
            for channel, subscribers in self._subscriptions.items()
        }

    def subscribers(self, channel: str) -> list[str]:
        return sorted(
            client_id
            for client_id in self._subscriptions.get(channel, set())
            if client_id in self._clients
        )

    def channel_connections(self, channel: str) -> list[ServerConnection]:
        return [
            self._clients[client_id]
            for client_id in self._subscriptions.get(channel, set())
            if client_id in self._clients
        ]


class NotificationServer:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        health_port: int = 8766,
        redis_url: Optional[str] = None,
        database_url: Optional[str] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.health_port = health_port
        self.registry = ClientRegistry()
        self.redis_url = (
            redis_url if redis_url is not None else os.environ.get("REDIS_URL")
        )
        database_url = (
            database_url if database_url is not None else os.environ.get("DATABASE_URL")
        )
        if database_url is None:
            database_url = ":memory:"
        self.store = MessageStore(database_url)
        self.broker: Optional[RedisBroker] = (
            RedisBroker(self.redis_url) if self.redis_url else None
        )
        self._ws_server: Optional[asyncio.Server] = None
        self._health_server: Optional[asyncio.Server] = None

    async def start(self) -> "NotificationServer":
        self._ws_server = await serve(self._handle_connection, self.host, self.port)
        self.port = self._ws_server.sockets[0].getsockname()[1]
        self._health_server = await asyncio.start_server(
            self._handle_http, self.host, self.health_port
        )
        self.health_port = self._health_server.sockets[0].getsockname()[1]
        if self.broker is not None:
            try:
                await self.broker.connect()
                await self.broker.start_listener(self._deliver_from_redis)
            except Exception:
                self.broker = None
        return self

    async def stop(self) -> None:
        if self.broker is not None:
            await self.broker.close()
            self.broker = None
        if self._ws_server is not None:
            self._ws_server.close()
            await self._ws_server.wait_closed()
            self._ws_server = None
        if self._health_server is not None:
            self._health_server.close()
            await self._health_server.wait_closed()
            self._health_server = None
        self.store.close()

    async def __aenter__(self) -> "NotificationServer":
        return await self.start()

    async def __aexit__(self, *exc) -> None:
        await self.stop()

    async def _handle_connection(self, websocket: ServerConnection) -> None:
        client_id = self.registry.register(websocket)
        await self._on_client_registered(client_id)
        try:
            await websocket.send(
                encode_message(make_message("system", {"client_id": client_id}))
            )
            async for raw in websocket:
                await self._handle_incoming(client_id, raw)
        except ConnectionClosed:
            pass
        finally:
            self.registry.unregister(client_id)
            await self._on_client_unregistered(client_id)

    async def _handle_incoming(self, client_id: str, raw: str) -> None:
        try:
            message = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return
        if not isinstance(message, dict):
            return
        message_type = message.get("type", "broadcast")
        payload = message.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        channel = message.get("channel")
        if channel is None:
            channel = payload.get("channel")
        if message_type == "subscribe":
            if channel:
                await self.subscribe(client_id, channel)
        elif message_type == "unsubscribe":
            if channel:
                await self.unsubscribe(client_id, channel)
        elif message_type == "broadcast":
            if channel:
                await self.publish_to_channel(channel, "broadcast", payload)
            else:
                await self.broadcast("broadcast", payload)
        elif message_type == "direct":
            target = payload.get("to")
            if target:
                await self.send_to(target, "direct", payload)

    async def broadcast(
        self, message_type: str = "broadcast", payload: Optional[dict] = None
    ) -> int:
        message = make_message(message_type, payload)
        encoded = encode_message(message)
        targets = self.registry.connections()
        if targets:
            await asyncio.gather(
                *(websocket.send(encoded) for websocket in targets),
                return_exceptions=True,
            )
        await self._record_and_publish(
            "", message_type, message["payload"], message["timestamp"]
        )
        return len(targets)

    async def send_to(
        self, client_id: str, message_type: str = "direct", payload: Optional[dict] = None
    ) -> bool:
        message = make_message(message_type, payload)
        websocket = self.registry.get(client_id)
        if websocket is not None:
            await websocket.send(encode_message(message))
        await self._record_and_publish(
            client_id, message_type, message["payload"], message["timestamp"]
        )
        return websocket is not None

    async def subscribe(self, client_id: str, channel: str) -> bool:
        if not channel:
            return False
        subscribed = self.registry.subscribe(client_id, channel)
        if subscribed and self.broker is not None:
            await self.broker.subscribe_client(client_id, channel)
        return subscribed

    async def unsubscribe(self, client_id: str, channel: str) -> bool:
        if not channel:
            return False
        unsubscribed = self.registry.unsubscribe(client_id, channel)
        if unsubscribed and self.broker is not None:
            await self.broker.unsubscribe_client(client_id, channel)
        return unsubscribed

    async def publish_to_channel(
        self, channel: str, message_type: str = "broadcast", payload: Optional[dict] = None
    ) -> int:
        message = make_message(message_type, payload)
        encoded = encode_message(message)
        targets = self.registry.channel_connections(channel)
        if targets:
            await asyncio.gather(
                *(websocket.send(encoded) for websocket in targets),
                return_exceptions=True,
            )
        await self._record_and_publish(
            channel, message_type, message["payload"], message["timestamp"]
        )
        return len(targets)

    async def _record_and_publish(
        self,
        channel: str,
        message_type: str,
        payload: Optional[dict],
        timestamp: str,
    ) -> None:
        self.store.add(channel, message_type, payload, timestamp)
        if self.broker is not None:
            await self.broker.publish(channel, message_type, payload, timestamp)

    async def _deliver_from_redis(self, redis_channel: str, data: dict) -> None:
        message = make_message(data.get("type", "broadcast"), data.get("payload"))
        message["timestamp"] = data.get("timestamp", message["timestamp"])
        encoded = encode_message(message)
        if redis_channel == BROADCAST_CHANNEL:
            targets = self.registry.connections()
        elif redis_channel.startswith(f"{REDIS_CHANNEL_PREFIX}channel:"):
            channel = redis_channel[len(f"{REDIS_CHANNEL_PREFIX}channel:"):]
            targets = self.registry.channel_connections(channel)
        elif redis_channel.startswith(f"{REDIS_CHANNEL_PREFIX}direct:"):
            client_id = redis_channel[len(f"{REDIS_CHANNEL_PREFIX}direct:"):]
            websocket = self.registry.get(client_id)
            targets = [websocket] if websocket is not None else []
        else:
            targets = []
        if targets:
            await asyncio.gather(
                *(websocket.send(encoded) for websocket in targets),
                return_exceptions=True,
            )

    async def _on_client_registered(self, client_id: str) -> None:
        if self.broker is not None:
            await self.broker.register_client(client_id)

    async def _on_client_unregistered(self, client_id: str) -> None:
        if self.broker is not None:
            await self.broker.unregister_client(client_id)

    async def _handle_http(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=10)
            if not request_line:
                return
            parts = request_line.decode("latin-1").strip().split()
            method = parts[0] if parts else ""
            raw_path = parts[1] if len(parts) > 1 else ""
            if "?" in raw_path:
                path, _, query_string = raw_path.partition("?")
            else:
                path, query_string = raw_path, ""
            params = parse_qs(query_string)
            while True:
                line = await reader.readline()
                if not line or line in (b"\r\n", b"\n"):
                    break
            if method == "GET" and path == "/health":
                status = "200 OK"
                body = json.dumps(
                    {"status": "ok", "connected": self.registry.count()}
                ).encode("utf-8")
            elif method == "GET" and path == "/channels":
                status = "200 OK"
                body = json.dumps(self.registry.channels()).encode("utf-8")
            elif method == "GET" and path == "/messages":
                try:
                    limit = int(params.get("limit", ["50"])[0])
                except (ValueError, IndexError):
                    limit = 50
                try:
                    offset = int(params.get("offset", ["0"])[0])
                except (ValueError, IndexError):
                    offset = 0
                status = "200 OK"
                body = json.dumps(self.store.query(limit=limit, offset=offset)).encode(
                    "utf-8"
                )
            elif (
                method == "GET"
                and path.startswith("/channels/")
                and path.endswith("/subscribers")
            ):
                channel_name = path[len("/channels/"):-len("/subscribers")]
                status = "200 OK"
                body = json.dumps(self.registry.subscribers(channel_name)).encode("utf-8")
            else:
                status = "404 Not Found"
                body = json.dumps({"error": "not found"}).encode("utf-8")
            response = (
                f"HTTP/1.1 {status}\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode("latin-1") + body
            writer.write(response)
            await writer.drain()
        except (asyncio.TimeoutError, ConnectionError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass

    def run(self) -> None:
        asyncio.run(self._run_forever())

    async def _run_forever(self) -> None:
        await self.start()
        try:
            await asyncio.Future()
        finally:
            await self.stop()


if __name__ == "__main__":
    NotificationServer().run()
