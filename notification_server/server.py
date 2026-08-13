"""WebSocket-based notification server.

Accepts WebSocket connections, assigns each client a unique ID, and routes
JSON messages between clients (broadcast / direct / system). Also exposes a
plain HTTP GET /health endpoint on the same port via the websockets
library's process_request hook, so no extra web framework is needed.

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
import json
import logging
import re
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs, unquote

import websockets
from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response
from websockets.datastructures import Headers

from .broker import RedisBroker
from .config import database_path
from .messages import Message, MessageValidationError, utc_now_iso
from .persistence import MessageStore
from .registry import ClientRegistry, ChannelRegistry
from .state import RedisClientState

logger = logging.getLogger("notification_server")

HEALTH_PATH = "/health"
CHANNELS_PATH = "/channels"
MESSAGES_PATH = "/messages"
CHANNEL_SUBSCRIBERS_RE = re.compile(r"^/channels/([^/]+)/subscribers$")

NS_PREFIX = "ns"
BROADCAST_CHANNEL = f"{NS_PREFIX}:broadcast"
CHANNEL_PREFIX = f"{NS_PREFIX}:channel:"
DIRECT_PREFIX = f"{NS_PREFIX}:direct:"
SUBSCRIBE_PATTERN = f"{NS_PREFIX}:*"

DEFAULT_MESSAGES_LIMIT = 50
MAX_MESSAGES_LIMIT = 500


def _redis_channel_for(channel: str | None) -> str:
    return f"{CHANNEL_PREFIX}{channel}" if channel else BROADCAST_CHANNEL


def _redis_channel_for_direct(target_id: str) -> str:
    return f"{DIRECT_PREFIX}{target_id}"


class NotificationServer:
    """Owns the client registry and implements the connection/message logic."""

    def __init__(
        self,
        broker: RedisBroker | None = None,
        store: MessageStore | None = None,
        state: RedisClientState | None = None,
    ) -> None:
        self.registry = ClientRegistry()
        self.channel_registry = ChannelRegistry()
        self.broker = broker if broker is not None else RedisBroker()
        self.store = store if store is not None else MessageStore(database_path())
        self.state = state if state is not None else RedisClientState(self.broker.client)

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

    def _json_response(self, data: Any) -> Response:
        body = json.dumps(data).encode()
        headers = Headers()
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
        return Response(HTTPStatus.OK.value, HTTPStatus.OK.phrase, headers, body)

    @staticmethod
    def _parse_int(raw: str | None, default: int, minimum: int, maximum: int | None = None) -> int:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return default
        if value < minimum:
            return default
        if maximum is not None and value > maximum:
            return maximum
        return value

    async def process_request(
        self, connection: ServerConnection, request: Request
    ) -> Response | None:
        """Serve a few plain HTTP GET endpoints; let everything else proceed
        to the normal WebSocket handshake."""
        path, _, query_string = request.path.partition("?")
        if path == HEALTH_PATH:
            return self._json_response(await self.health_payload())
        if path == CHANNELS_PATH:
            return self._json_response(await self.channels_payload())
        match = CHANNEL_SUBSCRIBERS_RE.match(path)
        if match:
            channel = unquote(match.group(1))
            return self._json_response(await self.state.channel_subscribers(channel))
        if path == MESSAGES_PATH:
            query = parse_qs(query_string)
            limit = self._parse_int(
                query.get("limit", [None])[0], DEFAULT_MESSAGES_LIMIT, minimum=1, maximum=MAX_MESSAGES_LIMIT
            )
            offset = self._parse_int(query.get("offset", [None])[0], 0, minimum=0)
            return self._json_response(self.store.fetch(limit=limit, offset=offset))
        return None

    async def send_to(self, websocket: Any, message: Message) -> None:
        try:
            await websocket.send(message.to_json())
        except ConnectionClosed:
            pass

    async def send_error(self, websocket: Any, error: str) -> None:
        await self.send_to(
            websocket,
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
            target_ws = self.registry.get(target_id)
            if target_ws is not None:
                await self.send_to(target_ws, message)
            return

        if message.channel:
            recipients = [
                ws
                for ws in (
                    self.registry.get(client_id)
                    for client_id in self.channel_registry.subscribers(message.channel)
                )
                if ws is not None
            ]
        else:
            recipients = self.registry.all_clients()
        websockets.broadcast(recipients, message.to_json())

    async def _handle_subscribe(self, sender_id: str, websocket: Any, message: Message) -> None:
        channel = message.payload.get("channel")
        if not channel:
            await self.send_error(websocket, "'subscribe' messages require a 'channel' in payload")
            return
        self.channel_registry.subscribe(channel, sender_id)
        await self.state.subscribe(channel, sender_id)
        await self.send_to(
            websocket,
            Message(type="system", payload={"event": "subscribed", "channel": channel}, timestamp=utc_now_iso()),
        )

    async def _handle_unsubscribe(self, sender_id: str, websocket: Any, message: Message) -> None:
        channel = message.payload.get("channel")
        if not channel:
            await self.send_error(websocket, "'unsubscribe' messages require a 'channel' in payload")
            return
        self.channel_registry.unsubscribe(channel, sender_id)
        await self.state.unsubscribe(channel, sender_id)
        await self.send_to(
            websocket,
            Message(type="system", payload={"event": "unsubscribed", "channel": channel}, timestamp=utc_now_iso()),
        )

    async def route(self, sender_id: str, websocket: Any, message: Message) -> None:
        if message.type in ("broadcast", "system"):
            await self._fan_out(sender_id, message)

        elif message.type == "subscribe":
            await self._handle_subscribe(sender_id, websocket, message)

        elif message.type == "unsubscribe":
            await self._handle_unsubscribe(sender_id, websocket, message)

        elif message.type == "direct":
            target_id = message.payload.get("target")
            if not target_id:
                await self.send_error(websocket, "'direct' messages require a 'target' client id in payload")
                return
            if not await self.state.is_connected(target_id):
                await self.send_error(websocket, f"unknown target client '{target_id}'")
                return
            envelope = Message(
                type="direct",
                payload={"from": sender_id, **message.payload},
                timestamp=message.timestamp,
            )
            self.store.save(envelope)
            await self.broker.publish(_redis_channel_for_direct(target_id), envelope.to_json())

    async def handler(self, websocket: ServerConnection) -> None:
        client_id = self.registry.add(websocket)
        await self.state.add_client(client_id)
        logger.info("client connected: %s", client_id)
        try:
            await self.send_to(
                websocket,
                Message(
                    type="system",
                    payload={"event": "connected", "client_id": client_id},
                    timestamp=utc_now_iso(),
                ),
            )
            async for raw in websocket:
                try:
                    message = Message.from_json(raw)
                except MessageValidationError as exc:
                    await self.send_error(websocket, str(exc))
                    continue
                await self.route(client_id, websocket, message)
        except ConnectionClosed:
            pass
        finally:
            self.registry.remove(client_id)
            self.channel_registry.unsubscribe_all(client_id)
            await self.state.remove_client(client_id)
            await self.state.unsubscribe_all(client_id)
            logger.info("client disconnected: %s", client_id)
            websockets.broadcast(
                self.registry.all_clients(),
                Message(
                    type="system",
                    payload={"event": "disconnected", "client_id": client_id},
                    timestamp=utc_now_iso(),
                ).to_json(),
            )


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
