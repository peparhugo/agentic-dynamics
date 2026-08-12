"""Pluggable client transports for the notification server."""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Iterable
from typing import Any
from urllib.parse import parse_qs, urlparse

from websockets.asyncio.server import ServerConnection, serve


class BaseTransport(ABC):
    """Transport contract used by the notification routing layer."""

    async def start(self, *callbacks: Any) -> None:
        """Start accepting clients, when the transport has a listener."""

    async def stop(self) -> None:
        """Stop accepting clients, when the transport has a listener."""

    @abstractmethod
    async def on_connect(self, client_id: str, endpoint: Any) -> None:
        """Register a newly connected client endpoint."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Remove a disconnected client endpoint."""

    @abstractmethod
    async def send_message(self, client_id: str, message: dict[str, Any]) -> None:
        """Send a message to one client."""

    @abstractmethod
    async def broadcast(
        self, message: dict[str, Any], client_ids: Iterable[str] | None = None
    ) -> None:
        """Send a message to all, or to the supplied clients."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport contract."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._connections: dict[str, ServerConnection] = {}
        self._server = None

    async def start(
        self,
        on_connect: Callable[[ServerConnection, str | None], Awaitable[str]],
        on_message: Callable[[str, str], Awaitable[None]],
        on_disconnect: Callable[[str], Awaitable[None]],
        on_ready: Callable[[str], Awaitable[None]],
    ) -> None:
        async def handle(connection: ServerConnection) -> None:
            path = getattr(getattr(connection, "request", None), "path", "")
            requested_id = parse_qs(urlparse(path).query).get("client_id", [None])[0]
            client_id = await on_connect(connection, requested_id)
            await self.on_connect(client_id, connection)
            await on_ready(client_id)
            try:
                async for raw_message in connection:
                    await on_message(client_id, raw_message)
            finally:
                await self.on_disconnect(client_id)
                await on_disconnect(client_id)

        self._server = await serve(handle, self.host, self.port)
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def on_connect(self, client_id: str, endpoint: ServerConnection) -> None:
        self._connections[client_id] = endpoint

    async def on_disconnect(self, client_id: str) -> None:
        self._connections.pop(client_id, None)

    async def send_message(self, client_id: str, message: dict[str, Any]) -> None:
        connection = self._connections.get(client_id)
        if connection is not None:
            try:
                await connection.send(json.dumps(message))
            except Exception:
                # A connection can close between lookup and send.
                pass

    async def broadcast(
        self, message: dict[str, Any], client_ids: Iterable[str] | None = None
    ) -> None:
        ids = client_ids if client_ids is not None else self._connections
        await asyncio.gather(*(
            self.send_message(client_id, message) for client_id in ids
        ))
