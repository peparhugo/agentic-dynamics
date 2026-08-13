"""Async WebSocket notification server with a small HTTP health endpoint."""

import asyncio
from datetime import datetime, timezone
import json
import threading
from typing import Any
from uuid import uuid4

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response


SUPPORTED_MESSAGE_TYPES = frozenset({"broadcast", "direct", "system"})


class ClientRegistry:
    """A thread-safe mapping of assigned client IDs to WebSocket connections."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = threading.RLock()

    def add(self, connection: ServerConnection) -> str:
        client_id = str(uuid4())
        with self._lock:
            self._clients[client_id] = connection
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str) -> ServerConnection | None:
        with self._lock:
            return self._clients.get(client_id)

    def connections(self) -> list[ServerConnection]:
        with self._lock:
            return list(self._clients.values())

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)


class NotificationServer:
    """Routes JSON notifications between connected WebSocket clients."""

    def __init__(self) -> None:
        self.clients = ClientRegistry()

    @staticmethod
    def message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": message_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def handler(self, connection: ServerConnection) -> None:
        client_id = self.clients.add(connection)
        try:
            await connection.send(json.dumps(self.message("system", {"client_id": client_id})))
            async for raw_message in connection:
                await self.handle_message(client_id, raw_message)
        finally:
            self.clients.remove(client_id)

    async def handle_message(self, sender_id: str, raw_message: str | bytes) -> None:
        if isinstance(raw_message, bytes):
            await self._send_error(sender_id, "messages must be JSON text")
            return
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            await self._send_error(sender_id, "invalid JSON")
            return

        if not isinstance(message, dict):
            await self._send_error(sender_id, "message must be an object")
            return
        message_type = message.get("type")
        payload = message.get("payload")
        if message_type not in SUPPORTED_MESSAGE_TYPES:
            await self._send_error(sender_id, "unsupported message type")
            return
        if not isinstance(payload, dict):
            await self._send_error(sender_id, "payload must be an object")
            return

        notification = json.dumps(self.message(message_type, payload))
        if message_type == "direct":
            target_id = payload.get("client_id")
            if not isinstance(target_id, str):
                await self._send_error(sender_id, "direct messages require payload.client_id")
                return
            target = self.clients.get(target_id)
            if target is None:
                await self._send_error(sender_id, "target client not found")
                return
            await self._send(target, notification)
            return

        await self.broadcast_raw(notification)

    async def broadcast_raw(self, notification: str) -> None:
        """Send a serialized notification to a stable registry snapshot."""
        await asyncio.gather(
            *(self._send(connection, notification) for connection in self.clients.connections()),
            return_exceptions=True,
        )

    async def _send_error(self, client_id: str, error: str) -> None:
        connection = self.clients.get(client_id)
        if connection is not None:
            await self._send(connection, json.dumps(self.message("system", {"error": error})))

    @staticmethod
    async def _send(connection: ServerConnection, notification: str) -> None:
        try:
            await connection.send(notification)
        except Exception:
            # The connection handler removes closed clients; a failed send must
            # not prevent delivery to the remaining clients.
            pass

    async def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        if request.path == "/health" and request.headers.get("Upgrade") is None:
            body = json.dumps({"connected_clients": len(self.clients)}).encode()
            return Response(200, "OK", Headers({"Content-Type": "application/json"}), body)
        if request.headers.get("Upgrade") is None:
            return Response(404, "Not Found", Headers(), b"Not Found")
        return None

    async def start(self, host: str = "127.0.0.1", port: int = 8765) -> Server:
        return await serve(self.handler, host, port, process_request=self.process_request)


async def main() -> None:
    notification_server = NotificationServer()
    async with await notification_server.start():
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
