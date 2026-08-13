"""Pluggable transport layer for the notification server.

BaseTransport defines the small delivery contract NotificationServer relies
on to move clients and messages: on_connect(), on_disconnect(),
send_message(), and broadcast(). The core server only ever talks to a
transport through those four methods, so a new wire protocol (SSE,
long-polling, raw TCP, ...) can be plugged in without touching the routing
logic in notification_server.py. WebSocketTransport is the only transport
implemented so far, and is the default.
"""

from __future__ import annotations

import abc
import asyncio
import json
import os
import re
import urllib.parse
import uuid
from typing import Any, Awaitable, Callable

from websockets.asyncio.server import ServerConnection
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from messages import make_message

_CHANNEL_SUBSCRIBERS_PATH = re.compile(r"^/channels/([^/]+)/subscribers$")

StaleClientHook = Callable[[str], Awaitable[None]]


class ClientRegistry:
    """Asyncio-safe registry mapping client ids to their live connection object."""

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def add(self, connection: Any) -> str:
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

    async def snapshot(self) -> list[tuple[str, Any]]:
        async with self._lock:
            return list(self._clients.items())

    async def get(self, client_id: str) -> Any | None:
        async with self._lock:
            return self._clients.get(client_id)


class BaseTransport(abc.ABC):
    """Contract every pluggable transport must satisfy."""

    def __init__(self, on_stale_client: StaleClientHook | None = None) -> None:
        self.registry = ClientRegistry()
        self._on_stale_client = on_stale_client

    @abc.abstractmethod
    async def on_connect(self, *args: Any, **kwargs: Any) -> str:
        """Register a newly arrived client connection and return its client id."""

    @abc.abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Tear down bookkeeping for a client that has gone away."""

    @abc.abstractmethod
    async def send_message(self, client_id: str, message: dict) -> bool:
        """Deliver `message` to a single client. Returns whether it was delivered."""

    @abc.abstractmethod
    async def broadcast(self, message: dict, target_ids: set[str] | None = None) -> int:
        """Deliver `message` to all clients, or only those in `target_ids` if given."""


class WebSocketTransport(BaseTransport):
    """Serves clients over WebSocket connections (the `websockets` library)."""

    def __init__(self, server: Any, on_stale_client: StaleClientHook | None = None) -> None:
        super().__init__(on_stale_client=on_stale_client)
        self.server = server

    async def on_connect(self, connection: ServerConnection) -> str:
        return await self.registry.add(connection)

    async def on_disconnect(self, client_id: str) -> None:
        await self.registry.remove(client_id)

    async def send_message(self, client_id: str, message: dict) -> bool:
        connection = await self.registry.get(client_id)
        if connection is None:
            return False
        try:
            await connection.send(json.dumps(message))
            return True
        except ConnectionClosed:
            await self.registry.remove(client_id)
            return False

    async def broadcast(self, message: dict, target_ids: set[str] | None = None) -> int:
        encoded = json.dumps(message)
        sent = 0
        for client_id, connection in await self.registry.snapshot():
            if target_ids is not None and client_id not in target_ids:
                continue
            try:
                await connection.send(encoded)
                sent += 1
            except ConnectionClosed:
                await self.registry.remove(client_id)
                if self._on_stale_client is not None:
                    await self._on_stale_client(client_id)
        return sent

    async def handler(self, connection: ServerConnection) -> None:
        client_id = await self.on_connect(connection)
        if self.server.redis_backbone is not None:
            await self.server.redis_backbone.set_client_state(client_id)
        try:
            await connection.send(
                json.dumps(make_message("system", {"event": "connected", "client_id": client_id}))
            )
            async for raw in connection:
                await self.server._handle_incoming(client_id, raw)
        except ConnectionClosed:
            pass
        finally:
            await self.on_disconnect(client_id)
            await self.server.channels.remove_client(client_id)
            if self.server.redis_backbone is not None:
                await self.server.redis_backbone.clear_client_state(client_id)

    @staticmethod
    def _json_response(payload: dict) -> Response:
        body = json.dumps(payload).encode()
        headers = Headers([("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
        return Response(200, "OK", headers, body)

    async def process_request(self, connection: ServerConnection, request: Request) -> Response | None:
        parsed = urllib.parse.urlsplit(request.path)
        path = parsed.path

        if path == "/health":
            count = await self.registry.count()
            return self._json_response({"connected_clients": count})

        if path == "/channels":
            counts = await self.server.channels.channel_counts()
            return self._json_response({"channels": counts})

        if path == "/messages":
            query = urllib.parse.parse_qs(parsed.query)
            limit = _parse_int(query.get("limit", ["50"])[0], default=50)
            offset = _parse_int(query.get("offset", ["0"])[0], default=0)
            if self.server.message_store is None:
                return self._json_response({"messages": [], "limit": limit, "offset": offset})
            messages = await self.server.message_store.list_messages(limit=limit, offset=offset)
            return self._json_response({"messages": messages, "limit": limit, "offset": offset})

        match = _CHANNEL_SUBSCRIBERS_PATH.match(path)
        if match:
            channel = match.group(1)
            subscribers = await self.server.channels.subscribers(channel)
            return self._json_response({"channel": channel, "subscribers": subscribers})

        return None


def _parse_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


TRANSPORTS: dict[str, type[BaseTransport]] = {
    "websocket": WebSocketTransport,
}


def create_transport(server: Any, on_stale_client: StaleClientHook | None = None) -> BaseTransport:
    """Build the transport selected by the TRANSPORT env var (default: websocket)."""
    name = os.environ.get("TRANSPORT", "websocket").lower()
    try:
        transport_cls = TRANSPORTS[name]
    except KeyError:
        raise ValueError(f"unsupported transport: {name!r}") from None
    return transport_cls(server, on_stale_client=on_stale_client)
