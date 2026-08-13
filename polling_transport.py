"""HTTP polling transport implementation (for demonstration)."""

import asyncio
import logging
import json
from typing import Optional, Callable, Any, Dict
from aiohttp import web

from transport import BaseTransport
from message_handler import Message

logger = logging.getLogger(__name__)


class PollingTransport(BaseTransport):
    """HTTP polling transport implementation for demonstration."""

    def __init__(
        self,
        host: str = 'localhost',
        port: int = 8766,
        on_client_connect: Optional[Callable] = None,
        on_client_disconnect: Optional[Callable] = None,
        on_client_message: Optional[Callable] = None,
        client_registry: Optional[Any] = None
    ):
        self.host = host
        self.port = port
        self.on_client_connect = on_client_connect
        self.on_client_disconnect = on_client_disconnect
        self.on_client_message = on_client_message
        self.client_registry = client_registry
        self.app = web.Application()
        self._setup_routes()
        self._stop_event = asyncio.Event()
        self._client_queues: Dict[str, asyncio.Queue] = {}
        self._runner: Optional[web.AppRunner] = None

    def _setup_routes(self):
        """Setup polling routes."""
        self.app.router.add_post('/poll/connect', self._handle_connect)
        self.app.router.add_get('/poll/{client_id}/messages', self._handle_receive)
        self.app.router.add_post('/poll/{client_id}/send', self._handle_send)
        self.app.router.add_post('/poll/{client_id}/disconnect', self._handle_disconnect)

    async def _handle_connect(self, request: web.Request) -> web.Response:
        """Handle client connection."""
        client_id = self.client_registry.register(None)
        self._client_queues[client_id] = asyncio.Queue()
        logger.info(f"Client connected via polling: {client_id}")

        if self.on_client_connect:
            await self.on_client_connect(client_id)

        return web.json_response({'client_id': client_id})

    async def _handle_receive(self, request: web.Request) -> web.Response:
        """Handle client receiving messages."""
        client_id = request.match_info['client_id']

        if client_id not in self._client_queues:
            return web.json_response({'error': 'Unknown client'}, status=404)

        try:
            message = await asyncio.wait_for(
                self._client_queues[client_id].get(),
                timeout=30
            )
            return web.json_response(json.loads(message.to_json()))
        except asyncio.TimeoutError:
            return web.json_response({'type': 'heartbeat'})

    async def _handle_send(self, request: web.Request) -> web.Response:
        """Handle client sending messages."""
        client_id = request.match_info['client_id']

        if client_id not in self._client_queues:
            return web.json_response({'error': 'Unknown client'}, status=404)

        try:
            data = await request.json()
            message = Message.from_json(json.dumps(data))

            if self.on_client_message:
                await self.on_client_message(client_id, message)

            return web.json_response({'status': 'ok'})
        except Exception as e:
            logger.error(f"Error handling send from {client_id}: {e}")
            return web.json_response({'error': str(e)}, status=400)

    async def _handle_disconnect(self, request: web.Request) -> web.Response:
        """Handle client disconnection."""
        client_id = request.match_info['client_id']

        if client_id in self._client_queues:
            del self._client_queues[client_id]
        self.client_registry.unregister(client_id)
        logger.info(f"Client disconnected via polling: {client_id}")

        if self.on_client_disconnect:
            await self.on_client_disconnect(client_id)

        return web.json_response({'status': 'ok'})

    async def on_connect(self, client_id: str) -> None:
        """Called when a client connects (no-op for polling)."""
        pass

    async def on_disconnect(self, client_id: str) -> None:
        """Called when a client disconnects (no-op for polling)."""
        pass

    async def send_message(self, client_id: str, message: Message) -> None:
        """Send a message to a specific client."""
        if client_id in self._client_queues:
            try:
                await self._client_queues[client_id].put(message)
            except Exception as e:
                logger.error(f"Error queuing message for {client_id}: {e}")

    async def broadcast(self, message: Message, channel: str = None) -> None:
        """Broadcast a message to all clients or channel subscribers."""
        if channel:
            client_ids = self.client_registry.get_channel_subscribers(channel)
        else:
            client_ids = list(self.client_registry.get_all_clients().keys())

        for client_id in client_ids:
            await self.send_message(client_id, message)

    async def run(self) -> None:
        """Start the polling transport server."""
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        logger.info(f"Polling transport running on http://{self.host}:{self.port}")

        try:
            await self._stop_event.wait()
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            if self._runner:
                await self._runner.cleanup()
            logger.info("Polling transport shut down")

    async def stop(self) -> None:
        """Stop the polling transport server."""
        self._stop_event.set()
