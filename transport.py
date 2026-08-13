"""Transport implementations for notification delivery."""

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Iterable
import json
import threading
import uuid
from typing import Any

from websockets.asyncio.server import ServerConnection


class BaseTransport(ABC):
    """Delivers notification messages to connected clients."""

    @abstractmethod
    async def on_connect(self, connection: Any) -> str:
        """Register a connection and return its client identifier."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Remove a disconnected client."""

    @abstractmethod
    async def send_message(self, client_id: str, message: dict[str, Any]) -> bool:
        """Send a message to one client, returning whether it was connected."""

    @abstractmethod
    async def broadcast(self, message: dict[str, Any], client_ids: Iterable[str] | None = None) -> None:
        """Send a message to every client or a specified group of clients."""

class WebSocketTransport(BaseTransport):
    """WebSocket-backed transport using the project's existing wire protocol."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._clients_lock = threading.Lock()

    async def on_connect(self, connection: ServerConnection) -> str:
        client_id = uuid.uuid4().hex
        with self._clients_lock:
            self._clients[client_id] = connection
        return client_id

    async def on_disconnect(self, client_id: str) -> None:
        with self._clients_lock:
            self._clients.pop(client_id, None)

    async def send_message(self, client_id: str, message: dict[str, Any]) -> bool:
        with self._clients_lock:
            connection = self._clients.get(client_id)
        if connection is None:
            return False
        await connection.send(json.dumps(message))
        return True

    async def broadcast(self, message: dict[str, Any], client_ids: Iterable[str] | None = None) -> None:
        with self._clients_lock:
            if client_ids is None:
                connections = list(self._clients.values())
            else:
                connections = [self._clients[client_id] for client_id in client_ids if client_id in self._clients]
        if connections:
            encoded = json.dumps(message)
            await asyncio.gather(*(connection.send(encoded) for connection in connections), return_exceptions=True)
