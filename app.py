"""
WebSocket-based notification server with REST health endpoint.
"""

import asyncio
import json
import uuid
import os
from datetime import datetime
from typing import Dict, Optional
import websockets
from websockets.exceptions import ConnectionClosed
from aiohttp import web
import redis.asyncio as redis
import aiosqlite


class ClientRegistry:
    """Thread-safe registry of connected WebSocket clients with channel support."""

    def __init__(self):
        self.clients: Dict[str, object] = {}
        self.channels: Dict[str, set] = {}
        self.lock = asyncio.Lock()

    async def register(self, client_id: str, websocket: object):
        async with self.lock:
            self.clients[client_id] = websocket

    async def unregister(self, client_id: str):
        async with self.lock:
            self.clients.pop(client_id, None)
            for channel_subscribers in self.channels.values():
                channel_subscribers.discard(client_id)
            self.channels = {ch: subs for ch, subs in self.channels.items() if subs}

    async def subscribe(self, client_id: str, channel: str):
        """Subscribe client to a channel."""
        async with self.lock:
            if client_id in self.clients:
                if channel not in self.channels:
                    self.channels[channel] = set()
                self.channels[channel].add(client_id)
                return True
        return False

    async def unsubscribe(self, client_id: str, channel: str):
        """Unsubscribe client from a channel."""
        async with self.lock:
            if channel in self.channels:
                self.channels[channel].discard(client_id)
                if not self.channels[channel]:
                    del self.channels[channel]
                return True
        return False

    async def get_channels(self) -> dict:
        """Get all channels with subscriber counts."""
        async with self.lock:
            return {ch: len(subs) for ch, subs in self.channels.items()}

    async def get_channel_subscribers(self, channel: str) -> list:
        """Get subscriber IDs for a specific channel."""
        async with self.lock:
            return list(self.channels.get(channel, set()))

    async def get_client_count(self) -> int:
        async with self.lock:
            return len(self.clients)

    async def broadcast(self, message: dict, channel: str = None):
        """Send message to clients. If channel is specified, only to that channel's subscribers."""
        async with self.lock:
            if channel:
                client_ids = self.channels.get(channel, set()).copy()
            else:
                client_ids = set(self.clients.keys())

            disconnected = set()
            for client_id in client_ids:
                websocket = self.clients.get(client_id)
                if websocket:
                    try:
                        await websocket.send(json.dumps(message))
                    except (ConnectionClosed, Exception):
                        disconnected.add(client_id)

        for client_id in disconnected:
            await self.unregister(client_id)

    async def broadcast_to_local(self, message: dict, channel: str = None):
        """Broadcast only to local clients without Redis pub/sub."""
        async with self.lock:
            if channel:
                client_ids = self.channels.get(channel, set()).copy()
            else:
                client_ids = set(self.clients.keys())

            disconnected = set()
            for client_id in client_ids:
                websocket = self.clients.get(client_id)
                if websocket:
                    try:
                        await websocket.send(json.dumps(message))
                    except (ConnectionClosed, Exception):
                        disconnected.add(client_id)

        for client_id in disconnected:
            await self.unregister(client_id)

    async def send_direct(self, client_id: str, message: dict):
        """Send message to specific client."""
        async with self.lock:
            websocket = self.clients.get(client_id)

        if websocket:
            try:
                await websocket.send(json.dumps(message))
            except (ConnectionClosed, Exception):
                await self.unregister(client_id)


# Global registry
registry = ClientRegistry()

# Global Redis and database instances
redis_client: Optional[redis.Redis] = None


def get_db_path() -> str:
    """Get the database path from environment or use default."""
    return os.environ.get("DATABASE_URL", "notifications.db")


def get_redis_url() -> str:
    """Get the Redis URL from environment or use default."""
    return os.environ.get("REDIS_URL", "redis://localhost:6379")


async def init_database():
    """Initialize SQLite database with messages table."""
    db_path = get_db_path()
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        await db.commit()


