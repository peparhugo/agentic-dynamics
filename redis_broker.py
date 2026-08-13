"""
Redis pub/sub message broker.

Provides:
- Async Redis pub/sub for distributed message delivery
- Client connection state storage in Redis
- Support for multiple server instances sharing the same backbone
"""

import json
import os
import logging
from typing import Callable, Optional, Dict, Set
from datetime import datetime, timedelta
import asyncio
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisBroker:
    """Redis pub/sub message broker with client state storage."""

    def __init__(self, redis_url: str = None):
        """Initialize Redis broker.

        Args:
            redis_url: Redis connection URL. Defaults to REDIS_URL env var or 'redis://localhost'
        """
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost')
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub = None
        self._subscribers: Dict[str, Callable] = {}
        self._connected = False

    async def connect(self):
        """Connect to Redis."""
        try:
            self.redis_client = await redis.from_url(
                self.redis_url,
                encoding='utf-8',
                decode_responses=True,
                socket_connect_timeout=5
            )
            await self.redis_client.ping()
            self._connected = True
            logger.info(f"Connected to Redis at {self.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
            raise

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.close()
            self._connected = False
            logger.info("Disconnected from Redis")

    async def publish(self, channel: str, message: dict):
        """Publish a message to a Redis channel.

        Args:
            channel: Channel name
            message: Message dict to publish
        """
        if not self._connected:
            logger.warning("Redis broker not connected, skipping publish")
            return

        try:
            message_json = json.dumps(message)
            num_subscribers = await self.redis_client.publish(channel, message_json)
            logger.debug(f"Published to channel '{channel}' for {num_subscribers} subscribers")
        except Exception as e:
            logger.error(f"Error publishing to Redis channel '{channel}': {e}")

    async def subscribe(self, channel: str, callback: Callable):
        """Subscribe to a Redis channel.

        Args:
            channel: Channel name to subscribe to
            callback: Async callback function to call with messages
        """
        if not self._connected:
            logger.warning("Redis broker not connected, cannot subscribe")
            return

        self._subscribers[channel] = callback

    async def start_listening(self):
        """Start listening to subscribed channels."""
        if not self._connected or not self._subscribers:
            return

        try:
            pubsub = self.redis_client.pubsub()

            for channel in self._subscribers:
                await pubsub.subscribe(channel)
                logger.info(f"Subscribed to Redis channel '{channel}'")

            async for message in pubsub.listen():
                if message['type'] == 'message':
                    channel = message['channel']
                    try:
                        payload = json.loads(message['data'])
                        callback = self._subscribers.get(channel)
                        if callback:
                            await callback(payload)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to decode message from '{channel}': {e}")
                    except Exception as e:
                        logger.error(f"Error processing message from '{channel}': {e}")

        except Exception as e:
            logger.error(f"Error listening to Redis channels: {e}")
        finally:
            await pubsub.close()

    async def store_client_connection(self, client_id: str, channel: str = None):
        """Store client connection state in Redis (survives server restart).

        Args:
            client_id: Unique client identifier
            channel: Optional channel client is connected to
        """
        if not self._connected:
            return

        try:
            client_key = f"client:{client_id}"
            client_data = {
                'client_id': client_id,
                'connected_at': datetime.utcnow().isoformat(),
                'channel': channel or ''
            }

            await self.redis_client.setex(
                client_key,
                timedelta(hours=24),
                json.dumps(client_data)
            )
            logger.debug(f"Stored connection state for client {client_id}")
        except Exception as e:
            logger.error(f"Error storing client connection: {e}")

    async def remove_client_connection(self, client_id: str):
        """Remove client connection state from Redis.

        Args:
            client_id: Unique client identifier
        """
        if not self._connected:
            return

        try:
            client_key = f"client:{client_id}"
            await self.redis_client.delete(client_key)
            logger.debug(f"Removed connection state for client {client_id}")
        except Exception as e:
            logger.error(f"Error removing client connection: {e}")

    async def get_client_connections(self) -> Dict[str, Dict]:
        """Get all active client connections from Redis.

        Returns:
            Dict of client_id -> client_data
        """
        if not self._connected:
            return {}

        try:
            clients = {}
            cursor = 0
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor,
                    match='client:*',
                    count=100
                )

                for key in keys:
                    try:
                        data_json = await self.redis_client.get(key)
                        if data_json:
                            data = json.loads(data_json)
                            client_id = data.get('client_id')
                            if client_id:
                                clients[client_id] = data
                    except (json.JSONDecodeError, Exception) as e:
                        logger.debug(f"Error reading client data from {key}: {e}")

                if cursor == 0:
                    break

            return clients
        except Exception as e:
            logger.error(f"Error retrieving client connections: {e}")
            return {}

    async def is_connected(self) -> bool:
        """Check if broker is connected to Redis."""
        return self._connected
