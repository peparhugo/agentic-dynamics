"""Async WebSocket notification server with a small HTTP health endpoint."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, urlsplit

import websockets
from websockets.exceptions import ConnectionClosed


MESSAGE_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _message(message_type: str, payload: dict[str, Any]) -> str:
    return json.dumps(
        {"type": message_type, "payload": payload, "timestamp": _timestamp()}
    )


class NotificationServer:
    """Manage connected clients and route validated JSON notifications."""

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    @property
    def clients(self) -> dict[str, Any]:
        """Return a snapshot of the registry, never the mutable registry itself."""
        with self._lock:
            return dict(self._clients)

    @property
    def connected_client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    def add_client(self, websocket: Any) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self._clients[client_id] = websocket
        return client_id

    def remove_client(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in list(self._channels):
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def subscribe(self, client_id: str, channel: str) -> None:
        if not isinstance(channel, str) or not channel:
            return
        with self._lock:
            if client_id in self._clients:
                self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    def channel_snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                channel: len(subscribers)
                for channel, subscribers in sorted(self._channels.items())
            }

    def channel_subscribers(self, channel: str) -> list[str]:
        with self._lock:
            return sorted(self._channels.get(channel, set()))

    async def _send_to(self, client_id: str, message: str) -> None:
        with self._lock:
            websocket = self._clients.get(client_id)
        if websocket is None:
            return
        try:
            await websocket.send(message)
        except ConnectionClosed:
            self.remove_client(client_id)

    async def broadcast(self, message: str) -> None:
        with self._lock:
            recipients = list(self._clients.items())
        if not recipients:
            return
        results = await asyncio.gather(
            *(self._send_to(client_id, message) for client_id, _ in recipients),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                continue

    async def _broadcast_to_channel(self, channel: str, message: str) -> None:
        with self._lock:
            recipients = list(self._channels.get(channel, set()))
        await asyncio.gather(
            *(self._send_to(client_id, message) for client_id in recipients),
            return_exceptions=True,
        )

    async def handle_client(self, websocket: Any) -> None:
        client_id = self.add_client(websocket)
        await self._send_to(client_id, _message("system", {"client_id": client_id}))
        try:
            async for raw_message in websocket:
                await self.handle_message(client_id, raw_message)
        except (ConnectionClosed, asyncio.CancelledError):
            pass
        finally:
            self.remove_client(client_id)

    async def handle_message(self, sender_id: str, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(message, dict):
            return
        message_type = message.get("type")
        payload = message.get("payload")
        if message_type not in MESSAGE_TYPES or not isinstance(payload, dict):
            return

        channel = message.get("channel")
        if channel is None:
            channel = payload.get("channel")
        if not isinstance(channel, str) or not channel:
            channel = None

        if message_type == "subscribe":
            if channel is not None:
                self.subscribe(sender_id, channel)
            return
        if message_type == "unsubscribe":
            if channel is not None:
                self.unsubscribe(sender_id, channel)
            return

        outgoing = _message(message_type, payload)
        if channel is not None:
            outgoing_data = json.loads(outgoing)
            outgoing_data["channel"] = channel
            outgoing = json.dumps(outgoing_data)
        if channel is not None:
            await self._broadcast_to_channel(channel, outgoing)
            return
        if message_type == "direct":
            target_id = payload.get("client_id") or payload.get("target_id")
            if isinstance(target_id, str):
                await self._send_to(target_id, outgoing)
            return
        await self.broadcast(outgoing)

    def health(self) -> dict[str, Any]:
        return {"status": "ok", "connected_clients": self.connected_client_count}


class NotificationHTTPServer:
    """Minimal asyncio HTTP server used so health shares the same event loop."""

    def __init__(self, notification_server: NotificationServer) -> None:
        self.notification_server = notification_server

    async def handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=5)
            method, path, *_ = request_line.decode("ascii", "replace").split()
            while await reader.readline() != b"\r\n":
                pass
            if method == "GET" and path == "/health":
                body = json.dumps(self.notification_server.health()).encode()
                response = (
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                    + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                    + body
                )
            elif method == "GET" and path == "/channels":
                body = json.dumps({"channels": self.notification_server.channel_snapshot()}).encode()
                response = (
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                    + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                    + body
                )
            elif method == "GET" and urlsplit(path).path.startswith("/channels/"):
                channel_path = urlsplit(path).path.removeprefix("/channels/")
                if channel_path.endswith("/subscribers"):
                    channel = unquote(channel_path.removesuffix("/subscribers").rstrip("/"))
                    body = json.dumps(
                        {"channel": channel, "subscribers": self.notification_server.channel_subscribers(channel)}
                    ).encode()
                    response = (
                        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                        + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                        + body
                    )
                else:
                    body = b'{"error":"not found"}'
                    response = (
                        b"HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\n"
                        + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                        + body
                    )
            else:
                body = b'{"error":"not found"}'
                response = (
                    b"HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\n"
                    + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                    + body
                )
            writer.write(response)
            await writer.drain()
        except (asyncio.TimeoutError, ValueError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()


async def run_server(
    websocket_host: str = "0.0.0.0",
    websocket_port: int = 8765,
    http_host: str = "0.0.0.0",
    http_port: int = 8080,
) -> None:
    server = NotificationServer()
    websocket_server = await websockets.serve(server.handle_client, websocket_host, websocket_port)
    http_server = await asyncio.start_server(
        NotificationHTTPServer(server).handler, http_host, http_port
    )
    try:
        await asyncio.Future()
    finally:
        websocket_server.close()
        await websocket_server.wait_closed()
        http_server.close()
        await http_server.wait_closed()


# Convenient application object for callers that import ``app``.
app = NotificationServer()


if __name__ == "__main__":
    asyncio.run(
        run_server(
            websocket_port=int(os.getenv("WEBSOCKET_PORT", "8765")),
            http_port=int(os.getenv("HTTP_PORT", "8080")),
        )
    )
