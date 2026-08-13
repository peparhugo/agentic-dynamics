"""WebSocket-based notification server with REST health endpoint."""

import asyncio
import json
import logging
from typing import Optional
import websockets
from websockets.server import WebSocketServerProtocol
from aiohttp import web

from client_registry import ClientRegistry
from message_handler import Message, MessageHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NotificationServer:
    """Main WebSocket notification server."""

    def __init__(
        self,
        ws_host: str = 'localhost',
        ws_port: int = 8765,
        rest_port: int = 8080
    ):
        self.ws_host = ws_host
        self.ws_port = ws_port
        self.rest_port = rest_port
        self.client_registry = ClientRegistry()
        self.rest_app = web.Application()
        self._setup_rest_routes()
        self.ws_server: Optional[websockets.server.WebSocketServer] = None
        self._stop_event = asyncio.Event()

    def _setup_rest_routes(self):
        """Setup REST API routes."""
        self.rest_app.router.add_get('/health', self._health_handler)
        self.rest_app.router.add_get('/channels', self._channels_handler)
        self.rest_app.router.add_get('/channels/{name}/subscribers', self._channel_subscribers_handler)

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

    async def handle_client(
        self,
        websocket: WebSocketServerProtocol,
        path: str
    ) -> None:
        """Handle new WebSocket client connection."""
        client_id = self.client_registry.register(websocket)
        logger.info(f"Client connected: {client_id}")

        try:
            # Send client ID to the new client
            client_msg = Message('system', {'client_id': client_id})
            await websocket.send(client_msg.to_json())

            # Listen for messages from this client
            async for message_data in websocket:
                if MessageHandler.validate_message(message_data):
                    message = Message.from_json(message_data)
                    await self._handle_message(client_id, message)
                else:
                    logger.warning(f"Invalid message from {client_id}: {message_data}")

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
        finally:
            self.client_registry.unregister(client_id)

    async def _handle_message(self, sender_id: str, message: Message) -> None:
        """Route message to appropriate handler."""
        if message.type == 'broadcast':
            await self._broadcast_message(message)
        elif message.type == 'direct':
            await self._direct_message(message)
        elif message.type == 'subscribe':
            await self._handle_subscribe(sender_id, message)
        elif message.type == 'unsubscribe':
            await self._handle_unsubscribe(sender_id, message)
        elif message.type == 'system':
            logger.info(f"System message from {sender_id}: {message.payload}")

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

    async def _broadcast_message(self, message: Message) -> None:
        """Broadcast message to all connected clients or to channel subscribers."""
        channel = message.payload.get('channel')

        if channel:
            clients = self.client_registry.get_clients_in_channel(channel)
        else:
            clients = self.client_registry.get_all_clients()

        if not clients:
            return

        tasks = [
            self._send_message(websocket, message)
            for websocket in clients.values()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error sending broadcast: {result}")

    async def _direct_message(self, message: Message) -> None:
        """Send direct message to specific client."""
        recipient_id = message.payload.get('recipient_id')
        if not recipient_id:
            logger.warning("Direct message without recipient_id")
            return

        recipient = self.client_registry.get_client(recipient_id)
        if recipient:
            await self._send_message(recipient, message)
        else:
            logger.warning(f"Recipient not found: {recipient_id}")

    async def _send_message(
        self,
        websocket: WebSocketServerProtocol,
        message: Message
    ) -> None:
        """Send message to a specific WebSocket."""
        try:
            await websocket.send(message.to_json())
        except websockets.exceptions.ConnectionClosed:
            logger.debug("Target websocket already closed")
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    async def run(self) -> None:
        """Run both WebSocket and REST servers."""
        # Start WebSocket server
        self.ws_server = await websockets.serve(
            self.handle_client,
            self.ws_host,
            self.ws_port
        )
        logger.info(f"WebSocket server running on ws://{self.ws_host}:{self.ws_port}")

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
            if self.ws_server:
                self.ws_server.close()
                await self.ws_server.wait_closed()
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
