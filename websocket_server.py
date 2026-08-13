"""
WebSocket-based notification server with REST health endpoint.
Handles client connections, message broadcasting, and client lifecycle.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Any
from threading import Lock

import websockets
from aiohttp import web


class ClientRegistry:
    """Thread-safe registry of connected WebSocket clients."""

    def __init__(self):
        self._clients: Dict[str, Any] = {}
        self._lock = Lock()

    def add(self, client_id: str, websocket: Any) -> None:
        """Add a client to the registry."""
        with self._lock:
            self._clients[client_id] = websocket

    def remove(self, client_id: str) -> None:
        """Remove a client from the registry."""
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str) -> Any | None:
        """Get a specific client."""
        with self._lock:
            return self._clients.get(client_id)

    def get_all(self) -> Dict[str, Any]:
        """Get all connected clients."""
        with self._lock:
            return dict(self._clients)

    def get_count(self) -> int:
        """Get count of connected clients."""
        with self._lock:
            return len(self._clients)


class NotificationServer:
    """WebSocket notification server with broadcast capabilities."""

    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.registry = ClientRegistry()
        self.server = None
        self.http_runner = None
        self.http_site = None

    async def handle_client(self, websocket: Any, path: str = "") -> None:
        """Handle a new WebSocket connection."""
        client_id = str(uuid.uuid4())
        self.registry.add(client_id, websocket)

        try:
            await websocket.send(json.dumps({
                "type": "system",
                "payload": {
                    "message": "Connected to notification server",
                    "client_id": client_id
                },
                "timestamp": datetime.utcnow().isoformat()
            }))

            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._process_message(data, client_id)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "type": "system",
                        "payload": {"error": "Invalid JSON"},
                        "timestamp": datetime.utcnow().isoformat()
                    }))
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.registry.remove(client_id)

    async def _process_message(self, data: dict, sender_id: str) -> None:
        """Process incoming message and route accordingly."""
        msg_type = data.get("type", "broadcast")
        payload = data.get("payload", {})

        if msg_type == "broadcast":
            await self.broadcast(payload, sender_id)
        elif msg_type == "direct":
            target_id = payload.get("target_id")
            if target_id:
                await self.send_direct(target_id, payload)
        elif msg_type == "system":
            pass

    async def broadcast(self, payload: dict, sender_id: str | None = None) -> None:
        """Broadcast a message to all connected clients."""
        message = json.dumps({
            "type": "broadcast",
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat()
        })

        clients = self.registry.get_all()
        disconnected = []

        for client_id, websocket in clients.items():
            try:
                await websocket.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.append(client_id)

        for client_id in disconnected:
            self.registry.remove(client_id)

    async def send_direct(self, target_id: str, payload: dict) -> None:
        """Send a direct message to a specific client."""
        websocket = self.registry.get(target_id)
        if websocket:
            message = json.dumps({
                "type": "direct",
                "payload": payload,
                "timestamp": datetime.utcnow().isoformat()
            })
            try:
                await websocket.send(message)
            except websockets.exceptions.ConnectionClosed:
                self.registry.remove(target_id)

    async def health_handler(self, request: web.Request) -> web.Response:
        """Health check endpoint that returns connected client count."""
        return web.json_response({
            "status": "healthy",
            "connected_clients": self.registry.get_count()
        })

    async def start(self) -> None:
        """Start both WebSocket and HTTP servers."""
        self.server = await websockets.serve(
            self.handle_client,
            self.host,
            self.port
        )

        app = web.Application()
        app.router.add_get("/health", self.health_handler)

        self.http_runner = web.AppRunner(app)
        await self.http_runner.setup()
        self.http_site = web.TCPSite(self.http_runner, self.host, self.port + 1000)
        await self.http_site.start()

    async def stop(self) -> None:
        """Stop both WebSocket and HTTP servers."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        if self.http_site:
            await self.http_site.stop()
        if self.http_runner:
            await self.http_runner.cleanup()


async def main():
    """Run the notification server."""
    server = NotificationServer(host="0.0.0.0", port=8765)
    await server.start()
    print(f"WebSocket server running on ws://0.0.0.0:8765")
    print(f"Health endpoint at http://0.0.0.0:9765/health")

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        print("Shutting down...")
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
