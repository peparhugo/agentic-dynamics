"""Transport implementations used by the notification server."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from typing import Any

from websockets.exceptions import ConnectionClosed


class BaseTransport(ABC):
    """Deliver messages without coupling notification routing to a protocol."""

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}

    @property
    def clients(self) -> dict[str, Any]:
        return dict(self._clients)

    @abstractmethod
    def on_connect(self, client_id: str, client: Any) -> None:
        """Register a newly connected client."""

    @abstractmethod
    def on_disconnect(self, client_id: str) -> None:
        """Remove a disconnected client."""

    @abstractmethod
    async def send_message(self, client_id: str, message: str) -> None:
        """Send one serialized message to a client."""

    @abstractmethod
    async def broadcast(self, message: str) -> None:
        """Send a serialized message to all connected clients."""


class WebSocketTransport(BaseTransport):
    """Transport implementation for WebSocket-compatible connections."""

    def on_connect(self, client_id: str, client: Any) -> None:
        self._clients[client_id] = client

    def on_disconnect(self, client_id: str) -> None:
        self._clients.pop(client_id, None)

    async def send_message(self, client_id: str, message: str) -> None:
        client = self._clients.get(client_id)
        if client is None:
            return
        try:
            await client.send(message)
        except ConnectionClosed:
            self.on_disconnect(client_id)

    async def broadcast(self, message: str) -> None:
        recipients = list(self._clients)
        await asyncio.gather(
            *(self.send_message(client_id, message) for client_id in recipients),
            return_exceptions=True,
        )
