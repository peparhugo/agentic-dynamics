"""Async WebSocket notification server."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response


MESSAGE_TYPES = {"broadcast", "direct", "system"}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class NotificationServer:
    """Manage WebSocket clients and route notification messages."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.clients: dict[str, ServerConnection] = {}
        self._server: Server | None = None

    @property
    def connected_client_count(self) -> int:
        return len(self.clients)

    async def start(self) -> None:
        """Start accepting WebSocket and health-check HTTP connections."""
        self._server = await serve(
            self._handle_client,
            self.host,
            self.port,
            process_request=self._process_request,
        )

    async def stop(self) -> None:
        """Stop accepting connections and close current clients."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        clients = list(self.clients.values())
        self.clients.clear()
        if clients:
            await asyncio.gather(*(client.close() for client in clients))

    async def _process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        if request.path != "/health":
            return None
        body = json.dumps({"connected_clients": self.connected_client_count}).encode()
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
        client_id = uuid.uuid4().hex
        self.clients[client_id] = websocket
        await self._send(
            websocket,
            {"type": "system", "payload": {"event": "connected", "client_id": client_id}},
        )
        try:
            async for raw_message in websocket:
                await self._handle_message(client_id, raw_message)
        finally:
            self.clients.pop(client_id, None)

    async def _handle_message(self, sender_id: str, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(message, dict):
            return
        message_type = message.get("type")
        payload = message.get("payload")
        if message_type not in MESSAGE_TYPES or not isinstance(payload, dict):
            return

        outgoing: dict[str, Any] = {
            "type": message_type,
            "payload": payload,
            "timestamp": _timestamp(),
        }
        if message_type == "direct":
            target_id = payload.get("client_id") or message.get("client_id")
            if isinstance(target_id, str) and target_id in self.clients:
                await self._send(self.clients[target_id], outgoing)
        elif message_type in {"broadcast", "system"}:
            await self._broadcast(outgoing)

    async def _broadcast(self, message: dict[str, Any]) -> None:
        encoded = json.dumps(message)
        clients = list(self.clients.items())
        results = await asyncio.gather(
            *(client.send(encoded) for _, client in clients), return_exceptions=True
        )
        for (client_id, _), result in zip(clients, results):
            if isinstance(result, Exception):
                self.clients.pop(client_id, None)

    async def _send(self, client: ServerConnection, message: dict[str, Any]) -> None:
        try:
            await client.send(json.dumps(message))
        except Exception:
            # A client can disconnect between registry lookup and sending.
            pass


async def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = NotificationServer(host, port)
    await server.start()
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        pass
