"""Async WebSocket notification server with a small HTTP health endpoint."""

import asyncio
import json
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any
from urllib.parse import urlsplit

from websockets.asyncio.server import ServerConnection, Server as WebSocketServer, serve

Message = dict[str, Any]
SUPPORTED_MESSAGE_TYPES = frozenset(
    {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
)


class NotificationServer:
    """Maintains WebSocket clients and delivers validated notification messages."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._channels: dict[str, set[str]] = {}
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
                for channel in tuple(self._channels):
                    self._channels[channel].discard(client_id)
                    if not self._channels[channel]:
                        del self._channels[channel]

    async def broadcast(self, message: Message) -> None:
        """Send a message to every currently connected client."""
        async with self._lock:
            clients = tuple(self._clients.values())
        await self._send_to_clients(clients, message)

    async def _send_to_clients(
        self, clients: tuple[ServerConnection, ...], message: Message
    ) -> None:
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

        message_type = message["type"]
        if message_type in {"subscribe", "unsubscribe"}:
            channel = message.get("channel")
            if channel is None:
                await self._send_error(sender_id, f"{message_type} messages require channel")
                return
            async with self._lock:
                if message_type == "subscribe":
                    self._channels.setdefault(channel, set()).add(sender_id)
                else:
                    subscribers = self._channels.get(channel)
                    if subscribers is not None:
                        subscribers.discard(sender_id)
                        if not subscribers:
                            del self._channels[channel]
            return

        if "channel" in message:
            async with self._lock:
                clients = tuple(
                    self._clients[client_id]
                    for client_id in self._channels.get(message["channel"], set())
                    if client_id in self._clients
                )
            await self._send_to_clients(clients, message)
            return

        if message_type == "direct":
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
        channel = value.get("channel")
        if channel is not None and (not isinstance(channel, str) or not channel):
            raise ValueError("channel must be a non-empty string")
        message = {"type": message_type, "payload": payload, "timestamp": timestamp}
        if channel is not None:
            message["channel"] = channel
        return message

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
        path = urlsplit(request.path).path
        if path == "/health":
            body = json.dumps({"connected_clients": self.client_count})
            return connection.respond(HTTPStatus.OK, body)
        if path == "/channels":
            async with self._lock:
                channels = {
                    name: len(subscribers) for name, subscribers in self._channels.items()
                }
            return connection.respond(HTTPStatus.OK, json.dumps({"channels": channels}))
        if path.startswith("/channels/") and path.endswith("/subscribers"):
            name = path[len("/channels/") : -len("/subscribers")].strip("/")
            if not name:
                return connection.respond(HTTPStatus.NOT_FOUND, "Not found")
            async with self._lock:
                subscribers = sorted(self._channels.get(name, set()))
            return connection.respond(HTTPStatus.OK, json.dumps({"subscribers": subscribers}))
        if path != "/health":
            return None


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
