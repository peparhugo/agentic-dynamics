"""
WebSocket-based notification server built on the `websockets` library.

Features:
- Accepts WebSocket connections from clients.
- Assigns each client a unique ID on connect.
- Broadcasts a message to ALL connected clients.
- Sends direct messages to a specific client.
- Supports named channels: clients subscribe/unsubscribe dynamically
  and channel-scoped messages are delivered only to subscribers.
- Handles client disconnect with clean removal from the registry.
- REST endpoints: GET /health, GET /channels, GET /channels/{name}/subscribers.

Message format (JSON):
    {type: str, payload: dict, timestamp: str}

Supported types: 'broadcast', 'direct', 'system', 'subscribe', 'unsubscribe'.

Channel routing:
- A message with a top-level 'channel' field (or one inside its payload)
  is delivered only to clients subscribed to that channel.
- A message without a 'channel' field broadcasts to all connected clients.

Thread-safety: asyncio runs everything on a single event loop, so the
client registry needs no locking; plain dict reads/writes are safe by
construction.
"""

import asyncio
import json
from datetime import datetime, timezone
from urllib.parse import urlsplit

from websockets.asyncio.server import ServerConnection, serve
from websockets.http11 import Headers, Response

SUPPORTED_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}
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
        # channel name -> set of client_ids subscribed to that channel.
        self._channels: dict[str, set[str]] = {}
        self._next_id = 1

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def client_ids(self) -> list[str]:
        return list(self._clients)

    @property
    def channel_names(self) -> list[str]:
        return list(self._channels)

    # ── Channel subscriptions ─────────────────────────────────

    def subscribe(self, client_id: str, channel: str) -> None:
        """Subscribe a client to a named channel."""
        if not channel:
            raise ValueError("channel name must be non-empty")
        self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        """Unsubscribe a client from a named channel."""
        subs = self._channels.get(channel)
        if subs is None:
            return
        subs.discard(client_id)
        if not subs:
            del self._channels[channel]

    def subscribed_channels(self, client_id: str) -> list[str]:
        """List the channels a client is currently subscribed to."""
        return [
            name
            for name, subs in self._channels.items()
            if client_id in subs
        ]

    def channel_subscribers(self, channel: str) -> list[str]:
        """Return the IDs of clients subscribed to a channel."""
        return sorted(self._channels.get(channel, set()))

    def channels_info(self) -> list[dict]:
        """Return info for all active channels: name and subscriber count."""
        return [
            {"name": name, "subscribers": len(subs)}
            for name, subs in sorted(self._channels.items())
        ]

    def _drop_client(self, client_id: str) -> None:
        """Remove a client from the registry and all channel subscriptions."""
        self._clients.pop(client_id, None)
        if not self._channels:
            return
        for name, subs in list(self._channels.items()):
            subs.discard(client_id)
            if not subs:
                del self._channels[name]

    def _issue_id(self) -> str:
        client_id = str(self._next_id)
        self._next_id += 1
        return client_id

    # ── Outbound send helpers ───────────────────────────────────

    async def _send(self, connection: ServerConnection, message: dict) -> None:
        await connection.send(json.dumps(message))

    async def broadcast(self, payload: dict, channel: str | None = None) -> int:
        """Send a 'broadcast' message to clients.

        When ``channel`` is given, the message is delivered only to clients
        subscribed to that channel; otherwise it goes to every connected
        client. Returns the number of clients the message was delivered to.
        """
        message = make_message("broadcast", payload)
        if channel is None:
            targets = list(self._clients.items())
        else:
            targets = [
                (client_id, self._clients[client_id])
                for client_id in self._channels.get(channel, set())
                if client_id in self._clients
            ]
        failed: list[str] = []
        for client_id, connection in targets:
            try:
                await self._send(connection, message)
            except Exception:
                failed.append(client_id)
        for client_id in failed:
            self._drop_client(client_id)
        return len(targets) - len(failed)

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
                    channel = data.get("channel") or payload.get("channel")
                    await self.broadcast(payload, channel=channel)
                elif msg_type == "subscribe":
                    channel = data.get("channel") or payload.get("channel")
                    if not channel:
                        await self._send(
                            websocket,
                            make_message(
                                "system",
                                {"event": "error", "error": "subscribe missing channel"},
                            ),
                        )
                    else:
                        self.subscribe(client_id, channel)
                elif msg_type == "unsubscribe":
                    channel = data.get("channel") or payload.get("channel")
                    if not channel:
                        await self._send(
                            websocket,
                            make_message(
                                "system",
                                {"event": "error", "error": "unsubscribe missing channel"},
                            ),
                        )
                    else:
                        self.unsubscribe(client_id, channel)
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
            self._drop_client(client_id)

    # ── HTTP (REST) handling ────────────────────────────────────

    def _json_response(self, status: int, data: dict) -> Response:
        body = json.dumps(data).encode("utf-8")
        headers = Headers(
            {
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
            }
        )
        return Response(status, "OK" if status == 200 else "Not Found", headers, body)

    def process_request(self, connection: ServerConnection, request) -> Response | None:
        """Handle plain HTTP requests (e.g. GET /health) before WS upgrade."""
        if request.headers.get("Upgrade", "").lower() == "websocket":
            return None

        path = urlsplit(request.path).path
        if path == "/health":
            return self._json_response(
                200, {"clients": self.client_count, "status": "ok"}
            )
        if path == "/channels":
            return self._json_response(
                200, {"channels": self.channels_info()}
            )
        if path.startswith("/channels/") and path.endswith("/subscribers"):
            name = path[len("/channels/"):-len("/subscribers")]
            return self._json_response(
                200,
                {"channel": name, "subscribers": self.channel_subscribers(name)},
            )
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
