"""
WebSocket-based notification server with Redis pub/sub and SQLite persistence.

Features:
- Accept WebSocket connections and assign unique IDs
- Broadcast messages to all connected clients
- Handle client disconnections
- REST endpoint for health status
- Thread-safe client registry
- Redis pub/sub for distributed message delivery
- SQLite for message persistence
- Client connection state stored in Redis
"""

import asyncio
import json
import uuid
import os
from datetime import datetime, timezone
from typing import Dict, Any
import threading

from aiohttp import web
import websockets
from websockets import ConnectionClosed

from database import MessageDatabase
from redis_pubsub import RedisPublisher, RedisSubscriber, ClientConnectionState


class ClientRegistry:
    """Thread-safe registry of connected clients."""

    def __init__(self):
        self._clients: Dict[str, Any] = {}
        self._subscriptions: Dict[str, set] = {}
        self._lock = threading.RLock()

    def register(self, client_id: str, websocket: Any) -> None:
        """Register a new client."""
        with self._lock:
            self._clients[client_id] = websocket
            self._subscriptions[client_id] = set()

    def unregister(self, client_id: str) -> None:
        """Unregister a client."""
        with self._lock:
            self._clients.pop(client_id, None)
            self._subscriptions.pop(client_id, None)

    def get_client(self, client_id: str) -> Any | None:
        """Get a specific client."""
        with self._lock:
            return self._clients.get(client_id)

    def get_all_clients(self) -> Dict[str, Any]:
        """Get all connected clients."""
        with self._lock:
            return dict(self._clients)

    def get_count(self) -> int:
        """Get the number of connected clients."""
        with self._lock:
            return len(self._clients)

    def subscribe(self, client_id: str, channel: str) -> None:
        """Subscribe a client to a channel."""
        with self._lock:
            if client_id in self._subscriptions:
                self._subscriptions[client_id].add(channel)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        """Unsubscribe a client from a channel."""
        with self._lock:
            if client_id in self._subscriptions:
                self._subscriptions[client_id].discard(channel)

    def get_channel_subscribers(self, channel: str) -> list:
        """Get all clients subscribed to a channel."""
        with self._lock:
            return [
                client_id for client_id, channels in self._subscriptions.items()
                if channel in channels
            ]

    def get_active_channels(self) -> Dict[str, int]:
        """Get all active channels and their subscriber counts."""
        with self._lock:
            channel_counts = {}
            for channels in self._subscriptions.values():
                for channel in channels:
                    channel_counts[channel] = channel_counts.get(channel, 0) + 1
            return channel_counts


