"""WebSocket notification server built on the ``websockets`` library."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

SUPPORTED_TYPES = ("broadcast", "direct", "system")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_message(message_type: str, payload: Optional[dict] = None) -> dict:
    return {
        "type": message_type,
        "payload": payload if payload is not None else {},
        "timestamp": utcnow_iso(),
    }


def encode_message(message: dict) -> str:
    return json.dumps(message)


class ClientRegistry:
    """Registry of connected clients keyed by their unique client id.

    Asyncio runs everything on a single event loop, so plain dict reads and
    writes are always safe and require no locking.
    """

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}

    def register(self, websocket: ServerConnection) -> str:
        client_id = uuid.uuid4().hex
        self._clients[client_id] = websocket
        return client_id

    def unregister(self, client_id: str) -> None:
        self._clients.pop(client_id, None)

    def get(self, client_id: str) -> Optional[ServerConnection]:
        return self._clients.get(client_id)

    def count(self) -> int:
        return len(self._clients)

    def connections(self) -> list[ServerConnection]:
        return list(self._clients.values())

    def ids(self) -> list[str]:
        return list(self._clients.keys())


class NotificationServer:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        health_port: int = 8766,
    ) -> None:
        self.host = host
        self.port = port
        self.health_port = health_port
        self.registry = ClientRegistry()
        self._ws_server: Optional[asyncio.Server] = None
        self._health_server: Optional[asyncio.Server] = None

    async def start(self) -> "NotificationServer":
        self._ws_server = await serve(self._handle_connection, self.host, self.port)
        self.port = self._ws_server.sockets[0].getsockname()[1]
        self._health_server = await asyncio.start_server(
            self._handle_http, self.host, self.health_port
        )
        self.health_port = self._health_server.sockets[0].getsockname()[1]
        return self

    async def stop(self) -> None:
        if self._ws_server is not None:
            self._ws_server.close()
            await self._ws_server.wait_closed()
            self._ws_server = None
        if self._health_server is not None:
            self._health_server.close()
            await self._health_server.wait_closed()
            self._health_server = None

    async def __aenter__(self) -> "NotificationServer":
        return await self.start()

    async def __aexit__(self, *exc) -> None:
        await self.stop()

    async def _handle_connection(self, websocket: ServerConnection) -> None:
        client_id = self.registry.register(websocket)
        try:
            await websocket.send(
                encode_message(make_message("system", {"client_id": client_id}))
            )
            async for raw in websocket:
                await self._handle_incoming(client_id, raw)
        except ConnectionClosed:
            pass
        finally:
            self.registry.unregister(client_id)

    async def _handle_incoming(self, client_id: str, raw: str) -> None:
        try:
            message = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return
        if not isinstance(message, dict):
            return
        message_type = message.get("type")
        payload = message.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        if message_type == "broadcast":
            await self.broadcast("broadcast", payload)
        elif message_type == "direct":
            target = payload.get("to")
            if target:
                await self.send_to(target, "direct", payload)

    async def broadcast(
        self, message_type: str = "broadcast", payload: Optional[dict] = None
    ) -> int:
        message = encode_message(make_message(message_type, payload))
        targets = self.registry.connections()
        if targets:
            await asyncio.gather(
                *(websocket.send(message) for websocket in targets),
                return_exceptions=True,
            )
        return len(targets)

    async def send_to(
        self, client_id: str, message_type: str = "direct", payload: Optional[dict] = None
    ) -> bool:
        websocket = self.registry.get(client_id)
        if websocket is None:
            return False
        await websocket.send(encode_message(make_message(message_type, payload)))
        return True

    async def _handle_http(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=10)
            if not request_line:
                return
            parts = request_line.decode("latin-1").strip().split()
            method = parts[0] if parts else ""
            path = parts[1] if len(parts) > 1 else ""
            while True:
                line = await reader.readline()
                if not line or line in (b"\r\n", b"\n"):
                    break
            if method == "GET" and path == "/health":
                status = "200 OK"
                body = json.dumps(
                    {"status": "ok", "connected": self.registry.count()}
                ).encode("utf-8")
            else:
                status = "404 Not Found"
                body = json.dumps({"error": "not found"}).encode("utf-8")
            response = (
                f"HTTP/1.1 {status}\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode("latin-1") + body
            writer.write(response)
            await writer.drain()
        except (asyncio.TimeoutError, ConnectionError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass

    def run(self) -> None:
        asyncio.run(self._run_forever())

    async def _run_forever(self) -> None:
        await self.start()
        try:
            await asyncio.Future()
        finally:
            await self.stop()


if __name__ == "__main__":
    NotificationServer().run()
