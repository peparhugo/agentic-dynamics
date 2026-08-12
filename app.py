"""Async WebSocket notification server with a small HTTP health endpoint."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Headers, Response

LOGGER = logging.getLogger(__name__)
MESSAGE_TYPES = {"broadcast", "direct", "system"}


def timestamp() -> str:
    """Return an ISO 8601 timestamp that is unambiguous across time zones."""
    return datetime.now(timezone.utc).isoformat()


def make_message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    if message_type not in MESSAGE_TYPES:
        raise ValueError(f"unsupported message type: {message_type}")
    return {"type": message_type, "payload": payload, "timestamp": timestamp()}


class ClientRegistry:
    """A thread-safe mapping of generated client IDs to WebSocket connections."""

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._lock = threading.RLock()

    def add(self, websocket: Any) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = websocket
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str) -> Any | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._clients)

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)


class NotificationServer:
    """WebSocket notification server.

    Clients send JSON messages. ``broadcast`` and ``system`` messages are sent
    to every connected client. A ``direct`` message is sent to the client ID
    in ``payload["client_id"]`` (``target_id`` is accepted as an alias).
    """

    def __init__(self, host: str = "localhost", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.clients = ClientRegistry()
        self._server: Any | None = None

    @property
    def connected_clients(self) -> int:
        return len(self.clients)

    async def process_request(self, _connection: Any, request: Any) -> Response | None:
        if request.path != "/health":
            return None
        body = json.dumps({"status": "ok", "connected_clients": len(self.clients)}).encode()
        headers = Headers([("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
        return Response(HTTPStatus.OK.value, "OK", headers, body)

    async def handler(self, websocket: Any) -> None:
        client_id = self.clients.add(websocket)
        await websocket.send(json.dumps(make_message("system", {"event": "connected", "client_id": client_id})))
        try:
            async for raw_message in websocket:
                await self.handle_message(raw_message, client_id)
        except ConnectionClosed:
            pass
        finally:
            self.clients.remove(client_id)

    async def handle_message(self, raw_message: str | bytes, sender_id: str) -> None:
        try:
            message = json.loads(raw_message)
            if not isinstance(message, dict):
                raise ValueError("message must be a JSON object")
            message_type = message.get("type")
            payload = message.get("payload")
            if message_type not in MESSAGE_TYPES or not isinstance(payload, dict):
                raise ValueError("message requires a supported type and object payload")
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            LOGGER.warning("Ignoring invalid message from %s: %s", sender_id, exc)
            return

        outgoing = make_message(message_type, payload)
        if message_type in {"broadcast", "system"}:
            await self.broadcast(outgoing)
            return

        target_id = payload.get("client_id", payload.get("target_id"))
        target = self.clients.get(target_id) if isinstance(target_id, str) else None
        if target is not None:
            await self._send(target, outgoing)

    async def _send(self, websocket: Any, message: dict[str, Any]) -> None:
        try:
            await websocket.send(json.dumps(message))
        except ConnectionClosed:
            pass

    async def broadcast(self, message: dict[str, Any]) -> None:
        clients = self.clients.snapshot()
        results = await asyncio.gather(
            *(self._send(websocket, message) for websocket in clients.values()),
            return_exceptions=True,
        )
        for client_id, result in zip(clients, results):
            if isinstance(result, Exception):
                self.clients.remove(client_id)

    async def start(self) -> Any:
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


async def run_server(host: str = "localhost", port: int = 8765) -> None:
    server = NotificationServer(host, port)
    await server.start()
    try:
        await asyncio.Future()
    finally:
        await server.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_server(args.host, args.port))


if __name__ == "__main__":
    main()
