"""WebSocket transport, built on the `websockets` library.

This is the default transport and the only one currently implemented; it
holds all the `websockets`-specific behavior that `NotificationServer` used
to have inline (connection-closed handling, `websockets.serve(...)`).
"""
from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

import websockets

from .messages import dumps
from .transport import BaseTransport, ConnectionHandler


class WebSocketTransport(BaseTransport):
    async def on_connect(self, connection: Any) -> None:
        pass

    async def on_disconnect(self, connection: Any) -> None:
        pass

    async def send_message(self, connection: Any, message: dict) -> None:
        try:
            await connection.send(dumps(message))
        except websockets.exceptions.ConnectionClosed:
            pass

    async def broadcast(self, connections: list, message: dict) -> None:
        if not connections:
            return
        await asyncio.gather(
            *(self.send_message(connection, message) for connection in connections),
            return_exceptions=True,
        )

    async def receive(self, connection: Any) -> AsyncIterator[str]:
        try:
            async for raw in connection:
                yield raw
        except websockets.exceptions.ConnectionClosed:
            return

    def serve(self, handler: ConnectionHandler, host: str, port: int):
        return websockets.serve(handler, host, port)
