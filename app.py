"""
WebSocket-based notification server with REST health endpoint.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict
import websockets
from websockets.exceptions import ConnectionClosed
from aiohttp import web


class ClientRegistry:
    """Thread-safe registry of connected WebSocket clients."""

    def __init__(self):
        self.clients: Dict[str, object] = {}
        self.lock = asyncio.Lock()

    async def register(self, client_id: str, websocket: object):
        async with self.lock:
            self.clients[client_id] = websocket

    async def unregister(self, client_id: str):
        async with self.lock:
            self.clients.pop(client_id, None)

    async def get_client_count(self) -> int:
        async with self.lock:
            return len(self.clients)

    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        async with self.lock:
            disconnected = set()
            for client_id, websocket in self.clients.items():
                try:
                    await websocket.send(json.dumps(message))
                except (ConnectionClosed, Exception):
                    disconnected.add(client_id)

        for client_id in disconnected:
            await self.unregister(client_id)

    async def send_direct(self, client_id: str, message: dict):
        """Send message to specific client."""
        async with self.lock:
            websocket = self.clients.get(client_id)

        if websocket:
            try:
                await websocket.send(json.dumps(message))
            except (ConnectionClosed, Exception):
                await self.unregister(client_id)


# Global registry
registry = ClientRegistry()


def create_message(msg_type: str, payload: dict) -> dict:
    """Create a properly formatted message."""
    return {
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.utcnow().isoformat(),
    }


async def websocket_handler(websocket):
    """Handle WebSocket connection."""
    client_id = str(uuid.uuid4())

    # Register client
    await registry.register(client_id, websocket)

    # Notify all clients of new connection
    await registry.broadcast(
        create_message("system", {"event": "client_joined", "client_id": client_id})
    )

    try:
        async for raw_message in websocket:
            try:
                message = json.loads(raw_message)
                msg_type = message.get("type")

                if msg_type == "broadcast":
                    await registry.broadcast(
                        create_message("broadcast", message.get("payload", {}))
                    )
                elif msg_type == "direct":
                    target_client_id = message.get("target_client_id")
                    if target_client_id:
                        await registry.send_direct(
                            target_client_id,
                            create_message("direct", message.get("payload", {})),
                        )
                else:
                    await websocket.send(
                        json.dumps(
                            create_message("system", {"error": f"Unknown message type: {msg_type}"})
                        )
                    )
            except json.JSONDecodeError:
                await websocket.send(
                    json.dumps(create_message("system", {"error": "Invalid JSON"}))
                )
    except ConnectionClosed:
        pass
    finally:
        # Unregister client
        await registry.unregister(client_id)
        # Notify all clients of disconnection
        await registry.broadcast(
            create_message("system", {"event": "client_left", "client_id": client_id})
        )


async def health_handler(request):
    """Health check endpoint returning connected client count."""
    count = await registry.get_client_count()
    return web.json_response({"status": "ok", "connected_clients": count})


async def start_servers():
    """Start both WebSocket and REST servers."""
    async with websockets.serve(websocket_handler, "localhost", 8765):
        app = web.Application()
        app.router.add_get("/health", health_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "localhost", 8766)
        await site.start()

        print("WebSocket server running on ws://localhost:8765")
        print("REST API running on http://localhost:8766")

        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(start_servers())
