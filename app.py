"""Async WebSocket notification server with a small HTTP health endpoint."""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import websockets
from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.http11 import Headers, Request, Response


SUPPORTED_TYPES = {"broadcast", "direct", "system"}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _message(message_type: str, payload: dict[str, Any]) -> str:
    return json.dumps({"type": message_type, "payload": payload, "timestamp": _timestamp()})


class NotificationServer:
    """Manage WebSocket clients and route notification messages."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.clients: dict[str, ServerConnection] = {}
        self._server: Server | None = None

    @property
    def client_count(self) -> int:
        return len(self.clients)

    async def _process_request(
        self, _connection: ServerConnection, request: Request
    ) -> Response | None:
        if request.path != "/health":
            return None
        body = json.dumps({"connected_clients": self.client_count}).encode()
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

    async def _send_error(self, websocket: ServerConnection, detail: str) -> None:
        await websocket.send(_message("system", {"error": detail}))

    async def _broadcast(self, message: str) -> None:
        disconnected: list[str] = []
        for client_id, websocket in list(self.clients.items()):
            try:
                await websocket.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.append(client_id)
        for client_id in disconnected:
            self.clients.pop(client_id, None)

    async def _handle_message(self, client_id: str, websocket: ServerConnection, raw: str) -> None:
        try:
            incoming = json.loads(raw)
        except json.JSONDecodeError:
            await self._send_error(websocket, "message must be valid JSON")
            return

        message_type = incoming.get("type") if isinstance(incoming, dict) else None
        payload = incoming.get("payload") if isinstance(incoming, dict) else None
        if message_type not in SUPPORTED_TYPES:
            await self._send_error(websocket, "unsupported message type")
            return
        if not isinstance(payload, dict):
            await self._send_error(websocket, "payload must be an object")
            return

        outgoing = _message(message_type, payload)
        if message_type in {"broadcast", "system"}:
            await self._broadcast(outgoing)
            return

        target_id = payload.get("client_id", payload.get("target_client_id"))
        target = self.clients.get(target_id)
        if target is None:
            await self._send_error(websocket, "target client not found")
            return
        try:
            await target.send(outgoing)
        except websockets.exceptions.ConnectionClosed:
            self.clients.pop(target_id, None)
            await self._send_error(websocket, "target client not found")

    async def _handler(self, websocket: ServerConnection) -> None:
        client_id = str(uuid.uuid4())
        self.clients[client_id] = websocket
        try:
            async for raw in websocket:
                await self._handle_message(client_id, websocket, raw)
        finally:
            self.clients.pop(client_id, None)

    async def start(self) -> None:
        """Start serving. The returned server runs until :meth:`stop` is called."""
        self._server = await serve(
            self._handler,
            self.host,
            self.port,
            process_request=self._process_request,
        )
        sockets = self._server.sockets
        if sockets:
            self.port = sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self.clients.clear()

    async def __aenter__(self) -> "NotificationServer":
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.stop()


async def create_server(host: str = "127.0.0.1", port: int = 8765) -> NotificationServer:
    """Create and start a notification server, useful for application embedding."""
    server = NotificationServer(host, port)
    await server.start()
    return server


async def main(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = await create_server(host, port)
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        asyncio.run(main(args.host, args.port))
    except KeyboardInterrupt:
        pass
