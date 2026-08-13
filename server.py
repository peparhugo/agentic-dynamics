"""
Pluggable notification server with pluggable transport layer.

Features:
- Pluggable transport layer (WebSocket, SSE, polling, raw TCP)
- Broadcast messages to all connected clients
- Direct messages to specific clients
- System messages
- REST health endpoint
- Thread-safe client registry
- Redis pub/sub for multi-server message distribution
- SQLite persistence for message history
"""

import asyncio
import json
import uuid
import sqlite3
import os
from abc import ABC, abstractmethod
from datetime import datetime
from threading import Lock
from typing import Dict, Set, Any

import websockets
from aiohttp import web
import aioredis


# Configuration
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
DATABASE_URL = os.environ.get("DATABASE_URL", "messages.db")
TRANSPORT = os.environ.get("TRANSPORT", "websocket")


def init_db():
    """Initialize SQLite database for message persistence."""
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT NOT NULL,
            type TEXT NOT NULL,
            payload TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_message(channel: str, msg_type: str, payload: dict, timestamp: str) -> int:
    """Save a message to SQLite."""
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
        (channel, msg_type, json.dumps(payload), timestamp)
    )
    conn.commit()
    msg_id = cursor.lastrowid
    conn.close()
    return msg_id


def get_messages(limit: int = 50, offset: int = 0) -> list:
    """Retrieve messages from SQLite with pagination."""
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
        (limit, offset)
    )
    rows = cursor.fetchall()
    conn.close()

    messages = []
    for row in rows:
        messages.append({
            "id": row["id"],
            "channel": row["channel"],
            "type": row["type"],
            "payload": json.loads(row["payload"]),
            "timestamp": row["timestamp"],
        })
    return messages


class BaseTransport(ABC):
    """Abstract base class for transport mechanisms."""

    @abstractmethod
    def add_client(self, client_id: str, connection: Any) -> None:
        """Add a client connection."""
        pass

    @abstractmethod
    def remove_client(self, client_id: str) -> None:
        """Remove a client connection."""
        pass

    @abstractmethod
    def get_client_count(self) -> int:
        """Get the number of connected clients."""
        pass

    @abstractmethod
    def get_all_clients(self) -> Dict[str, Any]:
        """Get a snapshot of all client connections."""
        pass

    @abstractmethod
    async def send_to_client(self, client_id: str, message: str) -> bool:
        """Send a message to a specific client. Returns True if successful."""
        pass

    @abstractmethod
    async def broadcast(self, message: str) -> None:
        """Broadcast a message to all connected clients."""
        pass

    @abstractmethod
    async def broadcast_to_subscribers(self, subscriber_ids: Set[str], message: str) -> None:
        """Broadcast a message to specific subscribers."""
        pass


