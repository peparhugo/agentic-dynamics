"""Async WebSocket notification server with a small HTTP health endpoint."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

LOGGER = logging.getLogger(__name__)
SUPPORTED_TYPES = frozenset({"broadcast", "direct", "system"})


def make_message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Create a message in the server's wire format."""
    if message_type not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported message type: {message_type}")
    if not isinstance(payload, dict):
        raise TypeError("payload must be an object")
    return {
        "type": message_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class ClientRegistry:
    """Concurrency-safe mapping of client IDs to WebSocket connections."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = asyncio.Lock()

    async def add(self, websocket: ServerConnection) -> str:
        client_id = str(uuid4())
        async with self._lock:
            self._clients[client_id] = websocket
        return client_id

    async def remove(self, client_id: str) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)

    async def count(self) -> int:
        async with self._lock:
            return len(self._clients)

    async def snapshot(self) -> list[tuple[str, ServerConnection]]:
        async with self._lock:
            return list(self._clients.items())

    async def get(self, client_id: str) -> ServerConnection | None:
        async with self._lock:
            return self._clients.get(client_id)


class NotificationServer:
    """Manage WebSocket clients and route notification messages."""

    def __init__(self) -> None:
        self.clients = ClientRegistry()

    async def websocket_handler(self, websocket: ServerConnection) -> None:
        client_id = await self.clients.add(websocket)
        await websocket.send(
            json.dumps(make_message("system", {"event": "connected", "client_id": client_id}))
        )

        try:
            async for raw_message in websocket:
                await self._handle_message(client_id, websocket, raw_message)
        except ConnectionClosed:
            pass
        finally:
            await self.clients.remove(client_id)

    async def _handle_message(
        self, client_id: str, websocket: ServerConnection, raw_message: str | bytes
    ) -> None:
        try:
            message = json.loads(raw_message)
            self._validate_message(message)
            message_type = message["type"]

            if message_type == "broadcast":
                await self.broadcast(make_message("broadcast", message["payload"]))
            elif message_type == "direct":
                await self._send_direct(message["payload"])
            else:
                raise ValueError("clients cannot send system messages")
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            await websocket.send(
                json.dumps(make_message("system", {"event": "error", "message": str(error)}))
            )

    @staticmethod
    def _validate_message(message: Any) -> None:
        if not isinstance(message, dict):
            raise TypeError("message must be an object")
        if set(message) != {"type", "payload", "timestamp"}:
            raise ValueError("message must contain type, payload, and timestamp")
        if message["type"] not in SUPPORTED_TYPES:
            raise ValueError("unsupported message type")
        if not isinstance(message["payload"], dict):
            raise TypeError("payload must be an object")
        if not isinstance(message["timestamp"], str):
            raise TypeError("timestamp must be a string")

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a message to every client connected at call time."""
        encoded = json.dumps(message)
        clients = await self.clients.snapshot()
        if not clients:
            return

        results = await asyncio.gather(
            *(websocket.send(encoded) for _, websocket in clients),
            return_exceptions=True,
        )
        for (client_id, _), result in zip(clients, results):
            if isinstance(result, Exception):
                await self.clients.remove(client_id)

    async def _send_direct(self, payload: dict[str, Any]) -> None:
        recipient_id = payload.get("client_id")
        if not isinstance(recipient_id, str):
            raise ValueError("direct payload requires client_id")
        recipient = await self.clients.get(recipient_id)
        if recipient is None:
            raise ValueError("direct recipient is not connected")
        await recipient.send(json.dumps(make_message("direct", payload)))

    async def health_handler(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        status = "404 Not Found"
        body: dict[str, Any] = {"error": "not found"}
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=5)
            parts = request_line.decode("ascii", errors="replace").strip().split()
            if len(parts) == 3 and parts[0] == "GET" and parts[1] == "/health":
                status = "200 OK"
                body = {"connected_clients": await self.clients.count()}

            encoded = json.dumps(body).encode()
            writer.write(
                f"HTTP/1.1 {status}\r\nContent-Type: application/json\r\n"
                f"Content-Length: {len(encoded)}\r\nConnection: close\r\n\r\n".encode()
                + encoded
            )
            await writer.drain()
        except (asyncio.TimeoutError, ConnectionError):
            LOGGER.debug("Health client disconnected before receiving a response")
        finally:
            writer.close()
            await writer.wait_closed()


async def run_server(host: str, websocket_port: int, health_port: int) -> None:
    notification_server = NotificationServer()
    websocket_server: Server
    async with serve(notification_server.websocket_handler, host, websocket_port) as websocket_server:
        health_server = await asyncio.start_server(
            notification_server.health_handler, host, health_port
        )
        LOGGER.info(
            "WebSocket server listening on %s:%d; health endpoint on %s:%d",
            host,
            websocket_port,
            host,
            health_port,
        )
        async with health_server:
            await websocket_server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket port")
    parser.add_argument("--health-port", type=int, default=8080)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_server(args.host, args.port, args.health_port))


if __name__ == "__main__":
    main()
