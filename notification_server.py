"""
WebSocket-based notification server with async support and thread-safe client registry.

Features:
- Accept WebSocket connections from clients
- Assign unique IDs to each client
- Broadcast messages to all connected clients
- Handle client disconnect
- REST endpoint: GET /health with connected client count
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Set, Dict, Any
import logging

import websockets
from websockets.asyncio.server import serve, ServerConnection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClientRegistry:
    """Thread-safe registry of connected WebSocket clients."""

    def __init__(self):
        self._clients: Dict[str, ServerConnection] = {}
        self._lock = Lock()

    def add(self, client_id: str, connection: ServerConnection) -> None:
        """Add a client to the registry."""
        with self._lock:
            self._clients[client_id] = connection

    def remove(self, client_id: str) -> None:
        """Remove a client from the registry."""
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str) -> ServerConnection | None:
        """Get a client connection by ID."""
        with self._lock:
            return self._clients.get(client_id)

    def get_all(self) -> Dict[str, ServerConnection]:
        """Get a copy of all clients."""
        with self._lock:
            return dict(self._clients)

    def count(self) -> int:
        """Get the number of connected clients."""
        with self._lock:
            return len(self._clients)


class NotificationMessage:
    """Message formatter for notifications."""

    def __init__(self, msg_type: str, payload: dict | None = None):
        self.type = msg_type
        self.payload = payload or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps({
            "type": self.type,
            "payload": self.payload,
            "timestamp": self.timestamp,
        })

    @staticmethod
    def from_json(data: str) -> "NotificationMessage":
        """Parse JSON string to NotificationMessage."""
        obj = json.loads(data)
        msg = NotificationMessage(obj["type"], obj.get("payload", {}))
        if "timestamp" in obj:
            msg.timestamp = obj["timestamp"]
        return msg


class NotificationServer:
    """WebSocket notification server with broadcast capability."""

    def __init__(self, host: str = "127.0.0.1", ws_port: int = 8765, http_port: int = 8080):
        self.host = host
        self.ws_port = ws_port
        self.http_port = http_port
        self.clients = ClientRegistry()
        self.loop = None

    async def handle_client(self, websocket: ServerConnection) -> None:
        """Handle a connected WebSocket client."""
        client_id = str(uuid.uuid4())
        self.clients.add(client_id, websocket)

        logger.info(f"Client {client_id} connected. Total clients: {self.clients.count()}")

        try:
            system_msg = NotificationMessage(
                "system",
                {"action": "connected", "client_id": client_id}
            )
            await websocket.send(system_msg.to_json())

            async for message in websocket:
                try:
                    msg = NotificationMessage.from_json(message)
                    logger.info(f"Received from {client_id}: {msg.type}")

                    if msg.type == "broadcast":
                        await self.broadcast(
                            NotificationMessage("broadcast", msg.payload)
                        )
                    elif msg.type == "direct":
                        target_id = msg.payload.get("target_id")
                        if target_id:
                            await self.send_direct(target_id, msg)
                    elif msg.type == "system":
                        await self.broadcast(msg)

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from {client_id}: {e}")
                    error_msg = NotificationMessage(
                        "system",
                        {"action": "error", "message": "Invalid JSON format"}
                    )
                    await websocket.send(error_msg.to_json())

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(client_id)
            logger.info(f"Client {client_id} disconnected. Total clients: {self.clients.count()}")

    async def broadcast(self, message: NotificationMessage) -> None:
        """Broadcast a message to all connected clients."""
        clients = self.clients.get_all()
        if not clients:
            logger.debug("No clients to broadcast to")
            return

        message_json = message.to_json()
        tasks = []

        for client_id, connection in clients.items():
            tasks.append(self._send_safe(connection, message_json, client_id))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_safe(self, connection: ServerConnection, message: str, client_id: str) -> None:
        """Safely send a message to a connection, handling disconnects."""
        try:
            await connection.send(message)
        except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
            logger.debug(f"Failed to send to {client_id} (disconnected)")
        except Exception as e:
            logger.error(f"Error sending to {client_id}: {e}")

    async def send_direct(self, target_id: str, message: NotificationMessage) -> None:
        """Send a message to a specific client."""
        connection = self.clients.get(target_id)
        if connection:
            await self._send_safe(connection, message.to_json(), target_id)
        else:
            logger.warning(f"Target client {target_id} not found")

    async def http_health(self, reader, writer) -> None:
        """Simple HTTP server for /health endpoint."""
        request_line = await reader.readline()
        request_line = request_line.decode().strip()

        if not request_line:
            writer.close()
            return

        parts = request_line.split()
        if len(parts) < 2:
            writer.close()
            return

        method, path = parts[0], parts[1]

        if method == "GET" and path == "/health":
            client_count = self.clients.count()
            response_body = json.dumps({"connected_clients": client_count})
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(response_body)}\r\n"
                "Connection: close\r\n"
                "\r\n"
                f"{response_body}"
            )
            writer.write(response.encode())
        else:
            response = (
                "HTTP/1.1 404 Not Found\r\n"
                "Content-Type: text/plain\r\n"
                "Connection: close\r\n"
                "\r\n"
                "Not Found"
            )
            writer.write(response.encode())

        await writer.drain()
        writer.close()

    async def http_server(self) -> None:
        """Start HTTP server for health checks."""
        server = await asyncio.start_server(
            self.http_health,
            self.host,
            self.http_port
        )
        logger.info(f"HTTP server listening on {self.host}:{self.http_port}")
        async with server:
            await server.serve_forever()

    async def ws_server(self) -> None:
        """Start WebSocket server."""
        async with serve(self.handle_client, self.host, self.ws_port):
            logger.info(f"WebSocket server listening on ws://{self.host}:{self.ws_port}")
            await asyncio.Future()  # Run forever

    async def start(self) -> None:
        """Start both WebSocket and HTTP servers."""
        self.loop = asyncio.get_running_loop()
        await asyncio.gather(
            self.ws_server(),
            self.http_server(),
        )


def create_server(host: str = "127.0.0.1", ws_port: int = 8765, http_port: int = 8080) -> NotificationServer:
    """Factory function to create a NotificationServer."""
    return NotificationServer(host=host, ws_port=ws_port, http_port=http_port)


if __name__ == "__main__":
    server = create_server()
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server shutting down")
