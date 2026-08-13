"""
WebSocket notification server with async support.

Features:
- Accept WebSocket connections from clients with unique IDs
- Broadcast messages to all connected clients
- REST health endpoint: GET /health
- Thread-safe client registry using asyncio locks
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Set
from aiohttp import web
import websockets
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClientRegistry:
    """Thread-safe registry of connected WebSocket clients."""

    def __init__(self):
        self.clients: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.lock = asyncio.Lock()

    async def register(self, client_id: str, websocket: websockets.WebSocketServerProtocol):
        """Register a new client."""
        async with self.lock:
            self.clients[client_id] = websocket
            logger.info(f"Client {client_id} registered. Total clients: {len(self.clients)}")

    async def unregister(self, client_id: str):
        """Remove a client."""
        async with self.lock:
            if client_id in self.clients:
                del self.clients[client_id]
                logger.info(f"Client {client_id} unregistered. Total clients: {len(self.clients)}")

    async def get_client_count(self) -> int:
        """Get the number of connected clients."""
        async with self.lock:
            return len(self.clients)

    async def get_all_clients(self) -> Dict[str, websockets.WebSocketServerProtocol]:
        """Get a copy of all clients."""
        async with self.lock:
            return dict(self.clients)

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        clients = await self.get_all_clients()
        if not clients:
            logger.warning("No clients connected for broadcast")
            return

        message_json = json.dumps(message)
        failed_clients = []

        for client_id, websocket in clients.items():
            try:
                await websocket.send(message_json)
            except websockets.exceptions.ConnectionClosed:
                failed_clients.append(client_id)
            except Exception as e:
                logger.error(f"Error sending to {client_id}: {e}")
                failed_clients.append(client_id)

        for client_id in failed_clients:
            await self.unregister(client_id)


# Global client registry
registry = ClientRegistry()


def create_message(msg_type: str, payload: dict) -> dict:
    """Create a properly formatted message."""
    return {
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.utcnow().isoformat()
    }


async def websocket_handler(websocket: websockets.WebSocketServerProtocol, path: str):
    """Handle WebSocket connections."""
    client_id = str(uuid.uuid4())
    await registry.register(client_id, websocket)

    connect_message = create_message("system", {
        "event": "client_connected",
        "client_id": client_id
    })
    await registry.broadcast(connect_message)

    try:
        async for message_str in websocket:
            try:
                message_data = json.loads(message_str)
                msg_type = message_data.get("type", "broadcast")
                payload = message_data.get("payload", {})

                formatted_message = create_message(msg_type, {
                    **payload,
                    "from_client": client_id
                })

                if msg_type == "broadcast":
                    await registry.broadcast(formatted_message)
                elif msg_type == "direct":
                    target_client = payload.get("to_client")
                    if target_client:
                        clients = await registry.get_all_clients()
                        if target_client in clients:
                            try:
                                await clients[target_client].send(json.dumps(formatted_message))
                            except websockets.exceptions.ConnectionClosed:
                                await registry.unregister(target_client)
                else:
                    logger.warning(f"Unknown message type: {msg_type}")

            except json.JSONDecodeError:
                error_message = create_message("system", {
                    "event": "error",
                    "message": "Invalid JSON format"
                })
                await websocket.send(json.dumps(error_message))
            except Exception as e:
                logger.error(f"Error processing message from {client_id}: {e}")

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await registry.unregister(client_id)
        disconnect_message = create_message("system", {
            "event": "client_disconnected",
            "client_id": client_id
        })
        await registry.broadcast(disconnect_message)


async def health_handler(request):
    """REST endpoint: GET /health - returns connected client count."""
    count = await registry.get_client_count()
    return web.json_response({
        "status": "ok",
        "connected_clients": count,
        "timestamp": datetime.utcnow().isoformat()
    })


async def start_websocket_server(host="0.0.0.0", ws_port=8765):
    """Start WebSocket server."""
    async with websockets.serve(websocket_handler, host, ws_port):
        logger.info(f"WebSocket server listening on ws://{host}:{ws_port}")
        await asyncio.Future()


async def start_rest_server(host="0.0.0.0", rest_port=8080):
    """Start REST API server for health endpoint."""
    app = web.Application()
    app.router.add_get('/health', health_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, rest_port)
    await site.start()
    logger.info(f"REST server listening on http://{host}:{rest_port}")

    return runner


async def main():
    """Start both WebSocket and REST servers."""
    ws_host = "0.0.0.0"
    ws_port = 8765
    rest_host = "0.0.0.0"
    rest_port = 8080

    ws_task = asyncio.create_task(start_websocket_server(ws_host, ws_port))
    rest_runner = await start_rest_server(rest_host, rest_port)

    try:
        await ws_task
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await rest_runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped")
