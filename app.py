"""Async WebSocket notification server with a small HTTP health endpoint."""

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Response

MESSAGE_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


class NotificationServer:
    """Manages connected clients and routes validated notification messages."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._channels: dict[str, set[str]] = {}
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
                self._remove_client(client_id)

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
        if message["type"] == "subscribe":
            channel = self._channel_from(message)
            if channel is None:
                await self._send_error(sender_id, "subscribe messages require a channel")
                return
            await self.subscribe(sender_id, channel)
        elif message["type"] == "unsubscribe":
            channel = self._channel_from(message)
            if channel is None:
                await self._send_error(sender_id, "unsubscribe messages require a channel")
                return
            await self.unsubscribe(sender_id, channel)
        elif message["type"] == "direct":
            recipient_id = message["payload"].get("client_id")
            if not isinstance(recipient_id, str):
                await self._send_error(sender_id, "direct messages require payload.client_id")
                return
            await self.send_to(recipient_id, message)
        else:
            channel = message.get("channel")
            if channel is None:
                await self.broadcast(message)
            elif isinstance(channel, str) and channel:
                await self.broadcast_to_channel(channel, message)
            else:
                await self._send_error(sender_id, "channel must be a non-empty string")

    @staticmethod
    def _is_valid_message(message: object) -> bool:
        return (
            isinstance(message, dict)
            and message.get("type") in MESSAGE_TYPES
            and isinstance(message.get("payload"), dict)
            and isinstance(message.get("timestamp"), str)
        )

    @staticmethod
    def _channel_from(message: dict[str, object]) -> str | None:
        channel = message.get("channel")
        return channel if isinstance(channel, str) and channel else None

    async def subscribe(self, client_id: str, channel: str) -> bool:
        async with self._lock:
            if client_id not in self._clients:
                return False
            self._channels.setdefault(channel, set()).add(client_id)
        return True

    async def unsubscribe(self, client_id: str, channel: str) -> bool:
        async with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None or client_id not in subscribers:
                return False
            subscribers.remove(client_id)
            if not subscribers:
                self._channels.pop(channel, None)
        return True

    async def channels(self) -> dict[str, int]:
        async with self._lock:
            return {channel: len(subscribers) for channel, subscribers in self._channels.items()}

    async def channel_subscribers(self, channel: str) -> list[str]:
        async with self._lock:
            return sorted(self._channels.get(channel, set()))

    async def broadcast(self, message: dict[str, object]) -> None:
        async with self._lock:
            recipients = list(self._clients.items())
        await self._send_to_recipients(recipients, message)

    async def broadcast_to_channel(self, channel: str, message: dict[str, object]) -> None:
        async with self._lock:
            recipients = [
                (client_id, self._clients[client_id])
                for client_id in self._channels.get(channel, set())
                if client_id in self._clients
            ]
        await self._send_to_recipients(recipients, message)

    async def _send_to_recipients(
        self, recipients: list[tuple[str, ServerConnection]], message: dict[str, object]
    ) -> None:
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
                    self._remove_client(client_id)

    def _remove_client(self, client_id: str) -> None:
        self._clients.pop(client_id, None)
        for channel, subscribers in list(self._channels.items()):
            subscribers.discard(client_id)
            if not subscribers:
                self._channels.pop(channel)

    @staticmethod
    def _message(message_type: str, payload: dict[str, object]) -> dict[str, object]:
        return {"type": message_type, "payload": payload, "timestamp": NotificationServer._timestamp()}

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()


def create_process_request(server: NotificationServer) -> Callable[..., Awaitable[Response | None]]:
    """Create the HTTP request handler bound to a notification server instance."""

    async def process_request(connection: ServerConnection, request: object) -> Response | None:
        path = urlsplit(getattr(request, "path", "")).path
        if path == "/health":
            body = json.dumps({"connected_clients": server.client_count}).encode()
        elif path == "/channels":
            body = json.dumps(await server.channels()).encode()
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            channel = unquote(path[len("/channels/") : -len("/subscribers")]).rstrip("/")
            if not channel:
                return None
            body = json.dumps(await server.channel_subscribers(channel)).encode()
        else:
            return None
        return Response(200, "OK", Headers({"Content-Type": "application/json"}), body)

    return process_request


async def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = NotificationServer()
    async with serve(server.handler, host, port, process_request=create_process_request(server)):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(run_server())
