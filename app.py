"""Async WebSocket notification server with a JSON health endpoint."""

import asyncio
import json
from datetime import datetime, timezone
from threading import RLock
from typing import Any
from urllib.parse import unquote

from websockets.asyncio.server import ServerConnection, serve


MESSAGE_TYPES = {"broadcast", "direct", "subscribe", "system", "unsubscribe"}


class ClientRegistry:
    """Thread-safe registry keyed by each live connection's remote address."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = RLock()

    @staticmethod
    def client_id(connection: ServerConnection) -> str:
        address = connection.remote_address
        if address is None:
            raise ValueError("connection has no remote address")
        return f"{address[0]}:{address[1]}"

    def add(self, connection: ServerConnection) -> str:
        client_id = self.client_id(connection)
        with self._lock:
            self._clients[client_id] = connection
        return client_id

    def remove(self, connection: ServerConnection) -> None:
        client_id = self.client_id(connection)
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in list(self._channels):
                subscribers = self._channels[channel]
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[channel]

    def get(self, client_id: str) -> ServerConnection | None:
        with self._lock:
            return self._clients.get(client_id)

    def connections(self, channel: str | None = None) -> list[ServerConnection]:
        with self._lock:
            if channel is not None:
                return [
                    self._clients[client_id]
                    for client_id in self._channels.get(channel, set())
                    if client_id in self._clients
                ]
            return list(self._clients.values())

    def subscribe(self, connection: ServerConnection, channel: str) -> None:
        client_id = self.client_id(connection)
        with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, connection: ServerConnection, channel: str) -> None:
        client_id = self.client_id(connection)
        with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    def channels(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"name": channel, "subscriber_count": len(subscribers)}
                for channel, subscribers in sorted(self._channels.items())
            ]

    def subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)


class NotificationServer:
    def __init__(self) -> None:
        self.clients = ClientRegistry()

    @staticmethod
    def build_message(
        message_type: str, payload: dict[str, Any], channel: str | None = None
    ) -> str:
        if message_type not in MESSAGE_TYPES:
            raise ValueError(f"unsupported message type: {message_type}")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        message = {
            "type": message_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if channel is not None:
            message["channel"] = channel
        return json.dumps(message)

    async def broadcast(self, message: str, channel: str | None = None) -> None:
        connections = self.clients.connections(channel)
        if connections:
            await asyncio.gather(*(connection.send(message) for connection in connections))

    async def handler(self, connection: ServerConnection) -> None:
        client_id = self.clients.add(connection)
        await connection.send(self.build_message("system", {"client_id": client_id}))
        try:
            async for raw_message in connection:
                try:
                    message = json.loads(raw_message)
                    message_type = message["type"]
                    payload = message["payload"]
                    channel = message.get("channel")
                    if channel is not None and (not isinstance(channel, str) or not channel):
                        raise ValueError("channel must be a non-empty string")
                    if message_type in {"subscribe", "unsubscribe"}:
                        if channel is None:
                            raise ValueError("channel is required")
                        if message_type == "subscribe":
                            self.clients.subscribe(connection, channel)
                        else:
                            self.clients.unsubscribe(connection, channel)
                        continue

                    encoded = self.build_message(message_type, payload, channel)
                    if message_type == "direct":
                        target = payload.get("client_id")
                        recipient = self.clients.get(target) if isinstance(target, str) else None
                        if recipient is not None:
                            await recipient.send(encoded)
                    else:
                        await self.broadcast(encoded, channel)
                except (json.JSONDecodeError, KeyError, ValueError) as error:
                    await connection.send(self.build_message("system", {"error": str(error)}))
        finally:
            self.clients.remove(connection)

    async def process_request(self, connection: ServerConnection, request: Any) -> Any:
        if request.path == "/health":
            response = connection.respond(200, json.dumps({"connected_clients": len(self.clients)}))
            response.headers["Content-Type"] = "application/json"
            return response
        if request.path == "/channels":
            response = connection.respond(200, json.dumps({"channels": self.clients.channels()}))
            response.headers["Content-Type"] = "application/json"
            return response
        if request.path.startswith("/channels/") and request.path.endswith("/subscribers"):
            channel = unquote(request.path[len("/channels/") : -len("/subscribers")].rstrip("/"))
            response = connection.respond(200, json.dumps({"subscribers": self.clients.subscribers(channel)}))
            response.headers["Content-Type"] = "application/json"
            return response
        return None

    def create_server(self, host: str = "127.0.0.1", port: int = 8765) -> Any:
        return serve(self.handler, host, port, process_request=self.process_request)


async def main() -> None:
    notification_server = NotificationServer()
    async with notification_server.create_server():
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
