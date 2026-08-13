"""WebSocket transport: delivers messages over the `websockets` library, and
exposes the server's plain HTTP GET endpoints (`/health`, `/channels`, ...)
on the same port via the `process_request` handshake hook, so no extra web
framework is needed. This is the default transport, and the only one that
currently exists -- SSE, long-polling, or raw TCP transports would each live
in their own module implementing the same `BaseTransport` interface.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from http import HTTPStatus
from typing import Any, Iterable
from urllib.parse import parse_qs, unquote

import websockets
from websockets.asyncio.server import ServerConnection
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response
from websockets.datastructures import Headers

from .messages import Message, MessageValidationError, utc_now_iso
from .transport import BaseTransport

logger = logging.getLogger("notification_server")

HEALTH_PATH = "/health"
CHANNELS_PATH = "/channels"
MESSAGES_PATH = "/messages"
HISTORY_PATH = "/history"
CHANNEL_SUBSCRIBERS_RE = re.compile(r"^/channels/([^/]+)/subscribers$")

DEFAULT_MESSAGES_LIMIT = 50
MAX_MESSAGES_LIMIT = 500


class WebSocketTransport(BaseTransport):
    def __init__(self) -> None:
        super().__init__()
        self._connections: dict[str, ServerConnection] = {}
        self._lock = threading.Lock()

    # -- BaseTransport ----------------------------------------------------

    async def on_connect(self, client_id: str, connection: Any) -> None:
        with self._lock:
            self._connections[client_id] = connection

    async def on_disconnect(self, client_id: str) -> None:
        with self._lock:
            self._connections.pop(client_id, None)

    async def send_message(self, client_id: str, message: Message) -> None:
        with self._lock:
            connection = self._connections.get(client_id)
        if connection is None:
            return
        try:
            await connection.send(message.to_json())
        except ConnectionClosed:
            pass

    async def broadcast(self, client_ids: Iterable[str] | None, message: Message) -> None:
        with self._lock:
            if client_ids is None:
                connections = list(self._connections.values())
            else:
                connections = [self._connections[cid] for cid in client_ids if cid in self._connections]
        websockets.broadcast(connections, message.to_json())

    # -- HTTP endpoints served over the same port via serve()'s
    #    process_request hook --------------------------------------------

    def _json_response(self, data: Any) -> Response:
        body = json.dumps(data).encode()
        headers = Headers()
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
        return Response(HTTPStatus.OK.value, HTTPStatus.OK.phrase, headers, body)

    @staticmethod
    def _parse_int(raw: str | None, default: int, minimum: int, maximum: int | None = None) -> int:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return default
        if value < minimum:
            return default
        if maximum is not None and value > maximum:
            return maximum
        return value

    async def process_request(self, connection: ServerConnection, request: Request) -> Response | None:
        """Serve a few plain HTTP GET endpoints; let everything else proceed
        to the normal WebSocket handshake."""
        server = self.server
        path, _, query_string = request.path.partition("?")
        if path == HEALTH_PATH:
            return self._json_response(await server.health_payload())
        if path == CHANNELS_PATH:
            return self._json_response(await server.channels_payload())
        match = CHANNEL_SUBSCRIBERS_RE.match(path)
        if match:
            channel = unquote(match.group(1))
            return self._json_response(await server.state.channel_subscribers(channel))
        if path == MESSAGES_PATH:
            query = parse_qs(query_string)
            limit = self._parse_int(
                query.get("limit", [None])[0], DEFAULT_MESSAGES_LIMIT, minimum=1, maximum=MAX_MESSAGES_LIMIT
            )
            offset = self._parse_int(query.get("offset", [None])[0], 0, minimum=0)
            return self._json_response(server.store.fetch(limit=limit, offset=offset))
        if path == HISTORY_PATH:
            query = parse_qs(query_string)
            channel = query.get("channel", [None])[0]
            since = query.get("since", [None])[0]
            limit = self._parse_int(
                query.get("limit", [None])[0], DEFAULT_MESSAGES_LIMIT, minimum=1, maximum=MAX_MESSAGES_LIMIT
            )
            return self._json_response(server.history_payload(channel=channel, since=since, limit=limit))
        return None

    # -- WebSocket connection lifecycle -----------------------------------

    async def handler(self, websocket: ServerConnection) -> None:
        server = self.server
        client_id = server.registry.add(websocket)
        await self.on_connect(client_id, websocket)
        await server.state.add_client(client_id)
        logger.info("client connected: %s", client_id)
        try:
            await server.send_to(
                client_id,
                Message(type="system", payload={"event": "connected", "client_id": client_id}, timestamp=utc_now_iso()),
            )
            async for raw in websocket:
                try:
                    message = Message.from_json(raw)
                except MessageValidationError as exc:
                    await server.send_error(client_id, str(exc))
                    continue
                await server.route(client_id, message)
        except ConnectionClosed:
            pass
        finally:
            server.registry.remove(client_id)
            server.channel_registry.unsubscribe_all(client_id)
            await server.state.remove_client(client_id)
            await server.state.unsubscribe_all(client_id)
            await self.on_disconnect(client_id)
            logger.info("client disconnected: %s", client_id)
            await self.broadcast(
                None,
                Message(type="system", payload={"event": "disconnected", "client_id": client_id}, timestamp=utc_now_iso()),
            )
