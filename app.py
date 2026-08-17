"""
Transport-agnostic notification server.

Features:
- Accept client connections via a pluggable transport (WebSocket by default)
- Assign each client a unique ID on connect
- Broadcast a message to ALL connected clients
- Route messages with a 'channel' field to that channel's subscribers
- Subscribe/unsubscribe clients to named channels
- Handle client disconnect (clean removal)
- REST endpoints:
    GET /health -> connected client count
    GET /channels -> active channels and subscriber counts
    GET /channels/{name}/subscribers -> subscriber IDs

The wire protocol is provided by a :class:`transport.BaseTransport` selected via
the ``TRANSPORT`` environment variable; ``WebSocketTransport`` is the default.

Message format (JSON): {type: str, payload: dict, timestamp: str, channel?: str}
Supported types: 'broadcast', 'direct', 'system', 'subscribe', 'unsubscribe'
"""

import asyncio
import json
import os
import threading
from datetime import datetime, timezone
from itertools import count
from urllib.parse import parse_qs

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Response

from broker import Broker, make_broker
from store import MessageStore
from transport import BaseTransport, decode_message, encode_message, make_transport

BROKER_CHANNEL = "notifications"


def utcnow_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


class ClientRegistry:
    """Thread-safe registry of connected WebSocket clients and their channel subscriptions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clients: dict[int, ServerConnection] = {}
        self._ids = count(1)
        self._subscriptions: dict[int, set[str]] = {}
        self._channels: dict[str, set[int]] = {}

    def add(self, connection: ServerConnection) -> int:
        """Register a connection and return its unique client ID."""
        with self._lock:
            client_id = next(self._ids)
            self._clients[client_id] = connection
            return client_id

    def remove(self, client_id: int) -> None:
        """Remove a client from the registry (idempotent)."""
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in self._subscriptions.pop(client_id, set()):
                members = self._channels.get(channel)
                if members is not None:
                    members.discard(client_id)
                    if not members:
                        self._channels.pop(channel, None)

    def get(self, client_id: int):
        """Return a client's connection by ID, or None."""
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> list[tuple[int, ServerConnection]]:
        """Return a consistent snapshot of all connected clients."""
        with self._lock:
            return list(self._clients.items())

    def count(self) -> int:
        """Return the number of currently connected clients."""
        with self._lock:
            return len(self._clients)

    def subscribe(self, client_id: int, channel: str) -> None:
        """Subscribe a client to a channel (idempotent)."""
        with self._lock:
            if client_id not in self._clients:
                return
            self._subscriptions.setdefault(client_id, set()).add(channel)
            self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: int, channel: str) -> None:
        """Unsubscribe a client from a channel (idempotent)."""
        with self._lock:
            subs = self._subscriptions.get(client_id)
            if subs is not None:
                subs.discard(channel)
                if not subs:
                    self._subscriptions.pop(client_id, None)
            members = self._channels.get(channel)
            if members is not None:
                members.discard(client_id)
                if not members:
                    self._channels.pop(channel, None)

    def channel_subscribers(self, channel: str) -> list[int]:
        """Return the client IDs currently subscribed to a channel."""
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    def list_channels(self) -> dict[str, int]:
        """Return a mapping of active channel names to their subscriber counts."""
        with self._lock:
            return {
                name: len(members)
                for name, members in sorted(self._channels.items())
                if members
            }

    def client_subscriptions(self, client_id: int) -> list[str]:
        """Return the channels a client is currently subscribed to."""
        with self._lock:
            return sorted(self._subscriptions.get(client_id, set()))


def make_message(message_type: str, payload: dict, timestamp: str | None = None) -> dict:
    """Build a well-formed message."""
    return {
        "type": message_type,
        "payload": payload,
        "timestamp": timestamp or utcnow_iso(),
    }


def message_channel(message: dict) -> str | None:
    """Extract the channel name from a message (top-level or inside payload)."""
    channel = message.get("channel")
    if channel is None:
        payload = message.get("payload")
        if isinstance(payload, dict):
            channel = payload.get("channel")
    return channel


