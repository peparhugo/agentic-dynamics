"""
WebSocket-based notification server with REST health endpoint.
Handles client connections, message broadcasting, and client lifecycle.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Set
from threading import Lock

import websockets
from aiohttp import web


class ClientRegistry:
    """Thread-safe registry of connected WebSocket clients with channel subscriptions."""

    def __init__(self):
        self._clients: Dict[str, Any] = {}
        self._subscriptions: Dict[str, Set[str]] = {}
        self._client_channels: Dict[str, Set[str]] = {}
        self._lock = Lock()

    def add(self, client_id: str, websocket: Any) -> None:
        """Add a client to the registry."""
        with self._lock:
            self._clients[client_id] = websocket
            self._client_channels[client_id] = set()

    def remove(self, client_id: str) -> None:
        """Remove a client from the registry."""
        with self._lock:
            self._clients.pop(client_id, None)
            channels = self._client_channels.pop(client_id, set())
            for channel in channels:
                if channel in self._subscriptions:
                    self._subscriptions[channel].discard(client_id)

    def get(self, client_id: str) -> Any | None:
        """Get a specific client."""
        with self._lock:
            return self._clients.get(client_id)

    def get_all(self) -> Dict[str, Any]:
        """Get all connected clients."""
        with self._lock:
            return dict(self._clients)

    def get_count(self) -> int:
        """Get count of connected clients."""
        with self._lock:
            return len(self._clients)

    def subscribe(self, client_id: str, channel: str) -> bool:
        """Subscribe a client to a channel. Returns True if subscription succeeded."""
        with self._lock:
            if client_id not in self._clients:
                return False
            if channel not in self._subscriptions:
                self._subscriptions[channel] = set()
            self._subscriptions[channel].add(client_id)
            self._client_channels[client_id].add(channel)
            return True

    def unsubscribe(self, client_id: str, channel: str) -> bool:
        """Unsubscribe a client from a channel. Returns True if unsubscription succeeded."""
        with self._lock:
            if client_id not in self._client_channels:
                return False
            if channel not in self._client_channels[client_id]:
                return False
            self._client_channels[client_id].discard(channel)
            if channel in self._subscriptions:
                self._subscriptions[channel].discard(client_id)
            return True

    def get_channel_subscribers(self, channel: str) -> Set[str]:
        """Get all client IDs subscribed to a channel."""
        with self._lock:
            return set(self._subscriptions.get(channel, set()))

    def get_channels(self) -> Dict[str, int]:
        """Get all active channels and their subscriber counts."""
        with self._lock:
            return {
                channel: len(subscribers)
                for channel, subscribers in self._subscriptions.items()
                if subscribers
            }

    def get_client_channels(self, client_id: str) -> Set[str]:
        """Get all channels a client is subscribed to."""
        with self._lock:
            return set(self._client_channels.get(client_id, set()))


class NotificationServer:
    """WebSocket notification server with broadcast capabilities."""

    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.registry = ClientRegistry()
        self.server = None
        self.http_runner = None
        self.http_site = None

    async def handle_client(self, websocket: Any, path: str = "") -> None:
        """Handle a new WebSocket connection."""
        client_id = str(uuid.uuid4())
        self.registry.add(client_id, websocket)

        try:
            await websocket.send(json.dumps({
                "type": "system",
                "payload": {
                    "message": "Connected to notification server",
                    "client_id": client_id
                },
                "timestamp": datetime.utcnow().isoformat()
            }))

            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._process_message(data, client_id)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "type": "system",
                        "payload": {"error": "Invalid JSON"},
                        "timestamp": datetime.utcnow().isoformat()
                    }))
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.registry.remove(client_id)

    async def _process_message(self, data: dict, sender_id: str) -> None:
        """Process incoming message and route accordingly."""
        msg_type = data.get("type", "broadcast")
        payload = data.get("payload", {})

        if msg_type == "broadcast":
            await self.broadcast(payload, sender_id)
        elif msg_type == "direct":
            target_id = payload.get("target_id")
            if target_id:
                await self.send_direct(target_id, payload)
        elif msg_type == "subscribe":
            channel = payload.get("channel")
            if channel:
                await self._handle_subscribe(sender_id, channel)
        elif msg_type == "unsubscribe":
            channel = payload.get("channel")
            if channel:
                await self._handle_unsubscribe(sender_id, channel)
        elif msg_type == "system":
            pass

    async def _handle_subscribe(self, client_id: str, channel: str) -> None:
        """Handle client subscription to a channel."""
        success = self.registry.subscribe(client_id, channel)
        websocket = self.registry.get(client_id)
        if websocket:
            message = json.dumps({
                "type": "system",
                "payload": {
                    "action": "subscribed" if success else "subscription_failed",
                    "channel": channel,
                    "success": success
                },
                "timestamp": datetime.utcnow().isoformat()
            })
            try:
                await websocket.send(message)
            except websockets.exceptions.ConnectionClosed:
                self.registry.remove(client_id)

    async def _handle_unsubscribe(self, client_id: str, channel: str) -> None:
        """Handle client unsubscription from a channel."""
        success = self.registry.unsubscribe(client_id, channel)
        websocket = self.registry.get(client_id)
        if websocket:
            message = json.dumps({
                "type": "system",
                "payload": {
                    "action": "unsubscribed" if success else "unsubscription_failed",
                    "channel": channel,
                    "success": success
                },
                "timestamp": datetime.utcnow().isoformat()
            })
            try:
                await websocket.send(message)
            except websockets.exceptions.ConnectionClosed:
                self.registry.remove(client_id)

    async def broadcast(self, payload: dict, sender_id: str | None = None) -> None:
        """Broadcast a message to clients. Routes to channel subscribers if channel specified."""
        channel = payload.get("channel")

        message = json.dumps({
            "type": "broadcast",
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat()
        })

        disconnected = []

        if channel:
            target_clients = self.registry.get_channel_subscribers(channel)
        else:
            target_clients = set(self.registry.get_all().keys())

        clients = self.registry.get_all()
        for client_id in target_clients:
            websocket = clients.get(client_id)
            if websocket:
                try:
                    await websocket.send(message)
                except websockets.exceptions.ConnectionClosed:
                    disconnected.append(client_id)

        for client_id in disconnected:
            self.registry.remove(client_id)

    async def send_direct(self, target_id: str, payload: dict) -> None:
        """Send a direct message to a specific client."""
        websocket = self.registry.get(target_id)
        if websocket:
            message = json.dumps({
                "type": "direct",
                "payload": payload,
                "timestamp": datetime.utcnow().isoformat()
            })
            try:
                await websocket.send(message)
            except websockets.exceptions.ConnectionClosed:
                self.registry.remove(target_id)

    async def health_handler(self, request: web.Request) -> web.Response:
        """Health check endpoint that returns connected client count."""
        return web.json_response({
            "status": "healthy",
            "connected_clients": self.registry.get_count()
        })

    async def channels_handler(self, request: web.Request) -> web.Response:
        """List all active channels and their subscriber counts."""
        channels = self.registry.get_channels()
        return web.json_response({
            "channels": channels,
            "total_channels": len(channels)
        })

    async def channel_subscribers_handler(self, request: web.Request) -> web.Response:
        """List subscriber IDs for a specific channel."""
        channel_name = request.match_info.get("channel")
        if not channel_name:
            return web.json_response({"error": "channel name required"}, status=400)

        subscribers = self.registry.get_channel_subscribers(channel_name)
        return web.json_response({
            "channel": channel_name,
            "subscribers": sorted(list(subscribers)),
            "subscriber_count": len(subscribers)
        })

    async def start(self) -> None:
        """Start both WebSocket and HTTP servers."""
        self.server = await websockets.serve(
            self.handle_client,
            self.host,
            self.port
        )

        app = web.Application()
        app.router.add_get("/health", self.health_handler)
        app.router.add_get("/channels", self.channels_handler)
        app.router.add_get("/channels/{channel}", self.channel_subscribers_handler)

        self.http_runner = web.AppRunner(app)
        await self.http_runner.setup()
        self.http_site = web.TCPSite(self.http_runner, self.host, self.port + 1000)
        await self.http_site.start()

    async def stop(self) -> None:
        """Stop both WebSocket and HTTP servers."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        if self.http_site:
            await self.http_site.stop()
        if self.http_runner:
            await self.http_runner.cleanup()


async def main():
    """Run the notification server."""
    server = NotificationServer(host="0.0.0.0", port=8765)
    await server.start()
    print(f"WebSocket server running on ws://0.0.0.0:8765")
    print(f"Health endpoint at http://0.0.0.0:9765/health")

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        print("Shutting down...")
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
