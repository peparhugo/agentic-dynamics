"""WebSocket-based notification server with REST health endpoint."""

import asyncio
import json
import logging
import os
from typing import Optional
from aiohttp import web

from client_registry import ClientRegistry
from message_handler import Message, MessageHandler
from redis_broker import RedisBroker
from message_persistence import MessagePersistence
from transport import BaseTransport
from websocket_transport import WebSocketTransport
from polling_transport import PollingTransport

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NotificationServer:
    """Main notification server with pluggable transport."""

    def __init__(
        self,
        ws_host: str = 'localhost',
        ws_port: int = 8765,
        rest_port: int = 8080,
        transport: Optional[BaseTransport] = None
    ):
        self.ws_host = ws_host
        self.ws_port = ws_port
        self.rest_port = rest_port
        self.client_registry = ClientRegistry()
        self.redis_broker = RedisBroker()
        self.message_persistence = MessagePersistence()
        self.rest_app = web.Application()
        self._setup_rest_routes()
        self._stop_event = asyncio.Event()
        self._redis_subscribe_task: Optional[asyncio.Task] = None

        # Initialize transport
        if transport is None:
            transport = self._create_transport()
        self.transport = transport
        self._transport_task: Optional[asyncio.Task] = None

    def _create_transport(self) -> BaseTransport:
        """Create transport based on environment config."""
        transport_type = os.getenv('TRANSPORT', 'websocket').lower()

        if transport_type == 'websocket':
            return WebSocketTransport(
                host=self.ws_host,
                port=self.ws_port,
                on_client_connect=self._on_client_connect,
                on_client_disconnect=self._on_client_disconnect,
                on_client_message=self._handle_message,
                client_registry=self.client_registry
            )
        elif transport_type == 'polling':
            return PollingTransport(
                host=self.ws_host,
                port=self.ws_port,
                on_client_connect=self._on_client_connect,
                on_client_disconnect=self._on_client_disconnect,
                on_client_message=self._handle_message,
                client_registry=self.client_registry
            )
        else:
            raise ValueError(f"Unknown transport type: {transport_type}")

    def _setup_rest_routes(self):
        """Setup REST API routes."""
        self.rest_app.router.add_get('/health', self._health_handler)
        self.rest_app.router.add_get('/channels', self._channels_handler)
        self.rest_app.router.add_get('/channels/{name}/subscribers', self._channel_subscribers_handler)
        self.rest_app.router.add_get('/messages', self._messages_handler)

    async def _health_handler(self, request: web.Request) -> web.Response:
        """Handle health check endpoint."""
        count = self.client_registry.get_client_count()
        return web.json_response({
            'connected_clients': count,
            'status': 'ok'
        })

    async def _channels_handler(self, request: web.Request) -> web.Response:
        """Handle GET /channels endpoint."""
        channels = self.client_registry.get_active_channels()
        return web.json_response({
            'channels': channels,
            'count': len(channels)
        })

    async def _channel_subscribers_handler(self, request: web.Request) -> web.Response:
        """Handle GET /channels/{name}/subscribers endpoint."""
        channel_name = request.match_info['name']
        subscribers = self.client_registry.get_channel_subscribers(channel_name)
        return web.json_response({
            'channel': channel_name,
            'subscribers': subscribers,
            'count': len(subscribers)
        })

    async def _messages_handler(self, request: web.Request) -> web.Response:
        """Handle GET /messages endpoint for message history."""
        limit = int(request.query.get('limit', 50))
        offset = int(request.query.get('offset', 0))
        channel = request.query.get('channel')

        limit = min(limit, 1000)

        messages = self.message_persistence.get_messages(
            channel=channel,
            limit=limit,
            offset=offset
        )
        total_count = self.message_persistence.get_message_count(channel=channel)

        return web.json_response({
            'messages': messages,
            'count': len(messages),
            'total': total_count,
            'limit': limit,
            'offset': offset,
            'channel': channel
        })

    async def _on_client_connect(self, client_id: str) -> None:
        """Handle new client connection."""
        logger.info(f"Client connected: {client_id}")
        # Send client ID to the new client
        client_msg = Message('system', {'client_id': client_id})
        await self.transport.send_message(client_id, client_msg)

    async def _on_client_disconnect(self, client_id: str) -> None:
        """Handle client disconnection."""
        logger.info(f"Client disconnected: {client_id}")

    async def _handle_message(self, sender_id: str, message: Message) -> None:
        """Route message to appropriate handler."""
        if message.type == 'broadcast':
            await self._broadcast_message(message, from_redis=False)
        elif message.type == 'direct':
            await self._direct_message(message)
        elif message.type == 'subscribe':
            await self._handle_subscribe(sender_id, message)
        elif message.type == 'unsubscribe':
            await self._handle_unsubscribe(sender_id, message)
        elif message.type == 'system':
            logger.info(f"System message from {sender_id}: {message.payload}")

    async def _handle_redis_message(self, channel: str, data: str) -> None:
        """Handle messages received from Redis pub/sub."""
        try:
            message = Message.from_json(data)
            if message.type == 'broadcast':
                await self._broadcast_message(message, from_redis=True)
            elif message.type == 'direct':
                await self._direct_message(message)
        except Exception as e:
            logger.error(f"Error handling Redis message: {e}")

    async def _handle_subscribe(self, sender_id: str, message: Message) -> None:
        """Handle client subscribing to a channel."""
        channel = message.payload.get('channel')
        if not channel:
            logger.warning(f"Subscribe message from {sender_id} without channel")
            return
        self.client_registry.subscribe(sender_id, channel)
        logger.info(f"Client {sender_id} subscribed to channel '{channel}'")

    async def _handle_unsubscribe(self, sender_id: str, message: Message) -> None:
        """Handle client unsubscribing from a channel."""
        channel = message.payload.get('channel')
        if not channel:
            logger.warning(f"Unsubscribe message from {sender_id} without channel")
            return
        self.client_registry.unsubscribe(sender_id, channel)
        logger.info(f"Client {sender_id} unsubscribed from channel '{channel}'")

    async def _broadcast_message(self, message: Message, from_redis: bool = False) -> None:
        """Broadcast message to all connected clients or to channel subscribers."""
        channel = message.payload.get('channel')

        if not from_redis:
            try:
                await self.redis_broker.publish(
                    f"notifications:{channel}" if channel else "notifications:broadcast",
                    message.to_json()
                )
            except Exception as e:
                logger.warning(f"Failed to publish to Redis: {e}")

        self.message_persistence.store_message(
            channel=channel or "broadcast",
            message_type=message.type,
            payload=message.payload,
            timestamp=message.timestamp
        )

        await self.transport.broadcast(message, channel=channel)

    async def _direct_message(self, message: Message) -> None:
        """Send direct message to specific client."""
        recipient_id = message.payload.get('recipient_id')
        if not recipient_id:
            logger.warning("Direct message without recipient_id")
            return

        recipient = self.client_registry.get_client(recipient_id)
        if recipient:
            await self.transport.send_message(recipient_id, message)
        else:
            logger.warning(f"Recipient not found: {recipient_id}")

    async def run(self) -> None:
        """Run both transport and REST servers."""
        try:
            await self.redis_broker.connect()
        except Exception as e:
            logger.warning(f"Redis not available, continuing without pub/sub: {e}")

        # Start Redis subscription in background
        if self.redis_broker.redis:
            self._redis_subscribe_task = asyncio.create_task(
                self.redis_broker.subscribe(
                    ["notifications:broadcast", "notifications:*"],
                    self._handle_redis_message
                )
            )

        # Start transport server
        self._transport_task = asyncio.create_task(self.transport.run())

        # Start REST server
        runner = web.AppRunner(self.rest_app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.rest_port)
        await site.start()
        logger.info(f"REST server running on http://0.0.0.0:{self.rest_port}")

        try:
            # Wait for stop event
            await self._stop_event.wait()
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            await runner.cleanup()
            await self.transport.stop()
            await self.redis_broker.disconnect()
            if self._redis_subscribe_task:
                self._redis_subscribe_task.cancel()
                try:
                    await self._redis_subscribe_task
                except asyncio.CancelledError:
                    pass
            if self._transport_task:
                try:
                    await asyncio.wait_for(self._transport_task, timeout=2)
                except asyncio.TimeoutError:
                    self._transport_task.cancel()
                    try:
                        await self._transport_task
                    except asyncio.CancelledError:
                        pass
            logger.info("Server shut down")

    async def stop(self) -> None:
        """Stop the server."""
        self._stop_event.set()


async def main():
    """Entry point for running the server."""
    server = NotificationServer()
    await server.run()


if __name__ == '__main__':
    asyncio.run(main())
