"""WebSocket notification server with an HTTP health endpoint."""

import asyncio
import json
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any
from urllib.parse import unquote

from websockets.asyncio.server import ServerConnection, serve


SUPPORTED_MESSAGE_TYPES = frozenset({"broadcast", "direct", "system", "subscribe", "unsubscribe"})


class NotificationServer:
    """Manages connected WebSocket clients and notification delivery."""

    def __init__(self) -> None:
        self.clients: dict[str, ServerConnection] = {}
        self.channels: dict[str, set[str]] = {}
        self._clients_lock = asyncio.Lock()

    @property
    def connected_client_count(self) -> int:
        return len(self.clients)

    async def register(self, websocket: ServerConnection) -> str:
        client_id = str(websocket.id)
        async with self._clients_lock:
            self.clients[client_id] = websocket
        return client_id

    async def unregister(self, websocket: ServerConnection) -> None:
        async with self._clients_lock:
            client_id = str(websocket.id)
            self.clients.pop(client_id, None)
            for channel in tuple(self.channels):
                self.channels[channel].discard(client_id)
                if not self.channels[channel]:
                    del self.channels[channel]

    async def _client_snapshot(self) -> list[ServerConnection]:
        async with self._clients_lock:
            return list(self.clients.values())

    async def _channel_client_snapshot(self, channel: str) -> list[ServerConnection]:
        async with self._clients_lock:
            return [
                self.clients[client_id]
                for client_id in self.channels.get(channel, set())
                if client_id in self.clients
            ]

    @staticmethod
    def _validate_message(message: Any) -> dict[str, Any]:
        if not isinstance(message, dict):
            raise ValueError("message must be a JSON object")
        if message.get("type") not in SUPPORTED_MESSAGE_TYPES:
            raise ValueError("unsupported message type")
        if not isinstance(message.get("payload"), dict):
            raise ValueError("payload must be a JSON object")
        timestamp = message.get("timestamp")
        if not isinstance(timestamp, str) or not timestamp:
            raise ValueError("timestamp must be a non-empty string")
        channel = message.get("channel")
        if channel is not None and (not isinstance(channel, str) or not channel):
            raise ValueError("channel must be a non-empty string")
        if message["type"] in {"subscribe", "unsubscribe"}:
            subscription_channel = message["payload"].get("channel", channel)
            if not isinstance(subscription_channel, str) or not subscription_channel:
                raise ValueError("subscription channel must be a non-empty string")
        return message

    async def broadcast(self, message: dict[str, Any]) -> None:
        payload = json.dumps(message)
        channel = message.get("channel")
        clients = (
            await self._channel_client_snapshot(channel)
            if channel is not None
            else await self._client_snapshot()
        )
        results = await asyncio.gather(
            *(client.send(payload) for client in clients), return_exceptions=True
        )
        for client, result in zip(clients, results):
            if isinstance(result, Exception):
                await self.unregister(client)

    async def update_subscription(self, client_id: str, message: dict[str, Any]) -> None:
        channel = message["payload"].get("channel", message.get("channel"))
        async with self._clients_lock:
            if message["type"] == "subscribe":
                self.channels.setdefault(channel, set()).add(client_id)
            else:
                subscribers = self.channels.get(channel)
                if subscribers is not None:
                    subscribers.discard(client_id)
                    if not subscribers:
                        del self.channels[channel]

    async def handle_connection(self, websocket: ServerConnection) -> None:
        client_id = await self.register(websocket)
        await websocket.send(json.dumps(system_message({"client_id": client_id, "event": "connected"})))
        try:
            async for raw_message in websocket:
                try:
                    message = self._validate_message(json.loads(raw_message))
                except (json.JSONDecodeError, ValueError) as error:
                    await websocket.send(json.dumps(system_message({"error": str(error)})))
                    continue

                if message["type"] in {"subscribe", "unsubscribe"}:
                    await self.update_subscription(client_id, message)
                elif message["type"] == "broadcast":
                    await self.broadcast(message)
                elif message["type"] == "direct":
                    recipient_id = message["payload"].get("client_id")
                    async with self._clients_lock:
                        recipient = self.clients.get(str(recipient_id))
                    if recipient is not None:
                        await recipient.send(json.dumps(message))
        finally:
            await self.unregister(websocket)

    async def health_response(self, connection: ServerConnection, request: Any) -> Any:
        if request.path == "/health":
            body = json.dumps({"connected_clients": self.connected_client_count})
            return connection.respond(HTTPStatus.OK, body)
        if request.path == "/channels":
            async with self._clients_lock:
                channels = [
                    {"name": name, "subscriber_count": len(subscribers)}
                    for name, subscribers in sorted(self.channels.items())
                ]
            return connection.respond(HTTPStatus.OK, json.dumps({"channels": channels}))
        prefix = "/channels/"
        suffix = "/subscribers"
        if request.path.startswith(prefix) and request.path.endswith(suffix):
            name = unquote(request.path[len(prefix) : -len(suffix)])
            if name:
                async with self._clients_lock:
                    subscribers = sorted(self.channels.get(name, set()))
                return connection.respond(
                    HTTPStatus.OK,
                    json.dumps({"channel": name, "subscribers": subscribers}),
                )
        return None


def system_message(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "system",
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    notification_server = NotificationServer()
    async with serve(
        notification_server.handle_connection,
        host,
        port,
        process_request=notification_server.health_response,
    ) as server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(run_server())
