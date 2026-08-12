"""
WebSocket-based notification server.

Features:
- Accept WebSocket connections and assign each client a unique ID.
- Broadcast messages to all connected clients.
- Send direct and system messages to specific clients.
- Channel-based subscriptions: clients subscribe/unsubscribe to named
  channels and channel-tagged messages are routed only to subscribers.
- Clean removal of clients on disconnect.
- REST endpoints: GET /health, GET /channels, GET /channels/{name}/subscribers.

Message format (JSON): {type: str, payload: dict, timestamp: str}
Supported types: 'broadcast', 'direct', 'system', 'subscribe', 'unsubscribe'.
"""

import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone

import websockets
from aiohttp import web

DEFAULT_WS_HOST = "0.0.0.0"
DEFAULT_WS_PORT = 8765
DEFAULT_HTTP_HOST = "0.0.0.0"
DEFAULT_HTTP_PORT = 8080

VALID_TYPES = ("broadcast", "direct", "system", "subscribe", "unsubscribe")


def utcnow_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


class ClientRegistry:
    """Thread-safe registry of connected WebSocket clients.

    Guards its internal dictionary with a threading.Lock so it is safe to
    access from the asyncio loop as well as any worker thread (e.g. an HTTP
    handler running in a separate thread).
    """

    def __init__(self) -> None:
        self._clients: dict[str, object] = {}
        self._lock = threading.Lock()

    def add(self, client_id: str, websocket: object) -> None:
        with self._lock:
            self._clients[client_id] = websocket

    def remove(self, client_id: str) -> object | None:
        with self._lock:
            return self._clients.pop(client_id, None)

    def get(self, client_id: str) -> object | None:
        with self._lock:
            return self._clients.get(client_id)

    def snapshot(self) -> list[tuple[str, object]]:
        with self._lock:
            return list(self._clients.items())

    def count(self) -> int:
        with self._lock:
            return len(self._clients)


class ChannelRegistry:
    """Thread-safe registry of channel memberships.

    Maps a channel name to the set of client IDs subscribed to it. Guarded by a
    threading.Lock so it can be used from the asyncio loop and HTTP handlers.
    """

    def __init__(self) -> None:
        self._channels: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def subscribe(self, channel: str, client_id: str) -> None:
        with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, channel: str, client_id: str) -> None:
        with self._lock:
            members = self._channels.get(channel)
            if members is None:
                return
            members.discard(client_id)
            if not members:
                del self._channels[channel]

    def unsubscribe_all(self, client_id: str) -> None:
        """Remove a client from every channel it is subscribed to."""
        with self._lock:
            for channel in list(self._channels):
                members = self._channels[channel]
                members.discard(client_id)
                if not members:
                    del self._channels[channel]

    def members(self, channel: str) -> set[str]:
        with self._lock:
            return set(self._channels.get(channel, ()))

    def count(self, channel: str) -> int:
        with self._lock:
            return len(self._channels.get(channel, ()))

    def snapshot(self) -> dict[str, int]:
        """Return a mapping of channel name to subscriber count."""
        with self._lock:
            return {name: len(members) for name, members in self._channels.items()}


