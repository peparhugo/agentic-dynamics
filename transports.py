"""Pluggable transport layer for the notification server.

The core :class:`NotificationServer` is transport-agnostic: it owns routing,
subscriptions, persistence and the Redis backbone, and delegates every
connection-level concern (accepting connections, encoding/decoding wire
frames, and delivering messages) to a :class:`BaseTransport` implementation.

The active transport is selected via the ``TRANSPORT`` environment variable
(or an explicit argument) and defaults to ``websocket``.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

from websockets.asyncio.server import ServerConnection


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


class BaseTransport(ABC):
    """Abstract transport interface used by :class:`NotificationServer`.

    Implementations must provide four methods:

    - :meth:`on_connect` — handle a newly established connection.
    - :meth:`on_disconnect` — handle a closing connection.
    - :meth:`send_message` — deliver a message to a single connection.
    - :meth:`broadcast` — deliver a message to every connected client.
    """

    def __init__(self, server: Any) -> None:
        self.server = server

    @abstractmethod
    async def on_connect(self, connection: Any) -> str:
        """Handle a new connection and return its assigned client id."""

    @abstractmethod
    async def on_disconnect(self, connection: Any, client_id: str) -> None:
        """Handle a connection that is closing."""

    @abstractmethod
    async def send_message(self, connection: Any, message: dict) -> None:
        """Send a single message to a single connection."""

    @abstractmethod
    async def broadcast(self, message: dict) -> None:
        """Send a message to every connected client."""

    async def handle(self, connection: Any) -> None:
        """Run the full lifecycle for a single connection."""
        client_id = await self.on_connect(connection)
        try:
            await self._receive_loop(connection, client_id)
        finally:
            await self.on_disconnect(connection, client_id)

    @abstractmethod
    async def _receive_loop(self, connection: Any, client_id: str) -> None:
        """Receive and route messages for the lifetime of the connection."""


class WebSocketTransport(BaseTransport):
    """WebSocket transport using the ``websockets`` library.

    Every frame is base64-encoded on the wire, mirroring the original wire
    protocol so that client behaviour is unchanged.
    """

    async def on_connect(self, connection: ServerConnection) -> str:
        client_id = str(uuid.uuid4())
        self.server.registry.add(client_id, connection)
        if self.server.bus is not None:
            await self.server.bus.register_client(client_id, self.server.server_id)
        connected = {
            "type": "system",
            "payload": {"event": "connected", "client_id": client_id},
            "timestamp": now_iso(),
        }
        await self.send_message(connection, connected)
        return client_id

    async def on_disconnect(
        self, connection: ServerConnection, client_id: str
    ) -> None:
        self.server.registry.remove(client_id)
        self.server.remove_client(client_id)
        if self.server.bus is not None:
            await self.server.bus.unregister_client(client_id)

    async def send_message(self, connection: ServerConnection, message: dict) -> None:
        await connection.send(encode_message(message))

    async def broadcast(self, message: dict) -> None:
        encoded = encode_message(message)
        for client_id, connection in self.server.registry.items():
            try:
                await connection.send(encoded)
            except Exception:
                self.server.registry.remove(client_id)

    async def _receive_loop(
        self, connection: ServerConnection, client_id: str
    ) -> None:
        async for raw in connection:
            try:
                message = decode_message(raw)
            except (ValueError, TypeError, json.JSONDecodeError, base64.binascii.Error):
                continue
            await self.server.route_message(client_id, message)


TRANSPORTS: dict[str, type[BaseTransport]] = {
    "websocket": WebSocketTransport,
    "ws": WebSocketTransport,
}


def create_transport(name: Optional[str], server: Any) -> BaseTransport:
    """Instantiate the transport selected by ``name`` (or ``TRANSPORT``)."""
    selected = (name or os.environ.get("TRANSPORT", "websocket")).lower()
    try:
        transport_cls = TRANSPORTS[selected]
    except KeyError:
        raise ValueError(f"Unknown transport: {selected!r}") from None
    return transport_cls(server)
