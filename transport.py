"""Pluggable transport layer for the notification server.

The :class:`BaseTransport` abstract class defines the seam between the
transport-agnostic notification logic (routing, channels, persistence) in
:mod:`server` and the concrete wire protocol. New transport mechanisms
(SSE, polling, raw TCP, ...) are implemented by subclassing
``BaseTransport`` and registering the class in :func:`create_transport`
without touching the core notification logic.

The active transport is selected by the ``TRANSPORT`` environment variable
(default ``websocket``); ``WebSocketTransport`` is the default.
"""

import json
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import websockets
from websockets.asyncio.server import Server, serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def make_message(msg_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build a message dict following the required wire format."""
    return {"type": msg_type, "payload": payload, "timestamp": utc_now_iso()}


def dumps_message(msg_type: str, payload: Dict[str, Any]) -> str:
    """Serialize a message dict to JSON for sending."""
    return json.dumps(make_message(msg_type, payload))


class BaseTransport(ABC):
    """Abstract seam between notification logic and a wire protocol.

    A concrete transport is responsible for accepting connections, sending
    messages to clients and notifying the server about connect/disconnect
    events. It never decides what to send or where a message is routed —
    that stays in the transport-agnostic :class:`server.NotificationServer`.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port

    @abstractmethod
    async def start(self, server) -> None:
        """Begin accepting client connections for ``server``."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop accepting clients and release the listening socket."""

    @abstractmethod
    async def on_connect(self, server, connection) -> str:
        """Attach ``connection`` and return the assigned ``client_id``.

        The transport is free to assign ids and send protocol-specific
        welcome frames, but connection bookkeeping (registry, persisted
        state) is delegated to ``server``.
        """

    @abstractmethod
    async def on_disconnect(self, server, client_id: str) -> None:
        """Detach ``client_id`` after its connection ends."""

    @abstractmethod
    async def send_message(
        self, connection, msg_type: str, payload: Dict[str, Any]
    ) -> None:
        """Deliver a single JSON ``msg_type``/``payload`` message."""

    @abstractmethod
    def broadcast(self, connections, msg_type: str, payload: Dict[str, Any]) -> None:
        """Deliver a JSON message to every connection in ``connections``."""


class WebSocketTransport(BaseTransport):
    """WebSocket transport built on the ``websockets`` library.

    Accepts WebSocket connections, assigns each a unique id, delivers
    direct messages to individual connections and efficiently fans out
    broadcasts. The server's HTTP endpoints are mounted through the
    ``process_request`` hook of the underlying WebSocket server.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        super().__init__(host=host, port=port)
        self._server = None
        self._ws_server: Optional[Server] = None

    # ── lifecycle ────────────────────────────────────────────────────────

    async def start(self, server) -> None:
        """Start serving WebSocket connections, wiring HTTP through ``server``."""
        self._server = server
        self._ws_server = await serve(
            self._handle_connection,
            self.host,
            self.port,
            process_request=server.process_request,
        )
        if self._ws_server.sockets:
            self.port = self._ws_server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        """Shut the WebSocket server down and wait for handlers to finish."""
        if self._ws_server is not None:
            self._ws_server.close()
            await self._ws_server.wait_closed()
            self._ws_server = None

    # ── connection handling ──────────────────────────────────────────────

    async def _handle_connection(self, connection) -> None:
        """Keep the client alive until it disconnects, routing its messages."""
        server = self._server
        try:
            client_id = await self.on_connect(server, connection)
        except ConnectionClosed:
            return
        try:
            async for raw in connection:
                await server._on_message(client_id, raw)
        except ConnectionClosed:
            pass
        finally:
            await self.on_disconnect(server, client_id)

    async def on_connect(self, server, connection) -> str:
        """Assign a unique id, register the client and send a welcome."""
        client_id = str(uuid.uuid4())
        server.registry.add(client_id, connection)
        server.state.register(client_id)
        server._restore_membership(client_id)
        message = make_message(
            "system",
            {
                "message": "connected",
                "client_id": client_id,
                "connected_clients": server.registry.count(),
            },
        )
        try:
            await self.send_message(connection, "system", message["payload"])
        except ConnectionClosed:
            pass
        server.store.store_message(
            None, "system", message["payload"], message["timestamp"]
        )
        return client_id

    async def on_disconnect(self, server, client_id: str) -> None:
        """Remove the client from the registry and persisted state."""
        server.registry.remove(client_id)
        server.state.unregister(client_id)

    # ── messaging ────────────────────────────────────────────────────────

    async def send_message(
        self, connection, msg_type: str, payload: Dict[str, Any]
    ) -> None:
        """Send one JSON message on a single WebSocket connection."""
        await connection.send(dumps_message(msg_type, payload))

    def broadcast(self, connections, msg_type: str, payload: Dict[str, Any]) -> None:
        """Efficiently send one JSON message to many WebSocket connections."""
        websockets.broadcast(connections, dumps_message(msg_type, payload))


_TRANSPORTS = {
    "websocket": WebSocketTransport,
}


def create_transport(
    host: str = "127.0.0.1",
    port: int = 8765,
    name: Optional[str] = None,
) -> BaseTransport:
    """Build the transport selected by ``TRANSPORT`` (default ``websocket``).

    ``name`` overrides the environment variable when given.
    """
    name = (name or os.environ.get("TRANSPORT", "websocket")).strip().lower()
    try:
        transport_cls = _TRANSPORTS[name]
    except KeyError:
        raise ValueError(
            f"unknown transport: {name!r} (available: {sorted(_TRANSPORTS)})"
        )
    return transport_cls(host=host, port=port)
