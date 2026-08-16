"""Async WebSocket notification server with an HTTP health check."""

import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response


SUPPORTED_TYPES = {"broadcast", "direct", "system"}


class NotificationServer:
    """Manage connected clients and route validated notification messages."""

    def __init__(self) -> None:
        self.clients: dict[str, ServerConnection] = {}
        # An RLock keeps registry access safe for embedding code using threads.
        self._clients_lock = threading.RLock()

    @property
    def client_count(self) -> int:
        with self._clients_lock:
            return len(self.clients)

    async def handler(self, websocket: ServerConnection) -> None:
        client_id = uuid.uuid4().hex
        with self._clients_lock:
            self.clients[client_id] = websocket

        await self._send(websocket, self._message("system", {"event": "connected", "client_id": client_id}))
        try:
            async for raw_message in websocket:
                await self._handle_message(client_id, raw_message)
        except ConnectionClosed:
            pass
        finally:
            with self._clients_lock:
                self.clients.pop(client_id, None)

    async def _handle_message(self, sender_id: str, raw_message: str | bytes) -> None:
        if isinstance(raw_message, bytes):
            await self._send_error(sender_id, "messages must be JSON text")
            return
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            await self._send_error(sender_id, "invalid JSON")
            return

        if not self._valid_message(message):
            await self._send_error(sender_id, "message must contain a supported type and a dict payload")
            return

        normalized = self._message(message["type"], message["payload"])
        if normalized["type"] == "direct":
            recipient_id = normalized["payload"].get("client_id")
            if not isinstance(recipient_id, str):
                await self._send_error(sender_id, "direct messages require payload.client_id")
                return
            with self._clients_lock:
                recipient = self.clients.get(recipient_id)
            if recipient is None:
                await self._send_error(sender_id, "target client is not connected")
                return
            await self._send(recipient, normalized)
            return

        await self.broadcast(normalized)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a message to every currently connected client."""
        with self._clients_lock:
            recipients = list(self.clients.values())
        await asyncio.gather(*(self._send(client, message) for client in recipients))

    async def _send_error(self, client_id: str, detail: str) -> None:
        with self._clients_lock:
            client = self.clients.get(client_id)
        if client is not None:
            await self._send(client, self._message("system", {"event": "error", "detail": detail}))

    @staticmethod
    async def _send(client: ServerConnection, message: dict[str, Any]) -> None:
        try:
            await client.send(json.dumps(message))
        except ConnectionClosed:
            pass

    @staticmethod
    def _valid_message(message: Any) -> bool:
        return (
            isinstance(message, dict)
            and message.get("type") in SUPPORTED_TYPES
            and isinstance(message.get("payload"), dict)
        )

    @staticmethod
    def _message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": message_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def process_request(self, connection: ServerConnection, request: Request) -> Response | None:
        if request.path != "/health":
            return None
        body = json.dumps({"connected_clients": self.client_count}).encode()
        return Response(
            HTTPStatus.OK,
            "OK",
            Headers({"Content-Type": "application/json", "Content-Length": str(len(body))}),
            body,
        )

    def listen(self, host: str = "127.0.0.1", port: int = 8765):
        """Return a websockets server context manager for the configured address."""
        return serve(self.handler, host, port, process_request=self.process_request)


async def main() -> None:
    server = NotificationServer()
    async with server.listen("0.0.0.0", 8765):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
