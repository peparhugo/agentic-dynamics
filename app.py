"""Async WebSocket notification server with a small health endpoint."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed


MESSAGE_TYPES = {"broadcast", "direct", "system"}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class NotificationServer:
    """Serve notifications over WebSockets and connection count over HTTP."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        websocket_port: int = 8765,
        http_port: int = 8080,
    ) -> None:
        self.host = host
        self.websocket_port = websocket_port
        self.http_port = http_port
        self.clients: dict[str, Any] = {}
        self._clients_lock = asyncio.Lock()
        self._websocket_server: Any = None
        self._http_server: asyncio.AbstractServer | None = None

    @property
    def connected_count(self) -> int:
        return len(self.clients)

    async def start(self) -> None:
        """Start both listeners. Port zero may be used to select free ports."""
        self._websocket_server = await websockets.serve(
            self._handle_websocket, self.host, self.websocket_port
        )
        self._http_server = await asyncio.start_server(
            self._handle_http, self.host, self.http_port
        )
        self.websocket_port = self._websocket_server.sockets[0].getsockname()[1]
        self.http_port = self._http_server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        """Stop listeners and close all connected clients cleanly."""
        if self._websocket_server is not None:
            self._websocket_server.close()
            await self._websocket_server.wait_closed()
            self._websocket_server = None
        if self._http_server is not None:
            self._http_server.close()
            await self._http_server.wait_closed()
            self._http_server = None
        async with self._clients_lock:
            clients = list(self.clients.values())
            self.clients.clear()
        await asyncio.gather(*(client.close() for client in clients), return_exceptions=True)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a validated message to every currently connected client."""
        encoded = json.dumps(self._normalise_message(message))
        async with self._clients_lock:
            recipients = list(self.clients.items())
        results = await asyncio.gather(
            *(client.send(encoded) for _, client in recipients), return_exceptions=True
        )
        for (client_id, _), result in zip(recipients, results):
            if isinstance(result, Exception):
                await self._remove_client(client_id)

    async def _handle_websocket(self, websocket: Any) -> None:
        client_id = str(uuid.uuid4())
        async with self._clients_lock:
            self.clients[client_id] = websocket
        await websocket.send(
            json.dumps(
                {"type": "system", "payload": {"client_id": client_id}, "timestamp": _timestamp()}
            )
        )
        try:
            async for raw_message in websocket:
                await self._handle_message(client_id, raw_message)
        except (ConnectionClosed, asyncio.CancelledError):
            pass
        finally:
            await self._remove_client(client_id)

    async def _handle_message(self, sender_id: str, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
            if not isinstance(message, dict):
                raise ValueError
            normalised = self._normalise_message(message)
        except (ValueError, TypeError, json.JSONDecodeError):
            await self._send_system(sender_id, {"error": "invalid message"})
            return

        if normalised["type"] == "broadcast":
            await self.broadcast(normalised)
        elif normalised["type"] == "system":
            await self.broadcast(normalised)
        else:
            target_id = normalised["payload"].get("client_id")
            if not isinstance(target_id, str):
                await self._send_system(sender_id, {"error": "direct message requires payload.client_id"})
                return
            async with self._clients_lock:
                target = self.clients.get(target_id)
            if target is not None:
                await target.send(json.dumps(normalised))

    @staticmethod
    def _normalise_message(message: dict[str, Any]) -> dict[str, Any]:
        message_type = message.get("type")
        payload = message.get("payload")
        if message_type not in MESSAGE_TYPES or not isinstance(payload, dict):
            raise ValueError("message must contain a supported type and dict payload")
        timestamp = message.get("timestamp")
        return {
            "type": message_type,
            "payload": payload,
            "timestamp": timestamp if isinstance(timestamp, str) else _timestamp(),
        }

    async def _send_system(self, client_id: str, payload: dict[str, Any]) -> None:
        async with self._clients_lock:
            client = self.clients.get(client_id)
        if client is not None:
            await client.send(json.dumps({"type": "system", "payload": payload, "timestamp": _timestamp()}))

    async def _remove_client(self, client_id: str) -> None:
        async with self._clients_lock:
            self.clients.pop(client_id, None)

    async def _handle_http(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = (await reader.readline()).decode("ascii", errors="replace")
            method, path, *_ = request_line.split()
            while await reader.readline() not in (b"\r\n", b"\n", b""):
                pass
            if method == "GET" and path == "/health":
                body = json.dumps({"status": "ok", "connected_clients": self.connected_count}).encode()
                response = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: " + str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body
            else:
                body = b'{"error":"not found"}'
                response = b"HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\nContent-Length: " + str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body
            writer.write(response)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()


async def main() -> None:
    server = NotificationServer()
    await server.start()
    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
