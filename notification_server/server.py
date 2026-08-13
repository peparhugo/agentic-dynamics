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
import re
from typing import Any
from urllib.parse import unquote

import websockets
from websockets.asyncio.server import ServerConnection
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from .messages import InvalidMessage, build_message, encode, parse_message
from .registry import ClientRegistry

logger = logging.getLogger("notification_server")

HEALTH_PATH = "/health"
CHANNELS_PATH = "/channels"
CHANNEL_SUBSCRIBERS_RE = re.compile(r"^/channels/([^/]+)/subscribers$")


class NotificationServer:
    def __init__(self) -> None:
        self.registry = ClientRegistry()

    async def process_request(self, connection: ServerConnection, request: Request) -> Response | None:
        path = request.path.split("?", 1)[0]

        if path == HEALTH_PATH:
            body = json.dumps({"connected_clients": await self.registry.count()})
            return self._json_response(connection, 200, body)

        if path == CHANNELS_PATH:
            channels = await self.registry.channels_snapshot()
            body = json.dumps({
                "channels": [
                    {"name": name, "subscribers": count}
                    for name, count in sorted(channels.items())
                ],
            })
            return self._json_response(connection, 200, body)

        match = CHANNEL_SUBSCRIBERS_RE.match(path)
        if match:
            name = unquote(match.group(1))
            subscribers = await self.registry.subscribers(name)
            body = json.dumps({"channel": name, "subscribers": subscribers})
            return self._json_response(connection, 200, body)

        return None

    @staticmethod
    def _json_response(connection: ServerConnection, status: int, body: str) -> Response:
        response = connection.respond(status, body)
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
            channel = payload.get("channel")
            envelope = encode(build_message("broadcast", {**payload, "from": client_id}))
            if channel:
                await self.registry.broadcast_channel(envelope, channel)
            else:
                await self.registry.broadcast(envelope)
        elif msg_type == "direct":
            await self._handle_direct(client_id, payload)
        elif msg_type == "subscribe":
            await self._handle_subscribe(client_id, websocket, payload)
        elif msg_type == "unsubscribe":
            await self._handle_unsubscribe(client_id, websocket, payload)
        else:  # "system" — reserved for server-originated messages
            await self._send(websocket, build_message("system", {
                "event": "error",
                "detail": "clients may not send system messages",
            }))

    async def _handle_subscribe(self, client_id: str, websocket: Any, payload: dict) -> None:
        channel = payload.get("channel")
        if not isinstance(channel, str) or not channel:
            await self._send(websocket, build_message("system", {
                "event": "error",
                "detail": "subscribe requires a non-empty 'channel' string",
            }))
            return
        await self.registry.subscribe(client_id, channel)
        await self._send(websocket, build_message("system", {
            "event": "subscribed",
            "channel": channel,
            "client_id": client_id,
        }))

    async def _handle_unsubscribe(self, client_id: str, websocket: Any, payload: dict) -> None:
        channel = payload.get("channel")
        if not isinstance(channel, str) or not channel:
            await self._send(websocket, build_message("system", {
                "event": "error",
                "detail": "unsubscribe requires a non-empty 'channel' string",
            }))
            return
        await self.registry.unsubscribe(client_id, channel)
        await self._send(websocket, build_message("system", {
            "event": "unsubscribed",
            "channel": channel,
            "client_id": client_id,
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
