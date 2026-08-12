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
from urllib.parse import unquote

from websockets.asyncio.server import ServerConnection, serve
from websockets.http11 import Headers, Request, Response


_client_ids = itertools.count(1)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _message(
    message_type: str, payload: dict[str, Any], channel: str | None = None
) -> str:
    message = {"type": message_type, "payload": payload, "timestamp": _timestamp()}
    if channel is not None:
        message["channel"] = channel
    return json.dumps(message)


class NotificationServer:
    """Manage connected clients and serve notification messages."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.clients: dict[int, ServerConnection] = {}
        self.channels: dict[str, set[int]] = {}
        self._client_channels: dict[int, set[str]] = {}
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
            headers = Headers([
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
            ])
            return Response(200, "OK", headers, body)
        if request.path == "/channels":
            async with self._clients_lock:
                channels = {
                    name: len(subscribers)
                    for name, subscribers in self.channels.items()
                    if subscribers
                }
            return self._json_response({"channels": channels})
        channel_prefix = "/channels/"
        if request.path.startswith(channel_prefix) and request.path.endswith(
            "/subscribers"
        ):
            encoded_name = request.path[len(channel_prefix) : -len("/subscribers")]
            if not encoded_name or "/" in encoded_name:
                return self._json_response({"error": "invalid channel"}, 400, "Bad Request")
            channel = unquote(encoded_name)
            async with self._clients_lock:
                subscribers = sorted(self.channels.get(channel, set()))
            return self._json_response(
                {"channel": channel, "subscribers": subscribers}
            )
        return None

    @staticmethod
    def _json_response(
        value: dict[str, Any], status_code: int = 200, reason: str = "OK"
    ) -> Response:
        body = json.dumps(value).encode()
        return Response(
            status_code,
            reason,
            Headers([
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
            ]),
            body,
        )

    async def handler(self, websocket: ServerConnection) -> None:
        if websocket.request.path != "/":
            await websocket.close(code=1008, reason="WebSocket path must be /")
            return

        client_id = next(_client_ids)
        async with self._clients_lock:
            self.clients[client_id] = websocket
            self._client_channels[client_id] = set()

        try:
            async for raw_message in websocket:
                await self.handle_message(client_id, raw_message)
        except Exception:
            # Connection errors are expected when a client disappears abruptly.
            pass
        finally:
            async with self._clients_lock:
                self.clients.pop(client_id, None)
                for channel in self._client_channels.pop(client_id, set()):
                    subscribers = self.channels.get(channel)
                    if subscribers is not None:
                        subscribers.discard(client_id)
                        if not subscribers:
                            self.channels.pop(channel, None)

    async def handle_message(self, sender_id: int, raw_message: str) -> None:
        try:
            incoming = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            return

        if not isinstance(incoming, dict):
            return
        message_type = incoming.get("type")
        payload = incoming.get("payload")
        if message_type in {"subscribe", "unsubscribe"}:
            channel = incoming.get("channel")
            if channel is None and isinstance(payload, dict):
                channel = payload.get("channel")
            if not isinstance(channel, str) or not channel:
                return
            async with self._clients_lock:
                if sender_id not in self.clients:
                    return
                if message_type == "subscribe":
                    self.channels.setdefault(channel, set()).add(sender_id)
                    self._client_channels.setdefault(sender_id, set()).add(channel)
                else:
                    subscribers = self.channels.get(channel)
                    if subscribers is not None:
                        subscribers.discard(sender_id)
                        if not subscribers:
                            self.channels.pop(channel, None)
                    self._client_channels.setdefault(sender_id, set()).discard(channel)
            return

        if message_type not in {"broadcast", "direct", "system"} or not isinstance(
            payload, dict
        ):
            return

        channel = incoming.get("channel")
        if channel is None:
            channel = payload.get("channel")
        if channel is not None and not isinstance(channel, str):
            return

        if message_type == "direct":
            target_id = payload.get("client_id")
            if not isinstance(target_id, int):
                return
            async with self._clients_lock:
                target = self.clients.get(target_id)
                subscribed = channel is None or target_id in self.channels.get(channel, set())
            if target is not None and subscribed:
                await target.send(_message("direct", payload, channel))
            return

        await self.broadcast(_message(message_type, payload, channel), channel=channel)

    async def broadcast(
        self, message: str | dict[str, Any], channel: str | None = None
    ) -> None:
        """Send a message to every client, or only to subscribers of a channel."""
        if isinstance(message, dict):
            channel = message.get("channel", channel)
            message = _message(message["type"], message["payload"], channel)
        async with self._clients_lock:
            if channel is None:
                recipients = list(self.clients.values())
            else:
                recipients = [
                    self.clients[client_id]
                    for client_id in self.channels.get(channel, set())
                    if client_id in self.clients
                ]
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
