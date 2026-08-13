"""WebSocket-based notification server.

Clients connect over WebSocket, are assigned a unique ID, and can broadcast
JSON messages to every other connected client or send one directly to a
specific client ID. A plain HTTP GET /health is served from the same port
for monitoring.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from typing import Any, Iterable
from urllib.parse import parse_qs, unquote, urlsplit

import websockets
from websockets.asyncio.server import ServerConnection
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from .messages import InvalidMessage, build_message, encode, parse_message
from .redis_bus import RedisBus
from .registry import ClientRegistry
from .store import MessageStore

logger = logging.getLogger("notification_server")

HEALTH_PATH = "/health"
CHANNELS_PATH = "/channels"
MESSAGES_PATH = "/messages"
CHANNEL_SUBSCRIBERS_RE = re.compile(r"^/channels/([^/]+)/subscribers$")

DEFAULT_MESSAGES_LIMIT = 50
MAX_MESSAGES_LIMIT = 500

# Message types that represent actual notification content, as opposed to
# connection control-plane chatter (system/subscribe/unsubscribe). These are
# the ones persisted to SQLite and distributed over the Redis bus.
CONTENT_TYPES = {"broadcast", "direct"}


class NotificationServer:
    """Ties together the client registry, the Redis pub/sub bus, and SQLite history.

    `redis_client` and `db_path` are both optional so existing single-instance,
    in-memory behavior keeps working with no configuration at all: pass neither
    and every message stays local, exactly like before Redis was introduced.
    Pass a redis(.asyncio)-compatible client to fan messages out to other
    server instances sharing the same broker, and/or a db_path to persist
    message history to SQLite.
    """

    def __init__(
        self,
        redis_client: Any = None,
        db_path: str | None = None,
        server_id: str | None = None,
    ) -> None:
        self.server_id = server_id or uuid.uuid4().hex
        self.registry = ClientRegistry(redis_client=redis_client, server_id=self.server_id)
        self.bus = RedisBus(redis_client) if redis_client is not None else None
        self.store = MessageStore(db_path or os.environ.get("DATABASE_URL", "notification_server.db"))
        self._started = False

    async def start(self) -> None:
        """Idempotently subscribe to the Redis bus, if one is configured."""
        if self.bus is not None and not self._started:
            await self.bus.start(self._on_bus_message)
            self._started = True

    async def close(self) -> None:
        if self.bus is not None:
            await self.bus.stop()
        self.store.close()

    async def process_request(self, connection: ServerConnection, request: Request) -> Response | None:
        split = urlsplit(request.path)
        path = split.path
        query = parse_qs(split.query)

        if path == HEALTH_PATH:
            body = json.dumps({"connected_clients": await self.registry.global_count()})
            return self._json_response(connection, 200, body)

        if path == CHANNELS_PATH:
            channels = await self.registry.global_channels_snapshot()
            body = json.dumps({
                "channels": [
                    {"name": name, "subscribers": count}
                    for name, count in sorted(channels.items())
                ],
            })
            return self._json_response(connection, 200, body)

        if path == MESSAGES_PATH:
            limit = self._parse_query_int(query, "limit", DEFAULT_MESSAGES_LIMIT, minimum=1, maximum=MAX_MESSAGES_LIMIT)
            offset = self._parse_query_int(query, "offset", 0, minimum=0)
            messages = await asyncio.to_thread(self.store.get_messages, limit, offset)
            body = json.dumps({"messages": messages, "limit": limit, "offset": offset})
            return self._json_response(connection, 200, body)

        match = CHANNEL_SUBSCRIBERS_RE.match(path)
        if match:
            name = unquote(match.group(1))
            subscribers = await self.registry.global_subscribers(name)
            body = json.dumps({"channel": name, "subscribers": subscribers})
            return self._json_response(connection, 200, body)

        return None

    @staticmethod
    def _parse_query_int(query: dict, key: str, default: int, *, minimum: int, maximum: int | None = None) -> int:
        raw = query.get(key, [None])[0]
        if raw is None:
            value = default
        else:
            try:
                value = int(raw)
            except ValueError:
                value = default
        value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value

    @staticmethod
    def _json_response(connection: ServerConnection, status: int, body: str) -> Response:
        response = connection.respond(status, body)
        response.headers["Content-Type"] = "application/json"
        return response

    async def handler(self, websocket: ServerConnection) -> None:
        await self.start()
        client_id = await self.registry.register(websocket)
        logger.info("client %s connected", client_id)
        await self._send(websocket, build_message("system", {
            "event": "connected",
            "client_id": client_id,
        }))
        await self._distribute(
            build_message("system", {
                "event": "client_joined",
                "client_id": client_id,
                "connected_clients": await self.registry.global_count(),
            }),
            exclude=(client_id,),
        )
        try:
            async for raw in websocket:
                await self._dispatch(client_id, websocket, raw)
        except ConnectionClosed:
            pass
        finally:
            await self.registry.unregister(client_id)
            logger.info("client %s disconnected", client_id)
            await self._distribute(
                build_message("system", {
                    "event": "client_left",
                    "client_id": client_id,
                    "connected_clients": await self.registry.global_count(),
                })
            )

    async def _dispatch(self, client_id: str, websocket: Any, raw: str) -> None:
        try:
            message = parse_message(raw)
        except InvalidMessage as exc:
            await self._send(websocket, build_message("system", {
                "event": "error",
                "detail": str(exc),
            }))
            return

        msg_type = message["type"]
        payload = message["payload"]

        if msg_type == "broadcast":
            channel = payload.get("channel")
            out_message = build_message("broadcast", {**payload, "from": client_id})
            await self._persist(out_message, channel)
            await self._distribute(out_message, channel=channel)
        elif msg_type == "direct":
            await self._handle_direct(client_id, payload)
        elif msg_type == "subscribe":
            await self._handle_subscribe(client_id, websocket, payload)
        elif msg_type == "unsubscribe":
            await self._handle_unsubscribe(client_id, websocket, payload)
        else:  # "system" — reserved for server-originated messages
            await self._send(websocket, build_message("system", {
                "event": "error",
                "detail": "clients may not send system messages",
            }))

    async def _handle_subscribe(self, client_id: str, websocket: Any, payload: dict) -> None:
        channel = payload.get("channel")
        if not isinstance(channel, str) or not channel:
            await self._send(websocket, build_message("system", {
                "event": "error",
                "detail": "subscribe requires a non-empty 'channel' string",
            }))
            return
        await self.registry.subscribe(client_id, channel)
        await self._send(websocket, build_message("system", {
            "event": "subscribed",
            "channel": channel,
            "client_id": client_id,
        }))

    async def _handle_unsubscribe(self, client_id: str, websocket: Any, payload: dict) -> None:
        channel = payload.get("channel")
        if not isinstance(channel, str) or not channel:
            await self._send(websocket, build_message("system", {
                "event": "error",
                "detail": "unsubscribe requires a non-empty 'channel' string",
            }))
            return
        await self.registry.unsubscribe(client_id, channel)
        await self._send(websocket, build_message("system", {
            "event": "unsubscribed",
            "channel": channel,
            "client_id": client_id,
        }))

    async def _handle_direct(self, sender_id: str, payload: dict) -> None:
        target_id = payload.get("target")
        # `exists` (not just "connected to this instance") is what lets a
        # direct message find its target when the two clients are on
        # different server instances sharing the same Redis backbone.
        target_exists = await self.registry.exists(target_id) if target_id else False
        if not target_exists:
            sender_ws = await self.registry.get(sender_id)
            if sender_ws is not None:
                await self._send(sender_ws, build_message("system", {
                    "event": "error",
                    "detail": f"unknown target: {target_id!r}",
                }))
            return
        message = build_message("direct", {**payload, "from": sender_id})
        await self._persist(message, channel=None)
        await self._distribute(message, target=target_id)

    async def _distribute(
        self,
        message: dict,
        *,
        channel: str | None = None,
        target: str | None = None,
        exclude: Iterable[str] = (),
    ) -> None:
        """Route `message` to its recipients, via the Redis bus if one is configured.

        With a bus, this instance only ever publishes; delivery to local
        sockets happens in `_deliver_locally`, invoked for every instance
        (this one included) when the envelope comes back off the
        subscription. Without a bus, delivery happens immediately, in place.
        """
        envelope = {"message": message, "channel": channel, "target": target, "exclude": list(exclude)}
        if self.bus is not None:
            await self.bus.publish(envelope)
        else:
            await self._deliver_locally(envelope)

    async def _on_bus_message(self, envelope: dict) -> None:
        await self._deliver_locally(envelope)

    async def _deliver_locally(self, envelope: dict) -> None:
        message = envelope["message"]
        channel = envelope.get("channel")
        target = envelope.get("target")
        exclude = envelope.get("exclude") or ()

        if target:
            websocket = await self.registry.get(target)
            if websocket is not None:
                await self._send(websocket, message)
            return

        text = encode(message)
        if channel:
            await self.registry.broadcast_channel(text, channel, exclude=exclude)
        else:
            await self.registry.broadcast(text, exclude=exclude)

    async def _persist(self, message: dict, channel: str | None) -> None:
        if message["type"] not in CONTENT_TYPES:
            return
        await asyncio.to_thread(
            self.store.save_message,
            message["type"],
            message["payload"],
            message["timestamp"],
            channel,
        )

    @staticmethod
    async def _send(websocket: Any, message: dict) -> None:
        try:
            await websocket.send(encode(message))
        except ConnectionClosed:
            pass


def create_app() -> NotificationServer:
    redis_client = None
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        import redis.asyncio as redis_asyncio
        redis_client = redis_asyncio.from_url(redis_url)
    db_path = os.environ.get("DATABASE_URL", "notification_server.db")
    return NotificationServer(redis_client=redis_client, db_path=db_path)


async def run_server(host: str = "localhost", port: int = 8765) -> None:
    app = create_app()
    await app.start()
    try:
        async with websockets.serve(app.handler, host, port, process_request=app.process_request):
            logger.info("notification server listening on %s:%s", host, port)
            await asyncio.Future()
    finally:
        await app.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
