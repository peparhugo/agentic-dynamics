"""Async WebSocket notification server.

The WebSocket service and the small HTTP health service intentionally share a
``NotificationServer`` instance so the health count is always current.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from websockets.asyncio.server import Server, ServerConnection, serve

LOGGER = logging.getLogger(__name__)
SUPPORTED_TYPES = {"broadcast", "direct", "system"}


def make_message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Create a protocol message with a UTC timestamp."""
    if message_type not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported message type: {message_type}")
    return {
        "type": message_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class NotificationServer:
    """Serve notifications over WebSocket and status over HTTP."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        websocket_port: int = 8765,
        health_port: int | None = None,
    ) -> None:
        self.host = host
        self.websocket_port = websocket_port
        self.health_port = health_port if health_port is not None else websocket_port + 1
        self._clients: dict[str, ServerConnection] = {}
        self._clients_lock = threading.RLock()
        self._websocket_server: Server | None = None
        self._health_server: asyncio.AbstractServer | None = None

    @property
    def clients(self) -> dict[str, ServerConnection]:
        """Return a snapshot of connected clients, never the mutable registry."""
        with self._clients_lock:
            return dict(self._clients)

    @property
    def client_count(self) -> int:
        with self._clients_lock:
            return len(self._clients)

    async def start(self) -> None:
        """Start both listeners."""
        self._websocket_server = await serve(
            self._websocket_handler, self.host, self.websocket_port
        )
        self._health_server = await asyncio.start_server(
            self._health_handler, self.host, self.health_port
        )

    async def stop(self) -> None:
        """Stop listeners and close all active WebSocket connections."""
        if self._health_server is not None:
            self._health_server.close()
            await self._health_server.wait_closed()
            self._health_server = None
        if self._websocket_server is not None:
            self._websocket_server.close()
            await self._websocket_server.wait_closed()
            self._websocket_server = None
        for connection in self.clients.values():
            await connection.close()
        with self._clients_lock:
            self._clients.clear()

    async def wait_closed(self) -> None:
        """Wait for either listener to be closed by the caller."""
        if self._websocket_server is not None:
            await self._websocket_server.wait_closed()

    async def broadcast(self, payload: dict[str, Any]) -> None:
        """Send a broadcast message to every currently connected client."""
        await self._send_to_many(make_message("broadcast", payload), self.clients)

    async def send_direct(self, client_id: str, payload: dict[str, Any]) -> bool:
        """Send a direct message and return whether the client exists."""
        connection = self.clients.get(client_id)
        if connection is None:
            return False
        await connection.send(json.dumps(make_message("direct", payload)))
        return True

    async def _websocket_handler(self, connection: ServerConnection) -> None:
        client_id = str(uuid.uuid4())
        with self._clients_lock:
            self._clients[client_id] = connection
        try:
            await connection.send(
                json.dumps(make_message("system", {"client_id": client_id}))
            )
            async for raw_message in connection:
                await self._handle_client_message(client_id, raw_message)
        except Exception as exc:
            LOGGER.debug("WebSocket %s closed: %s", client_id, exc)
        finally:
            with self._clients_lock:
                self._clients.pop(client_id, None)

    async def _handle_client_message(self, client_id: str, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
            message_type = message["type"]
            payload = message["payload"]
            if message_type not in SUPPORTED_TYPES or not isinstance(payload, dict):
                raise ValueError
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            await self.send_direct(client_id, {"error": "invalid message"})
            return

        if message_type == "broadcast":
            await self.broadcast(payload)
        elif message_type == "direct":
            recipient = payload.get("client_id")
            if isinstance(recipient, str):
                await self.send_direct(recipient, payload)

    async def _send_to_many(
        self, message: dict[str, Any], clients: dict[str, ServerConnection]
    ) -> None:
        encoded = json.dumps(message)
        results = await asyncio.gather(
            *(connection.send(encoded) for connection in clients.values()),
            return_exceptions=True,
        )
        for client_id, result in zip(clients, results):
            if isinstance(result, Exception):
                with self._clients_lock:
                    self._clients.pop(client_id, None)

    async def _health_handler(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request_line = await reader.readline()
            path = request_line.decode("ascii", errors="ignore").split(" ")[1]
            if path != "/health":
                body = json.dumps({"error": "not found"}).encode()
                status = "404 Not Found"
            else:
                count = self.client_count
                body = json.dumps(
                    {"status": "ok", "clients": count, "connected_clients": count}
                ).encode()
                status = "200 OK"
            headers = (
                f"HTTP/1.1 {status}\r\nContent-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
            ).encode()
            writer.write(headers + body)
            await writer.drain()
        except (IndexError, UnicodeError):
            writer.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()


def main() -> None:
    parser = argparse.ArgumentParser(description="WebSocket notification server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--websocket-port", type=int, default=8765)
    parser.add_argument("--health-port", type=int, default=None)
    args = parser.parse_args()

    async def run() -> None:
        server = NotificationServer(args.host, args.websocket_port, args.health_port)
        await server.start()
        await server.wait_closed()

    asyncio.run(run())


if __name__ == "__main__":
    main()
