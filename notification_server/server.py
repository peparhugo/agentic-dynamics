"""WebSocket-based notification server.

Accepts WebSocket connections, assigns each client a unique ID, and routes
JSON messages between clients (broadcast / direct / system). Also exposes a
plain HTTP GET /health endpoint on the same port via the websockets
library's process_request hook, so no extra web framework is needed.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from http import HTTPStatus
from typing import Any

import websockets
from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response
from websockets.datastructures import Headers

from .messages import Message, MessageValidationError, utc_now_iso
from .registry import ClientRegistry

logger = logging.getLogger("notification_server")

HEALTH_PATH = "/health"


class NotificationServer:
    """Owns the client registry and implements the connection/message logic."""

    def __init__(self) -> None:
        self.registry = ClientRegistry()

    def health_payload(self) -> dict[str, Any]:
        return {"status": "ok", "connected_clients": self.registry.count()}

    async def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        """Serve GET /health as plain HTTP; let everything else proceed to the
        normal WebSocket handshake."""
        path = request.path.split("?", 1)[0]
        if path == HEALTH_PATH:
            body = json.dumps(self.health_payload()).encode()
            headers = Headers()
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(body))
            return Response(HTTPStatus.OK.value, HTTPStatus.OK.phrase, headers, body)
        return None

    async def send_to(self, websocket: Any, message: Message) -> None:
        try:
            await websocket.send(message.to_json())
        except ConnectionClosed:
            pass

    async def send_error(self, websocket: Any, error: str) -> None:
        await self.send_to(
            websocket,
            Message(type="system", payload={"error": error}, timestamp=utc_now_iso()),
        )

    async def route(self, sender_id: str, websocket: Any, message: Message) -> None:
        if message.type == "broadcast":
            envelope = Message(
                type="broadcast",
                payload={"from": sender_id, **message.payload},
                timestamp=message.timestamp,
            )
            websockets.broadcast(self.registry.all_clients(), envelope.to_json())

        elif message.type == "system":
            envelope = Message(
                type="system",
                payload={"from": sender_id, **message.payload},
                timestamp=message.timestamp,
            )
            websockets.broadcast(self.registry.all_clients(), envelope.to_json())

        elif message.type == "direct":
            target_id = message.payload.get("target")
            if not target_id:
                await self.send_error(websocket, "'direct' messages require a 'target' client id in payload")
                return
            target_ws = self.registry.get(target_id)
            if target_ws is None:
                await self.send_error(websocket, f"unknown target client '{target_id}'")
                return
            envelope = Message(
                type="direct",
                payload={"from": sender_id, **message.payload},
                timestamp=message.timestamp,
            )
            await self.send_to(target_ws, envelope)

    async def handler(self, websocket: ServerConnection) -> None:
        client_id = self.registry.add(websocket)
        logger.info("client connected: %s", client_id)
        try:
            await self.send_to(
                websocket,
                Message(
                    type="system",
                    payload={"event": "connected", "client_id": client_id},
                    timestamp=utc_now_iso(),
                ),
            )
            async for raw in websocket:
                try:
                    message = Message.from_json(raw)
                except MessageValidationError as exc:
                    await self.send_error(websocket, str(exc))
                    continue
                await self.route(client_id, websocket, message)
        except ConnectionClosed:
            pass
        finally:
            self.registry.remove(client_id)
            logger.info("client disconnected: %s", client_id)
            websockets.broadcast(
                self.registry.all_clients(),
                Message(
                    type="system",
                    payload={"event": "disconnected", "client_id": client_id},
                    timestamp=utc_now_iso(),
                ).to_json(),
            )


def build_server(host: str = "localhost", port: int = 8765):
    notification_server = NotificationServer()
    server = serve(
        notification_server.handler,
        host,
        port,
        process_request=notification_server.process_request,
    )
    return notification_server, server


async def run(host: str = "localhost", port: int = 8765) -> None:
    _, server = build_server(host, port)
    async with server:
        logger.info("notification server listening on ws://%s:%d", host, port)
        await asyncio.get_running_loop().create_future()


def main() -> None:
    parser = argparse.ArgumentParser(description="WebSocket notification server")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(args.host, args.port))


if __name__ == "__main__":
    main()
