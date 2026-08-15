"""
WebSocket-based notification server.

Features
--------
- Accept WebSocket connections and assign each client a unique ID.
- Broadcast a message to all connected clients.
- Deliver a "direct" message to a single client by ID.
- Remove clients cleanly on disconnect.
- Expose ``GET /health`` returning the number of connected clients.

Message format
--------------
Every application message is a JSON object::

    {"type": str, "payload": dict, "timestamp": str}

Supported ``type`` values: ``broadcast``, ``direct``, ``system``.

Wire format
-----------
The ``websockets`` library base64-encodes every frame on the wire.  We follow
that contract explicitly: every outgoing JSON message is base64-encoded before
it is sent and every incoming frame is base64-decoded before it is parsed as
JSON.
"""

from __future__ import annotations

import asyncio
import base64
import itertools
import json
import threading
from datetime import datetime, timezone
from typing import Any, Dict

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def encode_message(message: Dict[str, Any]) -> str:
    """Serialize a message to the on-the-wire base64 string."""
    raw = json.dumps(message).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def decode_message(raw: str) -> Dict[str, Any]:
    """Parse a base64 on-the-wire string back into a message dict."""
    data = base64.b64decode(raw.encode("ascii"))
    return json.loads(data.decode("utf-8"))


class ClientRegistry:
    """Thread-safe registry of connected clients."""

    def __init__(self) -> None:
        self._clients: Dict[int, ServerConnection] = {}
        self._lock = threading.Lock()
        self._counter = itertools.count(1)

    def register(self, websocket: ServerConnection) -> int:
        with self._lock:
            client_id = next(self._counter)
            self._clients[client_id] = websocket
            return client_id

    def unregister(self, client_id: int) -> ServerConnection | None:
        with self._lock:
            return self._clients.pop(client_id, None)

    def get(self, client_id: int) -> ServerConnection | None:
        with self._lock:
            return self._clients.get(client_id)

    def count(self) -> int:
        with self._lock:
            return len(self._clients)

    def snapshot(self) -> Dict[int, ServerConnection]:
        with self._lock:
            return dict(self._clients)


class NotificationServer:
    """Asyncio WebSocket notification server."""

    def __init__(self) -> None:
        self.clients = ClientRegistry()
        self._server = None

    async def start(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self._server = await serve(
            self._handle_connection,
            host,
            port,
            process_request=self._process_request,
        )

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    @property
    def port(self) -> int | None:
        if self._server is None or not self._server.sockets:
            return None
        return self._server.sockets[0].getsockname()[1]

    # ── HTTP handler ──────────────────────────────────────────

    def _process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        if request.path == "/health":
            body = json.dumps({"connected_clients": self.clients.count()}).encode("utf-8")
            return Response(200, "OK", Headers([("Content-Type", "application/json")]), body)
        return None

    # ── WebSocket handler ──────────────────────────────────────

    async def _handle_connection(self, websocket: ServerConnection) -> None:
        client_id = self.clients.register(websocket)
        try:
            await websocket.send(
                encode_message(
                    {
                        "type": "system",
                        "payload": {"client_id": client_id, "message": "connected"},
                        "timestamp": utcnow(),
                    }
                )
            )
            async for raw in websocket:
                try:
                    message = decode_message(raw)
                except (ValueError, TypeError):
                    continue
                await self._handle_message(client_id, message)
        finally:
            self.clients.unregister(client_id)

    async def _handle_message(self, sender_id: int, message: Dict[str, Any]) -> None:
        mtype = message.get("type")
        payload = message.get("payload") or {}
        timestamp = message.get("timestamp") or utcnow()

        if mtype == "broadcast":
            outgoing = {"type": "broadcast", "payload": payload, "timestamp": timestamp}
            outgoing["payload"]["sender_id"] = sender_id
            await self.broadcast(outgoing)
        elif mtype == "direct":
            target = payload.get("client_id")
            connection = self.clients.get(target)
            if connection is not None:
                outgoing = {"type": "direct", "payload": payload, "timestamp": timestamp}
                outgoing["payload"]["sender_id"] = sender_id
                await connection.send(encode_message(outgoing))

    # ── Public API ─────────────────────────────────────────────

    async def broadcast(self, message: Dict[str, Any]) -> None:
        encoded = encode_message(message)
        for websocket in self.clients.snapshot().values():
            try:
                await websocket.send(encoded)
            except Exception:
                continue


async def main() -> None:
    server = NotificationServer()
    await server.start(host="127.0.0.1", port=8765)
    print(f"notification server listening on ws://127.0.0.1:{server.port}")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
