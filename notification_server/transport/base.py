"""Pluggable transport interface.

A Transport owns the wire-level mechanics of one specific delivery mechanism
(WebSocket, SSE, long-polling, raw TCP, ...): accepting connections, tracking
which client_id maps to which live connection, and sending already-encoded
messages to one or many clients. It knows nothing about notification
semantics (broadcast/direct/system/channels) — that lives in
NotificationServer, which reacts to the transport's connect/message/
disconnect callbacks and pushes encoded strings back out through
send_message()/broadcast().
"""

from abc import ABC, abstractmethod

from ..registry import ClientRegistry


class BaseTransport(ABC):
    def __init__(self):
        self.registry = ClientRegistry()
        # Wired up by NotificationServer after construction. Each is an
        # async callable invoked by the transport as connections come and go.
        self.on_client_connect = None  # async (client_id) -> None
        self.on_client_message = None  # async (client_id, raw) -> None
        self.on_client_disconnect = None  # async (client_id) -> None

    @abstractmethod
    async def start(self, host, port, http_handler=None):
        """Start accepting connections on host:port.

        `http_handler`, if given, is an optional plain-HTTP request hook
        used for REST endpoints served alongside the transport's own
        protocol. Returns an implementation-defined handle (e.g. the
        underlying server object) for introspection and shutdown.
        """

    @abstractmethod
    async def stop(self):
        """Stop accepting new connections and release resources."""

    async def on_connect(self, raw_connection) -> str:
        """Register a newly established raw connection and return its
        client_id."""
        client_id = self.registry.add(raw_connection)
        if self.on_client_connect is not None:
            await self.on_client_connect(client_id)
        return client_id

    async def on_disconnect(self, client_id) -> None:
        """Release bookkeeping for a closed connection."""
        self.registry.remove(client_id)
        if self.on_client_disconnect is not None:
            await self.on_client_disconnect(client_id)

    @abstractmethod
    async def send_message(self, client_id, data) -> bool:
        """Send raw encoded data to a single connected client. Returns False
        (without raising) if the client is unknown or its connection is
        already closed."""

    @abstractmethod
    async def broadcast(self, client_ids, data) -> None:
        """Send raw encoded data concurrently to many connected clients."""
