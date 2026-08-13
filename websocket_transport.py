"""WebSocket transport implementation."""

import asyncio
import logging
from typing import Optional, Callable, Any
import websockets
from websockets.server import WebSocketServerProtocol

from transport import BaseTransport
from message_handler import Message, MessageHandler

logger = logging.getLogger(__name__)


class WebSocketTransport(BaseTransport):
    """WebSocket transport implementation."""

    def __init__(
        self,
        host: str = 'localhost',
        port: int = 8765,
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
        self.ws_server: Optional[websockets.server.WebSocketServer] = None
        self._stop_event = asyncio.Event()

    async def handle_client(
        self,
        websocket: WebSocketServerProtocol,
        path: str
    ) -> None:
        """Handle new WebSocket client connection."""
        client_id = self.client_registry.register(websocket)
        logger.info(f"Client connected: {client_id}")

        try:
            # Notify server of new connection
            await self.on_client_connect(client_id)

            # Listen for messages from this client
            async for message_data in websocket:
                if MessageHandler.validate_message(message_data):
                    message = Message.from_json(message_data)
                    if self.on_client_message:
                        await self.on_client_message(client_id, message)
                else:
                    logger.warning(f"Invalid message from {client_id}: {message_data}")

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
        finally:
            self.client_registry.unregister(client_id)
            await self.on_client_disconnect(client_id)

    async def on_connect(self, client_id: str) -> None:
        """Called when a client connects (no-op for WebSocket)."""
        pass

    async def on_disconnect(self, client_id: str) -> None:
        """Called when a client disconnects (no-op for WebSocket)."""
        pass

    async def send_message(self, client_id: str, message: Message) -> None:
        """Send a message to a specific client."""
        client = self.client_registry.get_client(client_id)
        if client:
            try:
                await client.send(message.to_json())
            except websockets.exceptions.ConnectionClosed:
                logger.debug("Target websocket already closed")
            except Exception as e:
                logger.error(f"Error sending message: {e}")

    async def broadcast(self, message: Message, channel: str = None) -> None:
        """Broadcast a message to all clients or channel subscribers."""
        if channel:
            clients = self.client_registry.get_clients_in_channel(channel)
        else:
            clients = self.client_registry.get_all_clients()

        if not clients:
            return

        tasks = [
            self._send_to_websocket(websocket, message)
            for websocket in clients.values()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error sending broadcast: {result}")

    async def _send_to_websocket(
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
        """Start the WebSocket server."""
        self.ws_server = await websockets.serve(
            self.handle_client,
            self.host,
            self.port
        )
        logger.info(f"WebSocket server running on ws://{self.host}:{self.port}")

        try:
            await self._stop_event.wait()
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            if self.ws_server:
                self.ws_server.close()
                await self.ws_server.wait_closed()
            logger.info("WebSocket transport shut down")

    async def stop(self) -> None:
        """Stop the WebSocket server."""
        self._stop_event.set()
