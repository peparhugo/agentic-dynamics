"""
WebSocket-based notification server with Redis pub/sub backbone and SQLite persistence.

Features:
- Accept WebSocket connections from clients
- Assign unique IDs to each client
- Broadcast messages via Redis pub/sub
- Store messages in SQLite for history
- Client state stored in Redis (survives server restart)
- REST endpoint: GET /messages?limit=50&offset=0
- Multiple server instances share the same Redis backbone
"""

import asyncio
import json
import uuid
import sqlite3
import os
from datetime import datetime, timezone
from threading import Lock
from typing import Set, Dict, Any
import logging

import websockets
from websockets.asyncio.server import serve, ServerConnection
import redis.asyncio as aioredis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MessagePersistence:
    """SQLite-based message persistence for history."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.environ.get("DATABASE_URL", "messages.db")
        self.lock = Lock()
        self.init_db()

    def init_db(self) -> None:
        """Initialize the messages table."""
        with self.get_connection() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS messages ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  channel TEXT NOT NULL,"
                "  type TEXT NOT NULL,"
                "  payload TEXT NOT NULL,"
                "  timestamp TEXT NOT NULL"
                ")"
            )
            conn.commit()

    def get_connection(self):
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def store_message(self, channel: str, msg_type: str, payload: dict, timestamp: str) -> int:
        """Store a message in the database."""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                    (channel, msg_type, json.dumps(payload), timestamp),
                )
                conn.commit()
                return cursor.lastrowid

    def get_messages(self, limit: int = 50, offset: int = 0) -> list:
        """Retrieve messages from the database."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    "channel": row["channel"],
                    "type": row["type"],
                    "payload": json.loads(row["payload"]),
                    "timestamp": row["timestamp"],
                }
                for row in rows
            ]

    def get_message_count(self) -> int:
        """Get total message count."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) as count FROM messages").fetchone()
            return row["count"]


class ClientRegistry:
    """Thread-safe registry of connected WebSocket clients with Redis-backed state."""

    def __init__(self, redis_client=None):
        self._clients: Dict[str, ServerConnection] = {}
        self._subscriptions: Dict[str, Set[str]] = {}
        self._lock = Lock()
        self.redis = redis_client

    async def add(self, client_id: str, connection: ServerConnection) -> None:
        """Add a client to the registry."""
        with self._lock:
            self._clients[client_id] = connection
            self._subscriptions[client_id] = set()
        if self.redis:
            await self.redis.set(f"client:{client_id}", "1", ex=3600)

    async def remove(self, client_id: str) -> None:
        """Remove a client from the registry."""
        with self._lock:
            self._clients.pop(client_id, None)
            self._subscriptions.pop(client_id, None)
        if self.redis:
            try:
                await self.redis.delete(f"client:{client_id}")
                await self.redis.delete(f"subscriptions:{client_id}")
            except Exception:
                pass

    def get(self, client_id: str) -> ServerConnection | None:
        """Get a client connection by ID."""
        with self._lock:
            return self._clients.get(client_id)

    def get_all(self) -> Dict[str, ServerConnection]:
        """Get a copy of all clients."""
        with self._lock:
            return dict(self._clients)

    def count(self) -> int:
        """Get the number of connected clients."""
        with self._lock:
            return len(self._clients)

    async def subscribe(self, client_id: str, channel: str) -> None:
        """Subscribe a client to a channel."""
        with self._lock:
            if client_id in self._subscriptions:
                self._subscriptions[client_id].add(channel)
        if self.redis:
            await self.redis.sadd(f"subscriptions:{client_id}", channel)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        """Unsubscribe a client from a channel."""
        with self._lock:
            if client_id in self._subscriptions:
                self._subscriptions[client_id].discard(channel)
        if self.redis:
            await self.redis.srem(f"subscriptions:{client_id}", channel)

    def get_subscriptions(self, client_id: str) -> Set[str]:
        """Get all channels a client is subscribed to."""
        with self._lock:
            return set(self._subscriptions.get(client_id, set()))

    def get_channel_subscribers(self, channel: str) -> Set[str]:
        """Get all client IDs subscribed to a channel."""
        with self._lock:
            subscribers = set()
            for client_id, channels in self._subscriptions.items():
                if channel in channels:
                    subscribers.add(client_id)
            return subscribers

    def get_all_channels(self) -> Dict[str, int]:
        """Get all active channels and their subscriber counts."""
        with self._lock:
            channels: Dict[str, Set[str]] = {}
            for client_id, subs in self._subscriptions.items():
                for channel in subs:
                    if channel not in channels:
                        channels[channel] = set()
                    channels[channel].add(client_id)
            return {channel: len(subscribers) for channel, subscribers in channels.items()}


class NotificationMessage:
    """Message formatter for notifications."""

    def __init__(self, msg_type: str, payload: dict | None = None):
        self.type = msg_type
        self.payload = payload or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps({
            "type": self.type,
            "payload": self.payload,
            "timestamp": self.timestamp,
        })

    @staticmethod
    def from_json(data: str) -> "NotificationMessage":
        """Parse JSON string to NotificationMessage."""
        obj = json.loads(data)
        msg = NotificationMessage(obj["type"], obj.get("payload", {}))
        if "timestamp" in obj:
            msg.timestamp = obj["timestamp"]
        return msg


class NotificationServer:
    """WebSocket notification server with Redis pub/sub backbone and SQLite persistence."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        ws_port: int = 8765,
        http_port: int = 8080,
        redis_url: str = None,
        db_path: str = None,
        redis_client=None,
    ):
        self.host = host
        self.ws_port = ws_port
        self.http_port = http_port
        self.redis_url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379")
        self.redis = redis_client
        self.persistence = MessagePersistence(db_path)
        self.clients = ClientRegistry(redis_client=redis_client)
        self.loop = None
        self.pubsub = None

    async def handle_client(self, websocket: ServerConnection) -> None:
        """Handle a connected WebSocket client."""
        client_id = str(uuid.uuid4())
        await self.clients.add(client_id, websocket)

        logger.info(f"Client {client_id} connected. Total clients: {self.clients.count()}")

        try:
            system_msg = NotificationMessage(
                "system",
                {"action": "connected", "client_id": client_id}
            )
            await websocket.send(system_msg.to_json())

            async for message in websocket:
                try:
                    msg = NotificationMessage.from_json(message)
                    logger.info(f"Received from {client_id}: {msg.type}")

                    if msg.type == "subscribe":
                        channel = msg.payload.get("channel")
                        if channel:
                            await self.clients.subscribe(client_id, channel)
                            logger.info(f"Client {client_id} subscribed to channel: {channel}")
                    elif msg.type == "unsubscribe":
                        channel = msg.payload.get("channel")
                        if channel:
                            await self.clients.unsubscribe(client_id, channel)
                            logger.info(f"Client {client_id} unsubscribed from channel: {channel}")
                    elif msg.type == "broadcast":
                        await self.broadcast(
                            NotificationMessage("broadcast", msg.payload)
                        )
                    elif msg.type == "direct":
                        target_id = msg.payload.get("target_id")
                        if target_id:
                            await self.send_direct(target_id, msg)
                    elif msg.type == "system":
                        await self.broadcast(msg)
                    else:
                        channel = msg.payload.get("channel")
                        if channel:
                            await self.broadcast_to_channel(channel, msg)
                        else:
                            await self.broadcast(msg)

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from {client_id}: {e}")
                    error_msg = NotificationMessage(
                        "system",
                        {"action": "error", "message": "Invalid JSON format"}
                    )
                    await websocket.send(error_msg.to_json())

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.clients.remove(client_id)
            logger.info(f"Client {client_id} disconnected. Total clients: {self.clients.count()}")

    async def broadcast(self, message: NotificationMessage) -> None:
        """Broadcast a message to all connected clients and publish to Redis."""
        self.persistence.store_message("broadcast", message.type, message.payload, message.timestamp)

        if self.redis:
            await self.redis.publish("broadcast", message.to_json())

        clients = self.clients.get_all()
        if not clients:
            logger.debug("No clients to broadcast to")
            return

        message_json = message.to_json()
        tasks = []

        for client_id, connection in clients.items():
            tasks.append(self._send_safe(connection, message_json, client_id))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_to_channel(self, channel: str, message: NotificationMessage) -> None:
        """Broadcast a message to all clients subscribed to a channel and publish to Redis."""
        self.persistence.store_message(channel, message.type, message.payload, message.timestamp)

        if self.redis:
            await self.redis.publish(f"channel:{channel}", message.to_json())

        subscribers = self.clients.get_channel_subscribers(channel)
        if not subscribers:
            logger.debug(f"No subscribers for channel {channel}")
            return

        message_json = message.to_json()
        tasks = []
        clients = self.clients.get_all()

        for client_id in subscribers:
            connection = clients.get(client_id)
            if connection:
                tasks.append(self._send_safe(connection, message_json, client_id))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_safe(self, connection: ServerConnection, message: str, client_id: str) -> None:
        """Safely send a message to a connection, handling disconnects."""
        try:
            await connection.send(message)
        except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
            logger.debug(f"Failed to send to {client_id} (disconnected)")
        except Exception as e:
            logger.error(f"Error sending to {client_id}: {e}")

    async def send_direct(self, target_id: str, message: NotificationMessage) -> None:
        """Send a message to a specific client."""
        connection = self.clients.get(target_id)
        if connection:
            await self._send_safe(connection, message.to_json(), target_id)
        else:
            logger.warning(f"Target client {target_id} not found")

    async def http_health(self, reader, writer) -> None:
        """HTTP server handler for REST endpoints."""
        request_line = await reader.readline()
        request_line = request_line.decode().strip()

        if not request_line:
            writer.close()
            return

        parts = request_line.split()
        if len(parts) < 2:
            writer.close()
            return

        method, path_with_query = parts[0], parts[1]

        path = path_with_query.split("?")[0]
        query_string = path_with_query.split("?")[1] if "?" in path_with_query else ""

        if method == "GET" and path == "/health":
            client_count = self.clients.count()
            response_body = json.dumps({"connected_clients": client_count})
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(response_body)}\r\n"
                "Connection: close\r\n"
                "\r\n"
                f"{response_body}"
            )
            writer.write(response.encode())
        elif method == "GET" and path == "/messages":
            limit = 50
            offset = 0
            if query_string:
                for param in query_string.split("&"):
                    if "=" in param:
                        key, value = param.split("=", 1)
                        if key == "limit":
                            try:
                                limit = int(value)
                            except ValueError:
                                pass
                        elif key == "offset":
                            try:
                                offset = int(value)
                            except ValueError:
                                pass

            messages = self.persistence.get_messages(limit=limit, offset=offset)
            total_count = self.persistence.get_message_count()
            response_body = json.dumps({
                "messages": messages,
                "total": total_count,
                "limit": limit,
                "offset": offset,
            })
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(response_body)}\r\n"
                "Connection: close\r\n"
                "\r\n"
                f"{response_body}"
            )
            writer.write(response.encode())
        elif method == "GET" and path == "/channels":
            channels = self.clients.get_all_channels()
            response_body = json.dumps({"channels": channels})
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(response_body)}\r\n"
                "Connection: close\r\n"
                "\r\n"
                f"{response_body}"
            )
            writer.write(response.encode())
        elif method == "GET" and path.startswith("/channels/") and path.endswith("/subscribers"):
            channel_name = path[len("/channels/"):-len("/subscribers")]
            subscribers = self.clients.get_channel_subscribers(channel_name)
            response_body = json.dumps({"channel": channel_name, "subscribers": list(subscribers)})
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(response_body)}\r\n"
                "Connection: close\r\n"
                "\r\n"
                f"{response_body}"
            )
            writer.write(response.encode())
        else:
            response = (
                "HTTP/1.1 404 Not Found\r\n"
                "Content-Type: text/plain\r\n"
                "Connection: close\r\n"
                "\r\n"
                "Not Found"
            )
            writer.write(response.encode())

        await writer.drain()
        writer.close()

    async def redis_subscribe(self) -> None:
        """Subscribe to Redis pub/sub channels for distributed messaging."""
        if not self.redis:
            return

        pubsub = self.redis.pubsub()
        self.pubsub = pubsub
        await pubsub.subscribe("broadcast", "channel:*")
        logger.info("Subscribed to Redis pub/sub channels")

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        channel = message["channel"]
                        if isinstance(channel, bytes):
                            channel = channel.decode()
                        data = message["data"]
                        if isinstance(data, bytes):
                            data = data.decode()

                        msg = NotificationMessage.from_json(data)
                        logger.info(f"Received from Redis on {channel}: {msg.type}")

                        if channel == "broadcast":
                            await self.broadcast_to_clients(msg)
                        elif channel.startswith("channel:"):
                            channel_name = channel[8:]
                            await self.broadcast_to_channel_clients(channel_name, msg)
                    except Exception as e:
                        logger.error(f"Error processing Redis message: {e}")
        except asyncio.CancelledError:
            await pubsub.unsubscribe()
            await pubsub.close()

    async def broadcast_to_clients(self, message: NotificationMessage) -> None:
        """Send message to all locally connected clients."""
        clients = self.clients.get_all()
        if not clients:
            return

        message_json = message.to_json()
        tasks = []

        for client_id, connection in clients.items():
            tasks.append(self._send_safe(connection, message_json, client_id))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_to_channel_clients(self, channel: str, message: NotificationMessage) -> None:
        """Send message to locally connected clients subscribed to a channel."""
        subscribers = self.clients.get_channel_subscribers(channel)
        if not subscribers:
            return

        message_json = message.to_json()
        tasks = []
        clients = self.clients.get_all()

        for client_id in subscribers:
            connection = clients.get(client_id)
            if connection:
                tasks.append(self._send_safe(connection, message_json, client_id))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def http_server(self) -> None:
        """Start HTTP server for health checks."""
        server = await asyncio.start_server(
            self.http_health,
            self.host,
            self.http_port
        )
        logger.info(f"HTTP server listening on {self.host}:{self.http_port}")
        async with server:
            await server.serve_forever()

    async def ws_server(self) -> None:
        """Start WebSocket server."""
        async with serve(self.handle_client, self.host, self.ws_port):
            logger.info(f"WebSocket server listening on ws://{self.host}:{self.ws_port}")
            await asyncio.Future()  # Run forever

    async def start(self) -> None:
        """Start WebSocket server, HTTP server, and Redis subscription."""
        self.loop = asyncio.get_running_loop()

        if not self.redis:
            try:
                self.redis = await aioredis.from_url(self.redis_url, decode_responses=True)
                self.clients.redis = self.redis
                logger.info(f"Connected to Redis at {self.redis_url}")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Continuing without Redis.")
                self.redis = None

        tasks = [
            self.ws_server(),
            self.http_server(),
        ]

        if self.redis:
            tasks.append(self.redis_subscribe())

        await asyncio.gather(*tasks)


def create_server(
    host: str = "127.0.0.1",
    ws_port: int = 8765,
    http_port: int = 8080,
    redis_url: str = None,
    db_path: str = None,
    redis_client=None,
) -> NotificationServer:
    """Factory function to create a NotificationServer."""
    return NotificationServer(
        host=host,
        ws_port=ws_port,
        http_port=http_port,
        redis_url=redis_url,
        db_path=db_path,
        redis_client=redis_client,
    )


if __name__ == "__main__":
    server = create_server()
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server shutting down")