class NotificationServer:
    """WebSocket notification server backed by a pub/sub broker and a store."""

    def __init__(
        self,
        registry: ClientRegistry | None = None,
        broker: Broker | None = None,
        store: MessageStore | None = None,
        transport: BaseTransport | None = None,
    ) -> None:
        self.registry = registry or ClientRegistry()
        self.broker = broker or make_broker()
        self.store = store or MessageStore()
        self.transport = transport or make_transport(self.registry)
        self._broker_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Subscribe to the broker channel and begin delivering messages."""
        self._broker_task = await self.broker.subscribe(
            [BROKER_CHANNEL], self.deliver
        )

    async def close(self) -> None:
        """Stop the broker listener and release resources."""
        await self.broker.close()

    async def send(self, connection, message: dict) -> None:
        """Encode and send a message to a single client via the transport."""
        await self.transport.send_message(connection, message)

    async def broadcast(self, message: dict) -> None:
        """Send a message to every connected client via the transport."""
        await self.transport.broadcast(message)

    async def broadcast_to_channel(self, channel: str, message: dict) -> None:
        """Send a message to every client subscribed to a channel."""
        for client_id in self.registry.channel_subscribers(channel):
            connection = self.registry.get(client_id)
            if connection is None:
                continue
            try:
                await self.transport.send_message(connection, message)
            except Exception:
                self.registry.remove(client_id)

    async def deliver(self, message: dict) -> None:
        """Deliver a broker message to the appropriate local clients."""
        message_type = message.get("type")
        channel = message_channel(message)

        if message_type == "broadcast":
            if channel is not None:
                await self.broadcast_to_channel(channel, message)
            else:
                await self.broadcast(message)
        elif message_type == "direct":
            payload = message.get("payload") or {}
            target = payload.get("to", payload.get("id"))
            target_connection = self.registry.get(target)
            if target_connection is not None:
                await self.send(target_connection, message)

    async def dispatch(self, connection: ServerConnection, client_id: int, message: dict) -> None:
        """Route an incoming message based on its type."""
        message_type = message.get("type")
        message.setdefault("timestamp", utcnow_iso())
        self.store.save(message)

        if message_type == "subscribe":
            channel = message_channel(message)
            if channel is not None:
                self.registry.subscribe(client_id, channel)
                await self._sync_client_state(client_id)
            return
        elif message_type == "unsubscribe":
            channel = message_channel(message)
            if channel is not None:
                self.registry.unsubscribe(client_id, channel)
                await self._sync_client_state(client_id)
            return

        await self.broker.publish(BROKER_CHANNEL, message)

    async def _sync_client_state(self, client_id: int) -> None:
        """Mirror a client's connection/subscription state into the broker."""
        await self.broker.set_client_state(
            client_id,
            {"id": client_id, "channels": self.registry.client_subscriptions(client_id)},
        )

    async def handle(self, connection: ServerConnection) -> None:
        """Handle a single client connection lifecycle via the transport."""
        await self.transport.on_connect(connection)
        client_id = self.registry.add(connection)
        await self.broker.set_client_state(client_id, {"id": client_id, "channels": []})
        try:
            connected = make_message("system", {"event": "connected", "id": client_id})
            self.store.save(connected)
            await self.send(connection, connected)
            async for message in self.transport.receive(connection):
                await self.dispatch(connection, client_id, message)
        finally:
            self.registry.remove(client_id)
            await self.broker.del_client_state(client_id)
            disconnected = make_message("system", {"event": "disconnected", "id": client_id})
            self.store.save(disconnected)
            await self.broadcast(disconnected)
            await self.transport.on_disconnect(connection)

    def process_request(self, connection: ServerConnection, request) -> Response | None:
        """Serve REST endpoints and pass WebSocket upgrades through."""
        headers = Headers({"Content-Type": "application/json"})

        path = request.path
        if "?" in path:
            path, query = path.split("?", 1)
        else:
            query = ""

        if path == "/health":
            body = json.dumps({"connected_clients": self.registry.count()}).encode("utf-8")
            return Response(200, "OK", headers, body)

        if path == "/channels":
            body = json.dumps({"channels": self.registry.list_channels()}).encode("utf-8")
            return Response(200, "OK", headers, body)

        if path == "/messages":
            params = parse_qs(query)
            try:
                limit = int(params.get("limit", ["50"])[0])
            except (TypeError, ValueError):
                limit = 50
            try:
                offset = int(params.get("offset", ["0"])[0])
            except (TypeError, ValueError):
                offset = 0
            messages = self.store.query(limit=limit, offset=offset)
            body = json.dumps({"messages": messages}).encode("utf-8")
            return Response(200, "OK", headers, body)

        prefix = "/channels/"
        suffix = "/subscribers"
        if path.startswith(prefix) and path.endswith(suffix):
            name = path[len(prefix):-len(suffix)]
            body = json.dumps(
                {"subscribers": self.registry.channel_subscribers(name)}
            ).encode("utf-8")
            return Response(200, "OK", headers, body)

        return None


def create_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    redis_url: str | None = None,
    db_url: str | None = None,
    broker: Broker | None = None,
    store: MessageStore | None = None,
):
    """Create a websockets server for a fresh NotificationServer instance."""
    if redis_url is None:
        redis_url = os.environ.get("REDIS_URL")
    if db_url is None:
        db_url = os.environ.get("DATABASE_URL")

    notification_server = NotificationServer(
        broker=broker or make_broker(redis_url),
        store=store or MessageStore(db_url),
    )
    return notification_server, _serve(notification_server, host, port)


async def _serve(notification_server: NotificationServer, host: str, port: int):
    """Start the broker worker, then the WebSocket server."""
    await notification_server.start()
    return await serve(
        notification_server.handle,
        host,
        port,
        process_request=notification_server.process_request,
    )


async def main() -> None:
    notification_server, server = create_server()
    server = await server
    host, port = server.sockets[0].getsockname()[:2]
    print(f"Notification server listening on ws://{host}:{port}")
    await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
