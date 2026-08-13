"""Transport implementations for the notification server."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Iterable
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import websockets
from websockets.exceptions import ConnectionClosed
from websockets.legacy.server import WebSocketServer, WebSocketServerProtocol

if TYPE_CHECKING:
    from app import NotificationServer


class BaseTransport(ABC):
    """Interface implemented by notification client transports."""

    def __init__(self, server: NotificationServer | None = None) -> None:
        self.server = server

    def bind(self, server: NotificationServer) -> None:
        self.server = server

    async def start(self) -> None:
        """Start accepting client connections."""

    async def stop(self) -> None:
        """Stop accepting client connections."""

    @abstractmethod
    async def on_connect(self, connection: Any) -> str:
        """Register a newly connected transport client."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Remove a disconnected transport client."""

    @abstractmethod
    async def send_message(self, connection: Any, encoded_message: str) -> None:
        """Send one encoded message to a connection."""

    @abstractmethod
    async def broadcast(
        self, clients: Iterable[tuple[str, Any]], encoded_message: str
    ) -> None:
        """Send an encoded message to a collection of clients."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport interface."""

    def __init__(self, server: NotificationServer, host: str, port: int) -> None:
        super().__init__(server)
        self.host = host
        self.port = port
        self.websocket_server: WebSocketServer | None = None

    async def start(self) -> None:
        self.websocket_server = await websockets.serve(
            self.handle_connection, self.host, self.port
        )

    async def stop(self) -> None:
        if self.websocket_server is not None:
            self.websocket_server.close()
            await self.websocket_server.wait_closed()
            self.websocket_server = None

    @property
    def bound_port(self) -> int:
        if self.websocket_server is None or not self.websocket_server.sockets:
            raise RuntimeError("server is not running")
        return self.websocket_server.sockets[0].getsockname()[1]

    async def handle_connection(self, websocket: WebSocketServerProtocol) -> None:
        assert self.server is not None
        client_id = await self.on_connect(websocket)
        try:
            async for raw_message in websocket:
                await self.server.process_message(client_id, websocket, raw_message)
        except ConnectionClosed:
            pass
        finally:
            await self.on_disconnect(client_id)

    async def on_connect(self, connection: WebSocketServerProtocol) -> str:
        assert self.server is not None
        return await self.server.on_connect(connection)

    async def on_disconnect(self, client_id: str) -> None:
        assert self.server is not None
        await self.server.on_disconnect(client_id)

    async def send_message(
        self, connection: WebSocketServerProtocol, encoded_message: str
    ) -> None:
        await connection.send(encoded_message)

    async def broadcast(
        self,
        clients: Iterable[tuple[str, WebSocketServerProtocol]],
        encoded_message: str,
    ) -> None:
        clients = list(clients)
        results = await asyncio.gather(
            *(self.send_message(client, encoded_message) for _, client in clients),
            return_exceptions=True,
        )
        for (client_id, _), result in zip(clients, results):
            if isinstance(result, Exception):
                await self.on_disconnect(client_id)


TransportFactory = Callable[["NotificationServer", str, int], BaseTransport]
TRANSPORTS: dict[str, TransportFactory] = {"websocket": WebSocketTransport}


def register_transport(name: str, factory: TransportFactory) -> None:
    """Register a transport factory for config-based selection."""
    TRANSPORTS[name.lower()] = factory


def create_transport(
    name: str, server: NotificationServer, host: str, port: int
) -> BaseTransport:
    try:
        factory = TRANSPORTS[name.lower()]
    except KeyError as exc:
        raise ValueError(f"unsupported transport: {name}") from exc
    return factory(server, host, port)
