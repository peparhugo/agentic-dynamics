"""WebSocket-based notification server.

Core features:
- Accept WebSocket connections and assign each client a unique ID.
- Broadcast messages to all connected clients.
- Route ``direct`` messages to a single client.
- Subscribe/unsubscribe clients to named channels.
- Route messages carrying a ``channel`` field only to that channel's
  subscribers.
- Cleanly remove clients on disconnect.
- REST endpoints ``GET /health``, ``GET /channels`` and
  ``GET /channels/{name}/subscribers``.

All messages use the JSON envelope ``{type, payload, timestamp}``.
The websockets transport base64-encodes every frame, so incoming frames are
base64-decoded before JSON parsing and outgoing frames are base64-encoded
before being sent.
"""

from __future__ import annotations

import asyncio
import base64
import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from websockets.asyncio.server import ServerConnection, serve
from websockets.http11 import Headers, Request, Response

SUPPORTED_TYPES = ("broadcast", "direct", "system", "subscribe", "unsubscribe")


def now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def encode_message(message: dict) -> str:
    """Serialize a message to JSON and base64-encode it for the wire."""
    return base64.b64encode(json.dumps(message).encode("utf-8")).decode("ascii")


def decode_message(raw: Any) -> dict:
    """Base64-decode an incoming frame and parse it as JSON."""
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    return json.loads(base64.b64decode(raw).decode("utf-8"))


class ClientRegistry:
    """Thread-safe registry of connected WebSocket clients."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = threading.Lock()

    def add(self, client_id: str, connection: ServerConnection) -> None:
        with self._lock:
            self._clients[client_id] = connection

    def remove(self, client_id: str) -> Optional[ServerConnection]:
        with self._lock:
            return self._clients.pop(client_id, None)

    def get(self, client_id: str) -> Optional[ServerConnection]:
        with self._lock:
            return self._clients.get(client_id)

    def items(self) -> list[tuple[str, ServerConnection]]:
        with self._lock:
            return list(self._clients.items())

    def ids(self) -> list[str]:
        with self._lock:
            return list(self._clients.keys())

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)

    def __contains__(self, client_id: str) -> bool:
        with self._lock:
            return client_id in self._clients


class NotificationServer:
    """WebSocket notification server."""

    def __init__(self) -> None:
        self.registry = ClientRegistry()
        self._subscriptions: dict[str, set[str]] = {}
        self._sub_lock = threading.Lock()

    # ── Channel subscription bookkeeping ─────────────────────────

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._sub_lock:
            self._subscriptions.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._sub_lock:
            subscribers = self._subscriptions.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                self._subscriptions.pop(channel, None)

    def remove_client(self, client_id: str) -> None:
        """Drop a client from every channel (used on disconnect)."""
        with self._sub_lock:
            for channel in list(self._subscriptions):
                subscribers = self._subscriptions[channel]
                subscribers.discard(client_id)
                if not subscribers:
                    self._subscriptions.pop(channel, None)

    def channel_subscribers(self, channel: str) -> list[str]:
        with self._sub_lock:
            return sorted(self._subscriptions.get(channel, set()))

    def channels(self) -> dict[str, int]:
        """Return active channels mapped to their subscriber counts."""
        with self._sub_lock:
            return {
                channel: len(subscribers)
                for channel, subscribers in self._subscriptions.items()
            }

    @staticmethod
    def _channel_of(message: dict) -> Optional[str]:
        """Extract a channel name from a message (top-level or payload)."""
        channel = message.get("channel")
        if channel is None:
            payload = message.get("payload")
            if isinstance(payload, dict):
                channel = payload.get("channel")
        if isinstance(channel, str) and channel:
            return channel
        return None

    async def handler(self, connection: ServerConnection) -> None:
        """Handle a single client connection for its full lifetime."""
        client_id = str(uuid.uuid4())
        self.registry.add(client_id, connection)
        try:
            connected = {
                "type": "system",
                "payload": {"event": "connected", "client_id": client_id},
                "timestamp": now_iso(),
            }
            await connection.send(encode_message(connected))

            async for raw in connection:
                try:
                    message = decode_message(raw)
                except (ValueError, TypeError, json.JSONDecodeError, base64.binascii.Error):
                    continue
                await self.route_message(client_id, message)
        finally:
            self.registry.remove(client_id)
            self.remove_client(client_id)

    async def route_message(self, sender_id: str, message: dict) -> None:
        """Route an inbound message based on its type."""
        mtype = message.get("type")
        if not isinstance(message, dict) or mtype not in SUPPORTED_TYPES:
            return

        message.setdefault("timestamp", now_iso())

        if mtype == "subscribe":
            channel = self._channel_of(message)
            if channel:
                self.subscribe(sender_id, channel)
            return
        elif mtype == "unsubscribe":
            channel = self._channel_of(message)
            if channel:
                self.unsubscribe(sender_id, channel)
            return

        channel = self._channel_of(message)
        if channel:
            await self.send_to_channel(channel, message)
        elif mtype == "broadcast":
            await self.broadcast(message)
        elif mtype == "direct":
            payload = message.get("payload") or {}
            target_id = payload.get("to") or payload.get("client_id")
            if target_id:
                await self.send_to(target_id, message)
        elif mtype == "system":
            await self.broadcast(message)

    async def broadcast(self, message: dict) -> None:
        """Send a message to every connected client."""
        encoded = encode_message(message)
        for client_id, connection in self.registry.items():
            try:
                await connection.send(encoded)
            except Exception:
                self.registry.remove(client_id)

    async def send_to_channel(self, channel: str, message: dict) -> None:
        """Send a message only to subscribers of the given channel."""
        encoded = encode_message(message)
        for client_id in self.channel_subscribers(channel):
            connection = self.registry.get(client_id)
            if connection is None:
                self.unsubscribe(client_id, channel)
                continue
            try:
                await connection.send(encoded)
            except Exception:
                self.registry.remove(client_id)
                self.unsubscribe(client_id, channel)

    async def send_to(self, target_id: str, message: dict) -> bool:
        """Send a message to a single client. Returns True if delivered."""
        connection = self.registry.get(target_id)
        if connection is None:
            return False
        await connection.send(encode_message(message))
        return True

    def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Optional[Response]:
        """Serve the REST endpoints."""
        path = request.path

        if path == "/health":
            body = json.dumps({"connected_clients": len(self.registry)}).encode("utf-8")
            headers = Headers([("Content-Type", "application/json")])
            return Response(200, "OK", headers, body)

        if path == "/channels":
            body = json.dumps(self.channels()).encode("utf-8")
            headers = Headers([("Content-Type", "application/json")])
            return Response(200, "OK", headers, body)

        prefix = "/channels/"
        suffix = "/subscribers"
        if path.startswith(prefix) and path.endswith(suffix):
            name = path[len(prefix):-len(suffix)]
            if name:
                body = json.dumps(self.channel_subscribers(name)).encode("utf-8")
                headers = Headers([("Content-Type", "application/json")])
                return Response(200, "OK", headers, body)

        return None


async def main(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = NotificationServer()
    async with serve(
        server.handler, host, port, process_request=server.process_request
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
