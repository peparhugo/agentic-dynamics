"""Async WebSocket notification server."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from http import HTTPStatus

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Response
from websockets.datastructures import Headers

MESSAGE_TYPES = frozenset({"broadcast", "direct", "system"})


class ClientRegistry:
    """Tracks active connections without exposing mutable internal state."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = asyncio.Lock()

    async def add(self, connection: ServerConnection) -> str:
        client_id = str(uuid.uuid4())
        async with self._lock:
            self._clients[client_id] = connection
        return client_id

    async def remove(self, client_id: str) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)

    async def count(self) -> int:
        async with self._lock:
            return len(self._clients)

    async def get(self, client_id: str) -> ServerConnection | None:
        async with self._lock:
            return self._clients.get(client_id)

    async def connections(self) -> tuple[ServerConnection, ...]:
        async with self._lock:
            return tuple(self._clients.values())


class NotificationServer:
    """Routes client messages and owns the WebSocket client registry."""

    def __init__(self) -> None:
        self.clients = ClientRegistry()

    @staticmethod
    def message(message_type: str, payload: Mapping[str, object]) -> dict[str, object]:
        return {
            "type": message_type,
            "payload": dict(payload),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def validate_message(raw_message: str) -> dict[str, object]:
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError as error:
            raise ValueError("message must be valid JSON") from error

        if not isinstance(message, dict):
            raise ValueError("message must be a JSON object")
        if message.get("type") not in MESSAGE_TYPES:
            raise ValueError("unsupported message type")
        if not isinstance(message.get("payload"), dict):
            raise ValueError("payload must be a JSON object")
        if "timestamp" in message and not isinstance(message["timestamp"], str):
            raise ValueError("timestamp must be a string")
        return message

    async def send(self, connection: ServerConnection, message: dict[str, object]) -> None:
        try:
            await connection.send(json.dumps(message))
        except ConnectionClosed:
            return

    async def broadcast(self, message: dict[str, object]) -> None:
        await asyncio.gather(
            *(self.send(connection, message) for connection in await self.clients.connections())
        )

    async def handle_message(self, client_id: str, raw_message: str) -> None:
        try:
            message = self.validate_message(raw_message)
        except ValueError as error:
            connection = await self.clients.get(client_id)
            if connection is not None:
                await self.send(connection, self.message("system", {"error": str(error)}))
            return

        message["timestamp"] = datetime.now(timezone.utc).isoformat()
        if message["type"] == "direct":
            target_id = message["payload"].get("client_id")
            if not isinstance(target_id, str):
                connection = await self.clients.get(client_id)
                if connection is not None:
                    await self.send(connection, self.message("system", {"error": "direct messages require payload.client_id"}))
                return
            target = await self.clients.get(target_id)
            if target is not None:
                await self.send(target, message)
            return

        await self.broadcast(message)

    async def websocket_handler(self, connection: ServerConnection) -> None:
        client_id = await self.clients.add(connection)
        try:
            await self.send(connection, self.message("system", {"client_id": client_id}))
            async for raw_message in connection:
                await self.handle_message(client_id, raw_message)
        finally:
            await self.clients.remove(client_id)

    async def process_request(self, connection: ServerConnection, request: object) -> Response | None:
        if getattr(request, "path", None) != "/health":
            return None
        body = json.dumps({"connected_clients": await self.clients.count()}).encode()
        return Response(
            HTTPStatus.OK,
            "OK",
            Headers({"Content-Type": "application/json", "Content-Length": str(len(body))}),
            body,
        )

    def create_server(self, host: str = "127.0.0.1", port: int = 8765):
        return serve(self.websocket_handler, host, port, process_request=self.process_request)


async def main() -> None:
    server = NotificationServer()
    async with server.create_server():
        await asyncio.get_running_loop().create_future()


if __name__ == "__main__":
    asyncio.run(main())
