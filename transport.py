"""
Pluggable transport layer for the notification server.

BaseTransport is the boundary between the core notification logic
(NotificationServer: client/channel registries, the Redis backbone,
message persistence, and message routing) and the mechanics of a
specific wire protocol. A transport only needs to know how to notice a
client arriving or leaving and how to deliver a string to one or many
client ids -- it has no opinion about what a "broadcast" or "channel"
means, so NotificationServer never has to change when a new transport
is added.

WebSocketTransport is the only transport implemented today and is the
default. Additional transports (Server-Sent Events, long-polling, raw
TCP, ...) can be added later as further BaseTransport subclasses,
registered in `_TRANSPORTS` below, without touching notification_server.py.

Transport is selected via the TRANSPORT environment variable (see
`create_transport`).
"""

from __future__ import annotations

import abc
import json
import logging
import os
import re
import urllib.parse
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, Optional

import websockets
from websockets.asyncio.server import serve

if TYPE_CHECKING:
    from notification_server import NotificationServer

logger = logging.getLogger("notification_server.transport")

TRANSPORT_ENV_VAR = "TRANSPORT"


@dataclass
class Client:
    client_id: str
    connection: "websockets.asyncio.server.ServerConnection"


class BaseTransport(abc.ABC):
    """Interface a transport must implement to plug into NotificationServer.

    A transport is bound to exactly one NotificationServer via `bind()`
    before use; `create_server`/`NotificationServer.__init__` do this
    automatically. Concrete transports call back into the bound server's
    `handle_connect`/`handle_disconnect`/`handle_incoming` hooks as their
    own connection/message events happen -- those hooks contain the core,
    transport-agnostic notification logic.
    """

    def __init__(self) -> None:
        self.notification_server: Optional["NotificationServer"] = None

    def bind(self, notification_server: "NotificationServer") -> None:
        self.notification_server = notification_server

    @abc.abstractmethod
    async def on_connect(self, client_id: str, connection) -> None:
        """Record a newly established connection for client_id, then run
        the core server's connect-time bookkeeping."""

    @abc.abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Release a connection for client_id, then run the core server's
        disconnect-time bookkeeping."""

    @abc.abstractmethod
    async def send_message(self, client_id: str, message: str) -> bool:
        """Deliver `message` to a single client. Returns False if that
        client is unreachable (unknown id, closed connection, etc)."""

    @abc.abstractmethod
    async def broadcast(self, client_ids: list[str], message: str) -> int:
        """Deliver `message` to every id in client_ids. Returns how many
        deliveries succeeded."""

    def serve(self, host: str, port: int):
        """Bind an actual network listener for this transport and return
        an awaitable async-context-manager server object, the way
        websockets.serve() does. Not part of the core on_connect/
        on_disconnect/send_message/broadcast contract -- only needed by
        transports that create_server() should bind directly to a
        host:port."""
        raise NotImplementedError(f"{type(self).__name__} does not support serve()")


class WebSocketTransport(BaseTransport):
    """The original (and default) transport: one raw WebSocket connection
    per client, plus a handful of plain HTTP GET endpoints served on the
    same port before the WebSocket handshake."""

    async def on_connect(self, client_id: str, connection) -> None:
        ns = self.notification_server
        ns.registry.add(Client(client_id=client_id, connection=connection))
        await ns.handle_connect(client_id)

    async def on_disconnect(self, client_id: str) -> None:
        ns = self.notification_server
        ns.registry.remove(client_id)
        await ns.handle_disconnect(client_id)

    async def send_message(self, client_id: str, message: str) -> bool:
        client = self.notification_server.registry.get(client_id)
        if client is None:
            return False
        try:
            await client.connection.send(message)
            return True
        except websockets.exceptions.ConnectionClosed:
            return False

    async def broadcast(self, client_ids: list[str], message: str) -> int:
        sent = 0
        for client_id in client_ids:
            if await self.send_message(client_id, message):
                sent += 1
        return sent

    async def handler(self, connection) -> None:
        client_id = str(uuid.uuid4())
        await self.on_connect(client_id, connection)
        logger.info("client connected: %s", client_id)
        try:
            async for raw_message in connection:
                await self.notification_server.handle_incoming(client_id, raw_message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.on_disconnect(client_id)
            logger.info("client disconnected: %s", client_id)

    async def process_request(self, connection, request):
        """Serve GET /health, /channels, /channels/{name}/subscribers, and
        /messages as plain HTTP responses before the WebSocket handshake;
        let every other path continue as a normal upgrade attempt."""
        ns = self.notification_server
        path = request.path.split("?", 1)[0]

        if path == "/health":
            body = json.dumps({"connected_clients": ns.registry.count()})
            return self._json_response(connection, body)

        if path == "/channels":
            body = json.dumps({"channels": ns.channels.channels()})
            return self._json_response(connection, body)

        match = re.fullmatch(r"/channels/([^/]+)/subscribers", path)
        if match:
            channel = urllib.parse.unquote(match.group(1))
            body = json.dumps({
                "channel": channel,
                "subscribers": ns.channels.subscribers(channel),
            })
            return self._json_response(connection, body)

        if path == "/messages":
            limit, offset = self._parse_pagination(request.path)
            rows = await ns.message_store.get_messages(limit=limit, offset=offset)
            for row in rows:
                row["payload"] = json.loads(row["payload"])
            body = json.dumps({"messages": rows, "limit": limit, "offset": offset})
            return self._json_response(connection, body)

        return None

    @staticmethod
    def _parse_pagination(full_path: str) -> tuple[int, int]:
        query = urllib.parse.urlsplit(full_path).query
        params = urllib.parse.parse_qs(query)
        limit = int(params.get("limit", ["50"])[0])
        offset = int(params.get("offset", ["0"])[0])
        return limit, offset

    @staticmethod
    def _json_response(connection, body: str):
        response = connection.respond(HTTPStatus.OK, body)
        response.headers["Content-Type"] = "application/json"
        return response

    def serve(self, host: str, port: int):
        return serve(self.handler, host, port, process_request=self.process_request)


_TRANSPORTS: dict[str, type[BaseTransport]] = {
    "websocket": WebSocketTransport,
}


def create_transport(name: Optional[str] = None) -> BaseTransport:
    """Build the transport selected by `name`, falling back to the
    TRANSPORT environment variable, defaulting to WebSocketTransport."""
    name = (name or os.environ.get(TRANSPORT_ENV_VAR) or "websocket").lower()
    try:
        transport_cls = _TRANSPORTS[name]
    except KeyError:
        raise ValueError(
            f"unsupported transport: {name!r} (available: {', '.join(sorted(_TRANSPORTS))})"
        ) from None
    return transport_cls()
