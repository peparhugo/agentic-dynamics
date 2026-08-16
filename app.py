"""Async WebSocket notification server with a small HTTP health endpoint."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, urlsplit

import websockets
from websockets.http11 import Headers, Response
from websockets.server import ServerConnection


LOGGER = logging.getLogger(__name__)
SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


def timestamp() -> str:
    """Return an unambiguous UTC timestamp for wire messages."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class NotificationServer:
    """Manage WebSocket clients and route notification messages."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.clients: dict[str, ServerConnection] = {}
        self.channels: dict[str, set[str]] = {}
        self._client_channels: dict[str, set[str]] = {}
        self._server: Any = None

    @property
    def client_count(self) -> int:
        return len(self.clients)

    async def start(self) -> "NotificationServer":
        """Start serving WebSocket connections and HTTP health checks."""
        self._server = await websockets.serve(
            self._handle_connection,
            self.host,
            self.port,
            process_request=self._process_request,
        )
        socket = self._server.sockets[0]
        self.port = socket.getsockname()[1]
        return self

    async def stop(self) -> None:
        """Stop accepting clients and close existing connections."""
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    async def broadcast(self, payload: dict[str, Any], message_type: str = "broadcast") -> None:
        """Send a notification to all clients or to a channel's subscribers."""
        if message_type not in SUPPORTED_TYPES:
            raise ValueError(f"unsupported message type: {message_type}")
        channel = payload.get("channel")
        if isinstance(channel, str):
            client_ids = self.channels.get(channel, set())
            clients = [self.clients[client_id] for client_id in client_ids if client_id in self.clients]
        else:
            clients = list(self.clients.values())
        await self._send_to(clients, self._message(message_type, payload))

    async def send_direct(self, client_id: str, payload: dict[str, Any]) -> None:
        """Send a notification to one client, if it is still connected."""
        client = self.clients.get(client_id)
        if client is not None:
            await self._send_to([client], self._message("direct", payload))

    async def _handle_connection(self, websocket: ServerConnection) -> None:
        client_id = str(uuid.uuid4())
        self.clients[client_id] = websocket
        self._client_channels[client_id] = set()
        try:
            async for raw_message in websocket:
                await self._handle_message(raw_message, client_id)
        except websockets.ConnectionClosed:
            pass
        finally:
            self.clients.pop(client_id, None)
            for channel in self._client_channels.pop(client_id, set()):
                subscribers = self.channels.get(channel)
                if subscribers is not None:
                    subscribers.discard(client_id)
                    if not subscribers:
                        self.channels.pop(channel, None)

    async def _handle_message(self, raw_message: str, client_id: str | None = None) -> None:
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
            if client_id is None or not isinstance(channel, str) or not channel:
                return
            if message_type == "subscribe":
                self.channels.setdefault(channel, set()).add(client_id)
                self._client_channels.setdefault(client_id, set()).add(channel)
            else:
                self._unsubscribe(client_id, channel)
            return

        if message_type == "direct":
            target_id = payload.get("client_id", payload.get("target_id"))
            if isinstance(target_id, str):
                direct_payload = {key: value for key, value in payload.items() if key not in {"client_id", "target_id"}}
                if isinstance(channel, str):
                    direct_payload["channel"] = channel
                    if target_id not in self.channels.get(channel, set()):
                        return
                await self.send_direct(target_id, direct_payload)
        else:
            if isinstance(channel, str) and "channel" not in payload:
                payload = {**payload, "channel": channel}
            await self.broadcast(payload, message_type)

    def _unsubscribe(self, client_id: str, channel: str) -> None:
        self._client_channels.get(client_id, set()).discard(channel)
        subscribers = self.channels.get(channel)
        if subscribers is not None:
            subscribers.discard(client_id)
            if not subscribers:
                self.channels.pop(channel, None)

    async def _send_to(self, clients: list[ServerConnection], message: dict[str, Any]) -> None:
        encoded = json.dumps(message)
        results = await asyncio.gather(*(client.send(encoded) for client in clients), return_exceptions=True)
        for client, result in zip(clients, results):
            if isinstance(result, Exception):
                client_id = next((key for key, value in self.clients.items() if value is client), None)
                if client_id is not None:
                    self.clients.pop(client_id, None)
                    for channel in self._client_channels.pop(client_id, set()):
                        subscribers = self.channels.get(channel)
                        if subscribers is not None:
                            subscribers.discard(client_id)
                            if not subscribers:
                                self.channels.pop(channel, None)

    @staticmethod
    def _message(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"type": message_type, "payload": payload, "timestamp": timestamp()}

    def _process_request(self, _connection: ServerConnection, request: Any) -> Response | None:
        path = urlsplit(request.path).path
        if path == "/health":
            body = json.dumps({"status": "ok", "connected_clients": self.client_count}).encode()
        elif path == "/channels":
            body = json.dumps({
                "channels": [
                    {"name": name, "subscriber_count": len(subscribers)}
                    for name, subscribers in sorted(self.channels.items())
                    if subscribers
                ]
            }).encode()
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            name = unquote(path[len("/channels/") : -len("/subscribers")]).rstrip("/")
            if not name:
                return None
            body = json.dumps({
                "channel": name,
                "subscribers": sorted(self.channels.get(name, set())),
            }).encode()
        else:
            return None
        return Response(
            200,
            "OK",
            Headers({"Content-Type": "application/json", "Content-Length": str(len(body))}),
            body,
        )


async def serve(host: str = "127.0.0.1", port: int = 8765) -> NotificationServer:
    """Create and start a notification server."""
    return await NotificationServer(host, port).start()


async def main() -> None:
    server = await serve()
    LOGGER.info("notification server listening on %s:%s", server.host, server.port)
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
