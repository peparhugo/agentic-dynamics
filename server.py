"""WebSocket notification server.

A single asyncio-based server (built on the ``websockets`` library) that:

* accepts WebSocket connections and assigns each client a unique id,
* broadcasts messages to every connected client,
* delivers direct messages to a single client,
* tracks connections in a thread-safe registry,
* exposes ``GET /health`` returning the connected client count.

Message format
--------------
Every message is JSON: ``{"type": str, "payload": dict, "timestamp": str}``
Supported ``type`` values:

* ``"broadcast"`` - delivered to every connected client,
* ``"direct"``    - delivered to a single client,
* ``"system"``    - server lifecycle notices (e.g. the connect welcome).
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import websockets
from websockets.asyncio.server import Server, serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Headers, Request, Response

from registry import ClientRegistry


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def make_message(msg_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build a message dict following the required wire format."""
    return {"type": msg_type, "payload": payload, "timestamp": utc_now_iso()}


def dumps_message(msg_type: str, payload: Dict[str, Any]) -> str:
    """Serialize a message dict to JSON for sending."""
    return json.dumps(make_message(msg_type, payload))


class NotificationServer:
    """WebSocket notification server with a REST health endpoint."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.registry = ClientRegistry()
        self._ws_server: Optional[Server] = None

    # ── lifecycle ────────────────────────────────────────────────────────

    async def start(self) -> "NotificationServer":
        """Start serving WebSocket connections and the health endpoint."""
        self._ws_server = await serve(
            self.handle_connection,
            self.host,
            self.port,
            process_request=self.process_request,
        )
        if self._ws_server.sockets:
            self.port = self._ws_server.sockets[0].getsockname()[1]
        return self

    async def stop(self) -> None:
        """Shut the server down and wait for all handlers to finish."""
        if self._ws_server is None:
            return
        self._ws_server.close()
        await self._ws_server.wait_closed()
        self._ws_server = None

    # ── websocket handling ───────────────────────────────────────────────

    async def handle_connection(self, connection) -> None:
        """Assign a unique id and keep the client alive until it disconnects."""
        client_id = str(uuid.uuid4())
        self.registry.add(client_id, connection)
        try:
            await self._send(
                connection,
                "system",
                {
                    "message": "connected",
                    "client_id": client_id,
                    "connected_clients": self.registry.count(),
                },
            )
            async for raw in connection:
                await self._on_message(connection, client_id, raw)
        except ConnectionClosed:
            pass
        finally:
            self.registry.remove(client_id)

    async def _on_message(self, connection, client_id: str, raw: str) -> None:
        """Handle an inbound client message (broadcast / direct requests)."""
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return
        if not isinstance(data, dict):
            return
        msg_type = data.get("type")
        payload = data.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        if msg_type == "broadcast":
            await self.broadcast(payload)
        elif msg_type == "direct":
            target = data.get("target")
            if target:
                await self.direct(target, payload)

    # ── messaging API ────────────────────────────────────────────────────

    def broadcast(self, payload: Dict[str, Any]) -> None:
        """Send a ``"broadcast"`` message to every connected client."""
        websockets.broadcast(
            self.registry.connections(),
            dumps_message("broadcast", payload),
        )

    async def direct(self, client_id: str, payload: Dict[str, Any]) -> bool:
        """Send a ``"direct"`` message to one client.

        Returns True when the client exists, False otherwise.
        """
        connection = self.registry.get(client_id)
        if connection is None:
            return False
        await self._send(connection, "direct", payload)
        return True

    async def _send(self, connection, msg_type: str, payload: Dict[str, Any]) -> None:
        await connection.send(dumps_message(msg_type, payload))

    # ── REST: GET /health ────────────────────────────────────────────────

    async def process_request(self, connection, request: Request) -> Optional[Response]:
        """Serve ``GET /health`` as plain HTTP; everything else is WebSocket."""
        if request.path != "/health":
            return None
        body = json.dumps(
            {"connected_clients": self.registry.count()}
        ).encode("utf-8")
        headers = Headers(
            [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
            ]
        )
        return Response(200, "OK", headers, body)


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the notification server until interrupted."""
    server = NotificationServer(host=host, port=port)

    async def _run() -> None:
        await server.start()
        print(f"notification server listening on ws://{server.host}:{server.port}")
        try:
            await asyncio.Future()
        finally:
            await server.stop()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
