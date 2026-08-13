"""WebSocket-based notification server.

Accepts WebSocket connections, assigns each client a unique ID, and
supports broadcast / direct / system JSON messages between clients.
Also exposes a plain HTTP GET /health endpoint on the same port.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from notification_server.registry import ClientRegistry

logger = logging.getLogger("notification_server")

MESSAGE_TYPES = {"broadcast", "direct", "system"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_message(msg_type: str, payload: dict, **extra) -> dict:
    return {"type": msg_type, "payload": payload, "timestamp": now_iso(), **extra}


class NotificationServer:
    """Wraps a websockets server with client registry and message routing."""

    def __init__(self, host: str = "localhost", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.registry = ClientRegistry()
        self._server: Server | None = None

    async def start(self) -> Server:
        self._server = await serve(
            self._handler,
            self.host,
            self.port,
            process_request=self._process_request,
        )
        return self._server

    def stop(self) -> None:
        if self._server is not None:
            self._server.close()

    async def wait_closed(self) -> None:
        if self._server is not None:
            await self._server.wait_closed()

    @property
    def bound_port(self) -> int:
        if self._server is None:
            raise RuntimeError("server has not been started")
        return self._server.sockets[0].getsockname()[1]

    # -- HTTP -------------------------------------------------------

    def _process_request(self, connection: ServerConnection, request: Request):
        """Intercept plain HTTP requests before the WebSocket handshake."""
        if request.path == "/health":
            body = json.dumps(
                {"connected_clients": self.registry.count()}
            ).encode("utf-8")
            headers = Headers()
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(body))
            return Response(200, "OK", headers, body)
        return None

    # -- WebSocket handling ------------------------------------------

    async def _handler(self, websocket: ServerConnection) -> None:
        client_id = str(uuid4())
        self.registry.add(client_id, websocket)
        logger.info("client %s connected", client_id)
        try:
            await self._send(
                websocket,
                make_message("system", {"event": "connected", "client_id": client_id}),
            )
            async for raw_message in websocket:
                await self._route(client_id, websocket, raw_message)
        except ConnectionClosed:
            pass
        finally:
            self.registry.remove(client_id)
            logger.info("client %s disconnected", client_id)

    async def _route(self, client_id: str, websocket: ServerConnection, raw_message) -> None:
        try:
            message = json.loads(raw_message)
        except (json.JSONDecodeError, TypeError):
            await self._send_error(websocket, "invalid JSON")
            return

        if not isinstance(message, dict) or "type" not in message or "payload" not in message:
            await self._send_error(websocket, "message must contain 'type' and 'payload'")
            return

        msg_type = message["type"]
        payload = message["payload"]

        if msg_type not in MESSAGE_TYPES:
            await self._send_error(websocket, f"unknown message type: {msg_type}")
            return

        if not isinstance(payload, dict):
            await self._send_error(websocket, "'payload' must be an object")
            return

        if msg_type == "broadcast":
            await self.broadcast(payload, sender_id=client_id)
        elif msg_type == "direct":
            await self._handle_direct(client_id, websocket, payload)
        elif msg_type == "system":
            await self._send_error(websocket, "'system' messages are reserved for server use")

    async def _handle_direct(self, client_id: str, websocket: ServerConnection, payload: dict) -> None:
        target_id = payload.get("target_id")
        target = self.registry.get(target_id) if target_id else None
        if target is None:
            await self._send_error(websocket, f"target client not found: {target_id}")
            return
        await self._send(target, make_message("direct", payload, sender_id=client_id))

    async def broadcast(self, payload: dict, sender_id: str | None = None) -> None:
        message = make_message("broadcast", payload, sender_id=sender_id)
        for connection in self.registry.all():
            await self._send(connection, message)

    @staticmethod
    async def _send(websocket: ServerConnection, message: dict) -> None:
        try:
            await websocket.send(json.dumps(message))
        except ConnectionClosed:
            pass

    async def _send_error(self, websocket: ServerConnection, error: str) -> None:
        await self._send(websocket, make_message("system", {"error": error}))


async def run(host: str = "localhost", port: int = 8765) -> None:
    server = NotificationServer(host, port)
    await server.start()
    logger.info("notification server listening on %s:%s", host, port)
    await server.wait_closed()


def main() -> None:
    parser = argparse.ArgumentParser(description="WebSocket notification server")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(args.host, args.port))


if __name__ == "__main__":
    main()
