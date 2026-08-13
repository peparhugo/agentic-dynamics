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


SUPPORTED_TYPES = frozenset({"broadcast", "direct", "system", "subscribe", "unsubscribe"})


class NotificationServer:
    """Routes JSON notification messages between connected WebSocket clients."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._channels: dict[str, set[str]] = {}
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
            self._remove_client(client_id)

    async def handle_message(self, sender_id: str, raw_message: str | bytes) -> None:
        """Validate an incoming message and route it to its recipients."""
        try:
            message = json.loads(raw_message)
            message_type = message["type"]
            payload = message.get("payload", {}) if message_type in {"subscribe", "unsubscribe"} else message["payload"]
        except (json.JSONDecodeError, KeyError, TypeError):
            await self._send_error(sender_id, "message must contain type and payload")
            return

        if message_type not in SUPPORTED_TYPES or not isinstance(payload, dict):
            await self._send_error(sender_id, "unsupported message type or invalid payload")
            return

        channel = message.get("channel")
        if channel is not None and (not isinstance(channel, str) or not channel):
            await self._send_error(sender_id, "channel must be a non-empty string")
            return

        if message_type in {"subscribe", "unsubscribe"}:
            if not channel:
                await self._send_error(sender_id, f"{message_type} messages require channel")
                return
            self._update_subscription(sender_id, channel, message_type == "subscribe")
            return

        notification: dict[str, Any] = {
            "type": message_type,
            "payload": payload,
            "timestamp": message.get("timestamp") or self._timestamp(),
        }
        if channel:
            notification["channel"] = channel
        if message_type == "direct":
            if channel:
                await self._broadcast_to_channel(channel, notification)
                return
            target_id = payload.get("client_id")
            if not isinstance(target_id, str):
                await self._send_error(sender_id, "direct messages require payload.client_id")
                return
            await self._send_to(target_id, notification)
            return

        if channel:
            await self._broadcast_to_channel(channel, notification)
        else:
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
                self._remove_client(client_id)

    async def _broadcast_to_channel(self, channel: str, message: dict[str, Any]) -> None:
        with self._lock:
            recipients = [
                (client_id, self._clients[client_id])
                for client_id in self._channels.get(channel, set())
                if client_id in self._clients
            ]
        results = await asyncio.gather(
            *(connection.send(json.dumps(message)) for _, connection in recipients),
            return_exceptions=True,
        )
        for (client_id, _), result in zip(recipients, results):
            if isinstance(result, Exception):
                self._remove_client(client_id)

    async def _send_to(self, client_id: str, message: dict[str, Any]) -> None:
        with self._lock:
            connection = self._clients.get(client_id)
        if connection is None:
            return
        try:
            await connection.send(json.dumps(message))
        except Exception:
            self._remove_client(client_id)

    def _update_subscription(self, client_id: str, channel: str, subscribe: bool) -> None:
        with self._lock:
            if subscribe:
                self._channels.setdefault(channel, set()).add(client_id)
            else:
                subscribers = self._channels.get(channel)
                if subscribers is not None:
                    subscribers.discard(client_id)
                    if not subscribers:
                        self._channels.pop(channel, None)

    def _remove_client(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            for channel, subscribers in list(self._channels.items()):
                subscribers.discard(client_id)
                if not subscribers:
                    self._channels.pop(channel)

    async def _send_error(self, client_id: str, error: str) -> None:
        await self._send_to(
            client_id,
            {"type": "system", "payload": {"event": "error", "message": error}, "timestamp": self._timestamp()},
        )

    async def process_request(self, connection: ServerConnection, request: Any) -> Any:
        """Serve lightweight HTTP status endpoints on the WebSocket port."""
        if request.path == "/health":
            body = json.dumps({"connected_clients": self.client_count})
            return connection.respond(HTTPStatus.OK, body)
        if request.path == "/channels":
            with self._lock:
                channels = [
                    {"name": name, "subscriber_count": len(subscribers)}
                    for name, subscribers in sorted(self._channels.items())
                ]
            return connection.respond(HTTPStatus.OK, json.dumps({"channels": channels}))
        if request.path.startswith("/channels/") and request.path.endswith("/subscribers"):
            name = request.path[len("/channels/") : -len("/subscribers")].rstrip("/")
            if not name:
                return connection.respond(HTTPStatus.NOT_FOUND, "not found")
            with self._lock:
                subscribers = sorted(self._channels.get(name, set()))
            return connection.respond(
                HTTPStatus.OK, json.dumps({"channel": name, "subscribers": subscribers})
            )
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
