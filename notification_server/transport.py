"""Pluggable transport layer for the notification server.

`NotificationServer` never touches a raw connection object (a WebSocket, an
SSE stream, a TCP socket, ...) directly -- it only ever calls the four
methods on `BaseTransport`. That's what lets a new transport mechanism be
added by writing a new `BaseTransport` subclass, without changing any of the
routing/broadcast/subscription logic in `NotificationServer`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable

from .messages import Message


class BaseTransport(ABC):
    """A pluggable delivery mechanism: owns the raw client connections and
    knows how to actually get a message to (or drop a connection for) one
    or more clients, addressed only by client id."""

    def __init__(self) -> None:
        self.server: Any = None

    def bind(self, server: Any) -> None:
        """Give the transport a reference back to the `NotificationServer`
        that owns it, so connection-handling code specific to this
        transport (e.g. an HTTP entry point) can call into core routing and
        state. Transports that don't need this may ignore it."""
        self.server = server

    @abstractmethod
    async def on_connect(self, client_id: str, connection: Any) -> None:
        """Register a newly-accepted `connection` under `client_id`."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Forget the connection previously registered for `client_id`."""

    @abstractmethod
    async def send_message(self, client_id: str, message: Message) -> None:
        """Deliver `message` to a single client. Must be a no-op (not an
        error) if `client_id` isn't connected to this transport instance."""

    @abstractmethod
    async def broadcast(self, client_ids: Iterable[str] | None, message: Message) -> None:
        """Deliver `message` to every client id in `client_ids`, or to all
        currently-connected clients if `client_ids` is None. Unknown or
        already-disconnected ids are silently skipped."""


def build_transport(name: str | None = None) -> BaseTransport:
    """Build the transport selected by `name` (or the TRANSPORT env var,
    defaulting to "websocket")."""
    from .config import transport_name
    from .websocket_transport import WebSocketTransport

    resolved = (name or transport_name()).strip().lower()
    if resolved == "websocket":
        return WebSocketTransport()
    raise ValueError(f"unknown transport '{resolved}'")
