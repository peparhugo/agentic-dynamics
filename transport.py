"""Pluggable transport layer for the notification server.

The core :class:`NotificationServer` depends only on :class:`BaseTransport`, so
new wire protocols (SSE, long-polling, raw TCP, ...) can be added by
implementing a transport and selecting it via the ``TRANSPORT`` environment
variable. ``WebSocketTransport`` is the default.
"""

import base64
import json
import os
from abc import ABC, abstractmethod


def encode_message(message: dict) -> str:
    """Serialize a message to JSON and base64-encode it for the wire."""
    return base64.b64encode(json.dumps(message).encode("utf-8")).decode("ascii")


def decode_message(raw: str) -> dict:
    """Base64-decode an incoming frame and parse it as JSON."""
    return json.loads(base64.b64decode(raw.encode("ascii")).decode("utf-8"))


class BaseTransport(ABC):
    """Abstract interface for a notification transport.

    A transport owns the wire-format details (how to send and receive messages)
    while the core server owns routing, subscriptions, and persistence.
    """

    def __init__(self, registry) -> None:
        self.registry = registry

    @abstractmethod
    async def on_connect(self, connection) -> None:
        """Perform transport-specific work when a client connects."""
        raise NotImplementedError

    @abstractmethod
    async def on_disconnect(self, connection) -> None:
        """Perform transport-specific work when a client disconnects."""
        raise NotImplementedError

    @abstractmethod
    async def send_message(self, connection, message: dict) -> None:
        """Send a single message to one client."""
        raise NotImplementedError

    @abstractmethod
    async def broadcast(self, message: dict) -> None:
        """Send a message to every connected client."""
        raise NotImplementedError

    @abstractmethod
    async def receive(self, connection):
        """Yield decoded messages received from a client."""
        raise NotImplementedError


class WebSocketTransport(BaseTransport):
    """WebSocket transport: base64 JSON frames over a websockets connection."""

    async def on_connect(self, connection) -> None:
        return None

    async def on_disconnect(self, connection) -> None:
        return None

    async def send_message(self, connection, message: dict) -> None:
        await connection.send(encode_message(message))

    async def broadcast(self, message: dict) -> None:
        for client_id, connection in self.registry.snapshot():
            try:
                await self.send_message(connection, message)
            except Exception:
                self.registry.remove(client_id)

    async def receive(self, connection):
        async for raw in connection:
            yield decode_message(raw)


_TRANSPORTS = {
    "websocket": WebSocketTransport,
}


def make_transport(registry, name: str | None = None) -> BaseTransport:
    """Build a transport from the TRANSPORT env var, defaulting to WebSocket."""
    if name is None:
        name = os.environ.get("TRANSPORT") or "websocket"
    name = name.strip().lower()
    transport_cls = _TRANSPORTS.get(name)
    if transport_cls is None:
        raise ValueError(f"Unknown TRANSPORT: {name!r}")
    return transport_cls(registry)
