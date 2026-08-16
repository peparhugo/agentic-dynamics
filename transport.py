"""Pluggable transport layer for the notification server.

The core notification logic is transport-agnostic. It talks to connected
clients exclusively through a :class:`BaseTransport` implementation, so new
transport mechanisms (SSE, polling, raw TCP, ...) can be added without
touching the core server.

The WebSocket transport is the default implementation. A transport is
selected at runtime via the ``TRANSPORT`` environment variable (or by passing
an explicit transport instance to :class:`NotificationServer`).
"""

from abc import ABC, abstractmethod
import uuid
from typing import Any

from websockets.asyncio.server import ServerConnection, serve


class BaseTransport(ABC):
    """Abstract interface every transport must implement.

    The four core operations are:

    * :meth:`on_connect` / :meth:`on_disconnect` — register/unregister a
      client connection.
    * :meth:`send_message` — deliver a message to a single client.
    * :meth:`broadcast` — deliver a message to every connected client.

    ``send_message`` and ``broadcast`` receive an already serialized
    (JSON-encoded) message payload; the transport's only job is to move bytes
    to the client using the appropriate wire framing.
    """

    def __init__(
        self, server: Any, host: str = "127.0.0.1", port: int = 8765
    ) -> None:
        self.server = server
        self.host = host
        self.port = port

    @abstractmethod
    async def start(self) -> None:
        """Start accepting incoming connections."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop accepting connections and release all resources."""

    @abstractmethod
    async def serve_forever(self) -> None:
        """Run the transport until :meth:`stop` is called."""

    @abstractmethod
    async def on_connect(self, client_id: str, connection: Any) -> None:
        """Register a newly established client connection."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Unregister and clean up a client connection."""

    @abstractmethod
    async def send_message(self, client_id: str, data: str) -> bool:
        """Send an encoded message to a single client."""

    @abstractmethod
    async def broadcast(self, data: str) -> int:
        """Broadcast an encoded message to all connected clients."""

    @abstractmethod
    def has_client(self, client_id: str) -> bool:
        """Return whether ``client_id`` is currently connected."""

    @abstractmethod
    def client_ids(self) -> list[str]:
        """Return the IDs of all currently connected clients."""

    @property
    @abstractmethod
    def client_count(self) -> int:
        """Return the number of currently connected clients."""


class WebSocketTransport(BaseTransport):
    """WebSocket transport implementation built on the ``websockets`` library."""

    def __init__(
        self, server: Any, host: str = "127.0.0.1", port: int = 8765
    ) -> None:
        super().__init__(server, host, port)
        self._clients: dict[str, ServerConnection] = {}
        self._server = None

    async def start(self) -> None:
        self._server = await serve(
            self._handler,
            self.host,
            self.port,
            process_request=self.server.process_request,
        )
        if self.port == 0:
            self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def serve_forever(self) -> None:
        if self._server is not None:
            await self._server.serve_forever()

    async def _handler(self, websocket: ServerConnection) -> None:
        client_id = str(uuid.uuid4())
        await self.on_connect(client_id, websocket)
        await self.server.on_client_connected(client_id)
        try:
            async for raw in websocket:
                await self.server.on_client_message(client_id, raw)
        finally:
            await self.server.on_client_disconnected(client_id)

    async def on_connect(self, client_id: str, connection: Any) -> None:
        self._clients[client_id] = connection

    async def on_disconnect(self, client_id: str) -> None:
        self._clients.pop(client_id, None)

    async def send_message(self, client_id: str, data: str) -> bool:
        ws = self._clients.get(client_id)
        if ws is None:
            return False
        await ws.send(data)
        return True

    async def broadcast(self, data: str) -> int:
        delivered = 0
        stale: list[str] = []
        for client_id, ws in list(self._clients.items()):
            try:
                await ws.send(data)
                delivered += 1
            except Exception:
                stale.append(client_id)
        for client_id in stale:
            await self.server._drop_client(client_id)
        return delivered

    def has_client(self, client_id: str) -> bool:
        return client_id in self._clients

    def client_ids(self) -> list[str]:
        return list(self._clients.keys())

    @property
    def client_count(self) -> int:
        return len(self._clients)
