"""Async WebSocket notification server.

The WebSocket and health HTTP endpoint share one TCP port.  The server has no
framework dependency: ``websockets`` handles both the upgrade and the small
HTTP response needed by ``/health``.
"""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response


SUPPORTED_TYPES = {"broadcast", "direct", "system"}


def timestamp() -> str:
    """Return an unambiguous UTC timestamp for a message."""
    return datetime.now(timezone.utc).isoformat()


class ClientRegistry:
    """Thread-safe mapping of generated client IDs to WebSocket connections."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = threading.RLock()

    def add(self, connection: ServerConnection) -> str:
        client_id = uuid.uuid4().hex
        with self._lock:
            self._clients[client_id] = connection
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str) -> ServerConnection | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> dict[str, ServerConnection]:
        with self._lock:
            return dict(self._clients)

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._clients)


def make_message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    if message_type not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported message type: {message_type}")
    return {"type": message_type, "payload": payload, "timestamp": timestamp()}


class NotificationServer:
    """WebSocket notification server with broadcast and direct delivery."""

    def __init__(self, host: str = "localhost", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.registry = ClientRegistry()
        self._server: Any = None

    async def start(self) -> None:
        self._server = await serve(
            self._handle_connection,
            self.host,
            self.port,
            process_request=self._process_request,
        )
        if self._server.sockets:
            self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        if request.path != "/health":
            return None
        body = json.dumps({"status": "ok", "clients": self.registry.count}).encode()
        return Response(
            200,
            "OK",
            Headers(
                {
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body)),
                }
            ),
            body,
        )

    async def _handle_connection(self, connection: ServerConnection) -> None:
        client_id = self.registry.add(connection)
        try:
            await connection.send(
                json.dumps(make_message("system", {"event": "connected", "client_id": client_id}))
            )
            async for raw_message in connection:
                await self._handle_message(client_id, raw_message)
        finally:
            self.registry.remove(client_id)

    async def _handle_message(self, sender_id: str, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
            if not isinstance(message, dict):
                raise ValueError
            message_type = message.get("type")
            payload = message.get("payload")
            if message_type not in SUPPORTED_TYPES or not isinstance(payload, dict):
                raise ValueError
        except (json.JSONDecodeError, TypeError, ValueError):
            sender = self.registry.get(sender_id)
            if sender is not None:
                await sender.send(json.dumps(make_message("system", {"error": "invalid message"})))
            return

        outgoing = make_message(message_type, payload)
        if message_type == "broadcast":
            await self.broadcast(outgoing)
        elif message_type == "direct":
            target_id = payload.get("client_id") or payload.get("recipient")
            target = self.registry.get(target_id) if isinstance(target_id, str) else None
            if target is not None:
                await target.send(json.dumps(outgoing))
        else:
            # System messages are server-generated; clients may send them only
            # to themselves, which keeps the message contract predictable.
            sender = self.registry.get(sender_id)
            if sender is not None:
                await sender.send(json.dumps(outgoing))

    async def broadcast(self, message: dict[str, Any]) -> None:
        encoded = json.dumps(message)
        connections = self.registry.snapshot().values()
        if connections:
            await asyncio.gather(*(connection.send(encoded) for connection in connections), return_exceptions=True)


async def run_server(host: str = "localhost", port: int = 8765) -> None:
    server = NotificationServer(host, port)
    await server.start()
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(run_server())
