"""Async WebSocket notification server with a small health endpoint."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed


LOGGER = logging.getLogger(__name__)
SUPPORTED_TYPES = {"broadcast", "direct", "system"}


def make_message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Create a message with the wire format used by the server."""
    if message_type not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported message type: {message_type}")
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    return {
        "type": message_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class ClientRegistry:
    """Maps generated client IDs to sockets and serializes registry changes."""

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def add(self, websocket: Any) -> str:
        client_id = str(uuid.uuid4())
        async with self._lock:
            self._clients[client_id] = websocket
        return client_id

    async def remove(self, client_id: str) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)

    async def count(self) -> int:
        async with self._lock:
            return len(self._clients)

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            return dict(self._clients)

    async def get(self, client_id: str) -> Any | None:
        async with self._lock:
            return self._clients.get(client_id)


class NotificationServer:
    """WebSocket notification server and HTTP health endpoint."""

    def __init__(self, host: str = "127.0.0.1", websocket_port: int = 8765,
                 http_port: int = 8080) -> None:
        self.host = host
        self.websocket_port = websocket_port
        self.http_port = http_port
        self.clients = ClientRegistry()
        self._websocket_server: Any | None = None
        self._http_server: asyncio.AbstractServer | None = None

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a pre-built message to every currently connected client."""
        encoded = json.dumps(message)
        clients = await self.clients.snapshot()
        if clients:
            results = await asyncio.gather(
                *(websocket.send(encoded) for websocket in clients.values()),
                return_exceptions=True,
            )
            for client_id, result in zip(clients, results):
                if isinstance(result, Exception):
                    await self.clients.remove(client_id)

    async def broadcast_payload(self, payload: dict[str, Any]) -> None:
        await self.broadcast(make_message("broadcast", payload))

    async def _handle_websocket(self, websocket: Any, *_: Any) -> None:
        client_id = await self.clients.add(websocket)
        try:
            await websocket.send(json.dumps(make_message("system", {"client_id": client_id})))
            async for raw_message in websocket:
                await self._handle_message(client_id, raw_message)
        except (ConnectionClosed, asyncio.CancelledError):
            raise
        except Exception:
            LOGGER.exception("WebSocket client %s failed", client_id)
        finally:
            await self.clients.remove(client_id)

    async def _handle_message(self, sender_id: str, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
            message_type = message["type"]
            payload = message["payload"]
            if message_type not in SUPPORTED_TYPES or not isinstance(payload, dict):
                raise ValueError
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            sender = await self.clients.get(sender_id)
            if sender is not None:
                await sender.send(json.dumps(make_message("system", {"error": "invalid message"})))
            return

        outgoing = make_message(message_type, payload)
        if message_type == "broadcast" or message_type == "system":
            await self.broadcast(outgoing)
            return

        recipient_id = payload.get("client_id") or payload.get("recipient_id")
        recipient = await self.clients.get(recipient_id) if isinstance(recipient_id, str) else None
        if recipient is not None:
            await recipient.send(json.dumps(outgoing))

    async def _handle_http(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = await reader.readline()
            method, path, *_ = request_line.decode("ascii", "replace").split()
            if method == "GET" and path == "/health":
                body = json.dumps({"connected_clients": await self.clients.count()}).encode()
                status = "200 OK"
            else:
                body = json.dumps({"error": "not found"}).encode()
                status = "404 Not Found"
            headers = (
                f"HTTP/1.1 {status}\r\nContent-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
            ).encode()
            writer.write(headers + body)
            await writer.drain()
        except (ValueError, UnicodeDecodeError):
            writer.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self) -> None:
        self._websocket_server = await websockets.serve(
            self._handle_websocket, self.host, self.websocket_port
        )
        self._http_server = await asyncio.start_server(
            self._handle_http, self.host, self.http_port
        )

    async def stop(self) -> None:
        if self._websocket_server is not None:
            self._websocket_server.close()
            await self._websocket_server.wait_closed()
            self._websocket_server = None
        if self._http_server is not None:
            self._http_server.close()
            await self._http_server.wait_closed()
            self._http_server = None

    async def run(self) -> None:
        await self.start()
        try:
            await asyncio.Future()
        finally:
            await self.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(NotificationServer().run())


if __name__ == "__main__":
    main()
