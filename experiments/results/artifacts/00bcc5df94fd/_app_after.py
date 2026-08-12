"""Async WebSocket notification server with a small HTTP health endpoint."""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import unquote, urlparse

from websockets.asyncio.server import ServerConnection, serve


SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class _HealthHandler(BaseHTTPRequestHandler):
    server_version = "NotificationHealth/1.0"

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        owner: NotificationServer = self.server.owner  # type: ignore[attr-defined]
        path = urlparse(self.path).path
        if path == "/health":
            body_data = {"connected_clients": owner.client_count}
        elif path == "/channels":
            body_data = {"channels": owner.channel_counts()}
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            channel = unquote(path[len("/channels/"):-len("/subscribers")])
            if not channel or "/" in channel:
                self.send_error(404)
                return
            body_data = {"subscribers": owner.channel_subscribers(channel)}
        else:
            self.send_error(404)
            return
        body = json.dumps(body_data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: Any) -> None:
        return


class _HealthServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], owner: "NotificationServer") -> None:
        self.owner = owner
        super().__init__(address, _HealthHandler)


class NotificationServer:
    """Manage WebSocket clients and route notification messages.

    The registry is shared by the async WebSocket loop and the HTTP server
    thread, so every registry access is protected by ``registry_lock``.
    """

    def __init__(self, host: str = "127.0.0.1", websocket_port: int = 8765,
                 http_port: int = 8080) -> None:
        self.host = host
        self.websocket_port = websocket_port
        self.http_port = http_port
        self.registry_lock = threading.Lock()
        self.clients: dict[str, ServerConnection] = {}
        self.client_channels: dict[str, set[str]] = {}
        self.channels: dict[str, set[str]] = {}
        self._websocket_server = None
        self._health_server: _HealthServer | None = None
        self._health_thread: threading.Thread | None = None

    @property
    def client_count(self) -> int:
        with self.registry_lock:
            return len(self.clients)

    def channel_counts(self) -> dict[str, int]:
        with self.registry_lock:
            return {name: len(subscribers) for name, subscribers in self.channels.items()
                    if subscribers}

    def channel_subscribers(self, channel: str) -> list[str]:
        with self.registry_lock:
            return sorted(self.channels.get(channel, set()))

    async def start(self) -> None:
        self._websocket_server = await serve(
            self._handle_client, self.host, self.websocket_port
        )
        actual_ws_port = self._websocket_server.sockets[0].getsockname()[1]
        self.websocket_port = actual_ws_port
        self._health_server = _HealthServer((self.host, self.http_port), self)
        self.http_port = self._health_server.server_address[1]
        self._health_thread = threading.Thread(
            target=self._health_server.serve_forever,
            name="notification-health",
            daemon=True,
        )
        self._health_thread.start()

    async def stop(self) -> None:
        if self._websocket_server is not None:
            self._websocket_server.close()
            await self._websocket_server.wait_closed()
        with self.registry_lock:
            connections = list(self.clients.values())
            self.clients.clear()
            self.client_channels.clear()
            self.channels.clear()
        await asyncio.gather(*(connection.close() for connection in connections),
                             return_exceptions=True)
        if self._health_server is not None:
            self._health_server.shutdown()
            self._health_server.server_close()
        if self._health_thread is not None:
            self._health_thread.join(timeout=2)

    async def _handle_client(self, connection: ServerConnection) -> None:
        client_id = str(uuid.uuid4())
        with self.registry_lock:
            self.clients[client_id] = connection
            self.client_channels[client_id] = set()
        await connection.send(self._message("system", {
            "event": "connected", "client_id": client_id
        }))
        try:
            async for raw_message in connection:
                await self._handle_message(client_id, raw_message)
        finally:
            with self.registry_lock:
                self.clients.pop(client_id, None)
                for channel in self.client_channels.pop(client_id, set()):
                    subscribers = self.channels.get(channel)
                    if subscribers is not None:
                        subscribers.discard(client_id)
                        if not subscribers:
                            self.channels.pop(channel, None)

    async def _handle_message(self, sender_id: str, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(message, dict):
            return
        message_type = message.get("type")
        payload = message.get("payload", {})
        if message_type not in SUPPORTED_TYPES or not isinstance(payload, dict):
            return
        channel = message.get("channel", payload.get("channel"))
        if message_type in {"subscribe", "unsubscribe"}:
            if not isinstance(channel, str) or not channel:
                return
            with self.registry_lock:
                if sender_id not in self.clients:
                    return
                subscribed = self.client_channels.setdefault(sender_id, set())
                if message_type == "subscribe":
                    subscribed.add(channel)
                    self.channels.setdefault(channel, set()).add(sender_id)
                else:
                    subscribed.discard(channel)
                    subscribers = self.channels.get(channel)
                    if subscribers is not None:
                        subscribers.discard(sender_id)
                        if not subscribers:
                            self.channels.pop(channel, None)
            return
        outgoing = {
            "type": message_type,
            "payload": payload,
            "timestamp": message.get("timestamp") or timestamp(),
        }
        if isinstance(channel, str) and channel:
            outgoing["channel"] = channel
        encoded = json.dumps(outgoing)
        if message_type == "direct":
            target_id = payload.get("client_id") or payload.get("target_id")
            with self.registry_lock:
                target = self.clients.get(target_id)
                if channel:
                    target = target if target_id in self.channels.get(channel, set()) else None
            if target is not None:
                await target.send(encoded)
            return
        with self.registry_lock:
            if isinstance(channel, str) and channel:
                recipients = [self.clients[client_id]
                              for client_id in self.channels.get(channel, set())
                              if client_id in self.clients]
            else:
                recipients = list(self.clients.values())
        await asyncio.gather(*(client.send(encoded) for client in recipients),
                             return_exceptions=True)

    @staticmethod
    def _message(message_type: str, payload: dict[str, Any]) -> str:
        return json.dumps({"type": message_type, "payload": payload,
                           "timestamp": timestamp()})


# Convenient default instance for applications that import ``app``.
server = NotificationServer()


async def main() -> None:
    await server.start()
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
