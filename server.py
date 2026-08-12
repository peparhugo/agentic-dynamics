"""WebSocket-based notification server.

Features
--------
* Assigns each connected client a unique ID on connect.
* Broadcasts messages to all connected clients.
* Delivers direct messages to a single target client.
* Sends system messages for lifecycle / error events.
* Cleans up clients on disconnect.
* Exposes a REST endpoint ``GET /health`` returning the connected client count.

Message format
--------------
All messages are JSON objects::

    {"type": "broadcast" | "direct" | "system", "payload": {...}, "timestamp": "..."}
"""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
import threading
from datetime import datetime, timezone
from urllib.parse import urlsplit

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Headers, Response

logger = logging.getLogger("notifyserver")

VALID_TYPES = ("broadcast", "direct", "system")


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def make_message(msg_type: str, payload: dict) -> dict:
    """Build a message dict using the canonical message format."""
    if msg_type not in VALID_TYPES:
        raise ValueError(f"unsupported message type: {msg_type!r}")
    return {
        "type": msg_type,
        "payload": payload,
        "timestamp": utc_now_iso(),
    }


class ClientRegistry:
    """Thread-safe registry mapping client IDs to WebSocket connections.

    All mutating and reading operations are guarded by a ``threading.Lock``,
    so the registry is safe to touch from any thread. Operations never block
    on I/O, so holding the lock is harmless to the event loop.
    """

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = threading.Lock()

    def add(self, client_id: str, ws: ServerConnection) -> None:
        with self._lock:
            self._clients[client_id] = ws

    def remove(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def get(self, client_id: str) -> ServerConnection | None:
        with self._lock:
            return self._clients.get(client_id)

    def count(self) -> int:
        with self._lock:
            return len(self._clients)

    def snapshot(self) -> dict[str, ServerConnection]:
        """Return a shallow copy so callers can iterate without the lock."""
        with self._lock:
            return dict(self._clients)

    def __len__(self) -> int:
        return self.count()


class NotificationServer:
    """WebSocket notification server built on the ``websockets`` library."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.registry = ClientRegistry()
        self._ids = itertools.count(1)
        self._server = None

    # ── lifecycle ──────────────────────────────────────────────

    async def start(self) -> None:
        """Start accepting connections on ``host:port``."""
        if self._server is not None:
            return
        self._server = await serve(
            self._client_handler,
            self.host,
            self.port,
            process_request=self._process_request,
        )

    async def stop(self) -> None:
        """Close the listening socket and stop accepting connections."""
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    @property
    def sockets(self):
        return self._server.sockets if self._server is not None else None

    @property
    def bound_port(self) -> int:
        """Return the actual bound port (handles ``port=0``)."""
        if self.sockets is None:
            return self.port
        return self.sockets[0].getsockname()[1]

    # ── message helpers ────────────────────────────────────────

    @staticmethod
    def _encode(msg: dict) -> str:
        return json.dumps(msg)

    async def _send(self, ws: ServerConnection, msg_type: str, payload: dict) -> None:
        await ws.send(self._encode(make_message(msg_type, payload)))

    # ── public API ─────────────────────────────────────────────

    async def broadcast(self, payload: dict) -> int:
        """Send a ``broadcast`` message to every connected client.

        Returns the number of clients the message was delivered to.
        """
        message = self._encode(make_message("broadcast", payload))
        sent = 0
        for client_id, ws in self.registry.snapshot().items():
            try:
                await ws.send(message)
                sent += 1
            except ConnectionClosed:
                self.registry.remove(client_id)
        return sent

    async def send_direct(self, target_id: str, payload: dict) -> bool:
        """Send a ``direct`` message to a single client.

        Returns ``False`` if the target client is not connected.
        """
        ws = self.registry.get(target_id)
        if ws is None:
            return False
        message = self._encode(make_message("direct", payload))
        try:
            await ws.send(message)
        except ConnectionClosed:
            self.registry.remove(target_id)
            return False
        return True

    async def client_count(self) -> int:
        """Return the number of currently connected clients."""
        return self.registry.count()

    # ── connection handling ────────────────────────────────────

    async def _client_handler(self, ws: ServerConnection) -> None:
        client_id = f"client-{next(self._ids)}"
        self.registry.add(client_id, ws)
        logger.info("client connected: %s", client_id)
        try:
            await self._send(
                ws, "system", {"event": "connected", "client_id": client_id}
            )
            async for raw in ws:
                await self._handle_message(client_id, ws, raw)
        except ConnectionClosed:
            pass
        finally:
            self.registry.remove(client_id)
            logger.info("client disconnected: %s", client_id)

    async def _handle_message(
        self, client_id: str, ws: ServerConnection, raw: str
    ) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await self._send(
                ws,
                "system",
                {"client_id": client_id, "error": "invalid JSON message"},
            )
            return

        if not isinstance(data, dict):
            await self._send(
                ws,
                "system",
                {"client_id": client_id, "error": "message must be a JSON object"},
            )
            return

        msg_type = data.get("type")
        payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}

        if msg_type == "broadcast":
            await self.broadcast(payload)
        elif msg_type == "direct":
            target = payload.get("to")
            if not isinstance(target, str) or not target:
                await self._send(
                    ws,
                    "system",
                    {
                        "client_id": client_id,
                        "error": "direct message requires a string 'to' target",
                    },
                )
                return
            forwarded = dict(payload)
            forwarded["from"] = client_id
            if not await self.send_direct(target, forwarded):
                await self._send(
                    ws,
                    "system",
                    {
                        "client_id": client_id,
                        "error": f"unknown target client: {target}",
                    },
                )
        else:
            await self._send(
                ws,
                "system",
                {
                    "client_id": client_id,
                    "error": f"unsupported message type: {msg_type!r}",
                },
            )

    # ── REST endpoint ──────────────────────────────────────────

    async def _process_request(self, connection, request) -> Response | None:
        """Serve ``GET /health`` over plain HTTP; pass everything else through."""
        path = urlsplit(request.path).path
        if path.rstrip("/") == "/health":
            return await self._health_response()
        return None

    async def _health_response(self) -> Response:
        body = json.dumps(
            {
                "status": "ok",
                "clients": self.registry.count(),
                "timestamp": utc_now_iso(),
            }
        ).encode("utf-8")
        headers = Headers()
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
        return Response(200, "OK", headers, body)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    server = NotificationServer()
    await server.start()
    print(
        f"WebSocket notification server listening on "
        f"ws://{server.host}:{server.bound_port}"
    )
    try:
        await asyncio.Future()  # run forever
    finally:
        await server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
