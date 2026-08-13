"""
WebSocket-based notification server.

Accepts WebSocket connections, assigns each client a unique ID, broadcasts
messages to all connected clients, handles clean disconnects, and exposes a
REST endpoint ``GET /health`` returning the connected client count.

Message format (JSON)::

    {"type": str, "payload": dict, "timestamp": str}

Supported types: ``"broadcast"``, ``"direct"``, ``"system"``.
"""

import asyncio
import json
import os
import threading
import uuid
from datetime import datetime, timezone

import websockets
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

MESSAGE_TYPES = ("broadcast", "direct", "system")

HEALTH_PATH = "/health"
WEBSOCKET_PATHS = ("/", "/ws")


def now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def make_message(msg_type: str, payload: dict, timestamp: str | None = None) -> dict:
    """Build a message dict conforming to the canonical message format."""
    if msg_type not in MESSAGE_TYPES:
        raise ValueError(f"unsupported message type: {msg_type!r}")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
    return {
        "type": msg_type,
        "payload": payload,
        "timestamp": timestamp or now_iso(),
    }


class ClientRegistry:
    """
    Thread-safe registry mapping client IDs to their WebSocket connections.

    All operations are protected by a reentrant lock so the registry can be
    mutated from the asyncio event loop or from plain threads (e.g. the
    synchronous HTTP health check) without corruption.
    """

    def __init__(self) -> None:
        self._clients: dict[str, object] = {}
        self._lock = threading.RLock()

    def add(self, client_id: str, websocket: object) -> None:
        with self._lock:
            self._clients[client_id] = websocket

    def remove(self, client_id: str) -> object | None:
        with self._lock:
            return self._clients.pop(client_id, None)

    def get(self, client_id: str) -> object | None:
        with self._lock:
            return self._clients.get(client_id)

    def all(self) -> list[tuple[str, object]]:
        with self._lock:
            return list(self._clients.items())

    def count(self) -> int:
        with self._lock:
            return len(self._clients)


class NotificationServer:
    """WebSocket notification server built on the ``websockets`` library."""

    def __init__(self, registry: ClientRegistry | None = None) -> None:
        self.registry = registry or ClientRegistry()

    async def handler(self, websocket) -> None:
        """Handle a single WebSocket connection lifecycle."""
        client_id = self._new_client_id()
        self.registry.add(client_id, websocket)
        welcome = make_message(
            "system",
            {"client_id": client_id, "message": "connected"},
        )
        try:
            await websocket.send(json.dumps(welcome))
            async for raw in websocket:
                await self._handle_message(client_id, websocket, raw)
        except ConnectionClosed:
            pass
        finally:
            self.registry.remove(client_id)

    def _new_client_id(self) -> str:
        while True:
            candidate = str(uuid.uuid4())
            if self.registry.get(candidate) is None:
                return candidate

    async def _handle_message(self, sender_id: str, websocket, raw: str) -> None:
        try:
            message = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            await self._send_error(websocket, "message must be valid JSON")
            return

        if not isinstance(message, dict):
            await self._send_error(websocket, "message must be a JSON object")
            return

        msg_type = message.get("type")
        payload = message.get("payload")
        timestamp = message.get("timestamp") or now_iso()

        if msg_type not in MESSAGE_TYPES:
            await self._send_error(websocket, f"unsupported message type: {msg_type!r}")
            return
        if not isinstance(payload, dict):
            await self._send_error(websocket, "payload must be an object")
            return

        if msg_type == "broadcast":
            await self.broadcast(msg_type, payload, timestamp)
        elif msg_type == "direct":
            await self._handle_direct(sender_id, websocket, payload, timestamp)
        elif msg_type == "system":
            await websocket.send(
                json.dumps(
                    make_message(
                        "system",
                        {"message": "ack", "echo": payload},
                        timestamp,
                    )
                )
            )

    async def _handle_direct(
        self,
        sender_id: str,
        sender_ws,
        payload: dict,
        timestamp: str,
    ) -> None:
        target = payload.get("to")
        if not target:
            await self._send_error(sender_ws, "direct message requires payload.to")
            return
        target_ws = self.registry.get(target)
        if target_ws is None:
            await self._send_error(sender_ws, f"unknown target client: {target}")
            return
        await target_ws.send(json.dumps(make_message("direct", payload, timestamp)))

    async def _send_error(self, websocket, message: str) -> None:
        await websocket.send(
            json.dumps(
                make_message("system", {"message": "error", "error": message})
            )
        )

    async def broadcast(
        self,
        msg_type: str = "broadcast",
        payload: dict | None = None,
        timestamp: str | None = None,
    ) -> None:
        """Send a message to every connected client."""
        msg = json.dumps(make_message(msg_type, payload or {}, timestamp))
        dead: list[str] = []
        for client_id, ws in self.registry.all():
            try:
                await ws.send(msg)
            except ConnectionClosed:
                dead.append(client_id)
        for client_id in dead:
            self.registry.remove(client_id)

    async def direct(self, target_id: str, payload: dict, timestamp: str | None = None) -> bool:
        """Send a message to a single client. Returns True if delivered."""
        target_ws = self.registry.get(target_id)
        if target_ws is None:
            return False
        await target_ws.send(
            json.dumps(make_message("direct", payload, timestamp))
        )
        return True

    async def process_request(
        self,
        connection,
        request: Request,
    ) -> Response | None:
        """Serve ``GET /health`` over HTTP; upgrade everything else to WS."""
        if request.path == HEALTH_PATH:
            body = json.dumps(
                {"status": "ok", "connected_clients": self.registry.count()}
            ).encode("utf-8")
            headers = Headers(
                {
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body)),
                }
            )
            return Response(200, "OK", headers, body)
        if request.path in WEBSOCKET_PATHS:
            return None
        return Response(404, "Not Found", Headers({"Content-Length": "0"}), b"")

    async def run(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        """Serve until cancelled."""
        async with websockets.serve(
            self.handler,
            host,
            port,
            process_request=self.process_request,
        ):
            await asyncio.Future()


async def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))
    server = NotificationServer()
    await server.run(host, port)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
