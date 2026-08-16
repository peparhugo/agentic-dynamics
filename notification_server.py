"""
Notification server core: client/channel registries, the Redis-backed
cross-instance bus, SQLite persistence, and message routing.

Accepts client connections, assigns each client a unique ID, and
supports broadcasting JSON messages to every connected client (or every
subscriber of a channel). A plain GET /health request reports the
number of currently connected clients; see transport.py for that and
the other HTTP endpoints.

How clients actually connect and receive bytes is delegated entirely to
a pluggable Transport (see transport.py): NotificationServer never
touches a raw connection object itself, only client ids. It calls
`self.transport.send_message()`/`.broadcast()` to deliver, and the
transport calls back into `handle_connect`/`handle_disconnect`/
`handle_incoming` as connection/message events happen. WebSocketTransport
is the default; the TRANSPORT env var selects a different one.

Every client registry mutation happens inside a coroutine running on the
single asyncio event loop driving this server (connection handlers,
broadcast, health check). No background thread ever touches the
registry, so the usual asyncio single-thread guarantee applies and a
plain dict is safe here. That guarantee does NOT generalize to "dict
access is always safe even from other threads" -- a dict mutated from a
real OS thread while the event loop reads it would still need a lock or
another handoff mechanism. It applies only because this design keeps all
registry access on the loop.

Redis pub/sub is the message backbone: every broadcast/direct message is
published onto a shared Redis channel (see redis_backbone.py) in addition
to being delivered directly to this instance's own locally-connected
clients. Every server instance also subscribes to that same channel, so
sibling instances (each holding a different subset of live connections)
receive the envelope and deliver it to whichever of their own local
clients should get it. That is what lets multiple server processes share
one logical set of clients. Connection and channel subscription state is
additionally mirrored into plain Redis keys as it changes, so it is
visible cluster-wide and isn't lost if one instance restarts. Every
broadcast/direct message is also persisted to SQLite (persistence.py) for
history, retrievable via GET /messages.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from persistence import MessageStore
from redis_backbone import RedisBackbone, create_redis_client
from transport import BaseTransport, Client, create_transport

logger = logging.getLogger("notification_server")

MESSAGE_TYPES = {"broadcast", "direct", "system"}

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL = os.environ.get("DATABASE_URL", "notifications.db")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ClientRegistry:
    """Tracks connected clients.

    All access happens from coroutines scheduled on the single asyncio
    event loop that runs this server (transport connect/disconnect
    hooks, broadcast, and the /health request handler). Because nothing
    outside that event loop ever touches `_clients`, plain dict
    reads/writes are safe without a lock. If a caller ever needed to
    mutate this registry from a separate OS thread, that guarantee would
    no longer hold and an asyncio.Lock (or a thread-safe handoff via
    call_soon_threadsafe) would be required.
    """

    def __init__(self) -> None:
        self._clients: dict[str, Client] = {}

    def add(self, client: Client) -> None:
        self._clients[client.client_id] = client

    def remove(self, client_id: str) -> None:
        self._clients.pop(client_id, None)

    def get(self, client_id: str) -> Optional[Client]:
        return self._clients.get(client_id)

    def all(self) -> list[Client]:
        return list(self._clients.values())

    def count(self) -> int:
        return len(self._clients)


class ChannelRegistry:
    """Tracks channel subscriptions as channel name -> set of client IDs.

    Like ClientRegistry, every mutation happens from a coroutine running on
    the single event loop that drives this server, so a plain dict of sets
    is safe without a lock.
    """

    def __init__(self) -> None:
        self._channels: dict[str, set[str]] = {}

    def subscribe(self, channel: str, client_id: str) -> None:
        self._channels.setdefault(channel, set()).add(client_id)

    def unsubscribe(self, channel: str, client_id: str) -> None:
        subscribers = self._channels.get(channel)
        if subscribers is None:
            return
        subscribers.discard(client_id)
        if not subscribers:
            del self._channels[channel]

    def unsubscribe_all(self, client_id: str) -> None:
        for channel in list(self._channels.keys()):
            self.unsubscribe(channel, client_id)

    def subscribers(self, channel: str) -> list[str]:
        return sorted(self._channels.get(channel, set()))

    def channels(self) -> dict[str, int]:
        return {name: len(subscribers) for name, subscribers in self._channels.items()}


def make_message(msg_type: str, payload: dict, timestamp: Optional[str] = None) -> dict:
    if msg_type not in MESSAGE_TYPES:
        raise ValueError(f"unsupported message type: {msg_type}")
    return {
        "type": msg_type,
        "payload": payload,
        "timestamp": timestamp or utc_now_iso(),
    }


class NotificationServer:
    def __init__(
        self,
        redis_backbone: RedisBackbone,
        message_store: MessageStore,
        instance_id: Optional[str] = None,
        transport: Optional[BaseTransport] = None,
    ) -> None:
        self.registry = ClientRegistry()
        self.channels = ChannelRegistry()
        self.redis_backbone = redis_backbone
        self.message_store = message_store
        self.instance_id = instance_id or str(uuid.uuid4())
        self.transport = transport or create_transport()
        self.transport.bind(self)
        self._bus_task: Optional[asyncio.Task] = None

    def start(self) -> None:
        """Start the background task that relays envelopes from the Redis
        bus to this instance's locally-connected clients. Must be called
        from within a running event loop."""
        if self._bus_task is None:
            self._bus_task = asyncio.create_task(self._bus_listener_loop())

    async def close(self) -> None:
        if self._bus_task is not None:
            self._bus_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._bus_task
            self._bus_task = None

    async def _bus_listener_loop(self) -> None:
        async for envelope in self.redis_backbone.listen():
            if envelope.get("origin_instance") == self.instance_id:
                # Already delivered synchronously to local clients by the
                # publish()-ing call in broadcast()/send_direct().
                continue
            try:
                await self._deliver_envelope(envelope)
            except Exception:
                logger.exception("failed to deliver bus envelope: %r", envelope)

    async def _deliver_envelope(self, envelope: dict) -> None:
        kind = envelope.get("kind")
        if kind == "broadcast":
            await self._deliver_local_broadcast(envelope["message"], envelope.get("channel"))
        elif kind == "direct":
            await self._deliver_local_direct(envelope["target_id"], envelope["message"])

    async def handle_connect(self, client_id: str) -> None:
        """Called by the transport once client_id is registered and
        reachable. Registers the client cluster-wide and sends the
        "connected" welcome message."""
        await self.redis_backbone.register_client(client_id)
        await self.transport.send_message(client_id, json.dumps(make_message(
            "system",
            {"event": "connected", "client_id": client_id},
        )))

    async def handle_disconnect(self, client_id: str) -> None:
        """Called by the transport once client_id is no longer reachable.
        Cleans up channel subscriptions and cluster-wide registration."""
        self.channels.unsubscribe_all(client_id)
        await self.redis_backbone.unregister_client(client_id)
        await self.redis_backbone.unsubscribe_all_channels(client_id)

    async def handle_incoming(self, client_id: str, raw_message: str) -> None:
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            await self.transport.send_message(client_id, json.dumps(make_message(
                "system", {"error": "invalid JSON"},
            )))
            return

        msg_type = data.get("type")
        payload = data.get("payload", {})

        if msg_type == "broadcast":
            await self.broadcast(payload, sender_id=client_id)
        elif msg_type == "direct":
            target_id = payload.get("target_id")
            await self.send_direct(target_id, payload.get("message", {}), sender_id=client_id)
        elif msg_type == "subscribe":
            await self._handle_subscribe(client_id, payload)
        elif msg_type == "unsubscribe":
            await self._handle_unsubscribe(client_id, payload)
        else:
            await self.transport.send_message(client_id, json.dumps(make_message(
                "system", {"error": f"unsupported message type: {msg_type}"},
            )))

    async def _handle_subscribe(self, client_id: str, payload: dict) -> None:
        channel = payload.get("channel")
        if not channel:
            await self.transport.send_message(client_id, json.dumps(make_message(
                "system", {"error": "channel is required"},
            )))
            return
        self.channels.subscribe(channel, client_id)
        await self.redis_backbone.subscribe_channel(channel, client_id)
        await self.transport.send_message(client_id, json.dumps(make_message(
            "system", {"event": "subscribed", "channel": channel},
        )))

    async def _handle_unsubscribe(self, client_id: str, payload: dict) -> None:
        channel = payload.get("channel")
        if not channel:
            await self.transport.send_message(client_id, json.dumps(make_message(
                "system", {"error": "channel is required"},
            )))
            return
        self.channels.unsubscribe(channel, client_id)
        await self.redis_backbone.unsubscribe_channel(channel, client_id)
        await self.transport.send_message(client_id, json.dumps(make_message(
            "system", {"event": "unsubscribed", "channel": channel},
        )))

    async def broadcast(self, payload: dict, sender_id: Optional[str] = None) -> int:
        message_dict = make_message("broadcast", {**payload, **({"sender_id": sender_id} if sender_id else {})})
        channel = payload.get("channel")
        sent = await self._deliver_local_broadcast(message_dict, channel)
        await self._persist(channel, message_dict)
        await self.redis_backbone.publish({
            "kind": "broadcast",
            "channel": channel,
            "message": message_dict,
        })
        return sent

    async def _deliver_local_broadcast(self, message_dict: dict, channel: Optional[str]) -> int:
        message = json.dumps(message_dict)
        if channel:
            client_ids = self.channels.subscribers(channel)
        else:
            client_ids = [client.client_id for client in self.registry.all()]
        return await self.transport.broadcast(client_ids, message)

    async def send_direct(self, target_id: Optional[str], payload: dict, sender_id: Optional[str] = None) -> bool:
        message_dict = make_message("direct", {**payload, **({"sender_id": sender_id} if sender_id else {})})
        delivered = await self._deliver_local_direct(target_id, message_dict)
        await self._persist(None, message_dict)
        await self.redis_backbone.publish({
            "kind": "direct",
            "target_id": target_id,
            "message": message_dict,
        })
        return delivered

    async def _deliver_local_direct(self, target_id: Optional[str], message_dict: dict) -> bool:
        if not target_id:
            return False
        return await self.transport.send_message(target_id, json.dumps(message_dict))

    async def _persist(self, channel: Optional[str], message_dict: dict) -> None:
        await self.message_store.store_message(
            channel,
            message_dict["type"],
            json.dumps(message_dict["payload"]),
            message_dict["timestamp"],
        )


def create_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    redis_client=None,
    db_path: Optional[str] = None,
    instance_id: Optional[str] = None,
    transport: Optional[BaseTransport] = None,
):
    instance_id = instance_id or str(uuid.uuid4())
    if redis_client is None:
        redis_client = create_redis_client(REDIS_URL)
    redis_backbone = RedisBackbone(redis_client, instance_id)

    message_store = MessageStore(db_path or DATABASE_URL)
    message_store.init_sync()

    server_state = NotificationServer(redis_backbone, message_store, instance_id, transport)
    server_state.start()

    ws_server = server_state.transport.serve(host, port)
    return ws_server, server_state


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ws_server, _ = create_server()
    async with ws_server:
        logger.info("notification server listening")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
