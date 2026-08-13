"""
Example implementations of alternative transports for the notification server.

This demonstrates how the pluggable transport layer allows different
communication mechanisms to be used interchangeably.
"""

import asyncio
import json
import logging
from typing import Set, Dict
from notification_server import BaseTransport, create_server

logger = logging.getLogger(__name__)


class PollingTransport(BaseTransport):
    """Example: Polling-based transport (clients poll for messages)."""

    def __init__(self, message_handler=None):
        self.message_handler = message_handler
        self._clients: Dict[str, list] = {}
        self._pending_messages: Dict[str, list] = {}

    async def on_connect(self, client_id: str) -> None:
        """Register a new client."""
        self._clients[client_id] = []
        self._pending_messages[client_id] = []
        logger.info(f"Client {client_id} connected via polling")

    async def on_disconnect(self, client_id: str) -> None:
        """Unregister a client."""
        self._clients.pop(client_id, None)
        self._pending_messages.pop(client_id, None)
        logger.info(f"Client {client_id} disconnected from polling")

    async def send_message(self, client_id: str, message: str) -> None:
        """Queue a message for a specific client."""
        if client_id in self._pending_messages:
            self._pending_messages[client_id].append(message)

    async def broadcast(self, message: str, client_ids: Set[str] | None = None) -> None:
        """Queue a message for all or specific clients."""
        target_clients = client_ids or set(self._pending_messages.keys())
        for client_id in target_clients:
            if client_id in self._pending_messages:
                self._pending_messages[client_id].append(message)

    async def get_pending_messages(self, client_id: str) -> list:
        """Retrieve queued messages for a client."""
        messages = self._pending_messages.get(client_id, [])
        self._pending_messages[client_id] = []
        return messages

    async def start(self, host: str, port: int) -> None:
        """Start polling transport (stub - no server to start)."""
        logger.info(f"Polling transport ready on {host}:{port}")

    async def shutdown(self) -> None:
        """Shutdown polling transport."""
        pass


class SSETransport(BaseTransport):
    """Example: Server-Sent Events (SSE) transport."""

    def __init__(self, message_handler=None):
        self.message_handler = message_handler
        self._connections: Dict[str, asyncio.Queue] = {}

    async def on_connect(self, client_id: str) -> None:
        """Register a new client with an event queue."""
        self._connections[client_id] = asyncio.Queue()
        logger.info(f"Client {client_id} connected via SSE")

    async def on_disconnect(self, client_id: str) -> None:
        """Unregister a client."""
        self._connections.pop(client_id, None)
        logger.info(f"Client {client_id} disconnected from SSE")

    async def send_message(self, client_id: str, message: str) -> None:
        """Queue a message for a specific client."""
        if client_id in self._connections:
            await self._connections[client_id].put(message)

    async def broadcast(self, message: str, client_ids: Set[str] | None = None) -> None:
        """Queue a message for all or specific clients."""
        target_clients = client_ids or set(self._connections.keys())
        tasks = [
            self._connections[cid].put(message)
            for cid in target_clients
            if cid in self._connections
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def get_event_stream(self, client_id: str):
        """Get an async generator for SSE events."""
        if client_id not in self._connections:
            return

        while client_id in self._connections:
            try:
                message = await asyncio.wait_for(
                    self._connections[client_id].get(),
                    timeout=30
                )
                yield f"data: {message}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"

    async def start(self, host: str, port: int) -> None:
        """Start SSE transport (stub - no server to start)."""
        logger.info(f"SSE transport ready on {host}:{port}")

    async def shutdown(self) -> None:
        """Shutdown SSE transport."""
        pass


# Example usage:
if __name__ == "__main__":
    # WebSocket (default) - select via TRANSPORT env var or direct instantiation
    # server = create_server()

    # Polling transport - manual instantiation
    # polling = PollingTransport()
    # server = create_server(transport=polling)

    # SSE transport - manual instantiation
    # sse = SSETransport()
    # server = create_server(transport=sse)

    print("Transport examples available:")
    print("- BaseTransport: Abstract base class for custom implementations")
    print("- WebSocketTransport: Built-in WebSocket implementation")
    print("- PollingTransport: Example polling-based transport")
    print("- SSETransport: Example Server-Sent Events transport")
