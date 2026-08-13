"""
Notification server with a pluggable transport layer.

Accepts client connections over whatever Transport is configured (a
WebSocketTransport by default — see transport.py), assigns each client a
unique ID, and lets clients broadcast JSON notification messages to every
connected client, to a channel's subscribers, or directly to one other
client. The routing/business logic here never touches a wire protocol
directly — it only calls the small Transport contract (on_connect,
on_disconnect, send_message, broadcast), so new transports (SSE, polling,
raw TCP, ...) can be added without modifying this file. Also exposes a
plain HTTP GET /health endpoint (served over the same socket, for the
WebSocket transport) that reports the number of currently connected
clients.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid

from websockets.asyncio.server import serve

from messages import MESSAGE_TYPES, make_message
from persistence import MessageStore
from redis_backbone import RedisBackbone
from transport import BaseTransport, ClientRegistry, WebSocketTransport, create_transport

__all__ = [
    "MESSAGE_TYPES",
    "ChannelRegistry",
    "ClientRegistry",
    "NotificationServer",
    "make_message",
    "BaseTransport",
    "WebSocketTransport",
    "create_app",
    "run_server",
]


class ChannelRegistry:
    """Asyncio-safe registry of channel -> subscribed client id sets."""

    def __init__(self) -> None:
        self._channels: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            self._channels.setdefault(channel, set()).add(client_id)

    async def unsubscribe(self, client_id: str, channel: str) -> None:
        async with self._lock:
            subs = self._channels.get(channel)
            if subs is None:
                return
            subs.discard(client_id)
            if not subs:
                del self._channels[channel]

    async def remove_client(self, client_id: str) -> None:
        async with self._lock:
            emptied = []
            for channel, subs in self._channels.items():
                subs.discard(client_id)
                if not subs:
                    emptied.append(channel)
            for channel in emptied:
                del self._channels[channel]

    async def channel_counts(self) -> dict[str, int]:
        async with self._lock:
            return {name: len(subs) for name, subs in self._channels.items()}

    async def subscribers(self, channel: str) -> list[str]:
        async with self._lock:
            return sorted(self._channels.get(channel, set()))


class NotificationServer:
    def __init__(
        self,
        redis_backbone: RedisBackbone | None = None,
        message_store: MessageStore | None = None,
        server_id: str | None = None,
        transport: BaseTransport | None = None,
    ) -> None:
        self.channels = ChannelRegistry()
        self.redis_backbone = redis_backbone
        self.message_store = message_store
        self.server_id = server_id or str(uuid.uuid4())
        self.transport = transport or create_transport(self, on_stale_client=self.channels.remove_client)

    @property
    def registry(self) -> ClientRegistry:
        return self.transport.registry

    @property
    def handler(self):
        return self.transport.handler

    @property
    def process_request(self):
        return self.transport.process_request

    async def start(self) -> None:
        """Begin subscribing to the Redis backbone, if configured."""
        if self.redis_backbone is not None:
            await self.redis_backbone.start(self._on_redis_message)

    async def stop(self) -> None:
        if self.redis_backbone is not None:
            await self.redis_backbone.stop()

    async def _deliver_broadcast_local(self, message: dict, channel: str | None) -> int:
        target_ids = set(await self.channels.subscribers(channel)) if channel is not None else None
        return await self.transport.broadcast(message, target_ids)

    async def _deliver_direct_local(self, client_id: str, message: dict) -> bool:
        return await self.transport.send_message(client_id, message)

    async def _on_redis_message(self, envelope: dict) -> None:
        # Messages this same instance published were already delivered to
        # its local clients synchronously — skip to avoid double delivery.
        if envelope.get("_origin") == self.server_id:
            return
        message = envelope.get("message")
        if not isinstance(message, dict):
            return
        if envelope.get("kind") == "direct":
            await self._deliver_direct_local(envelope.get("target_client_id"), message)
        else:
            await self._deliver_broadcast_local(message, envelope.get("channel"))

    async def broadcast(
        self, payload: dict, msg_type: str = "broadcast", channel: str | None = None
    ) -> int:
        message = make_message(msg_type, payload, channel=channel)
        if self.message_store is not None:
            await self.message_store.save(message)
        sent = await self._deliver_broadcast_local(message, channel)
        if self.redis_backbone is not None:
            await self.redis_backbone.publish(
                {
                    "_origin": self.server_id,
                    "kind": "broadcast",
                    "channel": channel,
                    "message": message,
                }
            )
        return sent

    async def send_direct(self, client_id: str, payload: dict) -> bool:
        message = make_message("direct", payload)
        if self.message_store is not None:
            await self.message_store.save(message)
        delivered = await self._deliver_direct_local(client_id, message)
        if not delivered and self.redis_backbone is not None:
            await self.redis_backbone.publish(
                {
                    "_origin": self.server_id,
                    "kind": "direct",
                    "target_client_id": client_id,
                    "message": message,
                }
            )
        return delivered

    async def _handle_incoming(self, client_id: str, raw: str | bytes) -> None:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            await self._send_error(client_id, "invalid JSON")
            return

        if not isinstance(data, dict):
            await self._send_error(client_id, "message must be a JSON object")
            return

        msg_type = data.get("type")
        payload = data.get("payload", {})
        channel = data.get("channel")

        if msg_type not in MESSAGE_TYPES:
            await self._send_error(client_id, f"unsupported message type: {msg_type!r}")
            return

        if msg_type == "subscribe":
            if not channel or not isinstance(channel, str):
                await self._send_error(client_id, "subscribe requires a 'channel' field")
                return
            await self.channels.subscribe(client_id, channel)
            await self._send_ack(client_id, "subscribed", channel)
        elif msg_type == "unsubscribe":
            if not channel or not isinstance(channel, str):
                await self._send_error(client_id, "unsubscribe requires a 'channel' field")
                return
            await self.channels.unsubscribe(client_id, channel)
            await self._send_ack(client_id, "unsubscribed", channel)
        elif msg_type == "broadcast":
            await self.broadcast(payload, channel=channel)
        elif msg_type == "direct":
            target_id = payload.get("client_id") if isinstance(payload, dict) else None
            if not target_id:
                await self._send_error(client_id, "direct message requires payload.client_id")
                return
            delivered = await self.send_direct(target_id, payload.get("payload", {}))
            if not delivered:
                await self._send_error(client_id, f"unknown client_id: {target_id!r}")
        elif msg_type == "system":
            # System messages from clients are acknowledged but not rebroadcast.
            await self.transport.send_message(
                client_id, make_message("system", {"event": "ack", "received": payload})
            )

    async def _send_error(self, client_id: str, error: str) -> None:
        await self.transport.send_message(
            client_id, make_message("system", {"event": "error", "message": error})
        )

    async def _send_ack(self, client_id: str, event: str, channel: str) -> None:
        delivered = await self.transport.send_message(
            client_id, make_message("system", {"event": event, "channel": channel})
        )
        if not delivered:
            await self.channels.remove_client(client_id)


def create_app(
    redis_url: str | None = None,
    database_url: str | None = None,
    server_id: str | None = None,
) -> NotificationServer:
    redis_url = redis_url if redis_url is not None else os.environ.get("REDIS_URL")
    database_url = database_url if database_url is not None else os.environ.get("DATABASE_URL", "messages.db")
    server_id = server_id or str(uuid.uuid4())

    redis_backbone = None
    if redis_url:
        import redis.asyncio as redis_asyncio

        redis_backbone = RedisBackbone(redis_asyncio.from_url(redis_url), server_id=server_id)

    message_store = MessageStore(database_url)
    return NotificationServer(
        redis_backbone=redis_backbone, message_store=message_store, server_id=server_id
    )


async def run_server(host: str = "localhost", port: int = 8765) -> None:
    app = create_app()
    await app.start()
    try:
        async with serve(app.handler, host, port, process_request=app.process_request):
            await asyncio.Future()  # run forever
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(run_server())
