"""Async WebSocket notification server with an HTTP health endpoint."""

from __future__ import annotations

import argparse
import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response


SUPPORTED_TYPES = {"broadcast", "direct", "system"}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": message_type,
        "payload": payload,
        "timestamp": utc_timestamp(),
    }


class ClientRegistry:
    """A registry safe to inspect or modify from concurrent threads."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = threading.RLock()

    def add(self, websocket: ServerConnection) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = websocket
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str) -> ServerConnection | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> list[ServerConnection]:
        with self._lock:
            return list(self._clients.values())

    def __len__(self) -> int:
        with self._lock:
            return len(self._clients)


class NotificationServer:
    def __init__(self) -> None:
        self.clients = ClientRegistry()

    async def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        del connection
        if request.path != "/health":
            return None

        body = json.dumps({"connected_clients": len(self.clients)}).encode("utf-8")
        return Response(
            200,
            "OK",
            Headers(
                {
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body)),
                    "Connection": "close",
                }
            ),
            body,
        )

    async def handler(self, websocket: ServerConnection) -> None:
        client_id = self.clients.add(websocket)
        await self._send(
            websocket,
            message("system", {"event": "connected", "client_id": client_id}),
        )

        try:
            async for raw_message in websocket:
                parsed, error = self._parse_message(raw_message)
                if error:
                    await self._send(websocket, message("system", {"error": error}))
                    continue
                await self._route(parsed, websocket)
        except ConnectionClosed:
            pass
        finally:
            self.clients.remove(client_id)

    @staticmethod
    def _parse_message(raw_message: str | bytes) -> tuple[dict[str, Any], str | None]:
        if isinstance(raw_message, bytes):
            return {}, "messages must be JSON text"
        try:
            parsed = json.loads(raw_message)
        except (json.JSONDecodeError, TypeError):
            return {}, "invalid JSON"

        if not isinstance(parsed, dict):
            return {}, "message must be a JSON object"
        if set(parsed) != {"type", "payload", "timestamp"}:
            return {}, "message must contain type, payload, and timestamp"
        if parsed["type"] not in SUPPORTED_TYPES:
            return {}, "unsupported message type"
        if not isinstance(parsed["payload"], dict):
            return {}, "payload must be an object"
        if not isinstance(parsed["timestamp"], str):
            return {}, "timestamp must be a string"
        return parsed, None

    async def _route(
        self, outgoing: dict[str, Any], sender: ServerConnection
    ) -> None:
        if outgoing["type"] in {"broadcast", "system"}:
            await self._send_many(self.clients.snapshot(), outgoing)
            return

        target_id = outgoing["payload"].get("client_id")
        if not isinstance(target_id, str):
            await self._send(
                sender,
                message("system", {"error": "direct payload requires client_id"}),
            )
            return
        target = self.clients.get(target_id)
        if target is None:
            await self._send(
                sender,
                message("system", {"error": "client not found", "client_id": target_id}),
            )
            return
        await self._send(target, outgoing)

    async def _send_many(
        self, clients: list[ServerConnection], outgoing: dict[str, Any]
    ) -> None:
        if clients:
            await asyncio.gather(
                *(self._send(client, outgoing) for client in clients),
                return_exceptions=True,
            )

    @staticmethod
    async def _send(websocket: ServerConnection, outgoing: dict[str, Any]) -> None:
        await websocket.send(json.dumps(outgoing))


async def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    notification_server = NotificationServer()
    async with serve(
        notification_server.handler,
        host,
        port,
        process_request=notification_server.process_request,
    ):
        await asyncio.get_running_loop().create_future()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    try:
        asyncio.run(run(args.host, args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
