"""Transport-agnostic notification server.

Accepts connections over a pluggable Transport (see notification_server/
transport/), assigns each client a unique ID, and supports broadcast /
direct / system / subscribe / unsubscribe JSON messages between clients.
Clients can subscribe to named channels; broadcast messages carrying a
'channel' field in their payload are routed only to that channel's
subscribers, while channel-less broadcasts still reach everyone. Also
exposes plain HTTP endpoints (GET /health, GET /channels, GET /channels/
{name}/subscribers, GET /messages) via the transport, when the transport
supports serving HTTP.

The WebSocket transport is the default (and only one shipped today); a new
transport (SSE, polling, raw TCP, ...) can be added by implementing
BaseTransport without touching any of the routing/registry/presence/
persistence logic below -- this module only ever deals with opaque
"connection" objects and JSON-serializable message dicts, never with the
wire protocol itself. The transport is selected via the TRANSPORT env var,
or by passing an explicit `transport=` instance to NotificationServer.

Redis pub/sub is the message backbone: routed messages are published
to a shared Redis channel rather than delivered directly, and a
background worker task subscribes to that channel and delivers to
whichever locally-connected clients are the intended recipients. This
lets multiple server processes share one notification system -- a
client connected to one instance can receive a message that originated
on another, as long as both point at the same Redis backbone. Channel
subscriptions and connected-client presence are stored in Redis too
(see presence.py), so that state is visible across instances and
outlives any single server process restart. Every broadcast/direct
message is also persisted to SQLite (see store.py) for history,
served back via GET /messages.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote
from uuid import uuid4

import redis.asyncio as redis_asyncio

from notification_server.presence import RedisPresence
from notification_server.registry import ClientRegistry
from notification_server.store import MessageStore
from notification_server.transport import create_transport
from notification_server.transport.base import BaseTransport

logger = logging.getLogger("notification_server")

MESSAGE_TYPES = {"broadcast", "direct", "system", "subscribe", "unsubscribe"}

CHANNEL_SUBSCRIBERS_RE = re.compile(r"^/channels/([^/]+)/subscribers$")

DEFAULT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_DATABASE_URL = "notifications.db"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_message(msg_type: str, payload: dict, **extra) -> dict:
    return {"type": msg_type, "payload": payload, "timestamp": now_iso(), **extra}


def _parse_query_int(query: dict, key: str, default: int, minimum: int, maximum: int) -> int:
    raw = query.get(key, [None])[0]
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


class NotificationServer:
    """Wraps a pluggable Transport with client registry, Redis-backed
    message routing/presence, and SQLite-backed message history."""

    BUS_CHANNEL = "notification_server:bus"

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8765,
        redis_url: str | None = None,
        redis_client=None,
        db_path: str | None = None,
        instance_id: str | None = None,
        transport: BaseTransport | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.registry = ClientRegistry()
        self.transport = transport or create_transport()

        self.redis_url = redis_url or os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)
        self.db_path = db_path or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
        self.instance_id = instance_id or str(uuid4())

        self._redis_client_override = redis_client
        self.redis = None
        self.presence: RedisPresence | None = None
        self.store: MessageStore | None = None
        self._pubsub = None
        self._pubsub_task: asyncio.Task | None = None

        self._client_ids: dict[Any, str] = {}

    async def start(self) -> BaseTransport:
        self.redis = self._redis_client_override or redis_asyncio.Redis.from_url(
            self.redis_url, decode_responses=True
        )
        self.presence = RedisPresence(self.redis)

        self.store = MessageStore(self.db_path)
        await self.store.init()

        self._pubsub = self.redis.pubsub()
        await self._pubsub.subscribe(self.BUS_CHANNEL)
        self._pubsub_task = asyncio.create_task(self._consume_bus())

        self.transport.on_connect(self._handle_connect)
        self.transport.on_message(self._handle_message)
        self.transport.on_disconnect(self._handle_disconnect)
        self.transport.set_http_handler(self._handle_http)
        await self.transport.start(self.host, self.port)
        return self.transport

    def stop(self) -> None:
        self.transport.stop()

    async def wait_closed(self) -> None:
        await self.transport.wait_closed()
        await self._shutdown_bus()

    async def _shutdown_bus(self) -> None:
        if self._pubsub_task is not None:
            self._pubsub_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._pubsub_task
            self._pubsub_task = None
        if self._pubsub is not None:
            await self._pubsub.aclose()
            self._pubsub = None
        if self.redis is not None:
            await self.redis.aclose()

    @property
    def bound_port(self) -> int:
        return self.transport.bound_port

    # -- Redis bus ----------------------------------------------------

    async def _publish(self, envelope: dict) -> None:
        await self.redis.publish(self.BUS_CHANNEL, json.dumps(envelope))

    async def _consume_bus(self) -> None:
        async for raw in self._pubsub.listen():
            if raw.get("type") != "message":
                continue
            try:
                envelope = json.loads(raw["data"])
            except (json.JSONDecodeError, TypeError):
                continue
            await self._deliver(envelope)

    async def _deliver(self, envelope: dict) -> None:
        route = envelope.get("route")
        message = envelope.get("message")
        if message is None:
            return
        if route == "broadcast":
            channel = envelope.get("channel")
            connections = (
                self.registry.connections_for_channel(channel) if channel else self.registry.all()
            )
            await self.transport.broadcast(connections, message)
        elif route == "direct":
            target = self.registry.get(envelope.get("target_id"))
            if target is not None:
                await self.transport.send_message(target, message)

    async def _persist(self, channel: str | None, msg_type: str, payload: dict, timestamp: str) -> None:
        await self.store.save(channel, msg_type, payload, timestamp)

    # -- HTTP -------------------------------------------------------

    async def _handle_http(self, path: str, query: dict) -> dict | None:
        """Resolve a plain HTTP GET path/query into a JSON-serializable
        response body, or None if the path isn't recognized. The transport
        is responsible for turning this into an actual protocol response."""
        if path == "/health":
            return {"connected_clients": self.registry.count()}

        if path == "/channels":
            return {"channels": await self.presence.channels()}

        if path == "/messages":
            limit = _parse_query_int(query, "limit", default=50, minimum=1, maximum=500)
            offset = _parse_query_int(query, "offset", default=0, minimum=0, maximum=2**31)
            messages = await self.store.list_messages(limit=limit, offset=offset)
            return {"messages": messages, "limit": limit, "offset": offset}

        match = CHANNEL_SUBSCRIBERS_RE.match(path)
        if match:
            channel = unquote(match.group(1))
            return {"channel": channel, "subscribers": await self.presence.subscribers(channel)}

        return None

    # -- connection lifecycle ------------------------------------------

    async def _handle_connect(self, connection: Any) -> None:
        client_id = str(uuid4())
        self._client_ids[connection] = client_id
        self.registry.add(client_id, connection)
        await self.presence.add_client(client_id, self.instance_id)
        logger.info("client %s connected", client_id)
        await self.transport.send_message(
            connection,
            make_message("system", {"event": "connected", "client_id": client_id}),
        )

    async def _handle_disconnect(self, connection: Any) -> None:
        client_id = self._client_ids.pop(connection, None)
        if client_id is None:
            return
        self.registry.remove(client_id)
        await self.presence.remove_client(client_id)
        logger.info("client %s disconnected", client_id)

    async def _handle_message(self, connection: Any, raw_message) -> None:
        client_id = self._client_ids.get(connection)
        if client_id is None:
            return
        await self._route(client_id, connection, raw_message)

    async def _route(self, client_id: str, connection: Any, raw_message) -> None:
        try:
            message = json.loads(raw_message)
        except (json.JSONDecodeError, TypeError):
            await self._send_error(connection, "invalid JSON")
            return

        if not isinstance(message, dict) or "type" not in message or "payload" not in message:
            await self._send_error(connection, "message must contain 'type' and 'payload'")
            return

        msg_type = message["type"]
        payload = message["payload"]

        if msg_type not in MESSAGE_TYPES:
            await self._send_error(connection, f"unknown message type: {msg_type}")
            return

        if not isinstance(payload, dict):
            await self._send_error(connection, "'payload' must be an object")
            return

        if msg_type == "broadcast":
            await self.broadcast(payload, sender_id=client_id)
        elif msg_type == "direct":
            await self._handle_direct(client_id, connection, payload)
        elif msg_type == "system":
            await self._send_error(connection, "'system' messages are reserved for server use")
        elif msg_type == "subscribe":
            await self._handle_subscribe(client_id, connection, payload)
        elif msg_type == "unsubscribe":
            await self._handle_unsubscribe(client_id, connection, payload)

    @staticmethod
    def _extract_channel(payload: dict) -> str | None:
        channel = payload.get("channel")
        return channel if isinstance(channel, str) and channel else None

    async def _handle_subscribe(self, client_id: str, connection: Any, payload: dict) -> None:
        channel = self._extract_channel(payload)
        if channel is None:
            await self._send_error(connection, "'channel' is required to subscribe")
            return
        self.registry.subscribe(client_id, channel)
        await self.presence.subscribe(client_id, channel)
        await self.transport.send_message(
            connection, make_message("system", {"event": "subscribed", "channel": channel})
        )

    async def _handle_unsubscribe(self, client_id: str, connection: Any, payload: dict) -> None:
        channel = self._extract_channel(payload)
        if channel is None:
            await self._send_error(connection, "'channel' is required to unsubscribe")
            return
        self.registry.unsubscribe(client_id, channel)
        await self.presence.unsubscribe(client_id, channel)
        await self.transport.send_message(
            connection, make_message("system", {"event": "unsubscribed", "channel": channel})
        )

    async def _handle_direct(self, client_id: str, connection: Any, payload: dict) -> None:
        target_id = payload.get("target_id")
        if not target_id or not await self.presence.has_client(target_id):
            await self._send_error(connection, f"target client not found: {target_id}")
            return
        message = make_message("direct", payload, sender_id=client_id)
        await self._persist(None, "direct", payload, message["timestamp"])
        await self._publish({"route": "direct", "target_id": target_id, "message": message})

    async def broadcast(self, payload: dict, sender_id: str | None = None) -> None:
        channel = self._extract_channel(payload)
        message = make_message("broadcast", payload, sender_id=sender_id)
        await self._persist(channel, "broadcast", payload, message["timestamp"])
        await self._publish({"route": "broadcast", "channel": channel, "message": message})

    async def _send_error(self, connection: Any, error: str) -> None:
        await self.transport.send_message(connection, make_message("system", {"error": error}))


async def run(host: str = "localhost", port: int = 8765) -> None:
    server = NotificationServer(host, port)
    await server.start()
    logger.info("notification server listening on %s:%s", host, port)
    await server.wait_closed()


def main() -> None:
    parser = argparse.ArgumentParser(description="Notification server")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(args.host, args.port))


if __name__ == "__main__":
    main()
