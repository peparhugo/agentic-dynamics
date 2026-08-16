"""Pluggable client transports for the notification server."""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from websockets.asyncio.server import ServerConnection
from websockets.exceptions import ConnectionClosed

Message = dict[str, Any]
ConnectHandler = Callable[[Any], Awaitable[str]]
MessageHandler = Callable[[str, str | bytes], Awaitable[None]]
DisconnectHandler = Callable[[str], Awaitable[None]]


class ClientRegistry:
    """Thread-safe mapping of client IDs to transport connections."""

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
                subscribers = self._channels[channel]
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[channel]

    def get(self, client_id: str) -> Any | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> list[tuple[str, Any]]:
        with self._lock:
            return list(self._clients.items())

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            if client_id in self._clients:
                self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    def channel_snapshot(self, channel: str) -> list[tuple[str, Any]]:
        with self._lock:
            return [
                (client_id, self._clients[client_id])
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
    """Interface between notification routing and connected clients."""

    def __init__(self, registry: ClientRegistry | None = None) -> None:
        self.registry = registry or ClientRegistry()

    @abstractmethod
    async def on_connect(self, connection: Any) -> str:
        """Register a connection and return its public client ID."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Remove a connection and its local subscriptions."""

    @abstractmethod
    async def send_message(self, client_id: str, message: Message) -> None:
        """Send one message to a connected client."""

    @abstractmethod
    async def broadcast(
        self,
        message: Message,
        channel: str | None = None,
        target_id: str | None = None,
    ) -> None:
        """Send a message to the selected local clients."""

    async def handle_connection(
        self,
        connection: Any,
        on_connect: ConnectHandler,
        on_message: MessageHandler,
        on_disconnect: DisconnectHandler,
    ) -> None:
        """Drive an inbound connection when the transport supports one."""
        raise NotImplementedError


class WebSocketTransport(BaseTransport):
    """WebSocket connection lifecycle, serialization, and delivery."""

    async def on_connect(self, connection: ServerConnection) -> str:
        return self.registry.add(connection)

    async def on_disconnect(self, client_id: str) -> None:
        self.registry.remove(client_id)

    async def send_message(self, client_id: str, message: Message) -> None:
        connection = self.registry.get(client_id)
        if connection is not None:
            await connection.send(json.dumps(message, separators=(",", ":")))

    async def broadcast(
        self,
        message: Message,
        channel: str | None = None,
        target_id: str | None = None,
    ) -> None:
        if target_id is not None:
            connection = self.registry.get(target_id)
            clients = [] if connection is None else [(target_id, connection)]
        elif channel is None:
            clients = self.registry.snapshot()
        else:
            clients = self.registry.channel_snapshot(channel)

        results = await asyncio.gather(
            *(
                connection.send(json.dumps(message, separators=(",", ":")))
                for _, connection in clients
            ),
            return_exceptions=True,
        )
        for (client_id, _), result in zip(clients, results, strict=True):
            if isinstance(result, ConnectionClosed):
                self.registry.remove(client_id)

    async def handle_connection(
        self,
        connection: ServerConnection,
        on_connect: ConnectHandler,
        on_message: MessageHandler,
        on_disconnect: DisconnectHandler,
    ) -> None:
        client_id = await on_connect(connection)
        try:
            async for raw_message in connection:
                await on_message(client_id, raw_message)
        except ConnectionClosed:
            pass
        finally:
            await on_disconnect(client_id)


def create_transport(name: str | None = None) -> BaseTransport:
    """Create the configured transport implementation."""
    transport_name = (name or "websocket").strip().lower()
    if transport_name == "websocket":
        return WebSocketTransport()
    raise ValueError(f"unsupported transport: {transport_name}")
