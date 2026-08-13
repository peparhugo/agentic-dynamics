"""
WebSocket notification server.

Accepts WebSocket connections, assigns each client a unique ID, supports
broadcast / direct / system messages, and exposes a health endpoint both as a
WebSocket 'system' message and via a plain HTTP listener running in a separate
thread (thread-safety is guaranteed by a threading.Lock around the registry).
"""

import asyncio
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from websockets.asyncio.server import serve

WS_HOST = os.environ.get("WS_HOST", "127.0.0.1")
WS_PORT = int(os.environ.get("WS_PORT", "8765"))
HEALTH_HOST = os.environ.get("HEALTH_HOST", "127.0.0.1")
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "8766"))

SUPPORTED_TYPES = ("broadcast", "direct", "system")


def make_message(msg_type: str, payload: dict) -> dict:
    """Build a message in the canonical wire format."""
    return {
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class ClientRegistry:
    """Thread-safe registry of connected clients (client_id -> connection).

    Every mutation is guarded by a threading.Lock so the separate HTTP health
    thread can safely observe and coordinate with the async world.
    """

    def __init__(self):
        self._clients = {}
        self._lock = threading.Lock()

    def add(self, connection) -> str:
        client_id = uuid.uuid4().hex
        with self._lock:
            self._clients[client_id] = connection
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str):
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._clients)

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)


async def broadcast(registry: ClientRegistry, message: dict, exclude: str | None = None) -> None:
    """Broadcast to every connected client by iterating the registry and
    awaiting send() on each connection (websockets.broadcast is deprecated)."""
    for client_id, connection in registry.snapshot().items():
        if exclude is not None and client_id == exclude:
            continue
        try:
            await connection.send(json.dumps(message))
        except Exception:
            registry.remove(client_id)


class NotificationServer:
    """Owns a ClientRegistry and drives the per-connection event loop."""

    def __init__(self, registry: ClientRegistry | None = None):
        self.registry = registry or ClientRegistry()

    async def handle(self, connection) -> None:
        client_id = self.registry.add(connection)
        try:
            await connection.send(
                json.dumps(
                    make_message("system", {"action": "connected", "client_id": client_id})
                )
            )
            async for raw in connection:
                await self._process(client_id, connection, raw)
        finally:
            self.registry.remove(client_id)

    async def _process(self, client_id: str, connection, raw: str) -> None:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            await connection.send(
                json.dumps(make_message("system", {"action": "error", "message": "invalid json"}))
            )
            return

        msg_type = data.get("type")
        payload = data.get("payload") or {}

        if msg_type == "system" and payload.get("action") == "health":
            await connection.send(
                json.dumps(
                    make_message("system", {"action": "health", "client_count": len(self.registry)})
                )
            )
        elif msg_type == "broadcast":
            await broadcast(self.registry, make_message("broadcast", payload))
        elif msg_type == "direct":
            target = payload.get("client_id")
            conn = self.registry.get(target)
            if conn is not None:
                await conn.send(json.dumps(make_message("direct", payload)))
            else:
                await connection.send(
                    json.dumps(
                        make_message("system", {"action": "error", "message": "client not found"})
                    )
                )
        else:
            await connection.send(
                json.dumps(make_message("system", {"action": "error", "message": "unsupported type"}))
            )


def _make_health_handler(registry: ClientRegistry):
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?", 1)[0] == "/health":
                body = json.dumps({"client_count": len(registry)}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)

        def log_message(self, format, *args):
            pass

    return HealthHandler


def start_health_server(registry: ClientRegistry, host: str = HEALTH_HOST, port: int = 0):
    """Run the HTTP health listener in a separate thread."""
    httpd = ThreadingHTTPServer((host, port), _make_health_handler(registry))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def stop_health_server(httpd) -> None:
    httpd.shutdown()
    httpd.server_close()


async def start_ws_server(server: NotificationServer, host: str = WS_HOST, port: int = 0):
    """Start the WebSocket listener and return the underlying server object."""
    return await serve(server.handle, host, port)


async def main():
    server = NotificationServer()
    ws_server = await start_ws_server(server)
    httpd = start_health_server(server.registry)
    ws_port = ws_server.sockets[0].getsockname()[1]
    health_port = httpd.server_address[1]
    print(f"WebSocket listening on {WS_HOST}:{ws_port}")
    print(f"Health listening on {HEALTH_HOST}:{health_port}")
    try:
        await asyncio.Future()
    finally:
        ws_server.close()
        stop_health_server(httpd)


if __name__ == "__main__":
    asyncio.run(main())
