"""Transport implementations for the notification server."""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from websockets.asyncio.server import Server, ServerConnection, serve


class BaseTransport(ABC):
    """Interface used by the notification server to deliver messages."""

    def __init__(self) -> None:
        self.clients: dict[str, Any] = {}

    @abstractmethod
    async def on_connect(self, client_id: str, client: Any) -> None:
        """Register a newly connected client."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Unregister a disconnected client."""

    @abstractmethod
    async def send_message(self, client_id: str, message: str) -> None:
        """Send a message to one client."""

    @abstractmethod
    async def broadcast(self, message: str, client_ids: Iterable[str]) -> None:
        """Send a message to a collection of clients."""

    async def start(
        self,
        handler: Callable[[Any], Awaitable[None]],
        host: str,
        port: int,
    ) -> None:
        """Start the transport listener, when the transport has one."""
        del handler, host, port

    async def stop(self) -> None:
        """Stop the transport listener, when the transport has one."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport."""

    def __init__(self) -> None:
        super().__init__()
        self.server: Server | None = None

    async def on_connect(self, client_id: str, client: ServerConnection) -> None:
        self.clients[client_id] = client

    async def on_disconnect(self, client_id: str) -> None:
        self.clients.pop(client_id, None)

    async def send_message(self, client_id: str, message: str) -> None:
        client = self.clients.get(client_id)
        if client is not None:
            await client.send(message)

    async def broadcast(self, message: str, client_ids: Iterable[str]) -> None:
        clients = tuple(
            self.clients[client_id] for client_id in client_ids if client_id in self.clients
        )
        if not clients:
            return
        await asyncio.gather(
            *(client.send(message) for client in clients), return_exceptions=True
        )

    async def start(
        self,
        handler: Callable[[ServerConnection], Awaitable[None]],
        host: str,
        port: int,
    ) -> None:
        self.server = await serve(handler, host, port)

    async def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
