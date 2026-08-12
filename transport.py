"""Transport implementations for the notification server."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Iterable

from websockets.asyncio.server import Request, Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Response


class BaseTransport(ABC):
    """Interface used by the notification logic to communicate with clients."""

    @abstractmethod
    async def on_connect(self, client_id: str, connection: Any) -> None:
        """Register a newly connected client."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Remove a disconnected client."""

    @abstractmethod
    async def send_message(self, client_id: str, message: str) -> bool:
        """Send a message and report whether the client is still available."""

    @abstractmethod
    async def broadcast(self, message: str, client_ids: Iterable[str]) -> set[str]:
        """Send a message to the supplied clients and return failed client IDs."""

    async def start(
        self,
        handler: Callable[[Any], Awaitable[None]],
        process_request: Callable[[Any, Request], Awaitable[Response | None]],
        host: str,
        port: int,
    ) -> Any:
        """Start listening for transport connections, when applicable."""
        raise NotImplementedError("This transport does not provide a listener")

    async def stop(self) -> None:
        """Stop listening and release transport resources, when applicable."""

    @property
    def bound_port(self) -> int:
        """Return the active listening port, when applicable."""
        return 0


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport."""

    def __init__(self, port: int = 8765) -> None:
        self.port = port
        self._connections: dict[str, ServerConnection] = {}
        self._server: Server | None = None

    async def on_connect(self, client_id: str, connection: ServerConnection) -> None:
        self._connections[client_id] = connection

    async def on_disconnect(self, client_id: str) -> None:
        self._connections.pop(client_id, None)

    async def send_message(self, client_id: str, message: str) -> bool:
        connection = self._connections.get(client_id)
        if connection is None:
            return False
        try:
            await connection.send(message)
            return True
        except ConnectionClosed:
            return False

    async def broadcast(self, message: str, client_ids: Iterable[str]) -> set[str]:
        ids = list(client_ids)
        results = await asyncio.gather(*(self.send_message(i, message) for i in ids))
        return {client_id for client_id, sent in zip(ids, results) if not sent}

    async def start(
        self,
        handler: Callable[[ServerConnection], Awaitable[None]],
        process_request: Callable[[ServerConnection, Request], Awaitable[Response | None]],
        host: str,
        port: int,
    ) -> Server:
        self._server = await serve(handler, host, port, process_request=process_request)
        return self._server

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self._connections.clear()

    @property
    def bound_port(self) -> int:
        if self._server is None or not self._server.sockets:
            return self.port
        return self._server.sockets[0].getsockname()[1]
