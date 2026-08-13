"""
WebSocket-based notification server.

Features:
- Accepts WebSocket connections and assigns each client a unique ID.
- Broadcasts a message to ALL connected clients.
- Routes direct messages to a single target client.
- Sends system messages (e.g. the assigned client id) to clients.
- Handles client disconnect with clean registry removal.
- Exposes a REST endpoint GET /health reporting the connected client count.
- Supports channel-based subscriptions: clients subscribe/unsubscribe to
  named channels and messages carrying a 'channel' field are delivered only
  to that channel's subscribers. Messages without a channel broadcast to all.
- Exposes REST endpoints GET /channels and GET /channels/{name}/subscribers.

All messages use the JSON envelope:
    {"type": str, "payload": dict, "timestamp": str}

Supported message types: 'broadcast', 'direct', 'system', 'subscribe',
'unsubscribe'.

Tech: websockets library, asyncio, thread-safe client registry.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import unquote

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

logger = logging.getLogger("notification_server")


def utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def build_message(msg_type: str, payload: dict) -> dict:
    """Build a message using the canonical JSON envelope."""
    return {"type": msg_type, "payload": payload, "timestamp": utc_now()}


def serialize(message: dict) -> str:
    """Serialize a message envelope to JSON text."""
    return json.dumps(message)


class ClientRegistry:
    """
    Thread-safe registry of connected WebSocket clients.

    Maps a unique client id to its websocket. Access is guarded by an
    asyncio.Lock so concurrent tasks can safely add/remove/query clients.
    """

    def __init__(self) -> None:
        self._clients: dict[str, ServerConnection] = {}
        self._lock = asyncio.Lock()

    async def add(self, client_id: str, websocket: ServerConnection) -> None:
        async with self._lock:
            self._clients[client_id] = websocket

    async def remove(self, client_id: str) -> None:
        async with self._lock:
            self._clients.pop(client_id, None)

    async def get(self, client_id: str) -> Optional[ServerConnection]:
        async with self._lock:
            return self._clients.get(client_id)

    async def count(self) -> int:
        async with self._lock:
            return len(self._clients)

    async def snapshot(self) -> dict[str, ServerConnection]:
        async with self._lock:
            return dict(self._clients)


class NotificationServer:
    """
    WebSocket notification server with an embedded REST /health endpoint.

    The /health endpoint is served by the same listener through
    websockets' ``process_request`` hook, so a single asyncio event loop
    handles both WebSocket and plain HTTP traffic.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.registry = ClientRegistry()
        self._channels: dict[str, set[str]] = {}
        self._channels_lock = asyncio.Lock()
        self._server: Optional[Server] = None
        self._id_counter = 0
        self._id_lock = asyncio.Lock()

    # ── Client id allocation ──────────────────────────────────────

    async def _next_id(self) -> str:
        async with self._id_lock:
            self._id_counter += 1
            return f"client-{self._id_counter}"

    # ── Channel subscriptions ─────────────────────────────────────

    async def subscribe(self, client_id: str, channel: str) -> None:
        """Subscribe a client to a named channel."""
        if not isinstance(channel, str) or not channel:
            return
        async with self._channels_lock:
            self._channels.setdefault(channel, set()).add(client_id)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        """Unsubscribe a client from a named channel."""
        if not isinstance(channel, str) or not channel:
            return
        async with self._channels_lock:
            subscribers = self._channels.get(channel)
            if subscribers is None:
                return
            subscribers.discard(client_id)
            if not subscribers:
                del self._channels[channel]

    async def channel_subscribers(self, channel: str) -> set[str]:
        """Return the set of client ids subscribed to a channel (may be empty)."""
        async with self._channels_lock:
            subscribers = self._channels.get(channel)
            return set(subscribers) if subscribers else set()

    async def channel_counts(self) -> dict[str, int]:
        """Return a mapping of active channel name to subscriber count."""
        async with self._channels_lock:
            return {name: len(subs) for name, subs in self._channels.items()}

    async def _remove_client_channels(self, client_id: str) -> None:
        """Remove a client from every channel, dropping channels left empty."""
        async with self._channels_lock:
            empty = [
                name
                for name, subscribers in self._channels.items()
                if client_id in subscribers
            ]
            for name in empty:
                subscribers = self._channels[name]
                subscribers.discard(client_id)
                if not subscribers:
                    del self._channels[name]

    # ── Sending helpers ───────────────────────────────────────────

    async def _send(self, websocket: ServerConnection, message: dict) -> bool:
        """Send a message envelope to a single websocket.

        Returns True on success and False if the connection is gone.
        """
        try:
            await websocket.send(serialize(message))
            return True
        except (ConnectionClosed, ConnectionError, OSError):
            return False

    async def broadcast(self, message: dict) -> None:
        """Deliver a message envelope to every connected client."""
        for client_id, websocket in (await self.registry.snapshot()).items():
            if not await self._send(websocket, message):
                await self.registry.remove(client_id)

    async def send_direct(self, client_id: str, message: dict) -> bool:
        """Deliver a message envelope to a single client.

        Returns True if the target was found and the message sent,
        otherwise False.
        """
        websocket = await self.registry.get(client_id)
        if websocket is None:
            return False
        delivered = await self._send(websocket, message)
        if not delivered:
            await self.registry.remove(client_id)
        return delivered

    async def send_to_channel(self, channel: str, message: dict) -> int:
        """Deliver a message envelope to every subscriber of a channel.

        Returns the number of clients the message was sent to.
        """
        snapshot = await self.registry.snapshot()
        delivered = 0
        for client_id in await self.channel_subscribers(channel):
            websocket = snapshot.get(client_id)
            if websocket is None:
                continue
            if await self._send(websocket, message):
                delivered += 1
            else:
                await self.registry.remove(client_id)
        return delivered

    @property
    async def client_count(self) -> int:
        return await self.registry.count()

    # ── Inbound client messages ───────────────────────────────────

    async def _handle_client_message(self, client_id: str, raw: str) -> None:
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            await self.send_direct(
                client_id, build_message("system", {"error": "invalid json"})
            )
            return

        msg_type = data.get("type")
        payload = data.get("payload")
        if not isinstance(msg_type, str):
            await self.send_direct(
                client_id, build_message("system", {"error": "malformed message"})
            )
            return
        if not isinstance(payload, dict):
            if msg_type in ("subscribe", "unsubscribe"):
                payload = {}
            else:
                await self.send_direct(
                    client_id,
                    build_message("system", {"error": "malformed message"}),
                )
                return

        if msg_type == "subscribe":
            channel = self._resolve_channel(data, payload)
            if channel is None:
                await self.send_direct(
                    client_id,
                    build_message(
                        "system", {"error": "subscribe requires a 'channel'"}
                    ),
                )
                return
            await self.subscribe(client_id, channel)
        elif msg_type == "unsubscribe":
            channel = self._resolve_channel(data, payload)
            if channel is None:
                await self.send_direct(
                    client_id,
                    build_message(
                        "system", {"error": "unsubscribe requires a 'channel'"}
                    ),
                )
                return
            await self.unsubscribe(client_id, channel)
        elif msg_type == "broadcast":
            channel = self._resolve_channel(data, payload)
            if channel is not None:
                await self.send_to_channel(channel, build_message("broadcast", payload))
            else:
                await self.broadcast(build_message("broadcast", payload))
        elif msg_type == "direct":
            target = payload.get("target")
            if not isinstance(target, str) or not target:
                await self.send_direct(
                    client_id,
                    build_message(
                        "system", {"error": "direct message requires a 'target'"}
                    ),
                )
                return
            await self.send_direct(target, build_message("direct", payload))
        elif msg_type == "system":
            # System messages are server-generated; ignore client attempts.
            return
        else:
            await self.send_direct(
                client_id,
                build_message("system", {"error": f"unknown type: {msg_type}"}),
            )

    @staticmethod
    def _resolve_channel(data: dict, payload: dict) -> Optional[str]:
        """Extract a channel name from a message, top-level or payload."""
        channel = data.get("channel")
        if isinstance(channel, str) and channel:
            return channel
        channel = payload.get("channel")
        if isinstance(channel, str) and channel:
            return channel
        return None

    # ── Per-connection handler ────────────────────────────────────

    async def handler(self, websocket: ServerConnection) -> None:
        """Handle a single WebSocket client connection."""
        client_id = await self._next_id()
        await self.registry.add(client_id, websocket)
        logger.info("client %s connected", client_id)
        try:
            await self._send(
                websocket,
                build_message("system", {"event": "connected", "client_id": client_id}),
            )
            async for raw in websocket:
                await self._handle_client_message(client_id, raw)
        except ConnectionClosed:
            pass
        finally:
            await self.registry.remove(client_id)
            await self._remove_client_channels(client_id)
            logger.info("client %s disconnected", client_id)

    # ── REST /health endpoint ─────────────────────────────────────

    def _json_response(
        self, body: dict, status: int = 200, reason: str = "OK"
    ) -> Response:
        encoded = json.dumps(body).encode("utf-8")
        headers = Headers(
            {
                "Content-Type": "application/json",
                "Content-Length": str(len(encoded)),
            }
        )
        return Response(status, reason, headers, encoded)

    async def _process_request(
        self, connection: ServerConnection, request: Request
    ) -> Optional[Response]:
        path = request.path
        if path == "/health":
            return self._json_response(
                {"status": "ok", "clients": await self.registry.count()}
            )
        if path == "/channels":
            return self._json_response({"channels": await self.channel_counts()})
        if path.startswith("/channels/") and path.endswith("/subscribers"):
            name = unquote(path[len("/channels/") : -len("/subscribers")])
            if name not in await self.channel_counts():
                return self._json_response(
                    {"error": "channel not found"}, status=404, reason="Not Found"
                )
            subscribers = sorted(await self.channel_subscribers(name))
            return self._json_response(
                {"channel": name, "subscribers": subscribers}
            )
        return None

    # ── Lifecycle ─────────────────────────────────────────────────

    async def start(self) -> None:
        """Bind the listener and start accepting connections."""
        if self._server is not None:
            return
        self._server = await serve(
            self.handler,
            self.host,
            self.port,
            process_request=self._process_request,
        )
        self.port = self.bound_port

    @property
    def bound_port(self) -> int:
        if self._server is not None and self._server.sockets:
            return self._server.sockets[0].getsockname()[1]
        return self.port

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.bound_port}"

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None


async def _run(host: str, port: int) -> None:
    server = NotificationServer(host, port)
    await server.start()
    print(f"Notification server listening on {server.url}")
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await server.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))
    asyncio.run(_run(host, port))


if __name__ == "__main__":
    main()
