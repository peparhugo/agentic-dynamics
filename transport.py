"""Transport implementations for the notification server."""

from __future__ import annotations

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed


class BaseTransport(ABC):
    """Interface used by the notification core to deliver messages."""

    def __init__(self, server: Any) -> None:
        self.server = server
        self.clients: dict[str, Any] = {}

    async def start(self) -> None:
        """Start transport listeners."""

    async def stop(self) -> None:
        """Stop transport listeners and disconnect clients."""

    @abstractmethod
    async def on_connect(self, connection: Any) -> str:
        """Register a new transport connection and return its client id."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Remove a transport connection."""

    @abstractmethod
    async def send_message(self, client_id: str, message: dict[str, Any]) -> None:
        """Send one message to one client."""

    @abstractmethod
    async def broadcast(self, message: dict[str, Any], recipients: list[tuple[str, Any]]) -> None:
        """Send a message to the selected clients."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport."""

    def __init__(self, server: Any, host: str, port: int) -> None:
        super().__init__(server)
        self.host = host
        self.port = port
        self._server: Any = None
        self._clients_lock = asyncio.Lock()

    async def start(self) -> None:
        self._server = await websockets.serve(self._handle_connection, self.host, self.port)
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        async with self._clients_lock:
            client_ids = list(self.clients)
            clients = list(self.clients.values())
            self.clients.clear()
        await asyncio.gather(*(self.on_disconnect(client_id) for client_id in client_ids), return_exceptions=True)
        await asyncio.gather(*(client.close() for client in clients), return_exceptions=True)

    async def on_connect(self, connection: Any) -> str:
        client_id = str(uuid.uuid4())
        async with self._clients_lock:
            self.clients[client_id] = connection
        await self.server._register_client(client_id)
        await connection.send(json.dumps({
            "type": "system",
            "payload": {"client_id": client_id},
            "timestamp": self.server.timestamp(),
        }))
        return client_id

    async def on_disconnect(self, client_id: str) -> None:
        async with self._clients_lock:
            self.clients.pop(client_id, None)
        await self.server._remove_client_state(client_id)
        await self.server._unregister_client(client_id)

    async def send_message(self, client_id: str, message: dict[str, Any]) -> None:
        async with self._clients_lock:
            client = self.clients.get(client_id)
        if client is not None:
            await client.send(json.dumps(message))

    async def broadcast(self, message: dict[str, Any], recipients: list[tuple[str, Any]]) -> None:
        results = await asyncio.gather(
            *(client.send(json.dumps(message)) for _, client in recipients),
            return_exceptions=True,
        )
        for (client_id, _), result in zip(recipients, results):
            if isinstance(result, Exception):
                await self.on_disconnect(client_id)

    async def _handle_connection(self, websocket: Any) -> None:
        client_id = await self.on_connect(websocket)
        try:
            async for raw_message in websocket:
                await self.server._handle_message(client_id, raw_message)
        except (ConnectionClosed, asyncio.CancelledError):
            pass
        finally:
            await self.on_disconnect(client_id)


# Keep the interface available under the concise name used by integrations.
Transport = BaseTransport
