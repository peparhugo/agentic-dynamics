"""Async WebSocket notification server.

The server exposes a WebSocket endpoint at ``/`` and a small HTTP health
endpoint on the same listening port.
"""

from __future__ import annotations

import asyncio
import itertools
import json
from datetime import datetime, timezone
from typing import Any

from websockets.asyncio.server import ServerConnection, serve
from websockets.http11 import Headers, Request, Response


_client_ids = itertools.count(1)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _message(message_type: str, payload: dict[str, Any]) -> str:
    return json.dumps(
        {"type": message_type, "payload": payload, "timestamp": _timestamp()}
    )


class NotificationServer:
    """Manage connected clients and serve notification messages."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.clients: dict[int, ServerConnection] = {}
        self._clients_lock = asyncio.Lock()
        self._server: Any = None

    @property
    def connected_client_count(self) -> int:
        """Return the count for callers outside the event loop lock context."""
        return len(self.clients)

    async def process_request(
        self, _connection: ServerConnection, request: Request
    ) -> Response | None:
        if request.path == "/health":
            body = json.dumps(
                {"status": "ok", "connected_clients": self.connected_client_count}
            ).encode()
            headers = Headers(
                [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
            )
            return Response(200, "OK", headers, body)
        return None

    async def handler(self, websocket: ServerConnection) -> None:
        if websocket.request.path != "/":
            await websocket.close(code=1008, reason="WebSocket path must be /")
            return

        client_id = next(_client_ids)
        async with self._clients_lock:
            self.clients[client_id] = websocket

        try:
            async for raw_message in websocket:
                await self.handle_message(client_id, raw_message)
        except Exception:
            # Connection errors are expected when a client disappears abruptly.
            pass
        finally:
            async with self._clients_lock:
                self.clients.pop(client_id, None)

    async def handle_message(self, sender_id: int, raw_message: str) -> None:
        try:
            incoming = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            return

        if not isinstance(incoming, dict):
            return
        message_type = incoming.get("type")
        payload = incoming.get("payload")
        if message_type not in {"broadcast", "direct", "system"} or not isinstance(
            payload, dict
        ):
            return

        if message_type == "direct":
            target_id = payload.get("client_id")
            if not isinstance(target_id, int):
                return
            async with self._clients_lock:
                target = self.clients.get(target_id)
            if target is not None:
                await target.send(_message("direct", payload))
            return

        await self.broadcast(_message(message_type, payload))

    async def broadcast(self, message: str | dict[str, Any]) -> None:
        """Send a JSON message to every client currently connected."""
        if isinstance(message, dict):
            message = _message(message["type"], message["payload"])
        async with self._clients_lock:
            recipients = list(self.clients.values())
        if recipients:
            await asyncio.gather(*(client.send(message) for client in recipients), return_exceptions=True)

    async def start(self) -> Any:
        self._server = await serve(
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

    async def run(self) -> None:
        await self.start()
        await asyncio.Future()


async def main() -> None:
    server = NotificationServer()
    try:
        await server.run()
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
