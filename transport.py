"""
Pluggable transport layer for the notification server.

The core ``NotificationServer`` is transport-agnostic: it owns the client
registry, message routing, Redis backbone, and persistence, and delegates all
network I/O to a ``BaseTransport`` implementation.  Additional transports
(SSE, polling, raw TCP) can be added by subclassing ``BaseTransport`` and
registering the class in ``TRANSPORT_REGISTRY`` without touching the core.

The transport is selected at runtime via the ``TRANSPORT`` environment
variable (or by passing a transport to ``NotificationServer``).  The default
transport is ``WebSocketTransport``.

Wire format
-----------
``WebSocketTransport`` base64-encodes every JSON message before it is sent and
base64-decodes every incoming frame before it is parsed as JSON.
"""

from __future__ import annotations

import base64
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict

from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.http11 import Response


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def encode_message(message: Dict[str, Any]) -> str:
    """Serialize a message to the on-the-wire base64 string."""
    raw = json.dumps(message).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def decode_message(raw: str) -> Dict[str, Any]:
    """Parse a base64 on-the-wire string back into a message dict."""
    data = base64.b64decode(raw.encode("ascii"))
    return json.loads(data.decode("utf-8"))


class BaseTransport(ABC):
    """Abstract interface every transport implementation must provide."""

    def __init__(self, server: "NotificationServer") -> None:
        self.server = server

    @abstractmethod
    async def start(self, host: str, port: int) -> None:
        """Start listening for incoming client connections."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop listening and release any transport resources."""

    @property
    @abstractmethod
    def port(self) -> int | None:
        """The bound port, or ``None`` before start/after stop."""

    @abstractmethod
    async def on_connect(self, connection: Any) -> None:
        """Transport hook invoked when a client connects."""

    @abstractmethod
    async def on_disconnect(self, connection: Any) -> None:
        """Transport hook invoked when a client disconnects."""

    @abstractmethod
    async def send_message(self, connection: Any, message: Dict[str, Any]) -> None:
        """Send a single message to one connection."""

    @abstractmethod
    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Send a message to every connected client."""


class WebSocketTransport(BaseTransport):
    """WebSocket transport built on the ``websockets`` library."""

    def __init__(self, server: "NotificationServer") -> None:
        super().__init__(server)
        self._server = None

    async def start(self, host: str, port: int) -> None:
        self._server = await serve(
            self._handle_connection,
            host,
            port,
            process_request=self._process_request,
        )

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    @property
    def port(self) -> int | None:
        if self._server is None or not self._server.sockets:
            return None
        return self._server.sockets[0].getsockname()[1]

    async def on_connect(self, connection: Any) -> None:
        # The WebSocket handshake is already complete; nothing extra to do.
        return None

    async def on_disconnect(self, connection: Any) -> None:
        # websockets closes the connection automatically.
        return None

    async def send_message(self, connection: Any, message: Dict[str, Any]) -> None:
        await connection.send(encode_message(message))

    async def broadcast(self, message: Dict[str, Any]) -> None:
        encoded = encode_message(message)
        for connection in self.server.clients.snapshot().values():
            try:
                await connection.send(encoded)
            except Exception:
                continue

    def _process_request(self, connection: Any, request: Any) -> Response | None:
        body = self.server._handle_http_request(request.path)
        if body is None:
            return None
        headers = Headers([("Content-Type", "application/json")])
        return Response(200, "OK", headers, body.encode("utf-8"))

    async def _handle_connection(self, websocket: Any) -> None:
        client_id = await self.server.broker.next_client_id()
        self.server.clients.register(websocket, client_id)
        await self.server.broker.register_client(client_id, self.server.instance_id)
        try:
            await self.on_connect(websocket)
            await self.send_message(
                websocket,
                {
                    "type": "system",
                    "payload": {"client_id": client_id, "message": "connected"},
                    "timestamp": utcnow(),
                },
            )
            async for raw in websocket:
                try:
                    message = decode_message(raw)
                except (ValueError, TypeError):
                    continue
                await self.server._handle_message(client_id, message)
        finally:
            await self.on_disconnect(websocket)
            self.server.clients.unregister(client_id)
            await self.server.broker.unregister_client(client_id)


TRANSPORT_REGISTRY: Dict[str, type] = {
    "websocket": WebSocketTransport,
    "ws": WebSocketTransport,
}

DEFAULT_TRANSPORT = "websocket"


def create_transport(name: str | None, server: "NotificationServer") -> BaseTransport:
    """Instantiate the transport registered under ``name``."""
    key = (name or DEFAULT_TRANSPORT).lower()
    cls = TRANSPORT_REGISTRY.get(key)
    if cls is None:
        raise ValueError(f"unknown transport: {key!r}")
    return cls(server)
