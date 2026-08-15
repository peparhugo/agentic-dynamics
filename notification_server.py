"""Async WebSocket notification server."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, urlsplit

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response


MESSAGE_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class NotificationServer:
    """Manage WebSocket clients and route notification messages."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.clients: dict[str, ServerConnection] = {}
        self._subscriptions: dict[str, set[str]] = {}
        self._client_channels: dict[str, set[str]] = {}
        self._server: Server | None = None

    @property
    def connected_client_count(self) -> int:
        return len(self.clients)

    async def start(self) -> None:
        """Start accepting WebSocket and health-check HTTP connections."""
        self._server = await serve(
            self._handle_client,
            self.host,
            self.port,
            process_request=self._process_request,
        )

    async def stop(self) -> None:
        """Stop accepting connections and close current clients."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        clients = list(self.clients.values())
        self.clients.clear()
        self._subscriptions.clear()
        self._client_channels.clear()
        if clients:
            await asyncio.gather(*(client.close() for client in clients))

    async def _process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        path = urlsplit(request.path).path
        if path == "/health":
            body_data: Any = {"connected_clients": self.connected_client_count}
        elif path == "/channels":
            body_data = {
                "channels": [
                    {"name": name, "subscriber_count": len(subscribers)}
                    for name, subscribers in sorted(self._subscriptions.items())
                    if subscribers
                ]
            }
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            name = unquote(path[len("/channels/") : -len("/subscribers")]).strip("/")
            body_data = {
                "channel": name,
                "subscribers": sorted(self._subscriptions.get(name, set()) & self.clients.keys()),
            }
        else:
            return None
        body = json.dumps(body_data).encode()
        return Response(
            200,
            "OK",
            Headers(
                [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(body))),
                ]
            ),
            body,
        )

    async def _handle_client(self, websocket: ServerConnection) -> None:
        client_id = uuid.uuid4().hex
        self.clients[client_id] = websocket
        await self._send(
            websocket,
            {"type": "system", "payload": {"event": "connected", "client_id": client_id}},
        )
        try:
            async for raw_message in websocket:
                await self._handle_message(client_id, raw_message)
        finally:
            self.clients.pop(client_id, None)
            for channel in self._client_channels.pop(client_id, set()):
                subscribers = self._subscriptions.get(channel)
                if subscribers is not None:
                    subscribers.discard(client_id)
                    if not subscribers:
                        self._subscriptions.pop(channel, None)

    async def _handle_message(self, sender_id: str, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(message, dict):
            return
        message_type = message.get("type")
        payload = message.get("payload")
        if message_type not in MESSAGE_TYPES:
            return

        if not isinstance(payload, dict):
            payload = {}
        channel = message.get("channel")
        if not isinstance(channel, str):
            channel = payload.get("channel")
        if not isinstance(channel, str) or not channel.strip():
            channel = None
        else:
            channel = channel.strip()

        if message_type in {"subscribe", "unsubscribe"}:
            if channel is None:
                return
            if message_type == "subscribe":
                self._subscriptions.setdefault(channel, set()).add(sender_id)
                self._client_channels.setdefault(sender_id, set()).add(channel)
            else:
                subscribers = self._subscriptions.get(channel)
                if subscribers is not None:
                    subscribers.discard(sender_id)
                    if not subscribers:
                        self._subscriptions.pop(channel, None)
                self._client_channels.get(sender_id, set()).discard(channel)
            return

        outgoing: dict[str, Any] = {
            "type": message_type,
            "payload": payload,
            "timestamp": _timestamp(),
        }
        if channel is not None:
            outgoing["channel"] = channel
            await self._broadcast(outgoing, channel)
        elif message_type == "direct":
            target_id = payload.get("client_id") or message.get("client_id")
            if isinstance(target_id, str) and target_id in self.clients:
                await self._send(self.clients[target_id], outgoing)
        elif message_type in {"broadcast", "system"}:
            await self._broadcast(outgoing)

    async def _broadcast(self, message: dict[str, Any], channel: str | None = None) -> None:
        encoded = json.dumps(message)
        if channel is None:
            clients = list(self.clients.items())
        else:
            subscriber_ids = self._subscriptions.get(channel, set())
            clients = [
                (client_id, self.clients[client_id])
                for client_id in subscriber_ids
                if client_id in self.clients
            ]
        results = await asyncio.gather(
            *(client.send(encoded) for _, client in clients), return_exceptions=True
        )
        for (client_id, _), result in zip(clients, results):
            if isinstance(result, Exception):
                self.clients.pop(client_id, None)
                for subscribed_channel in self._client_channels.pop(client_id, set()):
                    subscribers = self._subscriptions.get(subscribed_channel)
                    if subscribers is not None:
                        subscribers.discard(client_id)
                        if not subscribers:
                            self._subscriptions.pop(subscribed_channel, None)

    async def _send(self, client: ServerConnection, message: dict[str, Any]) -> None:
        try:
            await client.send(json.dumps(message))
        except Exception:
            # A client can disconnect between registry lookup and sending.
            pass


async def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = NotificationServer(host, port)
    await server.start()
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        pass
