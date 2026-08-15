"""Async WebSocket notification server with a small health endpoint."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from aiohttp import web
from websockets.asyncio.server import Server, ServerConnection, serve


MESSAGE_TYPES = {"broadcast", "direct", "system"}


def timestamp() -> str:
    """Return an RFC 3339 timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat()


class NotificationServer:
    """Own WebSocket clients and route JSON notification messages."""

    def __init__(self) -> None:
        # All access happens on the asyncio event loop; no lock is needed.
        self.clients: dict[str, ServerConnection] = {}
        self.websocket_server: Server | None = None
        self.health_runner: web.AppRunner | None = None
        self.websocket_port: int | None = None
        self.health_port: int | None = None

    @property
    def client_count(self) -> int:
        return len(self.clients)

    def _message(self, message_type: str, payload: dict[str, Any]) -> str:
        return json.dumps(
            {"type": message_type, "payload": payload, "timestamp": timestamp()}
        )

    async def _send_system(self, client: ServerConnection, payload: dict[str, Any]) -> None:
        await client.send(self._message("system", payload))

    async def _broadcast(self, message: str) -> None:
        clients = tuple(self.clients.values())
        if not clients:
            return
        results = await asyncio.gather(
            *(client.send(message) for client in clients), return_exceptions=True
        )
        # A failed send is cleaned up by that connection's finally block. This
        # also keeps one stale client from preventing delivery to the others.
        del results

    async def _handle_message(self, client_id: str, data: Any) -> None:
        client = self.clients.get(client_id)
        if client is None:
            return
        if not isinstance(data, dict):
            await self._send_system(client, {"error": "message must be a JSON object"})
            return

        message_type = data.get("type")
        payload = data.get("payload")
        if message_type not in MESSAGE_TYPES or not isinstance(payload, dict):
            await self._send_system(
                client,
                {"error": "message requires a supported type and object payload"},
            )
            return

        if message_type == "direct":
            target_id = payload.get("client_id", payload.get("recipient_id"))
            if not isinstance(target_id, str) or target_id not in self.clients:
                await self._send_system(client, {"error": "target client not found"})
                return
            target_payload = payload.get("message", payload)
            if not isinstance(target_payload, dict):
                await self._send_system(client, {"error": "direct message must be an object"})
                return
            await self.clients[target_id].send(self._message("direct", target_payload))
            return

        await self._broadcast(self._message(message_type, payload))

    async def handler(self, websocket: ServerConnection) -> None:
        client_id = uuid4().hex
        self.clients[client_id] = websocket
        try:
            await self._send_system(websocket, {"client_id": client_id})
            async for raw_message in websocket:
                try:
                    data = json.loads(raw_message)
                except (TypeError, json.JSONDecodeError):
                    await self._send_system(websocket, {"error": "message must be valid JSON"})
                    continue
                await self._handle_message(client_id, data)
        finally:
            self.clients.pop(client_id, None)

    async def health(self, request: web.Request) -> web.Response:
        return web.json_response({"connected_clients": self.client_count})

    async def start(
        self,
        websocket_host: str = "127.0.0.1",
        websocket_port: int = 8765,
        health_host: str = "127.0.0.1",
        health_port: int = 8080,
    ) -> None:
        """Start both listeners. Use ``stop`` to release their sockets."""
        self.websocket_server = await serve(self.handler, websocket_host, websocket_port)
        self.websocket_port = self.websocket_server.sockets[0].getsockname()[1]

        health_app = web.Application()
        health_app.router.add_get("/health", self.health)
        self.health_runner = web.AppRunner(health_app)
        await self.health_runner.setup()
        site = web.TCPSite(self.health_runner, health_host, health_port)
        await site.start()
        self.health_port = site._server.sockets[0].getsockname()[1]  # type: ignore[union-attr]

    async def stop(self) -> None:
        if self.websocket_server is not None:
            self.websocket_server.close()
            await self.websocket_server.wait_closed()
            self.websocket_server = None
        if self.health_runner is not None:
            await self.health_runner.cleanup()
            self.health_runner = None


async def main() -> None:
    server = NotificationServer()
    await server.start()
    print(f"WebSocket server listening on port {server.websocket_port}")
    print(f"Health endpoint listening on port {server.health_port}")
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
