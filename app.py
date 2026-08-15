"""Async WebSocket notification server with an HTTP health endpoint."""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any

from websockets.exceptions import ConnectionClosed
from websockets.legacy.server import WebSocketServerProtocol, serve


MESSAGE_TYPES = frozenset({"broadcast", "direct", "system"})


class NotificationServer:
    """Manage connected clients and route JSON notification messages."""

    def __init__(self) -> None:
        self._clients: dict[str, WebSocketServerProtocol] = {}
        # Asyncio protects one event loop, not callers from other threads.
        self._clients_lock = threading.RLock()

    @property
    def client_count(self) -> int:
        with self._clients_lock:
            return len(self._clients)

    @property
    def client_ids(self) -> tuple[str, ...]:
        with self._clients_lock:
            return tuple(self._clients)

    async def handler(self, websocket: WebSocketServerProtocol, _path: str) -> None:
        client_id = str(uuid.uuid4())
        with self._clients_lock:
            self._clients[client_id] = websocket

        await self.send_to_client(
            client_id,
            self._message("system", {"event": "connected", "client_id": client_id}),
        )
        try:
            async for raw_message in websocket:
                await self._handle_message(client_id, raw_message)
        except ConnectionClosed:
            pass
        finally:
            with self._clients_lock:
                self._clients.pop(client_id, None)

    async def _handle_message(self, sender_id: str, raw_message: str | bytes) -> None:
        if isinstance(raw_message, bytes):
            await self.send_to_client(
                sender_id,
                self._message("system", {"event": "error", "message": "messages must be JSON text"}),
            )
            return

        try:
            incoming = json.loads(raw_message)
            message_type = incoming["type"]
            payload = incoming["payload"]
            if message_type not in MESSAGE_TYPES or not isinstance(payload, Mapping):
                raise (KeyError if message_type not in MESSAGE_TYPES else TypeError)
        except (json.JSONDecodeError, KeyError, TypeError):
            await self.send_to_client(
                sender_id,
                self._message("system", {"event": "error", "message": "invalid message format"}),
            )
            return

        message = self._message(message_type, dict(payload))
        if message_type == "broadcast" or message_type == "system":
            await self.broadcast(message)
        else:
            recipient_id = payload.get("client_id")
            if not isinstance(recipient_id, str) or not await self.send_to_client(recipient_id, message):
                await self.send_to_client(
                    sender_id,
                    self._message("system", {"event": "error", "message": "unknown direct recipient"}),
                )

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a valid notification message to every currently connected client."""
        encoded_message = json.dumps(message)
        with self._clients_lock:
            clients = list(self._clients.items())

        results = await asyncio.gather(
            *(self._send(client_id, websocket, encoded_message) for client_id, websocket in clients),
            return_exceptions=True,
        )
        stale_ids = [client_id for (client_id, _), result in zip(clients, results) if result is False]
        if stale_ids:
            with self._clients_lock:
                for client_id in stale_ids:
                    self._clients.pop(client_id, None)

    async def send_to_client(self, client_id: str, message: dict[str, Any]) -> bool:
        with self._clients_lock:
            websocket = self._clients.get(client_id)
        if websocket is None:
            return False
        return await self._send(client_id, websocket, json.dumps(message))

    async def _send(
        self, client_id: str, websocket: WebSocketServerProtocol, encoded_message: str
    ) -> bool:
        try:
            await websocket.send(encoded_message)
            return True
        except ConnectionClosed:
            with self._clients_lock:
                self._clients.pop(client_id, None)
            return False

    async def health_response(
        self, path: str, _request_headers: Any
    ) -> tuple[Any, list[tuple[str, str]], bytes] | None:
        if path != "/health":
            return None
        body = json.dumps({"connected_clients": self.client_count}).encode("utf-8")
        return (
            HTTPStatus.OK,
            [("Content-Type", "application/json"), ("Content-Length", str(len(body)))],
            body,
        )

    @staticmethod
    def _message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": message_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


async def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the notification service until cancelled."""
    notification_server = NotificationServer()
    async with serve(
        notification_server.handler,
        host,
        port,
        process_request=notification_server.health_response,
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(run_server())
