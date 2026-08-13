"""Transport interfaces and implementations for notification delivery."""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Iterable

from websockets.asyncio.server import ServerConnection
from websockets.exceptions import ConnectionClosed

if TYPE_CHECKING:
    from app import NotificationServer


class ClientRegistry:
    """Transport-independent registry of local live client connections."""

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def add(self, connection: Any) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = connection
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in list(self._channels):
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def get(self, client_id: str) -> Any | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> list[Any]:
        with self._lock:
            return list(self._clients.values())

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers:
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[channel]

    def channel_snapshot(self, channel: str) -> list[Any]:
        with self._lock:
            return [
                self._clients[client_id]
                for client_id in self._channels.get(channel, set())
                if client_id in self._clients
            ]

    def channels(self) -> dict[str, int]:
        with self._lock:
            return {
                channel: len(subscribers)
                for channel, subscribers in sorted(self._channels.items())
            }

    def subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    def is_subscribed(self, client_id: str, channel: str) -> bool:
        with self._lock:
            return client_id in self._channels.get(channel, set())

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)


class BaseTransport(ABC):
    """Interface implemented by notification client transports."""

    def __init__(self) -> None:
        self.clients = ClientRegistry()
        self.server: NotificationServer | None = None

    def bind(self, server: NotificationServer) -> None:
        self.server = server

    @abstractmethod
    async def on_connect(self, connection: Any) -> str:
        """Register a newly connected client and return its identifier."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Remove a disconnected client."""

    @abstractmethod
    async def send_message(self, connection: Any, outgoing: dict[str, Any]) -> None:
        """Send one notification to one transport connection."""

    @abstractmethod
    async def broadcast(
        self, outgoing: dict[str, Any], recipients: Iterable[Any] | None = None
    ) -> None:
        """Send one notification to the selected local connections."""


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport interface."""

    async def on_connect(self, connection: ServerConnection) -> str:
        if self.server is None:
            raise RuntimeError("transport is not bound to a notification server")
        client_id = self.clients.add(connection)
        await self.server.client_connected(client_id)
        await self.send_message(
            connection, self.server.connected_message(client_id)
        )
        return client_id

    async def on_disconnect(self, client_id: str) -> None:
        if self.server is None:
            raise RuntimeError("transport is not bound to a notification server")
        self.clients.remove(client_id)
        await self.server.client_disconnected(client_id)

    async def send_message(
        self, connection: ServerConnection, outgoing: dict[str, Any]
    ) -> None:
        await connection.send(json.dumps(outgoing))

    async def broadcast(
        self,
        outgoing: dict[str, Any],
        recipients: Iterable[ServerConnection] | None = None,
    ) -> None:
        selected = list(recipients) if recipients is not None else self.clients.snapshot()
        if selected:
            await asyncio.gather(
                *(self.send_message(client, outgoing) for client in selected),
                return_exceptions=True,
            )

    async def handler(self, websocket: ServerConnection) -> None:
        if self.server is None:
            raise RuntimeError("transport is not bound to a notification server")
        await self.server.start()
        client_id = await self.on_connect(websocket)
        try:
            async for raw_message in websocket:
                await self.server.handle_message(raw_message, websocket, client_id)
        except ConnectionClosed:
            pass
        finally:
            await self.on_disconnect(client_id)


def create_transport(name: str) -> BaseTransport:
    """Create the configured transport implementation."""
    normalized = name.strip().lower()
    if normalized in {"websocket", "websockets", "ws"}:
        return WebSocketTransport()
    raise ValueError(f"unsupported transport: {name}")
