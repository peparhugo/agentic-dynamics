"""
WebSocket-based notification server built on the `websockets` library.

Features:
- Accepts WebSocket connections from clients.
- Assigns each client a unique ID on connect.
- Broadcasts a message to ALL connected clients.
- Sends direct messages to a specific client.
- Handles client disconnect with clean removal from the registry.
- REST endpoint GET /health returns the connected client count.

Message format (JSON):
    {type: str, payload: dict, timestamp: str}

Supported types: 'broadcast', 'direct', 'system'.

Thread-safety: asyncio runs everything on a single event loop, so the
client registry needs no locking; plain dict reads/writes are safe by
construction.
"""

import asyncio
import json
from datetime import datetime, timezone

from websockets.asyncio.server import ServerConnection, serve
from websockets.http11 import Headers, Response

SUPPORTED_TYPES = {"broadcast", "direct", "system"}
WELCOME_TIMEOUT = 5.0


def make_message(msg_type: str, payload: dict) -> dict:
    """Build a message dict in the canonical wire format."""
    if msg_type not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported message type: {msg_type!r}")
    return {
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class NotificationServer:
    """Async WebSocket notification server with an in-memory client registry."""

    def __init__(self) -> None:
        # client_id -> ServerConnection. No locking needed: asyncio runs all
        # access to this dict on a single event loop, so reads and writes are
        # thread-safe by construction.
        self._clients: dict[str, ServerConnection] = {}
        self._next_id = 1

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def client_ids(self) -> list[str]:
        return list(self._clients)

    def _issue_id(self) -> str:
        client_id = str(self._next_id)
        self._next_id += 1
        return client_id

    # ── Outbound send helpers ───────────────────────────────────

    async def _send(self, connection: ServerConnection, message: dict) -> None:
        await connection.send(json.dumps(message))

    async def broadcast(self, payload: dict) -> int:
        """Send a 'broadcast' message to every connected client.

        Returns the number of clients the message was delivered to.
        """
        message = make_message("broadcast", payload)
        failed: list[str] = []
        for client_id, connection in list(self._clients.items()):
            try:
                await self._send(connection, message)
            except Exception:
                failed.append(client_id)
        for client_id in failed:
            self._clients.pop(client_id, None)
        return self.client_count

    async def send_direct(self, client_id: str, payload: dict) -> bool:
        """Send a 'direct' message to a single client. Returns success."""
        connection = self._clients.get(client_id)
        if connection is None:
            return False
        message = make_message("direct", payload)
        try:
            await self._send(connection, message)
            return True
        except Exception:
            self._clients.pop(client_id, None)
            return False

    # ── Connection lifecycle ────────────────────────────────────

    async def handle_connection(self, websocket: ServerConnection) -> None:
        """Per-connection coroutine: register, welcome, serve, clean up."""
        client_id = self._issue_id()
        self._clients[client_id] = websocket
        try:
            await self._send(
                websocket,
                make_message(
                    "system",
                    {"event": "connected", "client_id": client_id},
                ),
            )
            async for raw in websocket:
                try:
                    data = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    await self._send(
                        websocket,
                        make_message(
                            "system",
                            {"event": "error", "error": "invalid JSON message"},
                        ),
                    )
                    continue
                if not isinstance(data, dict) or data.get("type") not in SUPPORTED_TYPES:
                    await self._send(
                        websocket,
                        make_message(
                            "system",
                            {"event": "error", "error": "unsupported message"},
                        ),
                    )
                    continue
                payload = data.get("payload") or {}
                msg_type = data["type"]
                if msg_type == "broadcast":
                    await self.broadcast(payload)
                elif msg_type == "direct":
                    target = payload.get("target_id")
                    if target is None:
                        await self._send(
                            websocket,
                            make_message(
                                "system",
                                {"event": "error", "error": "direct message missing target_id"},
                            ),
                        )
                    elif not await self.send_direct(target, payload):
                        await self._send(
                            websocket,
                            make_message(
                                "system",
                                {"event": "error", "error": f"unknown client {target!r}"},
                            ),
                        )
        finally:
            # Clean removal regardless of how the connection ended.
            self._clients.pop(client_id, None)

    # ── HTTP (REST) handling ────────────────────────────────────

    def process_request(self, connection: ServerConnection, request) -> Response | None:
        """Handle plain HTTP requests (e.g. GET /health) before WS upgrade."""
        if request.path == "/health" and request.headers.get("Upgrade", "").lower() != "websocket":
            body = json.dumps(
                {"clients": self.client_count, "status": "ok"}
            ).encode("utf-8")
            headers = Headers(
                {
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body)),
                }
            )
            return Response(200, "OK", headers, body)
        return None

    # ── Lifecycle ───────────────────────────────────────────────

    async def start(self, host: str = "localhost", port: int = 8765) -> None:
        self._server = await serve(
            self.handle_connection,
            host,
            port,
            process_request=self.process_request,
        )

    async def stop(self) -> None:
        self._clients.clear()
        self._server.close()
        await self._server.wait_closed()


async def run_server(host: str = "localhost", port: int = 8765) -> None:
    """Run the notification server until interrupted."""
    server = NotificationServer()
    await server.start(host, port)
    print(f"Notification server listening on ws://{host}:{port}")
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        pass
