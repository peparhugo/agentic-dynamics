"""WebSocket transport: the default, and current production, transport.

Wraps the `websockets` library server. Owns the WebSocket handshake/accept
loop, per-connection send/receive framing, disconnect detection, and
intercepting plain HTTP requests (GET /health, /channels, /messages, ...)
before the WebSocket handshake -- a feature specific to this library, which
is why HTTP routing decisions are delegated back to the registered
`http_handler` while the response-object plumbing stays here.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from notification_server.transport.base import BaseTransport


class WebSocketTransport(BaseTransport):
    def __init__(self) -> None:
        super().__init__()
        self._server: Server | None = None

    async def start(self, host: str, port: int) -> None:
        self._server = await serve(
            self._handler,
            host,
            port,
            process_request=self._process_request,
        )

    def stop(self) -> None:
        if self._server is not None:
            self._server.close()

    async def wait_closed(self) -> None:
        if self._server is not None:
            await self._server.wait_closed()

    @property
    def bound_port(self) -> int:
        if self._server is None:
            raise RuntimeError("transport has not been started")
        return self._server.sockets[0].getsockname()[1]

    async def send_message(self, connection: ServerConnection, message: dict) -> None:
        try:
            await connection.send(json.dumps(message))
        except ConnectionClosed:
            pass

    # -- WebSocket handling -----------------------------------------------

    async def _handler(self, websocket: ServerConnection) -> None:
        if self._connect_handler is not None:
            await self._connect_handler(websocket)
        try:
            async for raw_message in websocket:
                if self._message_handler is not None:
                    await self._message_handler(websocket, raw_message)
        except ConnectionClosed:
            pass
        finally:
            if self._disconnect_handler is not None:
                await self._disconnect_handler(websocket)

    # -- HTTP ---------------------------------------------------------

    async def _process_request(self, connection: ServerConnection, request: Request):
        """Intercept plain HTTP requests before the WebSocket handshake."""
        if self._http_handler is None:
            return None

        split = urlsplit(request.path)
        query = parse_qs(split.query)
        data = await self._http_handler(split.path, query)
        if data is None:
            return None
        return self._json_response(data)

    @staticmethod
    def _json_response(data: dict) -> Response:
        body = json.dumps(data).encode("utf-8")
        headers = Headers()
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
        return Response(200, "OK", headers, body)
