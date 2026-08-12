"""Async WebSocket notification server with a small health endpoint."""

from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from websockets.asyncio.server import Server, ServerConnection, serve


MESSAGE_TYPES = {"broadcast", "direct", "system"}


def message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Build a message with the wire format used by the server."""
    return {
        "type": message_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class NotificationServer:
    """Manage WebSocket clients and serve their current count over HTTP."""

    def __init__(self, websocket_host: str = "127.0.0.1", websocket_port: int = 8765,
                 http_host: str | None = None, http_port: int = 8080) -> None:
        self.websocket_host = websocket_host
        self.websocket_port = websocket_port
        self.http_host = http_host or websocket_host
        self.http_port = http_port
        self.clients: dict[str, ServerConnection] = {}
        self._clients_lock = threading.RLock()
        self._websocket_server: Server | None = None
        self._http_server: asyncio.AbstractServer | None = None

    @property
    def connected_clients(self) -> int:
        with self._clients_lock:
            return len(self.clients)

    async def start(self) -> "NotificationServer":
        self._websocket_server = await serve(
            self._handle_websocket, self.websocket_host, self.websocket_port
        )
        self._http_server = await asyncio.start_server(
            self._handle_http, self.http_host, self.http_port
        )
        self.websocket_port = self._websocket_server.sockets[0].getsockname()[1]
        self.http_port = self._http_server.sockets[0].getsockname()[1]
        return self

    async def stop(self) -> None:
        if self._websocket_server is not None:
            self._websocket_server.close()
            await self._websocket_server.wait_closed()
            self._websocket_server = None
        if self._http_server is not None:
            self._http_server.close()
            await self._http_server.wait_closed()
            self._http_server = None
        with self._clients_lock:
            self.clients.clear()

    async def broadcast(self, payload: dict[str, Any], message_type: str = "broadcast") -> None:
        if message_type not in MESSAGE_TYPES:
            raise ValueError(f"unsupported message type: {message_type}")
        wire_message = json.dumps(message(message_type, payload))
        with self._clients_lock:
            connections = list(self.clients.values())
        if connections:
            await asyncio.gather(*(client.send(wire_message) for client in connections),
                                 return_exceptions=True)

    async def send_direct(self, client_id: str, payload: dict[str, Any]) -> bool:
        with self._clients_lock:
            client = self.clients.get(client_id)
        if client is None:
            return False
        try:
            await client.send(json.dumps(message("direct", payload)))
        except Exception:
            return False
        return True

    async def _handle_websocket(self, websocket: ServerConnection) -> None:
        client_id = str(uuid4())
        with self._clients_lock:
            self.clients[client_id] = websocket
        try:
            await websocket.send(json.dumps(message("system", {"client_id": client_id})))
            async for raw_message in websocket:
                await self._handle_message(client_id, raw_message)
        except Exception:
            pass
        finally:
            with self._clients_lock:
                self.clients.pop(client_id, None)

    async def _handle_message(self, sender_id: str, raw_message: str) -> None:
        try:
            incoming = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(incoming, dict):
            return
        message_type = incoming.get("type")
        payload = incoming.get("payload")
        if message_type not in MESSAGE_TYPES or not isinstance(payload, dict):
            return
        if message_type == "direct":
            target_id = payload.get("client_id")
            if isinstance(target_id, str):
                direct_payload = {key: value for key, value in payload.items() if key != "client_id"}
                await self.send_direct(target_id, direct_payload)
            return
        await self.broadcast(payload, message_type)

    async def _handle_http(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = (await reader.readline()).decode("ascii", "ignore").strip()
            method, path, *_ = request_line.split()
            if method == "GET" and path == "/health":
                body = json.dumps({"connected_clients": self.connected_clients}).encode()
                status = "200 OK"
            else:
                body = json.dumps({"error": "not found"}).encode()
                status = "404 Not Found"
            headers = (f"HTTP/1.1 {status}\r\nContent-Type: application/json\r\n"
                       f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode()
            writer.write(headers + body)
            await writer.drain()
        except (ValueError, UnicodeError):
            writer.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def serve_forever(self) -> None:
        if self._websocket_server is None or self._http_server is None:
            await self.start()
        await asyncio.Future()

    def run(self) -> None:
        asyncio.run(self.serve_forever())


def create_server() -> NotificationServer:
    return NotificationServer()
