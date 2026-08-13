"""WebSocket-based notification server.

Clients connect over WebSocket, are assigned a unique ID, and can broadcast
JSON messages to every other connected client or send one directly to a
specific client ID. A plain HTTP GET /health is served from the same port
for monitoring.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import websockets
from websockets.asyncio.server import ServerConnection
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from .messages import InvalidMessage, build_message, encode, parse_message
from .registry import ClientRegistry

logger = logging.getLogger("notification_server")

HEALTH_PATH = "/health"


class NotificationServer:
    def __init__(self) -> None:
        self.registry = ClientRegistry()

    async def process_request(self, connection: ServerConnection, request: Request) -> Response | None:
        if request.path.split("?", 1)[0] != HEALTH_PATH:
            return None
        body = json.dumps({"connected_clients": await self.registry.count()})
        response = connection.respond(200, body)
        response.headers["Content-Type"] = "application/json"
        return response

    async def handler(self, websocket: ServerConnection) -> None:
        client_id = await self.registry.register(websocket)
        logger.info("client %s connected", client_id)
        await self._send(websocket, build_message("system", {
            "event": "connected",
            "client_id": client_id,
        }))
        await self.registry.broadcast(
            encode(build_message("system", {
                "event": "client_joined",
                "client_id": client_id,
                "connected_clients": await self.registry.count(),
            })),
            exclude=(client_id,),
        )
        try:
            async for raw in websocket:
                await self._dispatch(client_id, websocket, raw)
        except ConnectionClosed:
            pass
        finally:
            await self.registry.unregister(client_id)
            logger.info("client %s disconnected", client_id)
            await self.registry.broadcast(
                encode(build_message("system", {
                    "event": "client_left",
                    "client_id": client_id,
                    "connected_clients": await self.registry.count(),
                }))
            )

    async def _dispatch(self, client_id: str, websocket: Any, raw: str) -> None:
        try:
            message = parse_message(raw)
        except InvalidMessage as exc:
            await self._send(websocket, build_message("system", {
                "event": "error",
                "detail": str(exc),
            }))
            return

        msg_type = message["type"]
        payload = message["payload"]

        if msg_type == "broadcast":
            await self.registry.broadcast(encode(build_message(
                "broadcast",
                {**payload, "from": client_id},
            )))
        elif msg_type == "direct":
            await self._handle_direct(client_id, payload)
        else:  # "system" — reserved for server-originated messages
            await self._send(websocket, build_message("system", {
                "event": "error",
                "detail": "clients may not send system messages",
            }))

    async def _handle_direct(self, sender_id: str, payload: dict) -> None:
        target_id = payload.get("target")
        target_ws = await self.registry.get(target_id) if target_id else None
        if target_ws is None:
            sender_ws = await self.registry.get(sender_id)
            if sender_ws is not None:
                await self._send(sender_ws, build_message("system", {
                    "event": "error",
                    "detail": f"unknown target: {target_id!r}",
                }))
            return
        await self._send(target_ws, build_message(
            "direct",
            {**payload, "from": sender_id},
        ))

    @staticmethod
    async def _send(websocket: Any, message: dict) -> None:
        try:
            await websocket.send(encode(message))
        except ConnectionClosed:
            pass


def create_app() -> NotificationServer:
    return NotificationServer()


async def run_server(host: str = "localhost", port: int = 8765) -> None:
    app = create_app()
    async with websockets.serve(app.handler, host, port, process_request=app.process_request):
        logger.info("notification server listening on %s:%s", host, port)
        await asyncio.Future()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
