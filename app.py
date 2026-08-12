"""Async WebSocket notification server.

The WebSocket and health HTTP endpoint share one TCP port.  The server has no
framework dependency: ``websockets`` handles both the upgrade and the small
HTTP response needed by ``/health``.
"""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, urlsplit

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response


SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


def timestamp() -> str:
    """Return an unambiguous UTC timestamp for a message."""
    return datetime.now(timezone.utc).isoformat()


class ClientRegistry:
    """Thread-safe mapping of generated client IDs to WebSocket connections."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def add(self, connection: ServerConnection) -> str:
        client_id = uuid.uuid4().hex
        with self._lock:
            self._clients[client_id] = connection
        return client_id

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)
            for channel in list(self._channels):
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

    def subscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        with self._lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    def channel_subscribers(self, channel: str) -> set[str]:
        with self._lock:
            return set(self._channels.get(channel, set()))

    def channels(self) -> dict[str, set[str]]:
        with self._lock:
            return {name: set(ids) for name, ids in self._channels.items()}

    def get(self, client_id: str) -> ServerConnection | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> dict[str, ServerConnection]:
        with self._lock:
            return dict(self._clients)

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._clients)


def make_message(
    message_type: str, payload: dict[str, Any], channel: str | None = None
) -> dict[str, Any]:
    if message_type not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported message type: {message_type}")
    message = {"type": message_type, "payload": payload, "timestamp": timestamp()}
    if channel is not None:
        message["channel"] = channel
    return message


class NotificationServer:
    """WebSocket notification server with broadcast and direct delivery."""

    def __init__(self, host: str = "localhost", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.registry = ClientRegistry()
        self._server: Any = None

    async def start(self) -> None:
        self._server = await serve(
            self._handle_connection,
            self.host,
            self.port,
            process_request=self._process_request,
        )
        if self._server.sockets:
            self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        path = urlsplit(request.path).path
        body_data: dict[str, Any] | None = None
        if path == "/health":
            body_data = {"status": "ok", "clients": self.registry.count}
        elif path == "/channels":
            body_data = {
                "channels": [
                    {"name": name, "subscribers": len(subscribers)}
                    for name, subscribers in sorted(self.registry.channels().items())
                ]
            }
        elif path.startswith("/channels/") and path.endswith("/subscribers"):
            channel = unquote(path[len("/channels/") : -len("/subscribers")]).strip("/")
            if not channel:
                return None
            body_data = {
                "channel": channel,
                "subscribers": sorted(self.registry.channel_subscribers(channel)),
            }
        else:
            return None
        body = json.dumps(body_data).encode()
        return Response(
            200,
            "OK",
            Headers(
                {
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body)),
                }
            ),
            body,
        )

    async def _handle_connection(self, connection: ServerConnection) -> None:
        client_id = self.registry.add(connection)
        try:
            await connection.send(
                json.dumps(make_message("system", {"event": "connected", "client_id": client_id}))
            )
            async for raw_message in connection:
                await self._handle_message(client_id, raw_message)
        finally:
            self.registry.remove(client_id)

    async def _handle_message(self, sender_id: str, raw_message: str) -> None:
        try:
            message = json.loads(raw_message)
            if not isinstance(message, dict):
                raise ValueError
            message_type = message.get("type")
            payload = message.get("payload")
            if message_type in {"subscribe", "unsubscribe"} and payload is None:
                payload = {}
            if message_type not in SUPPORTED_TYPES or not isinstance(payload, dict):
                raise ValueError
            channel = message.get("channel")
            if channel is None:
                channel = payload.get("channel")
            if channel is not None and (
                not isinstance(channel, str) or not channel.strip()
            ):
                raise ValueError
            if message_type in {"subscribe", "unsubscribe"} and channel is None:
                raise ValueError
        except (json.JSONDecodeError, TypeError, ValueError):
            sender = self.registry.get(sender_id)
            if sender is not None:
                await sender.send(json.dumps(make_message("system", {"error": "invalid message"})))
            return

        channel = channel.strip() if isinstance(channel, str) else None
        if message_type == "subscribe":
            self.registry.subscribe(sender_id, channel)
            await self._send_control(sender_id, "subscribed", channel)
        elif message_type == "unsubscribe":
            self.registry.unsubscribe(sender_id, channel)
            await self._send_control(sender_id, "unsubscribed", channel)
        else:
            outgoing = make_message(message_type, payload, channel)
            if message_type == "broadcast":
                await self.broadcast(outgoing, channel)
            elif message_type == "direct":
                target_id = payload.get("client_id") or payload.get("recipient")
                target = self.registry.get(target_id) if isinstance(target_id, str) else None
                if target is not None and (
                    channel is None
                    or target_id in self.registry.channel_subscribers(channel)
                ):
                    await target.send(json.dumps(outgoing))
            else:
                # System messages are server-generated; clients may send them only
                # to themselves, which keeps the message contract predictable.
                sender = self.registry.get(sender_id)
                if sender is not None and (
                    channel is None
                    or sender_id in self.registry.channel_subscribers(channel)
                ):
                    await sender.send(json.dumps(outgoing))

    async def _send_control(self, client_id: str, event: str, channel: str) -> None:
        client = self.registry.get(client_id)
        if client is not None:
            await client.send(
                json.dumps(make_message("system", {"event": event, "channel": channel}))
            )

    async def broadcast(self, message: dict[str, Any], channel: str | None = None) -> None:
        encoded = json.dumps(message)
        clients = self.registry.snapshot()
        if channel is not None:
            clients = {
                client_id: connection
                for client_id, connection in clients.items()
                if client_id in self.registry.channel_subscribers(channel)
            }
        connections = clients.values()
        if connections:
            await asyncio.gather(*(connection.send(encoded) for connection in connections), return_exceptions=True)


async def run_server(host: str = "localhost", port: int = 8765) -> None:
    server = NotificationServer(host, port)
    await server.start()
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(run_server())
