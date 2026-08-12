"""Transport implementations for notification delivery."""

from abc import ABC, abstractmethod
import asyncio
import json


class BaseTransport(ABC):
    """Protocol-independent boundary used by :class:`NotificationServer`."""

    @abstractmethod
    def on_connect(self, client_id, client):
        """Register a newly connected client with the transport."""

    @abstractmethod
    def on_disconnect(self, client_id):
        """Remove a disconnected client from the transport."""

    @abstractmethod
    async def send_message(self, client_id, message) -> bool:
        """Send a serialized message to one client."""

    @abstractmethod
    async def broadcast(self, message, client_ids=None) -> list:
        """Send a serialized message to selected clients.

        The return value contains client IDs whose delivery failed.
        """


class _WebSocketAdapter:
    def __init__(self, websocket):
        self.websocket = websocket

    async def send_text(self, message):
        await self.websocket.send(message)

    async def close(self):
        await self.websocket.close()


class WebSocketTransport(BaseTransport):
    """WebSocket implementation of the notification transport boundary."""

    def __init__(self):
        self.clients = {}

    def on_connect(self, client_id, client):
        self.clients[client_id] = client

    def on_disconnect(self, client_id):
        self.clients.pop(client_id, None)

    async def send_message(self, client_id, message) -> bool:
        client = self.clients.get(client_id)
        if client is None:
            return False
        try:
            await client.send_text(message)
            return True
        except Exception:
            return False

    async def broadcast(self, message, client_ids=None) -> list:
        ids = list(self.clients if client_ids is None else client_ids)
        results = await asyncio.gather(
            *(self.send_message(client_id, message) for client_id in ids),
            return_exceptions=False,
        )
        return [client_id for client_id, delivered in zip(ids, results) if not delivered]

    async def handle_connection(self, websocket, server):
        """Run the WebSocket protocol while delegating notification semantics."""
        client_id = server.register(_WebSocketAdapter(websocket))
        try:
            async for raw_message in websocket:
                try:
                    message = json.loads(raw_message)
                    message_type = message.get("type")
                    payload = message.get("payload")
                    if message_type not in {
                        "broadcast", "direct", "system", "subscribe", "unsubscribe"
                    }:
                        continue
                    if not server.allow_message(client_id):
                        await server.send_error(client_id, "rate limit exceeded")
                        continue
                    if message_type in {"subscribe", "unsubscribe"}:
                        channel = message.get("channel")
                        if channel is None and isinstance(payload, dict):
                            channel = payload.get("channel")
                        if channel is None and isinstance(payload, str):
                            channel = payload
                        operation = server.subscribe if message_type == "subscribe" else server.unsubscribe
                        operation(client_id, channel)
                        continue
                    if not isinstance(payload, dict):
                        continue
                except (TypeError, json.JSONDecodeError):
                    continue

                if message_type == "broadcast":
                    await server.broadcast(payload, channel=message.get("channel"))
                elif message_type == "direct":
                    recipient = payload.get("client_id") or payload.get("recipient_id")
                    if recipient:
                        direct_payload = dict(payload)
                        direct_payload.pop("client_id", None)
                        direct_payload.pop("recipient_id", None)
                        await server.send_direct(recipient, direct_payload)
                else:
                    await server.broadcast(payload, "system", message.get("channel"))
        finally:
            server.unregister(client_id)
