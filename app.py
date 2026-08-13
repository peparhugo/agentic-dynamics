"""WebSocket notification server with a small HTTP health endpoint."""

import asyncio
import json
import threading
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any

from websockets.asyncio.server import ServerConnection, serve


Message = dict[str, Any]


class NotificationServer:
    """Manages connected WebSocket clients and notification delivery."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._channels: dict[str, set[str]] = {}
        self._clients_lock = threading.Lock()

    @property
    def connected_client_count(self) -> int:
        with self._clients_lock:
            return len(self._clients)

    @staticmethod
    def _message(message_type: str, payload: dict[str, Any], channel: str | None = None) -> Message:
        message: Message = {
            "type": message_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if channel is not None:
            message["channel"] = channel
        return message

    def _add_client(self, client_id: str, connection: ServerConnection) -> None:
        with self._clients_lock:
            self._clients[client_id] = connection

    def _remove_client(self, client_id: str) -> None:
        with self._clients_lock:
            self._clients.pop(client_id, None)
            for channel, subscribers in list(self._channels.items()):
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[channel]

    def _client_snapshot(self) -> list[ServerConnection]:
        with self._clients_lock:
            return list(self._clients.values())

    def _channel_snapshot(self, channel: str) -> list[ServerConnection]:
        with self._clients_lock:
            return [
                self._clients[client_id]
                for client_id in self._channels.get(channel, set())
                if client_id in self._clients
            ]

    def _get_client(self, client_id: str) -> ServerConnection | None:
        with self._clients_lock:
            return self._clients.get(client_id)

    def _subscribe(self, client_id: str, channel: str) -> None:
        with self._clients_lock:
            self._channels.setdefault(channel, set()).add(client_id)

    def _unsubscribe(self, client_id: str, channel: str) -> None:
        with self._clients_lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    def _channel_details(self) -> dict[str, int]:
        with self._clients_lock:
            return {
                channel: len(subscribers)
                for channel, subscribers in sorted(self._channels.items())
            }

    def _channel_subscribers(self, channel: str) -> list[str]:
        with self._clients_lock:
            return sorted(self._channels.get(channel, set()))

    async def broadcast(self, payload: dict[str, Any], channel: str | None = None) -> None:
        """Send a broadcast message to every client connected at send time."""
        encoded = json.dumps(self._message("broadcast", payload, channel))
        clients = self._channel_snapshot(channel) if channel is not None else self._client_snapshot()
        if clients:
            await asyncio.gather(*(client.send(encoded) for client in clients), return_exceptions=True)

    async def send_direct(self, client_id: str, payload: dict[str, Any]) -> bool:
        """Send a direct message, returning whether the recipient was connected."""
        client = self._get_client(client_id)
        if client is None:
            return False
        await client.send(json.dumps(self._message("direct", payload)))
        return True

    async def handler(self, connection: ServerConnection) -> None:
        client_id = uuid.uuid4().hex
        self._add_client(client_id, connection)
        await connection.send(json.dumps(self._message("system", {"client_id": client_id})))
        try:
            async for raw_message in connection:
                await self._handle_message(client_id, raw_message)
        finally:
            self._remove_client(client_id)

    async def _handle_message(self, sender_id: str, raw_message: str | bytes) -> None:
        try:
            message = json.loads(raw_message)
            message_type = message["type"]
            payload = message.get("payload", {})
            if not isinstance(message_type, str):
                raise ValueError("type must be a string")
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            sender = self._get_client(sender_id)
            if sender is not None:
                await sender.send(json.dumps(self._message("system", {"error": "invalid message"})))
            return

        if message_type == "broadcast":
            channel = message.get("channel")
            if channel is not None and not isinstance(channel, str):
                sender = self._get_client(sender_id)
                if sender is not None:
                    await sender.send(json.dumps(self._message("system", {"error": "channel must be a string"})))
                return
            await self.broadcast(payload, channel)
        elif message_type in {"subscribe", "unsubscribe"}:
            channel = message.get("channel")
            if not isinstance(channel, str):
                sender = self._get_client(sender_id)
                if sender is not None:
                    await sender.send(json.dumps(self._message("system", {"error": "channel required"})))
                return
            if message_type == "subscribe":
                self._subscribe(sender_id, channel)
            else:
                self._unsubscribe(sender_id, channel)
        elif message_type == "direct":
            recipient_id = payload.get("client_id")
            if isinstance(recipient_id, str):
                await self.send_direct(recipient_id, payload)
            else:
                sender = self._get_client(sender_id)
                if sender is not None:
                    await sender.send(json.dumps(self._message("system", {"error": "client_id required"})))
        elif message_type == "system":
            sender = self._get_client(sender_id)
            if sender is not None:
                await sender.send(json.dumps(self._message("system", payload)))
        else:
            sender = self._get_client(sender_id)
            if sender is not None:
                await sender.send(json.dumps(self._message("system", {"error": "unsupported message type"})))

    async def process_request(self, connection: ServerConnection, request: Any) -> Any:
        if request.path == "/health":
            body = json.dumps({"connected_clients": self.connected_client_count})
            return connection.respond(HTTPStatus.OK, body)
        if request.path == "/channels":
            return connection.respond(HTTPStatus.OK, json.dumps(self._channel_details()))
        if request.path.startswith("/channels/") and request.path.endswith("/subscribers"):
            channel = request.path[len("/channels/"):-len("/subscribers")]
            if channel and "/" not in channel:
                return connection.respond(
                    HTTPStatus.OK,
                    json.dumps({"subscribers": self._channel_subscribers(channel)}),
                )
        return None


async def start_server(host: str = "127.0.0.1", port: int = 8765) -> Any:
    """Create an unstarted-by-context-manager websockets server instance."""
    notification_server = NotificationServer()
    return await serve(
        notification_server.handler,
        host,
        port,
        process_request=notification_server.process_request,
    )


async def main() -> None:
    server = await start_server()
    print("Notification server listening on ws://127.0.0.1:8765")
    await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
