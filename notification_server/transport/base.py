"""Transport interface: decouples NotificationServer's core routing logic
(registry, presence, persistence, Redis bus, message semantics) from the
mechanics of any one wire protocol.

A transport owns everything protocol-specific: accepting connections,
framing/parsing on the wire, detecting disconnects, and (optionally) serving
plain HTTP endpoints alongside the main protocol. It knows nothing about
notifications, channels, or clients -- it only ferries opaque "connection"
objects and JSON-serializable message dicts.

NotificationServer talks to a transport in two directions:

  - Outbound: it calls `send_message()` / `broadcast()` to deliver messages.
  - Inbound: it registers callbacks via `on_connect()`, `on_message()`, and
    `on_disconnect()`, which the transport invokes as connection lifecycle
    events happen. This is the seam that lets a brand new transport (SSE,
    long-polling, raw TCP, ...) plug in without NotificationServer changing
    at all -- it only ever deals with connection objects and dicts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable

ConnectHandler = Callable[[Any], Awaitable[None]]
MessageHandler = Callable[[Any, Any], Awaitable[None]]
DisconnectHandler = Callable[[Any], Awaitable[None]]
HttpHandler = Callable[[str, dict], Awaitable[dict | None]]


class BaseTransport(ABC):
    """Abstract base for pluggable notification transports."""

    def __init__(self) -> None:
        self._connect_handler: ConnectHandler | None = None
        self._message_handler: MessageHandler | None = None
        self._disconnect_handler: DisconnectHandler | None = None
        self._http_handler: HttpHandler | None = None

    # -- callback registration (concrete: shared by every transport) ----

    def on_connect(self, handler: ConnectHandler) -> None:
        """Register `await handler(connection)`, invoked once a new
        connection is established, before any messages are read from it."""
        self._connect_handler = handler

    def on_message(self, handler: MessageHandler) -> None:
        """Register `await handler(connection, raw_message)`, invoked for
        every inbound message a connection sends."""
        self._message_handler = handler

    def on_disconnect(self, handler: DisconnectHandler) -> None:
        """Register `await handler(connection)`, invoked once a connection
        has closed (cleanly or otherwise)."""
        self._disconnect_handler = handler

    def set_http_handler(self, handler: HttpHandler) -> None:
        """Register `await handler(path, query) -> dict | None` for plain
        HTTP requests served alongside the main protocol, if the transport
        supports it. Transports without an HTTP surface (e.g. raw TCP) may
        simply never call it."""
        self._http_handler = handler

    # -- lifecycle (transport-specific) ----------------------------------

    @abstractmethod
    async def start(self, host: str, port: int) -> None:
        """Bind to `host`/`port` and begin accepting connections."""

    @abstractmethod
    def stop(self) -> None:
        """Stop accepting new connections and begin shutting down."""

    @abstractmethod
    async def wait_closed(self) -> None:
        """Wait for shutdown to finish and release any held resources."""

    @property
    @abstractmethod
    def bound_port(self) -> int:
        """The actual port bound to (useful when started with port=0)."""

    # -- outbound delivery (transport-specific) --------------------------

    @abstractmethod
    async def send_message(self, connection: Any, message: dict) -> None:
        """Send a single JSON-serializable message to one connection."""

    async def broadcast(self, connections: list, message: dict) -> None:
        """Send a single JSON-serializable message to many connections.

        Default implementation delivers sequentially via `send_message()`;
        transports may override for a more efficient fan-out.
        """
        for connection in connections:
            await self.send_message(connection, message)
