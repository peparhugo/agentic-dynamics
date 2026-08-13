"""Async WebSocket notification server with a small HTTP health endpoint."""

import asyncio
import json
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any

from websockets.asyncio.server import ServerConnection, Server as WebSocketServer, serve

Message = dict[str, Any]
SUPPORTED_MESSAGE_TYPES = frozenset({"broadcast", "direct", "system"})


class NotificationServer:
    """Maintains WebSocket clients and delivers validated notification messages."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = asyncio.Lock()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def handler(self, websocket: ServerConnection) -> None:
        client_id = str(uuid.uuid4())
        async with self._lock:
            self._clients[client_id] = websocket

        await self._send(websocket, self._message("system", {"client_id": client_id}))
        try:
            async for raw_message in websocket:
                await self._handle_message(client_id, raw_message)
        finally:
            async with self._lock:
                self._clients.pop(client_id, None)

    async def broadcast(self, message: Message) -> None:
        """Send a message to every currently connected client."""
        async with self._lock:
            clients = tuple(self._clients.values())
        await asyncio.gather(
            *(self._send(client, message) for client in clients), return_exceptions=True
        )

    async def _handle_message(self, sender_id: str, raw_message: str | bytes) -> None:
        try:
            incoming = json.loads(raw_message)
            message = self._validate_message(incoming)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            await self._send_error(sender_id, str(error))
            return

        if message["type"] == "direct":
            recipient_id = message["payload"].get("client_id")
            if not isinstance(recipient_id, str):
                await self._send_error(sender_id, "direct messages require payload.client_id")
                return
            async with self._lock:
                recipient = self._clients.get(recipient_id)
            if recipient is None:
                await self._send_error(sender_id, "recipient is not connected")
                return
            await self._send(recipient, message)
            return

        await self.broadcast(message)

    @staticmethod
    def _message(message_type: str, payload: dict[str, Any]) -> Message:
        return {
            "type": message_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _validate_message(value: Any) -> Message:
        if not isinstance(value, Mapping):
            raise ValueError("message must be a JSON object")
        message_type = value.get("type")
        payload = value.get("payload")
        timestamp = value.get("timestamp")
        if message_type not in SUPPORTED_MESSAGE_TYPES:
            raise ValueError("unsupported message type")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        if not isinstance(timestamp, str):
            raise ValueError("timestamp must be a string")
        return {"type": message_type, "payload": payload, "timestamp": timestamp}

    async def _send_error(self, client_id: str, detail: str) -> None:
        async with self._lock:
            client = self._clients.get(client_id)
        if client is not None:
            await self._send(client, self._message("system", {"error": detail}))

    @staticmethod
    async def _send(client: ServerConnection, message: Message) -> None:
        try:
            await client.send(json.dumps(message))
        except Exception:
            # The connection handler performs registry cleanup after disconnects.
            pass

    async def process_request(self, connection: ServerConnection, request: Any) -> Any:
        if request.path != "/health":
            return None
        body = json.dumps({"connected_clients": self.client_count})
        return connection.respond(HTTPStatus.OK, body)


async def start_server(host: str = "127.0.0.1", port: int = 8765) -> WebSocketServer:
    """Start and return the notification server without blocking the event loop."""
    notification_server = NotificationServer()
    return await serve(
        notification_server.handler,
        host,
        port,
        process_request=notification_server.process_request,
    )


async def main() -> None:
    server = await start_server()
    await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
