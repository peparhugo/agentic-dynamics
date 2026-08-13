"""
WebSocket-based notification server with REST health endpoint.

Features:
- WebSocket connections with unique client IDs
- Broadcast messages to all connected clients
- Direct messages to specific clients
- System messages
- REST health endpoint
- Thread-safe client registry
"""

import asyncio
import json
import uuid
from datetime import datetime
from threading import Lock
from typing import Dict, Set, Any

import websockets
from aiohttp import web


class NotificationServer:
    """Thread-safe WebSocket notification server."""

    def __init__(self):
        self.clients: Dict[str, Any] = {}
        self.lock = Lock()

    def add_client(self, client_id: str, websocket) -> None:
        """Add a client to the registry."""
        with self.lock:
            self.clients[client_id] = websocket

    def remove_client(self, client_id: str) -> None:
        """Remove a client from the registry."""
        with self.lock:
            self.clients.pop(client_id, None)

    def get_client_count(self) -> int:
        """Get the number of connected clients."""
        with self.lock:
            return len(self.clients)

    def get_all_clients(self) -> Dict[str, Any]:
        """Get a snapshot of all clients."""
        with self.lock:
            return self.clients.copy()

    async def broadcast(self, message: dict) -> None:
        """Broadcast a message to all connected clients."""
        if not message.get("timestamp"):
            message["timestamp"] = datetime.utcnow().isoformat()

        msg_json = json.dumps(message)
        clients = self.get_all_clients()

        # Create tasks for all sends
        tasks = [self._send_to_client(ws, msg_json) for ws in clients.values()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_to_client(self, websocket, message: str) -> None:
        """Send a message to a client, silently skip if send fails."""
        try:
            await websocket.send(message)
        except Exception:
            pass

    async def send_direct(self, client_id: str, message: dict) -> bool:
        """Send a direct message to a specific client."""
        if not message.get("timestamp"):
            message["timestamp"] = datetime.utcnow().isoformat()

        clients = self.get_all_clients()
        if client_id not in clients:
            return False

        try:
            await clients[client_id].send(json.dumps(message))
            return True
        except Exception:
            return False


# Global server instance
server = NotificationServer()


async def handle_websocket(websocket, path):
    """Handle WebSocket connections."""
    client_id = str(uuid.uuid4())
    server.add_client(client_id, websocket)

    # Send connection confirmation
    await websocket.send(
        json.dumps({
            "type": "system",
            "payload": {"message": "connected", "client_id": client_id},
            "timestamp": datetime.utcnow().isoformat(),
        })
    )

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get("type")
                payload = data.get("payload", {})

                if msg_type == "broadcast":
                    await server.broadcast({
                        "type": "broadcast",
                        "payload": payload,
                    })
                elif msg_type == "direct":
                    target_id = payload.get("client_id")
                    direct_payload = payload.get("message", {})
                    await server.send_direct(target_id, {
                        "type": "direct",
                        "payload": {
                            "from": client_id,
                            "message": direct_payload,
                        },
                    })
            except json.JSONDecodeError:
                await websocket.send(
                    json.dumps({
                        "type": "system",
                        "payload": {"error": "invalid json"},
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                )
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        server.remove_client(client_id)


async def health_handler(request):
    """REST endpoint for health check."""
    return web.json_response({
        "status": "ok",
        "connected_clients": server.get_client_count(),
    })


async def start_websocket_server(host: str = "localhost", port: int = 8765):
    """Start the WebSocket server."""
    async with websockets.serve(handle_websocket, host, port):
        print(f"WebSocket server running on ws://{host}:{port}")
        await asyncio.Event().wait()


async def start_rest_server(host: str = "localhost", port: int = 8080):
    """Start the REST server."""
    app = web.Application()
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    print(f"REST server running on http://{host}:{port}")
    await asyncio.Event().wait()


async def main(ws_host: str = "localhost", ws_port: int = 8765,
               rest_host: str = "localhost", rest_port: int = 8080):
    """Start both WebSocket and REST servers."""
    ws_task = asyncio.create_task(start_websocket_server(ws_host, ws_port))
    rest_task = asyncio.create_task(start_rest_server(rest_host, rest_port))
    await asyncio.gather(ws_task, rest_task)


if __name__ == "__main__":
    asyncio.run(main())
