"""
WebSocket notification server with async support.

Features:
- Accept WebSocket connections from clients with unique IDs
- Broadcast messages to all connected clients
- Redis pub/sub for distributed message delivery
- SQLite message persistence with REST history endpoint
- REST health endpoint: GET /health
- Thread-safe client registry using asyncio locks
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Set
from aiohttp import web
import websockets
import logging
from database import MessageDatabase
from redis_broker import RedisBroker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClientRegistry:
    """Thread-safe registry of connected WebSocket clients with channel subscriptions."""

    def __init__(self):
        self.clients: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.subscriptions: Dict[str, Set[str]] = {}  # channel_name -> set of client_ids
        self.client_channels: Dict[str, Set[str]] = {}  # client_id -> set of channel_names
        self.lock = asyncio.Lock()

    async def register(self, client_id: str, websocket: websockets.WebSocketServerProtocol):
        """Register a new client."""
        async with self.lock:
            self.clients[client_id] = websocket
            logger.info(f"Client {client_id} registered. Total clients: {len(self.clients)}")

    async def unregister(self, client_id: str):
        """Remove a client and unsubscribe from all channels."""
        async with self.lock:
            if client_id in self.clients:
                del self.clients[client_id]
                # Remove client from all channels
                if client_id in self.client_channels:
                    for channel in self.client_channels[client_id]:
                        if channel in self.subscriptions:
                            self.subscriptions[channel].discard(client_id)
                            if not self.subscriptions[channel]:
                                del self.subscriptions[channel]
                    del self.client_channels[client_id]
                logger.info(f"Client {client_id} unregistered. Total clients: {len(self.clients)}")

    async def get_client_count(self) -> int:
        """Get the number of connected clients."""
        async with self.lock:
            return len(self.clients)

    async def get_all_clients(self) -> Dict[str, websockets.WebSocketServerProtocol]:
        """Get a copy of all clients."""
        async with self.lock:
            return dict(self.clients)

    async def subscribe(self, client_id: str, channel: str):
        """Subscribe a client to a channel."""
        async with self.lock:
            if client_id not in self.clients:
                return False
            if channel not in self.subscriptions:
                self.subscriptions[channel] = set()
            self.subscriptions[channel].add(client_id)
            if client_id not in self.client_channels:
                self.client_channels[client_id] = set()
            self.client_channels[client_id].add(channel)
            logger.info(f"Client {client_id} subscribed to channel '{channel}'")
            return True

    async def unsubscribe(self, client_id: str, channel: str):
        """Unsubscribe a client from a channel."""
        async with self.lock:
            if channel in self.subscriptions:
                self.subscriptions[channel].discard(client_id)
                if not self.subscriptions[channel]:
                    del self.subscriptions[channel]
            if client_id in self.client_channels:
                self.client_channels[client_id].discard(channel)
            logger.info(f"Client {client_id} unsubscribed from channel '{channel}'")
            return True

    async def get_channels(self) -> Dict[str, int]:
        """Get all active channels and their subscriber counts."""
        async with self.lock:
            return {channel: len(subscribers) for channel, subscribers in self.subscriptions.items()}

    async def get_channel_subscribers(self, channel: str) -> Set[str]:
        """Get all subscriber IDs for a channel."""
        async with self.lock:
            return set(self.subscriptions.get(channel, set()))

    async def broadcast(self, message: dict, channel: str = None):
        """Broadcast a message to clients. If channel is specified, only to subscribers of that channel."""
        clients = await self.get_all_clients()
        if not clients:
            logger.warning("No clients connected for broadcast")
            return

        message_json = json.dumps(message)
        failed_clients = []

        if channel:
            # Send only to subscribers of the specified channel
            subscribers = await self.get_channel_subscribers(channel)
            for client_id in subscribers:
                if client_id in clients:
                    websocket = clients[client_id]
                    try:
                        await websocket.send(message_json)
                    except websockets.exceptions.ConnectionClosed:
                        failed_clients.append(client_id)
                    except Exception as e:
                        logger.error(f"Error sending to {client_id}: {e}")
                        failed_clients.append(client_id)
        else:
            # Send to all connected clients
            for client_id, websocket in clients.items():
                try:
                    await websocket.send(message_json)
                except websockets.exceptions.ConnectionClosed:
                    failed_clients.append(client_id)
                except Exception as e:
                    logger.error(f"Error sending to {client_id}: {e}")
                    failed_clients.append(client_id)

        for client_id in failed_clients:
            await self.unregister(client_id)

    async def broadcast_and_store(self, message: dict, channel: str = None):
        """Broadcast message, store in database, and publish to Redis."""
        await self.broadcast(message, channel)

        # Store message in database
        msg_type = message.get('type', 'unknown')
        payload = message.get('payload', {})
        timestamp = message.get('timestamp', datetime.utcnow().isoformat())
        ch = channel or 'broadcast'
        database.store_message(ch, msg_type, payload, timestamp)

        # Publish to Redis if broker is connected
        if await broker.is_connected():
            await broker.publish(ch, message)


# Global client registry
registry = ClientRegistry()

# Global database and broker
database = MessageDatabase()
broker = RedisBroker()


def create_message(msg_type: str, payload: dict) -> dict:
    """Create a properly formatted message."""
    return {
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.utcnow().isoformat()
    }


async def websocket_handler(websocket: websockets.WebSocketServerProtocol, path: str):
    """Handle WebSocket connections."""
    client_id = str(uuid.uuid4())
    await registry.register(client_id, websocket)
    await broker.store_client_connection(client_id)

    connect_message = create_message("system", {
        "event": "client_connected",
        "client_id": client_id
    })
    await registry.broadcast_and_store(connect_message)

    try:
        async for message_str in websocket:
            try:
                message_data = json.loads(message_str)
                msg_type = message_data.get("type", "broadcast")
                payload = message_data.get("payload", {})

                formatted_message = create_message(msg_type, {
                    **payload,
                    "from_client": client_id
                })

                if msg_type == "broadcast":
                    channel = payload.get("channel")
                    await registry.broadcast_and_store(formatted_message, channel=channel)
                elif msg_type == "direct":
                    target_client = payload.get("to_client")
                    if target_client:
                        clients = await registry.get_all_clients()
                        if target_client in clients:
                            try:
                                await clients[target_client].send(json.dumps(formatted_message))
                                database.store_message("direct", msg_type, formatted_message.get("payload", {}), formatted_message.get("timestamp", ""))
                            except websockets.exceptions.ConnectionClosed:
                                await registry.unregister(target_client)
                elif msg_type == "subscribe":
                    channel = payload.get("channel")
                    if channel:
                        await registry.subscribe(client_id, channel)
                        await broker.store_client_connection(client_id, channel)
                        response = create_message("system", {
                            "event": "subscribed",
                            "channel": channel
                        })
                        await websocket.send(json.dumps(response))
                elif msg_type == "unsubscribe":
                    channel = payload.get("channel")
                    if channel:
                        await registry.unsubscribe(client_id, channel)
                        response = create_message("system", {
                            "event": "unsubscribed",
                            "channel": channel
                        })
                        await websocket.send(json.dumps(response))
                else:
                    logger.warning(f"Unknown message type: {msg_type}")

            except json.JSONDecodeError:
                error_message = create_message("system", {
                    "event": "error",
                    "message": "Invalid JSON format"
                })
                await websocket.send(json.dumps(error_message))
            except Exception as e:
                logger.error(f"Error processing message from {client_id}: {e}")

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await registry.unregister(client_id)
        await broker.remove_client_connection(client_id)
        disconnect_message = create_message("system", {
            "event": "client_disconnected",
            "client_id": client_id
        })
        await registry.broadcast_and_store(disconnect_message)


async def health_handler(request):
    """REST endpoint: GET /health - returns connected client count."""
    count = await registry.get_client_count()
    return web.json_response({
        "status": "ok",
        "connected_clients": count,
        "timestamp": datetime.utcnow().isoformat()
    })


async def channels_handler(request):
    """REST endpoint: GET /channels - list active channels and subscriber counts."""
    channels = await registry.get_channels()
    return web.json_response({
        "channels": channels,
        "timestamp": datetime.utcnow().isoformat()
    })


async def channel_subscribers_handler(request):
    """REST endpoint: GET /channels/{name}/subscribers - list subscriber IDs for a channel."""
    channel_name = request.match_info.get('name')
    subscribers = await registry.get_channel_subscribers(channel_name)
    return web.json_response({
        "channel": channel_name,
        "subscribers": list(subscribers),
        "count": len(subscribers),
        "timestamp": datetime.utcnow().isoformat()
    })


async def messages_handler(request):
    """REST endpoint: GET /messages - retrieve message history."""
    limit = int(request.query.get('limit', 50))
    offset = int(request.query.get('offset', 0))
    channel = request.query.get('channel', None)

    limit = min(limit, 500)  # Cap at 500
    offset = max(offset, 0)

    if channel:
        messages = database.get_messages_by_channel(channel, limit=limit, offset=offset)
    else:
        messages = database.get_messages(limit=limit, offset=offset)

    total_count = database.get_message_count()

    return web.json_response({
        "messages": messages,
        "count": len(messages),
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "timestamp": datetime.utcnow().isoformat()
    })


async def start_websocket_server(host="0.0.0.0", ws_port=8765):
    """Start WebSocket server."""
    async with websockets.serve(websocket_handler, host, ws_port):
        logger.info(f"WebSocket server listening on ws://{host}:{ws_port}")
        await asyncio.Future()


async def start_rest_server(host="0.0.0.0", rest_port=8080):
    """Start REST API server for health endpoint and channel management."""
    app = web.Application()
    app.router.add_get('/health', health_handler)
    app.router.add_get('/channels', channels_handler)
    app.router.add_get('/channels/{name}/subscribers', channel_subscribers_handler)
    app.router.add_get('/messages', messages_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, rest_port)
    await site.start()
    logger.info(f"REST server listening on http://{host}:{rest_port}")

    return runner


async def main():
    """Start both WebSocket and REST servers."""
    ws_host = "0.0.0.0"
    ws_port = 8765
    rest_host = "0.0.0.0"
    rest_port = 8080

    # Try to connect to Redis (graceful degradation if not available)
    try:
        await broker.connect()
    except Exception as e:
        logger.warning(f"Redis broker not available: {e}. Running without Redis pub/sub.")

    ws_task = asyncio.create_task(start_websocket_server(ws_host, ws_port))
    rest_runner = await start_rest_server(rest_host, rest_port)

    try:
        await ws_task
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await rest_runner.cleanup()
        await broker.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped")
