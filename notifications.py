"""WebSocket-based notification server.

A single-file server built on the ``websockets`` library (not Flask-SocketIO).
It accepts WebSocket connections, assigns each client a unique ID, supports
broadcast / direct / system message types, and exposes a REST ``GET /health``
endpoint reporting the number of connected clients.

Everything runs inside a single asyncio event loop. Because asyncio guarantees
thread safety by construction, the client registry uses a plain dict with no
locking, even when background threads touch the registry.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from itertools import count
from typing import Any

import websockets
from aiohttp import web
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

log = logging.getLogger(__name__)

_client_ids = count(1)

# Supported message types.
TYPE_BROADCAST = "broadcast"
TYPE_DIRECT = "direct"
TYPE_SYSTEM = "system"

ALLOWED_TYPES = {TYPE_BROADCAST, TYPE_DIRECT, TYPE_SYSTEM}


def utcnow_iso() -> str:
    """ISO-8601 UTC timestamp for messages."""
    return datetime.now(timezone.utc).isoformat()


def make_message(message_type: str, payload: dict) -> dict:
    """Build a message dict with the required {type, payload, timestamp} shape."""
    return {
        "type": message_type,
        "payload": payload,
        "timestamp": utcnow_iso(),
    }


def serialize(message: dict) -> str:
    """Serialize a message dict to a JSON string."""
    return json.dumps(message)


class ClientRegistry:
    """Registry of connected WebSocket clients.

    asyncio runs everything on a single event loop, so plain dict reads and
    writes are always safe — no locking is required even when background
    threads touch the registry.
    """

    def __init__(self) -> None:
        self._clients: dict[str, websockets.ServerConnection] = {}

    def add(self, websocket: websockets.ServerConnection) -> str:
        """Register a client and return its unique ID."""
        client_id = f"client-{next(_client_ids)}"
        self._clients[client_id] = websocket
        return client_id

    def remove(self, client_id: str) -> websockets.ServerConnection | None:
        """Remove a client and return the removed connection, if any."""
        return self._clients.pop(client_id, None)

    def get(self, client_id: str) -> websockets.ServerConnection | None:
        """Return the connection for a client ID, if present."""
        return self._clients.get(client_id)

    def connections(self) -> list[websockets.ServerConnection]:
        """Return all live connections."""
        return list(self._clients.values())

    @property
    def count(self) -> int:
        """Number of connected clients."""
        return len(self._clients)


class NotificationServer:
    """WebSocket notification server with a REST health endpoint."""

    def __init__(self, host: str = "127.0.0.1", ws_port: int = 8765,
                 rest_port: int = 8080) -> None:
        self.host = host
        self.ws_port = ws_port
        self.rest_port = rest_port
        self.registry = ClientRegistry()
        self._ws_server: websockets.Server | None = None
        self._rest_runner: web.AppRunner | None = None
        self._rest_site: web.TCPSite | None = None
        self.ws_bound_port: int | None = None
        self.rest_bound_port: int | None = None

    @property
    def connected_clients(self) -> int:
        """Convenience alias for the current client count."""
        return self.registry.count

    # ── lifecycle ───────────────────────────────────────────────

    async def start(self) -> "NotificationServer":
        """Start the WebSocket server and the REST endpoint."""
        self._ws_server = await serve(
            self.ws_handler, self.host, self.ws_port
        )
        self.ws_bound_port = self._ws_server.sockets[0].getsockname()[1]

        rest_app = web.Application()
        rest_app.router.add_get("/health", self.health_handler)
        self._rest_runner = web.AppRunner(rest_app)
        await self._rest_runner.setup()
        self._rest_site = web.TCPSite(self._rest_runner, self.host, self.rest_port)
        await self._rest_site.start()
        self.rest_bound_port = self._rest_site._server.sockets[0].getsockname()[1]

        log.info(
            "Notification server listening on ws://%s:%s and http://%s:%s",
            self.host, self.ws_bound_port, self.host, self.rest_bound_port,
        )
        return self

    async def stop(self) -> None:
        """Stop the WebSocket server and the REST endpoint."""
        if self._ws_server is not None:
            self._ws_server.close()
            await self._ws_server.wait_closed()
        if self._rest_runner is not None:
            await self._rest_runner.cleanup()

    # ── websocket handling ─────────────────────────────────────

    async def ws_handler(self, websocket: websockets.ServerConnection) -> None:
        """Handle a single WebSocket connection lifetime."""
        client_id = self.registry.add(websocket)
        await self._send(client_id, make_message(
            TYPE_SYSTEM,
            {"client_id": client_id, "message": "connected"},
        ))
        try:
            async for raw in websocket:
                await self._handle_client_message(client_id, raw)
        except ConnectionClosed:
            pass
        finally:
            self.registry.remove(client_id)
            await self.broadcast(make_message(
                TYPE_SYSTEM,
                {"client_id": client_id, "message": "disconnected"},
            ))

    async def _handle_client_message(self, sender_id: str, raw: Any) -> None:
        """Parse and dispatch a message received from a client."""
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            await self._send(sender_id, make_message(
                TYPE_SYSTEM, {"error": "invalid JSON message"}
            ))
            return

        message_type = data.get("type")
        payload = data.get("payload") or {}

        if message_type not in ALLOWED_TYPES:
            await self._send(sender_id, make_message(
                TYPE_SYSTEM,
                {"error": f"unsupported message type: {message_type!r}"},
            ))
            return

        if message_type == TYPE_BROADCAST:
            await self.broadcast(make_message(
                TYPE_BROADCAST, {"sender": sender_id, **payload}
            ))
        elif message_type == TYPE_DIRECT:
            target = payload.get("target_id")
            if target is None or self.registry.get(target) is None:
                await self._send(sender_id, make_message(
                    TYPE_SYSTEM,
                    {"error": "direct target not connected",
                     "target_id": target},
                ))
                return
            await self.direct(target, make_message(
                TYPE_DIRECT, {"sender": sender_id, **payload}
            ))
        else:  # TYPE_SYSTEM
            await self.broadcast(make_message(
                TYPE_SYSTEM, {"sender": sender_id, **payload}
            ))

    # ── messaging primitives ───────────────────────────────────

    async def _send(self, client_id: str, message: dict) -> None:
        """Send a message dict to a single client."""
        connection = self.registry.get(client_id)
        if connection is None:
            return
        await connection.send(serialize(message))

    async def send(self, client_id: str, message: dict) -> None:
        """Public alias for :meth:`_send`."""
        await self._send(client_id, message)

    async def direct(self, client_id: str, message: dict) -> None:
        """Send a message directly to one client by ID."""
        await self._send(client_id, message)

    async def broadcast(self, message: dict) -> None:
        """Broadcast a message dict to every connected client."""
        connections = self.registry.connections()
        if connections:
            websockets.broadcast(connections, serialize(message))

    # ── REST endpoints ─────────────────────────────────────────

    async def health_handler(self, request: web.Request) -> web.Response:
        """REST ``GET /health`` — report the connected client count."""
        return web.json_response({
            "status": "ok",
            "clients": self.registry.count,
        })
