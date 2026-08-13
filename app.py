"""Async WebSocket notification server.

Run with: python app.py
"""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any

from websockets.asyncio.server import ServerConnection, serve


SUPPORTED_TYPES = frozenset({"broadcast", "direct", "system"})


class NotificationServer:
    """Routes JSON notification messages between connected WebSocket clients."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = threading.RLock()

    @property
    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def handler(self, websocket: ServerConnection) -> None:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = websocket

        try:
            await websocket.send(
                json.dumps(
                    {
                        "type": "system",
                        "payload": {"event": "connected", "client_id": client_id},
                        "timestamp": self._timestamp(),
                    }
                )
            )
            async for raw_message in websocket:
                await self.handle_message(client_id, raw_message)
        finally:
            with self._lock:
                self._clients.pop(client_id, None)

    async def handle_message(self, sender_id: str, raw_message: str | bytes) -> None:
        """Validate an incoming message and route it to its recipients."""
        try:
            message = json.loads(raw_message)
            message_type = message["type"]
            payload = message["payload"]
        except (json.JSONDecodeError, KeyError, TypeError):
            await self._send_error(sender_id, "message must contain type and payload")
            return

        if message_type not in SUPPORTED_TYPES or not isinstance(payload, dict):
            await self._send_error(sender_id, "unsupported message type or invalid payload")
            return

        notification = {
            "type": message_type,
            "payload": payload,
            "timestamp": message.get("timestamp") or self._timestamp(),
        }
        if message_type == "direct":
            target_id = payload.get("client_id")
            if not isinstance(target_id, str):
                await self._send_error(sender_id, "direct messages require payload.client_id")
                return
            await self._send_to(target_id, notification)
            return

        await self.broadcast(notification)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Deliver a message to every currently connected client."""
        with self._lock:
            recipients = list(self._clients.items())
        results = await asyncio.gather(
            *(connection.send(json.dumps(message)) for _, connection in recipients),
            return_exceptions=True,
        )
        for (client_id, _), result in zip(recipients, results):
            if isinstance(result, Exception):
                with self._lock:
                    self._clients.pop(client_id, None)

    async def _send_to(self, client_id: str, message: dict[str, Any]) -> None:
        with self._lock:
            connection = self._clients.get(client_id)
        if connection is None:
            return
        try:
            await connection.send(json.dumps(message))
        except Exception:
            with self._lock:
                self._clients.pop(client_id, None)

    async def _send_error(self, client_id: str, error: str) -> None:
        await self._send_to(
            client_id,
            {"type": "system", "payload": {"event": "error", "message": error}, "timestamp": self._timestamp()},
        )

    async def process_request(self, connection: ServerConnection, request: Any) -> Any:
        """Serve the lightweight HTTP health check on the WebSocket port."""
        if request.path == "/health":
            body = json.dumps({"connected_clients": self.client_count})
            return connection.respond(HTTPStatus.OK, body)
        return None


async def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the notification server until cancelled."""
    notification_server = NotificationServer()
    async with serve(
        notification_server.handler,
        host,
        port,
        process_request=notification_server.process_request,
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(run_server())
