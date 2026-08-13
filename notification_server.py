"""
WebSocket-based notification server.

Accepts WebSocket connections, assigns each client a unique ID, and lets
clients broadcast JSON notification messages to every connected client.
Also exposes a plain HTTP GET /health endpoint (served over the same
socket) that reports the number of currently connected clients.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

MESSAGE_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}

_CHANNEL_SUBSCRIBERS_PATH = re.compile(r"^/channels/([^/]+)/subscribers$")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_message(msg_type: str, payload: dict, channel: str | None = None) -> dict:
    if msg_type not in MESSAGE_TYPES:
        raise ValueError(f"unsupported message type: {msg_type!r}")
    message = {"type": msg_type, "payload": payload, "timestamp": utc_timestamp()}
    if channel is not None:
        message["channel"] = channel
    return message


class ClientRegistry:
    """Thread-safe (asyncio-safe) registry of connected clients."""

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = asyncio.Lock()

    async def add(self, connection: ServerConnection) -> str:
        client_id = str(uuid.uuid4())
        async with self._lock:
            self._clients[client_id] = connection
        return client_id

    async def remove(self, client_id: str) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)

    async def count(self) -> int:
        async with self._lock:
            return len(self._clients)

    async def snapshot(self) -> list[tuple[str, ServerConnection]]:
        async with self._lock:
            return list(self._clients.items())

    async def get(self, client_id: str) -> ServerConnection | None:
        async with self._lock:
            return self._clients.get(client_id)


class ChannelRegistry:
    """Asyncio-safe registry of channel -> subscribed client id sets."""

    def __init__(self) -> None:
        self._channels: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            subs = self._channels.get(channel)
            if subs is None:
                return
            subs.discard(client_id)
            if not subs:
                del self._channels[channel]

    async def remove_client(self, client_id: str) -> None:
        async with self._lock:
            emptied = []
            for channel, subs in self._channels.items():
                subs.discard(client_id)
                if not subs:
                    emptied.append(channel)
            for channel in emptied:
                del self._channels[channel]

    async def channel_counts(self) -> dict[str, int]:
        async with self._lock:
            return {name: len(subs) for name, subs in self._channels.items()}

    async def subscribers(self, channel: str) -> list[str]:
        async with self._lock:
            return sorted(self._channels.get(channel, set()))


class NotificationServer:
    def __init__(self) -> None:
        self.registry = ClientRegistry()
        self.channels = ChannelRegistry()

    async def broadcast(
        self, payload: dict, msg_type: str = "broadcast", channel: str | None = None
    ) -> int:
        message = json.dumps(make_message(msg_type, payload, channel=channel))
        target_ids = set(await self.channels.subscribers(channel)) if channel is not None else None
        sent = 0
        for client_id, connection in await self.registry.snapshot():
            if target_ids is not None and client_id not in target_ids:
                continue
            try:
                await connection.send(message)
                sent += 1
            except ConnectionClosed:
                await self.registry.remove(client_id)
                await self.channels.remove_client(client_id)
        return sent

    async def send_direct(self, client_id: str, payload: dict) -> bool:
        connection = await self.registry.get(client_id)
        if connection is None:
            return False
        message = json.dumps(make_message("direct", payload))
        try:
            await connection.send(message)
            return True
        except ConnectionClosed:
            await self.registry.remove(client_id)
            return False

    async def handler(self, connection: ServerConnection) -> None:
        client_id = await self.registry.add(connection)
        try:
            await connection.send(
                json.dumps(
                    make_message("system", {"event": "connected", "client_id": client_id})
                )
            )
            async for raw in connection:
                await self._handle_incoming(client_id, raw)
        except ConnectionClosed:
            pass
        finally:
            await self.registry.remove(client_id)
            await self.channels.remove_client(client_id)

    async def _handle_incoming(self, client_id: str, raw: str | bytes) -> None:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            await self._send_error(client_id, "invalid JSON")
            return

        if not isinstance(data, dict):
            await self._send_error(client_id, "message must be a JSON object")
            return

        msg_type = data.get("type")
        payload = data.get("payload", {})
        channel = data.get("channel")

        if msg_type not in MESSAGE_TYPES:
            await self._send_error(client_id, f"unsupported message type: {msg_type!r}")
            return

        if msg_type == "subscribe":
            if not channel or not isinstance(channel, str):
                await self._send_error(client_id, "subscribe requires a 'channel' field")
                return
            await self.channels.subscribe(client_id, channel)
            await self._send_ack(client_id, "subscribed", channel)
        elif msg_type == "unsubscribe":
            if not channel or not isinstance(channel, str):
                await self._send_error(client_id, "unsubscribe requires a 'channel' field")
                return
            await self.channels.unsubscribe(client_id, channel)
            await self._send_ack(client_id, "unsubscribed", channel)
        elif msg_type == "broadcast":
            await self.broadcast(payload, channel=channel)
        elif msg_type == "direct":
            target_id = payload.get("client_id") if isinstance(payload, dict) else None
            if not target_id:
                await self._send_error(client_id, "direct message requires payload.client_id")
                return
            delivered = await self.send_direct(target_id, payload.get("payload", {}))
            if not delivered:
                await self._send_error(client_id, f"unknown client_id: {target_id!r}")
        elif msg_type == "system":
            # System messages from clients are acknowledged but not rebroadcast.
            connection = await self.registry.get(client_id)
            if connection is not None:
                await connection.send(
                    json.dumps(make_message("system", {"event": "ack", "received": payload}))
                )

    async def _send_error(self, client_id: str, error: str) -> None:
        connection = await self.registry.get(client_id)
        if connection is None:
            return
        try:
            await connection.send(
                json.dumps(make_message("system", {"event": "error", "message": error}))
            )
        except ConnectionClosed:
            await self.registry.remove(client_id)

    async def _send_ack(self, client_id: str, event: str, channel: str) -> None:
        connection = await self.registry.get(client_id)
        if connection is None:
            return
        try:
            await connection.send(
                json.dumps(make_message("system", {"event": event, "channel": channel}))
            )
        except ConnectionClosed:
            await self.registry.remove(client_id)
            await self.channels.remove_client(client_id)

    @staticmethod
    def _json_response(payload: dict) -> Response:
        body = json.dumps(payload).encode()
        headers = Headers([("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
        return Response(200, "OK", headers, body)

    async def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        if request.path == "/health":
            count = await self.registry.count()
            return self._json_response({"connected_clients": count})

        if request.path == "/channels":
            counts = await self.channels.channel_counts()
            return self._json_response({"channels": counts})

        match = _CHANNEL_SUBSCRIBERS_PATH.match(request.path)
        if match:
            channel = match.group(1)
            subscribers = await self.channels.subscribers(channel)
            return self._json_response({"channel": channel, "subscribers": subscribers})

        return None


def create_app() -> NotificationServer:
    return NotificationServer()


async def run_server(host: str = "localhost", port: int = 8765) -> None:
    app = create_app()
    async with serve(app.handler, host, port, process_request=app.process_request):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(run_server())
