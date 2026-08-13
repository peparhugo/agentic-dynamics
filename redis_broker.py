"""Redis pub/sub broker for distributed message distribution."""

import asyncio
import json
import logging
import os
from typing import Callable, Optional
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisBroker:
    """Handles Redis pub/sub for message distribution across multiple server instances."""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379")
        self.redis: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self._running = False

    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            self.redis = await redis.from_url(self.redis_url)
            await self.redis.ping()
            logger.info(f"Connected to Redis at {self.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.pubsub:
            await self.pubsub.aclose()
        if self.redis:
            await self.redis.aclose()
        logger.info("Disconnected from Redis")

    async def publish(self, channel: str, message: str) -> int:
        """Publish a message to a Redis channel."""
        if not self.redis:
            raise RuntimeError("Redis broker not connected")
        try:
            num_subscribers = await self.redis.publish(channel, message)
            return num_subscribers
        except Exception as e:
            logger.error(f"Error publishing to {channel}: {e}")
            raise

    async def subscribe(
        self,
        channels: list[str],
        callback: Callable
    ) -> None:
        """Subscribe to Redis channels and handle messages."""
        if not self.redis:
            raise RuntimeError("Redis broker not connected")

        self.pubsub = self.redis.pubsub()
        await self.pubsub.subscribe(*channels)
        self._running = True

        logger.info(f"Subscribed to channels: {channels}")

        try:
            async for message in self.pubsub.listen():
                if not self._running:
                    break

                if message['type'] == 'message':
                    channel = message['channel'].decode() if isinstance(message['channel'], bytes) else message['channel']
                    data = message['data'].decode() if isinstance(message['data'], bytes) else message['data']
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(channel, data)
                        else:
                            callback(channel, data)
                    except Exception as e:
                        logger.error(f"Error in message callback: {e}")
        except Exception as e:
            logger.error(f"Error in subscribe loop: {e}")
        finally:
            await self.pubsub.aclose()

    async def unsubscribe(self, channels: Optional[list[str]] = None) -> None:
        """Unsubscribe from Redis channels."""
        if self.pubsub:
            if channels:
                await self.pubsub.unsubscribe(*channels)
            else:
                await self.pubsub.unsubscribe()
        self._running = False

    async def set_client_state(self, client_id: str, state: dict) -> None:
        """Store client connection state in Redis (survives server restart)."""
        if not self.redis:
            raise RuntimeError("Redis broker not connected")
        try:
            key = f"client:{client_id}"
            await self.redis.set(key, json.dumps(state), ex=86400)
        except Exception as e:
            logger.error(f"Error setting client state: {e}")

    async def get_client_state(self, client_id: str) -> Optional[dict]:
        """Retrieve client connection state from Redis."""
        if not self.redis:
            raise RuntimeError("Redis broker not connected")
        try:
            key = f"client:{client_id}"
            data = await self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Error getting client state: {e}")
            return None

    async def delete_client_state(self, client_id: str) -> None:
        """Delete client state from Redis."""
        if not self.redis:
            raise RuntimeError("Redis broker not connected")
        try:
            key = f"client:{client_id}"
            await self.redis.delete(key)
        except Exception as e:
            logger.error(f"Error deleting client state: {e}")
