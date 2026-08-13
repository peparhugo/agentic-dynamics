"""Async WebSocket notification server with a small HTTP health endpoint."""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Response


SUPPORTED_MESSAGE_TYPES = frozenset({"broadcast", "direct", "system"})


class NotificationServer:
    """Maintains connected WebSocket clients and routes notification messages."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = asyncio.Lock()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def register(self, websocket: ServerConnection) -> str:
        client_id = str(uuid.uuid4())
        async with self._lock:
            self._clients[client_id] = websocket
        return client_id

    async def unregister(self, client_id: str) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)

    async def broadcast(self, message: dict[str, Any]) -> None:
        serialized = json.dumps(message)
        async with self._lock:
            clients = list(self._clients.items())

        failed_clients: list[str] = []
        for client_id, websocket in clients:
            try:
                await websocket.send(serialized)
            except Exception:
                failed_clients.append(client_id)

        if failed_clients:
            async with self._lock:
                for client_id in failed_clients:
                    self._clients.pop(client_id, None)

    async def send_direct(self, client_id: str, message: dict[str, Any]) -> bool:
        async with self._lock:
            websocket = self._clients.get(client_id)
        if websocket is None:
            return False

        try:
            await websocket.send(json.dumps(message))
        except Exception:
            await self.unregister(client_id)
            return False
        return True

    async def websocket_handler(self, websocket: ServerConnection) -> None:
        client_id = await self.register(websocket)
        await websocket.send(json.dumps(self._message("system", {"client_id": client_id})))
        try:
            async for raw_message in websocket:
                message = self._parse_message(raw_message)
                if message["type"] == "broadcast":
                    await self.broadcast(message)
                elif message["type"] == "direct":
                    target_id = message["payload"].get("client_id")
                    if not isinstance(target_id, str) or not await self.send_direct(target_id, message):
                        await websocket.send(
                            json.dumps(self._message("system", {"error": "client not found"}))
                        )
                else:
                    await self.broadcast(message)
        except ValueError as error:
            await websocket.send(json.dumps(self._message("system", {"error": str(error)})))
        finally:
            await self.unregister(client_id)

    def health_response(self, connection: ServerConnection, request: Any) -> Response | None:
        if request.path != "/health":
            return None
        body = json.dumps({"connected_clients": self.client_count}).encode()
        return Response(
            HTTPStatus.OK,
            "OK",
            headers=Headers({"Content-Type": "application/json"}),
            body=body,
        )

    @staticmethod
    def _message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": message_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _parse_message(raw_message: str | bytes) -> dict[str, Any]:
        if not isinstance(raw_message, str):
            raise ValueError("messages must be JSON text")
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError as error:
            raise ValueError("messages must be valid JSON") from error

        if not isinstance(message, dict):
            raise ValueError("messages must be JSON objects")
        if message.get("type") not in SUPPORTED_MESSAGE_TYPES:
            raise ValueError("unsupported message type")
        if not isinstance(message.get("payload"), dict):
            raise ValueError("payload must be an object")
        if not isinstance(message.get("timestamp"), str):
            raise ValueError("timestamp must be a string")
        return message


async def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the notification service until cancelled."""
    notification_server = NotificationServer()
    async with serve(
        notification_server.websocket_handler,
        host,
        port,
        process_request=notification_server.health_response,
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(run_server())
