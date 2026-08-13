"""
WebSocket-based notification server.

- Accepts WebSocket connections, assigns each client a unique ID.
- Supports broadcast / direct / system JSON messages.
- Cleans up clients on disconnect.
- Exposes GET /health as a plain HTTP endpoint (served on the same port,
  intercepted before the WebSocket handshake) returning the connected
  client count.
"""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any, Optional

import websockets
from websockets.legacy.server import WebSocketServerProtocol

MESSAGE_TYPES = {"broadcast", "direct", "system"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_message(msg_type: str, payload: dict) -> dict:
    return {"type": msg_type, "payload": payload, "timestamp": utc_now_iso()}


class ProtocolError(Exception):
    """Raised when an incoming message does not match the expected format."""


def parse_message(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ProtocolError(f"invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ProtocolError("message must be a JSON object")

    msg_type = data.get("type")
    if msg_type not in MESSAGE_TYPES:
        raise ProtocolError(
            f"unsupported type {msg_type!r}; expected one of {sorted(MESSAGE_TYPES)}"
        )

    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise ProtocolError("payload must be a JSON object")

    return {"type": msg_type, "payload": payload}


@dataclass
class ClientRegistry:
    """Thread-safe registry mapping client IDs to their WebSocket connection."""

    _clients: dict = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, client_id: str, websocket: WebSocketServerProtocol) -> None:
        with self._lock:
            self._clients[client_id] = websocket

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str) -> Optional[WebSocketServerProtocol]:
        with self._lock:
            return self._clients.get(client_id)

    def count(self) -> int:
        with self._lock:
            return len(self._clients)

    def snapshot(self) -> list:
        with self._lock:
            return list(self._clients.items())


class NotificationServer:
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.registry = ClientRegistry()
        self._server: Optional[websockets.WebSocketServer] = None

    async def register(self, websocket: WebSocketServerProtocol) -> str:
        client_id = str(uuid.uuid4())
        self.registry.add(client_id, websocket)
        return client_id

    async def unregister(self, client_id: str) -> None:
        self.registry.remove(client_id)

    async def send_to(self, client_id: str, message: dict) -> bool:
        websocket = self.registry.get(client_id)
        if websocket is None:
            return False
        try:
            await websocket.send(json.dumps(message))
            return True
        except websockets.ConnectionClosed:
            return False

    async def broadcast(self, message: dict, exclude: Optional[str] = None) -> None:
        data = json.dumps(message)
        for client_id, websocket in self.registry.snapshot():
            if client_id == exclude:
                continue
            try:
                await websocket.send(data)
            except websockets.ConnectionClosed:
                pass

    async def _dispatch(self, client_id: str, message: dict) -> None:
        msg_type = message["type"]
        payload = message["payload"]

        if msg_type == "broadcast":
            await self.broadcast(make_message("broadcast", payload))

        elif msg_type == "direct":
            target_id = payload.get("target")
            if not target_id:
                await self.send_to(
                    client_id,
                    make_message("system", {"error": "direct message requires payload.target"}),
                )
                return
            delivered = await self.send_to(
                client_id=target_id,
                message=make_message("direct", {"from": client_id, "data": payload.get("data")}),
            )
            if not delivered:
                await self.send_to(
                    client_id,
                    make_message("system", {"error": f"client {target_id} not found"}),
                )

        elif msg_type == "system":
            # Clients may not originate system messages; echo back a rejection.
            await self.send_to(
                client_id,
                make_message("system", {"error": "clients cannot send system messages"}),
            )

    async def handler(self, websocket: WebSocketServerProtocol) -> None:
        client_id = await self.register(websocket)
        try:
            await self.send_to(
                client_id, make_message("system", {"event": "connected", "client_id": client_id})
            )
            await self.broadcast(
                make_message("system", {"event": "client_joined", "client_id": client_id}),
                exclude=client_id,
            )

            async for raw in websocket:
                try:
                    message = parse_message(raw)
                except ProtocolError as exc:
                    await self.send_to(client_id, make_message("system", {"error": str(exc)}))
                    continue
                await self._dispatch(client_id, message)

        except websockets.ConnectionClosed:
            pass
        finally:
            await self.unregister(client_id)
            await self.broadcast(
                make_message("system", {"event": "client_left", "client_id": client_id})
            )

    async def process_request(self, path: str, request_headers) -> Optional[tuple]:
        if path == "/health":
            body = json.dumps({"connected_clients": self.registry.count()}).encode()
            headers = [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
            return HTTPStatus.OK, headers, body
        return None

    async def start(self) -> "websockets.WebSocketServer":
        self._server = await websockets.serve(
            self.handler,
            self.host,
            self.port,
            process_request=self.process_request,
        )
        return self._server

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None


async def main() -> None:
    server = NotificationServer(host="0.0.0.0", port=8765)
    await server.start()
    print(f"Notification server listening on ws://{server.host}:{server.port}")
    await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
