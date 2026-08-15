"""Transport implementations for the notification server."""

from __future__ import annotations

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterable
from http import HTTPStatus
from typing import Any, Protocol
from urllib.parse import parse_qs, urlsplit

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response


class TransportApplication(Protocol):
    """Operations a transport needs from the notification core."""

    async def transport_connected(self, client_id: str) -> dict[str, Any]: ...

    async def transport_disconnected(self, client_id: str) -> None: ...

    async def handle_message(self, sender_id: str, raw_message: str | bytes) -> None: ...

    async def handle_http_request(
        self, path: str
    ) -> tuple[dict[str, Any], HTTPStatus] | None: ...


class BaseTransport(ABC):
    """Interface between a client transport and the notification core."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.application: TransportApplication | None = None

    def bind(self, application: TransportApplication) -> None:
        self.application = application

    async def start(self) -> None:
        """Start accepting clients, if the transport requires a listener."""

    async def stop(self) -> None:
        """Stop accepting clients and release transport resources."""

    async def serve_forever(self) -> None:
        """Keep a started transport alive until it is cancelled."""
        await asyncio.Future()

    @property
    def bound_port(self) -> int:
        raise RuntimeError("transport does not expose a bound port")

    @abstractmethod
    async def on_connect(self, connection: Any) -> str:
        """Register a newly connected transport client and return its ID."""

    @abstractmethod
    async def on_disconnect(self, client_id: str) -> None:
        """Remove a disconnected transport client."""

    @abstractmethod
    async def send_message(self, client_id: str, notification: dict[str, Any]) -> None:
        """Send one notification to one client."""

    @abstractmethod
    async def broadcast(
        self,
        notification: dict[str, Any],
        client_ids: Iterable[str] | None = None,
    ) -> None:
        """Send one notification to the selected clients, or all clients."""


class WebSocketTransport(BaseTransport):
    """WebSocket transport preserving the notification server's wire protocol."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        super().__init__(host, port)
        self._server: Server | None = None
        self._connections: dict[str, ServerConnection] = {}

    async def start(self) -> None:
        if self._server is not None:
            raise RuntimeError("transport is already running")
        self._server = await serve(
            self._handle_connection,
            self.host,
            self.port,
            process_request=self._process_request,
        )

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    @property
    def bound_port(self) -> int:
        if self._server is None or not self._server.sockets:
            raise RuntimeError("server is not running")
        return int(self._server.sockets[0].getsockname()[1])

    async def serve_forever(self) -> None:
        if self._server is None:
            raise RuntimeError("transport is not running")
        await self._server.serve_forever()

    async def _handle_connection(self, connection: ServerConnection) -> None:
        client_id = await self.on_connect(connection)
        try:
            async for raw_message in connection:
                assert self.application is not None
                await self.application.handle_message(client_id, raw_message)
        except ConnectionClosed:
            pass
        finally:
            if self._connections.get(client_id) is connection:
                await self.on_disconnect(client_id)

    async def on_connect(self, connection: ServerConnection) -> str:
        if self.application is None:
            raise RuntimeError("transport is not bound to an application")
        query = parse_qs(urlsplit(connection.request.path).query)
        requested_ids = query.get("client_id", [])
        client_id = (
            requested_ids[0]
            if len(requested_ids) == 1 and requested_ids[0]
            else str(uuid.uuid4())
        )
        welcome = await self.application.transport_connected(client_id)
        self._connections[client_id] = connection
        await self.send_message(client_id, welcome)
        return client_id

    async def on_disconnect(self, client_id: str) -> None:
        connection = self._connections.pop(client_id, None)
        if connection is None:
            return
        if self.application is not None:
            await self.application.transport_disconnected(client_id)

    async def send_message(self, client_id: str, notification: dict[str, Any]) -> None:
        connection = self._connections.get(client_id)
        if connection is None:
            return
        try:
            await connection.send(json.dumps(notification, separators=(",", ":")))
        except ConnectionClosed:
            await self.on_disconnect(client_id)

    async def broadcast(
        self,
        notification: dict[str, Any],
        client_ids: Iterable[str] | None = None,
    ) -> None:
        recipients = list(self._connections) if client_ids is None else list(client_ids)
        await asyncio.gather(
            *(self.send_message(client_id, notification) for client_id in recipients)
        )

    async def _process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        del connection
        if self.application is None:
            raise RuntimeError("transport is not bound to an application")
        result = await self.application.handle_http_request(request.path)
        if result is None:
            return None
        payload, status = result
        body = json.dumps(payload).encode("utf-8")
        headers = Headers(
            {
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
                "Connection": "close",
            }
        )
        return Response(status, status.phrase, headers, body)


Transport = BaseTransport

TRANSPORTS: dict[str, type[BaseTransport]] = {
    "websocket": WebSocketTransport,
    "ws": WebSocketTransport,
}


def register_transport(name: str, transport_type: type[BaseTransport]) -> None:
    """Register a transport type for config-driven selection."""
    TRANSPORTS[name.strip().lower()] = transport_type


def create_transport(name: str, host: str, port: int) -> BaseTransport:
    """Build a configured transport from the registry."""
    normalized_name = name.strip().lower()
    try:
        transport_type = TRANSPORTS[normalized_name]
    except KeyError as exc:
        raise ValueError(f"unsupported transport: {normalized_name}") from exc
    return transport_type(host, port)
