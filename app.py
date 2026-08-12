"""Async WebSocket notification server.

The WebSocket listener also serves ``GET /health`` through the
``websockets`` HTTP request hook, so the service only needs one port.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote

from websockets.asyncio.server import Server, ServerConnection, Request, serve
from websockets.datastructures import Headers
from websockets.http11 import Response
from websockets.exceptions import ConnectionClosed


LOGGER = logging.getLogger(__name__)
MESSAGE_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


def timestamp() -> str:
    """Return a JSON-friendly UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


class NotificationServer:
    """Manage clients and route notification messages between them."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.clients: dict[str, ServerConnection] = {}
        self.channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()
        self._server: Server | None = None

    @property
    def bound_port(self) -> int:
        """Return the actual listener port, including an OS-assigned port."""
        if self._server is None or not self._server.sockets:
            return self.port
        return self._server.sockets[0].getsockname()[1]

    async def client_count(self) -> int:
        with self._lock:
            return len(self.clients)

    def _make_message(self, message_type: str, payload: dict[str, Any]) -> str:
        return json.dumps(
            {"type": message_type, "payload": payload, "timestamp": timestamp()}
        )

    async def _health_response(self) -> Response:
        body = json.dumps({"connected_clients": await self.client_count()}).encode()
        return Response(
            200,
            "OK",
            Headers({"Content-Type": "application/json", "Content-Length": str(len(body))}),
            body,
        )

    def _json_response(self, body_value: Any, status: int = 200, reason: str = "OK") -> Response:
        body = json.dumps(body_value).encode()
        return Response(
            status,
            reason,
            Headers({"Content-Type": "application/json", "Content-Length": str(len(body))}),
            body,
        )

    async def _channels_response(self) -> Response:
        with self._lock:
            channels = {
                name: len(subscribers)
                for name, subscribers in self.channels.items()
                if subscribers
            }
        return self._json_response({"channels": channels})

    async def _subscribers_response(self, name: str) -> Response:
        with self._lock:
            subscribers = sorted(self.channels.get(name, set()))
        return self._json_response({"channel": name, "subscribers": subscribers})

    async def _process_request(
        self, _connection: ServerConnection, request: Request
    ) -> Response | None:
        path = request.path.split("?", 1)[0]
        if request.headers.get("Connection", "").lower() == "upgrade":
            return None
        if path == "/health":
            return await self._health_response()
        if path == "/channels":
            return await self._channels_response()
        if path.startswith("/channels/") and path.endswith("/subscribers"):
            name = unquote(path[len("/channels/") : -len("/subscribers")]).strip("/")
            if name:
                return await self._subscribers_response(name)
        if path.startswith("/channels/"):
            return self._json_response({"error": "not found"}, 404, "Not Found")
        return None

    async def _register(self, connection: ServerConnection) -> str:
        client_id = str(uuid.uuid4())
        with self._lock:
            self.clients[client_id] = connection
        return client_id

    async def _remove(self, client_id: str) -> None:
        with self._lock:
            self.clients.pop(client_id, None)
            for name in list(self.channels):
                self.channels[name].discard(client_id)
                if not self.channels[name]:
                    del self.channels[name]

    async def _send_to(self, connection: ServerConnection, message: str) -> bool:
        try:
            await connection.send(message)
            return True
        except ConnectionClosed:
            return False

    async def broadcast(
        self, message_type: str, payload: dict[str, Any], channel: str | None = None
    ) -> None:
        """Send a valid message to all clients or subscribers of a channel."""
        message = self._make_message(message_type, payload)
        with self._lock:
            if channel is None:
                recipients = list(self.clients.items())
            else:
                recipients = [
                    (client_id, self.clients[client_id])
                    for client_id in self.channels.get(channel, set())
                    if client_id in self.clients
                ]
        results = await asyncio.gather(
            *(self._send_to(connection, message) for _, connection in recipients),
            return_exceptions=False,
        )
        for (client_id, _), sent in zip(recipients, results):
            if not sent:
                await self._remove(client_id)

    async def _handle_message(self, client_id: str, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
            message_type = message.get("type")
            payload = message.get("payload")
            if message_type not in MESSAGE_TYPES or not isinstance(payload, dict):
                raise ValueError("type must be supported and payload must be an object")
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as exc:
            with self._lock:
                connection = self.clients.get(client_id)
            if connection is not None:
                await self._send_to(
                    connection,
                    self._make_message("system", {"error": str(exc)}),
                )
            return

        channel = payload.get("channel", message.get("channel"))
        if channel is not None and not isinstance(channel, str):
            await self._send_error(client_id, "channel must be a string")
            return
        if channel is not None:
            channel = channel.strip()
            if not channel:
                await self._send_error(client_id, "channel must be a non-empty string")
                return

        if message_type == "direct" and channel is None:
            target_id = payload.get("client_id")
            with self._lock:
                target = self.clients.get(target_id)
            if target is not None:
                await self._send_to(target, self._make_message("direct", payload))
            return

        if message_type in {"subscribe", "unsubscribe"}:
            channel = payload.get("channel", message.get("channel"))
            if not isinstance(channel, str) or not channel.strip():
                await self._send_error(client_id, "channel must be a non-empty string")
                return
            channel = channel.strip()
            with self._lock:
                if message_type == "subscribe":
                    self.channels.setdefault(channel, set()).add(client_id)
                else:
                    subscribers = self.channels.get(channel)
                    if subscribers is not None:
                        subscribers.discard(client_id)
                        if not subscribers:
                            del self.channels[channel]
            return

        await self.broadcast(message_type, payload, channel)

    async def _send_error(self, client_id: str, error: str) -> None:
        with self._lock:
            connection = self.clients.get(client_id)
        if connection is not None:
            await self._send_to(connection, self._make_message("system", {"error": error}))

    async def _handler(self, connection: ServerConnection) -> None:
        client_id = await self._register(connection)
        await connection.send(
            self._make_message("system", {"event": "connected", "client_id": client_id})
        )
        try:
            async for raw_message in connection:
                await self._handle_message(client_id, raw_message)
        except ConnectionClosed:
            pass
        finally:
            await self._remove(client_id)

    async def start(self) -> None:
        """Start serving until :meth:`stop` is called."""
        if self._server is not None:
            return
        self._server = await serve(
            self._handler,
            self.host,
            self.port,
            process_request=self._process_request,
        )

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        with self._lock:
            self.clients.clear()
            self.channels.clear()


async def main() -> None:
    server = NotificationServer()
    await server.start()
    LOGGER.info("Notification server listening on %s:%s", server.host, server.bound_port)
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