async def store_message(channel: str, msg_type: str, payload: dict, timestamp: str):
    """Store message in SQLite database."""
    try:
        db_path = get_db_path()
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """
                INSERT INTO messages (channel, type, payload, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (channel, msg_type, json.dumps(payload), timestamp)
            )
            await db.commit()
    except Exception:
        pass


async def get_messages(limit: int = 50, offset: int = 0) -> list:
    """Retrieve messages from SQLite database (newest first)."""
    db_path = get_db_path()
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            SELECT id, channel, type, payload, timestamp
            FROM messages
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset)
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": row[0],
                "channel": row[1],
                "type": row[2],
                "payload": json.loads(row[3]),
                "timestamp": row[4]
            }
            for row in rows
        ]


def create_message(msg_type: str, payload: dict) -> dict:
    """Create a properly formatted message."""
    return {
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.utcnow().isoformat(),
    }


async def redis_publisher(message: dict, channel: str = None):
    """Publish message to Redis pub/sub."""
    if redis_client:
        channel_name = channel or "broadcast"
        try:
            await redis_client.publish(channel_name, json.dumps(message))
        except Exception:
            pass


async def redis_subscriber():
    """Subscribe to Redis channels and deliver messages to local clients."""
    if not redis_client:
        return

    pubsub = redis_client.pubsub()
    try:
        await pubsub.subscribe("broadcast", "alerts", "system", "chat")
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    channel = message["channel"].decode() if isinstance(message["channel"], bytes) else message["channel"]
                    await registry.broadcast_to_local(data, channel=channel if channel != "broadcast" else None)
                except Exception:
                    pass
    except Exception:
        pass
    finally:
        await pubsub.unsubscribe()
        await pubsub.close()


async def websocket_handler(websocket):
    """Handle WebSocket connection."""
    client_id = str(uuid.uuid4())

    # Register client
    await registry.register(client_id, websocket)

    # Notify all clients of new connection
    await registry.broadcast(
        create_message("system", {"event": "client_joined", "client_id": client_id})
    )

    try:
        async for raw_message in websocket:
            try:
                message = json.loads(raw_message)
                msg_type = message.get("type")

                if msg_type == "broadcast":
                    channel = message.get("channel")
                    msg = create_message("broadcast", message.get("payload", {}))
                    await registry.broadcast(msg, channel=channel)
                    await redis_publisher(msg, channel=channel)
                    await store_message(channel or "broadcast", "broadcast", message.get("payload", {}), msg["timestamp"])
                elif msg_type == "direct":
                    target_client_id = message.get("target_client_id")
                    if target_client_id:
                        msg = create_message("direct", message.get("payload", {}))
                        await registry.send_direct(target_client_id, msg)
                        await store_message("direct", "direct", {"target": target_client_id, **message.get("payload", {})}, msg["timestamp"])
                elif msg_type == "subscribe":
                    channel = message.get("channel")
                    if channel:
                        success = await registry.subscribe(client_id, channel)
                        await websocket.send(
                            json.dumps(
                                create_message("system", {
                                    "event": "subscribed",
                                    "channel": channel,
                                    "success": success
                                })
                            )
                        )
                    else:
                        await websocket.send(
                            json.dumps(
                                create_message("system", {"error": "Channel name required for subscribe"})
                            )
                        )
                elif msg_type == "unsubscribe":
                    channel = message.get("channel")
                    if channel:
                        success = await registry.unsubscribe(client_id, channel)
                        await websocket.send(
                            json.dumps(
                                create_message("system", {
                                    "event": "unsubscribed",
                                    "channel": channel,
                                    "success": success
                                })
                            )
                        )
                    else:
                        await websocket.send(
                            json.dumps(
                                create_message("system", {"error": "Channel name required for unsubscribe"})
                            )
                        )
                else:
                    await websocket.send(
                        json.dumps(
                            create_message("system", {"error": f"Unknown message type: {msg_type}"})
                        )
                    )
            except json.JSONDecodeError:
                await websocket.send(
                    json.dumps(create_message("system", {"error": "Invalid JSON"}))
                )
    except ConnectionClosed:
        pass
    finally:
        # Unregister client
        await registry.unregister(client_id)
        # Notify all clients of disconnection
        await registry.broadcast(
            create_message("system", {"event": "client_left", "client_id": client_id})
        )


async def health_handler(request):
    """Health check endpoint returning connected client count."""
    count = await registry.get_client_count()
    return web.json_response({"status": "ok", "connected_clients": count})


async def channels_handler(request):
    """List all active channels with subscriber counts."""
    channels = await registry.get_channels()
    return web.json_response(channels)


async def channel_subscribers_handler(request):
    """List subscriber IDs for a specific channel."""
    channel_name = request.match_info["name"]
    subscribers = await registry.get_channel_subscribers(channel_name)
    return web.json_response({"channel": channel_name, "subscribers": subscribers})


async def messages_handler(request):
    """Get message history with pagination."""
    try:
        limit = int(request.query.get("limit", 50))
        offset = int(request.query.get("offset", 0))
        limit = min(limit, 1000)
        offset = max(offset, 0)
    except (ValueError, TypeError):
        limit = 50
        offset = 0

    messages = await get_messages(limit, offset)
    return web.json_response({"messages": messages, "limit": limit, "offset": offset})


async def start_servers():
    """Start both WebSocket and REST servers."""
    global redis_client

    await init_database()

    try:
        redis_client = await redis.from_url(get_redis_url())
        await redis_client.ping()
    except Exception:
        print("Warning: Redis connection failed, running without pub/sub")
        redis_client = None

    async with websockets.serve(websocket_handler, "localhost", 8765):
        app = web.Application()
        app.router.add_get("/health", health_handler)
        app.router.add_get("/channels", channels_handler)
        app.router.add_get("/channels/{name}/subscribers", channel_subscribers_handler)
        app.router.add_get("/messages", messages_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "localhost", 8766)
        await site.start()

        print("WebSocket server running on ws://localhost:8765")
        print("REST API running on http://localhost:8766")

        redis_task = None
        if redis_client:
            redis_task = asyncio.create_task(redis_subscriber())

        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            if redis_task:
                redis_task.cancel()
                try:
                    await redis_task
                except asyncio.CancelledError:
                    pass
            if redis_client:
                await redis_client.close()
            await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(start_servers())
