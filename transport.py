"""Pluggable transport layer for the notification server.

The core ``NotificationServer`` is transport-agnostic: it handles message
routing, channel subscriptions, Redis-backed connection state and message
history, while all client-facing I/O is delegated to a Transport
implementation.

Transports expose a small interface:

* ``on_connect`` / ``on_disconnect`` — lifecycle hooks invoked when a client
  connects or disconnects.
* ``send_message`` — deliver a message envelope to a single client.
* ``broadcast`` — deliver a message envelope to every connected client.

The transport also owns the listener (accepting connections) and any
transport-specific HTTP endpoints such as the REST hooks served by the
WebSocket transport.

The active transport is selected through the ``TRANSPORT`` environment
variable (default ``websocket``). New transports (SSE, polling, raw TCP)
can be added by subclassing ``BaseTransport`` and registering them in
``create_transport``.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Optional

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from messages import build_message, serialize

logger = logging.getLogger("notification_server")


class BaseTransport(ABC):
    """
    Abstract transport for the notification server.

    Concrete transports implement ``start``/``close`` to manage the listener,
    ``send_message``/``broadcast`` to push message envelopes to clients, and
    ``bound_port`` to report the port actually bound. The per-connection
    handler must call ``on_connect``/``on_disconnect`` so the core server can
    keep its registry and Redis state consistent.
    """

    name = "base"

    def __init__(
        self,
        server: Any,
        host: str = "127.0.0.1",
        port: int = 8765,
    ) -> None:
        self.server = server
        self.host = host
        self.port = port

    @abstractmethod
    async def start(self) -> None:
        """Bind the listener and start accepting connections."""

    @abstractmethod
    async def close(self) -> None:
        """Stop the listener and release transport resources."""

    @abstractmethod
    async def send_message(self, client_id: str, message: dict) -> bool:
        """Send a message envelope to a single client.

        Returns True on success and False if the client is gone.
        """

    @abstractmethod
    async def broadcast(self, message: dict) -> int:
        """Deliver a message envelope to every connected client.

        Returns the number of clients the message was delivered to.
        """

    @property
    @abstractmethod
    def bound_port(self) -> int:
        """Return the port the transport is bound to."""

    @property
    def url(self) -> str:
        """Return the client-facing URL of this transport."""
        return f"ws://{self.host}:{self.bound_port}"

    async def on_connect(self, connection: Any, client_id: str) -> None:
        """Register a connected client with the core server.

        Subclasses may override this to perform transport-specific connection
        work; the default registers the client, publishes its connection state
        and notifies it of its assigned id.
        """
        await self.server.on_client_connect(client_id, connection)
        await self.send_message(
            client_id,
            build_message("system", {"event": "connected", "client_id": client_id}),
        )
        logger.info("client %s connected", client_id)

    async def on_disconnect(self, client_id: str) -> None:
        """Clean up a disconnected client in the core server."""
        await self.server.on_client_disconnect(client_id)
        logger.info("client %s disconnected", client_id)


class WebSocketTransport(BaseTransport):
    """WebSocket transport backed by the ``websockets`` library.

    This is the default transport. It serves the same REST endpoints
    (``/health``, ``/channels``, ``/channels/<name>/subscribers``,
    ``/messages``) through the ``process_request`` hook, so a single asyncio
    event loop handles both WebSocket and plain HTTP traffic.
    """

    name = "websocket"

    def __init__(
        self,
        server: Any,
        host: str = "127.0.0.1",
        port: int = 8765,
    ) -> None:
        super().__init__(server, host, port)
        self._server: Optional[Server] = None

    async def start(self) -> None:
        """Bind the WebSocket listener and start accepting connections."""
        if self._server is not None:
            return
        self._server = await serve(
            self._connection_handler,
            self.host,
            self.port,
            process_request=self.server.process_http_request,
        )

    async def close(self) -> None:
        """Stop the WebSocket listener."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    @property
    def bound_port(self) -> int:
        if self._server is not None and self._server.sockets:
            return self._server.sockets[0].getsockname()[1]
        return self.port

    async def send_message(self, client_id: str, message: dict) -> bool:
        """Send a message envelope to a single connected client."""
        websocket = await self.server.registry.get(client_id)
        if websocket is None:
            return False
        try:
            await websocket.send(serialize(message))
            return True
        except (ConnectionClosed, ConnectionError, OSError):
            return False

    async def broadcast(self, message: dict) -> int:
        """Deliver a message envelope to every connected client."""
        delivered = 0
        for client_id, websocket in (await self.server.registry.snapshot()).items():
            if await self.send_message(client_id, message):
                delivered += 1
            else:
                await self.server.registry.remove(client_id)
        return delivered

    async def _connection_handler(self, websocket: ServerConnection) -> None:
        """Handle a single WebSocket client connection."""
        client_id = await self.server.next_client_id()
        await self.on_connect(websocket, client_id)
        try:
            async for raw in websocket:
                await self.server.handle_client_message(client_id, raw)
        except ConnectionClosed:
            pass
        finally:
            await self.on_disconnect(client_id)


_TRANSPORTS: dict[str, type[BaseTransport]] = {
    WebSocketTransport.name: WebSocketTransport,
}


def create_transport(
    server: Any,
    host: str = "127.0.0.1",
    port: int = 8765,
    name: Optional[str] = None,
) -> BaseTransport:
    """Instantiate the transport selected by the ``TRANSPORT`` env var.

    Unknown or unset values fall back to the default WebSocket transport.
    """
    selected = (name or os.environ.get("TRANSPORT") or "").strip().lower()
    cls = _TRANSPORTS.get(selected, WebSocketTransport)
    return cls(server, host, port)