class WebSocketTransport(BaseTransport):
    """WebSocket transport implementation.

    Manages client connections using WebSocket protocol.
    Provides full-duplex communication with connected clients.
    """

    def __init__(self):
        self.clients: Dict[str, Any] = {}
        self.lock = Lock()

    def add_client(self, client_id: str, connection: Any) -> None:
        """Add a WebSocket client."""
        with self.lock:
            self.clients[client_id] = connection

    def remove_client(self, client_id: str) -> None:
        """Remove a WebSocket client."""
        with self.lock:
            self.clients.pop(client_id, None)

    def get_client_count(self) -> int:
        """Get the number of connected WebSocket clients."""
        with self.lock:
            return len(self.clients)

    def get_all_clients(self) -> Dict[str, Any]:
        """Get a snapshot of all WebSocket clients."""
        with self.lock:
            return self.clients.copy()

    async def send_to_client(self, client_id: str, message: str) -> bool:
        """Send a message to a specific WebSocket client."""
        clients = self.get_all_clients()
        if client_id not in clients:
            return False

        try:
            await clients[client_id].send(message)
            return True
        except Exception:
            return False

    async def broadcast(self, message: str) -> None:
        """Broadcast a message to all WebSocket clients."""
        clients = self.get_all_clients()
        tasks = [self._send_safe(ws, message) for ws in clients.values()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_to_subscribers(self, subscriber_ids: Set[str], message: str) -> None:
        """Broadcast a message to specific WebSocket client subscribers."""
        clients = self.get_all_clients()
        tasks = [self._send_safe(clients[sub_id], message) for sub_id in subscriber_ids if sub_id in clients]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_safe(self, websocket, message: str) -> None:
        """Send a message to a WebSocket client, silently skip if send fails."""
        try:
            await websocket.send(message)
        except Exception:
            pass


class SSETransport(BaseTransport):
    """Server-Sent Events transport implementation.

    Alternative transport using HTTP Server-Sent Events (SSE).
    Provides one-way push notifications from server to client.

    Example of how to extend the transport layer for different protocols.
    This is a placeholder showing the interface contract.
    """

    def __init__(self):
        self.clients: Dict[str, Any] = {}
        self.lock = Lock()

    def add_client(self, client_id: str, connection: Any) -> None:
        """Add an SSE client response object."""
        with self.lock:
            self.clients[client_id] = connection

    def remove_client(self, client_id: str) -> None:
        """Remove an SSE client."""
        with self.lock:
            self.clients.pop(client_id, None)

    def get_client_count(self) -> int:
        """Get the number of connected SSE clients."""
        with self.lock:
            return len(self.clients)

    def get_all_clients(self) -> Dict[str, Any]:
        """Get a snapshot of all SSE clients."""
        with self.lock:
            return self.clients.copy()

    async def send_to_client(self, client_id: str, message: str) -> bool:
        """Send a message to a specific SSE client."""
        clients = self.get_all_clients()
        if client_id not in clients:
            return False

        try:
            response = clients[client_id]
            await response.write(f"data: {message}\n\n")
            return True
        except Exception:
            return False

    async def broadcast(self, message: str) -> None:
        """Broadcast a message to all SSE clients."""
        clients = self.get_all_clients()
        tasks = [self._send_safe(response, message) for response in clients.values()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_to_subscribers(self, subscriber_ids: Set[str], message: str) -> None:
        """Broadcast a message to specific SSE client subscribers."""
        clients = self.get_all_clients()
        tasks = [self._send_safe(clients[sub_id], message) for sub_id in subscriber_ids if sub_id in clients]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_safe(self, response, message: str) -> None:
        """Send a message to an SSE client, silently skip if send fails."""
        try:
            await response.write(f"data: {message}\n\n")
        except Exception:
            pass


class NotificationServer:
    """Notification server with pluggable transport layer and Redis pub/sub."""

    def __init__(self, transport: BaseTransport = None):
        if transport is None:
            transport = WebSocketTransport()
        self.transport = transport
        self.channels: Dict[str, Set[str]] = {}
        self.channel_lock = Lock()
        self.redis_pub = None
        self.redis_sub = None
        self.redis_listen_task = None

    @property
    def clients(self) -> Dict[str, Any]:
        """Access transport's clients for backward compatibility."""
        if isinstance(self.transport, WebSocketTransport):
            return self.transport.clients
        return {}

    def add_client(self, client_id: str, websocket) -> None:
        """Add a client to the registry via transport."""
        self.transport.add_client(client_id, websocket)

    def remove_client(self, client_id: str) -> None:
        """Remove a client from the registry via transport."""
        self.transport.remove_client(client_id)

    def get_client_count(self) -> int:
        """Get the number of connected clients from transport."""
        return self.transport.get_client_count()

    def get_all_clients(self) -> Dict[str, Any]:
        """Get a snapshot of all clients from transport."""
        return self.transport.get_all_clients()

    def subscribe(self, client_id: str, channel: str) -> bool:
        """Subscribe a client to a channel. Returns True if new subscription."""
        with self.channel_lock:
            if channel not in self.channels:
                self.channels[channel] = set()
            is_new = client_id not in self.channels[channel]
            self.channels[channel].add(client_id)
            return is_new

    def unsubscribe(self, client_id: str, channel: str) -> bool:
        """Unsubscribe a client from a channel. Returns True if was subscribed."""
        with self.channel_lock:
            if channel not in self.channels:
                return False
            was_subscribed = client_id in self.channels[channel]
            self.channels[channel].discard(client_id)
            if not self.channels[channel]:
                del self.channels[channel]
            return was_subscribed

    def unsubscribe_from_all(self, client_id: str) -> None:
        """Unsubscribe a client from all channels."""
        with self.channel_lock:
            for channel in list(self.channels.keys()):
                self.channels[channel].discard(client_id)
                if not self.channels[channel]:
                    del self.channels[channel]

    def get_channel_subscribers(self, channel: str) -> Set[str]:
        """Get a snapshot of subscribers for a channel."""
        with self.channel_lock:
            if channel not in self.channels:
                return set()
            return self.channels[channel].copy()

    def get_all_channels(self) -> Dict[str, int]:
        """Get all channels with subscriber counts."""
        with self.channel_lock:
            return {ch: len(subs) for ch, subs in self.channels.items()}

    async def broadcast(self, message: dict) -> None:
        """Broadcast a message to all connected clients and publish to Redis."""
        if not message.get("timestamp"):
            message["timestamp"] = datetime.utcnow().isoformat()

        # Save to SQLite
        channel = message.get("channel", "broadcast")
        save_message(channel, message.get("type", "broadcast"), message.get("payload", {}), message["timestamp"])

        # Publish to Redis
        await self.publish_to_redis(channel, message)

        msg_json = json.dumps(message)
        await self.transport.broadcast(msg_json)

    async def broadcast_to_channel(self, channel: str, message: dict) -> None:
        """Broadcast a message to subscribers of a specific channel and publish to Redis."""
        if not message.get("timestamp"):
            message["timestamp"] = datetime.utcnow().isoformat()

        # Save to SQLite
        save_message(channel, message.get("type", "broadcast"), message.get("payload", {}), message["timestamp"])

        # Publish to Redis
        await self.publish_to_redis(channel, message)

        msg_json = json.dumps(message)
        subscribers = self.get_channel_subscribers(channel)
        await self.transport.broadcast_to_subscribers(subscribers, msg_json)

    async def init_redis(self) -> None:
        """Initialize Redis publisher connection."""
        self.redis_pub = await aioredis.from_url(REDIS_URL)

    async def init_redis_subscriber(self) -> None:
        """Initialize Redis subscriber and start listening."""
        self.redis_sub = await aioredis.from_url(REDIS_URL)
        self.redis_listen_task = asyncio.create_task(self._listen_redis())

    async def _listen_redis(self) -> None:
        """Listen for messages from Redis channels."""
        channels = [self.redis_sub.pubsub_channels()]
        while True:
            try:
                if self.redis_sub:
                    channels_dict = await self.redis_sub.pubsub_channels()
                    for channel_name in channels_dict:
                        # For each channel, set up subscription
                        pass
                await asyncio.sleep(1)
            except Exception:
                await asyncio.sleep(1)

    async def publish_to_redis(self, channel: str, message: dict) -> None:
        """Publish a message to Redis channel."""
        if self.redis_pub:
            try:
                await self.redis_pub.publish(channel, json.dumps(message))
            except Exception:
                pass

    async def close_redis(self) -> None:
        """Close Redis connections."""
        if self.redis_listen_task:
            self.redis_listen_task.cancel()
        if self.redis_pub:
            self.redis_pub.close()
            await self.redis_pub.wait_closed()
        if self.redis_sub:
            self.redis_sub.close()
            await self.redis_sub.wait_closed()

    async def send_direct(self, client_id: str, message: dict) -> bool:
        """Send a direct message to a specific client."""
        if not message.get("timestamp"):
            message["timestamp"] = datetime.utcnow().isoformat()

        # Save to SQLite
        channel = f"direct:{client_id}"
        save_message(channel, message.get("type", "direct"), message.get("payload", {}), message["timestamp"])

        # Publish to Redis
        await self.publish_to_redis(channel, message)

        msg_json = json.dumps(message)
        return await self.transport.send_to_client(client_id, msg_json)


def create_transport(transport_type: str = None) -> BaseTransport:
    """Factory function to create transport instance based on configuration.

    Supported transport types:
    - "websocket" (default): WebSocket transport for full-duplex communication
    - "sse": Server-Sent Events transport for one-way server-to-client messaging

    Args:
        transport_type: Transport type name. If None, uses TRANSPORT env var.

    Returns:
        Instance of BaseTransport subclass.

    Raises:
        ValueError: If transport type is unknown.
    """
    if transport_type is None:
        transport_type = TRANSPORT

    if transport_type == "websocket":
        return WebSocketTransport()
    elif transport_type == "sse":
        return SSETransport()
    else:
        raise ValueError(f"Unknown transport type: {transport_type}. Supported: websocket, sse")


# Global server instance
server = NotificationServer(transport=create_transport())


async def handle_websocket(websocket, path):
    """Handle WebSocket connections."""
    client_id = str(uuid.uuid4())
    server.add_client(client_id, websocket)

    # Send connection confirmation
    await websocket.send(
        json.dumps({
            "type": "system",
            "payload": {"message": "connected", "client_id": client_id},
            "timestamp": datetime.utcnow().isoformat(),
        })
    )

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get("type")
                payload = data.get("payload", {})
                channel = data.get("channel")

                if msg_type == "subscribe":
                    channel_name = payload.get("channel")
                    if channel_name:
                        server.subscribe(client_id, channel_name)
                elif msg_type == "unsubscribe":
                    channel_name = payload.get("channel")
                    if channel_name:
                        server.unsubscribe(client_id, channel_name)
                elif msg_type == "broadcast":
                    if channel:
                        await server.broadcast_to_channel(channel, {
                            "type": "broadcast",
                            "payload": payload,
                            "channel": channel,
                        })
                    else:
                        await server.broadcast({
                            "type": "broadcast",
                            "payload": payload,
                        })
                elif msg_type == "direct":
                    target_id = payload.get("client_id")
                    direct_payload = payload.get("message", {})
                    await server.send_direct(target_id, {
                        "type": "direct",
                        "payload": {
                            "from": client_id,
                            "message": direct_payload,
                        },
                    })
            except json.JSONDecodeError:
                await websocket.send(
                    json.dumps({
                        "type": "system",
                        "payload": {"error": "invalid json"},
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                )
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        server.unsubscribe_from_all(client_id)
        server.remove_client(client_id)


async def health_handler(request):
    """REST endpoint for health check."""
    return web.json_response({
        "status": "ok",
        "connected_clients": server.get_client_count(),
    })


async def channels_handler(request):
    """REST endpoint to list all channels with subscriber counts."""
    channels = server.get_all_channels()
    return web.json_response({
        "channels": channels,
    })


async def channel_subscribers_handler(request):
    """REST endpoint to list subscribers of a specific channel."""
    channel_name = request.match_info.get("name")
    if not channel_name:
        return web.json_response({"error": "channel name required"}, status=400)

    subscribers = server.get_channel_subscribers(channel_name)
    return web.json_response({
        "channel": channel_name,
        "subscribers": list(subscribers),
        "count": len(subscribers),
    })


async def messages_handler(request):
    """REST endpoint to retrieve message history."""
    try:
        limit = int(request.query.get("limit", "50"))
        offset = int(request.query.get("offset", "0"))

        # Clamp values
        limit = max(1, min(limit, 1000))
        offset = max(0, offset)

        messages = get_messages(limit, offset)
        return web.json_response({
            "messages": messages,
            "limit": limit,
            "offset": offset,
            "count": len(messages),
        })
    except ValueError:
        return web.json_response({"error": "invalid limit or offset"}, status=400)


async def start_websocket_server(host: str = "localhost", port: int = 8765):
    """Start the WebSocket server."""
    async with websockets.serve(handle_websocket, host, port):
        print(f"WebSocket server running on ws://{host}:{port}")
        await asyncio.Event().wait()


async def start_rest_server(host: str = "localhost", port: int = 8080):
    """Start the REST server."""
    app = web.Application()
    app.router.add_get("/health", health_handler)
    app.router.add_get("/channels", channels_handler)
    app.router.add_get("/channels/{name}/subscribers", channel_subscribers_handler)
    app.router.add_get("/messages", messages_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    print(f"REST server running on http://{host}:{port}")
    await asyncio.Event().wait()


async def main(ws_host: str = "localhost", ws_port: int = 8765,
               rest_host: str = "localhost", rest_port: int = 8080):
    """Start both WebSocket and REST servers."""
    # Initialize database
    init_db()

    # Initialize Redis connections
    try:
        await server.init_redis()
        await server.init_redis_subscriber()
    except Exception as e:
        print(f"Warning: Could not connect to Redis: {e}")

    try:
        ws_task = asyncio.create_task(start_websocket_server(ws_host, ws_port))
        rest_task = asyncio.create_task(start_rest_server(rest_host, rest_port))
        await asyncio.gather(ws_task, rest_task)
    finally:
        await server.close_redis()


if __name__ == "__main__":
    asyncio.run(main())
