"""Async WebSocket notification server with a small HTTP health endpoint."""

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Response

MESSAGE_TYPES = {"broadcast", "direct", "system"}


class NotificationServer:
    """Manages connected clients and routes validated notification messages."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = asyncio.Lock()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def handler(self, websocket: ServerConnection) -> None:
        client_id = uuid.uuid4().hex
        async with self._lock:
            self._clients[client_id] = websocket

        await self._send(
            websocket,
            self._message("system", {"event": "connected", "client_id": client_id}),
        )
        try:
            async for raw_message in websocket:
                await self._handle_message(client_id, raw_message)
        finally:
            async with self._lock:
                self._clients.pop(client_id, None)

    async def _handle_message(self, sender_id: str, raw_message: str | bytes) -> None:
        if isinstance(raw_message, bytes):
            await self._send_error(sender_id, "messages must be JSON text")
            return

        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            await self._send_error(sender_id, "invalid JSON")
            return

        if not self._is_valid_message(message):
            await self._send_error(sender_id, "invalid message format")
            return

        message["timestamp"] = self._timestamp()
        if message["type"] == "broadcast":
            await self.broadcast(message)
        elif message["type"] == "direct":
            recipient_id = message["payload"].get("client_id")
            if not isinstance(recipient_id, str):
                await self._send_error(sender_id, "direct messages require payload.client_id")
                return
            await self.send_to(recipient_id, message)
        else:
            await self.broadcast(message)

    @staticmethod
    def _is_valid_message(message: object) -> bool:
        return (
            isinstance(message, dict)
            and message.get("type") in MESSAGE_TYPES
            and isinstance(message.get("payload"), dict)
            and isinstance(message.get("timestamp"), str)
        )

    async def broadcast(self, message: dict[str, object]) -> None:
        async with self._lock:
            recipients = list(self._clients.items())
        await asyncio.gather(
            *(self._send(client, message, client_id) for client_id, client in recipients),
            return_exceptions=True,
        )

    async def send_to(self, client_id: str, message: dict[str, object]) -> bool:
        async with self._lock:
            client = self._clients.get(client_id)
        if client is None:
            return False
        await self._send(client, message, client_id)
        return True

    async def _send_error(self, client_id: str, detail: str) -> None:
        await self.send_to(client_id, self._message("system", {"event": "error", "detail": detail}))

    async def _send(
        self, websocket: ServerConnection, message: dict[str, object], client_id: str | None = None
    ) -> None:
        try:
            await websocket.send(json.dumps(message))
        except Exception:
            if client_id is not None:
                async with self._lock:
                    self._clients.pop(client_id, None)

    @staticmethod
    def _message(message_type: str, payload: dict[str, object]) -> dict[str, object]:
        return {"type": message_type, "payload": payload, "timestamp": NotificationServer._timestamp()}

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()


def create_process_request(server: NotificationServer) -> Callable[..., Awaitable[Response | None]]:
    """Create the HTTP request handler bound to a notification server instance."""

    async def process_request(connection: ServerConnection, request: object) -> Response | None:
        if getattr(request, "path", None) != "/health":
            return None
        body = json.dumps({"connected_clients": server.client_count}).encode()
        return Response(200, "OK", Headers({"Content-Type": "application/json"}), body)

    return process_request


async def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = NotificationServer()
    async with serve(server.handler, host, port, process_request=create_process_request(server)):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(run_server())
