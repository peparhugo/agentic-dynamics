"""Async WebSocket notification server with a small HTTP health endpoint."""

import asyncio
from datetime import datetime, timezone
import json
import threading
from typing import Any
from uuid import uuid4

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Response


MESSAGE_TYPES = frozenset({"broadcast", "direct", "system"})


class NotificationServer:
    """Maintains WebSocket clients and delivers structured notifications."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        # This also makes count and snapshot reads safe for monitoring threads.
        self._clients_lock = threading.RLock()
        self._server: Server | None = None

    @property
    def client_count(self) -> int:
        with self._clients_lock:
            return len(self._clients)

    @property
    def port(self) -> int:
        if self._server is None or not self._server.sockets:
            raise RuntimeError("server is not running")
        return self._server.sockets[0].getsockname()[1]

    async def start(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        if self._server is not None:
            raise RuntimeError("server is already running")
        self._server = await serve(self._handle_client, host, port, process_request=self._handle_http)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        with self._clients_lock:
            self._clients.clear()

    async def broadcast(self, payload: dict[str, Any]) -> None:
        """Send a broadcast message to every currently connected client."""
        await self._send_to_connections(self._connections(), "broadcast", payload)

    async def direct(self, client_id: str, payload: dict[str, Any]) -> bool:
        """Send a direct message to one client, returning whether it existed."""
        with self._clients_lock:
            connection = self._clients.get(client_id)
        if connection is None:
            return False
        await self._send_to_connections([connection], "direct", payload)
        return True

    async def system(self, payload: dict[str, Any]) -> None:
        await self._send_to_connections(self._connections(), "system", payload)

    async def _handle_client(self, connection: ServerConnection) -> None:
        client_id = str(uuid4())
        with self._clients_lock:
            self._clients[client_id] = connection

        try:
            await self._send_to_connections([connection], "system", {"event": "connected", "client_id": client_id})
            async for raw_message in connection:
                await self._handle_message(connection, client_id, raw_message)
        finally:
            with self._clients_lock:
                self._clients.pop(client_id, None)

    async def _handle_message(
        self, connection: ServerConnection, sender_id: str, raw_message: str | bytes
    ) -> None:
        if isinstance(raw_message, bytes):
            await self._send_to_connections([connection], "system", {"event": "error", "message": "messages must be JSON text"})
            return

        try:
            message = json.loads(raw_message)
            message_type = message["type"]
            payload = message["payload"]
            if message_type not in MESSAGE_TYPES or not isinstance(payload, dict):
                raise ValueError
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            await self._send_to_connections([connection], "system", {"event": "error", "message": "invalid message format"})
            return

        if message_type == "broadcast":
            await self.broadcast({"sender_id": sender_id, **payload})
        elif message_type == "direct":
            recipient_id = payload.get("client_id")
            if not isinstance(recipient_id, str) or not await self.direct(recipient_id, {"sender_id": sender_id, **payload}):
                await self._send_to_connections([connection], "system", {"event": "error", "message": "unknown client_id"})
        else:
            await self.system({"sender_id": sender_id, **payload})

    async def _handle_http(self, _connection: ServerConnection, request: Any) -> Response | None:
        if request.path != "/health":
            return None
        body = json.dumps({"connected_clients": self.client_count}).encode("utf-8")
        return Response(200, "OK", Headers({"Content-Type": "application/json", "Content-Length": str(len(body))}), body)

    def _connections(self) -> list[ServerConnection]:
        with self._clients_lock:
            return list(self._clients.values())

    async def _send_to_connections(
        self, connections: list[ServerConnection], message_type: str, payload: dict[str, Any]
    ) -> None:
        message = json.dumps({"type": message_type, "payload": payload, "timestamp": datetime.now(timezone.utc).isoformat()})
        results = await asyncio.gather(*(connection.send(message) for connection in connections), return_exceptions=True)
        if any(isinstance(result, Exception) for result in results):
            # A failed send is harmless here; the connection handler removes it on close.
            return


async def main() -> None:
    server = NotificationServer()
    await server.start(host="0.0.0.0", port=8765)
    print("Notification server listening on ws://0.0.0.0:8765")
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
