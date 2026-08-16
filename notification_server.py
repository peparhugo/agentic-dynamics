"""WebSocket-based notification server built on the `websockets` library.

Core features:
- Accepts WebSocket connections and assigns each client a unique ID.
- Broadcasts messages to all connected clients.
- Routes direct messages to a single target client.
- Sends server-generated system messages (connect ack, errors, ...).
- Cleans up clients on disconnect.
- Exposes a REST ``GET /health`` endpoint reporting the connected client
  count via a small background HTTP server.

Message format (JSON): ``{type: str, payload: dict, timestamp: str}``.
Supported types: ``broadcast``, ``direct``, ``system``.

Thread safety: everything runs on a single asyncio event loop, so the client
registry needs no locking -- plain dict reads and writes are safe by
construction, even when the background HTTP server thread reads the registry.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import websockets


def make_message(msg_type: str, payload: dict | None = None) -> dict:
    """Build a message conforming to the standard wire format."""
    return {
        "type": msg_type,
        "payload": payload or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class ClientRegistry:
    """Thread-safe client registry mapping client IDs to WebSocket objects.

    asyncio runs everything on a single event loop, so plain dict operations
    are always safe here -- no locking is required even when background
    threads (e.g. the HTTP health server thread) read the registry.
    """

    def __init__(self) -> None:
        self._clients: dict[str, websockets.ServerConnection] = {}
        self._next_id: int = 1

    def add(self, websocket) -> str:
        """Register a connection and return its unique client ID."""
        client_id = str(self._next_id)
        self._next_id += 1
        self._clients[client_id] = websocket
        return client_id

    def remove(self, client_id: str) -> None:
        """Remove a client from the registry (no-op if already gone)."""
        self._clients.pop(client_id, None)

    def get(self, client_id: str):
        """Return the WebSocket for a client ID, or None."""
        return self._clients.get(client_id)

    def count(self) -> int:
        """Number of connected clients."""
        return len(self._clients)

    def connected_ids(self) -> list[str]:
        """Snapshot of the connected client IDs."""
        return list(self._clients)

    def items(self) -> list[tuple[str, websockets.ServerConnection]]:
        """Snapshot of ``(client_id, websocket)`` pairs."""
        return list(self._clients.items())


def build_health_handler(registry: ClientRegistry):
    """Build a ``BaseHTTPRequestHandler`` reporting connected client counts.

    ``GET /health`` -> 200 ``{"status": "ok", "connected_clients": N}``
    """

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler API)
            if self.path in ("/health", "/health/"):
                self._send_json(
                    200,
                    {"status": "ok", "connected_clients": registry.count()},
                )
            else:
                self._send_json(404, {"error": "not found"})

        def _send_json(self, code: int, data: dict) -> None:
            body = json.dumps(data).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args) -> None:  # keep test output clean
            pass

    return HealthHandler


class NotificationServer:
    """Async WebSocket notification server with a ``/health`` REST endpoint."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        ws_port: int = 0,
        http_port: int = 0,
        registry: ClientRegistry | None = None,
    ) -> None:
        self.host = host
        self.ws_port = ws_port
        self.http_port = http_port
        self.registry = registry or ClientRegistry()
        self.ws_url: str | None = None
        self.http_url: str | None = None
        self._ws_server = None
        self._http_server: ThreadingHTTPServer | None = None
        self._http_thread: Thread | None = None

    async def start(self) -> "NotificationServer":
        """Start the WebSocket server and the background HTTP server."""
        self._ws_server = await websockets.serve(
            self._handle_connection, self.host, self.ws_port
        )
        bound_port = self._ws_server.sockets[0].getsockname()[1]
        self.ws_port = bound_port
        self.ws_url = f"ws://{self.host}:{bound_port}"

        self._http_server = ThreadingHTTPServer(
            (self.host, self.http_port), build_health_handler(self.registry)
        )
        self.http_port = self._http_server.server_address[1]
        self.http_url = f"http://{self.host}:{self.http_port}"
        self._http_thread = Thread(
            target=self._http_server.serve_forever, daemon=True
        )
        self._http_thread.start()
        return self

    async def stop(self) -> None:
        """Stop both servers and release their ports."""
        if self._http_server is not None:
            self._http_server.shutdown()
            self._http_server.server_close()
            if self._http_thread is not None:
                self._http_thread.join(timeout=5)
            self._http_server = None
            self._http_thread = None
        if self._ws_server is not None:
            self._ws_server.close()
            await self._ws_server.wait_closed()
            self._ws_server = None

    async def _handle_connection(self, websocket) -> None:
        """Per-connection handler: assign ID, pump messages, clean up."""
        client_id = self.registry.add(websocket)
        try:
            await websocket.send(
                json.dumps(
                    make_message(
                        "system",
                        {"event": "connected", "client_id": client_id},
                    )
                )
            )
            async for raw in websocket:
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    await self._send_error(
                        websocket, "invalid JSON payload"
                    )
                    continue
                await self._dispatch(websocket, client_id, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.registry.remove(client_id)

    async def _dispatch(self, websocket, sender_id: str, message: dict) -> None:
        """Route an incoming client message."""
        msg_type = message.get("type")
        payload = message.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}

        if msg_type == "broadcast":
            outbound = make_message("broadcast", {"from": sender_id, **payload})
            await self.broadcast(outbound)
        elif msg_type == "direct":
            target = payload.get("to")
            if not target:
                await self._send_error(websocket, "direct message missing 'to'")
                return
            outbound = make_message(
                "direct",
                {
                    "from": sender_id,
                    "to": target,
                    "data": payload.get("data", {}),
                },
            )
            delivered = await self.send_to(target, outbound)
            if not delivered:
                await self._send_error(
                    websocket, "target not connected", to=target
                )
        elif msg_type == "system":
            await websocket.send(
                json.dumps(
                    make_message(
                        "system",
                        {"event": "ack", "from": sender_id},
                    )
                )
            )
        else:
            await self._send_error(
                websocket, f"unsupported message type: {msg_type}"
            )

    async def _send_error(self, websocket, error: str, **extra) -> None:
        try:
            await websocket.send(
                json.dumps(
                    make_message(
                        "system",
                        {"event": "error", "error": error, **extra},
                    )
                )
            )
        except websockets.exceptions.ConnectionClosed:
            pass

    async def broadcast(self, message: dict) -> None:
        """Send a message to every connected client."""
        data = json.dumps(message)
        for client_id, ws in self.registry.items():
            try:
                await ws.send(data)
            except websockets.exceptions.ConnectionClosed:
                self.registry.remove(client_id)

    async def send_to(self, client_id: str, message: dict) -> bool:
        """Send a message to a single client. Returns False if it is gone."""
        ws = self.registry.get(client_id)
        if ws is None:
            return False
        try:
            await ws.send(json.dumps(message))
        except websockets.exceptions.ConnectionClosed:
            self.registry.remove(client_id)
            return False
        return True
