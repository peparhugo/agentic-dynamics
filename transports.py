"""Transport implementations for the notification server."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Iterable
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from websockets.asyncio.server import Server, ServerConnection, serve

if TYPE_CHECKING:
    from app import NotificationServer


class BaseTransport(ABC):
    """Carries notifications between a client connection and the server."""

    @abstractmethod
    async def on_connect(self, server: NotificationServer, connection: Any) -> None:
        """Handle a newly connected client until it disconnects."""

    @abstractmethod
    async def on_disconnect(self, server: NotificationServer, client_id: str) -> None:
        """Release transport resources for a disconnected client."""

    @abstractmethod
    async def send_message(self, connection: Any, message: str) -> None:
        """Send one serialized notification to a connection."""

    @abstractmethod
    async def broadcast(self, connections: Iterable[Any], message: str) -> None:
        """Send one serialized notification to multiple connections."""

    async def start(self, server: NotificationServer, host: str, port: int) -> Any:
        """Start accepting connections for this transport."""
        raise NotImplementedError(f"{type(self).__name__} does not implement server startup")


class WebSocketTransport(BaseTransport):
    """WebSocket implementation preserving the server's existing wire protocol."""

    async def on_connect(self, server: NotificationServer, connection: ServerConnection) -> None:
        client_id = await server._register_connection(connection)
        try:
            await self.send_message(connection, server.welcome_message(client_id))
            async for raw_message in connection:
                await server.handle_message(client_id, raw_message)
        finally:
            await self.on_disconnect(server, client_id)

    async def on_disconnect(self, server: NotificationServer, client_id: str) -> None:
        await server._unregister_connection(client_id)

    async def send_message(self, connection: ServerConnection, message: str) -> None:
        with suppress(Exception):
            await connection.send(message)

    async def broadcast(self, connections: Iterable[ServerConnection], message: str) -> None:
        await asyncio.gather(
            *(self.send_message(connection, message) for connection in connections),
            return_exceptions=True,
        )

    async def start(self, server: NotificationServer, host: str, port: int) -> Server:
        return await serve(server.handler, host, port, process_request=server.process_request)
