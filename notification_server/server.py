"""Transport-agnostic notification server.

Accepts client connections via a pluggable `BaseTransport`, assigns each
client a unique ID, and routes JSON messages between clients (broadcast /
direct / system). `NotificationServer` never touches a raw connection object
-- all delivery goes through `self.transport`, so swapping the transport
(WebSocket, SSE, polling, raw TCP, ...) never requires touching the routing
logic below.

Redis pub/sub is the message backbone: outgoing messages are published to a
Redis channel rather than delivered directly, and a background worker task
subscribes to that channel namespace and delivers each message to whichever
locally-connected clients should receive it. Multiple `NotificationServer`
instances pointed at the same Redis backend therefore share one backbone --
a client connected to instance A can receive a broadcast sent by a client on
instance B. Client presence and channel-subscription state is mirrored into
Redis too, so it is shared across instances and survives a server restart.
Every routed message is also persisted to SQLite for history, queryable via
GET /messages.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Any

from websockets.asyncio.server import serve

from .broker import RedisBroker
from .config import database_path
from .messages import Message, MessageValidationError, utc_now_iso
from .persistence import MessageStore
from .registry import ClientRegistry, ChannelRegistry
from .state import RedisClientState
from .transport import BaseTransport, build_transport

logger = logging.getLogger("notification_server")

NS_PREFIX = "ns"
BROADCAST_CHANNEL = f"{NS_PREFIX}:broadcast"
CHANNEL_PREFIX = f"{NS_PREFIX}:channel:"
DIRECT_PREFIX = f"{NS_PREFIX}:direct:"
SUBSCRIBE_PATTERN = f"{NS_PREFIX}:*"


def _redis_channel_for(channel: str | None) -> str:
    return f"{CHANNEL_PREFIX}{channel}" if channel else BROADCAST_CHANNEL


def _redis_channel_for_direct(target_id: str) -> str:
    return f"{DIRECT_PREFIX}{target_id}"


class NotificationServer:
    """Owns the client registry and implements the connection/message logic."""

    def __init__(
        self,
        transport: BaseTransport | None = None,
        broker: RedisBroker | None = None,
        store: MessageStore | None = None,
        state: RedisClientState | None = None,
    ) -> None:
        self.registry = ClientRegistry()
        self.channel_registry = ChannelRegistry()
        self.broker = broker if broker is not None else RedisBroker()
        self.store = store if store is not None else MessageStore(database_path())
        self.state = state if state is not None else RedisClientState(self.broker.client)
        self.transport = transport if transport is not None else build_transport()
        self.transport.bind(self)

    async def start(self) -> None:
        """Start the Redis delivery worker. Must be awaited before the
        server accepts connections, so no early publish is missed."""
        await self.broker.start(SUBSCRIBE_PATTERN, self._on_redis_message)

    async def close(self) -> None:
        await self.broker.stop()
        self.store.close()

    async def health_payload(self) -> dict[str, Any]:
        return {"status": "ok", "connected_clients": await self.state.count()}

    async def channels_payload(self) -> dict[str, int]:
        return await self.state.all_channels()

    async def handler(self, connection: Any) -> None:
        """Entry point for the transport's connection lifecycle (e.g. passed
        directly to `websockets.serve` for `WebSocketTransport`)."""
        await self.transport.handler(connection)

    async def process_request(self, connection: Any, request: Any) -> Any:
        """Entry point for the transport's HTTP hook, where the transport
        exposes one (e.g. `WebSocketTransport`'s `process_request` handshake
        hook that serves /health, /channels, /messages)."""
        return await self.transport.process_request(connection, request)

    async def send_to(self, client_id: str, message: Message) -> None:
        await self.transport.send_message(client_id, message)

    async def send_error(self, client_id: str, error: str) -> None:
        await self.send_to(
            client_id,
            Message(type="system", payload={"error": error}, timestamp=utc_now_iso()),
        )

    async def _fan_out(self, sender_id: str, message: Message) -> None:
        envelope = Message(
            type=message.type,
            payload={"from": sender_id, **message.payload},
            timestamp=message.timestamp,
            channel=message.channel,
        )
        self.store.save(envelope)
        await self.broker.publish(_redis_channel_for(message.channel), envelope.to_json())

    async def _on_redis_message(self, redis_channel: str, data: str) -> None:
        """The delivery worker: deliver a message received from Redis to
        whichever clients are connected to *this* instance."""
        try:
            message = Message.from_json(data)
        except MessageValidationError:
            return

        if redis_channel.startswith(DIRECT_PREFIX):
            target_id = redis_channel[len(DIRECT_PREFIX):]
            await self.transport.send_message(target_id, message)
            return

        recipients = self.channel_registry.subscribers(message.channel) if message.channel else None
        await self.transport.broadcast(recipients, message)

    async def _handle_subscribe(self, sender_id: str, message: Message) -> None:
        channel = message.payload.get("channel")
        if not channel:
            await self.send_error(sender_id, "'subscribe' messages require a 'channel' in payload")
            return
        self.channel_registry.subscribe(channel, sender_id)
        await self.state.subscribe(channel, sender_id)
        await self.send_to(
            sender_id,
            Message(type="system", payload={"event": "subscribed", "channel": channel}, timestamp=utc_now_iso()),
        )

    async def _handle_unsubscribe(self, sender_id: str, message: Message) -> None:
        channel = message.payload.get("channel")
        if not channel:
            await self.send_error(sender_id, "'unsubscribe' messages require a 'channel' in payload")
            return
        self.channel_registry.unsubscribe(channel, sender_id)
        await self.state.unsubscribe(channel, sender_id)
        await self.send_to(
            sender_id,
            Message(type="system", payload={"event": "unsubscribed", "channel": channel}, timestamp=utc_now_iso()),
        )

    async def route(self, sender_id: str, message: Message) -> None:
        if message.type in ("broadcast", "system"):
            await self._fan_out(sender_id, message)

        elif message.type == "subscribe":
            await self._handle_subscribe(sender_id, message)

        elif message.type == "unsubscribe":
            await self._handle_unsubscribe(sender_id, message)

        elif message.type == "direct":
            target_id = message.payload.get("target")
            if not target_id:
                await self.send_error(sender_id, "'direct' messages require a 'target' client id in payload")
                return
            if not await self.state.is_connected(target_id):
                await self.send_error(sender_id, f"unknown target client '{target_id}'")
                return
            envelope = Message(
                type="direct",
                payload={"from": sender_id, **message.payload},
                timestamp=message.timestamp,
            )
            self.store.save(envelope)
            await self.broker.publish(_redis_channel_for_direct(target_id), envelope.to_json())


def build_server(host: str = "localhost", port: int = 8765):
    notification_server = NotificationServer()
    server = serve(
        notification_server.handler,
        host,
        port,
        process_request=notification_server.process_request,
    )
    return notification_server, server


async def run(host: str = "localhost", port: int = 8765) -> None:
    notification_server, server = build_server(host, port)
    await notification_server.start()
    try:
        async with server:
            logger.info("notification server listening on ws://%s:%d", host, port)
            await asyncio.get_running_loop().create_future()
    finally:
        await notification_server.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="WebSocket notification server")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(args.host, args.port))


if __name__ == "__main__":
    main()