class NotificationServer:
    """WebSocket notification server."""

    def __init__(self, host: str = "localhost", ws_port: int = 8765, http_port: int = 8080,
                 redis_url: str | None = None, database_url: str | None = None):
        self.host = host
        self.ws_port = ws_port
        self.http_port = http_port
        self.registry = ClientRegistry()
        self.http_app = web.Application()

        # Initialize Redis and database
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.db_path = database_url or os.getenv("DATABASE_URL", "messages.db")

        self.db = MessageDatabase(self.db_path)
        self.publisher = RedisPublisher(self.redis_url)
        self.subscriber = RedisSubscriber(self.redis_url)
        self.connection_state = ClientConnectionState(self.redis_url)

        self._setup_http_routes()

    def _setup_http_routes(self) -> None:
        """Setup HTTP REST routes."""
        self.http_app.router.add_get("/health", self._health_handler)
        self.http_app.router.add_get("/channels", self._channels_handler)
        self.http_app.router.add_get("/channels/{name}/subscribers", self._channel_subscribers_handler)
        self.http_app.router.add_get("/messages", self._messages_handler)

    async def _health_handler(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({
            "status": "healthy",
            "connected_clients": self.registry.get_count(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def _channels_handler(self, request: web.Request) -> web.Response:
        """List active channels and subscriber counts."""
        channels = self.registry.get_active_channels()
        return web.json_response({
            "channels": channels,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def _channel_subscribers_handler(self, request: web.Request) -> web.Response:
        """List subscriber IDs for a specific channel."""
        channel_name = request.match_info["name"]
        subscribers = self.registry.get_channel_subscribers(channel_name)
        return web.json_response({
            "channel": channel_name,
            "subscribers": subscribers,
            "count": len(subscribers),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def _messages_handler(self, request: web.Request) -> web.Response:
        """Get stored messages from database."""
        try:
            limit = int(request.query.get("limit", 50))
            offset = int(request.query.get("offset", 0))
            channel = request.query.get("channel")

            # Validate limits
            limit = min(max(limit, 1), 1000)
            offset = max(offset, 0)

            messages = self.db.get_messages(channel=channel, limit=limit, offset=offset)
            total_count = self.db.get_message_count(channel=channel)

            return web.json_response({
                "messages": messages,
                "limit": limit,
                "offset": offset,
                "total": total_count,
                "count": len(messages),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except (ValueError, TypeError):
            return web.json_response({
                "error": "Invalid query parameters",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }, status=400)

    async def _handle_client(self, websocket: Any, path: str) -> None:
        """Handle a new WebSocket client connection."""
        client_id = str(uuid.uuid4())
        self.registry.register(client_id, websocket)

        # Store connection state in Redis
        try:
            self.connection_state.set_connected(client_id, {
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "status": "connected",
            })
        except Exception:
            pass

        try:
            # Send welcome message
            welcome = {
                "type": "system",
                "payload": {
                    "message": "Connected",
                    "client_id": client_id,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await websocket.send(json.dumps(welcome))

            # Broadcast connection event
            await self.broadcast({
                "type": "system",
                "payload": {
                    "message": f"Client {client_id} connected",
                    "client_count": self.registry.get_count(),
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }, exclude=client_id)

            # Handle incoming messages
            async for message in websocket:
                await self._handle_message(client_id, message)

        except ConnectionClosed:
            pass
        finally:
            self.registry.unregister(client_id)

            # Remove connection state from Redis
            try:
                self.connection_state.remove_connected(client_id)
            except Exception:
                pass

            # Broadcast disconnection event
            await self.broadcast({
                "type": "system",
                "payload": {
                    "message": f"Client {client_id} disconnected",
                    "client_count": self.registry.get_count(),
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    async def _handle_message(self, client_id: str, raw_message: str) -> None:
        """Handle an incoming message from a client."""
        try:
            message = json.loads(raw_message)
            msg_type = message.get("type")

            if msg_type == "subscribe":
                channel = message.get("payload", {}).get("channel")
                if channel:
                    self.registry.subscribe(client_id, channel)

            elif msg_type == "unsubscribe":
                channel = message.get("payload", {}).get("channel")
                if channel:
                    self.registry.unsubscribe(client_id, channel)

            elif msg_type == "broadcast":
                channel = message.get("channel")
                await self.broadcast({
                    "type": "broadcast",
                    "payload": message.get("payload", {}),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }, exclude=client_id, channel=channel)

            elif msg_type == "direct":
                target_id = message.get("payload", {}).get("target_id")
                if target_id:
                    await self.send_direct(target_id, {
                        "type": "direct",
                        "payload": {
                            "from": client_id,
                            "message": message.get("payload", {}).get("message"),
                        },
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

        except json.JSONDecodeError:
            pass

    async def broadcast(self, message: dict, exclude: str | None = None, channel: str | None = None) -> None:
        """Broadcast a message to all connected clients or to a specific channel."""
        # Store message in database
        msg_type = message.get("type", "unknown")
        payload = message.get("payload", {})
        timestamp = message.get("timestamp", datetime.now(timezone.utc).isoformat())
        broadcast_channel = channel or "broadcast"

        try:
            self.db.store_message(broadcast_channel, msg_type, payload, timestamp)
        except Exception:
            pass

        # Publish to Redis
        try:
            await self.publisher.publish(broadcast_channel, message)
        except Exception:
            pass

        if channel:
            # Send only to subscribers of the channel
            subscribers = self.registry.get_channel_subscribers(channel)
            target_clients = {
                client_id: self.registry.get_client(client_id)
                for client_id in subscribers
                if self.registry.get_client(client_id) is not None
            }
        else:
            # Broadcast to all clients
            target_clients = self.registry.get_all_clients()

        if not target_clients:
            return

        message_json = json.dumps(message)
        tasks = []

        for client_id, websocket in target_clients.items():
            if exclude and client_id == exclude:
                continue
            tasks.append(self._send_safe(websocket, message_json))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def send_direct(self, client_id: str, message: dict) -> None:
        """Send a direct message to a specific client."""
        # Store message in database
        msg_type = message.get("type", "unknown")
        payload = message.get("payload", {})
        timestamp = message.get("timestamp", datetime.now(timezone.utc).isoformat())
        channel = f"direct:{client_id}"

        try:
            self.db.store_message(channel, msg_type, payload, timestamp)
        except Exception:
            pass

        # Publish to Redis
        try:
            await self.publisher.publish(channel, message)
        except Exception:
            pass

        client = self.registry.get_client(client_id)
        if client:
            await self._send_safe(client, json.dumps(message))

    async def _send_safe(self, websocket: Any, message: str) -> None:
        """Safely send a message, handling closed connections."""
        try:
            await websocket.send(message)
        except ConnectionClosed:
            pass

    async def start(self) -> None:
        """Start both WebSocket and HTTP servers."""
        # Initialize Redis connections
        try:
            await self.publisher.connect()
            await self.subscriber.connect()
            await self.subscriber.start()
        except Exception:
            pass

        # Start WebSocket server
        ws_server = await websockets.serve(self._handle_client, self.host, self.ws_port)

        # Start HTTP server
        runner = web.AppRunner(self.http_app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.http_port)
        await site.start()

        print(f"WebSocket server running on ws://{self.host}:{self.ws_port}")
        print(f"HTTP server running on http://{self.host}:{self.http_port}")

        return ws_server, runner

    async def shutdown(self) -> None:
        """Shutdown the server and cleanup resources."""
        try:
            await self.subscriber.stop()
            await self.publisher.disconnect()
            await self.subscriber.disconnect()
        except Exception:
            pass

        try:
            self.connection_state.close()
        except Exception:
            pass


async def main():
    """Run the notification server."""
    server = NotificationServer(host="0.0.0.0", ws_port=8765, http_port=8080)
    await server.start()
    await asyncio.Future()  # Run forever


if __name__ == "__main__":
    asyncio.run(main())
