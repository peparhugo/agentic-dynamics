"""Transport implementations used by the notification server."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable
from uuid import uuid4

from websockets.asyncio.server import Server, ServerConnection, serve


ConnectHandler = Callable[[str, Any], Awaitable[None]]
DisconnectHandler = Callable[[str], Awaitable[None]]
MessageHandler = Callable[[str, str], Awaitable[None]]


class BaseTransport(ABC):
    """The asynchronous transport contract used by notification routing."""

    @abstractmethod
    async def on_connect(self, client_id: str, connection: Any) -> None:
        """Register a newly connected client."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Remove a disconnected client."""

    @abstractmethod
    async def send_message(self, client_id: str, message: str) -> None:
        """Send a wire-format message to one client."""

    @abstractmethod
    async def broadcast(self, message: str, client_ids: list[str]) -> None:
        """Send a wire-format message to a set of clients."""

    async def start(self) -> None:
        """Start the transport, if it has a listener."""

    async def stop(self) -> None:
        """Stop the transport, if it has a listener."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport."""

    def __init__(self, host: str, port: int, on_message: MessageHandler,
                 on_connect: ConnectHandler, on_disconnect: DisconnectHandler) -> None:
        self.host = host
        self.port = port
        self._on_message = on_message
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._connections: dict[str, ServerConnection] = {}
        self._server: Server | None = None

    async def start(self) -> None:
        self._server = await serve(self._handle_connection, self.host, self.port)
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self._connections.clear()

    async def on_connect(self, client_id: str, connection: ServerConnection) -> None:
        self._connections[client_id] = connection

    async def on_disconnect(self, client_id: str) -> None:
        self._connections.pop(client_id, None)

    async def send_message(self, client_id: str, message: str) -> None:
        connection = self._connections.get(client_id)
        if connection is not None:
            await connection.send(message)

    async def broadcast(self, message: str, client_ids: list[str]) -> None:
        await asyncio.gather(*(self.send_message(client_id, message) for client_id in client_ids),
                             return_exceptions=True)

    async def _handle_connection(self, connection: ServerConnection) -> None:
        client_id = await self._register(connection)
        try:
            async for raw_message in connection:
                await self._on_message(client_id, raw_message)
        except Exception:
            pass
        finally:
            await self._on_disconnect(client_id)
            await self.on_disconnect(client_id)

    async def _register(self, connection: ServerConnection) -> str:
        # The server owns the ID so every transport presents the same identity API.
        client_id = str(uuid4())
        while client_id in self._connections:
            client_id = f"{client_id}-1"
        await self.on_connect(client_id, connection)
        await self._on_connect(client_id, connection)
        return client_id
