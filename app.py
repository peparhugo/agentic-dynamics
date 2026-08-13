"""
WebSocket-based notification server with REST health endpoint.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict
import websockets
from websockets.exceptions import ConnectionClosed
from aiohttp import web


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


def create_message(msg_type: str, payload: dict) -> dict:
    """Create a properly formatted message."""
    return {
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.utcnow().isoformat(),
    }


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
                    await registry.broadcast(
                        create_message("broadcast", message.get("payload", {})),
                        channel=channel
                    )
                elif msg_type == "direct":
                    target_client_id = message.get("target_client_id")
                    if target_client_id:
                        await registry.send_direct(
                            target_client_id,
                            create_message("direct", message.get("payload", {})),
                        )
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


async def start_servers():
    """Start both WebSocket and REST servers."""
    async with websockets.serve(websocket_handler, "localhost", 8765):
        app = web.Application()
        app.router.add_get("/health", health_handler)
        app.router.add_get("/channels", channels_handler)
        app.router.add_get("/channels/{name}/subscribers", channel_subscribers_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "localhost", 8766)
        await site.start()

        print("WebSocket server running on ws://localhost:8765")
        print("REST API running on http://localhost:8766")

        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(start_servers())
