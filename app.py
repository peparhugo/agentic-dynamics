"""
WebSocket-based notification server.

Features:
- Accept WebSocket connections from clients
- Assign each client a unique ID on connect
- Broadcast a message to ALL connected clients
- Handle client disconnect (clean removal)
- REST endpoint: GET /health -> connected client count

Message format (JSON): {type: str, payload: dict, timestamp: str}
Supported types: 'broadcast', 'direct', 'system'
"""

import asyncio
import base64
import json
import threading
from datetime import datetime, timezone
from itertools import count

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Response


def utcnow_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def encode_message(message: dict) -> str:
    """Serialize a message to JSON and base64-encode it for the wire."""
    return base64.b64encode(json.dumps(message).encode("utf-8")).decode("ascii")


def decode_message(raw: str) -> dict:
    """Base64-decode an incoming frame and parse it as JSON."""
    return json.loads(base64.b64decode(raw.encode("ascii")).decode("utf-8"))


class ClientRegistry:
    """Thread-safe registry of connected WebSocket clients."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clients: dict[int, ServerConnection] = {}
        self._ids = count(1)

    def add(self, connection: ServerConnection) -> int:
        """Register a connection and return its unique client ID."""
        with self._lock:
            client_id = next(self._ids)
            self._clients[client_id] = connection
            return client_id

    def remove(self, client_id: int) -> None:
        """Remove a client from the registry (idempotent)."""
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: int):
        """Return a client's connection by ID, or None."""
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> list[tuple[int, ServerConnection]]:
        """Return a consistent snapshot of all connected clients."""
        with self._lock:
            return list(self._clients.items())

    def count(self) -> int:
        """Return the number of currently connected clients."""
        with self._lock:
            return len(self._clients)


def make_message(message_type: str, payload: dict, timestamp: str | None = None) -> dict:
    """Build a well-formed message."""
    return {
        "type": message_type,
        "payload": payload,
        "timestamp": timestamp or utcnow_iso(),
    }


class NotificationServer:
    """WebSocket notification server with a bound client registry."""

    def __init__(self, registry: ClientRegistry | None = None) -> None:
        self.registry = registry or ClientRegistry()

    async def send(self, connection: ServerConnection, message: dict) -> None:
        """Encode and send a message to a single client."""
        await connection.send(encode_message(message))

    async def broadcast(self, message: dict) -> None:
        """Send a message to every connected client."""
        encoded = encode_message(message)
        for client_id, connection in self.registry.snapshot():
            try:
                await connection.send(encoded)
            except Exception:
                self.registry.remove(client_id)

    async def dispatch(self, connection: ServerConnection, client_id: int, message: dict) -> None:
        """Route an incoming message based on its type."""
        message_type = message.get("type")
        message.setdefault("timestamp", utcnow_iso())

        if message_type == "broadcast":
            await self.broadcast(message)
        elif message_type == "direct":
            payload = message.get("payload") or {}
            target = payload.get("to", payload.get("id"))
            target_connection = self.registry.get(target)
            if target_connection is not None:
                await self.send(target_connection, message)

    async def handle(self, connection: ServerConnection) -> None:
        """Handle a single WebSocket connection lifecycle."""
        client_id = self.registry.add(connection)
        try:
            await self.send(
                connection,
                make_message("system", {"event": "connected", "id": client_id}),
            )
            async for raw in connection:
                message = decode_message(raw)
                await self.dispatch(connection, client_id, message)
        finally:
            self.registry.remove(client_id)
            await self.broadcast(
                make_message("system", {"event": "disconnected", "id": client_id})
            )

    def process_request(self, connection: ServerConnection, request) -> Response | None:
        """Serve the /health REST endpoint and pass WebSocket upgrades through."""
        if request.path == "/health":
            body = json.dumps({"connected_clients": self.registry.count()}).encode("utf-8")
            headers = Headers({"Content-Type": "application/json"})
            return Response(200, "OK", headers, body)
        return None


def create_server(host: str = "127.0.0.1", port: int = 8765):
    """Create a websockets server for a fresh NotificationServer instance."""
    notification_server = NotificationServer()
    return notification_server, serve(
        notification_server.handle,
        host,
        port,
        process_request=notification_server.process_request,
    )


async def main() -> None:
    notification_server, server = create_server()
    server = await server
    host, port = server.sockets[0].getsockname()[:2]
    print(f"Notification server listening on ws://{host}:{port}")
    await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
