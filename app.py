"""Async WebSocket notification server with a small HTTP health endpoint."""

import asyncio
from datetime import datetime, timezone
import json
import threading
from typing import Any
from uuid import uuid4

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response


SUPPORTED_MESSAGE_TYPES = frozenset({"broadcast", "direct", "system"})


class NotificationServer:
    """Manage WebSocket clients and route JSON notifications between them."""

    def __init__(self) -> None:
        self.clients: dict[str, ServerConnection] = {}
        # An asyncio lock only coordinates tasks on one loop. This lock also
        # protects registry inspection or mutation when called from a thread.
        self._clients_lock = threading.RLock()
        self._server: Server | None = None

    @property
    def client_count(self) -> int:
        with self._clients_lock:
            return len(self.clients)

    async def start(self, host: str = "127.0.0.1", port: int = 8765) -> Server:
        if self._server is not None:
            raise RuntimeError("server is already running")
        self._server = await serve(
            self._handle_client,
            host,
            port,
            process_request=self._handle_http_request,
        )
        return self._server

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    async def _handle_http_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        if request.path != "/health":
            return None
        body = json.dumps({"connected_clients": self.client_count}).encode("utf-8")
        return Response(
            200,
            "OK",
            Headers(
                [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(body))),
                ]
            ),
            body,
        )

    async def _handle_client(self, websocket: ServerConnection) -> None:
        client_id = str(uuid4())
        with self._clients_lock:
            self.clients[client_id] = websocket

        await self._send_to(
            websocket,
            self._message("system", {"event": "connected", "client_id": client_id}),
        )
        try:
            async for raw_message in websocket:
                await self._handle_message(websocket, raw_message)
        finally:
            with self._clients_lock:
                self.clients.pop(client_id, None)

    async def _handle_message(
        self, sender: ServerConnection, raw_message: str | bytes) -> None:
        if isinstance(raw_message, bytes):
            await self._send_error(sender, "messages must be text JSON")
            return
        try:
            incoming = json.loads(raw_message)
            message_type = incoming["type"]
            payload = incoming["payload"]
            if message_type not in SUPPORTED_MESSAGE_TYPES or not isinstance(payload, dict):
                raise ValueError
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            await self._send_error(sender, "invalid message format")
            return

        message = self._message(message_type, payload)
        if message_type == "direct":
            client_id = payload.get("client_id")
            if not isinstance(client_id, str):
                await self._send_error(sender, "direct messages require payload.client_id")
                return
            with self._clients_lock:
                recipient = self.clients.get(client_id)
            if recipient is None:
                await self._send_error(sender, "recipient not connected")
                return
            await self._send_to(recipient, message)
            return

        await self.broadcast(payload, message_type)

    async def broadcast(self, payload: dict[str, Any], message_type: str = "broadcast") -> None:
        """Send a supported notification to every currently connected client."""
        if message_type not in SUPPORTED_MESSAGE_TYPES:
            raise ValueError(f"unsupported message type: {message_type}")
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary")
        message = self._message(message_type, payload)
        with self._clients_lock:
            recipients = list(self.clients.values())
        results = await asyncio.gather(
            *(self._send_to(client, message) for client in recipients),
            return_exceptions=True,
        )
        if any(isinstance(result, Exception) for result in results):
            await self._remove_closed_clients()

    async def _remove_closed_clients(self) -> None:
        with self._clients_lock:
            stale_ids = [client_id for client_id, client in self.clients.items() if client.closed]
            for client_id in stale_ids:
                self.clients.pop(client_id, None)

    @staticmethod
    def _message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": message_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    async def _send_to(client: ServerConnection, message: dict[str, Any]) -> None:
        await client.send(json.dumps(message))

    async def _send_error(self, client: ServerConnection, detail: str) -> None:
        await self._send_to(client, self._message("system", {"event": "error", "detail": detail}))


async def main() -> None:
    server = NotificationServer()
    await server.start()
    print("Notification server listening on ws://127.0.0.1:8765")
    await asyncio.get_running_loop().create_future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
