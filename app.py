"""Async WebSocket notification server with a JSON health endpoint."""

import asyncio
import json
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from websockets.asyncio.server import ServerConnection, serve


MESSAGE_TYPES = {"broadcast", "direct", "system"}


class ClientRegistry:
    """Thread-safe registry keyed by each live connection's remote address."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
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

    def get(self, client_id: str) -> ServerConnection | None:
        with self._lock:
            return self._clients.get(client_id)

    def connections(self) -> list[ServerConnection]:
        with self._lock:
            return list(self._clients.values())

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)


class NotificationServer:
    def __init__(self) -> None:
        self.clients = ClientRegistry()

    @staticmethod
    def build_message(message_type: str, payload: dict[str, Any]) -> str:
        if message_type not in MESSAGE_TYPES:
            raise ValueError(f"unsupported message type: {message_type}")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        return json.dumps(
            {
                "type": message_type,
                "payload": payload,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def broadcast(self, message: str) -> None:
        connections = self.clients.connections()
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
                    encoded = self.build_message(message_type, payload)
                    if message_type == "direct":
                        target = payload.get("client_id")
                        recipient = self.clients.get(target) if isinstance(target, str) else None
                        if recipient is not None:
                            await recipient.send(encoded)
                    else:
                        await self.broadcast(encoded)
                except (json.JSONDecodeError, KeyError, ValueError) as error:
                    await connection.send(self.build_message("system", {"error": str(error)}))
        finally:
            self.clients.remove(connection)

    async def process_request(self, connection: ServerConnection, request: Any) -> Any:
        if request.path == "/health":
            response = connection.respond(200, json.dumps({"connected_clients": len(self.clients)}))
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
