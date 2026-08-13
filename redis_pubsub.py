"""
Redis pub/sub handler for message distribution.
"""

import asyncio
import json
import threading
from typing import Callable, Dict, Any, Optional
import redis
import redis.asyncio as aioredis


class RedisPublisher:
    """Publishes messages to Redis channels."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.client = None

    async def connect(self) -> None:
        """Connect to Redis."""
        self.client = await aioredis.from_url(self.redis_url)

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.client:
            await self.client.close()

    async def publish(self, channel: str, message: Dict[str, Any]) -> None:
        """Publish a message to a Redis channel."""
        if not self.client:
            return

        message_json = json.dumps(message)
        try:
            await self.client.publish(channel, message_json)
        except Exception:
            pass


class RedisSubscriber:
    """Subscribes to Redis channels and receives messages."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.pubsub = None
        self.client = None
        self._running = False
        self._task = None
        self.message_handlers: Dict[str, list] = {}

    async def connect(self) -> None:
        """Connect to Redis."""
        self.client = await aioredis.from_url(self.redis_url)
        self.pubsub = await self.client.pubsub()

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        self._running = False
        if self._task:
            await self._task
        if self.pubsub:
            await self.pubsub.close()
        if self.client:
            await self.client.close()

    async def subscribe(self, channel: str, handler: Callable) -> None:
        """Subscribe to a channel with a message handler."""
        if channel not in self.message_handlers:
            self.message_handlers[channel] = []
            if self.pubsub:
                await self.pubsub.subscribe(channel)

        self.message_handlers[channel].append(handler)

    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel."""
        if channel in self.message_handlers:
            del self.message_handlers[channel]
            if self.pubsub:
                await self.pubsub.unsubscribe(channel)

    async def start(self) -> None:
        """Start listening for messages."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        """Stop listening for messages."""
        self._running = False
        if self._task:
            await self._task

    async def _listen(self) -> None:
        """Listen for incoming messages."""
        if not self.pubsub:
            return

        try:
            async for message in self.pubsub.listen():
                if not self._running:
                    break

                if message["type"] == "message":
                    channel = message["channel"].decode() if isinstance(message["channel"], bytes) else message["channel"]
                    data = message["data"]

                    if isinstance(data, bytes):
                        data = data.decode()

                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    # Call all handlers for this channel
                    if channel in self.message_handlers:
                        for handler in self.message_handlers[channel]:
                            try:
                                await handler(payload)
                            except Exception:
                                pass

        except Exception:
            pass


class ClientConnectionState:
    """Manages client connection state in Redis."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.client = redis.from_url(redis_url)

    def set_connected(self, client_id: str, data: Dict[str, Any]) -> None:
        """Store client connection state."""
        key = f"client:{client_id}"
        value = json.dumps(data)
        self.client.setex(key, 86400, value)  # 24-hour TTL

    def get_connected(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve client connection state."""
        key = f"client:{client_id}"
        value = self.client.get(key)
        if value:
            return json.loads(value)
        return None

    def remove_connected(self, client_id: str) -> None:
        """Remove client connection state."""
        key = f"client:{client_id}"
        self.client.delete(key)

    def get_all_connected(self) -> Dict[str, Dict[str, Any]]:
        """Get all connected clients."""
        pattern = "client:*"
        keys = self.client.keys(pattern)
        clients = {}
        for key in keys:
            client_id = key.decode().replace("client:", "")
            value = self.client.get(key)
            if value:
                clients[client_id] = json.loads(value)
        return clients

    def close(self) -> None:
        """Close the Redis connection."""
        self.client.close()