class NotificationServer:
    """Async notification server exposing a WebSocket endpoint and a
    REST health check, both running on the same asyncio event loop."""

    def __init__(self, registry: ClientRegistry | None = None,
                 channels: ChannelRegistry | None = None) -> None:
        self.registry = registry or ClientRegistry()
        self.channels = channels or ChannelRegistry()
        self._ws_server = None
        self._http_runner = None
        self._http_site = None
        self.ws_port = None
        self.http_port = None

    @staticmethod
    def make_message(msg_type: str, payload: dict) -> dict:
        if msg_type not in VALID_TYPES:
            raise ValueError(f"unsupported message type: {msg_type}")
        return {
            "type": msg_type,
            "payload": payload,
            "timestamp": utcnow_iso(),
        }

    @staticmethod
    def encode(message: dict) -> str:
        return json.dumps(message)

    async def broadcast(self, payload: dict, channel: str | None = None) -> int:
        """Send a 'broadcast' message to connected clients.

        When ``channel`` is given, the message is delivered only to clients
        subscribed to that channel. Otherwise it goes to every connected
        client. Returns the number of recipients.
        """
        message = self.make_message("broadcast", payload)
        if channel is not None:
            await self._send_to_channel(str(channel), message)
            return self.channels.count(str(channel))
        await self._send_to_all(message)
        return self.registry.count()

    async def send_direct(self, client_id: str, payload: dict) -> bool:
        """Send a 'direct' message to a specific client.

        Returns True if the client was connected, False otherwise.
        """
        message = self.make_message("direct", payload)
        return await self._send_to(client_id, message)

    async def send_system(self, client_id: str, payload: dict) -> bool:
        """Send a 'system' message to a specific client."""
        message = self.make_message("system", payload)
        return await self._send_to(client_id, message)

    async def _send_to(self, client_id: str, message: dict) -> bool:
        websocket = self.registry.get(client_id)
        if websocket is None:
            return False
        try:
            await websocket.send(self.encode(message))
            return True
        except Exception:
            self.registry.remove(client_id)
            return False

    async def _send_to_all(self, message: dict) -> None:
        data = self.encode(message)
        for client_id, websocket in self.registry.snapshot():
            try:
                await websocket.send(data)
            except Exception:
                self.registry.remove(client_id)

    async def _send_to_channel(self, channel: str, message: dict) -> None:
        data = self.encode(message)
        for client_id in self.channels.members(channel):
            websocket = self.registry.get(client_id)
            if websocket is None:
                self.channels.unsubscribe(channel, client_id)
                continue
            try:
                await websocket.send(data)
            except Exception:
                self.registry.remove(client_id)
                self.channels.unsubscribe(channel, client_id)

    async def handler(self, websocket, path: str | None = None) -> None:
        """Per-connection handler: registers the client, then relays messages."""
        client_id = str(uuid.uuid4())
        self.registry.add(client_id, websocket)
        await self.send_system(client_id, {"client_id": client_id})
        try:
            async for raw in websocket:
                await self._dispatch(client_id, raw)
        except websockets.ConnectionClosed:
            pass
        finally:
            self.registry.remove(client_id)
            self.channels.unsubscribe_all(client_id)

    async def _dispatch(self, client_id: str, raw: str) -> None:
        """Route an incoming client message based on its type."""
        try:
            message = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return
        msg_type = message.get("type")
        payload = message.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {"data": payload}
        if msg_type == "broadcast":
            channel = message.get("channel") or payload.get("channel")
            if channel is not None:
                await self.broadcast(payload, str(channel))
            else:
                await self.broadcast(payload)
        elif msg_type == "direct":
            target = payload.get("to")
            if target is not None:
                await self.send_direct(str(target), payload)
        elif msg_type == "system":
            await self.send_system(client_id, {"ack": msg_type})
        elif msg_type == "subscribe":
            channel = message.get("channel") or payload.get("channel")
            if channel is not None:
                self.channels.subscribe(str(channel), client_id)
        elif msg_type == "unsubscribe":
            channel = message.get("channel") or payload.get("channel")
            if channel is not None:
                self.channels.unsubscribe(str(channel), client_id)

    async def start(self, ws_host: str = DEFAULT_WS_HOST, ws_port: int = DEFAULT_WS_PORT,
                    http_host: str = DEFAULT_HTTP_HOST, http_port: int = DEFAULT_HTTP_PORT) -> None:
        """Start the WebSocket server and the HTTP health endpoint."""
        self._ws_server = await websockets.serve(self.handler, ws_host, ws_port)
        self.ws_port = self._ws_server.sockets[0].getsockname()[1]

        http_app = web.Application()
        http_app.router.add_get("/health", self._health_handler)
        http_app.router.add_get("/channels", self._channels_handler)
        http_app.router.add_get("/channels/{name}/subscribers", self._channel_subscribers_handler)
        self._http_runner = web.AppRunner(http_app)
        await self._http_runner.setup()
        self._http_site = web.TCPSite(self._http_runner, http_host, http_port)
        await self._http_site.start()
        self.http_port = self._http_site._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._ws_server is not None:
            self._ws_server.close()
            await self._ws_server.wait_closed()
        if self._http_runner is not None:
            await self._http_runner.cleanup()

    async def _health_handler(self, request):
        return web.json_response({"clients": self.registry.count()})

    async def _channels_handler(self, request):
        snapshot = self.channels.snapshot()
        return web.json_response({
            "channels": [
                {"name": name, "subscribers": count}
                for name, count in snapshot.items()
            ],
        })

    async def _channel_subscribers_handler(self, request):
        name = request.match_info["name"]
        subscribers = sorted(self.channels.members(name))
        return web.json_response({
            "name": name,
            "subscribers": subscribers,
        })

    async def serve_forever(self) -> None:
        """Block forever, serving both endpoints."""
        stop = asyncio.Event()
        await stop.wait()


async def main() -> None:
    server = NotificationServer()
    await server.start()
    print(
        f"WebSocket server listening on ws://{DEFAULT_WS_HOST}:{server.ws_port} "
        f"and health on http://{DEFAULT_HTTP_HOST}:{server.http_port}"
    )
    await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
