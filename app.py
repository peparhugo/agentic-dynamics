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
        self._clients_lock = threading.Lock()

    @property
    def connected_client_count(self) -> int:
        with self._clients_lock:
            return len(self._clients)

    @staticmethod
    def _message(message_type: str, payload: dict[str, Any]) -> Message:
        return {
            "type": message_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _add_client(self, client_id: str, connection: ServerConnection) -> None:
        with self._clients_lock:
            self._clients[client_id] = connection

    def _remove_client(self, client_id: str) -> None:
        with self._clients_lock:
            self._clients.pop(client_id, None)

    def _client_snapshot(self) -> list[ServerConnection]:
        with self._clients_lock:
            return list(self._clients.values())

    def _get_client(self, client_id: str) -> ServerConnection | None:
        with self._clients_lock:
            return self._clients.get(client_id)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        """Send a broadcast message to every client connected at send time."""
        encoded = json.dumps(self._message("broadcast", payload))
        clients = self._client_snapshot()
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
            payload = message["payload"]
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            sender = self._get_client(sender_id)
            if sender is not None:
                await sender.send(json.dumps(self._message("system", {"error": "invalid message"})))
            return

        if message_type == "broadcast":
            await self.broadcast(payload)
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
