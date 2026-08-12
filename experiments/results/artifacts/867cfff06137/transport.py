"""Pluggable transports for the notification server."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable

from websockets.asyncio.server import Server, ServerConnection, serve

LOGGER = logging.getLogger(__name__)
MessageHandler = Callable[[str, str], Awaitable[None]]
ClientHandler = Callable[[str], Awaitable[None]]


class BaseTransport(ABC):
    """Interface implemented by notification transports."""

    @abstractmethod
    async def on_connect(self, connection: Any) -> str:
        pass

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        pass

    @abstractmethod
    async def send_message(self, client_id: str, message: dict[str, Any]) -> None:
        pass

    @abstractmethod
    async def broadcast(self, message: dict[str, Any], client_ids: set[str] | None = None) -> None:
        pass

    async def start(
        self, host: str, port: int, on_connect: ClientHandler,
        on_message: MessageHandler, on_disconnect: ClientHandler,
    ) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        pass

    async def wait_closed(self) -> None:
        pass

    @property
    def clients(self) -> dict[str, Any]:
        return {}


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the transport contract."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._server: Server | None = None
        self._on_connect: ClientHandler | None = None
        self._on_message: MessageHandler | None = None
        self._on_disconnect: ClientHandler | None = None

    @property
    def clients(self) -> dict[str, ServerConnection]:
        return dict(self._clients)

    async def start(self, host: str, port: int, on_connect: ClientHandler,
                    on_message: MessageHandler, on_disconnect: ClientHandler) -> None:
        self._on_connect = on_connect
        self._on_message = on_message
        self._on_disconnect = on_disconnect
        self._server = await serve(self._handler, host, port)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        for connection in self.clients.values():
            await connection.close()
        self._clients.clear()

    async def wait_closed(self) -> None:
        if self._server is not None:
            await self._server.wait_closed()

    async def on_connect(self, connection: ServerConnection) -> str:
        client_id = str(uuid.uuid4())
        self._clients[client_id] = connection
        return client_id

    async def on_disconnect(self, client_id: str) -> None:
        self._clients.pop(client_id, None)

    async def send_message(self, client_id: str, message: dict[str, Any]) -> None:
        connection = self._clients.get(client_id)
        if connection is not None:
            await connection.send(json.dumps(message))

    async def broadcast(self, message: dict[str, Any], client_ids: set[str] | None = None) -> None:
        recipients = self._clients if client_ids is None else {
            client_id: self._clients[client_id] for client_id in client_ids if client_id in self._clients
        }
        results = await asyncio.gather(
            *(connection.send(json.dumps(message)) for connection in recipients.values()),
            return_exceptions=True,
        )
        for client_id, result in zip(recipients, results):
            if isinstance(result, Exception):
                await self.on_disconnect(client_id)
                if self._on_disconnect is not None:
                    await self._on_disconnect(client_id)

    async def _handler(self, connection: ServerConnection) -> None:
        client_id = await self.on_connect(connection)
        try:
            if self._on_connect is not None:
                await self._on_connect(client_id)
            if self._on_message is not None:
                async for raw_message in connection:
                    await self._on_message(client_id, raw_message)
        except Exception as exc:
            LOGGER.debug("WebSocket %s closed: %s", client_id, exc)
        finally:
            await self.on_disconnect(client_id)
            if self._on_disconnect is not None:
                await self._on_disconnect(client_id)
