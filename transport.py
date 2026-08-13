"""
Pluggable transport layer for notification server.

Supports different transport mechanisms (WebSocket, SSE, polling, etc.)
without modifying core notification logic.
"""

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import websockets
from websockets import ConnectionClosed


class BaseTransport(ABC):
    """Abstract base class for notification transport mechanisms."""

    def __init__(self, registry: Any):
        self.registry = registry

    @abstractmethod
    async def send_message(self, client_id: str, message: dict) -> None:
        """Send a message to a specific client."""
        pass

    @abstractmethod
    async def broadcast(
        self, message: dict, exclude: Optional[str] = None, channel: Optional[str] = None
    ) -> None:
        """Broadcast a message to all connected clients or to a specific channel."""
        pass


class WebSocketTransport(BaseTransport):
    """WebSocket-based transport implementation."""

    async def send_message(self, client_id: str, message: dict) -> None:
        """Send a message to a specific client via WebSocket."""
        client = self.registry.get_client(client_id)
        if client:
            await self._send_safe(client, json.dumps(message))

    async def broadcast(
        self, message: dict, exclude: Optional[str] = None, channel: Optional[str] = None
    ) -> None:
        """Broadcast a message to all clients or to a specific channel via WebSocket."""
        if channel:
            subscribers = self.registry.get_channel_subscribers(channel)
            target_clients = {
                client_id: self.registry.get_client(client_id)
                for client_id in subscribers
                if self.registry.get_client(client_id) is not None
            }
        else:
            target_clients = self.registry.get_all_clients()

        if not target_clients:
            return

        message_json = json.dumps(message)
        tasks = []

        for client_id, websocket in target_clients.items():
            if exclude and client_id == exclude:
                continue
            tasks.append(self._send_safe(websocket, message_json))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_safe(self, websocket: Any, message: str) -> None:
        """Safely send a message, handling closed connections."""
        try:
            await websocket.send(message)
        except ConnectionClosed:
            pass
